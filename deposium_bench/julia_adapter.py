"""Explicit, offline Julia CPU candidate transport; importing performs no I/O."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path
import selectors
import signal
import subprocess
import time
from typing import Any

from .cases import _json as validate_json, _no_annotations
from .choice_protocol import CONTEXT_CHOICE_CONTRACT, CONTEXT_CHOICE_PROMPT, ordered_choice_ids, validate_choice_input

MODEL_FIELDS = {"repo_id", "local_dir", "runtime_python", "assets_manifest", "prompt_path", "runtime_lock",
                "max_length", "head_length", "threads", "max_rss_mb"}
PATH_FIELDS = {"local_dir", "runtime_python", "assets_manifest", "prompt_path", "runtime_lock"}
TASKS = ["catalog", "stored_summaries", "retrieve_answer", "abstain"]
WORKER = Path(__file__).resolve().parents[1] / "bridges" / "julia-worker.py"
MAX_LINE = 1024 * 1024
INITIALIZATION_SECONDS = 120
CHOICE_PROTOCOL = Path(__file__).with_name("choice_protocol.py")
ENCODING_ERRORS = {"julia_context_overflow", "julia_head_overflow", "julia_option_overflow", "julia_reserved_marker"}


class JuliaProfileError(ValueError):
    """Malformed explicit local candidate settings."""


def validate_model_profile(profile: dict) -> None:
    model = profile.get("model")
    if not isinstance(model, dict) or set(model) != MODEL_FIELDS:
        raise JuliaProfileError("Julia model fields do not match the local CPU profile.")
    if (profile.get("adapter") != "julia" or profile.get("qualification") != "model_isolated"
            or profile.get("capabilities") not in (["mcps.document-plan"], [CONTEXT_CHOICE_CONTRACT]) or profile.get("recordings") is not None):
        raise JuliaProfileError("Julia requires one isolated document-task or context-choice capability.")
    if not isinstance(profile.get("revision"), str) or not re.fullmatch(r"[0-9a-f]{40}", profile["revision"]):
        raise JuliaProfileError("Julia requires an explicit pinned model revision.")
    if model["repo_id"] != "SupersonicLabs/Julia-1":
        raise JuliaProfileError("Julia profile requires the reviewed official repository.")
    for key in PATH_FIELDS:
        value = model[key]
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise JuliaProfileError("Julia paths must be explicit local paths.")
    for key, ceiling in (("max_length", 8192), ("head_length", 8192), ("threads", 4), ("max_rss_mb", 3072)):
        if type(model[key]) is not int or not 1 <= model[key] <= ceiling:
            raise JuliaProfileError("Julia CPU setting is outside its bounded range.")
    if model["head_length"] + 4 >= model["max_length"]:
        raise JuliaProfileError("Julia max_length must leave room beyond head_length and special tokens.")


def _encode(value: Any) -> bytes:
    validate_json(value)
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_encode(value)).hexdigest()


def _decode(data: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    value = json.loads(data, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))
    validate_json(value)
    return value


def _stat(path: Path) -> tuple:
    value = path.stat()
    return (str(path.resolve()), value.st_size, value.st_mtime_ns, value.st_ctime_ns, value.st_dev, value.st_ino)


def _fingerprint(path: Path) -> tuple[str, tuple]:
    if not path.is_file():
        raise FileNotFoundError("julia_asset_missing")
    before = _stat(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if before != _stat(path):
        raise ValueError("julia_asset_changed")
    return digest.hexdigest(), before


def _small_json(path: Path) -> tuple[dict, str]:
    if not path.is_file():
        raise FileNotFoundError("julia_configuration_missing")
    if path.stat().st_size > MAX_LINE:
        raise ValueError("julia_configuration_too_large")
    data = path.read_bytes()
    value = _decode(data)
    if not isinstance(value, dict):
        raise ValueError("julia_configuration_invalid")
    return value, hashlib.sha256(data).hexdigest()


def _envelope(status, output=None, raw_output=None, error=None):
    return {"status": status, "output": output, "raw_output": raw_output, "error": error}


class JuliaAdapter:
    """One CPU model process per adapter; serial bounded requests, explicit close."""

    def __init__(self, profile: dict, profile_path: str | Path):
        initialized_at = time.monotonic()
        validate_model_profile(profile)
        self.capabilities = list(profile["capabilities"])
        self._profile = json.loads(_encode(profile))
        self._process: subprocess.Popen | None = None
        self._buffer = bytearray()
        self._states: dict[Path, tuple] = {}
        self._asset_paths: set[Path] = set()
        self._failure = None
        self._sequence = 0
        self._peak_rss_mb = 0.0
        self._timeout = float(profile["timeout_seconds"])
        self._model = profile["model"]
        self._paths = {key: Path(profile_path).resolve().parent / self._model[key] for key in PATH_FIELDS}
        self.provenance = {"profile_sha256": _digest(profile), "adapter_sha256": self._remember(Path(__file__)),
                           "adapter": "julia", "qualification": "model_isolated", "model": dict(self._model),
                           "model_revision": profile["revision"], "capabilities": list(self.capabilities),
                           "available": False}
        self._choice_mode = self.capabilities == [CONTEXT_CHOICE_CONTRACT]
        deadline = initialized_at + INITIALIZATION_SECONDS
        try:
            self._prepare(profile)
            config = {"local_dir": str(self._paths["local_dir"].resolve()), "prompt": self._prompt,
                      "revision": profile["revision"], "max_length": self._model["max_length"],
                      "head_length": self._model["head_length"], "threads": self._model["threads"]}
            environment = {"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
                           "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
                           "CUDA_VISIBLE_DEVICES": "", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
                           "JULIA_CPU_THREADS": str(self._model["threads"]),
                           "OMP_NUM_THREADS": str(self._model["threads"]), "MKL_NUM_THREADS": str(self._model["threads"]),
                           "TOKENIZERS_PARALLELISM": "false"}
            self._process = subprocess.Popen([str(self._paths["runtime_python"]), "-I", "-B", str(WORKER)],
                                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                             env=environment, start_new_session=True)
            os.set_blocking(self._process.stdin.fileno(), False)
            os.set_blocking(self._process.stdout.fileno(), False)
            ready = self._exchange({"op": "initialize", "config": config}, max(0, deadline - time.monotonic()))
            if not isinstance(ready, dict) or ready.get("status") != "ready":
                code = ready.get("error") if isinstance(ready, dict) else None
                if code == "julia_runtime_missing":
                    raise FileNotFoundError(code)
                raise ValueError("julia_initialization_failed")
            if (set(ready) != {"status", "runtime", "load_ms", "rss_mb"}
                    or not isinstance(ready["runtime"], dict)
                    or set(ready["runtime"]) != {"python", "torch", "transformers", "tokenizers", "numpy"}
                    or any(not isinstance(item, str) or not item for item in ready["runtime"].values())
                    or not self._nonnegative(ready["load_ms"]) or not self._nonnegative(ready["rss_mb"])):
                raise ValueError("julia_invalid_ready")
            self._guard()
            if max(self._peak_rss_mb, ready["rss_mb"]) > self._model["max_rss_mb"]:
                raise MemoryError("julia_rss_limit")
            self.provenance.update(available=True, runtime=ready["runtime"], load_ms=ready["load_ms"],
                                   load_rss_mb=max(self._peak_rss_mb, ready["rss_mb"]))
        except TimeoutError:
            self._fail("timeout", "julia_initialization_timeout")
        except FileNotFoundError:
            self._fail("missing", "julia_assets_or_runtime_missing")
        except MemoryError:
            self._fail("error", "julia_rss_limit")
        except (OSError, ValueError, KeyError, TypeError):
            self._fail("error", "julia_initialization_invalid")
        except BaseException:
            self.close()
            raise
        self.provenance["init_wall_ms"] = (time.monotonic() - initialized_at) * 1000
        identity = {key: value for key, value in self.provenance.items()
                    if key not in {"model", "profile_sha256", "load_ms", "load_rss_mb", "init_wall_ms"}}
        identity["model"] = {key: value for key, value in self._model.items() if key not in PATH_FIELDS}
        self.provenance["identity_sha256"] = _digest(identity)

    @staticmethod
    def _nonnegative(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    def _remember(self, path: Path) -> str:
        digest, state = _fingerprint(path)
        self._states[path] = state
        return digest

    def _list_assets(self) -> set[Path]:
        root = self._paths["local_dir"].resolve()
        return {path.relative_to(root) for path in root.rglob("*")
                if path.is_file() and not any(part in {".cache", "__pycache__"} for part in path.relative_to(root).parts)}

    def _prepare(self, profile):
        manifest, digest = _small_json(self._paths["assets_manifest"])
        self.provenance["assets_manifest_sha256"] = digest
        if self._remember(self._paths["assets_manifest"]) != digest:
            raise ValueError("julia_configuration_changed")
        self.provenance["assets_manifest"] = manifest
        if (set(manifest) != {"schema_version", "repo_id", "revision", "files"}
                or manifest["schema_version"] != "deposium.model-assets/v1"
                or manifest["repo_id"] != self._model["repo_id"] or manifest["revision"] != profile["revision"]
                or not isinstance(manifest["files"], list) or not manifest["files"] or len(manifest["files"]) > 10000):
            raise ValueError("julia_assets_manifest_invalid")
        root = self._paths["local_dir"].resolve()
        indexed = {}
        for item in manifest["files"]:
            if not isinstance(item, dict) or set(item) != {"path", "sha256", "size"}:
                raise ValueError("julia_assets_manifest_invalid")
            relative = Path(item["path"])
            if (not isinstance(item["path"], str) or relative.is_absolute() or not relative.parts
                    or any(part in {".", "..", ".cache", "__pycache__"} for part in relative.parts)
                    or relative.as_posix() != item["path"] or relative in self._asset_paths):
                raise ValueError("julia_asset_path_invalid")
            path = root / relative
            if not path.resolve().is_relative_to(root) or type(item["size"]) is not int or item["size"] < 0:
                raise ValueError("julia_asset_path_invalid")
            actual = self._remember(path)
            if actual != item["sha256"] or path.stat().st_size != item["size"]:
                raise ValueError("julia_asset_hash_mismatch")
            self._asset_paths.add(relative)
            indexed[relative.as_posix()] = {"sha256": actual, "size": item["size"]}
        if self._asset_paths != self._list_assets():
            raise ValueError("julia_unlisted_model_asset")
        self.provenance["model_assets_sha256"] = _digest(indexed)
        prompt, digest = _small_json(self._paths["prompt_path"])
        self.provenance["prompt_sha256"] = digest
        if self._remember(self._paths["prompt_path"]) != digest:
            raise ValueError("julia_configuration_changed")
        self.provenance["prompt"] = prompt
        if self._choice_mode:
            if prompt != CONTEXT_CHOICE_PROMPT:
                raise ValueError("julia_prompt_invalid")
        else:
            if (set(prompt) != {"schema_version", "input_protocol", "question", "options", "order"}
                    or prompt["schema_version"] != "deposium.document-task-prompt/v1"
                    or prompt["input_protocol"] != "current_equivalent"
                    or not isinstance(prompt["question"], str) or not prompt["question"].strip()
                    or prompt["order"] not in {"canonical", "reversed"} or not isinstance(prompt["options"], list)
                    or len(prompt["options"]) != len(TASKS)):
                raise ValueError("julia_prompt_invalid")
            for option in prompt["options"]:
                if (not isinstance(option, dict) or set(option) != {"id", "description"}
                        or not isinstance(option["description"], str) or not option["description"].strip()):
                    raise ValueError("julia_prompt_invalid")
            ordered = TASKS if prompt["order"] == "canonical" else list(reversed(TASKS))
            if [item["id"] for item in prompt["options"]] != ordered:
                raise ValueError("julia_prompt_invalid")
        self._prompt = prompt
        if self._paths["runtime_lock"].stat().st_size > MAX_LINE:
            raise ValueError("julia_runtime_lock_too_large")
        lock_bytes = self._paths["runtime_lock"].read_bytes()
        lock_hash = self._remember(self._paths["runtime_lock"])
        if lock_hash != hashlib.sha256(lock_bytes).hexdigest():
            raise ValueError("julia_configuration_changed")
        self.provenance["runtime_lock"] = lock_bytes.decode("utf-8")
        self.provenance.update(prompt_schema_version=prompt["schema_version"], input_protocol=prompt["input_protocol"],
                               worker_sha256=self._remember(WORKER),
                               choice_protocol_sha256=self._remember(CHOICE_PROTOCOL),
                               runtime_python_sha256=self._remember(self._paths["runtime_python"]),
                               runtime_lock_sha256=lock_hash,
                               settings={"device": "cpu", "backend": "torch", "max_length": self._model["max_length"],
                                         "head_length": self._model["head_length"], "threads": self._model["threads"],
                                         "max_rss_mb": self._model["max_rss_mb"], "strict_encoding": True,
                                         "marker_only_head": False})

    def _rss(self):
        if self._process is None:
            return
        status = Path(f"/proc/{self._process.pid}/status")
        try:
            for line in status.read_text().splitlines():
                if line.startswith("VmRSS:"):
                    rss = int(line.split()[1]) / 1024
                    self._peak_rss_mb = max(self._peak_rss_mb, rss)
                    if rss > self._model["max_rss_mb"]:
                        raise MemoryError("julia_rss_limit")
                    return
        except FileNotFoundError:
            if self._process.poll() is None:
                raise OSError("julia_rss_unavailable")

    def _guard(self):
        if self._asset_paths != self._list_assets() or any(_stat(path) != state for path, state in self._states.items()):
            raise ValueError("julia_assets_changed")
        self._rss()

    def _exchange(self, message, timeout):
        payload = _encode(message)
        if len(payload) > MAX_LINE:
            raise ValueError("julia_request_too_large")
        if self._process is None or self._process.poll() is not None:
            raise OSError("julia_worker_exited")
        deadline = time.monotonic() + timeout
        sent = 0
        with selectors.DefaultSelector() as selector:
            selector.register(self._process.stdin, selectors.EVENT_WRITE)
            selector.register(self._process.stdout, selectors.EVENT_READ)
            while True:
                self._rss()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("julia_worker_timeout")
                for key, event in selector.select(min(remaining, 0.05)):
                    if event & selectors.EVENT_WRITE:
                        sent += os.write(key.fd, payload[sent:sent + 65536])
                        if sent == len(payload):
                            selector.unregister(self._process.stdin)
                    elif event & selectors.EVENT_READ:
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            raise OSError("julia_worker_exited")
                        self._buffer.extend(chunk)
                        if len(self._buffer) > MAX_LINE:
                            raise ValueError("julia_worker_output_too_large")
                        if b"\n" in self._buffer:
                            line, _, rest = self._buffer.partition(b"\n")
                            if rest or sent != len(payload):
                                raise ValueError("julia_worker_protocol_invalid")
                            self._buffer.clear()
                            return _decode(line)

    def _fail(self, status, code):
        self._failure = _envelope(status, error=code)
        self.provenance.update(available=False, availability_error=code)
        self.close()

    def predict(self, request):
        if (not isinstance(request, dict) or not isinstance(request.get("contract_id"), str)
                or not isinstance(request.get("input"), dict)):
            raise JuliaProfileError("Candidate request is invalid.")
        if request["contract_id"] not in self.capabilities:
            return _envelope("unsupported", error="unsupported_contract")
        validate_json(request["input"])
        _no_annotations(request["input"])
        if self._choice_mode:
            validate_choice_input(request["input"])
        if self._failure is not None:
            return dict(self._failure)
        self._sequence += 1
        try:
            self._guard()
            response = self._exchange({"op": "predict", "sequence": self._sequence, "input": request["input"]}, self._timeout)
            self._guard()
            if (not isinstance(response, dict) or set(response) != {"sequence", "status", "output", "raw_output", "error"}
                    or type(response["sequence"]) is not int or response["sequence"] != self._sequence
                    or response["status"] not in {"ok", "abstain", "error"}):
                raise ValueError("julia_worker_protocol_invalid")
            raw = response["raw_output"]
            if response["status"] == "error":
                if response["error"] not in ENCODING_ERRORS | {"julia_inference_failed"} or response["output"] is not None:
                    raise ValueError("julia_worker_result_invalid")
                if response["error"] in ENCODING_ERRORS:
                    if (not isinstance(raw, dict) or set(raw) != {"decision_ms", "inference_ms", "forward_executed"}
                            or not self._nonnegative(raw["decision_ms"]) or raw["inference_ms"] is not None
                            or raw["forward_executed"] is not False):
                        raise ValueError("julia_worker_result_invalid")
                elif raw is not None:
                    raise ValueError("julia_worker_result_invalid")
            else:
                ids = ordered_choice_ids(request["input"]) if self._choice_mode else [option["id"] for option in self._prompt["options"]]
                count = len(ids)
                required = {"logits", "probabilities", "ordered_ids", "input_sha256", "inference_ms", "decision_ms", "rss_mb", "encoding_info"}
                if (response["error"] is not None or not isinstance(raw, dict) or not required <= set(raw)
                        or set(raw) - required - {"token_components"} or raw["ordered_ids"] != ids
                        or raw["input_sha256"] != hashlib.sha256(json.dumps(request["input"], sort_keys=True, ensure_ascii=False,
                                                                          separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                        or not self._nonnegative(raw["inference_ms"]) or not self._nonnegative(raw["decision_ms"])
                        or raw["decision_ms"] < raw["inference_ms"] or not self._nonnegative(raw["rss_mb"])
                        or not isinstance(raw["logits"], list) or len(raw["logits"]) != count
                        or not isinstance(raw["probabilities"], list) or len(raw["probabilities"]) != count
                        or any(type(value) not in (int, float) or not math.isfinite(value) for value in raw["logits"])
                        or any(not self._nonnegative(value) or value > 1 for value in raw["probabilities"])):
                    raise ValueError("julia_worker_result_invalid")
                encoding = raw["encoding_info"]
                if (not isinstance(encoding, dict) or set(encoding) != {"tokens", "optionTokens", "headLength", "stateTruncated", "optionsTruncated"}
                        or type(encoding["tokens"]) is not int or not 1 <= encoding["tokens"] <= self._model["max_length"]
                        or type(encoding["headLength"]) is not int or encoding["headLength"] != self._model["head_length"]
                        or not isinstance(encoding["optionTokens"], list) or len(encoding["optionTokens"]) != count
                        or any(type(number) is not int or not 1 <= number <= 48 for number in encoding["optionTokens"])
                        or encoding["stateTruncated"] is not False or encoding["optionsTruncated"] is not False):
                    raise ValueError("julia_encoding_audit_invalid")
                if "token_components" in raw:
                    components = raw["token_components"]
                    if (not isinstance(components, dict) or set(components) != {"state", "question", "options", "special", "total", "padded"}
                            or any(type(components[key]) is not int or components[key] < 0 for key in ("state", "question", "special", "total", "padded"))
                            or components["options"] != encoding["optionTokens"] or components["special"] != count + 4
                            or components["total"] != encoding["tokens"]
                            or components["state"] + components["question"] + sum(components["options"]) + components["special"] != components["total"]
                            or components["padded"] != min(self._model["max_length"], ((encoding["tokens"] + 7) // 8) * 8)):
                        raise ValueError("julia_token_components_invalid")
                exponents = [math.exp(value - max(raw["logits"])) for value in raw["logits"]]
                if any(abs(probability - exponent / sum(exponents)) > 1e-10
                       for probability, exponent in zip(raw["probabilities"], exponents)):
                    raise ValueError("julia_probabilities_invalid")
                if raw["rss_mb"] > self._model["max_rss_mb"]:
                    raise MemoryError("julia_rss_limit")
                winner = ids[max(range(count), key=lambda i: raw["logits"][i])]
                status = "ok" if self._choice_mode or winner != "abstain" else "abstain"
                output = {"choice_id": winner} if self._choice_mode else (None if winner == "abstain" else {"task": winner})
                if response["status"] != status or response["output"] != output:
                    raise ValueError("julia_worker_result_invalid")
            return {key: response[key] for key in ("status", "output", "raw_output", "error")}
        except TimeoutError:
            self._fail("timeout", "julia_inference_timeout")
        except MemoryError:
            self._fail("error", "julia_rss_limit")
        except FileNotFoundError:
            self._fail("missing", "julia_runtime_missing")
        except (OSError, ValueError, TypeError, KeyError):
            self._fail("error", "julia_runtime_or_protocol_changed")
        except BaseException:
            self.close()
            raise
        return dict(self._failure)

    def close(self):
        process = self._process
        if process is None:
            return
        self._process = None
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=1)
        finally:
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()
