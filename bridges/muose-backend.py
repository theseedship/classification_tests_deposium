"""Native, resident Muose50M criterion scorer for context choices.

The upstream checkpoint has no published prompt template. The separate profile
freezes this experiment's STATE / INSTRUCTIONS / CRITERION representation.
Loading weights and importing model dependencies happen only in initialize().
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import resource
import sys
import time

from deposium_bench.choice_protocol import ordered_choice_ids, validate_choice_input


MAX_LENGTH = 512
REVISION = "5afb8eeff127621fea2d66fc63f56798ada12eda"
TEMPLATE = {
    "schema_version": "deposium.muose-choice-template/v1",
    "repo_id": "muose/Muose-50M-Decision",
    "revision": REVISION,
    "format": "STATE:\n{context}\n\nINSTRUCTIONS:\n{question}\n\nCRITERION:\n{description}",
    "criterion_mode": "one_independent_sequence_per_option",
    "order": "as_supplied",
    "id_visibility": "opaque_ids_excluded",
    "max_length": MAX_LENGTH,
}


class MuoseBackendError(ValueError):
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
            not {"python", "torch", "safetensors", "tokenizers"} <= set(pins) or
            any(not isinstance(k, str) or not k or not isinstance(v, str) or not v
                for k, v in pins.items())):
        raise MuoseBackendError("muose_runtime_pins_invalid")
    try:
        actual = {name: importlib.metadata.version(name)
                  for name in pins if name != "python"}
    except importlib.metadata.PackageNotFoundError as exc:
        raise MuoseBackendError("muose_runtime_missing") from exc
    actual["python"] = sys.version.split()[0]
    if any(actual[name] != version for name, version in pins.items()):
        raise MuoseBackendError("muose_runtime_lock_mismatch")
    return actual


def _assets(root: Path, names: tuple[str, ...]) -> None:
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise MuoseBackendError("muose_assets_missing")
    for name in names:
        item = root / name
        if item.is_symlink() or not item.is_file():
            raise MuoseBackendError("muose_assets_missing")


def _pad_rows(rows: list[list[int]], lengths: list[int]) -> list[list[int]]:
    """Right padding is safe for Muose's causal attention and last-real-token pool."""
    if (not rows or len(rows) != len(lengths) or
            any(type(n) is not int or n < 1 or n > MAX_LENGTH or len(row) != n
                for row, n in zip(rows, lengths))):
        raise MuoseBackendError("muose_encoding_invalid")
    width = max(lengths)
    return [row + [0] * (width - length) for row, length in zip(rows, lengths)]


class MuoseBackend:
    def __init__(self, model, tokenizer, *, versions: dict | None = None,
                 load_ms: float = 0.0, template_sha256: str = ""):
        self.model = model
        self.tokenizer = tokenizer
        self.versions = versions or {}
        self.load_ms = load_ms
        self.template_sha256 = template_sha256

    def ready(self) -> dict:
        return {"runtime": self.versions, "load_ms": self.load_ms, "rss_mb": _rss(),
                "max_length": MAX_LENGTH, "dtype": "float32", "device": "cpu",
                "backend": "muose_native", "template_sha256": self.template_sha256}

    def _score_sequences(self, rows: list[list[int]], lengths: list[int]) -> list[float]:
        import torch

        padded = _pad_rows(rows, lengths)
        inputs = torch.tensor(padded, dtype=torch.long, device="cpu")
        actual_lengths = torch.tensor(lengths, dtype=torch.long, device="cpu")
        with torch.inference_mode():
            scores = self.model(inputs, actual_lengths)
        return scores.detach().cpu().tolist()

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
            return finish("error", "muose_input_invalid")
        descriptions = [option["description"] for option in value["options"]]
        raw["ordered_ids"] = ids
        raw["ordered_descriptions"] = descriptions

        # Each option has its own complete context and question. No answer IDs,
        # annotations, reference choices, or other options enter a model row.
        try:
            prompts = [TEMPLATE["format"].format(context=value["context"],
                       question=value["question"], description=description)
                       for description in descriptions]
            rows = [self.tokenizer.encode(prompt, add_special_tokens=False).ids
                    for prompt in prompts]
            if any(not isinstance(row, list) or any(type(token) is not int or token < 0
                                                    for token in row) for row in rows):
                return finish("error", "muose_encoding_invalid")
        except Exception:
            return finish("error", "muose_encoding_failed")
        lengths = [len(row) for row in rows]
        width = max(lengths)
        raw["encoding_info"] = {
            "tokens_per_option": lengths,
            "max_sequence_tokens": width,
            "sum_sequence_tokens": sum(lengths),
            "padded_batch_tokens": width * len(rows),
            "max_length": MAX_LENGTH,
            "prompt_sha256": [_sha256(prompt.encode("utf-8")) for prompt in prompts],
            "input_ids_sha256": [_ids_hash(row) for row in rows],
            "truncated": False,
        }
        if any(length == 0 for length in lengths):
            return finish("unsupported", "muose_empty_encoding")
        if any(length > MAX_LENGTH for length in lengths):
            return finish("unsupported", "muose_context_overflow")

        model = self.model
        native_forward = model.forward
        had_local_forward = "forward" in vars(model)
        prior_local_forward = vars(model).get("forward")
        forward_count = 0

        def observed_forward(*args, **kwargs):
            nonlocal forward_count
            forward_count += 1
            raw["forward_executed"] = True
            if forward_count != 1:
                raise MuoseBackendError("muose_forward_count_mismatch")
            return native_forward(*args, **kwargs)

        inference_started = time.perf_counter()
        hook_installed = False
        try:
            model.forward = observed_forward
            hook_installed = True
            scores = self._score_sequences(rows, lengths)
            raw["inference_ms"] = (time.perf_counter() - inference_started) * 1000
        except MuoseBackendError as exc:
            raw["inference_ms"] = (time.perf_counter() - inference_started) * 1000
            return finish("error", str(exc))
        except Exception:
            raw["inference_ms"] = (time.perf_counter() - inference_started) * 1000
            return finish("error", "muose_inference_failed")
        finally:
            if hook_installed:
                if had_local_forward:
                    model.forward = prior_local_forward
                else:
                    del model.forward
        if forward_count != 1:
            return finish("error", "muose_forward_count_mismatch")
        if (not isinstance(scores, list) or len(scores) != len(ids) or
                any(type(score) not in (int, float) or not math.isfinite(score)
                    for score in scores)):
            return finish("error", "muose_distribution_invalid")
        # Softmax is explicitly cross-option; checkpoint outputs are scalar scores.
        peak = max(scores)
        weights = [math.exp(score - peak) for score in scores]
        normalizer = sum(weights)
        if not math.isfinite(normalizer) or normalizer <= 0:
            return finish("error", "muose_distribution_invalid")
        probabilities = [weight / normalizer for weight in weights]
        selected_index = max(range(len(scores)), key=lambda index: scores[index])
        raw["native_result"] = {"scores": [float(score) for score in scores],
                                "probabilities": probabilities,
                                "selected_index": selected_index}
        return finish("ok", output={"choice_id": ids[selected_index]})


