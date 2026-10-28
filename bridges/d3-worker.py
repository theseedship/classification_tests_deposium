"""Isolated, offline transport for the pinned upstream D3 CPU engine."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import resource
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deposium_bench.choice_protocol import ordered_choice_ids, validate_choice_input
from deposium_bench.worker_transport import MAX_LINE, decode

REPO_ID = "vllm-sr/d3-edge"
MODELS = {
    REPO_ID: ("18d61df78684675463af9ae732872478845c5a79", 594321600, [255, 1024], 6144),
    "vllm-sr/d3-lite": ("a8d25a91ef75552803f7009d25b7bd435991abd9", 852985920, [255, 1024], 6144),
    "vllm-sr/d3-nano": ("3aeb1c22a5632aac72353c36b3d0111c40e7dbf4", 2213241664, [255, 2048], 12288),
    "vllm-sr/d3-mini": ("a475367de0d8133a3c1a2a0dc12303d89cfa2ab4", 4539265536, [255, 2560], 14336),
    "vllm-sr/d3-flash": ("521525effa79469d899a570726547dd7f00da3af", 8392695024, [255, 4096], 18432),
}
REQUIRED_SOURCE = {"d3_runtime.py", "d3_format.py", "modeling_d3.py", "config.json",
                   "decision_config.json", "MODEL_MANIFEST.json", "readout.safetensors"}
LOADING_MODE = "native-d3-bf16-readout-fp32"

def _read():
    data = sys.stdin.buffer.readline(MAX_LINE + 1)
    if not data:
        return None
    if len(data) > MAX_LINE or not data.endswith(b"\n"):
        raise ValueError("d3_protocol_limit")
    return decode(data)


def _rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_bundle(root, manifest_path, manifest_sha, repo_id, revision):
    if (root.is_symlink() or not root.is_dir() or manifest_path.is_symlink()
            or not manifest_path.is_file() or manifest_path.stat().st_size > MAX_LINE
            or _hash(manifest_path) != manifest_sha):
        raise FileNotFoundError("d3_asset_missing")
    manifest = decode(manifest_path.read_bytes())
    if (not isinstance(manifest, dict) or set(manifest) != {"schema_version", "repo_id", "revision", "files"}
            or manifest["schema_version"] != "deposium.model-assets/v1"
            or manifest["repo_id"] != repo_id or manifest["revision"] != revision
            or not isinstance(manifest["files"], list) or not manifest["files"]
            or len(manifest["files"]) > 10000):
        raise ValueError("d3_asset_manifest_invalid")
    seen = set()
    for item in manifest["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "size", "sha256"}:
            raise ValueError("d3_asset_manifest_invalid")
        name = item["path"]
        relative = Path(name) if isinstance(name, str) else Path(".")
        if (not isinstance(name, str) or relative.is_absolute() or not relative.parts
                or any(part in {".", "..", ".cache", "__pycache__"} for part in relative.parts)
                or relative.as_posix() != name or name in seen
                or type(item["size"]) is not int or item["size"] < 0
                or not isinstance(item["sha256"], str) or len(item["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in item["sha256"] )):
            raise ValueError("d3_asset_manifest_invalid")
        path = root / relative
        if (path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve())
                or path.stat().st_size != item["size"] or _hash(path) != item["sha256"]):
            raise ValueError("d3_asset_hash_mismatch")
        seen.add(name)
    actual = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".cache" in relative.parts or "__pycache__" in relative.parts:
            continue
        if path.is_symlink():
            raise ValueError("d3_asset_symlink")
        if path.is_file():
            actual.add(relative.as_posix())
    if (actual != seen or not REQUIRED_SOURCE <= seen
            or not any(name.endswith(".safetensors") for name in seen)):
        raise ValueError("d3_asset_inventory_changed")


def _block_network():
    def blocked(*_args, **_kwargs):
        raise OSError("d3_network_disabled")
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.socket.sendto = blocked
    socket.create_connection = blocked


def _versions(pins):
    actual = {name: importlib.metadata.version(name) for name in pins if name != "python"}
    actual["python"] = sys.version.split()[0]
    if any(actual.get(name) != version for name, version in pins.items()):
        raise ValueError("d3_runtime_lock_mismatch")
    return actual


def _host_available_mb():
    available = None
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            available = int(line.split()[1]) / 1024
            break
    if available is None:
        raise OSError("d3_host_memory_unknown")
    limit, current = Path("/sys/fs/cgroup/memory.max"), Path("/sys/fs/cgroup/memory.current")
    if limit.is_file() and current.is_file():
        bound = limit.read_text().strip()
        if bound != "max":
            available = min(available, max(0, (int(bound) - int(current.read_text().strip())) / 1048576))
    return available


def _input_hash(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False) + "\n"
    return hashlib.sha256(payload.encode()).hexdigest()




def _check_model(model, repo_id, torch):
    """Audit actual loaded tensors; named_parameters yields (name, tensor) pairs."""
    parameters = list(model.backbone.named_parameters())
    if (not isinstance(model.manifest, dict) or model.manifest.get("repo_id") != repo_id
            or model.model_name != repo_id.rsplit("/", 1)[-1]
            or model.config.get("max_length", "absent") is not None
            or not parameters or sum(t.numel() for _, t in parameters) != MODELS[repo_id][1]
            or any(t.dtype != torch.bfloat16 or t.device.type != "cpu" for _, t in parameters)
            or list(model.readout.shape) != MODELS[repo_id][2]
            or model.readout.dtype != torch.float32 or model.readout.device.type != "cpu"
            or model.batch_size != 1 or model.max_length != 4096
            or model.permutation_average is not False or model.fast is not None):
        raise ValueError("d3_model_identity_invalid")
    return len(parameters)


def _prepared_full(model, state, question):
    """Native rendering/tokenization under a temporary unbounded cap; no forward."""
    original = model.max_length
    try:
        model.max_length = None
        prepared = model.prepare(state, {"decision": question})
    finally:
        model.max_length = original
    if (prepared.keys != ["decision"] or prepared.errors or list(prepared.sequences) != ["decision"]
            or prepared.images or prepared.videos or prepared.reversed_sequences):
        raise ValueError("d3_native_prepare_invalid")
    sequence = prepared.sequences["decision"]
    if not isinstance(sequence, list) or not sequence or any(type(t) is not int or t < 0 for t in sequence):
        raise ValueError("d3_native_tokens_invalid")
    return prepared, tuple(sequence)


def _checked_run(model, prepared, sequence, torch, raw):
    """Observe the exact native text backbone call and reject changed input or mask."""
    calls = []
    def audit(_module, args, kwargs):
        if args or set(kwargs) != {"input_ids", "attention_mask", "use_cache"} or kwargs["use_cache"] is not False:
            raise ValueError("d3_forward_payload_invalid")
        ids, mask = kwargs["input_ids"], kwargs["attention_mask"]
        if (not isinstance(ids, torch.Tensor) or not isinstance(mask, torch.Tensor)
                or ids.dtype != torch.long or mask.dtype != torch.long
                or ids.device.type != "cpu" or mask.device.type != "cpu"
                or list(ids.shape) != [1, len(sequence)] or list(mask.shape) != [1, len(sequence)]
                or ids[0].tolist() != list(sequence) or mask[0].tolist() != [1] * len(sequence)
                or calls):
            raise ValueError("d3_forward_payload_invalid")
        calls.append(True)
        raw["forward_executed"] = True
    hook = model.backbone.register_forward_pre_hook(audit, with_kwargs=True)
    try:
        probabilities, tokens = model.run(prepared)
    finally:
        hook.remove()
    if calls != [True] or tokens != len(sequence):
        raise ValueError("d3_forward_count_invalid")
    return probabilities, tokens


def _valid_native(native, keys, tokens, model_name):
    if (not isinstance(native, dict) or set(native) != {"model", "answers", "usage"}
            or native["model"] != model_name or not isinstance(native["answers"], dict)
            or set(native["answers"]) != {"decision"} or not isinstance(native["usage"], dict)
            or native["usage"] != {"input_tokens": tokens, "output_tokens": 0}):
        raise ValueError("d3_native_output_invalid")
    answer = native["answers"]["decision"]
    if (not isinstance(answer, dict) or set(answer) != {"type", "choice", "probabilities", "confidence"}
            or answer["type"] != "choice" or answer["choice"] not in keys
            or not isinstance(answer["probabilities"], dict) or list(answer["probabilities"]) != keys
            or type(answer["confidence"]) not in (int, float)
            or not math.isfinite(answer["confidence"]) or not 0 <= answer["confidence"] <= 1):
        raise ValueError("d3_native_output_invalid")
    probs = answer["probabilities"]
    if (any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in probs.values())
            or abs(sum(probs.values()) - 1) > 1e-5):
        raise ValueError("d3_native_output_invalid")
    winner = max(keys, key=lambda k: probs[k])
    entropy = -sum(p * math.log(p) for p in probs.values() if p > 0)
    confidence = max(0.0, min(1.0, 1.0 - entropy / math.log(len(keys))))
    if answer["choice"] != winner or abs(answer["confidence"] - confidence) > 1e-6:
        raise ValueError("d3_native_output_invalid")
    return winner


def _predict(model, value, cap, torch):
    from deposium_bench.choice_protocol import ordered_choice_ids, validate_choice_input
    validate_choice_input(value)
    started = time.perf_counter()
    ids = ordered_choice_ids(value)
    keys = [f"c{i}" for i in range(len(ids))]
    question = {"type": "choice", "instructions": value["question"],
                "criteria": {key: option["description"] for key, option in zip(keys, value["options"])}}
    prepared, sequence = _prepared_full(model, value["context"], question)
    tokens = len(sequence)
    raw = {"native_result": None, "native_tokens": 0, "input_sha256": _input_hash(value),
           "ordered_ids": ids, "encoding_info": {"tokens": tokens, "stateTruncated": False,
                                                  "optionsTruncated": False},
           "forward_executed": False, "inference_ms": None, "decision_ms": None, "rss_mb": None}
    if tokens > cap:
        raw.update(decision_ms=(time.perf_counter() - started) * 1000, rss_mb=_rss())
        return {"status": "unsupported", "output": None, "error": "d3_context_overflow", "raw_output": raw}
    try:
        if _host_available_mb() < 4096:
            raise MemoryError("d3_worker_memory_low")
        inferred = time.perf_counter()
        probabilities, native_tokens = _checked_run(model, prepared, sequence, torch, raw)
        raw["inference_ms"] = (time.perf_counter() - inferred) * 1000
        native = model.respond(prepared, probabilities, native_tokens)
        raw["native_result"] = native
        raw["native_tokens"] = native_tokens
        winner = _valid_native(native, keys, tokens, model.model_name)
        raw.update(decision_ms=(time.perf_counter() - started) * 1000, rss_mb=_rss())
        return {"status": "ok", "output": {"choice_id": ids[keys.index(winner)]},
                "raw_output": raw, "error": None}
    except Exception:
        try:
            json.dumps(raw["native_result"], allow_nan=False)
        except (TypeError, ValueError):
            raw["native_result"] = None
        raw.update(decision_ms=(time.perf_counter() - started) * 1000, rss_mb=_rss())
        return {"status": "error", "output": None, "raw_output": raw, "error": "d3_inference_failed"}


def main():
    protocol = os.dup(sys.stdout.fileno())
    sink = os.open(os.devnull, os.O_WRONLY)
    os.dup2(sink, sys.stdout.fileno())
    os.close(sink)
    def emit(value):
        data = (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode()
        if len(data) > MAX_LINE:
            raise ValueError("d3_protocol_limit")
        while data:
            data = data[os.write(protocol, data):]
    try:
        request = _read()
        if not isinstance(request, dict) or set(request) != {"op", "config"} or request["op"] != "initialize":
            raise ValueError("d3_initialization_invalid")
        config = request["config"]
        if (not isinstance(config, dict) or set(config) != {"local_dir", "repo_id", "revision", "max_length", "threads",
                                                   "pins", "assets_manifest", "assets_manifest_sha256"}
                or config["repo_id"] not in MODELS or config["revision"] != MODELS[config["repo_id"]][0]
                or not isinstance(config["local_dir"], str) or not Path(config["local_dir"]).is_absolute()
                or not isinstance(config["assets_manifest"], str) or not Path(config["assets_manifest"]).is_absolute()
                or type(config["max_length"]) is not int or config["max_length"] != 4096
                or type(config["threads"]) is not int or config["threads"] != 2
                or not isinstance(config["assets_manifest_sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", config["assets_manifest_sha256"]) is None
                or not isinstance(config["pins"], dict) or not config["pins"]
                or any(not isinstance(k, str) or not isinstance(v, str) or not v
                       for k, v in config["pins"].items())):
            raise ValueError("d3_initialization_invalid")
        root = Path(config["local_dir"])
        _verify_bundle(root, Path(config["assets_manifest"]), config["assets_manifest_sha256"],
                       config["repo_id"], config["revision"])
        versions = _versions(config["pins"])
        _block_network()
        started = time.perf_counter()
        import torch
        torch.set_num_threads(config["threads"])
        sys.path.insert(0, str(root))
        from d3_runtime import D3
        model = D3.from_pretrained(root, device="cpu", batch_size=1, verify="fast",
                                   local_files_only=True, max_length=4096,
                                   readout_dtype="float32", permutation_average=False)
        _check_model(model, config["repo_id"], torch)
        if _host_available_mb() < 4096:
            raise MemoryError("d3_worker_memory_low")
        emit({"status": "ready", "runtime": versions, "load_ms": (time.perf_counter() - started) * 1000,
              "rss_mb": _rss(), "native_max_input_tokens": model.max_length,
              "checkpoint_max_input_tokens": model.config["max_length"],
              "device": "cpu", "backbone_dtype": "bfloat16", "readout_dtype": "float32",
              "backbone_parameters": MODELS[config["repo_id"]][1], "readout_shape": MODELS[config["repo_id"]][2],
              "loading_mode": LOADING_MODE})
    except (FileNotFoundError, ImportError, importlib.metadata.PackageNotFoundError):
        emit({"status": "error", "error": "d3_runtime_missing"})
        os.close(protocol)
        return
    except Exception:
        emit({"status": "error", "error": "d3_initialization_failed"})
        os.close(protocol)
        return
    try:
        while True:
            request = _read()
            if request is None:
                return
            if (not isinstance(request, dict) or set(request) != {"op", "sequence", "input"}
                    or request["op"] != "predict" or type(request["sequence"]) is not int
                    or request["sequence"] < 1 or not isinstance(request["input"], dict)):
                raise ValueError("d3_protocol_invalid")
            try:
                result = _predict(model, request["input"], config["max_length"], torch)
            except Exception:
                result = {"status": "error", "output": None, "raw_output": None,
                          "error": "d3_inference_failed"}
            emit({"sequence": request["sequence"], **result})
    finally:
        os.close(protocol)


if __name__ == "__main__":
    main()
