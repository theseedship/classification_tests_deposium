"""Model-free adversarial checks of Vela3's native choice/encoder boundary."""
from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from deposium_bench.worker_transport import wire


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("vela3_fast_backend", ROOT / "bridges/vela3-fast-backend.py")
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)
INPUT = {"context": "Texte visible.\nSecond paragraph.", "question": "Quelle action ?",
         "options": [{"id": "opaque-b", "description": "Rechercher"},
                     {"id": "opaque-a", "description": "Compter"}]}
UNSET = object()


class FakeTensor:
    def __init__(self, rows, *, device="cpu", dtype="long"):
        self.rows = rows
        self.device, self.dtype = types.SimpleNamespace(type=device), dtype

    def detach(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return self.rows


class FakeEncoder:
    def __init__(self):
        self.hook, self.calls, self.training = None, 0, False
        self.config = types.SimpleNamespace(model_type="ultrabert", _attn_implementation="sdpa")

    def register_forward_pre_hook(self, hook, with_kwargs):
        if with_kwargs is not True or self.hook is not None:
            raise AssertionError("incorrect hook registration")
        self.hook = hook
        return types.SimpleNamespace(remove=lambda: setattr(self, "hook", None))

    def __call__(self, *args, **kwargs):
        if self.hook is not None:
            self.hook(self, args, kwargs)
        self.calls += 1


class FakeTokenizer:
    bos_token_id = eos_token_id = pad_token_id = 0
    all_special_tokens = ["<|endoftext|>", "<|im_start|>", "<|im_end|>", "<repo_name>",
                          "<reponame>", "<file_sep>", "<filename>", "<gh_stars>", "<issue_start>",
                          "<issue_comment>", "<issue_closed>", "<jupyter_start>", "<jupyter_text>",
                          "<jupyter_code>", "<jupyter_output>", "<|sep|>", "<|mask|>"]

    def __call__(self, text, *, add_special_tokens):
        if add_special_tokens is not False:
            raise AssertionError("native tokenizer policy changed")
        return {"input_ids": [v + 100 for v in text.encode("utf-8")]}

    def __len__(self):
        return 49152


class FakeDecision:
    """Small test double with the documented native encode/predict API.

    No production rendering is reproduced in the backend; this fixture lets
    independent mutations exercise its audit without Torch or model weights.
    """
    def __init__(self, mode="ok", native=UNSET):
        self.mode, self.native = mode, native
        self.device, self.max_len, self.budget = "cpu", 4096, 4096
        self.training, self.encoder, self.tok = False, FakeEncoder(), FakeTokenizer()
        self.mk = {marker: 49152 + i for i, marker in enumerate(backend.MARKERS)}
        self.parameter = types.SimpleNamespace(device=types.SimpleNamespace(type="cpu"), dtype="f32")
        self.last_call, self.encode_limits = None, []

    def parameters(self):
        return iter([self.parameter])

    def modules(self):
        return iter([self, self.encoder])

    def _ids(self, text):
        ids = self.tok(text, add_special_tokens=False)["input_ids"] if text else []
        return ids + [49152] if self.mode == "id_reserved" and text == INPUT["context"] else ids

    def encode(self, state, question, state_ids=None):
        self.encode_limits.append(self.max_len)
        if self.mode == "encode_error":
            raise RuntimeError("synthetic tokenization failure")
        ids = [self.tok.bos_token_id, self.mk["[Q]"]] + self._ids(question["instructions"])
        positions, names = [], []
        for name, description in question["criteria"].items():
            if description is not None:
                raise AssertionError("only visible descriptions belong in the native schema")
            positions.append(len(ids))
            names.append(name)
            ids += [self.mk["[O]"]] + self._ids(name)
        ids.append(self.mk["[SEP_SCHEMA]"])
        ps = len(ids)
        context = list(state_ids) if state_ids is not None else self._ids(state)
        if self.mode == "truncated_context":
            context = context[1:]
        ids += [self.mk["[SEG_user]"]] + context
        pe = len(ids)
        ids.append(self.tok.eos_token_id)
        if len(ids) > self.max_len:
            raise ValueError("native context limit")
        return dict(ids=ids, q_pos=1, opt_pos=positions, names=names, pool=(ps, pe))

    def predict(self, state, questions):
        self.last_call = (state, deepcopy(questions))
        if self.mode == "before_forward_error":
            raise RuntimeError("synthetic native failure")
        record = self.encode(state, questions["decision"], self._ids(state))
        ids = list(record["ids"])
        inputs = {"input_ids": FakeTensor([ids]), "attention_mask": FakeTensor([[1] * len(ids)])}
        if self.mode == "wrong_ids":
            inputs["input_ids"].rows[0][-1] = 999
        if self.mode == "wrong_mask":
            inputs["attention_mask"].rows[0][-1] = 0
        if self.mode == "wrong_device":
            inputs["input_ids"].device.type = "mps"
        if self.mode == "wrong_dtype":
            inputs["attention_mask"].dtype = "f32"
        if self.mode == "extra_kwarg":
            inputs["use_cache"] = False
        if self.mode != "no_forward":
            self.encoder(**inputs)
        if self.mode == "double_forward":
            self.encoder(**inputs)
        if self.mode == "after_forward_error":
            raise RuntimeError("synthetic readout failure")
        if self.native is not UNSET:
            return self.native(record)
        names = record["names"]
        probabilities = dict(zip(names, (.25, .75)))
        return {"decision": {"type": "choice", "choice": names[1], "probabilities": probabilities}}, len(ids)


def make(mode="ok", native=UNSET):
    model = FakeDecision(mode, native)
    torch = types.SimpleNamespace(float32="f32", long="long", inference_mode=nullcontext)
    return backend.Vela3FastBackend(model, torch, runtime={"python": "test"}), model


def native(probabilities, *, choice="Compter", tokens=None):
    return lambda record: ({"decision": {"type": "choice", "choice": choice,
                           "probabilities": probabilities}}, len(record["ids"]) if tokens is None else tokens)


class Vela3FastBackendTests(unittest.TestCase):
    def test_import_does_not_load_model_runtime(self):
        source = ("import importlib.util,sys; "
                  f"p={str(ROOT / 'bridges/vela3-fast-backend.py')!r}; "
                  "s=importlib.util.spec_from_file_location('safe',p); "
                  "s.loader.exec_module(importlib.util.module_from_spec(s)); "
                  "assert not any(n in sys.modules for n in ('torch','numpy','transformers','vela3_encoder'))")
        result = subprocess.run([sys.executable, "-B", "-c", source], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_native_projection_and_observed_forward_preserve_input(self):
        engine, model = make()
        result = engine.predict(INPUT)
        self.assertEqual((result["status"], result["output"]), ("ok", {"choice_id": "opaque-a"}))
        self.assertEqual(model.last_call, (INPUT["context"], {"decision": {
            "type": "choice", "instructions": INPUT["question"],
            "criteria": {"Rechercher": None, "Compter": None}}}))
        self.assertNotIn("opaque-", json.dumps(model.last_call))
        raw, info = result["raw_output"], result["raw_output"]["encoding_info"]
        self.assertEqual(raw["input_sha256"], hashlib.sha256(wire(INPUT)).hexdigest())
        self.assertEqual(raw["ordered_ids"], ["opaque-b", "opaque-a"])
        self.assertEqual(raw["ordered_descriptions"], ["Rechercher", "Compter"])
        self.assertEqual(raw["native_result"], [{"decision": {"type": "choice", "choice": "Compter",
                         "probabilities": {"Rechercher": .25, "Compter": .75}}}, info["full_input_tokens"]])
        self.assertEqual(raw["probabilities"], raw["native_result"][0]["decision"]["probabilities"])
        self.assertEqual(info["tokens"], info["encoded_tokens"])
        self.assertEqual(info["tokens"], info["full_input_tokens"])
        self.assertEqual(info["expected_sha256"], info["actual_sha256"])
        self.assertEqual(info["forward_count"], 1)
        self.assertEqual(info["context_tokens"], len(INPUT["context"].encode("utf-8")))
        self.assertEqual(info["context_tokens"] + info["label_tokens"], info["full_input_tokens"])
        self.assertTrue(all(info[k] for k in ("forward_ids_equal", "forward_masks_equal", "context_complete")))
        self.assertFalse(info["truncated"])
        self.assertTrue(raw["forward_executed"])
        self.assertEqual(model.encoder.calls, 1)
        self.assertEqual(model.encode_limits, [2**31 - 1, 4096])
        self.assertIsNone(model.encoder.hook)
        self.assertGreaterEqual(raw["decision_ms"], raw["inference_ms"])
        self.assertEqual(raw["gpu_allocated_mb"], 0.0)

    def test_order_and_ties_follow_original_options_without_id_semantics(self):
        value = deepcopy(INPUT)
        value["options"].reverse()
        engine, model = make(native=native({"Compter": .5, "Rechercher": .5}, choice="Compter"))
        result = engine.predict(value)
        self.assertEqual(result["output"], {"choice_id": "opaque-a"})
        self.assertEqual(list(model.last_call[1]["decision"]["criteria"]), ["Compter", "Rechercher"])

    def test_empty_context_remains_valid_and_is_not_replaced(self):
        value = {**INPUT, "context": ""}
        engine, model = make()
        result = engine.predict(value)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(model.last_call[0], "")
        self.assertEqual(result["raw_output"]["encoding_info"]["context_tokens"], 0)

    def test_overflow_and_silent_context_truncation_refuse_before_forward(self):
        for mode, value in (("ok", {**INPUT, "context": "x" * 4096}), ("truncated_context", INPUT)):
            with self.subTest(mode=mode):
                engine, model = make(mode)
                result = engine.predict(value)
                raw, info = result["raw_output"], result["raw_output"]["encoding_info"]
                self.assertEqual((result["status"], result["error"]), ("unsupported", "vela3_fast_context_overflow"))
                self.assertTrue(info["truncated"])
                self.assertFalse(info["context_complete"])
                self.assertEqual((info["tokens"], info["encoded_tokens"], info["forward_count"]), (0, 0, 0))
                self.assertFalse(raw["forward_executed"])
                self.assertIsNone(raw["inference_ms"])
                self.assertEqual(model.encoder.calls, 0)
                self.assertEqual(model.max_len, 4096)

    def test_native_length_limit_is_restored_even_on_encode_error(self):
        engine, model = make("encode_error")
        with patch.object(backend.traceback, "print_exc"):
            result = engine.predict(INPUT)
        self.assertEqual((result["status"], result["error"]), ("error", "vela3_fast_encoding_failed"))
        self.assertEqual(model.max_len, 4096)
        self.assertEqual(model.encoder.calls, 0)
        self.assertIsNone(result["raw_output"]["encoding_info"])

    def test_all_reserved_markers_refuse_before_forward_in_all_fragments(self):
        for marker in (*backend.MARKERS, *FakeTokenizer.all_special_tokens):
            for field in ("context", "question", "description"):
                with self.subTest(marker=marker, field=field):
                    value = deepcopy(INPUT)
                    if field == "description":
                        value["options"][0][field] += marker
                    else:
                        value[field] += marker
                    engine, model = make()
                    result = engine.predict(value)
                    self.assertEqual(result["status"], "unsupported")
                    self.assertTrue(result["raw_output"]["encoding_info"]["reserved_marker"])
                    self.assertEqual(model.encoder.calls, 0)
        engine, model = make("id_reserved")
        result = engine.predict(INPUT)
        self.assertEqual(result["status"], "unsupported")
        self.assertTrue(result["raw_output"]["encoding_info"]["reserved_marker"])
        self.assertEqual(model.encoder.calls, 0)

    def test_wrong_actual_encoder_input_is_rejected_before_encoder_execution(self):
        for mode in ("wrong_ids", "wrong_mask", "wrong_device", "wrong_dtype", "extra_kwarg"):
            with self.subTest(mode=mode):
                engine, model = make(mode)
                result = engine.predict(INPUT)
                self.assertEqual((result["status"], result["error"]), ("error", "vela3_fast_forward_encoding_mismatch"))
                self.assertEqual(model.encoder.calls, 0)
                self.assertFalse(result["raw_output"]["forward_executed"])
                self.assertIsNone(model.encoder.hook)

    def test_missing_and_extra_forwards_are_errors_and_hook_is_removed(self):
        for mode, error, calls in (("no_forward", "vela3_fast_forward_count_mismatch", 0),
                                    ("double_forward", "vela3_fast_forward_encoding_mismatch", 1)):
            with self.subTest(mode=mode):
                engine, model = make(mode)
                result = engine.predict(INPUT)
                self.assertEqual((result["status"], result["error"]), ("error", error))
                self.assertEqual(model.encoder.calls, calls)
                self.assertEqual(result["raw_output"]["forward_executed"], calls == 1)
                self.assertIsNone(model.encoder.hook)

    def test_native_failures_preserve_forward_observation_and_remove_hook(self):
        for mode, calls in (("before_forward_error", 0), ("after_forward_error", 1)):
            with self.subTest(mode=mode):
                engine, model = make(mode)
                with patch.object(backend.traceback, "print_exc"):
                    result = engine.predict(INPUT)
                self.assertEqual((result["status"], result["error"]), ("error", "vela3_fast_inference_failed"))
                self.assertEqual(model.encoder.calls, calls)
                self.assertEqual(result["raw_output"]["forward_executed"], calls == 1)
                self.assertIsNone(model.encoder.hook)

    def test_invalid_native_distributions_and_token_counts_are_not_repaired(self):
        bad = [lambda _r: (), lambda _r: [], lambda _r: ({}, 1),
               native({}), native({"Rechercher": .25}),
               native({"Compter": .75, "Rechercher": .25}),
               native({"Rechercher": .9, "Compter": .9}),
               native({"Rechercher": float("nan"), "Compter": .75}),
               native({"Rechercher": True, "Compter": 0.0}),
               native({"Rechercher": -.1, "Compter": 1.1}),
               native({"Rechercher": .25, "Compter": .75}, choice="Rechercher"),
               native({"Rechercher": .25, "Compter": .75}, tokens=1),
               native({"Rechercher": .25, "Compter": .75}, tokens=True)]
        for idx, response in enumerate(bad):
            with self.subTest(index=idx):
                engine, model = make(native=response)
                result = engine.predict(INPUT)
                self.assertEqual((result["status"], result["error"]), ("error", "vela3_fast_distribution_invalid"))
                self.assertIsNone(result["output"])
                self.assertEqual(model.encoder.calls, 1)
                json.dumps(result, allow_nan=False)

    def test_cpu_f32_sdpa_eval_mode_and_native_markers_are_enforced(self):
        mutations = [lambda m: setattr(m, "device", "mps"), lambda m: setattr(m, "training", True),
                     lambda m: setattr(m.encoder, "training", True), lambda m: setattr(m, "max_len", 8192),
                     lambda m: setattr(m, "budget", 8192), lambda m: setattr(m.parameter, "dtype", "bf16"),
                     lambda m: setattr(m.parameter.device, "type", "cuda"),
                     lambda m: setattr(m.encoder.config, "_attn_implementation", "eager"),
                     lambda m: setattr(m.encoder.config, "model_type", "other"),
                     lambda m: m.mk.update({"[Q]": 1}), lambda m: setattr(m, "parameters", lambda: iter([]))]
        for idx, mutate in enumerate(mutations):
            with self.subTest(index=idx):
                engine, model = make()
                mutate(model)
                result = engine.predict(INPUT)
                self.assertEqual((result["status"], result["error"]), ("error", "vela3_fast_model_mode_changed"))
                self.assertFalse(result["raw_output"]["forward_executed"])
                self.assertEqual(model.encoder.calls, 0)

    def test_invalid_runtime_rejected_before_importing_torch(self):
        config = {"source_dir": "not-loaded", "local_dir": "not-loaded", "max_length": 4096,
                  "threads": 2, "pins": {}, "device": "cpu", "dtype": "float32", "backend": "sdpa"}
        for change in ({"device": "mps"}, {"device": "cuda"}, {"dtype": "bfloat16"},
                       {"backend": "eager"}, {"threads": True}, {"threads": 0}, {"threads": 3},
                       {"max_length": 4096.0}, {"max_length": 8192}):
            with self.subTest(change=change), patch.dict(sys.modules, {"torch": None}), self.assertRaisesRegex(
                    ValueError, "vela3_fast_runtime_invalid"):
                backend.initialize({**config, **change})
        with self.assertRaisesRegex(ValueError, "vela3_fast_runtime_invalid"):
            backend.initialize(None)

    def test_ready_reports_cpu_and_distinct_zero_gpu_resource(self):
        engine, _model = make()
        ready = engine.ready()
        self.assertEqual(set(ready), {"runtime", "load_ms", "rss_mb", "max_length", "dtype", "device", "backend", "gpu_allocated_mb"})
        self.assertEqual((ready["device"], ready["dtype"], ready["backend"], ready["max_length"]), ("cpu", "float32", "sdpa", 4096))
        self.assertGreater(ready["rss_mb"], 0)
        self.assertEqual(ready["gpu_allocated_mb"], 0.0)

    def test_loader_calls_only_official_decision_encoder_with_explicit_cpu_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp).resolve()
            model = FakeDecision()
            model.encoder = type("PinnedEncoder", (FakeEncoder,), {"__module__": "test_pinned_ultrabert"})()
            for key, value in {"hidden_size": 1024, "num_hidden_layers": 24, "num_attention_heads": 8}.items():
                setattr(model.encoder.config, key, value)
            # Verified pinned state-header count, including scalar log_tau.
            model.parameter.numel = lambda: 380436226
            (source / "modeling_ultrabert.py").write_bytes(b"pinned custom encoder code")
            cached = source / "dynamic-cache-ultrabert.py"
            cached.write_bytes((source / "modeling_ultrabert.py").read_bytes())
            loader = Mock(return_value=model)
            full_loader = Mock(side_effect=AssertionError("full adapter suite must not be loaded"))
            torch = types.SimpleNamespace(float32="f32", long="long", inference_mode=nullcontext,
                                          set_num_threads=Mock(), set_num_interop_threads=Mock())
            modules = {"torch": torch,
                       "vela3_encoder": types.SimpleNamespace(__file__=str(source / "vela3_encoder.py"),
                           DecisionEncoder=types.SimpleNamespace(load=loader), Vela3Encoder=full_loader),
                       "ub_d3_common": types.SimpleNamespace(__file__=str(source / "ub_d3_common.py")),
                       "test_pinned_ultrabert": types.SimpleNamespace(__file__=str(cached))}
            config = {"source_dir": str(source), "local_dir": str(source), "max_length": 4096,
                      "threads": 2, "pins": {"python": "test"}, "device": "cpu",
                      "dtype": "float32", "backend": "sdpa"}
            with patch.dict(sys.modules, modules), patch.object(sys, "path", list(sys.path)):
                engine = backend.initialize(config)
            self.assertIs(engine.model, model)
            loader.assert_called_once_with(str(source), device="cpu", max_len=4096, token_budget=4096)
            full_loader.assert_not_called()
            torch.set_num_threads.assert_called_once_with(2)
            torch.set_num_interop_threads.assert_called_once_with(1)
            self.assertEqual(engine.ready()["runtime"], config["pins"])
            # The HF aggregate excludes the shape-[] scalar. It must not pass
            # the runtime's exact loaded-parameter identity check.
            model.parameter.numel = lambda: 380436225
            with patch.dict(sys.modules, modules), patch.object(sys, "path", list(sys.path)), self.assertRaisesRegex(
                    ValueError, "vela3_fast_model_identity_invalid"):
                backend.initialize(config)
            model.parameter.numel = lambda: 380436226
            # A Transformers dynamic cache is admissible only with identical
            # pinned source bytes, regardless of its filesystem location.
            cached.write_bytes(b"changed remote encoder code")
            with patch.dict(sys.modules, modules), patch.object(sys, "path", list(sys.path)), self.assertRaisesRegex(
                    ValueError, "vela3_fast_model_identity_invalid"):
                backend.initialize(config)

    def test_loader_rejects_preimported_helpers_from_another_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp).resolve()
            torch = types.SimpleNamespace(set_num_threads=Mock(), set_num_interop_threads=Mock())
            loader = Mock(side_effect=AssertionError("wrong helper must not load weights"))
            config = {"source_dir": str(source), "local_dir": str(source), "max_length": 4096,
                      "threads": 2, "pins": {}, "device": "cpu", "dtype": "float32", "backend": "sdpa"}
            with patch.dict(sys.modules, {
                    "torch": torch,
                    "vela3_encoder": types.SimpleNamespace(__file__=str(source / "other/vela3_encoder.py"),
                        DecisionEncoder=types.SimpleNamespace(load=loader)),
                    "ub_d3_common": types.SimpleNamespace(__file__=str(source / "ub_d3_common.py"))}), patch.object(
                        sys, "path", list(sys.path)), self.assertRaisesRegex(ValueError, "vela3_fast_source_identity_invalid"):
                backend.initialize(config)
            loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