def initialize(config: dict) -> MuoseBackend:
    if (not isinstance(config, dict) or
            not {"source_dir", "local_dir", "max_length", "threads", "pins", "template_path"} <= set(config) or
            type(config["max_length"]) is not int or config["max_length"] != MAX_LENGTH or
            type(config["threads"]) is not int or
            config["threads"] != 2 or any(not isinstance(config[key], str)
                                           for key in ("source_dir", "local_dir", "template_path"))):
        raise MuoseBackendError("muose_initialization_invalid")
    source = Path(config["source_dir"])
    local = Path(config["local_dir"])
    template_path = Path(config["template_path"])
    _assets(source, ("model.py", "decision_model.py"))
    _assets(local, ("config.json", "model.safetensors", "vocab.json", "merges.txt"))
    if not template_path.is_absolute() or template_path.is_symlink() or not template_path.is_file():
        raise MuoseBackendError("muose_template_missing")
    template_bytes = template_path.read_bytes()
    try:
        if json.loads(template_bytes) != TEMPLATE:
            raise MuoseBackendError("muose_template_mismatch")
        release = json.loads((local / "config.json").read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MuoseBackendError("muose_assets_invalid") from exc
    if (not isinstance(release, dict) or release.get("model_type") != "muose_decision" or
            release.get("architecture") != "MuoseDecision" or
            not isinstance(release.get("base_config"), dict) or
            release["base_config"].get("context_length") != MAX_LENGTH or
            release["base_config"].get("vocab_size") != 24000):
        raise MuoseBackendError("muose_model_identity_invalid")
    versions = _versions(config["pins"])
    started = time.perf_counter()
    import torch
    from safetensors.torch import load_model
    from tokenizers import ByteLevelBPETokenizer

    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    # This is the pinned upstream source, loaded in a dedicated worker process.
    sys.path.insert(0, str(source))
    from model import Muose, MuoseConfig
    from decision_model import MuoseDecision

    if (Path(sys.modules["model"].__file__).resolve() != (source / "model.py").resolve()
            or Path(sys.modules["decision_model"].__file__).resolve()
            != (source / "decision_model.py").resolve()):
        raise MuoseBackendError("muose_source_identity_invalid")

    model = MuoseDecision(Muose(MuoseConfig(**release["base_config"])))
    load_model(model, str(local / "model.safetensors"))
    model.eval()
    model.to(device="cpu", dtype=torch.float32)
    if any(parameter.device.type != "cpu" or parameter.dtype != torch.float32
           for parameter in model.parameters()):
        raise MuoseBackendError("muose_model_mode_changed")
    tokenizer = ByteLevelBPETokenizer(str(local / "vocab.json"), str(local / "merges.txt"))
    if (tokenizer.get_vocab_size() != release["base_config"]["vocab_size"] or
            tokenizer._tokenizer.truncation is not None or
            tokenizer._tokenizer.padding is not None):
        raise MuoseBackendError("muose_tokenizer_invalid")
    return MuoseBackend(model, tokenizer, versions=versions,
                        load_ms=(time.perf_counter() - started) * 1000,
                        template_sha256=_sha256(template_bytes))
