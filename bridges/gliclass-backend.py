"""Pinned GLiClass decoder-kv API with lossless inputs and observed MPS forward.

The native pipeline owns rendering, tokenization, calibration and prediction.
Only its exact inputs and outputs are audited here. No heavy import at import time.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time
import traceback

from deposium_bench.choice_protocol import ordered_choice_ids, validate_choice_input


def _rss():
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / divisor


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode() + b"\n").hexdigest()


def _ids_hash(ids):
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()


class GLiClassBackend:
    def __init__(self, model, pipeline, torch, *, runtime=None, load_ms=0.0, max_length=4096):
        self.model, self.pipeline, self.torch = model, pipeline, torch
        self.runtime, self.load_ms, self.max_length = runtime or {}, load_ms, max_length

    def _gpu_allocated(self):
        return self.torch.mps.current_allocated_memory() / (1024 * 1024)

    def ready(self):
        return {"runtime": self.runtime, "load_ms": self.load_ms, "rss_mb": _rss(),
                "max_length": self.max_length, "dtype": "bfloat16", "device": "mps",
                "backend": "eager", "gpu_allocated_mb": self._gpu_allocated()}

    def _mode_valid(self):
        return (self.model.training is False and self.pipeline.pipe.model is self.model
                and self.pipeline.pipe.device.type == "mps"
                and self.pipeline.pipe.max_length == self.max_length
                and self.pipeline.pipe.classification_type == "single-label"
                and self.model.config.architecture_type == "decoder-kv"
                and all(p.device.type == "mps" and p.dtype == self.torch.bfloat16
                        for p in self.model.parameters()))

    def _preflight(self, value, descriptions):
        pipe = self.pipeline.pipe
        tok = pipe.tokenizer
        # These are the pinned native builders called by prepare_inputs itself.
        contexts, label_sequences = pipe._build_context_and_labels(
            [value["context"]], descriptions, True, None, value["question"])
        if len(contexts) != 1 or len(label_sequences) != 1:
            raise ValueError("gliclass_encoding_failed")
        context_ids = tok(contexts[0], add_special_tokens=False, truncation=False)["input_ids"]
        label_ids = tok(label_sequences[0], add_special_tokens=False, truncation=False)["input_ids"]
        full = context_ids + label_ids
        marker_strings = (pipe.label_token, pipe.sep_token, pipe.example_token)
        reserved = any(marker in text for marker in marker_strings
                       for text in [value["context"], value["question"], *descriptions])
        info = {"tokens": 0, "full_input_tokens": len(full), "encoded_tokens": 0,
                "truncated": False, "forward_count": 0,
                "expected_sha256": _ids_hash(full), "actual_sha256": None,
                "forward_ids_equal": False, "forward_masks_equal": False,
                "context_tokens": len(context_ids), "label_tokens": len(label_ids),
                "reserved_marker": reserved, "context_complete": True}
        # Do not allocate an oversized MPS tensor merely to prove native truncation.
        if len(full) > self.max_length or reserved:
            info["truncated"] = len(full) > self.max_length
            info["context_complete"] = len(full) <= self.max_length
            return None, info
        encoded = pipe.prepare_inputs([value["context"]], descriptions, True,
                                      examples=None, prompt=value["question"])
        actual_ids = encoded["input_ids"].detach().cpu().tolist()
        masks = encoded["attention_mask"].detach().cpu().tolist()
        info["encoded_tokens"] = len(actual_ids[0]) if len(actual_ids) == 1 else 0
        info["tokens"] = info["encoded_tokens"]
        info["context_complete"] = actual_ids == [full]
        info["truncated"] = actual_ids != [full]
        if actual_ids != [full] or masks != [[1] * len(full)] or set(encoded) != {"input_ids", "attention_mask"}:
            return None, info
        return full, info

    def predict(self, value):
        started = time.perf_counter()
        validate_choice_input(value)
        ids = ordered_choice_ids(value)
        descriptions = [option["description"] for option in value["options"]]
        raw = {"native_result": None, "probabilities": None, "input_sha256": _hash(value),
               "ordered_ids": ids, "ordered_descriptions": descriptions, "encoding_info": None,
               "forward_executed": False, "decision_ms": None, "inference_ms": None,
               "rss_mb": None, "gpu_allocated_mb": None}

        def finish(status, error=None, output=None):
            raw["decision_ms"] = (time.perf_counter() - started) * 1000
            raw["rss_mb"] = _rss()
            raw["gpu_allocated_mb"] = self._gpu_allocated()
            return {"status": status, "output": output, "raw_output": raw, "error": error}

        if not self._mode_valid():
            return finish("error", "gliclass_model_mode_changed")
        try:
            expected, info = self._preflight(value, descriptions)
            raw["encoding_info"] = info
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return finish("error", "gliclass_encoding_failed")
        if expected is None:
            return finish("unsupported", "gliclass_context_overflow")

        def audited_forward(_module, args, kwargs):
            info["forward_count"] += 1
            actual_ids = kwargs["input_ids"].detach().cpu().tolist()
            masks = kwargs["attention_mask"].detach().cpu().tolist()
            info["actual_sha256"] = _ids_hash(actual_ids[0]) if len(actual_ids) == 1 else None
            info["forward_ids_equal"] = actual_ids == [expected]
            info["forward_masks_equal"] = masks == [[1] * len(expected)]
            if (args or info["forward_count"] != 1 or not info["forward_ids_equal"]
                    or not info["forward_masks_equal"]
                    or kwargs["input_ids"].device.type != "mps"
                    or kwargs["attention_mask"].device.type != "mps"
                    or kwargs.get("use_cache") is not False):
                raise ValueError("gliclass_forward_encoding_mismatch")
            raw["forward_executed"] = True

        handle = self.model.model.decoder_model.register_forward_pre_hook(audited_forward, with_kwargs=True)
        try:
            self.torch.mps.synchronize()
            inference_started = time.perf_counter()
            with self.torch.inference_mode():
                native = self.pipeline(value["context"], descriptions, batch_size=1,
                                       classification_type="single-label", prompt=value["question"],
                                       return_hierarchical=True)
            self.torch.mps.synchronize()
            raw["inference_ms"] = (time.perf_counter() - inference_started) * 1000
        except ValueError as exc:
            if str(exc) == "gliclass_forward_encoding_mismatch":
                return finish("error", str(exc))
            traceback.print_exc(file=sys.stderr)
            return finish("error", "gliclass_inference_failed")
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return finish("error", "gliclass_inference_failed")
        finally:
            handle.remove()
        try:
            # A malformed native result must not corrupt the bounded JSON stream.
            json.dumps(native, allow_nan=False)
        except (TypeError, ValueError):
            return finish("error", "gliclass_distribution_invalid")
        raw["native_result"] = native
        if info["forward_count"] != 1:
            return finish("error", "gliclass_forward_count_mismatch")
        try:
            if not isinstance(native, list) or len(native) != 1 or not isinstance(native[0], dict):
                raise ValueError
            probabilities = native[0]
            if (list(probabilities) != descriptions
                    or any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
                           for p in probabilities.values())
                    or abs(sum(probabilities.values()) - 1.0) > 0.002):
                raise ValueError
            raw["probabilities"] = dict(probabilities)
            selected = max(range(len(ids)), key=lambda i: probabilities[descriptions[i]])
        except (KeyError, TypeError, ValueError):
            return finish("error", "gliclass_distribution_invalid")
        return finish("ok", output={"choice_id": ids[selected]})


def initialize(config):
    import torch
    from transformers import AutoTokenizer

    started = time.perf_counter()
    if not torch.backends.mps.is_available():
        raise ValueError("gliclass_mps_unavailable")
    torch.set_num_threads(config["threads"])
    torch.set_num_interop_threads(1)
    source = Path(config["source_dir"]).resolve()
    sys.path.insert(0, str(source))
    import gliclass
    from gliclass import GLiClassModel, ZeroShotClassificationPipeline
    from gliclass.config import GLiClassModelConfig

    if not Path(gliclass.__file__).resolve().is_relative_to(source):
        raise ValueError("gliclass_source_identity_invalid")
    model_config = GLiClassModelConfig.from_pretrained(config["local_dir"], local_files_only=True)
    if model_config.architecture_type != "decoder-kv":
        raise ValueError("gliclass_architecture_invalid")
    # GLiClass wraps a multimodal Qwen config: pin each attention implementation,
    # including the language sub-config used to instantiate the real text encoder.
    configs = [model_config, model_config.encoder_config]
    for name in ("text_config", "vision_config"):
        nested = getattr(model_config.encoder_config, name, None)
        if nested is not None:
            configs.append(nested)
    for item in configs:
        item._attn_implementation = config["backend"]
    tok = AutoTokenizer.from_pretrained(config["local_dir"], local_files_only=True, trust_remote_code=False)
    model = GLiClassModel.from_pretrained(config["local_dir"], config=model_config,
                                         local_files_only=True, dtype=torch.bfloat16,
                                         attn_implementation=config["backend"])
    device = torch.device(config["device"])
    model.to(device=device, dtype=torch.bfloat16)
    model.eval()
    pipeline = ZeroShotClassificationPipeline(model, tok, max_length=config["max_length"],
                                               classification_type="single-label", device=device,
                                               progress_bar=False)
    # A string 'mps' would silently select CPU in the pinned native pipeline.
    engine = GLiClassBackend(model, pipeline, torch, runtime=config["pins"],
                             load_ms=(time.perf_counter() - started) * 1000,
                             max_length=config["max_length"])
    actual_encoder = model.model.decoder_model.config
    actual_text = actual_encoder.get_text_config()
    if (not engine._mode_valid() or actual_text._attn_implementation != "eager"
            or model.config.class_token_index != tok.convert_tokens_to_ids("<<LABEL>>")
            or model.config.sep_token_index != tok.convert_tokens_to_ids("<<SEP>>")):
        raise ValueError("gliclass_model_identity_invalid")
    torch.mps.synchronize()
    engine.load_ms = (time.perf_counter() - started) * 1000
    return engine
