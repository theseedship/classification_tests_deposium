"""Persistent local Julia CPU worker. No imports or model work until main()."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import resource
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deposium_bench.choice_protocol import CONTEXT_CHOICE_PROMPT, choice_row, ordered_choice_ids

MAX_LINE = 1024 * 1024
ENCODING_ERRORS = {
    "Option exceeds 48-token model contract": "julia_option_overflow",
    "Question/options exceed lossless head budget": "julia_head_overflow",
    "Question/options exceed sequence budget; shorten descriptions": "julia_context_overflow",
    "Game state exceeds lossless context budget": "julia_context_overflow",
    "Reserved model marker in request": "julia_reserved_marker",
}


def _read():
    data = sys.stdin.buffer.readline(MAX_LINE + 1)
    if not data:
        return None
    if len(data) > MAX_LINE or not data.endswith(b"\n"):
        raise ValueError("protocol_limit")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))


def _rss():
    # Linux reports ru_maxrss in KiB. The parent also observes current /proc RSS.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _input_json(value):
    forbidden = {"gold", "expected", "expected_output", "reference", "reference_output", "annotations",
                 "annotation", "assertions", "rationale"}
    def check(item):
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str) or key.lower() in forbidden:
                    raise ValueError("invalid_input")
                check(child)
            return
        if isinstance(item, list):
            for child in item:
                check(child)
            return
        raise ValueError("invalid_input")
    if not isinstance(value, dict) or not value:
        raise ValueError("invalid_input")
    check(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def main():
    # Native library writes and application logs cannot enter the JSON channel.
    protocol = os.dup(sys.stdout.fileno())
    sink = os.open(os.devnull, os.O_WRONLY)
    os.dup2(sink, sys.stdout.fileno())
    os.close(sink)
    def emit(value):
        data = (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode()
        if len(data) > MAX_LINE:
            raise ValueError("protocol_limit")
        view = memoryview(data)
        while view:
            written = os.write(protocol, view)
            view = view[written:]
    try:
        initialize = _read()
        if not isinstance(initialize, dict) or set(initialize) != {"op", "config"} or initialize["op"] != "initialize":
            raise ValueError("initialization_invalid")
        config = initialize["config"]
        if not isinstance(config, dict) or set(config) != {"local_dir", "prompt", "revision", "max_length", "head_length", "threads"}:
            raise ValueError("initialization_invalid")
        local_dir = Path(config["local_dir"])
        if not local_dir.is_dir() or not local_dir.is_absolute():
            raise FileNotFoundError("model_missing")
        prompt = config["prompt"]
        choice_mode = prompt == CONTEXT_CHOICE_PROMPT
        if not choice_mode:
            options = prompt["options"]
            ordered_ids = [option["id"] for option in options]
            if set(ordered_ids) != {"catalog", "stored_summaries", "retrieve_answer", "abstain"} or len(ordered_ids) != 4:
                raise ValueError("prompt_invalid")
        start = time.perf_counter()
        sys.path.insert(0, str(local_dir))
        import torch
        torch.set_num_threads(config["threads"])
        from julia import load_model
        engine = load_model(str(local_dir), device="cpu", backend="torch", strict_encoding=True,
                            max_length=config["max_length"], head_length=config["head_length"], batch_size=1,
                            compile_model=False, bend_postprocess=False, memory_map=True, marker_only_head=False)
        runtime = {name: importlib.metadata.version(name) for name in ("torch", "transformers", "tokenizers", "numpy")}
        runtime["python"] = sys.version.split()[0]
        emit({"status": "ready", "runtime": runtime, "load_ms": (time.perf_counter() - start) * 1000, "rss_mb": _rss()})
    except (ImportError, FileNotFoundError, importlib.metadata.PackageNotFoundError):
        emit({"status": "error", "error": "julia_runtime_missing"})
        os.close(protocol)
        return
    except Exception:
        emit({"status": "error", "error": "julia_initialization_failed"})
        os.close(protocol)
        return
    try:
        while True:
            request = _read()
            if request is None:
                return
            sequence = request.get("sequence") if isinstance(request, dict) else None
            decision_start = time.perf_counter()
            forward_executed = False
            try:
                if (not isinstance(request, dict) or set(request) != {"op", "sequence", "input"}
                        or request["op"] != "predict" or type(sequence) is not int or sequence < 1):
                    raise ValueError("request_invalid")
                canonical_input = _input_json(request["input"])
                if choice_mode:
                    row = choice_row(request["input"])
                    ordered_ids = ordered_choice_ids(request["input"])
                else:
                    row = {"state": canonical_input, "question": prompt["question"],
                           "options": [option["description"] for option in options], "type": "choice"}
                inference_start = time.perf_counter()
                # The official strict encoder rejects overflow before model forward.
                encoding_info = engine.encoding_info([row])
                if not isinstance(encoding_info, list) or len(encoding_info) != 1:
                    raise ValueError("encoding_audit_invalid")
                forward_executed = True
                scores = engine.logits([row])
                logits = [float(value) for value in scores[0]]
                if len(scores) != 1 or len(logits) != len(ordered_ids) or not all(math.isfinite(value) for value in logits):
                    raise ValueError("logits_invalid")
                exponentials = [math.exp(value - max(logits)) for value in logits]
                probabilities = [value / sum(exponentials) for value in exponentials]
                winner = ordered_ids[max(range(len(logits)), key=lambda index: logits[index])]
                input_sha256 = hashlib.sha256(canonical_input.encode()).hexdigest()
                inference_ms = (time.perf_counter() - inference_start) * 1000
                raw = {"logits": logits, "probabilities": probabilities, "ordered_ids": ordered_ids,
                       "input_sha256": input_sha256,
                       "inference_ms": inference_ms, "rss_mb": _rss(), "encoding_info": encoding_info[0]}
                # Julia's token cache already contains these exact fields after encoding_info.
                if hasattr(engine, "_tokens"):
                    audit = encoding_info[0]
                    raw["token_components"] = {
                        "state": len(engine._tokens(row["state"], add_special_tokens=False)["input_ids"]),
                        "question": len(engine._tokens(f"choice question: {row['question']}", add_special_tokens=False)["input_ids"]),
                        "options": audit["optionTokens"], "special": len(ordered_ids) + 4, "total": audit["tokens"],
                        "padded": min(config["max_length"], ((audit["tokens"] + 7) // 8) * 8),
                    }
                raw["decision_ms"] = (time.perf_counter() - decision_start) * 1000
                abstain = not choice_mode and winner == "abstain"
                emit({"sequence": sequence, "status": "abstain" if abstain else "ok",
                      "output": {"choice_id": winner} if choice_mode else (None if abstain else {"task": winner}),
                      "error": None, "raw_output": raw})
            except Exception as error:
                code = ENCODING_ERRORS.get(str(error)) if type(error) is ValueError and not forward_executed else None
                emit({"sequence": sequence, "status": "error", "output": None,
                      "raw_output": {"decision_ms": (time.perf_counter() - decision_start) * 1000,
                                     "inference_ms": None, "forward_executed": False} if code else None,
                      "error": code or "julia_inference_failed"})
    finally:
        os.close(protocol)


if __name__ == "__main__":
    main()
