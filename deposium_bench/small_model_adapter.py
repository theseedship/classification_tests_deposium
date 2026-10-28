"""Offline resident CPU adapter for pinned small decision models."""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from .cases import _no_annotations
from .choice_protocol import CONTEXT_CHOICE_CONTRACT, CONTEXT_CHOICE_PROMPT, ordered_choice_ids, validate_choice_input
from .decision2_adapter import _lock_pins
from .laya_adapter import LayaAdapter
from .worker_transport import MAX_LINE, decode, exchange, wire

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "bridges/small-decision-worker.py"
REPOS = {"omni": ("LiquidAI/d1-omni-600M", "414f8d6438174f5b2133a9c21a478fc42625e308", 16384),
         "muose": ("muose/Muose-50M-Decision", "5afb8eeff127621fea2d66fc63f56798ada12eda", 512),
         "modernjev": ("MaziyarPanahi/ModernJEV-Decide-Preview", "d5b398ed03de073a00bc4e53acf53afda409445e", 4096),
         "liquid3": ("LiquidAI/d1-3B", "051bcc464b01b9f92942b364d9586b0ef5912432", 4096)}
MIN_AVAILABLE_MIB = 6144
COMMON_PATHS = {"local_dir", "source_dir", "runtime_python", "assets_manifest", "source_manifest", "runtime_lock"}
COMMON_FIELDS = COMMON_PATHS | {"mode", "repo_id", "max_length", "threads", "max_rss_mb"}


def minimum_available_mib(mode):
    return 22528 if mode == "liquid3" else MIN_AVAILABLE_MIB


def rss_limit_mib(mode):
    return 18432 if mode == "liquid3" else 4096


def validate_model_profile(profile):
    model = profile.get("model") if isinstance(profile, dict) else None
    mode = model.get("mode") if isinstance(model, dict) else None
    if mode not in REPOS:
        raise ValueError("small_model_profile_identity_invalid")
    repo_id, revision, max_length = REPOS[mode]
    extra = "prompt_path" if mode in {"omni", "liquid3"} else "template_path"
    if (set(model) != COMMON_FIELDS | {extra} or profile.get("adapter") != "small_model"
            or profile.get("qualification") != "model_isolated"
            or profile.get("capabilities") != [CONTEXT_CHOICE_CONTRACT]
            or profile.get("recordings") is not None or profile.get("revision") != revision
            or model["repo_id"] != repo_id):
        raise ValueError("small_model_profile_identity_invalid")
    for name in COMMON_PATHS | {extra}:
        if not isinstance(model[name], str) or not model[name].strip() or "\0" in model[name]:
            raise ValueError("small_model_profile_path_invalid")
    for name, expected in (("max_length", max_length), ("max_rss_mb", rss_limit_mib(mode)), ("threads", 2)):
        if type(model[name]) is not int or model[name] != expected:
            raise ValueError("small_model_profile_limit_invalid")
    timeout = profile.get("timeout_seconds")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= (60 if mode == "liquid3" else 30):
        raise ValueError("small_model_profile_timeout_invalid")


def envelope(status, output=None, raw_output=None, error=None):
    return {"status": status, "output": output, "raw_output": raw_output, "error": error}


def _nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


