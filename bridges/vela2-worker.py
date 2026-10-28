"""Isolated, offline transport for the pinned upstream Vela2 CPU engine."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import resource
import socket
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deposium_bench.choice_protocol import ordered_choice_ids, validate_choice_input
from deposium_bench.worker_transport import MAX_LINE, decode

REPO_ID = "vllm-sr/Vela-2.0-0.3B"
REVISION = "d6f03aa9baca4f9017fa8f8e9c2764d3bed3f409"
# Exact named parameter elements in the pinned native model and safetensors.
# The Hub metadata omits two scalar temperatures in the encoder count.
PARAMETERS = 309114371
NATIVE_LIMIT = 8192
MODELS = {
    REPO_ID: (REVISION, PARAMETERS, NATIVE_LIMIT),
    "vllm-sr/Vela-2.0-0.8B": ("326b01d81f61fff7fd4ae570e54b87a49119e490", 754565954, 16384),
    # The pinned shard headers and publisher manifest count 4,211,182,082;
    # Hub aggregate metadata omits the scalar set_bias. _check_model requires
    # the exact shard names and shapes in the loaded native model before readiness.
    "vllm-sr/Vela-2.0-4B": ("d692394127f6f87fc581d8634c9558fe4776efce", 4211182082, 16384),
}
VELA4_REPO_ID = "vllm-sr/Vela-2.0-4B"
REQUIRED_SOURCE = {"vela2_inference.py", "modeling_vela2.py", "configuration_vela2.py",
                   "config.json", "calibration.json", "tokenizer.json"}


def _read():
    data = sys.stdin.buffer.readline(MAX_LINE + 1)
    if not data:
        return None
    if len(data) > MAX_LINE or not data.endswith(b"\n"):
        raise ValueError("vela2_protocol_limit")
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
        raise FileNotFoundError("vela2_asset_missing")
    manifest = decode(manifest_path.read_bytes())
    if (not isinstance(manifest, dict) or set(manifest) != {"schema_version", "repo_id", "revision", "files"}
            or manifest["schema_version"] != "deposium.model-assets/v1"
            or manifest["repo_id"] != repo_id or manifest["revision"] != revision
            or not isinstance(manifest["files"], list) or not manifest["files"]
            or len(manifest["files"]) > 10000):
        raise ValueError("vela2_asset_manifest_invalid")
    seen = set()
    for item in manifest["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "size", "sha256"}:
            raise ValueError("vela2_asset_manifest_invalid")
        name = item["path"]
        relative = Path(name) if isinstance(name, str) else Path(".")
        if (not isinstance(name, str) or relative.is_absolute() or not relative.parts
                or any(part in {".", "..", ".cache", "__pycache__"} for part in relative.parts)
                or relative.as_posix() != name or name in seen
                or type(item["size"]) is not int or item["size"] < 0
                or not isinstance(item["sha256"], str) or len(item["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in item["sha256"] )):
            raise ValueError("vela2_asset_manifest_invalid")
        path = root / relative
        if (path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve())
                or path.stat().st_size != item["size"] or _hash(path) != item["sha256"]):
            raise ValueError("vela2_asset_hash_mismatch")
        seen.add(name)
    actual = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".cache" in relative.parts or "__pycache__" in relative.parts:
            continue
        if path.is_symlink():
            raise ValueError("vela2_asset_symlink")
        if path.is_file():
            actual.add(relative.as_posix())
    if (actual != seen or not REQUIRED_SOURCE <= seen
            or (repo_id == VELA4_REPO_ID and "broad_head.safetensors" not in seen)
            or not any(name.endswith(".safetensors") for name in seen)):
        raise ValueError("vela2_asset_inventory_changed")


def _block_network():
    def blocked(*_args, **_kwargs):
        raise OSError("vela2_network_disabled")
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.socket.sendto = blocked
    socket.create_connection = blocked


def _versions(pins):
    actual = {name: importlib.metadata.version(name) for name in pins if name != "python"}
    actual["python"] = sys.version.split()[0]
    if any(actual.get(name) != version for name, version in pins.items()):
        raise ValueError("vela2_runtime_lock_mismatch")
    return actual


def _host_available_mb():
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


def _input_hash(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False) + "\n"
    return hashlib.sha256(payload.encode()).hexdigest()


def _complete_record(model, state, question):
    """Use upstream SystemOne conversion and assembly with a temporary permissive cap."""
    from vela2_inference import system_one_to_predict
    request, _ = system_one_to_predict(state, {"decision": question})
    parts, questions, _ = model._to_generic(request)
    row = model._prep({"parts": parts, "questions": questions})
    native_cap = model.max_len
    try:
        model.max_len = 1_000_000
        if hasattr(model, "_render"):
            record = model._render(row)
            record["head"] = row["head"]
        else:
            record = model._assemble(row)
    finally:
        model.max_len = native_cap
    if record["trunc"] != {"shrink_cut": 0, "protected_cut": 0}:
        raise ValueError("vela2_preflight_truncated")
    return record


def _tokens_in_record(record):
    return record["n_tokens"] if "n_tokens" in record else len(record["ids"])


def _serializable(value):
    if isinstance(value, dict):
        return {k: _serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(v) for v in value]
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        return value.item()
    return value


def _checked_decoder_backend(model, record, raw):
    """Verify the full native record and tokens entering the real embedding layer."""
    from deposium_bench.worker_transport import wire
    expected = wire(_serializable(record))
    backend = model.run
    embedding = backend.model.backbone.embed_tokens
    input_calls = []
    calls = 0
    def check_embedding(_module, args):
        if len(args) != 1:
            raise ValueError("vela2_embedding_payload_mismatch")
        actual = args[0].detach().cpu().tolist()
        index = len(input_calls)
        wanted = ([record["p_ids"]] if index == 0 else
                  [block["ids"] for block in record["blocks"]] if index == 1 else None)
        if wanted is None or len(actual) != len(wanted) or any(
                row[:len(ids)] != ids or (index == 0 and len(row) != len(ids))
                for row, ids in zip(actual, wanted)):
            raise ValueError("vela2_embedding_payload_mismatch")
        input_calls.append(True)
        raw["forward_executed"] = True
    hook = embedding.register_forward_pre_hook(check_embedding)
    def checked_run(recs):
        nonlocal calls
        if calls or len(recs) != 1 or wire(_serializable(recs[0])) != expected:
            raise ValueError("vela2_forward_payload_mismatch")
        calls += 1
        return backend(recs)
    return checked_run, hook, input_calls


def _expected_forward(model, record):
    """Ask upstream _forward to construct its exact backend arrays without inference."""
    import numpy as np
    original = model.run
    captured = []
    def capture(x, m, qi, oi, ui, ei):
        captured.append(tuple(a.copy() for a in (x, m, qi, oi, ui, ei)))
        return np.zeros((len(oi),), np.float32), np.zeros((len(ui), len(ei)), np.float32)
    try:
        model.run = capture
        model._forward([record])
    finally:
        model.run = original
    if len(captured) != 1:
        raise ValueError("vela2_preflight_forward_invalid")
    return captured[0]


def _predict(model, value, cap):
    started = time.perf_counter()
    floor = 4096 if getattr(model, "_repo_id", None) == VELA4_REPO_ID else 2048
    if _host_available_mb() < floor:
        raise MemoryError("vela2_host_memory_low")
    validate_choice_input(value)
    ids = ordered_choice_ids(value)
    criteria = {f"c{i}": option["description"] for i, option in enumerate(value["options"])}
    question = {"type": "choice", "instructions": value["question"], "criteria": criteria}
    record = _complete_record(model, value["context"], question)
    tokens = _tokens_in_record(record)
    raw = {"native_result": None, "native_tokens": 0, "input_sha256": _input_hash(value),
           "ordered_ids": ids, "encoding_info": {"tokens": tokens, "stateTruncated": False,
                                                  "optionsTruncated": False},
           "forward_executed": False, "inference_ms": None, "decision_ms": None, "rss_mb": None}
    if tokens > cap or tokens > model.max_len:
        raw.update(decision_ms=(time.perf_counter() - started) * 1000, rss_mb=_rss())
        return {"status": "unsupported", "output": None, "error": "vela2_context_overflow", "raw_output": raw}
    decoder = "n_tokens" in record
    expected = _expected_forward(model, record) if not decoder else None
    backend = model.run
    calls = 0
    def checked_encoder_run(*arrays):
        nonlocal calls
        if calls or len(arrays) != 6 or any(actual.shape != wanted.shape
                                             or actual.dtype != wanted.dtype or not (actual == wanted).all()
                                             for actual, wanted in zip(arrays, expected)):
            raise ValueError("vela2_forward_payload_mismatch")
        calls += 1
        raw["forward_executed"] = True
        return backend(*arrays)
    hook = None
    embedding_calls = None
    try:
        if decoder:
            checked_run, hook, embedding_calls = _checked_decoder_backend(model, record, raw)
        else:
            checked_run = checked_encoder_run
        model.run = checked_run
        inference_start = time.perf_counter()
        native = model.system_one(state=value["context"], questions={"decision": question},
                                  model=model._repo_id if hasattr(model, "_repo_id") else REPO_ID)
        raw["inference_ms"] = (time.perf_counter() - inference_start) * 1000 if raw["forward_executed"] else None
        raw["native_result"] = native
        raw["native_tokens"] = native.get("usage", {}).get("input_tokens") if isinstance(native, dict) else 0
        answer = native["answers"]["decision"]
        probabilities = answer["probabilities"]
        keys = list(criteria)
        if ((not decoder and calls != 1) or (decoder and len(embedding_calls) != 2)
                or set(native) != {"model", "answers", "usage"}
                or native["model"] != (model._repo_id if hasattr(model, "_repo_id") else REPO_ID)
                or set(native["answers"]) != {"decision"} or set(native["usage"]) != {"input_tokens", "output_tokens"}
                or raw["native_tokens"] != tokens or native["usage"]["output_tokens"] != 0
                or set(answer) != {"type", "choice", "probabilities", "confidence"}
                or answer["type"] != "choice" or answer["choice"] not in keys
                or type(answer["confidence"]) not in (int, float) or not math.isfinite(answer["confidence"])
                or not 0 <= answer["confidence"] <= 1 or not isinstance(probabilities, dict)
                or list(probabilities) != keys
                or any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
                       for p in probabilities.values())
                or abs(sum(probabilities.values()) - 1) > 1e-5):
            raise ValueError("vela2_native_output_invalid")
        highest = max(probabilities.values())
        winner = next(key for key in keys if probabilities[key] == highest)
        sorted_probs = sorted(probabilities.values(), reverse=True)
        confidence = min(1.0, max(0.0, sorted_probs[0] - sorted_probs[1]))
        if answer["choice"] != winner or abs(answer["confidence"] - confidence) > 1e-6:
            raise ValueError("vela2_native_output_invalid")
        raw.update(decision_ms=(time.perf_counter() - started) * 1000, rss_mb=_rss())
        return {"status": "ok", "output": {"choice_id": ids[keys.index(winner)]},
                "error": None, "raw_output": raw}
    except Exception:
        try:
            json.dumps(raw["native_result"], allow_nan=False)
        except (TypeError, ValueError):
            raw["native_result"] = None
        raw.update(decision_ms=(time.perf_counter() - started) * 1000, rss_mb=_rss())
        return {"status": "error", "output": None, "error": "vela2_inference_failed", "raw_output": raw}
    finally:
        model.run = backend
        if hook is not None:
            hook.remove()


def _load_engine(root, repo_id, threads, torch):
    """Load the audited upstream engine without a second FP32 weight copy for 0.3B."""
    from vela2_inference import Vela2
    if repo_id == REPO_ID:
        from transformers import AutoModel
        native_model = AutoModel.from_pretrained(
            str(root), trust_remote_code=True, local_files_only=True,
            dtype=torch.float32, attn_implementation="sdpa").eval()
        if type(native_model).__name__ != "Vela2Model":
            raise ValueError("vela2_native_model_invalid")
        return (Vela2(root, backend="torch", device="cpu", threads=threads, model=native_model),
                "hf-automodel-fp32")
    return Vela2(root, backend="torch", device="cpu", amp_bf16=False), "native-decoder-fp32"


def _safetensors_shapes(path):
    """Read only the pinned local shard header; never load a second weight copy."""
    with path.open("rb") as stream:
        prefix = stream.read(8)
        if len(prefix) != 8:
            raise ValueError("vela2_safetensors_header_invalid")
        size = struct.unpack("<Q", prefix)[0]
        if not 2 <= size <= 64 * 1024 * 1024:
            raise ValueError("vela2_safetensors_header_invalid")
        header = decode(stream.read(size))
    if not isinstance(header, dict):
        raise ValueError("vela2_safetensors_header_invalid")
    shapes = {}
    for name, meta in header.items():
        if name == "__metadata__":
            continue
        shape = meta.get("shape") if isinstance(meta, dict) else None
        if (not isinstance(name, str) or not name or not isinstance(shape, list)
                or any(type(dim) is not int or dim < 1 for dim in shape)):
            raise ValueError("vela2_safetensors_header_invalid")
        shapes[name] = tuple(shape)
    if not shapes:
        raise ValueError("vela2_safetensors_header_invalid")
    return shapes


def _pinned_shapes(root):
    index = decode((root / "model.safetensors.index.json").read_bytes())
    weight_map = index.get("weight_map") if isinstance(index, dict) else None
    if not isinstance(weight_map, dict) or not weight_map:
        raise ValueError("vela2_weight_index_invalid")
    files = set(weight_map.values())
    if (not all(isinstance(name, str) and name.startswith("model-")
                and name.endswith(".safetensors") and "/" not in name for name in files)
            or len(files) != 3):
        raise ValueError("vela2_weight_index_invalid")
    shapes = {}
    for name in sorted(files):
        shard = _safetensors_shapes(root / name)
        if shapes.keys() & shard.keys() or set(shard) != {
                key for key, shard_name in weight_map.items() if shard_name == name}:
            raise ValueError("vela2_weight_index_invalid")
        shapes.update(shard)
    if set(shapes) != set(weight_map):
        raise ValueError("vela2_weight_index_invalid")
    broad = _safetensors_shapes(root / "broad_head.safetensors")
    if any(not name.startswith("span_broad.") for name in broad):
        raise ValueError("vela2_weight_index_invalid")
    return shapes, broad


def _check_model(model, repo_id, torch, root=None):
    parameters = list(model.run.model.named_parameters())
    broad_count = sum(p.numel() for name, p in parameters if name.startswith("span_broad."))
    if repo_id == VELA4_REPO_ID:
        if root is None:
            raise ValueError("vela2_model_identity_invalid")
        shards, broad = _pinned_shapes(root)
        loaded = {name: tuple(p.shape) for name, p in parameters}
        if (sum(math.prod(shape) for shape in shards.values()) != MODELS[repo_id][1]
                or loaded != {**shards, **broad}):
            raise ValueError("vela2_model_identity_invalid")
    if (model.max_len != MODELS[repo_id][2] or not parameters
            or sum(p.numel() for name, p in parameters if not name.startswith("span_broad.")) != MODELS[repo_id][1]
            or (repo_id not in (REPO_ID, VELA4_REPO_ID) and broad_count != 1119745)
            or (repo_id == VELA4_REPO_ID and broad_count != sum(math.prod(shape) for shape in broad.values()))
            or any(p.dtype != torch.float32 or p.device.type != "cpu" for _, p in parameters)):
        raise ValueError("vela2_model_identity_invalid")


def main():
    protocol = os.dup(sys.stdout.fileno())
    sink = os.open(os.devnull, os.O_WRONLY)
    os.dup2(sink, sys.stdout.fileno())
    os.close(sink)
    def emit(value):
        data = (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode()
        if len(data) > MAX_LINE:
            raise ValueError("vela2_protocol_limit")
        while data:
            data = data[os.write(protocol, data):]
    try:
        request = _read()
        if not isinstance(request, dict) or set(request) != {"op", "config"} or request["op"] != "initialize":
            raise ValueError("vela2_initialization_invalid")
        config = request["config"]
        if (not isinstance(config, dict) or set(config) != {"local_dir", "repo_id", "revision", "max_length", "threads",
                                                   "pins", "assets_manifest", "assets_manifest_sha256"}
                or config["repo_id"] not in MODELS or config["revision"] != MODELS[config["repo_id"]][0]
                or not isinstance(config["local_dir"], str) or not Path(config["local_dir"]).is_absolute()
                or not isinstance(config["assets_manifest"], str) or not Path(config["assets_manifest"]).is_absolute()
                or type(config["max_length"]) is not int or not 1 <= config["max_length"] <= 4096
                or type(config["threads"]) is not int or not 1 <= config["threads"] <= 2
                or not isinstance(config["pins"], dict)):
            raise ValueError("vela2_initialization_invalid")
        root = Path(config["local_dir"])
        _verify_bundle(root, Path(config["assets_manifest"]), config["assets_manifest_sha256"],
                       config["repo_id"], config["revision"])
        versions = _versions(config["pins"])
        _block_network()
        started = time.perf_counter()
        import torch
        torch.set_num_threads(config["threads"])
        sys.path.insert(0, str(root))
        model, loading_mode = _load_engine(root, config["repo_id"], config["threads"], torch)
        model._repo_id = config["repo_id"]
        _check_model(model, config["repo_id"], torch, root)
        emit({"status": "ready", "runtime": versions, "load_ms": (time.perf_counter() - started) * 1000,
              "rss_mb": _rss(), "native_max_input_tokens": model.max_len,
              "device": "cpu", "dtype": "float32", "loading_mode": loading_mode})
    except (FileNotFoundError, ImportError, importlib.metadata.PackageNotFoundError):
        emit({"status": "error", "error": "vela2_runtime_missing"})
        os.close(protocol)
        return
    except Exception:
        emit({"status": "error", "error": "vela2_initialization_failed"})
        os.close(protocol)
        return
    try:
        while True:
            request = _read()
            if request is None:
                return
            if not isinstance(request, dict) or set(request) != {"op", "sequence", "input"} or request["op"] != "predict":
                raise ValueError("vela2_protocol_invalid")
            try:
                result = _predict(model, request["input"], config["max_length"])
            except Exception:
                result = {"status": "error", "output": None, "raw_output": None,
                          "error": "vela2_inference_failed"}
            emit({"sequence": request["sequence"], **result})
    finally:
        os.close(protocol)


if __name__ == "__main__":
    main()
