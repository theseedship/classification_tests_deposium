"""Bounded, offline transport for the released Vela2 CPU runtime.

Importing this module never imports or downloads a model. Both processes verify
the pinned local asset inventory before the child imports publisher code.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

from .cases import _json as validate_json, _no_annotations
from .choice_protocol import CONTEXT_CHOICE_CONTRACT, CONTEXT_CHOICE_PROMPT, ordered_choice_ids, validate_choice_input
from .worker_transport import MAX_LINE, decode as _decode, exchange, wire as _wire

MODEL_FIELDS = {"repo_id", "local_dir", "runtime_python", "assets_manifest", "prompt_path",
                "runtime_lock", "max_length", "threads", "max_rss_mb"}
PATH_FIELDS = {"local_dir", "runtime_python", "assets_manifest", "prompt_path", "runtime_lock"}
REPO_ID = "vllm-sr/Vela-2.0-0.3B"
MODELS = {
    REPO_ID: ("d6f03aa9baca4f9017fa8f8e9c2764d3bed3f409", REPO_ID, 8192),
    "vllm-sr/Vela-2.0-0.8B": ("326b01d81f61fff7fd4ae570e54b87a49119e490",
                                "vllm-sr/Vela-2.0-0.8B", 16384),
    "vllm-sr/Vela-2.0-4B": ("d692394127f6f87fc581d8634c9558fe4776efce",
                            "vllm-sr/Vela-2.0-4B", 16384),
}
VELA4_REPO_ID = "vllm-sr/Vela-2.0-4B"
WORKER = Path(__file__).resolve().parents[1] / "bridges" / "vela2-worker.py"
CHOICE_PROTOCOL = Path(__file__).with_name("choice_protocol.py")
TRANSPORT_FILE = Path(__file__).with_name("worker_transport.py")
INITIALIZATION_SECONDS = 120
# A per-call timeout no longer fails the whole campaign closed: the worker is
# restarted a bounded number of times and later cases are still attempted.
MAX_WORKER_RESTARTS = 3
RUNTIME_NAMES = {"numpy", "torch", "transformers", "tokenizers", "safetensors"}
LOADING_MODES = {REPO_ID: "hf-automodel-fp32", "vllm-sr/Vela-2.0-0.8B": "native-decoder-fp32",
                 VELA4_REPO_ID: "native-decoder-fp32"}


class Vela2ProfileError(ValueError):
    """Invalid explicit local Vela2 CPU profile."""


def minimum_available_mib(repo_id: str) -> int:
    if repo_id == REPO_ID:
        return 6144
    if repo_id == "vllm-sr/Vela-2.0-0.8B":
        return 8192
    if repo_id == VELA4_REPO_ID:
        return 24576
    raise Vela2ProfileError("Unsupported Vela2 model")


def memory_floor_mib(repo_id: str) -> int:
    return 4096 if repo_id == VELA4_REPO_ID else 2048


def validate_model_profile(profile: dict) -> None:
    model = profile.get("model") if isinstance(profile, dict) else None
    if not isinstance(model, dict) or set(model) != MODEL_FIELDS:
        raise Vela2ProfileError("Vela2 needs the complete local model configuration")
    if (profile.get("adapter") != "vela2" or profile.get("qualification") != "model_isolated"
            or profile.get("capabilities") != [CONTEXT_CHOICE_CONTRACT] or profile.get("recordings") is not None
            or model["repo_id"] not in MODELS
            or profile.get("revision") != MODELS[model["repo_id"]][0]):
        raise Vela2ProfileError("Vela2 requires a reviewed model revision and one isolated capability")
    for key in PATH_FIELDS:
        if not isinstance(model[key], str) or not model[key].strip() or "\x00" in model[key]:
            raise Vela2ProfileError("Vela2 paths must be explicit")
    rss_ceiling = 4096 if model["repo_id"] == REPO_ID else 22528 if model["repo_id"] == VELA4_REPO_ID else 6144
    for key, ceiling in (("max_length", 4096), ("threads", 2), ("max_rss_mb", rss_ceiling)):
        if type(model[key]) is not int or not 1 <= model[key] <= ceiling:
            raise Vela2ProfileError("Vela2 CPU limit is outside the bounded range")
    timeout = profile.get("timeout_seconds")
    timeout_ceiling = 60 if model["repo_id"] == VELA4_REPO_ID else 30
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= timeout_ceiling:
        raise Vela2ProfileError("Vela2 inference timeout is outside the bounded range")


def _hash(path, deadline=None):
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("vela2_initialization_timeout")
            digest.update(block)
    after = path.stat()
    state = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    if state != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("vela2_asset_changed")
    return digest.hexdigest(), state


def _lock_pins(text):
    """Parse exact pins, including hashed pip-compile continuations."""
    from urllib.parse import unquote, urlsplit
    pins = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("--hash="):
            continue
        line = line.removesuffix("\\").split(" --hash=", 1)[0].strip()
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.+!_-]*)", line)
        if match:
            name, version = match.groups()
        else:
            direct = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s*@\s*(https://\S+)", line)
            if not direct:
                raise ValueError("vela2_runtime_lock_unpinned")
            name, url = direct.groups()
            parsed = urlsplit(url)
            wheel = unquote(parsed.path).rsplit("/", 1)[-1]
            pieces = wheel.split("-")
            if (parsed.scheme != "https" or not re.fullmatch(r"sha256=[0-9a-f]{64}", parsed.fragment)
                    or len(pieces) != 5 or not wheel.endswith(".whl")
                    or re.sub(r"[-_.]+", "-", pieces[0]).lower() != re.sub(r"[-_.]+", "-", name).lower()):
                raise ValueError("vela2_runtime_lock_unpinned")
            version = pieces[1]
        name = re.sub(r"[-_.]+", "-", name).lower()
        if name in pins:
            raise ValueError("vela2_runtime_lock_duplicate")
        pins[name] = version
    if not RUNTIME_NAMES <= pins.keys():
        raise ValueError("vela2_runtime_lock_incomplete")
    return pins


def _envelope(status, output=None, raw_output=None, error=None):
    return {"status": status, "output": output, "raw_output": raw_output, "error": error}


class Vela2Adapter:
    """Single persistent CPU worker; serialized requests and explicit close."""

    def __init__(self, profile: dict, profile_path: str | Path):
        initialized_at = time.monotonic()
        validate_model_profile(profile)
        self.capabilities = list(profile["capabilities"])
        self._profile = _decode(_wire(profile))
        self._model = profile["model"]
        self._paths = {name: Path(profile_path).resolve().parent / self._model[name] for name in PATH_FIELDS}
        self._process = None
        self._pycache = None
        self._closed = False
        self._states = {}
        self._failure = None
        self._sequence = 0
        self._restarts = 0
        self._restart_pending = False
        self._peak_rss_mb = 0.0
        self._timeout = float(profile["timeout_seconds"])
        self.provenance = {"adapter": "vela2", "qualification": "model_isolated", "available": False,
                           "model": dict(self._model),
                           "model_revision": profile["revision"], "model_repo_id": self._model["repo_id"],
                           "profile_sha256": hashlib.sha256(_wire(profile)).hexdigest(),
                           "capabilities": self.capabilities}
        self.provenance["restart_policy"] = {"max_worker_restarts": MAX_WORKER_RESTARTS,
                                             "trigger": "vela2_inference_timeout",
                                             "timed_out_case_status": "timeout_not_cached"}
        self.provenance["worker_restarts"] = []
        self.provenance["adapter_sha256"] = self._remember(Path(__file__))
        self.provenance["worker_sha256"] = self._remember(WORKER)
        self.provenance["choice_protocol_sha256"] = self._remember(CHOICE_PROTOCOL)
        self.provenance["transport_sha256"] = self._remember(TRANSPORT_FILE)
        self._identity()
        deadline = initialized_at + (300 if self._model["repo_id"] == VELA4_REPO_ID else INITIALIZATION_SECONDS)
        try:
            self._prepare(deadline)
            if self._host_available_mb() < minimum_available_mib(self._model["repo_id"]):
                raise MemoryError("vela2_host_memory_low")
            self._launch_worker(deadline, profile)
        except TimeoutError:
            self._fail("timeout", "vela2_initialization_timeout")
        except MemoryError as exc:
            self._fail("error", "vela2_host_memory_low" if str(exc) == "vela2_host_memory_low" else "vela2_rss_limit")
        except FileNotFoundError:
            self._fail("missing", "vela2_assets_or_runtime_missing")
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            self._fail("error", "vela2_initialization_invalid")
        except BaseException:
            self.close()
            raise
        finally:
            self._identity()
            self.provenance["init_wall_ms"] = (time.monotonic() - initialized_at) * 1000

    def _launch_worker(self, deadline, profile):
        """Start the single CPU worker and verify its ready report; used at init and after a restart."""
        cache = Path(__file__).resolve().parents[1] / "results" / ".cache" / "vela2-worker"
        cache.mkdir(parents=True, exist_ok=True)
        self._pycache = Path(tempfile.mkdtemp(prefix="pycache-", dir=cache))
        env = {"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
               "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
               "HF_HUB_DISABLE_TELEMETRY": "1", "CUDA_VISIBLE_DEVICES": "", "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONNOUSERSITE": "1", "TOKENIZERS_PARALLELISM": "false", "HF_HOME": str(cache),
               "XDG_CACHE_HOME": str(cache), "TMPDIR": str(cache),
               "OMP_NUM_THREADS": str(self._model["threads"]), "MKL_NUM_THREADS": str(self._model["threads"])}
        self._process = subprocess.Popen([str(self._paths["runtime_python"]), "-I", "-B",
                                          "-X", f"pycache_prefix={self._pycache}", str(WORKER)],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL, env=env, start_new_session=True)
        os.set_blocking(self._process.stdin.fileno(), False)
        os.set_blocking(self._process.stdout.fileno(), False)
        ready = self._exchange({"op": "initialize", "config": {
            "local_dir": str(self._root), "revision": profile["revision"],
            "repo_id": self._model["repo_id"],
            "max_length": self._model["max_length"], "threads": self._model["threads"],
            "pins": self._pins, "assets_manifest": str(self._paths["assets_manifest"]),
            "assets_manifest_sha256": self.provenance["assets_manifest_sha256"]}},
            max(0, deadline - time.monotonic()))
        if not isinstance(ready, dict) or ready.get("status") != "ready":
            if isinstance(ready, dict) and ready.get("error") in {"vela2_model_missing", "vela2_runtime_missing"}:
                raise FileNotFoundError(ready["error"])
            raise ValueError("vela2_initialization_failed")
        if (set(ready) != {"status", "runtime", "load_ms", "rss_mb", "native_max_input_tokens", "dtype", "device", "loading_mode"}
                or ready["device"] != "cpu" or ready["dtype"] != "float32"
                or ready["loading_mode"] != LOADING_MODES[self._model["repo_id"]]
                or type(ready["native_max_input_tokens"]) is not int
                or ready["native_max_input_tokens"] != MODELS[self._model["repo_id"]][2]
                or not isinstance(ready["runtime"], dict)
                or any(ready["runtime"].get(name) != version for name, version in self._pins.items())
                or not self._nonnegative(ready["load_ms"]) or not self._nonnegative(ready["rss_mb"])):
            raise ValueError("vela2_invalid_ready")
        self._guard()
        if max(self._peak_rss_mb, ready["rss_mb"]) > self._model["max_rss_mb"]:
            raise MemoryError("vela2_rss_limit")
        self.provenance.update(available=True, runtime=ready["runtime"], device="cpu", dtype="float32",
                               loading_mode=ready["loading_mode"],
                               native_max_input_tokens=ready["native_max_input_tokens"],
                               effective_max_input_tokens=self._model["max_length"],
                               load_ms=ready["load_ms"], load_rss_mb=max(self._peak_rss_mb, ready["rss_mb"]))

    @staticmethod
    def _nonnegative(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    def _remember(self, path, deadline=None, *, allow_symlink=False):
        if not path.exists() and not path.is_symlink():
            raise FileNotFoundError("vela2_asset_missing")
        if (path.is_symlink() and not allow_symlink) or not path.is_file():
            raise ValueError("vela2_asset_invalid")
        digest, state = _hash(path, deadline)
        self._states[path] = state
        return digest

    def _remember_bytes(self, path, deadline, too_large):
        """Read a small pinned file once; parse and fingerprint those same bytes."""
        if not path.exists() and not path.is_symlink():
            raise FileNotFoundError("vela2_asset_missing")
        if path.is_symlink() or not path.is_file():
            raise ValueError("vela2_asset_invalid")
        before = path.stat()
        if before.st_size > MAX_LINE:
            raise ValueError(too_large)
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            data = stream.read(MAX_LINE + 1)
            finished = os.fstat(stream.fileno())
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("vela2_initialization_timeout")
        if len(data) > MAX_LINE:
            raise ValueError(too_large)
        after = path.stat()
        state = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if state(before) != state(opened) or state(before) != state(finished) or state(before) != state(after):
            raise ValueError("vela2_asset_changed")
        self._states[path] = state(before)
        return data, hashlib.sha256(data).hexdigest()

    def _identity(self):
        keys = ("model_revision", "model_repo_id", "assets_manifest_sha256",
                "model_assets_sha256", "prompt_sha256", "runtime_lock_sha256", "runtime_python_sha256",
                "worker_sha256", "adapter_sha256", "choice_protocol_sha256", "transport_sha256", "settings")
        self.provenance["identity_sha256"] = hashlib.sha256(
            _wire({key: self.provenance[key] for key in keys if key in self.provenance})
        ).hexdigest()

    def _prepare(self, deadline):
        root = self._paths["local_dir"]
        if not root.exists() and not root.is_symlink():
            raise FileNotFoundError("vela2_model_missing")
        if root.is_symlink() or not root.is_dir():
            raise ValueError("vela2_model_invalid")
        self._root = root.resolve()
        manifest_path = self._paths["assets_manifest"]
        manifest_bytes, self.provenance["assets_manifest_sha256"] = self._remember_bytes(
            manifest_path, deadline, "vela2_assets_manifest_too_large")
        manifest = _decode(manifest_bytes)
        if (not isinstance(manifest, dict) or set(manifest) != {"schema_version", "repo_id", "revision", "files"}
                or manifest["schema_version"] != "deposium.model-assets/v1"
                or manifest["repo_id"] != self._model["repo_id"] or manifest["revision"] != self._profile["revision"]
                or not isinstance(manifest["files"], list) or not manifest["files"] or len(manifest["files"]) > 10000):
            raise ValueError("vela2_assets_manifest_invalid")
        expected = set()
        indexed = {}
        for item in manifest["files"]:
            if not isinstance(item, dict) or set(item) != {"path", "size", "sha256"}:
                raise ValueError("vela2_assets_manifest_invalid")
            name = item["path"]
            relative = Path(name) if isinstance(name, str) else Path(".")
            if (not isinstance(name, str) or relative.is_absolute() or not relative.parts
                    or any(part in {".", "..", ".cache", "__pycache__"} for part in relative.parts)
                    or relative.as_posix() != name or name in expected
                    or type(item["size"]) is not int or item["size"] < 0
                    or not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
                raise ValueError("vela2_asset_path_invalid")
            path = self._root / relative
            if not path.resolve().is_relative_to(self._root) or self._remember(path, deadline) != item["sha256"] or path.stat().st_size != item["size"]:
                raise ValueError("vela2_asset_hash_mismatch")
            expected.add(name)
            indexed[name] = {"sha256": item["sha256"], "size": item["size"]}
        actual = self._list_assets()
        if actual != expected:
            raise ValueError("vela2_asset_inventory_changed")
        self.provenance["model_assets_sha256"] = hashlib.sha256(_wire(indexed)).hexdigest()
        self.provenance["model_assets"] = manifest
        prompt_path = self._paths["prompt_path"]
        prompt_bytes, self.provenance["prompt_sha256"] = self._remember_bytes(
            prompt_path, deadline, "vela2_prompt_too_large")
        if _decode(prompt_bytes) != CONTEXT_CHOICE_PROMPT:
            raise ValueError("vela2_prompt_invalid")
        lock_path = self._paths["runtime_lock"]
        lock_bytes, self.provenance["runtime_lock_sha256"] = self._remember_bytes(
            lock_path, deadline, "vela2_runtime_lock_too_large")
        self._pins = _lock_pins(lock_bytes.decode("utf-8"))
        self.provenance["runtime_pins"] = self._pins
        self.provenance["runtime_python_sha256"] = self._remember(self._paths["runtime_python"], deadline, allow_symlink=True)
        self.provenance["settings"] = {"device": "cpu", "dtype": "float32", "threads": self._model["threads"],
                                       "max_length": self._model["max_length"], "max_rss_mb": self._model["max_rss_mb"],
                                       "encoding_preflight": "official-vela2-assemble-complete", "shared_context": False,
                                       "loading_mode": LOADING_MODES[self._model["repo_id"]]}

    def _rss(self):
        if self._process is None:
            return
        try:
            for line in Path(f"/proc/{self._process.pid}/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    self._record_rss(int(line.split()[1]) / 1024)
                    return
        except FileNotFoundError:
            if platform.system() == "Darwin" and self._process.poll() is None:
                # The worker owns its own session, so its process group is the
                # worker alone; ps reports resident KiB (same helper as the native adapters).
                try:
                    from .native_resources import process_group_rss_mib
                    self._record_rss(process_group_rss_mib(self._process.pid))
                except (OSError, ValueError, subprocess.SubprocessError):
                    raise OSError("vela2_rss_unavailable") from None
                return
            if self._process.poll() is None:
                raise OSError("vela2_rss_unavailable")

    def _record_rss(self, rss):
        self._peak_rss_mb = max(self._peak_rss_mb, rss)
        if rss > self._model["max_rss_mb"]:
            raise MemoryError("vela2_rss_limit")
        if self._host_available_mb() < memory_floor_mib(self._model["repo_id"]):
            raise MemoryError("vela2_host_memory_low")

    def _list_assets(self):
        actual = set()
        for path in self._root.rglob("*"):
            relative = path.relative_to(self._root)
            if ".cache" in relative.parts or "__pycache__" in relative.parts:
                continue
            if path.is_symlink():
                raise ValueError("vela2_asset_symlink")
            if path.is_file():
                actual.add(relative.as_posix())
        return actual

    @staticmethod
    def _host_available_mb():
        if platform.system() == "Darwin":
            # Reclaimable-page estimate from vm_stat, as for the other macOS adapters.
            try:
                from .native_resources import memory_snapshot
                return float(memory_snapshot()["MemAvailable_mib"])
            except (OSError, ValueError, KeyError, subprocess.SubprocessError):
                raise OSError("vela2_host_memory_unknown") from None
        available = None
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                available = int(line.split()[1]) / 1024
                break
        if available is None:
            raise OSError("vela2_host_memory_unknown")
        limit, current = Path("/sys/fs/cgroup/memory.max"), Path("/sys/fs/cgroup/memory.current")
        if limit.is_file() and current.is_file():
            bound = limit.read_text().strip()
            if bound != "max":
                available = min(available, max(0, (int(bound) - int(current.read_text().strip())) / 1048576))
        return available

    def _guard(self):
        if self._paths["local_dir"].resolve() != self._root:
            raise ValueError("vela2_model_changed")
        for path, state in self._states.items():
            stat = path.stat()
            if state != (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns):
                raise ValueError("vela2_assets_changed")
        if self._list_assets() != {item["path"] for item in self.provenance["model_assets"]["files"]}:
            raise ValueError("vela2_asset_inventory_changed")
        self._rss()
        # The loaded worker is already absent from MemAvailable; apply the
        # variant's residual floor without counting its RSS a second time.
        if self._host_available_mb() < memory_floor_mib(self._model["repo_id"]):
            raise MemoryError("vela2_host_memory_low")

    def _exchange(self, message, timeout):
        return exchange(self._process, message, timeout_seconds=timeout, monitor=self._rss,
                        error_prefix="vela2")

    def _fail(self, status, code):
        self._failure = _envelope(status, error=code)
        self.provenance.update(available=False, availability_error=code)
        self.close()

    def _audit(self, response, value):
        if (not isinstance(response, dict) or set(response) != {"sequence", "status", "output", "raw_output", "error"}
                or response["sequence"] != self._sequence or response["status"] not in {"ok", "unsupported", "error"}):
            raise ValueError("vela2_worker_protocol_invalid")
        raw = response["raw_output"]
        if response["status"] == "error" and raw is None and response["output"] is None and response["error"] == "vela2_inference_failed":
            return
        if (not isinstance(raw, dict) or not {"native_result", "native_tokens", "input_sha256", "ordered_ids",
                "encoding_info", "forward_executed", "decision_ms", "inference_ms", "rss_mb"} <= raw.keys()
                or raw["ordered_ids"] != ordered_choice_ids(value)
                or raw["input_sha256"] != hashlib.sha256(_wire(value)).hexdigest()
                or not self._nonnegative(raw["decision_ms"]) or not self._nonnegative(raw["rss_mb"])):
            raise ValueError("vela2_worker_result_invalid")
        if raw["rss_mb"] > self._model["max_rss_mb"]:
            raise MemoryError("vela2_rss_limit")
        encoding = raw["encoding_info"]
        if (not isinstance(encoding, dict) or set(encoding) != {"tokens", "stateTruncated", "optionsTruncated"}
                or type(encoding["tokens"]) is not int or encoding["tokens"] < 1
                or encoding["stateTruncated"] is not False or encoding["optionsTruncated"] is not False
                or type(raw["native_tokens"]) is not int or raw["native_tokens"] < 0):
            raise ValueError("vela2_encoding_invalid")
        if response["status"] == "unsupported":
            if (response["error"] != "vela2_context_overflow" or response["output"] is not None
                    or raw["native_result"] is not None or raw["forward_executed"] is not False
                    or raw["inference_ms"] is not None or encoding["tokens"] <= self._model["max_length"]):
                raise ValueError("vela2_overflow_invalid")
            return
        if response["status"] == "error":
            if response["error"] != "vela2_inference_failed" or response["output"] is not None:
                raise ValueError("vela2_error_invalid")
            return
        native = raw["native_result"]
        if (response["error"] is not None or encoding["tokens"] > self._model["max_length"]
                or raw["forward_executed"] is not True or not self._nonnegative(raw["inference_ms"])
                or raw["decision_ms"] < raw["inference_ms"] or not isinstance(native, dict)
                or set(native) != {"model", "answers", "usage"}
                or native["model"] != MODELS[self._model["repo_id"]][1]
                or not isinstance(native["answers"], dict) or set(native["answers"]) != {"decision"}
                or not isinstance(native["usage"], dict) or native["usage"].get("input_tokens") != raw["native_tokens"]
                or raw["native_tokens"] != encoding["tokens"]
                or native["usage"].get("output_tokens") != 0):
            raise ValueError("vela2_native_invalid")
        answer = native["answers"]["decision"]
        keys = [f"c{i}" for i in range(len(value["options"]))]
        if (not isinstance(answer, dict) or set(answer) != {"type", "choice", "probabilities", "confidence"}
                or answer.get("type") != "choice" or answer.get("choice") not in keys
                or type(answer["confidence"]) not in (int, float) or not math.isfinite(answer["confidence"])
                or not 0 <= answer["confidence"] <= 1
                or not isinstance(answer.get("probabilities"), dict)
                or list(answer["probabilities"]) != keys or any(type(p) not in (int, float) or not math.isfinite(p)
                or not 0 <= p <= 1 for p in answer["probabilities"].values())
                or abs(sum(answer["probabilities"].values()) - 1) > 1e-5):
            raise ValueError("vela2_distribution_invalid")
        highest = max(answer["probabilities"].values())
        first_winner = next(key for key in keys if answer["probabilities"][key] == highest)
        entropy = -sum(p * math.log(p) for p in answer["probabilities"].values() if p > 0)
        sorted_probs = sorted(answer["probabilities"].values(), reverse=True)
        confidence = min(1.0, max(0.0, sorted_probs[0] - sorted_probs[1]))
        if answer["choice"] != first_winner or abs(answer["confidence"] - confidence) > 1e-6:
            raise ValueError("vela2_choice_probability_invalid")
        winner = value["options"][keys.index(answer["choice"])]["id"]
        if response["output"] != {"choice_id": winner}:
            raise ValueError("vela2_choice_invalid")

    def predict(self, request):
        if self._failure is not None:
            cached = dict(self._failure)
            cached["raw_output"] = {"forward_executed": False, "cached_failure": True}
            return cached
        if self._closed:
            return _envelope("error", error="vela2_adapter_closed",
                             raw_output={"forward_executed": False, "cached_failure": False})
        if (not isinstance(request, dict) or request.get("contract_id") != CONTEXT_CHOICE_CONTRACT
                or not isinstance(request.get("input"), dict)):
            return _envelope("unsupported", error="unsupported_contract")
        if self._restart_pending:
            self._relaunch()
            if self._failure is not None:
                return dict(self._failure)
        validate_json(request["input"])
        _no_annotations(request["input"])
        validate_choice_input(request["input"])
        message = {"op": "predict", "sequence": self._sequence + 1, "input": request["input"]}
        if len(_wire(message)) > MAX_LINE:
            # Refused for this case only, before any exchange: later cases remain evaluable.
            return _envelope("unsupported", error="vela2_request_too_large",
                             raw_output={"forward_executed": False, "cached_failure": False})
        self._sequence += 1
        try:
            self._guard()
            response = self._exchange(message, self._timeout)
            self._guard()
            self._audit(response, request["input"])
            if isinstance(response.get("raw_output"), dict):
                response["raw_output"]["worker_generation"] = self._restarts
            return {key: response[key] for key in ("status", "output", "raw_output", "error")}
        except TimeoutError:
            return self._timeout_outcome()
        except MemoryError as exc:
            self._fail("error", "vela2_host_memory_low" if str(exc) == "vela2_host_memory_low" else "vela2_rss_limit")
        except FileNotFoundError:
            self._fail("missing", "vela2_assets_or_runtime_missing")
        except (OSError, ValueError, TypeError, KeyError):
            self._fail("error", "vela2_runtime_or_protocol_changed")
        except BaseException:
            self.close()
            raise
        return dict(self._failure)

    def _terminate_worker(self):
        """Stop the owned worker process only; the adapter stays open for a bounded restart."""
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            # EPERM: the group already has no signalable member (macOS reports it for a reaped worker).
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                process.wait(timeout=1)
        finally:
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()

    def _timeout_outcome(self):
        """The timed-out case is recorded as attempted; later cases get a restarted worker."""
        if self._restarts >= MAX_WORKER_RESTARTS:
            self._fail("timeout", "vela2_inference_timeout")
            return dict(self._failure)
        self._restarts += 1
        self._terminate_worker()
        self._restart_pending = True
        self.provenance["worker_restarts"].append({"after_sequence": self._sequence, "restart": self._restarts,
                                                   "reason": "vela2_inference_timeout"})
        return _envelope("timeout", error="vela2_inference_timeout",
                         raw_output={"forward_executed": None, "cached_failure": False,
                                     "worker_restart_scheduled": self._restarts, "worker_generation": self._restarts - 1})

    def _relaunch(self):
        started = time.monotonic()
        deadline = started + (300 if self._model["repo_id"] == VELA4_REPO_ID else INITIALIZATION_SECONDS)
        try:
            # No process is running here, so this checks the remembered worker,
            # runtime, adapter and asset identities before anything executes.
            self._guard()
            if self._host_available_mb() < minimum_available_mib(self._model["repo_id"]):
                raise MemoryError("vela2_host_memory_low")
            self._launch_worker(deadline, self._profile)
            self.provenance["worker_restarts"][-1]["relaunch_ms"] = (time.monotonic() - started) * 1000
        except TimeoutError:
            self._fail("timeout", "vela2_initialization_timeout")
        except MemoryError as exc:
            self._fail("error", "vela2_host_memory_low" if str(exc) == "vela2_host_memory_low" else "vela2_rss_limit")
        except FileNotFoundError:
            self._fail("missing", "vela2_assets_or_runtime_missing")
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            self._fail("error", "vela2_initialization_invalid")
        finally:
            self._restart_pending = False

    def close(self):
        self._closed = True
        process = self._process
        self._process = None
        try:
            self._process = process
            self._terminate_worker()
        finally:
            if self._pycache is not None:
                # This directory was created uniquely for this worker; never sweep shared caches.
                owned, self._pycache = self._pycache, None
                shutil.rmtree(owned)
