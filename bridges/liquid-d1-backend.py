"""Pinned LiquidAI/d1-3B text choice backend; imports model code only at initialization."""
from __future__ import annotations

import hashlib
from importlib import import_module
import json
import math
from pathlib import Path
import resource
import time

from deposium_bench.choice_protocol import ordered_choice_ids, validate_choice_input


def _rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _hash(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode() + b"\n"
    return hashlib.sha256(data).hexdigest()


def _ids_hash(ids):
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()


def _reserved(value, tokenizer):
    """The native prompt has no escaping for chat control tokens in user text."""
    special = tuple(token for token in getattr(tokenizer, "all_special_tokens", ()) if token)
    return any("<|" in text or any(token in text for token in special) for text in
               (value["context"], value["question"],
                *(option["description"] for option in value["options"])))


class LiquidD1Backend:
    def __init__(self, model, max_length=4096, runtime=None, load_ms=0.0):
        self.model, self.max_length = model, max_length
        self.runtime, self.load_ms = runtime or {}, load_ms

    def ready(self):
        return {"runtime": self.runtime, "load_ms": self.load_ms, "rss_mb": _rss(),
                "max_length": self.max_length, "dtype": "float32", "device": "cpu",
                "backend": "system_one"}

    def predict(self, value):
        started = time.perf_counter()
        validate_choice_input(value)
        ids = ordered_choice_ids(value)
        descriptions = [item["description"] for item in value["options"]]
        names = [f"option_{i:03d}" for i in range(len(ids))]
        question = {"type": "choice", "instructions": value["question"],
                    "criteria": dict(zip(names, descriptions))}
        raw = {"native_result": None, "input_sha256": _hash(value), "ordered_ids": ids,
               "ordered_descriptions": descriptions, "encoding_info": None,
               "forward_executed": False, "decision_ms": None, "inference_ms": None,
               "rss_mb": None}

        def finish(status, error=None, output=None):
            raw["decision_ms"] = (time.perf_counter() - started) * 1000
            raw["rss_mb"] = _rss()
            return {"status": status, "output": output, "raw_output": raw, "error": error}

        try:
            engine = self.model.engine
            # The engine's own prompt module supplies the typed question through its API.
            prompt = import_module(type(engine).__module__.rsplit(".", 1)[0] + ".prompt")
            native_question = prompt.as_question(question)
            rendered = engine.render(value["context"], native_question)
            expected_ids = engine.tokenizer.encode(rendered, add_special_tokens=False)
            info = {"full_input_tokens": len(expected_ids),
                    "expected_sha256": _ids_hash(expected_ids), "native_sha256": None,
                    "full_input_equal": False, "forward_count": 0,
                    "model_forward_count": 0, "model_forward_ids_equal": False,
                    "model_forward_sha256": None,
                    "altered_segment": None}
            raw["encoding_info"] = info
        except Exception:
            return finish("error", "small_model_encoding_failed")
        if _reserved(value, engine.tokenizer):
            info["altered_segment"] = "reserved_delimiter"
            return finish("unsupported", "small_model_context_overflow")
        if not expected_ids or len(expected_ids) > self.max_length:
            info["altered_segment"] = "context_limit"
            return finish("unsupported", "small_model_context_overflow")

        original = engine._logz_ids
        original_forward = engine._one_pass
        observed = {"count": 0}
        model_calls = {"count": 0}

        def audited_model_forward(*args, **kwargs):
            model_calls["count"] += 1
            tensor = kwargs.get("input_ids")
            rows = tensor.tolist() if hasattr(tensor, "tolist") else tensor
            actual = rows[0] if isinstance(rows, list) and len(rows) == 1 else None
            info["model_forward_count"] = model_calls["count"]
            info["model_forward_ids_equal"] = actual == expected_ids
            info["model_forward_sha256"] = _ids_hash(actual) if actual is not None else None
            if (model_calls["count"] != 1 or args or set(kwargs) != {"input_ids", "logits_to_keep"}
                    or kwargs["logits_to_keep"] != 1 or actual != expected_ids
                    or (hasattr(tensor, "device") and tensor.device.type != "cpu")):
                raise ValueError("small_model_forward_encoding_mismatch")
            result = original_forward(*args, **kwargs)
            raw["forward_executed"] = True
            return result

        def audited(rows):
            observed["count"] += 1
            actual = rows[0] if len(rows) == 1 else None
            info["forward_count"] = observed["count"]
            info["native_sha256"] = _ids_hash(actual) if actual is not None else None
            info["full_input_equal"] = actual == expected_ids
            if observed["count"] != 1 or actual != expected_ids:
                raise ValueError("small_model_forward_encoding_mismatch")
            return original(rows)

        engine._logz_ids = audited
        engine._one_pass = audited_model_forward
        inference_started = time.perf_counter()
        try:
            native = self.model.system_one(value["context"], {"answer": question})
            raw["inference_ms"] = (time.perf_counter() - inference_started) * 1000
        except ValueError as exc:
            if str(exc) == "small_model_forward_encoding_mismatch":
                return finish("error", str(exc))
            return finish("error", "small_model_inference_failed")
        except Exception:
            return finish("error", "small_model_inference_failed")
        finally:
            engine._logz_ids = original
            engine._one_pass = original_forward
        if observed["count"] != 1 or model_calls["count"] != 1:
            return finish("error", "small_model_forward_count_mismatch")
        try:
            answer = native["answers"]["answer"]
            probabilities = answer["probabilities"]
            usage = native["usage"]
            if (answer["type"] != "choice" or list(probabilities) != names
                    or answer["choice"] not in names
                    or any(type(p) not in (int, float) or not math.isfinite(p) or p < 0 or p > 1
                           for p in probabilities.values())
                    or abs(sum(probabilities.values()) - 1) > 0.002
                    or probabilities[answer["choice"]] + 0.0001 < max(probabilities.values())
                    or usage != {"input_tokens": len(expected_ids), "output_tokens": 0}):
                raise ValueError
            selected = ids[names.index(answer["choice"])]
        except (KeyError, TypeError, ValueError):
            return finish("error", "small_model_distribution_invalid")
        raw["native_result"] = native
        return finish("ok", output={"choice_id": selected})


def initialize(config):
    if config.get("mode") != "liquid3" or config.get("max_length") != 4096:
        raise ValueError("small_model_initialization_invalid")
    import torch
    from transformers import AutoModel

    torch.set_num_threads(config["threads"])
    torch.set_num_interop_threads(1)
    started = time.perf_counter()
    model = AutoModel.from_pretrained(config["local_dir"], trust_remote_code=True,
                                      local_files_only=True, dtype=torch.float32).to("cpu")
    model.tie_weights()
    model.eval()
    root = Path(config["local_dir"]).resolve()
    if (type(model).__name__ != "D1Model" or model.config.model_type != "lfm2_vl"
            or model.config.text_config.max_position_embeddings != 32768
            or not Path(model.name_or_path).resolve().is_relative_to(root)
            or model.lm_head.weight is not model.model.language_model.embed_tokens.weight
            or sum(param.numel() for param in model.parameters()) != 3123483888
            or any(param.device.type != "cpu" or param.dtype != torch.float32
                   for param in model.parameters())):
        raise ValueError("small_model_identity_invalid")
    engine = model.engine
    if (engine.device.type != "cpu" or engine.model is not model
            or not Path(engine.tokenizer.name_or_path).resolve().is_relative_to(root)
            or engine.system != "none" or engine.state_style != "json_only"
            or engine.option_style != "desc" or engine.lead != "" or engine.calibration is not None):
        raise ValueError("small_model_identity_invalid")
    return LiquidD1Backend(model, runtime=config["pins"],
                           load_ms=(time.perf_counter() - started) * 1000)
