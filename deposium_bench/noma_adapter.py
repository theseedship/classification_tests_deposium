"""Explicit offline Noma CPU candidate; importing this module loads no model."""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

from .cases import _no_annotations
from .choice_protocol import CONTEXT_CHOICE_CONTRACT, CONTEXT_CHOICE_PROMPT, ordered_choice_ids, validate_choice_input
from .decision2_adapter import _hash, _lock_pins, Decision2Adapter
from .worker_transport import MAX_LINE, decode, exchange, wire

REPO_ID = "BlackdromeAILabs/noma"
REVISION = "fac0429688a137ce451a27ad34d05e9fd47fb624"
SOURCE_REPO = "blackdromeai-labs/noma"
SOURCE_REVISION = "8cfda260d8af88c18b1de1852e13dcbe9958042f"
REFERENCE_TIME = "2026-10-03T00:00:00Z"
ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "bridges/noma-worker.py"
PATH_FIELDS = {"local_dir", "source_dir", "runtime_python", "assets_manifest", "source_manifest", "prompt_path", "runtime_lock"}
MODEL_FIELDS = PATH_FIELDS | {"repo_id", "source_revision", "max_length", "threads", "max_rss_mb"}


def validate_model_profile(profile):
    model = profile.get("model") if isinstance(profile, dict) else None
    if (not isinstance(model, dict) or set(model) != MODEL_FIELDS
            or profile.get("adapter") != "noma" or profile.get("qualification") != "model_isolated"
            or profile.get("capabilities") != [CONTEXT_CHOICE_CONTRACT] or profile.get("recordings") is not None
            or profile.get("revision") != REVISION or model["repo_id"] != REPO_ID
            or model["source_revision"] != SOURCE_REVISION):
        raise ValueError("noma_profile_identity_invalid")
    for name in PATH_FIELDS:
        if not isinstance(model[name], str) or not model[name].strip() or "\0" in model[name]:
            raise ValueError("noma_profile_path_invalid")
    for name, cap in (("max_length", 1024), ("threads", 2), ("max_rss_mb", 8192)):
        if type(model[name]) is not int or not 1 <= model[name] <= cap:
            raise ValueError("noma_profile_limit_invalid")
    timeout = profile.get("timeout_seconds")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise ValueError("noma_profile_timeout_invalid")


def envelope(status, *, output=None, raw_output=None, error=None):
    return dict(status=status, output=output, raw_output=raw_output, error=error)


def _nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


