"""Explicit, offline GLiNER CPU candidate transport; importing performs no I/O."""
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
from .choice_protocol import CONTEXT_CHOICE_CONTRACT, ordered_choice_ids, validate_choice_input

MODEL_FIELDS = {"repo_id", "local_dir", "runtime_python", "assets_manifest", "prompt_path", "runtime_lock",
                "max_length", "threads", "max_rss_mb"}
PATH_FIELDS = {"local_dir", "runtime_python", "assets_manifest", "prompt_path", "runtime_lock"}
WORKER = Path(__file__).resolve().parents[1] / "bridges" / "gliner-worker.py"
CHOICE_PROTOCOL = Path(__file__).with_name("choice_protocol.py")
MAX_LINE = 1024 * 1024
INITIALIZATION_SECONDS = 120
GLINER_CHOICE_PROMPT = {"schema_version": "deposium.gliner-choice-prompt/v1", "input_protocol": "context_choice",
                       "text_field": "context", "prompt_field": "question", "labels_field": "options",
                       "output_field": "choice_id", "multi_label": False}
RUNTIME_NAMES = {"torch", "transformers", "tokenizers", "numpy", "gliner2"}


class GLiNERProfileError(ValueError):
    """Malformed explicit local GLiNER CPU settings."""


class _RuntimeLockMismatch(ValueError):
    pass


def validate_model_profile(profile: dict) -> None:
    model = profile.get("model")
    if not isinstance(model, dict) or set(model) != MODEL_FIELDS:
        raise GLiNERProfileError("GLiNER model fields do not match the local CPU profile.")
    if (profile.get("adapter") != "gliner" or profile.get("qualification") != "model_isolated"
            or profile.get("capabilities") != [CONTEXT_CHOICE_CONTRACT] or profile.get("recordings") is not None):
        raise GLiNERProfileError("GLiNER requires one isolated context-choice capability.")
    if not isinstance(profile.get("revision"), str) or not re.fullmatch(r"[0-9a-f]{40}", profile["revision"]):
        raise GLiNERProfileError("GLiNER requires an explicit pinned model revision.")
    if model["repo_id"] != "fastino/GLiNER2.5-multi-Decide":
        raise GLiNERProfileError("GLiNER profile requires the reviewed official repository.")
    for key in PATH_FIELDS:
        value = model[key]
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise GLiNERProfileError("GLiNER paths must be explicit local paths.")
    for key, ceiling in (("max_length", 4096), ("threads", 4), ("max_rss_mb", 3072)):
        if type(model[key]) is not int or not 1 <= model[key] <= ceiling:
            raise GLiNERProfileError("GLiNER CPU setting is outside its bounded range.")
    timeout = profile.get("timeout_seconds")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise GLiNERProfileError("GLiNER requires a finite positive inference timeout.")


def _canonical_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _lock_pins(text):
    """Restricted fully pinned lock syntax, including hashed CPU wheel URLs."""
    from urllib.parse import unquote, urlsplit
    pins = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(("--hash=", "--index-url ", "--extra-index-url ")):
            continue
        line = line.removesuffix("\\").strip()
        line = re.split(r"\s+--hash=", line, maxsplit=1)[0]
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.+!_-]*)", line)
        if match:
            name, version = match.groups()
        else:
            direct = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s*@\s*(https://\S+)", line)
            if not direct:
                raise ValueError("gliner_runtime_lock_unpinned")
            name, url = direct.groups()
            parts = unquote(urlsplit(url).path).rsplit("/", 1)[-1].split("-")
            if len(parts) != 5 or not parts[-1].endswith(".whl") or _canonical_name(parts[0]) != _canonical_name(name):
                raise ValueError("gliner_runtime_lock_unpinned")
            version = parts[1]
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+!_-]*", version):
                raise ValueError("gliner_runtime_lock_unpinned")
        name = _canonical_name(name)
        if name in pins:
            raise ValueError("gliner_runtime_lock_duplicate")
        pins[name] = version
    if not RUNTIME_NAMES <= set(pins):
        raise ValueError("gliner_runtime_lock_incomplete")
    return pins


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


