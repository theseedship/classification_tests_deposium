"""Pinned d1 Omni text choice backend. Nothing heavyweight is imported at module import."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import resource
import sys
import time

from deposium_bench.choice_protocol import ordered_choice_ids, validate_choice_input


def _rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode() + b"\n").hexdigest()


def _ids_hash(ids):
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()


def _load_prompt(source_dir):
    path = Path(source_dir) / "prompt.py"
    spec = importlib.util.spec_from_file_location("pinned_liquid_omni_prompt", path)
    if spec is None or spec.loader is None:
        raise ValueError("small_model_native_prompt_missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class OmniBackend:
    def __init__(self, model, prompt, max_length=16384, runtime=None, load_ms=0.0):
        self.model, self.prompt, self.max_length = model, prompt, max_length
        self.runtime, self.load_ms = runtime or {}, load_ms

    def ready(self):
        return {"runtime": self.runtime, "load_ms": self.load_ms, "rss_mb": _rss(),
                "max_length": self.max_length, "dtype": "float32", "device": "cpu",
                "backend": "system_one"}

    def _preflight(self, value, question):
        """Use the pinned native renderer/tokenizer, then compare with its actual encode.

        Native encode has independent instruction, per-option, state and final slices.
        Counting only the returned sequence would silently certify a shortened row.
        """
        prompt, tok = self.prompt, self.model.tokenizer
        state = prompt.serialize(value["context"])
        texts = [state, value["question"], *[o["description"] for o in value["options"]]]
        native_options = prompt.render_options(question)
        enc = lambda s: tok(prompt.escape(s), add_special_tokens=False)["input_ids"]
        state_ids = enc(state)
        instruction_ids = enc(question.instructions)
        option_ids = [enc(" " + text) for text in native_options]
        ids_of = tok.convert_tokens_to_ids
        delim = prompt.DELIM
        full = [tok.bos_token_id, ids_of(delim["state"]), *state_ids,
                ids_of(delim["q"]), *instruction_ids]
        markers = []
        for option in option_ids:
            markers.append(len(full) + 1)
            full += [ids_of(delim["opt"]), ids_of(prompt.MARKER), *option,
                     ids_of(delim["opt_end"])]
        full.append(ids_of(delim["decide"]))
        info = {"state_tokens": len(state_ids), "instruction_tokens": len(instruction_ids),
                "option_tokens": [len(part) for part in option_ids],
                "full_input_tokens": len(full), "encoded_tokens": None,
                "expected_sha256": _ids_hash(full), "native_sha256": None,
                "markers_equal": False, "full_input_equal": False,
                "altered_segment": None}
        if any(prompt.escape(text) != text for text in texts):
            info["altered_segment"] = "reserved_delimiter"
            return None, info
        try:
            encoded, native_markers = prompt.encode(tok, value["context"], question, self.max_length)
        except ValueError:
            info["altered_segment"] = "native_context_limit"
            return None, info
        info.update(encoded_tokens=len(encoded), native_sha256=_ids_hash(encoded),
                    markers_equal=markers == native_markers, full_input_equal=full == encoded)
        if full != encoded or markers != native_markers:
            budget = max(96, min(len(native_options) * 24 + 32, self.max_length // 2))
            per = max(2, (budget - 3 * len(native_options)) // len(native_options))
            if any(len(part) > per for part in option_ids):
                info["altered_segment"] = "option"
            elif 1 + len(instruction_ids) > max(16, budget):
                info["altered_segment"] = "instruction"
            elif len(full) > self.max_length:
                info["altered_segment"] = "state_or_total"
            else:
                info["altered_segment"] = "native_encoding"
            return None, info
        return (full, markers), info

    def predict(self, value):
        started = time.perf_counter()
        validate_choice_input(value)
        ids = ordered_choice_ids(value)
        descriptions = [item["description"] for item in value["options"]]
        names = [f"option_{i:03d}" for i in range(len(ids))]
        question_dict = {"type": "choice", "instructions": value["question"],
                         "criteria": dict(zip(names, descriptions))}
        raw = {"native_result": None, "input_sha256": _hash(value),
               "ordered_ids": ids, "ordered_descriptions": descriptions,
               "encoding_info": None, "forward_executed": False,
               "decision_ms": None, "inference_ms": None, "rss_mb": None}

        def finish(status, error=None, output=None):
            raw["decision_ms"] = (time.perf_counter() - started) * 1000
            raw["rss_mb"] = _rss()
            return {"status": status, "output": output, "raw_output": raw, "error": error}

        try:
            question = self.prompt.as_question(question_dict)
            expected, info = self._preflight(value, question)
            raw["encoding_info"] = info
        except Exception:
            return finish("error", "small_model_encoding_failed")
        if expected is None:
            return finish("unsupported", "small_model_context_overflow")
        expected_ids, expected_markers = expected
        observed = {"count": 0}
        original_forward = self.model._forward

        def audited_forward(rows):
            observed["count"] += 1
            actual = rows[0] if len(rows) == 1 else None
            valid = (observed["count"] == 1 and actual is not None
                     and actual[0] is None and actual[1] == expected_ids
                     and actual[2] == expected_markers and actual[3].type == "choice"
                     and actual[4] is True)
            info["forward_count"] = observed["count"]
            info["forward_ids_equal"] = actual is not None and actual[1] == expected_ids
            info["forward_markers_equal"] = actual is not None and actual[2] == expected_markers
            info["actual_sha256"] = _ids_hash(actual[1]) if actual is not None else None
            if not valid:
                raise ValueError("small_model_forward_encoding_mismatch")
            raw["forward_executed"] = True
            return original_forward(rows)

        self.model._forward = audited_forward
        inference_started = time.perf_counter()
        try:
            native = self.model.system_one(value["context"], {"answer": question_dict})
            raw["inference_ms"] = (time.perf_counter() - inference_started) * 1000
        except ValueError as exc:
            if str(exc) == "small_model_forward_encoding_mismatch":
                return finish("error", str(exc))
            return finish("error", "small_model_inference_failed")
        except Exception:
            return finish("error", "small_model_inference_failed")
        finally:
            self.model._forward = original_forward
        if observed["count"] != 1:
            return finish("error", "small_model_forward_count_mismatch")
        try:
            answer = native["answers"]["answer"]
            probabilities = answer["probabilities"]
            usage = native["usage"]
            if (answer["type"] != "choice" or list(probabilities) != names
                    or answer["choice"] not in names or
                    any(type(p) not in (int, float) or not math.isfinite(p) or p < 0 or p > 1
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
    if config.get("mode") != "omni" or config.get("max_length") != 16384:
        raise ValueError("small_model_initialization_invalid")
    import torch
    from transformers import AutoModel
    torch.set_num_threads(config["threads"])
    torch.set_num_interop_threads(1)
    started = time.perf_counter()
    prompt = _load_prompt(config["source_dir"])
    model = AutoModel.from_pretrained(config["local_dir"], trust_remote_code=True,
                                      local_files_only=True, dtype=torch.float32).to("cpu")
    model.eval()
    if (model.config.max_length != 16384 or model.device.type != "cpu"
            or model.encoder.embed_tokens.weight.dtype != torch.float32
            or not Path(model.name_or_path).resolve().is_relative_to(Path(config["local_dir"]).resolve())):
        raise ValueError("small_model_identity_invalid")
    return OmniBackend(model, prompt, runtime=config["pins"],
                       load_ms=(time.perf_counter()-started)*1000)
