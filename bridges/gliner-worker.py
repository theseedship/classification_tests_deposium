"""Persistent official GLiNER2 CPU classifier; no candidate imports on import."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import resource
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deposium_bench.choice_protocol import validate_choice_input
from deposium_bench.gliner_adapter import GLINER_CHOICE_PROMPT

MAX_LINE = 1024 * 1024
MARKERS = ("[SEP_STRUCT]", "[SEP_TEXT]", "[P]", "[C]", "[E]", "[R]", "[L]",
           "[EXAMPLE]", "[OUTPUT]", "[DESCRIPTION]", "[CLS]", "[SEP]", "[MASK]", "[PAD]", "[UNK]")


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
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _canonical(value):
    validate_choice_input(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _tensor_rows(value):
    return value.detach().cpu().tolist()


def _runtime_sources():
    """Fingerprint the installed wheel's GLiNER Python sources, never caches."""
    distribution = importlib.metadata.distribution("gliner2")
    sources = {}
    total_bytes = 0
    for relative in distribution.files or ():
        name = str(relative).replace("\\", "/")
        parts = Path(name).parts
        if not parts or parts[0] != "gliner2" or not name.endswith(".py") or "__pycache__" in parts:
            continue
        if Path(name).is_absolute() or ".." in parts or name in sources or len(sources) >= 1000:
            raise ValueError("runtime_sources_invalid")
        content = Path(distribution.locate_file(relative)).read_bytes()
        total_bytes += len(content)
        if total_bytes > 10 * 1024 * 1024:
            raise ValueError("runtime_sources_invalid")
        sources[name] = hashlib.sha256(content).hexdigest()
    if "gliner2/auto.py" not in sources or "gliner2/models/boundary/model.py" not in sources:
        raise ValueError("runtime_sources_missing")
    payload = json.dumps(sources, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    return str(Path(distribution.locate_file("")).resolve()), sources, hashlib.sha256(payload).hexdigest()


def _predict(engine, torch, value, max_length):
    started = time.perf_counter()
    canonical = _canonical(value)
    labels = [option["description"] for option in value["options"]]
    fields = [value["context"], value["question"], *labels]
    if any(marker.lower() in field.lower() for marker in MARKERS for field in fields):
        raise ValueError("reserved_marker")
    tasks = {"answer": {"labels": labels, "prompt": value["question"], "multi_label": False,
                         "class_act": "softmax"}}
    # The official collation appends punctuation, then lowercases word values.
    # Keep this declared normalization separate from the original request hash.
    model_text = value["context"]
    if not model_text.endswith((".", "!", "?")):
        model_text += "."
    engine.eval()
    engine.processor.change_mode(is_training=False)
    schema = engine._classification_schema(tasks)
    schema_dicts, _ = engine._build_schema_dicts_and_metadata([schema])
    batch = engine.processor.collate_fn_inference(
        [(value["context"], schema_dicts[0])], max_len=None, error_policy="raise", architecture="boundary")
    expected_ids = _tensor_rows(batch.input_ids)
    expected_mask = _tensor_rows(batch.attention_mask)
    if (len(expected_ids) != 1 or len(expected_mask) != 1 or len(expected_ids[0]) != len(expected_mask[0])
            or any(mask != 1 for mask in expected_mask[0])):
        raise ValueError("encoding_audit_invalid")
    # This direct formatter uses the same punctuation-normalized text as collation.
    transformed = engine.processor.transform_and_format(model_text, schema_dicts[0])
    if transformed.input_ids != expected_ids[0] or transformed.text != model_text:
        raise ValueError("encoding_audit_invalid")
    words = list(engine.processor.word_splitter(model_text, lower=True))
    if transformed.text_tokens != [word for word, _, _ in words] or batch.text_word_counts != [len(words)]:
        raise ValueError("encoding_audit_invalid")
    schema_tokens = len(engine.processor._format_input_with_mapping(transformed.schema_tokens_list, [])['input_ids'])
    tokens = len(expected_ids[0])
    if schema_tokens > tokens:
        raise ValueError("encoding_audit_invalid")
    raw = {"native_result": None, "ordered_ids": [option["id"] for option in value["options"]],
           "input_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
           "model_text_sha256": hashlib.sha256(model_text.encode()).hexdigest(),
           "preprocessing": {"appended_punctuation": model_text != value["context"], "lowercase": True},
           "encoding_info": {"tokens": tokens, "stateTruncated": False, "optionsTruncated": False},
           "token_components": {"schema_tokens": schema_tokens, "content_tokens": tokens - schema_tokens,
                                "total_tokens": tokens, "padded_tokens": tokens, "content_words": len(words)},
           "inference_ms": None, "forward_executed": False}
    if tokens > max_length:
        raw.update(decision_ms=(time.perf_counter() - started) * 1000, rss_mb=_rss())
        return {"status": "unsupported", "output": None, "error": "gliner_context_overflow", "raw_output": raw}
    forwards = 0
    def guard(module, args, kwargs):
        nonlocal forwards
        if (args or _tensor_rows(kwargs["input_ids"]) != expected_ids
                or _tensor_rows(kwargs["attention_mask"]) != expected_mask or forwards):
            raise ValueError("encoding_audit_mismatch")
        forwards += 1
        raw["forward_executed"] = True
    hook = engine.encoder.register_forward_pre_hook(guard, with_kwargs=True)
    try:
        inference_start = time.perf_counter()
        with torch.inference_mode():
            result = engine.classify_text(value["context"], tasks, include_confidence=True, max_len=None)
        raw["inference_ms"] = (time.perf_counter() - inference_start) * 1000
        answer = result.get("answer") if isinstance(result, dict) else None
        if (forwards != 1 or set(result) != {"answer"} or not isinstance(answer, dict)
                or set(answer) != {"label", "confidence"} or answer["label"] not in labels
                or type(answer["confidence"]) not in (float, int) or not math.isfinite(answer["confidence"])
                or not 0 <= answer["confidence"] <= 1):
            raise ValueError("native_output_invalid")
        raw["native_result"] = result
        raw.update(decision_ms=(time.perf_counter() - started) * 1000, rss_mb=_rss())
        winner = value["options"][labels.index(answer["label"])]["id"]
        return {"status": "ok", "output": {"choice_id": winner}, "error": None, "raw_output": raw}
    except Exception:
        raw.update(decision_ms=(time.perf_counter() - started) * 1000, rss_mb=_rss())
        return {"status": "error", "output": None, "error": "gliner_inference_failed", "raw_output": raw}
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
            raise ValueError("protocol_limit")
        view = memoryview(data)
        while view:
            written = os.write(protocol, view)
            view = view[written:]
    try:
        initialize = _read()
        if (not isinstance(initialize, dict) or set(initialize) != {"op", "config"}
                or initialize["op"] != "initialize"):
            raise ValueError("initialization_invalid")
        config = initialize["config"]
        if (not isinstance(config, dict) or set(config) != {"local_dir", "prompt", "revision", "max_length", "threads"}
                or config["prompt"] != GLINER_CHOICE_PROMPT or type(config["max_length"]) is not int
                or not 1 <= config["max_length"] <= 4096 or type(config["threads"]) is not int
                or not 1 <= config["threads"] <= 16 or not isinstance(config["revision"], str)
                or not re.fullmatch(r"[0-9a-f]{40}", config["revision"])):
            raise ValueError("initialization_invalid")
        local_dir = Path(config["local_dir"])
        if not local_dir.is_absolute() or not local_dir.is_dir():
            raise FileNotFoundError("model_missing")
        for name in ("config.json", "encoder_config/config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors"):
            if not (local_dir / name).is_file():
                raise FileNotFoundError("model_missing")
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
        packages = {re.sub(r"[-_.]+", "-", distribution.metadata["Name"]).lower(): distribution.version
                    for distribution in importlib.metadata.distributions() if distribution.metadata["Name"]}
        runtime_sources_root, runtime_sources, runtime_sources_sha256 = _runtime_sources()
        start = time.perf_counter()
        import torch
        torch.set_num_threads(config["threads"])
        from gliner2 import AutoExtractor
        import gliner2
        if Path(gliner2.__file__).resolve() != Path(runtime_sources_root) / "gliner2/__init__.py":
            raise ValueError("runtime_sources_invalid")
        engine = AutoExtractor.from_pretrained(str(local_dir), map_location="cpu", quantize=False,
                                               compile=False, use_flashdeberta=False, word_splitter="whitespace")
        if engine.architecture != "boundary":
            raise ValueError("architecture_invalid")
        runtime = {name: importlib.metadata.version(name)
                   for name in ("torch", "transformers", "tokenizers", "numpy", "gliner2")}
        runtime["python"] = sys.version.split()[0]
        emit({"status": "ready", "runtime": runtime, "runtime_packages": packages,
              "runtime_sources": runtime_sources, "runtime_sources_sha256": runtime_sources_sha256,
              "runtime_sources_root": runtime_sources_root,
              "load_ms": (time.perf_counter() - start) * 1000, "rss_mb": _rss()})
    except (ImportError, FileNotFoundError, importlib.metadata.PackageNotFoundError):
        emit({"status": "error", "error": "gliner_runtime_missing"})
        os.close(protocol)
        return
    except Exception:
        emit({"status": "error", "error": "gliner_initialization_failed"})
        os.close(protocol)
        return
    try:
        while True:
            request = _read()
            if request is None:
                return
            sequence = request.get("sequence") if isinstance(request, dict) else None
            try:
                if (not isinstance(request, dict) or set(request) != {"op", "sequence", "input"}
                        or request["op"] != "predict" or type(sequence) is not int or sequence < 1):
                    raise ValueError("request_invalid")
                response = _predict(engine, torch, request["input"], config["max_length"])
            except Exception:
                response = {"status": "error", "output": None, "error": "gliner_inference_failed", "raw_output": None}
            emit({"sequence": sequence, **response})
    finally:
        os.close(protocol)


if __name__ == "__main__":
    main()