def _fingerprint(path: Path, deadline: float | None = None) -> tuple[str, tuple]:
    if not path.is_file():
        raise FileNotFoundError("gliner_asset_missing")
    before = _stat(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("gliner_initialization_timeout")
            digest.update(chunk)
    if before != _stat(path):
        raise ValueError("gliner_asset_changed")
    return digest.hexdigest(), before


def _small_json(path: Path) -> tuple[dict, str]:
    if not path.is_file():
        raise FileNotFoundError("gliner_configuration_missing")
    if path.stat().st_size > MAX_LINE:
        raise ValueError("gliner_configuration_too_large")
    data = path.read_bytes()
    value = _decode(data)
    if not isinstance(value, dict):
        raise ValueError("gliner_configuration_invalid")
    return value, hashlib.sha256(data).hexdigest()


def _envelope(status, output=None, raw_output=None, error=None):
    return {"status": status, "output": output, "raw_output": raw_output, "error": error}


class GLiNERAdapter:
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
        self._initialization_deadline = initialized_at + INITIALIZATION_SECONDS
        self.provenance = {"profile_sha256": _digest(profile), "adapter_sha256": self._remember(Path(__file__)),
                           "adapter": "gliner", "qualification": "model_isolated", "model": dict(self._model),
                           "model_revision": profile["revision"], "capabilities": list(self.capabilities),
                           "available": False}
        deadline = initialized_at + INITIALIZATION_SECONDS
        try:
            self._prepare(profile)
            config = {"local_dir": str(self._asset_root), "prompt": self._prompt,
                      "revision": profile["revision"], "max_length": self._model["max_length"],
                      "threads": self._model["threads"]}
            environment = {"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
                           "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
                           "CUDA_VISIBLE_DEVICES": "", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
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
                if code == "gliner_runtime_missing":
                    raise FileNotFoundError(code)
                raise ValueError("gliner_initialization_failed")
            if (set(ready) != {"status", "runtime", "runtime_packages", "runtime_sources",
                              "runtime_sources_sha256", "runtime_sources_root", "load_ms", "rss_mb"}
                    or not isinstance(ready["runtime"], dict)
                    or set(ready["runtime"]) != RUNTIME_NAMES | {"python"}
                    or any(not isinstance(item, str) or not item for item in ready["runtime"].values())
                    or not self._nonnegative(ready["load_ms"]) or not self._nonnegative(ready["rss_mb"])):
                raise ValueError("gliner_invalid_ready")
            self._verify_runtime(ready)
            self._prepare_runtime_sources(ready)
            self._guard()
            if max(self._peak_rss_mb, ready["rss_mb"]) > self._model["max_rss_mb"]:
                raise MemoryError("gliner_rss_limit")
            self.provenance.update(available=True, runtime=ready["runtime"],
                                   runtime_packages=ready["runtime_packages"], runtime_lock_verified=True,
                                   load_ms=ready["load_ms"],
                                   load_rss_mb=max(self._peak_rss_mb, ready["rss_mb"]))
        except _RuntimeLockMismatch:
            self._fail("error", "gliner_runtime_lock_mismatch")
        except TimeoutError:
            self._fail("timeout", "gliner_initialization_timeout")
        except FileNotFoundError:
            self._fail("missing", "gliner_assets_or_runtime_missing")
        except MemoryError:
            self._fail("error", "gliner_rss_limit")
        except (OSError, ValueError, KeyError, TypeError):
            self._fail("error", "gliner_initialization_invalid")
        except BaseException:
            self.close()
            raise
        self._initialization_deadline = None
        self.provenance["init_wall_ms"] = (time.monotonic() - initialized_at) * 1000
        identity = {key: value for key, value in self.provenance.items()
                    if key not in {"model", "profile_sha256", "load_ms", "load_rss_mb", "init_wall_ms",
                                   "runtime_sources_root"}}
        identity["model"] = {key: value for key, value in self._model.items() if key not in PATH_FIELDS}
        self.provenance["identity_sha256"] = _digest(identity)

    @staticmethod
    def _nonnegative(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    def _remember(self, path: Path) -> str:
        digest, state = _fingerprint(path, self._initialization_deadline)
        self._states[path] = state
        return digest

    def _list_assets(self) -> set[Path]:
        root = self._paths["local_dir"].resolve()
        found = set()
        for path in root.rglob("*"):
            relative = path.relative_to(root)
            if any(part in {".cache", "__pycache__"} for part in relative.parts):
                continue
            if path.is_symlink() and (not path.resolve().is_relative_to(root) or path.is_dir()):
                raise ValueError("gliner_asset_symlink_invalid")
            if path.is_file():
                found.add(relative)
        return found

    def _verify_runtime(self, ready):
        packages = ready["runtime_packages"]
        if (not isinstance(packages, dict) or not packages or len(packages) > 10000
                or any(not isinstance(key, str) or _canonical_name(key) != key
                       or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", key)
                       or not isinstance(value, str) or not value for key, value in packages.items())):
            raise ValueError("gliner_invalid_runtime_inventory")
        if (any(packages.get(name) != version for name, version in self._pins.items())
                or any(ready["runtime"][name] != packages.get(name) for name in RUNTIME_NAMES)):
            raise _RuntimeLockMismatch("gliner_runtime_lock_mismatch")

    def _list_runtime_sources(self):
        package = self._runtime_root / "gliner2"
        found = set()
        for path in package.rglob("*"):
            relative = path.relative_to(self._runtime_root)
            if "__pycache__" in relative.parts:
                continue
            if path.is_symlink() and (not path.resolve().is_relative_to(self._runtime_root) or path.is_dir()):
                raise ValueError("gliner_runtime_source_symlink_invalid")
            if path.is_file() and path.suffix == ".py":
                found.add(relative)
        return found

    def _prepare_runtime_sources(self, ready):
        sources, root = ready["runtime_sources"], ready["runtime_sources_root"]
        if (not isinstance(root, str) or not Path(root).is_absolute() or str(Path(root).resolve()) != root
                or not isinstance(sources, dict) or not 1 <= len(sources) <= 1000
                or not {"gliner2/auto.py", "gliner2/models/boundary/model.py"} <= set(sources)):
            raise ValueError("gliner_runtime_sources_invalid")
        expected = hashlib.sha256(json.dumps(sources, sort_keys=True, ensure_ascii=False,
                                            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if ready["runtime_sources_sha256"] != expected:
            raise ValueError("gliner_runtime_source_hash_mismatch")
        self._runtime_root = Path(root)
        self._runtime_paths = set()
        total_bytes = 0
        for name, digest in sources.items():
            relative = Path(name)
            path = self._runtime_root / relative
            if (not isinstance(name, str) or not relative.parts or relative.parts[0] != "gliner2"
                    or relative.is_absolute() or relative.suffix != ".py" or relative.as_posix() != name
                    or any(part in {".", "..", "__pycache__"} for part in relative.parts)
                    or not path.resolve().is_relative_to(self._runtime_root)
                    or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                raise ValueError("gliner_runtime_sources_invalid")
            total_bytes += path.stat().st_size
            if total_bytes > 10 * 1024 * 1024 or self._remember(path) != digest:
                raise ValueError("gliner_runtime_source_hash_mismatch")
            self._runtime_paths.add(relative)
        if self._runtime_paths != self._list_runtime_sources():
            raise ValueError("gliner_unlisted_runtime_source")
        self.provenance.update(runtime_sources=sources, runtime_sources_sha256=expected,
                               runtime_sources_root=root)

    def _prepare(self, profile):
        manifest, digest = _small_json(self._paths["assets_manifest"])
        self.provenance["assets_manifest_sha256"] = digest
        if self._remember(self._paths["assets_manifest"]) != digest:
            raise ValueError("gliner_configuration_changed")
        self.provenance["assets_manifest"] = manifest
        if (set(manifest) != {"schema_version", "repo_id", "revision", "files"}
                or manifest["schema_version"] != "deposium.model-assets/v1"
                or manifest["repo_id"] != self._model["repo_id"] or manifest["revision"] != profile["revision"]
                or not isinstance(manifest["files"], list) or not manifest["files"] or len(manifest["files"]) > 10000):
            raise ValueError("gliner_assets_manifest_invalid")
        root = self._paths["local_dir"].resolve()
        self._asset_root = root
        indexed = {}
        for item in manifest["files"]:
            if not isinstance(item, dict) or set(item) != {"path", "sha256", "size"}:
                raise ValueError("gliner_assets_manifest_invalid")
            relative = Path(item["path"])
            if (not isinstance(item["path"], str) or relative.is_absolute() or not relative.parts
                    or any(part in {".", "..", ".cache", "__pycache__"} for part in relative.parts)
                    or relative.as_posix() != item["path"] or relative in self._asset_paths):
                raise ValueError("gliner_asset_path_invalid")
            path = root / relative
            if not path.resolve().is_relative_to(root) or type(item["size"]) is not int or item["size"] < 0:
                raise ValueError("gliner_asset_path_invalid")
            actual = self._remember(path)
            if actual != item["sha256"] or path.stat().st_size != item["size"]:
                raise ValueError("gliner_asset_hash_mismatch")
            self._asset_paths.add(relative)
            indexed[relative.as_posix()] = {"sha256": actual, "size": item["size"]}
        if self._asset_paths != self._list_assets():
            raise ValueError("gliner_unlisted_model_asset")
        self.provenance["model_assets_sha256"] = _digest(indexed)
        prompt, digest = _small_json(self._paths["prompt_path"])
        self.provenance["prompt_sha256"] = digest
        if self._remember(self._paths["prompt_path"]) != digest:
            raise ValueError("gliner_configuration_changed")
        self.provenance["prompt"] = prompt
        if prompt != GLINER_CHOICE_PROMPT or prompt.get("multi_label") is not False:
            raise ValueError("gliner_prompt_invalid")
        self._prompt = prompt
        if self._paths["runtime_lock"].stat().st_size > MAX_LINE:
            raise ValueError("gliner_runtime_lock_too_large")
        lock_bytes = self._paths["runtime_lock"].read_bytes()
        lock_hash = self._remember(self._paths["runtime_lock"])
        if lock_hash != hashlib.sha256(lock_bytes).hexdigest():
            raise ValueError("gliner_configuration_changed")
        self.provenance["runtime_lock"] = lock_bytes.decode("utf-8")
        self._pins = _lock_pins(self.provenance["runtime_lock"])
        self.provenance.update(prompt_schema_version=prompt["schema_version"], input_protocol=prompt["input_protocol"],
                               worker_sha256=self._remember(WORKER),
                               choice_protocol_sha256=self._remember(CHOICE_PROTOCOL),
                               runtime_python_sha256=self._remember(self._paths["runtime_python"]),
                               runtime_lock_sha256=lock_hash,
                               settings={"device": "cpu", "backend": "torch", "max_length": self._model["max_length"],
                                         "threads": self._model["threads"],
                                         "max_rss_mb": self._model["max_rss_mb"], "strict_encoding": True,
                                         "multi_label": False})

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
                        raise MemoryError("gliner_rss_limit")
                    return
        except FileNotFoundError:
            if self._process.poll() is None:
                raise OSError("gliner_rss_unavailable")

    def _guard(self):
        if (self._paths["local_dir"].resolve() != self._asset_root
                or self._asset_paths != self._list_assets()
                or self._runtime_paths != self._list_runtime_sources()
                or any(_stat(path) != state for path, state in self._states.items())):
            raise ValueError("gliner_assets_changed")
        self._rss()

    def _exchange(self, message, timeout):
        payload = _encode(message)
        if len(payload) > MAX_LINE:
            raise ValueError("gliner_request_too_large")
        if self._process is None or self._process.poll() is not None:
            raise OSError("gliner_worker_exited")
        deadline = time.monotonic() + timeout
        sent = 0
        with selectors.DefaultSelector() as selector:
            selector.register(self._process.stdin, selectors.EVENT_WRITE)
            selector.register(self._process.stdout, selectors.EVENT_READ)
            while True:
                self._rss()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("gliner_worker_timeout")
                for key, event in selector.select(min(remaining, 0.05)):
                    if event & selectors.EVENT_WRITE:
                        sent += os.write(key.fd, payload[sent:sent + 65536])
                        if sent == len(payload):
                            selector.unregister(self._process.stdin)
                    elif event & selectors.EVENT_READ:
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            raise OSError("gliner_worker_exited")
                        self._buffer.extend(chunk)
                        if len(self._buffer) > MAX_LINE:
                            raise ValueError("gliner_worker_output_too_large")
                        if b"\n" in self._buffer:
                            line, _, rest = self._buffer.partition(b"\n")
                            if rest or sent != len(payload):
                                raise ValueError("gliner_worker_protocol_invalid")
                            self._buffer.clear()
                            return _decode(line)

    def _fail(self, status, code):
        self._failure = _envelope(status, error=code)
        self.provenance.update(available=False, availability_error=code)
        self.close()

    def _audit_response(self, response, input_value):
        if (not isinstance(response, dict) or set(response) != {"sequence", "status", "output", "raw_output", "error"}
                or type(response["sequence"]) is not int or response["sequence"] != self._sequence
                or response["status"] not in {"ok", "unsupported", "error"}):
            raise ValueError("gliner_worker_protocol_invalid")
        raw = response["raw_output"]
        if response["status"] == "error":
            if response["error"] != "gliner_inference_failed" or response["output"] is not None:
                raise ValueError("gliner_worker_result_invalid")
            if raw is None:
                return
        required = {"native_result", "ordered_ids", "input_sha256", "model_text_sha256", "preprocessing",
                    "inference_ms", "decision_ms", "rss_mb", "encoding_info", "token_components", "forward_executed"}
        ids = ordered_choice_ids(input_value)
        original = input_value["context"]
        model_text = original if original.endswith((".", "!", "?")) else original + "."
        input_digest = hashlib.sha256(json.dumps(input_value, sort_keys=True, ensure_ascii=False,
                                                separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if (not isinstance(raw, dict) or set(raw) != required or raw["ordered_ids"] != ids
                or raw["input_sha256"] != input_digest
                or raw["model_text_sha256"] != hashlib.sha256(model_text.encode()).hexdigest()
                or not isinstance(raw["preprocessing"], dict)
                or set(raw["preprocessing"]) != {"appended_punctuation", "lowercase"}
                or raw["preprocessing"]["appended_punctuation"] is not (model_text != original)
                or raw["preprocessing"]["lowercase"] is not True
                or not self._nonnegative(raw["decision_ms"]) or not self._nonnegative(raw["rss_mb"])):
            raise ValueError("gliner_worker_result_invalid")
        audit, parts = raw["encoding_info"], raw["token_components"]
        if (not isinstance(audit, dict) or set(audit) != {"tokens", "stateTruncated", "optionsTruncated"}
                or type(audit["tokens"]) is not int or audit["tokens"] < 1
                or audit["stateTruncated"] is not False or audit["optionsTruncated"] is not False
                or not isinstance(parts, dict)
                or set(parts) != {"schema_tokens", "content_tokens", "total_tokens", "padded_tokens", "content_words"}
                or any(type(number) is not int or number < 0 for number in parts.values())
                or parts["schema_tokens"] + parts["content_tokens"] != parts["total_tokens"]
                or parts["total_tokens"] != audit["tokens"] or parts["padded_tokens"] != audit["tokens"]):
            raise ValueError("gliner_encoding_audit_invalid")
        if raw["rss_mb"] > self._model["max_rss_mb"]:
            raise MemoryError("gliner_rss_limit")
        if response["status"] == "error":
            if (raw["native_result"] is not None or type(raw["forward_executed"]) is not bool
                    or (raw["inference_ms"] is not None and
                        (not self._nonnegative(raw["inference_ms"]) or raw["decision_ms"] < raw["inference_ms"]))):
                raise ValueError("gliner_error_audit_invalid")
            return
        if response["status"] == "unsupported":
            if (response["error"] != "gliner_context_overflow" or response["output"] is not None
                    or raw["native_result"] is not None or raw["inference_ms"] is not None
                    or raw["forward_executed"] is not False or audit["tokens"] <= self._model["max_length"]):
                raise ValueError("gliner_overflow_audit_invalid")
            return
        native = raw["native_result"]
        if (response["error"] is not None or audit["tokens"] > self._model["max_length"]
                or raw["forward_executed"] is not True or not self._nonnegative(raw["inference_ms"])
                or raw["decision_ms"] < raw["inference_ms"]
                or not isinstance(native, dict) or set(native) != {"answer"}
                or not isinstance(native["answer"], dict) or set(native["answer"]) != {"label", "confidence"}
                or not isinstance(native["answer"]["label"], str)
                or not self._nonnegative(native["answer"]["confidence"]) or native["answer"]["confidence"] > 1):
            raise ValueError("gliner_worker_result_invalid")
        winners = [option["id"] for option in input_value["options"]
                   if option["description"] == native["answer"]["label"]]
        if len(winners) != 1 or response["output"] != {"choice_id": winners[0]}:
            raise ValueError("gliner_worker_result_invalid")

    def predict(self, request):
        if (not isinstance(request, dict) or request.get("contract_id") != CONTEXT_CHOICE_CONTRACT
                or not isinstance(request.get("input"), dict)):
            return _envelope("unsupported", error="unsupported_contract")
        validate_json(request["input"])
        _no_annotations(request["input"])
        validate_choice_input(request["input"])
        if self._failure is not None:
            return dict(self._failure)
        self._sequence += 1
        try:
            self._guard()
            response = self._exchange({"op": "predict", "sequence": self._sequence, "input": request["input"]}, self._timeout)
            self._guard()
            self._audit_response(response, request["input"])
            return {key: response[key] for key in ("status", "output", "raw_output", "error")}
        except TimeoutError:
            self._fail("timeout", "gliner_inference_timeout")
        except MemoryError:
            self._fail("error", "gliner_rss_limit")
        except FileNotFoundError:
            self._fail("missing", "gliner_runtime_missing")
        except (OSError, ValueError, TypeError, KeyError):
            self._fail("error", "gliner_runtime_or_protocol_changed")
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