class SmallModelAdapter(LayaAdapter):
    """Reuse the existing manifest, inventory, process and RSS primitives."""

    def __init__(self, profile, profile_path):
        started = time.monotonic()
        validate_model_profile(profile)
        self._profile = decode(wire(profile))
        self._model = self._profile["model"]
        self._mode = self._model["mode"]
        self.capabilities = list(profile["capabilities"])
        extra = "prompt_path" if self._mode in {"omni", "liquid3"} else "template_path"
        self._paths = {key: Path(os.path.abspath(Path(profile_path).parent / self._model[key]))
                       for key in COMMON_PATHS | {extra}}
        self._process = None
        self._cache = None
        self._closed = False
        self._failure = None
        self._sequence = 0
        self._states = {}
        self._inventories = {}
        self._peak_rss_mb = 0.0
        self.provenance = {"adapter": "small_model", "qualification": "model_isolated",
                           "available": False, "model": dict(self._model),
                           "model_repo_id": self._model["repo_id"],
                           "model_revision": profile["revision"], "capabilities": self.capabilities,
                           "profile_sha256": hashlib.sha256(wire(profile)).hexdigest()}
        try:
            deadline = started + (300 if self._mode == "liquid3" else 120)
            for name, path in (("adapter", Path(__file__)), ("worker", WORKER),
                               ("backend", ROOT / "bridges" / {
                                   "omni": "liquid-omni-backend.py", "muose": "muose-backend.py",
                                   "modernjev": "modernjev-backend.py", "liquid3": "liquid-d1-backend.py"}[self._mode]),
                               ("choice_protocol", ROOT / "deposium_bench/choice_protocol.py"),
                               ("transport", ROOT / "deposium_bench/worker_transport.py"),
                               ("asset_helpers", ROOT / "deposium_bench/decision2_adapter.py")):
                self.provenance[name + "_sha256"] = self._remember(path, deadline)
            self._prepare(deadline)
            if self._available() < minimum_available_mib(self._mode):
                raise MemoryError("small_model_host_memory_low")
            cache_parent = ROOT / "results/.cache/small-model-worker"
            cache_parent.mkdir(parents=True, exist_ok=True)
            self._cache = tempfile.TemporaryDirectory(dir=cache_parent)
            cache = self._cache.name
            env = {"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
                   "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
                   "HF_HUB_DISABLE_TELEMETRY": "1", "CUDA_VISIBLE_DEVICES": "",
                   "TOKENIZERS_PARALLELISM": "false", "PYTHONNOUSERSITE": "1", "USE_TF": "0",
                   "HF_HOME": cache, "XDG_CACHE_HOME": cache, "TMPDIR": cache,
                   "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"}
            command = [str(self._paths["runtime_python"]), "-I", "-B", "-X",
                       f"pycache_prefix={cache}/pycache", str(WORKER)]
            self._process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                             env=env, cwd=ROOT, start_new_session=True)
            os.set_blocking(self._process.stdin.fileno(), False)
            os.set_blocking(self._process.stdout.fileno(), False)
            config = {"mode": self._mode, "source_dir": str(self._paths["source_dir"]),
                      "local_dir": str(self._paths["local_dir"]),
                      "max_length": self._model["max_length"], "threads": 2, "pins": self._pins}
            if self._mode in {"muose", "modernjev"}:
                config["template_path"] = str(self._paths["template_path"])
            ready = exchange(self._process, {"op": "initialize", "config": config},
                             timeout_seconds=max(0, deadline-time.monotonic()),
                             monitor=self._monitor, error_prefix="small_model")
            if ready.get("status") == "error":
                raise ValueError(self._error_code(ready.get("error"), "small_model_initialization_failed"))
            fields = {"status", "runtime", "load_ms", "rss_mb", "max_length", "dtype", "device", "backend"}
            if self._mode in {"muose", "modernjev"}:
                fields.add("template_sha256")
            if (set(ready) != fields or ready["status"] != "ready" or ready["device"] != "cpu"
                    or ready["dtype"] != "float32" or ready["max_length"] != self._model["max_length"]
                    or not isinstance(ready["backend"], str)
                    or ready["backend"] != {"omni": "system_one", "liquid3": "system_one", "muose": "muose_native",
                                            "modernjev": "modernjev_native"}[self._mode]
                    or not isinstance(ready["runtime"], dict)
                    or any(ready["runtime"].get(k) != v for k, v in self._pins.items())
                    or not _nonnegative(ready["load_ms"]) or not _nonnegative(ready["rss_mb"])
                    or (self._mode in {"muose", "modernjev"}
                        and ready["template_sha256"] != self.provenance["template_sha256"])):
                raise ValueError("small_model_ready_invalid")
            self._guard()
            if max(ready["rss_mb"], self._peak_rss_mb) > rss_limit_mib(self._mode):
                raise MemoryError("small_model_rss_limit")
            self.provenance.update(available=True, runtime=ready["runtime"],
                                   device="cpu", dtype="float32", backend=ready["backend"],
                                   effective_max_input_tokens=self._model["max_length"],
                                   load_ms=ready["load_ms"],
                                   load_rss_mb=max(ready["rss_mb"], self._peak_rss_mb))
        except TimeoutError:
            self._fail("timeout", "small_model_initialization_timeout")
        except MemoryError as exc:
            self._fail("error", self._error_code(str(exc), "small_model_rss_limit"))
        except FileNotFoundError:
            self._fail("missing", "small_model_assets_or_runtime_missing")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self._fail("error", self._error_code(str(exc), "small_model_initialization_invalid"))
        except BaseException:
            self.close()
            raise
        finally:
            identity = {k: v for k, v in self.provenance.items() if k.endswith("_sha256") and k != "identity_sha256"}
            identity.update(model_revision=profile["revision"], settings=self.provenance.get("settings"))
            self.provenance["identity_sha256"] = hashlib.sha256(wire(identity)).hexdigest()
            self.provenance["init_wall_ms"] = (time.monotonic()-started)*1000

    @staticmethod
    def _error_code(code, fallback):
        return code if isinstance(code, str) and re.fullmatch(r"(?:small_model|muose|modernjev)_[a-z0-9_]{1,85}", code) else fallback

    def _read(self, path, deadline):
        # Only a genuinely absent configuration file is a missing asset.
        # Delegate symlink, directory, size and change checks to the parent.
        path.lstat()
        return super()._read(path, deadline)

    def _prepare(self, deadline):
        repo, revision, _ = REPOS[self._mode]
        assets, digest = self._bundle("local_dir", "assets_manifest", repo, revision, deadline)
        names = {item["path"] for item in assets["files"]}
        required = ({"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
                     "prompt.py", "modeling_d1.py", "api.py", "runner.py", "hybrid.py", "lfm2_vl.py"}
                    if self._mode == "liquid3" else
                    {"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
                     "prompt.py", "modeling_d1.py"} if self._mode == "omni" else
                    {"config.json", "model.safetensors", "vocab.json", "merges.txt"}
                    if self._mode == "muose" else
                    {"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json"})
        if not required <= names:
            raise ValueError("small_model_assets_incomplete")
        self.provenance.update(model_assets=assets, assets_manifest_sha256=digest,
                               model_assets_sha256=hashlib.sha256(wire(assets)).hexdigest())
        source, digest = self._bundle("source_dir", "source_manifest", repo, revision, deadline)
        source_names = {item["path"] for item in source["files"]}
        required_source = ({"api.py", "hybrid.py", "lfm2_vl.py", "modeling_d1.py", "prompt.py", "runner.py"}
                           if self._mode == "liquid3" else
                           {"prompt.py", "modeling_d1.py", "encoder.py", "vision.py", "audio.py"}
                           if self._mode == "omni" else
                           {"model.py", "decision_model.py"} if self._mode == "muose" else
                           {"predict.py"})
        if not required_source <= source_names:
            raise ValueError("small_model_source_incomplete")
        if self._mode in {"omni", "liquid3"}:
            model_hashes = {item["path"]: item["sha256"] for item in assets["files"]}
            source_hashes = {item["path"]: item["sha256"] for item in source["files"]}
            if any(model_hashes.get(name) != source_hashes.get(name)
                   for name in required_source):
                raise ValueError("small_model_source_mismatch")
        self.provenance.update(source_assets=source, source_manifest_sha256=digest,
                               source_assets_sha256=hashlib.sha256(wire(source)).hexdigest())
        if self._mode in {"omni", "liquid3"}:
            prompt, digest = self._read(self._paths["prompt_path"], deadline)
            if decode(prompt) != CONTEXT_CHOICE_PROMPT:
                raise ValueError("small_model_prompt_invalid")
            self.provenance["prompt_sha256"] = digest
        else:
            _, digest = self._read(self._paths["template_path"], deadline)
            self.provenance["template_sha256"] = digest
        lock, digest = self._read(self._paths["runtime_lock"], deadline)
        self._pins = _lock_pins(lock.decode())
        self.provenance.update(runtime_pins=self._pins, runtime_lock_sha256=digest,
                               runtime_python_sha256=self._remember(self._paths["runtime_python"], deadline, symlink=True),
                               settings={"device": "cpu", "dtype": "float32", "threads": 2,
                                         "max_length": self._model["max_length"],
                                         "max_rss_mb": rss_limit_mib(self._mode), "encoding_preflight": "native-lossless"})

    def _monitor(self):
        if self._process is not None:
            try:
                for line in Path(f"/proc/{self._process.pid}/status").read_text().splitlines():
                    if line.startswith(("VmRSS:", "VmHWM:")):
                        self._peak_rss_mb = max(self._peak_rss_mb, int(line.split()[1])/1024)
            except FileNotFoundError:
                if self._process.poll() is None:
                    raise OSError("small_model_rss_unavailable")
            if self._peak_rss_mb > rss_limit_mib(self._mode):
                raise MemoryError("small_model_rss_limit")
        if self._available() < (4096 if self._mode == "liquid3" else 2048):
            raise MemoryError("small_model_host_memory_low")

    def _audit(self, response, value):
        if (not isinstance(response, dict)
                or set(response) != {"sequence", "status", "output", "raw_output", "error"}
                or type(response["sequence"]) is not int or response["sequence"] != self._sequence
                or response["status"] not in {"ok", "unsupported", "error"}):
            raise ValueError("small_model_worker_protocol_invalid")
        raw = response["raw_output"]
        if response["status"] == "error" and raw is None and response["output"] is None:
            if self._error_code(response["error"], None) is None:
                raise ValueError("small_model_error_invalid")
            return
        ids = ordered_choice_ids(value)
        descriptions = [item["description"] for item in value["options"]]
        if (not isinstance(raw, dict) or set(raw) != {"native_result", "input_sha256", "ordered_ids",
                                                 "ordered_descriptions", "encoding_info", "forward_executed",
                                                 "decision_ms", "inference_ms", "rss_mb"}
                or raw["input_sha256"] != hashlib.sha256(wire(value)).hexdigest()
                or raw["ordered_ids"] != ids or raw["ordered_descriptions"] != descriptions
                or type(raw["forward_executed"]) is not bool
                or not _nonnegative(raw["decision_ms"]) or not _nonnegative(raw["rss_mb"])):
            raise ValueError("small_model_result_invalid")
        if raw["rss_mb"] > rss_limit_mib(self._mode):
            raise MemoryError("small_model_rss_limit")
        if response["status"] == "unsupported":
            if (response["output"] is not None or raw["forward_executed"]
                    or raw["native_result"] is not None or raw["inference_ms"] is not None
                    or self._error_code(response["error"], None) is None):
                raise ValueError("small_model_unsupported_invalid")
            info = raw["encoding_info"]
            if self._mode == "liquid3":
                if (response["error"] != "small_model_context_overflow" or not isinstance(info, dict)
                        or info.get("altered_segment") not in {"reserved_delimiter", "context_limit"}
                        or type(info.get("full_input_tokens")) is not int
                        or info["full_input_tokens"] < 1 or info.get("forward_count") != 0):
                    raise ValueError("small_model_unsupported_invalid")
            elif self._mode == "omni":
                if (response["error"] != "small_model_context_overflow" or not isinstance(info, dict)
                        or info.get("altered_segment") not in {
                            "reserved_delimiter", "option", "instruction", "state_or_total",
                            "native_encoding", "native_context_limit"}
                        or type(info.get("full_input_tokens")) is not int
                        or info["full_input_tokens"] < 1):
                    raise ValueError("small_model_unsupported_invalid")
            elif self._mode == "muose" and (
                    response["error"] not in {"muose_context_overflow", "muose_empty_encoding"}
                    or not isinstance(info, dict) or info.get("truncated") is not False):
                raise ValueError("small_model_unsupported_invalid")
            elif self._mode == "modernjev" and (
                    response["error"] not in {"modernjev_empty_encoding", "modernjev_context_overflow",
                                              "modernjev_pair_encoding_mismatch"}
                    or not isinstance(info, dict) or info.get("truncated") is not False
                    or info.get("max_length") != 4096
                    or not isinstance(info.get("tokens_per_pair"), list)
                    or len(info["tokens_per_pair"]) != len(ids)
                    or info.get("forward_count") != 0
                    or info.get("actual_input_ids_sha256") != []):
                raise ValueError("small_model_unsupported_invalid")
            return
        if response["status"] == "error":
            if response["output"] is not None or self._error_code(response["error"], None) is None:
                raise ValueError("small_model_error_invalid")
            return
        info, native = raw["encoding_info"], raw["native_result"]
        if (response["error"] is not None or not raw["forward_executed"]
                or not _nonnegative(raw["inference_ms"])
                or raw["decision_ms"] < raw["inference_ms"]
                or not isinstance(info, dict) or not isinstance(native, dict)
                or not isinstance(response["output"], dict)
                or response["output"].get("choice_id") not in ids):
            raise ValueError("small_model_native_invalid")
        if self._mode == "liquid3":
            names = [f"option_{i:03d}" for i in range(len(ids))]
            answer = native.get("answers", {}).get("answer", {})
            probabilities = answer.get("probabilities", {})
            if (type(info.get("full_input_tokens")) is not int
                    or not 1 <= info["full_input_tokens"] <= self._model["max_length"]
                    or info.get("full_input_equal") is not True or info.get("forward_count") != 1
                    or info.get("native_sha256") != info.get("expected_sha256")
                    or info.get("model_forward_count") != 1
                    or info.get("model_forward_ids_equal") is not True
                    or info.get("model_forward_sha256") != info.get("expected_sha256")
                    or not isinstance(info.get("expected_sha256"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", info["expected_sha256"])
                    or info.get("altered_segment") is not None
                    or answer.get("type") != "choice" or list(probabilities) != names
                    or answer.get("choice") not in names
                    or not all(_nonnegative(p) for p in probabilities.values())
                    or probabilities[answer["choice"]] + 0.0001 < max(probabilities.values())
                    or native.get("usage") != {"input_tokens": info["full_input_tokens"], "output_tokens": 0}
                    or response["output"] != {"choice_id": ids[names.index(answer["choice"])]}):
                raise ValueError("small_model_native_invalid")
        elif self._mode == "omni":
            names = [f"option_{i:03d}" for i in range(len(ids))]
            answer = native.get("answers", {}).get("answer", {})
            probabilities = answer.get("probabilities", {})
            if (not info.get("full_input_equal") or not info.get("markers_equal")
                    or info.get("full_input_tokens") != info.get("encoded_tokens")
                    or info.get("forward_count") != 1 or not info.get("forward_ids_equal")
                    or not info.get("forward_markers_equal")
                    or info.get("actual_sha256") != info.get("expected_sha256")
                    or answer.get("type") != "choice" or list(probabilities) != names
                    or answer.get("choice") not in names
                    or probabilities[answer["choice"]] + 0.0001 < max(probabilities.values())
                    or native.get("usage") != {"input_tokens": info.get("full_input_tokens"), "output_tokens": 0}
                    or response["output"] != {"choice_id": ids[names.index(answer["choice"])]}):
                raise ValueError("small_model_native_invalid")
        elif self._mode == "muose":
            probabilities = native.get("probabilities")
            scores = native.get("scores")
            chosen = native.get("selected_index")
            if (set(native) != {"scores", "probabilities", "selected_index"}
                    or not isinstance(probabilities, list) or len(probabilities) != len(ids)
                    or not isinstance(scores, list) or len(scores) != len(ids)
                    or any(type(score) not in (int, float) or not math.isfinite(score)
                           for score in scores)
                    or type(chosen) is not int or not 0 <= chosen < len(ids)
                    or chosen != max(range(len(scores)), key=scores.__getitem__)
                    or response["output"] != {"choice_id": ids[chosen]}
                    or info.get("truncated") is not False
                    or info.get("max_length") != 512
                    or not isinstance(info.get("tokens_per_option"), list)
                    or len(info["tokens_per_option"]) != len(ids)
                    or any(type(length) is not int or not 1 <= length <= 512
                           for length in info["tokens_per_option"])):
                raise ValueError("small_model_native_invalid")
        else:
            candidates = native.get("candidates")
            selected = native.get("predicted_label")
            if (set(native) != {"predicted_label", "allowed_choices", "candidates",
                                "truncated", "max_sequence_length", "note"}
                    or native.get("allowed_choices") != descriptions
                    or selected not in descriptions or native.get("truncated") is not False
                    or native.get("max_sequence_length") != 4096
                    or not isinstance(candidates, list) or len(candidates) != len(ids)
                    or any(not isinstance(item, dict)
                           or set(item) != {"label", "score", "raw_score", "rank"}
                           or item["label"] not in descriptions
                           or type(item["rank"]) is not int or item["rank"] < 1
                           or not _nonnegative(item["score"]) or item["score"] > 1
                           or type(item["raw_score"]) not in (int, float)
                           or not math.isfinite(item["raw_score"])
                           for item in candidates)
                    or {item["label"] for item in candidates} != set(descriptions)
                    or [item["rank"] for item in candidates] != list(range(1, len(ids)+1))
                    or candidates[0]["label"] != selected
                    or response["output"] != {"choice_id": ids[descriptions.index(selected)]}
                    or info.get("truncated") is not False
                    or info.get("max_length") != 4096
                    or info.get("candidate_batch_size") != 1
                    or info.get("forward_count") != len(ids)
                    or info.get("forward_ids_equal") is not True
                    or info.get("forward_masks_equal") is not True
                    or info.get("actual_input_ids_sha256") != info.get("pair_input_ids_sha256")):
                raise ValueError("small_model_native_invalid")
            probabilities = [item["score"] for item in candidates]
        values = probabilities.values() if isinstance(probabilities, dict) else probabilities
        if (any(not _nonnegative(p) or p > 1 for p in values)
                or abs(sum(probabilities.values() if isinstance(probabilities, dict) else probabilities)-1) > 0.002):
            raise ValueError("small_model_distribution_invalid")

    def predict(self, request):
        if not isinstance(request, dict) or request.get("contract_id") != CONTEXT_CHOICE_CONTRACT:
            return envelope("unsupported", error="unsupported_contract")
        value = request.get("input")
        validate_choice_input(value)
        _no_annotations(value)
        if self._failure is not None:
            return {**self._failure, "raw_output": {"forward_executed": False, "cached_failure": True}}
        if self._closed:
            return envelope("error", raw_output={"forward_executed": False}, error="small_model_adapter_closed")
        message = {"op": "predict", "sequence": self._sequence+1, "input": value}
        if len(wire(message)) > MAX_LINE:
            return envelope("unsupported", raw_output={"forward_executed": False},
                            error="small_model_request_too_large")
        self._sequence += 1
        try:
            self._guard()
            response = exchange(self._process, message,
                                timeout_seconds=self._profile["timeout_seconds"],
                                monitor=self._monitor, error_prefix="small_model")
            self._guard()
            self._audit(response, value)
            return {k: response[k] for k in ("status", "output", "raw_output", "error")}
        except TimeoutError:
            self._fail("timeout", "small_model_inference_timeout")
        except MemoryError as exc:
            self._fail("error", self._error_code(str(exc), "small_model_rss_limit"))
        except FileNotFoundError:
            self._fail("missing", "small_model_assets_missing")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self._fail("error", self._error_code(str(exc), "small_model_worker_protocol_invalid"))
        except BaseException:
            self.close()
            raise
        return dict(self._failure)

    def _fail(self, status, code):
        self._failure = envelope(status, error=code)
        self.provenance.update(available=False, availability_error=code)
        self.close()
