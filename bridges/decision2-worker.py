"""Official Decision 2.0 CPU runtime, verified and isolated from the network."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import resource
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deposium_bench.choice_protocol import ordered_choice_ids, validate_choice_input

MAX_LINE = 1024 * 1024
MODELS = {
    "vllm-sr/Decision-2.0-Eos-0.8B":
        ("3594047d69f476f1d01cf84c593e213fc3a4dfe0", "Decision-2.0-Eos-0.8B", 16384),
    "vllm-sr/Decision-2.0-Kai-0.6B":
        ("cd49ea3813fd8ba0928a9a23ef6c9a0f2f0cd764", "Decision-2.0-Kai-0.6B", 8192),
    "vllm-sr/Decision-2.0-Nox-4B":
        ("ae269ecf34a0b3a89026bc1afd9c995279212fad", "Decision-2.0-Nox-4B", 16384),
}


def _read():
    data = sys.stdin.buffer.readline(MAX_LINE + 1)
    if not data:
        return None
    if len(data) > MAX_LINE or not data.endswith(b"\n"):
        raise ValueError("decision2_protocol_limit")
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))


def _rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _host_available_mb():
    available = None
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            available = int(line.split()[1]) / 1024
            break
    if available is None:
        raise OSError("decision2_host_memory_unknown")
    limit, current = Path("/sys/fs/cgroup/memory.max"), Path("/sys/fs/cgroup/memory.current")
    if limit.is_file() and current.is_file():
        bound = limit.read_text().strip()
        if bound != "max":
            available = min(available, max(0, (int(bound) - int(current.read_text().strip())) / 1048576))
    return available


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_bundle(root, repo_id, revision):
    """Check every publisher-manifest byte before importing publisher Python."""
    if root.is_symlink() or not root.is_dir():
        raise FileNotFoundError("decision2_model_missing")
    manifest_file = root / "MODEL_MANIFEST.json"
    if manifest_file.is_symlink() or not manifest_file.is_file() or manifest_file.stat().st_size > MAX_LINE:
        raise FileNotFoundError("decision2_model_missing")
    manifest = json.loads(manifest_file.read_text())
    files = manifest.get("files_sha256")
    if repo_id not in MODELS or revision != MODELS[repo_id][0]:
        raise ValueError("decision2_revision_invalid")
    expected_name, native_limit = MODELS[repo_id][1:]
    if (not isinstance(files, dict) or not files or manifest.get("schema") != "dev2-package-manifest/1"
            or manifest.get("repo_id") != repo_id
            or manifest.get("model_name") != expected_name
            or manifest.get("profile") != "qwen-full" or manifest.get("max_input_tokens") != native_limit
            or len(files) > 10000):
        raise ValueError("decision2_bundle_invalid")
    expected = {"MODEL_MANIFEST.json", ".gitattributes"}
    for name, digest in files.items():
        relative = Path(name) if isinstance(name, str) else Path(".")
        if (not isinstance(name, str) or relative.is_absolute() or not relative.parts
                or any(part in {".", ".."} for part in relative.parts)
                or relative.as_posix() != name or not isinstance(digest, str) or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)):
            raise ValueError("decision2_bundle_invalid")
        path = root / relative
        if path.is_symlink() or not path.is_file() or _hash(path) != digest:
            raise ValueError("decision2_bundle_hash_mismatch")
        expected.add(name)
    actual = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".cache" in relative.parts or "__pycache__" in relative.parts:
            continue
        if path.is_symlink():
            raise ValueError("decision2_bundle_symlink")
        if path.is_file():
            actual.add(relative.as_posix())
    if actual != expected and actual != expected - {".gitattributes"}:
        raise ValueError("decision2_bundle_inventory_changed")
    return manifest


def _block_network():
    def blocked(*_args, **_kwargs):
        raise OSError("decision2_network_disabled")
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.socket.sendto = blocked
    socket.create_connection = blocked


def _versions(pins):
    actual = {name: importlib.metadata.version(name) for name in pins if name != "python"}
    actual["python"] = sys.version.split()[0]
    if any(actual.get(name) != version for name, version in pins.items()):
        raise ValueError("decision2_runtime_lock_mismatch")
    return actual


def _input_hash(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False) + "\n"
    return hashlib.sha256(payload.encode()).hexdigest()


def _predict(model, value, cap):
    started = time.perf_counter()
    floor = 4096 if getattr(model, "model_name", None) == "Decision-2.0-Nox-4B" else 1024
    if _host_available_mb() < floor:  # the worker's own RSS is already out of MemAvailable
        raise MemoryError("decision2_host_memory_low")
    validate_choice_input(value)
    ids = ordered_choice_ids(value)
    criteria = {f"c{i}": option["description"] for i, option in enumerate(value["options"])}
    question = {"type": "choice", "instructions": value["question"], "criteria": criteria}
    native_input = {"id": "request", "state": value["context"]}
    from decision2._vendor.dev2model.infer import question_to_row
    from decision2._vendor.dev2model.decision_model import collate, encode
    row = question_to_row(native_input, "decision", question)
    # Official encoder, with a permissive preflight ceiling solely to count the
    # complete sequence. The published runtime enforces its native cap.
    encoded = encode(row, model.backend.tokenizer, 1_000_000)
    tokens = len(encoded["ids"])
    raw = {"native_result": None, "native_tokens": 0, "input_sha256": _input_hash(value),
           "ordered_ids": ids, "encoding_info": {"tokens": tokens, "stateTruncated": False,
                                                  "optionsTruncated": False},
           "forward_executed": False, "inference_ms": None, "decision_ms": None, "rss_mb": None}
    if tokens > cap or tokens > model.max_input_tokens:
        raw.update(decision_ms=(time.perf_counter() - started) * 1000, rss_mb=_rss())
        return {"status": "unsupported", "output": None, "error": "decision2_context_overflow", "raw_output": raw}
    pad_id = model.backend.tokenizer.pad_token_id
    if pad_id is None:
        pad_id = model.backend.tokenizer.eos_token_id
    expected_batch = collate([encoded], pad_id)
    forward_count = 0
    def mark_forward(_module, args, kwargs):
        nonlocal forward_count
        if args or set(kwargs) != set(expected_batch):
            raise ValueError("decision2_forward_payload_mismatch")
        for name, expected in expected_batch.items():
            actual = kwargs[name]
            if not hasattr(actual, "detach") or not actual.detach().cpu().equal(expected):
                raise ValueError("decision2_forward_payload_mismatch")
        forward_count += 1
        raw["forward_executed"] = True
    hook = model.backend.model.register_forward_pre_hook(mark_forward, with_kwargs=True)
    try:
        inference_start = time.perf_counter()
        native = model.system_one(state=value["context"], questions={"decision": question},
                                  share_context=False)
        elapsed = (time.perf_counter() - inference_start) * 1000
        raw["native_result"] = native
        raw["native_tokens"] = native.get("usage", {}).get("input_tokens") if isinstance(native, dict) else 0
        raw["inference_ms"] = elapsed if forward_count else None
        answer = native["answers"]["decision"]
        keys = list(criteria)
        probabilities = answer["probabilities"]
        if (forward_count < 1 or native.get("model") != model.model_name
                or set(answer) != {"type", "choice", "probabilities", "confidence"}
                or answer.get("type") != "choice" or answer.get("choice") not in keys
                or type(answer["confidence"]) not in (int, float) or not math.isfinite(answer["confidence"])
                or not 0 <= answer["confidence"] <= 1
                or not isinstance(probabilities, dict) or list(probabilities) != keys
                or any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
                       for p in probabilities.values())
                or abs(sum(probabilities.values()) - 1) > 1e-5
                or raw["native_tokens"] != tokens or native.get("usage", {}).get("output_tokens") != 0):
            raise ValueError("decision2_native_output_invalid")
        highest = max(probabilities.values())
        first_winner = next(key for key in keys if probabilities[key] == highest)
        entropy = -sum(p * math.log(p) for p in probabilities.values() if p > 0)
        confidence = max(0.0, min(1.0, 1.0 - entropy / math.log(len(keys))))
        if answer["choice"] != first_winner or abs(answer["confidence"] - confidence) > 1e-6:
            raise ValueError("decision2_native_output_invalid")
        raw.update(decision_ms=(time.perf_counter() - started) * 1000, rss_mb=_rss())
        return {"status": "ok", "output": {"choice_id": ids[keys.index(answer["choice"])]},
                "error": None, "raw_output": raw}
    except Exception:
        try:
            json.dumps(raw["native_result"], allow_nan=False)
        except (TypeError, ValueError):
            raw["native_result"] = None
        raw.update(decision_ms=(time.perf_counter() - started) * 1000, rss_mb=_rss())
        return {"status": "error", "output": None, "error": "decision2_inference_failed", "raw_output": raw}
    finally:
        hook.remove()


def main():
    protocol = os.dup(sys.stdout.fileno())
    sink = os.open(os.devnull, os.O_WRONLY)
    os.dup2(sink, sys.stdout.fileno())
    os.close(sink)
    def emit(value):
        data = (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode()
        if len(data) > MAX_LINE:
            raise ValueError("decision2_protocol_limit")
        while data:
            written = os.write(protocol, data)
            data = data[written:]
    try:
        request = _read()
        if not isinstance(request, dict) or set(request) != {"op", "config"} or request["op"] != "initialize":
            raise ValueError("decision2_initialization_invalid")
        config = request["config"]
        if (not isinstance(config, dict) or set(config) != {"local_dir", "repo_id", "revision", "max_length", "threads", "pins"}
                or not isinstance(config["local_dir"], str) or not Path(config["local_dir"]).is_absolute()
                or type(config["max_length"]) is not int or not 1 <= config["max_length"] <= 4096
                or type(config["threads"]) is not int or not 1 <= config["threads"] <= 2
                or not isinstance(config["pins"], dict)):
            raise ValueError("decision2_initialization_invalid")
        root = Path(config["local_dir"])
        _verify_bundle(root, config["repo_id"], config["revision"])
        versions = _versions(config["pins"])
        _block_network()
        started = time.perf_counter()
        import torch
        torch.set_num_threads(config["threads"])
        sys.path.insert(0, str(root))
        from decision2 import Decision2
        model = Decision2.from_pretrained(root, device="cpu", threads=config["threads"],
                                          bf16_resident=False, graphs=False, kernels=False,
                                          share_context=False)
        if (model.model_name != MODELS[config["repo_id"]][1]
                or model.max_input_tokens != MODELS[config["repo_id"]][2]
                or str(model.backend.device) != "cpu"
                or any(parameter.dtype != torch.float32 for parameter in model.backend.model.parameters())):
            raise ValueError("decision2_model_identity_invalid")
        emit({"status": "ready", "runtime": versions, "load_ms": (time.perf_counter() - started) * 1000,
              "rss_mb": _rss(), "native_max_input_tokens": model.max_input_tokens,
              "device": "cpu", "dtype": "float32"})
    except (FileNotFoundError, ImportError, importlib.metadata.PackageNotFoundError):
        emit({"status": "error", "error": "decision2_runtime_missing"})
        os.close(protocol)
        return
    except Exception:
        emit({"status": "error", "error": "decision2_initialization_failed"})
        os.close(protocol)
        return
    try:
        while True:
            request = _read()
            if request is None:
                return
            if not isinstance(request, dict) or set(request) != {"op", "sequence", "input"} or request["op"] != "predict":
                raise ValueError("decision2_protocol_invalid")
            try:
                result = _predict(model, request["input"], config["max_length"])
            except Exception:
                result = {"status": "error", "output": None, "raw_output": None,
                          "error": "decision2_inference_failed"}
            emit({"sequence": request["sequence"], **result})
    finally:
        os.close(protocol)


if __name__ == "__main__":
    main()
