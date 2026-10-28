"""Pinned Vela 3 fast DecisionEncoder, with observed lossless CPU forwards.

The native helper owns rendering, tokenization, readout and probabilities.
This module performs no model import, download or initialization at import.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
from pathlib import Path
import resource
import sys
import time
import traceback

from deposium_bench.choice_protocol import ordered_choice_ids, validate_choice_input

MARKERS = ("[Q]", "[O]", "[ABS]", "[SEP_SCHEMA]", "[SEG_user]",
           "[SEG_answer]", "[E]", "[SEG_context]")
# 231 F32 tensors in the pinned safetensors header. The scalar log_tau
# has shape [] and one element; the publisher API's aggregate omits it.
PARAMETERS = 380436226


def _rss():
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / divisor


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode() + b"\n").hexdigest()


def _ids_hash(ids):
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()


class Vela3FastBackend:
    def __init__(self, model, torch, *, runtime=None, load_ms=0.0, max_length=4096):
        self.model, self.torch = model, torch
        self.runtime, self.load_ms, self.max_length = runtime or {}, load_ms, max_length

    def ready(self):
        return {"runtime": self.runtime, "load_ms": self.load_ms, "rss_mb": _rss(),
                "max_length": self.max_length, "dtype": "float32", "device": "cpu",
                "backend": "sdpa", "gpu_allocated_mb": 0.0}

    def _mode_valid(self):
        parameters = list(self.model.parameters())
        return (self.model.device == "cpu" and self.model.max_len == self.max_length
                and self.model.budget == self.max_length
                and self.model.training is False and self.model.encoder.training is False
                and all(module.training is False for module in self.model.modules())
                and self.model.encoder.config.model_type == "ultrabert"
                and self.model.encoder.config._attn_implementation == "sdpa"
                and self.model.mk == {marker: 49152 + i for i, marker in enumerate(MARKERS)}
                and bool(parameters)
                and all(p.device.type == "cpu" and p.dtype == self.torch.float32
                        for p in parameters))

    def _preflight(self, value, question, descriptions):
        model = self.model
        fragments = [value["context"], value["question"], *descriptions]
        special = tuple(marker for marker in model.tok.all_special_tokens if isinstance(marker, str) and marker)
        reserved = any(marker in text for marker in (*MARKERS, *special) for text in fragments)
        tokenized = [model._ids(text) for text in fragments]
        if any(not isinstance(ids, list) or any(type(i) is not int or i < 0 for i in ids)
               for ids in tokenized):
            raise ValueError("vela3_fast_encoding_failed")
        reserved = reserved or any(i >= 49152 for ids in tokenized for i in ids)
        # The native encode method raises at max_len, without returning a count.
        # Lift only its tokenizer preflight limit, restore it in all cases, and
        # refuse the full record before a forward. predict still sees 4096.
        original = model.max_len
        try:
            model.max_len = 2**31 - 1
            record = model.encode(value["context"], question)
        finally:
            model.max_len = original
        if (not isinstance(record, dict) or set(record) != {"ids", "q_pos", "opt_pos", "names", "pool"}
                or record["names"] != descriptions or record["q_pos"] != 1
                or not isinstance(record["ids"], list)
                or any(type(i) is not int or not 0 <= i < 49160 for i in record["ids"])
                or not isinstance(record["opt_pos"], list)
                or len(record["opt_pos"]) != len(descriptions)
                or any(type(p) is not int for p in record["opt_pos"])):
            raise ValueError("vela3_fast_encoding_failed")
        ids, positions = record["ids"], record["opt_pos"]
        pool = record["pool"]
        if (not isinstance(pool, (list, tuple)) or len(pool) != 2
                or any(type(p) is not int for p in pool)):
            raise ValueError("vela3_fast_encoding_failed")
        ps, pe = pool
        if (not ids or len(ids) < 5 or not 2 <= positions[0] < ps < pe == len(ids) - 1
                or positions != sorted(set(positions))
                or any(not 2 <= p < ps - 1 for p in positions)
                or ids[:2] != [model.tok.bos_token_id, model.mk["[Q]"]]
                or ids[-1] != model.tok.eos_token_id
                or ids[ps - 1] != model.mk["[SEP_SCHEMA]"]
                or ids[2:positions[0]] != tokenized[1]
                or any(ids[p] != model.mk["[O]"] for p in positions)
                or any(ids[p + 1:(positions[i + 1] if i + 1 < len(positions) else ps - 1)] != tokenized[i + 2]
                       for i, p in enumerate(positions))):
            raise ValueError("vela3_fast_encoding_failed")
        complete = ids[ps:pe] == [model.mk["[SEG_user]"], *tokenized[0]]
        info = {"tokens": 0, "full_input_tokens": len(ids), "encoded_tokens": 0,
                "truncated": not complete or len(ids) > self.max_length, "forward_count": 0,
                "expected_sha256": _ids_hash(ids), "actual_sha256": None,
                "forward_ids_equal": False, "forward_masks_equal": False,
                "context_tokens": len(tokenized[0]), "label_tokens": len(ids) - len(tokenized[0]),
                "reserved_marker": reserved, "context_complete": complete and len(ids) <= self.max_length}
        if info["truncated"] or reserved:
            return None, info
        info["tokens"] = info["encoded_tokens"] = len(ids)
        return ids, info

    def predict(self, value):
        started = time.perf_counter()
        validate_choice_input(value)
        ids = ordered_choice_ids(value)
        descriptions = [option["description"] for option in value["options"]]
        question = {"type": "choice", "instructions": value["question"],
                    "criteria": {description: None for description in descriptions}}
        raw = {"native_result": None, "probabilities": None, "input_sha256": _hash(value),
               "ordered_ids": ids, "ordered_descriptions": descriptions, "encoding_info": None,
               "forward_executed": False, "decision_ms": None, "inference_ms": None,
               "rss_mb": None, "gpu_allocated_mb": 0.0}

        def finish(status, error=None, output=None):
            raw["decision_ms"] = (time.perf_counter() - started) * 1000
            raw["rss_mb"] = _rss()
            return {"status": status, "output": output, "raw_output": raw, "error": error}

        if not self._mode_valid():
            return finish("error", "vela3_fast_model_mode_changed")
        try:
            expected, info = self._preflight(value, question, descriptions)
            raw["encoding_info"] = info
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return finish("error", "vela3_fast_encoding_failed")
        if expected is None:
            return finish("unsupported", "vela3_fast_context_overflow")

        def audited_forward(_module, args, kwargs):
            info["forward_count"] += 1
            if args or set(kwargs) != {"input_ids", "attention_mask"}:
                raise ValueError("vela3_fast_forward_encoding_mismatch")
            actual = kwargs["input_ids"].detach().cpu().tolist()
            masks = kwargs["attention_mask"].detach().cpu().tolist()
            info["actual_sha256"] = _ids_hash(actual[0]) if len(actual) == 1 else None
            info["forward_ids_equal"] = actual == [expected]
            info["forward_masks_equal"] = masks == [[1] * len(expected)]
            if (info["forward_count"] != 1 or not info["forward_ids_equal"] or not info["forward_masks_equal"]
                    or any(t.device.type != "cpu" or t.dtype != self.torch.long for t in kwargs.values())):
                raise ValueError("vela3_fast_forward_encoding_mismatch")
            raw["forward_executed"] = True

        handle = self.model.encoder.register_forward_pre_hook(audited_forward, with_kwargs=True)
        try:
            inference_started = time.perf_counter()
            with self.torch.inference_mode():
                native = self.model.predict(value["context"], {"decision": question})
            raw["inference_ms"] = (time.perf_counter() - inference_started) * 1000
        except Exception as exc:
            if isinstance(exc, ValueError) and str(exc) == "vela3_fast_forward_encoding_mismatch":
                return finish("error", str(exc))
            traceback.print_exc(file=sys.stderr)
            return finish("error", "vela3_fast_inference_failed")
        finally:
            handle.remove()
        try:
            json.dumps(native, allow_nan=False)
        except (TypeError, ValueError):
            return finish("error", "vela3_fast_distribution_invalid")
        raw["native_result"] = list(native) if isinstance(native, tuple) else native
        if info["forward_count"] != 1:
            return finish("error", "vela3_fast_forward_count_mismatch")
        try:
            if (not isinstance(native, (list, tuple)) or len(native) != 2
                    or type(native[1]) is not int or native[1] != len(expected)
                    or not isinstance(native[0], dict) or set(native[0]) != {"decision"}):
                raise ValueError
            answer = native[0]["decision"]
            if (not isinstance(answer, dict) or set(answer) != {"type", "choice", "probabilities"}
                    or answer["type"] != "choice" or not isinstance(answer["probabilities"], dict)):
                raise ValueError
            probabilities = answer["probabilities"]
            if (list(probabilities) != descriptions
                    or any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
                           for p in probabilities.values())
                    or abs(sum(probabilities.values()) - 1) > 0.002):
                raise ValueError
            raw["probabilities"] = dict(probabilities)
            selected = max(range(len(ids)), key=lambda i: probabilities[descriptions[i]])
            if answer["choice"] != descriptions[selected]:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            return finish("error", "vela3_fast_distribution_invalid")
        return finish("ok", output={"choice_id": ids[selected]})


def initialize(config):
    if (not isinstance(config, dict) or config.get("device") != "cpu" or config.get("dtype") != "float32"
            or config.get("backend") != "sdpa" or config.get("max_length") != 4096
            or type(config.get("max_length")) is not int
            or type(config.get("threads")) is not int or not 1 <= config["threads"] <= 2):
        raise ValueError("vela3_fast_runtime_invalid")
    import torch

    started = time.perf_counter()
    torch.set_num_threads(config["threads"])
    torch.set_num_interop_threads(1)
    source = Path(config["local_dir"]).resolve()
    if Path(config["source_dir"]).resolve() != source:
        raise ValueError("vela3_fast_source_identity_invalid")
    sys.path.insert(0, str(source))
    native = importlib.import_module("vela3_encoder")
    common = importlib.import_module("ub_d3_common")
    if any(Path(module.__file__).resolve() != source / name for module, name in
           ((native, "vela3_encoder.py"), (common, "ub_d3_common.py"))):
        raise ValueError("vela3_fast_source_identity_invalid")
    model = native.DecisionEncoder.load(str(source), device="cpu", max_len=4096, token_budget=4096)
    engine = Vela3FastBackend(model, torch, runtime=config["pins"],
                              load_ms=(time.perf_counter() - started) * 1000)
    cfg = model.encoder.config
    custom_module = sys.modules[model.encoder.__class__.__module__]
    custom_path = Path(custom_module.__file__).resolve()
    if (not engine._mode_valid() or sum(p.numel() for p in model.parameters()) != PARAMETERS
            or cfg.hidden_size != 1024 or cfg.num_hidden_layers != 24 or cfg.num_attention_heads != 8
            or len(model.tok) != 49152
            or custom_path.read_bytes() != (source / "modeling_ultrabert.py").read_bytes()):
        raise ValueError("vela3_fast_model_identity_invalid")
    engine.load_ms = (time.perf_counter() - started) * 1000
    return engine