class NomaAdapter:
    def __init__(self, profile, profile_path):
        started = time.monotonic()
        validate_model_profile(profile)
        self._profile = decode(wire(profile))
        self._model = self._profile["model"]
        self.capabilities = list(profile["capabilities"])
        self._paths = {key: Path(os.path.abspath(Path(profile_path).parent / self._model[key])) for key in PATH_FIELDS}
        self._process = None
        self._cache = None
        self._closed = False
        self._failure = None
        self._sequence = 0
        self._states = {}
        self._inventories = {}
        self._peak_rss_mb = 0.0
        self.provenance = dict(adapter="noma", qualification="model_isolated", available=False,
                               model=dict(self._model), model_revision=REVISION, model_repo_id=REPO_ID,
                               source_revision=SOURCE_REVISION, capabilities=self.capabilities,
                               profile_sha256=hashlib.sha256(wire(profile)).hexdigest())
        try:
            deadline = started + 120
            for name, path in (("adapter", Path(__file__)), ("worker", WORKER),
                               ("choice_protocol", ROOT / "deposium_bench/choice_protocol.py"),
                               ("transport", ROOT / "deposium_bench/worker_transport.py"),
                               ("asset_helpers", ROOT / "deposium_bench/decision2_adapter.py")):
                self.provenance[name + "_sha256"] = self._remember(path, deadline)
            self._prepare(deadline)
            if self._available() < self._model["max_rss_mb"] + 2048:
                raise MemoryError("noma_host_memory_low")
            cache_parent = ROOT / "results/.cache/noma-worker"
            cache_parent.mkdir(parents=True, exist_ok=True)
            self._cache = tempfile.TemporaryDirectory(dir=cache_parent)
            cache = self._cache.name
            env = {"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
                   "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
                   "HF_HUB_DISABLE_TELEMETRY": "1", "CUDA_VISIBLE_DEVICES": "", "TOKENIZERS_PARALLELISM": "false",
                   "HF_HOME": cache, "XDG_CACHE_HOME": cache, "TMPDIR": cache,
                   "OMP_NUM_THREADS": str(self._model["threads"]), "MKL_NUM_THREADS": str(self._model["threads"])}
            command = [str(self._paths["runtime_python"]), "-I", "-B", "-X", f"pycache_prefix={cache}/pycache", str(WORKER)]
            self._process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                             stderr=subprocess.DEVNULL, env=env, cwd=ROOT, start_new_session=True)
            os.set_blocking(self._process.stdin.fileno(), False)
            os.set_blocking(self._process.stdout.fileno(), False)
            ready = exchange(self._process, {"op": "initialize", "config": {
                "source_dir": str(self._paths["source_dir"]), "local_dir": str(self._paths["local_dir"]),
                "max_length": self._model["max_length"], "threads": self._model["threads"], "pins": self._pins}},
                timeout_seconds=max(0, deadline-time.monotonic()), monitor=self._monitor, error_prefix="noma")
            if isinstance(ready, dict) and ready.get("status") == "error":
                raise ValueError(self._error_code(ready.get("error"), "noma_initialization_failed"))
            if (not isinstance(ready, dict) or set(ready) != {"status", "runtime", "load_ms", "rss_mb", "native_max_prefix_tokens", "dtype", "device", "facts_version"}
                    or ready["status"] != "ready" or ready["device"] != "cpu" or ready["dtype"] != "bfloat16"
                    or ready["facts_version"] != "facts-0.2" or ready["native_max_prefix_tokens"] != 4096
                    or not isinstance(ready["runtime"], dict)
                    or ready["runtime"].get("noma-source") != "1.0.1"
                    or any(ready["runtime"].get(key) != value for key, value in self._pins.items())
                    or not _nonnegative(ready["load_ms"]) or not _nonnegative(ready["rss_mb"])):
                raise ValueError("noma_ready_invalid")
            if ready["rss_mb"] > self._model["max_rss_mb"]:
                raise MemoryError("noma_rss_limit")
            self._guard()
            self.provenance.update(available=True, runtime=ready["runtime"], device="cpu", dtype="bfloat16",
                                   native_max_prefix_tokens=4096, effective_max_input_tokens=self._model["max_length"],
                                   load_ms=ready["load_ms"], load_rss_mb=max(ready["rss_mb"], self._peak_rss_mb))
        except TimeoutError:
            self._fail("timeout", "noma_initialization_timeout")
        except MemoryError as exc:
            self._fail("error", self._error_code(str(exc), "noma_rss_limit"))
        except FileNotFoundError:
            self._fail("missing", "noma_assets_or_runtime_missing")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self._fail("error", self._error_code(str(exc), "noma_initialization_invalid"))
        except BaseException:
            self.close()
            raise
        finally:
            identity = {k: v for k, v in self.provenance.items() if k.endswith("_sha256") and k != "identity_sha256"}
            identity.update(model_revision=REVISION, source_revision=SOURCE_REVISION, settings=self.provenance.get("settings"))
            self.provenance["identity_sha256"] = hashlib.sha256(wire(identity)).hexdigest()
            self.provenance["init_wall_ms"] = (time.monotonic()-started)*1000

    @staticmethod
    def _error_code(code, fallback):
        return code if isinstance(code, str) and re.fullmatch(r"noma_[a-z0-9_]{1,85}", code) else fallback

    def _remember(self, path, deadline=None, *, symlink=False):
        if (path.is_symlink() and not symlink) or not path.is_file():
            raise FileNotFoundError("noma_asset_missing")
        digest, state = _hash(path, deadline)
        self._states[path] = state
        return digest

    def _read(self, path, deadline):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_LINE:
            raise ValueError("noma_configuration_file_invalid")
        before = path.stat()
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            data = stream.read(MAX_LINE+1)
            finished = os.fstat(stream.fileno())
        after = path.stat()
        state = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if (state(before) != state(opened) or state(before) != state(finished)
                or state(before) != state(after) or len(data) > MAX_LINE):
            raise ValueError("noma_configuration_changed")
        if time.monotonic() > deadline:
            raise TimeoutError("noma_initialization_timeout")
        self._states[path] = state(after)
        return data, hashlib.sha256(data).hexdigest()

    @staticmethod
    def _inventory(root):
        found = set()
        for path in root.rglob("*"):
            relative = path.relative_to(root)
            if any(p in {".git", ".cache", "__pycache__"} for p in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError("noma_asset_symlink")
            if path.is_file():
                found.add(relative.as_posix())
        return found

    def _bundle(self, root_key, manifest_key, repo_id, revision, deadline):
        root = self._paths[root_key]
        if root.is_symlink() or not root.is_dir():
            raise FileNotFoundError("noma_assets_missing")
        data, digest = self._read(self._paths[manifest_key], deadline)
        manifest = decode(data)
        if (not isinstance(manifest, dict) or set(manifest) != {"schema_version", "repo_id", "revision", "files"}
                or manifest["schema_version"] != "deposium.model-assets/v1" or manifest["repo_id"] != repo_id
                or manifest["revision"] != revision or not isinstance(manifest["files"], list)
                or not 1 <= len(manifest["files"]) <= 10000):
            raise ValueError("noma_asset_manifest_invalid")
        names = set()
        for item in manifest["files"]:
            if not isinstance(item, dict) or set(item) != {"path", "sha256", "size"}:
                raise ValueError("noma_asset_manifest_invalid")
            name = item["path"]
            relative = Path(name) if isinstance(name, str) else Path(".")
            if (not isinstance(name, str) or relative.is_absolute() or not relative.parts
                    or relative.as_posix() != name or any(x in {".", "..", ".git", ".cache", "__pycache__"} for x in relative.parts)
                    or name in names or type(item["size"]) is not int or item["size"] < 0
                    or not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
                raise ValueError("noma_asset_path_invalid")
            path = root / relative
            if (not path.resolve().is_relative_to(root.resolve()) or self._remember(path, deadline) != item["sha256"]
                    or path.stat().st_size != item["size"]):
                raise ValueError("noma_asset_hash_mismatch")
            names.add(name)
        if self._inventory(root) != names:
            raise ValueError("noma_asset_inventory_changed")
        self._inventories[root] = names
        return manifest, digest

    def _prepare(self, deadline):
        model, digest = self._bundle("local_dir", "assets_manifest", REPO_ID, REVISION, deadline)
        self.provenance.update(model_assets=model, assets_manifest_sha256=digest,
                               model_assets_sha256=hashlib.sha256(wire(model)).hexdigest())
        source, digest = self._bundle("source_dir", "source_manifest", SOURCE_REPO, SOURCE_REVISION, deadline)
        self.provenance.update(source_assets=source, source_manifest_sha256=digest,
                               source_assets_sha256=hashlib.sha256(wire(source)).hexdigest())
        prompt, digest = self._read(self._paths["prompt_path"], deadline)
        if decode(prompt) != CONTEXT_CHOICE_PROMPT:
            raise ValueError("noma_prompt_invalid")
        self.provenance["prompt_sha256"] = digest
        lock, digest = self._read(self._paths["runtime_lock"], deadline)
        self._pins = _lock_pins(lock.decode())
        self.provenance.update(runtime_pins=self._pins, runtime_lock_sha256=digest,
                               runtime_python_sha256=self._remember(self._paths["runtime_python"], deadline, symlink=True),
                               settings={"device": "cpu", "dtype": "bfloat16", "threads": self._model["threads"],
                                         "max_length": self._model["max_length"], "max_rss_mb": self._model["max_rss_mb"],
                                         "facts": True, "reference_time": REFERENCE_TIME, "fork": False,
                                         "encoding_preflight": "official-noma-serializer"})

    @staticmethod
    def _available():
        return Decision2Adapter._host_available_mb()

    def _monitor(self):
        if self._process is not None:
            try:
                for line in Path(f"/proc/{self._process.pid}/status").read_text().splitlines():
                    if line.startswith(("VmRSS:", "VmHWM:")):
                        self._peak_rss_mb = max(self._peak_rss_mb, int(line.split()[1])/1024)
            except FileNotFoundError:
                if self._process.poll() is None:
                    raise OSError("noma_rss_unavailable")
            if self._peak_rss_mb > self._model["max_rss_mb"]:
                raise MemoryError("noma_rss_limit")
        if self._available() < 2048:
            raise MemoryError("noma_host_memory_low")

    def _guard(self):
        for path, expected in self._states.items():
            s = path.stat()
            if (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns) != expected:
                raise ValueError("noma_assets_changed")
        for root, names in self._inventories.items():
            if root.is_symlink() or self._inventory(root) != names:
                raise ValueError("noma_asset_inventory_changed")
        self._monitor()

    def _audit(self, response, value):
        if (not isinstance(response, dict) or set(response) != {"sequence", "status", "output", "raw_output", "error"}
                or type(response["sequence"]) is not int or response["sequence"] != self._sequence
                or response["status"] not in {"ok", "unsupported", "error"}):
            raise ValueError("noma_worker_protocol_invalid")
        raw = response["raw_output"]
        if response["status"] == "error" and raw is None and response["output"] is None:
            if self._error_code(response["error"], None) is None:
                raise ValueError("noma_error_invalid")
            return
        if (not isinstance(raw, dict) or set(raw) != {"native_result", "native_tokens", "input_sha256", "ordered_ids", "encoding_info", "forward_executed", "decision_ms", "inference_ms", "rss_mb"}
                or raw["ordered_ids"] != ordered_choice_ids(value)
                or raw["input_sha256"] != hashlib.sha256(wire(value)).hexdigest()
                or not _nonnegative(raw["decision_ms"]) or not _nonnegative(raw["rss_mb"])
                or type(raw["native_tokens"]) is not int or raw["native_tokens"] < 0):
            raise ValueError("noma_result_invalid")
        if raw["rss_mb"] > self._model["max_rss_mb"]:
            raise MemoryError("noma_rss_limit")
        info = raw["encoding_info"]
        if (not isinstance(info, dict) or set(info) != {"tokens", "prefix_tokens", "block_tokens", "prefix_truncated", "prefix_uncapped_equal", "forward_count", "forward_ids_equal", "facts_version", "reference_time", "fact_lines"}
                or any(type(info[k]) is not int or info[k] < 0 for k in ("tokens", "prefix_tokens", "block_tokens", "forward_count"))
                or info["tokens"] < 1 or info["tokens"] != info["prefix_tokens"]+info["block_tokens"]
                or any(type(info[k]) is not bool for k in ("prefix_truncated", "prefix_uncapped_equal", "forward_ids_equal"))
                or info["facts_version"] != "facts-0.2" or info["reference_time"] != REFERENCE_TIME
                or not isinstance(info["fact_lines"], list) or any(not isinstance(x, str) for x in info["fact_lines"])):
            raise ValueError("noma_encoding_invalid")
        if response["status"] == "unsupported":
            if (response["error"] != "noma_context_overflow" or response["output"] is not None
                    or raw["native_result"] is not None or raw["forward_executed"] is not False
                    or raw["inference_ms"] is not None or raw["native_tokens"] != 0 or info["forward_count"] != 0
                    or not (info["prefix_truncated"] or not info["prefix_uncapped_equal"] or info["tokens"] > self._model["max_length"])):
                raise ValueError("noma_overflow_invalid")
            return
        if response["status"] == "error":
            if response["output"] is not None or self._error_code(response["error"], None) is None:
                raise ValueError("noma_error_invalid")
            return
        native = raw["native_result"]
        if (response["error"] is not None or info["prefix_truncated"] or not info["prefix_uncapped_equal"]
                or info["forward_count"] != 1 or not info["forward_ids_equal"] or raw["forward_executed"] is not True
                or raw["native_tokens"] != info["tokens"] or info["tokens"] > self._model["max_length"]
                or not _nonnegative(raw["inference_ms"]) or raw["decision_ms"] < raw["inference_ms"]
                or not isinstance(native, dict) or set(native) != {"probabilities", "abstain", "uncertainty"}):
            raise ValueError("noma_native_invalid")
        probs = native["probabilities"]
        keys = [f"c{i}" for i in range(len(value["options"]))]
        if (not isinstance(probs, dict) or list(probs) != keys
                or any(not _nonnegative(p) or p > 1 for p in probs.values()) or abs(sum(probs.values())-1) > 1e-4
                or not _nonnegative(native["abstain"]) or native["abstain"] > 1 or not _nonnegative(native["uncertainty"])):
            raise ValueError("noma_distribution_invalid")
        winner = max(keys, key=probs.get)
        if response["output"] != {"choice_id": value["options"][keys.index(winner)]["id"]}:
            raise ValueError("noma_choice_invalid")

    def predict(self, request):
        if not isinstance(request, dict) or request.get("contract_id") != CONTEXT_CHOICE_CONTRACT:
            return envelope("unsupported", error="unsupported_contract")
        value = request.get("input")
        validate_choice_input(value)
        _no_annotations(value)
        if self._failure is not None:
            return {**self._failure, "raw_output": {"forward_executed": False, "cached_failure": True}}
        if self._closed:
            return envelope("error", error="noma_adapter_closed", raw_output={"forward_executed": False})
        message = {"op": "predict", "sequence": self._sequence+1, "input": value}
        if len(wire(message)) > MAX_LINE:
            return envelope("unsupported", error="noma_request_too_large", raw_output={"forward_executed": False})
        self._sequence += 1
        try:
            self._guard()
            response = exchange(self._process, message, timeout_seconds=self._profile["timeout_seconds"], monitor=self._monitor, error_prefix="noma")
            self._guard()
            self._audit(response, value)
            return {k: response[k] for k in ("status", "output", "raw_output", "error")}
        except TimeoutError:
            self._fail("timeout", "noma_inference_timeout")
        except MemoryError as exc:
            self._fail("error", self._error_code(str(exc), "noma_rss_limit"))
        except FileNotFoundError:
            self._fail("missing", "noma_assets_or_runtime_missing")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self._fail("error", self._error_code(str(exc), "noma_runtime_or_protocol_changed"))
        except BaseException:
            self.close()
            raise
        return dict(self._failure)

    def _fail(self, status, code):
        self._failure = envelope(status, error=code)
        self.provenance.update(available=False, availability_error=code)
        self.close()

    def close(self):
        self._closed = True
        process, self._process = self._process, None
        if process is not None:
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
                for stream in (process.stdin, process.stdout):
                    if stream:
                        stream.close()
        if self._cache is not None:
            self._cache.cleanup()
            self._cache = None
