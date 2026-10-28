"""Lossless CPU bridge to the pinned ModernJEV native `predict.py` helper.

The helper's `decide` truncates `only_first`. We preflight every complete pair
with its tokenizer and its own JSON state serializer before calling it.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import resource
import sys
import time

from deposium_bench.choice_protocol import ordered_choice_ids, validate_choice_input


MAX_LENGTH = 4096
REVISION = "d5b398ed03de073a00bc4e53acf53afda409445e"
SOURCE_SHA256 = "d77ea48b1fadc19b8e77404d6066031d571d01d7c2b6120526499b069bea2fd5"
TEMPLATE = {
    "schema_version": "deposium.modernjev-choice-projection/v1",
    "repo_id": "MaziyarPanahi/ModernJEV-Decide-Preview",
    "revision": REVISION,
    "state": {"conversation": [{"role": "user", "content": "context"}],
              "available_tools": []},
    "question": "question",
    "criteria": "ordered_descriptions_as_native_list",
    "opaque_ids_visible": False,
    "candidate_batch_size": 1,
    "max_length": MAX_LENGTH,
}


class ModernJevBackendError(ValueError):
    pass


def _rss() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _input_hash(value: dict) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False) + "\n"
    return _sha256(data.encode("utf-8"))


def _ids_hash(ids: list[int]) -> str:
    return _sha256(json.dumps(ids, separators=(",", ":")).encode("ascii"))


def _versions(pins: dict) -> dict:
    if (not isinstance(pins, dict) or
            not {"python", "torch", "transformers", "tokenizers"} <= set(pins) or
            any(not isinstance(k, str) or not k or not isinstance(v, str) or not v
                for k, v in pins.items())):
        raise ModernJevBackendError("modernjev_runtime_pins_invalid")
    try:
        actual = {name: importlib.metadata.version(name)
                  for name in pins if name != "python"}
    except importlib.metadata.PackageNotFoundError as exc:
        raise ModernJevBackendError("modernjev_runtime_missing") from exc
    actual["python"] = sys.version.split()[0]
    if any(actual[name] != version for name, version in pins.items()):
        raise ModernJevBackendError("modernjev_runtime_lock_mismatch")
    return actual


def _assets(root: Path, names: tuple[str, ...]) -> None:
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ModernJevBackendError("modernjev_assets_missing")
    for name in names:
        item = root / name
        if item.is_symlink() or not item.is_file():
            raise ModernJevBackendError("modernjev_assets_missing")


class ModernJevBackend:
    def __init__(self, engine, helper, *, versions: dict | None = None,
                 load_ms: float = 0.0, template_sha256: str = ""):
        self.engine = engine
        self.helper = helper
        self.versions = versions or {}
        self.load_ms = load_ms
        self.template_sha256 = template_sha256

    def ready(self) -> dict:
        return {"runtime": self.versions, "load_ms": self.load_ms, "rss_mb": _rss(),
                "max_length": MAX_LENGTH, "dtype": "float32", "device": "cpu",
                "backend": "modernjev_native", "template_sha256": self.template_sha256}

    def _preflight(self, state: dict, question: str, descriptions: list[str]) -> dict:
        # Use the pinned helper's serializer and list-to-label projection. Only
        # the two literal pair separators need repeating here: it exposes no
        # public pair-building function outside `decide`, which already truncates.
        criteria = self.helper.normalize_criteria(descriptions)
        if list(criteria) != descriptions or any(criteria[key] != key for key in descriptions):
            raise ModernJevBackendError("modernjev_criteria_changed")
        text_a = question + "\n\nSTATE:\n" + self.helper.serialize_state(state)
        text_bs = [f"{key}: {criteria[key]}" for key in descriptions]
        tokenizer = self.engine.tokenizer
        raw_a = tokenizer(text_a, add_special_tokens=False, truncation=False,
                          padding=False, verbose=False)["input_ids"]
        special = tokenizer.num_special_tokens_to_add(pair=True)
        raw_lengths = [len(raw_a) + len(tokenizer(text_b, add_special_tokens=False,
                                                   truncation=False, padding=False,
                                                   verbose=False)["input_ids"]) + special
                       for text_b in text_bs]
        rows = [tokenizer(text_a, text_b, add_special_tokens=True,
                          truncation=False, padding=False, verbose=False)["input_ids"]
                for text_b in text_bs]
        if (any(not isinstance(row, list) or any(type(token) is not int or token < 0
                                                for token in row) for row in rows) or
                any(type(length) is not int for length in raw_lengths)):
            raise ModernJevBackendError("modernjev_encoding_invalid")
        lengths = [len(row) for row in rows]
        info = {"tokens_per_pair": lengths, "native_raw_pair_tokens": raw_lengths,
                "max_sequence_tokens": max(lengths),
                "sum_sequence_tokens": sum(lengths),
                "padded_batch_tokens": sum(lengths),  # native batch size 1
                "max_length": MAX_LENGTH,
                "pair_input_ids_sha256": [_ids_hash(row) for row in rows],
                "truncated": False, "candidate_batch_size": 1,
                "forward_count": 0, "forward_ids_equal": False,
                "forward_masks_equal": False, "actual_input_ids_sha256": []}
        return info, rows

    def _decide(self, state: dict, question: str, descriptions: list[str]) -> dict:
        return self.engine.decide(state=state, question=question, criteria=descriptions,
                                  candidate_batch_size=1)

    def predict(self, value: dict) -> dict:
        started = time.perf_counter()
        raw = {"native_result": None, "input_sha256": None, "ordered_ids": None,
               "ordered_descriptions": None, "encoding_info": None,
               "forward_executed": False, "decision_ms": None,
               "inference_ms": None, "rss_mb": None}

        def finish(status: str, error: str | None = None, output: dict | None = None) -> dict:
            raw["decision_ms"] = (time.perf_counter() - started) * 1000
            raw["rss_mb"] = _rss()
            return {"status": status, "output": output, "raw_output": raw, "error": error}

        try:
            validate_choice_input(value)
            raw["input_sha256"] = _input_hash(value)
            ids = ordered_choice_ids(value)
        except (TypeError, ValueError):
            return finish("error", "modernjev_input_invalid")
        descriptions = [option["description"] for option in value["options"]]
        raw["ordered_ids"] = ids
        raw["ordered_descriptions"] = descriptions
        state = {"conversation": [{"role": "user", "content": value["context"]}],
                 "available_tools": []}
        try:
            info, rows = self._preflight(state, value["question"], descriptions)
        except Exception:
            return finish("error", "modernjev_encoding_failed")
        raw["encoding_info"] = info
        if any(length == 0 for length in info["tokens_per_pair"]):
            return finish("unsupported", "modernjev_empty_encoding")
        if any(length > MAX_LENGTH for length in info["tokens_per_pair"]):
            return finish("unsupported", "modernjev_context_overflow")
        if info["tokens_per_pair"] != info["native_raw_pair_tokens"]:
            return finish("unsupported", "modernjev_pair_encoding_mismatch")

        # The pinned helper calls its model once per criterion when batch_size=1.
        # Compare the tensors at that boundary before any native model forward.
        model = self.engine.model
        native_forward = model.forward
        had_local_forward = "forward" in vars(model)
        prior_local_forward = vars(model).get("forward")

        def audited_forward(*args, **kwargs):
            raw["forward_executed"] = True
            index = info["forward_count"]
            info["forward_count"] += 1
            if index >= len(rows) or args or set(kwargs) != {"input_ids", "attention_mask"}:
                raise ModernJevBackendError("modernjev_forward_encoding_mismatch")
            try:
                actual_ids = kwargs["input_ids"].detach().cpu().tolist()
                actual_masks = kwargs["attention_mask"].detach().cpu().tolist()
            except (AttributeError, TypeError, ValueError) as exc:
                raise ModernJevBackendError("modernjev_forward_encoding_mismatch") from exc
            ids_equal = actual_ids == [rows[index]]
            masks_equal = actual_masks == [[1] * len(rows[index])]
            if (isinstance(actual_ids, list) and len(actual_ids) == 1 and
                    isinstance(actual_ids[0], list)):
                info["actual_input_ids_sha256"].append(_ids_hash(actual_ids[0]))
            info["forward_ids_equal"] = ids_equal if index == 0 else info["forward_ids_equal"] and ids_equal
            info["forward_masks_equal"] = masks_equal if index == 0 else info["forward_masks_equal"] and masks_equal
            if not ids_equal or not masks_equal:
                raise ModernJevBackendError("modernjev_forward_encoding_mismatch")
            return native_forward(*args, **kwargs)

        inference_started = time.perf_counter()
        hook_installed = False
        try:
            model.forward = audited_forward
            hook_installed = True
            native = self._decide(state, value["question"], descriptions)
            raw["inference_ms"] = (time.perf_counter() - inference_started) * 1000
        except ModernJevBackendError as exc:
            raw["inference_ms"] = (time.perf_counter() - inference_started) * 1000
            return finish("error", str(exc))
        except Exception:
            raw["inference_ms"] = (time.perf_counter() - inference_started) * 1000
            return finish("error", "modernjev_inference_failed")
        finally:
            if hook_installed:
                if had_local_forward:
                    model.forward = prior_local_forward
                else:
                    del model.forward
        if (info["forward_count"] != len(rows) or not info["forward_ids_equal"] or
                not info["forward_masks_equal"] or
                info["actual_input_ids_sha256"] != info["pair_input_ids_sha256"]):
            return finish("error", "modernjev_forward_count_mismatch")
        try:
            if (not isinstance(native, dict) or
                    set(native) != {"predicted_label", "allowed_choices", "candidates",
                                    "truncated", "max_sequence_length", "note"} or
                    native["allowed_choices"] != descriptions or
                    native["truncated"] is not False or native["max_sequence_length"] != MAX_LENGTH or
                    native["predicted_label"] not in descriptions or
                    not isinstance(native["candidates"], list) or
                    len(native["candidates"]) != len(descriptions)):
                raise ModernJevBackendError("modernjev_distribution_invalid")
            candidates = native["candidates"]
            if (any(not isinstance(item, dict) or
                    set(item) != {"label", "score", "raw_score", "rank"} or
                    item["label"] not in descriptions or
                    type(item["rank"]) is not int or item["rank"] < 1 or
                    type(item["score"]) not in (int, float) or
                    not math.isfinite(item["score"]) or not 0 <= item["score"] <= 1 or
                    type(item["raw_score"]) not in (int, float) or
                    not math.isfinite(item["raw_score"])
                    for item in candidates) or
                    {item["label"] for item in candidates} != set(descriptions) or
                    [item["rank"] for item in candidates] != list(range(1, len(ids)+1)) or
                    candidates[0]["label"] != native["predicted_label"] or
                    abs(sum(item["score"] for item in candidates) - 1) > 0.002):
                raise ModernJevBackendError("modernjev_distribution_invalid")
            selected_index = descriptions.index(native["predicted_label"])
        except (KeyError, TypeError, ValueError, ModernJevBackendError):
            return finish("error", "modernjev_distribution_invalid")
        raw["native_result"] = native
        return finish("ok", output={"choice_id": ids[selected_index]})


def initialize(config: dict) -> ModernJevBackend:
    if (not isinstance(config, dict) or
            set(config) != {"mode", "source_dir", "local_dir", "max_length", "threads", "pins", "template_path"} or
            config["mode"] != "modernjev" or type(config["max_length"]) is not int or
            config["max_length"] != MAX_LENGTH or type(config["threads"]) is not int or
            config["threads"] != 2 or any(not isinstance(config[key], str)
                                           for key in ("source_dir", "local_dir", "template_path"))):
        raise ModernJevBackendError("modernjev_initialization_invalid")
    source = Path(config["source_dir"])
    local = Path(config["local_dir"])
    template_path = Path(config["template_path"])
    _assets(source, ("predict.py",))
    _assets(local, ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json"))
    if _sha256((source / "predict.py").read_bytes()) != SOURCE_SHA256:
        raise ModernJevBackendError("modernjev_source_identity_invalid")
    if not template_path.is_absolute() or template_path.is_symlink() or not template_path.is_file():
        raise ModernJevBackendError("modernjev_template_missing")
    template_bytes = template_path.read_bytes()
    try:
        if json.loads(template_bytes) != TEMPLATE:
            raise ModernJevBackendError("modernjev_template_mismatch")
        release = json.loads((local / "config.json").read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ModernJevBackendError("modernjev_assets_invalid") from exc
    if (not isinstance(release, dict) or release.get("architectures") !=
            ["ModernBertForSequenceClassification"] or release.get("model_type") != "modernbert" or
            release.get("num_attention_heads") != 12 or release.get("num_hidden_layers") != 22 or
            release.get("vocab_size") != 50368 or release.get("max_position_embeddings") != 8192 or
            release.get("dtype") != "float32"):
        raise ModernJevBackendError("modernjev_model_identity_invalid")
    versions = _versions(config["pins"])
    started = time.perf_counter()
    import torch

    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    spec = importlib.util.spec_from_file_location("modernjev_native_predict", source / "predict.py")
    if spec is None or spec.loader is None:
        raise ModernJevBackendError("modernjev_source_invalid")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    if (helper.MAX_LEN != MAX_LENGTH or helper.MODEL_ID != "OpenMed/ModernJEV-Decide-Preview"):
        raise ModernJevBackendError("modernjev_source_identity_invalid")
    engine = helper.DecisionModel(model_path=str(local), device="cpu")
    if (engine.device != "cpu" or engine.model.config.num_labels != 1 or
            engine.model.config.model_type != "modernbert" or
            any(parameter.device.type != "cpu" or parameter.dtype != torch.float32
                for parameter in engine.model.parameters())):
        raise ModernJevBackendError("modernjev_model_mode_changed")
    return ModernJevBackend(engine, helper, versions=versions,
                            load_ms=(time.perf_counter() - started) * 1000,
                            template_sha256=_sha256(template_bytes))
