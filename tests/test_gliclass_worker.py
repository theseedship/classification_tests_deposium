"""Model-free checks of the GLiClass native projection and actual encoder gate."""
from __future__ import annotations

from contextlib import nullcontext
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "bridges" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


worker = load("gliclass-worker")
backend = load("gliclass-backend")
INPUT = {"context": "Visible text.", "question": "Which action?",
         "options": [{"id": "opaque-b", "description": "Search"},
                     {"id": "opaque-a", "description": "Count"}]}


class FakeTensor:
    def __init__(self, rows, device="mps"):
        self.rows, self.device = rows, types.SimpleNamespace(type=device)

    def detach(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return self.rows


class FakeTokenizer:
    def __call__(self, text, **kwargs):
        ids = list(text.encode("utf-8"))
        if kwargs.get("truncation"):
            ids = ids[:kwargs["max_length"]]
        return {"input_ids": ids}


class FakeDecoder:
    def __init__(self):
        self.hook = None
        self.calls = 0

    def register_forward_pre_hook(self, callback, with_kwargs):
        if with_kwargs is not True or self.hook is not None:
            raise AssertionError("incorrect hook registration")
        self.hook = callback
        return types.SimpleNamespace(remove=lambda: setattr(self, "hook", None))

    def __call__(self, **kwargs):
        if self.hook is not None:
            self.hook(self, (), kwargs)
        self.calls += 1


class FakePipeline:
    def __init__(self, *, mode="ok", native=None):
        self.mode, self.native = mode, native
        self.decoder = FakeDecoder()
        self.model = types.SimpleNamespace(training=False,
            config=types.SimpleNamespace(architecture_type="decoder-kv"),
            parameters=lambda: iter([types.SimpleNamespace(device=types.SimpleNamespace(type="mps"),
                                                          dtype="bf16")]),
            model=types.SimpleNamespace(decoder_model=self.decoder))
        self.pipe = self
        self.device = types.SimpleNamespace(type="mps")
        self.tokenizer = FakeTokenizer()
        self.max_length, self.classification_type = 4096, "single-label"
        self.label_token, self.sep_token, self.example_token = "<<LABEL>>", "<<SEP>>", "<<EXAMPLE>>"
        self.last_call = None

    def _build_context_and_labels(self, texts, labels, same_labels, examples, prompt):
        assert texts == [INPUT["context"]] or isinstance(texts[0], str)
        assert same_labels is True and examples is None
        return [prompt + texts[0]], ["<<SEP>>" + "".join(s + "<<LABEL>>" for s in labels) + "<<SEP>>"]

    def prepare_inputs(self, texts, labels, same_labels, examples, prompt):
        contexts, sequences = self._build_context_and_labels(texts, labels, same_labels, examples, prompt)
        full = self.tokenizer(contexts[0], truncation=False)["input_ids"]
        full += self.tokenizer(sequences[0], truncation=False)["input_ids"]
        if self.mode == "truncated":
            full = full[1:]
        return {"input_ids": FakeTensor([full]), "attention_mask": FakeTensor([[1] * len(full)])}

    def __call__(self, text, labels, **kwargs):
        self.last_call = (text, labels, kwargs)
        inputs = self.prepare_inputs([text], labels, True, None, kwargs["prompt"])
        if self.mode == "wrong_ids":
            inputs["input_ids"].rows[0][-1] = 999
        if self.mode == "wrong_mask":
            inputs["attention_mask"].rows[0][-1] = 0
        if self.mode == "wrong_device":
            inputs["input_ids"].device.type = "cpu"
        if self.mode != "no_forward":
            self.decoder(**inputs, use_cache=self.mode == "cached")
        if self.mode == "double_forward":
            self.decoder(**inputs, use_cache=False)
        return self.native if self.native is not None else [{"Search": 0.25, "Count": 0.75}]


def make(mode="ok", native=None):
    pipe = FakePipeline(mode=mode, native=native)
    torch = types.SimpleNamespace(bfloat16="bf16", inference_mode=nullcontext,
                                  mps=types.SimpleNamespace(synchronize=lambda: None,
                                      current_allocated_memory=lambda: 2 * 1024 * 1024))
    return backend.GLiClassBackend(pipe.model, pipe, torch), pipe


class GLiClassWorkerTests(unittest.TestCase):
    def test_import_is_safe_without_heavy_runtime(self):
        source = ("import importlib.util,sys; "
                  f"paths={str([str(ROOT / 'bridges/gliclass-worker.py'), str(ROOT / 'bridges/gliclass-backend.py')])}; "
                  "[(lambda s: s.loader.exec_module(importlib.util.module_from_spec(s)))"
                  "(importlib.util.spec_from_file_location('safe'+str(i),p)) for i,p in enumerate(paths)]; "
                  "assert not any(n in sys.modules for n in ('torch','transformers','gliclass'))")
        result = subprocess.run([sys.executable, "-c", source], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_native_projection_preserves_order_and_hides_choice_ids(self):
        engine, pipe = make()
        result = engine.predict(INPUT)
        self.assertEqual((result["status"], result["output"]), ("ok", {"choice_id": "opaque-a"}))
        text, labels, kwargs = pipe.last_call
        self.assertEqual(text, INPUT["context"])
        self.assertEqual(labels, ["Search", "Count"])
        self.assertEqual(kwargs, {"batch_size": 1, "classification_type": "single-label",
                                  "prompt": INPUT["question"], "return_hierarchical": True})
        self.assertEqual(result["raw_output"]["native_result"], [{"Search": 0.25, "Count": 0.75}])
        info = result["raw_output"]["encoding_info"]
        self.assertEqual(info["tokens"], info["full_input_tokens"])
        self.assertEqual(info["expected_sha256"], info["actual_sha256"])
        self.assertEqual(info["forward_count"], 1)
        self.assertTrue(info["forward_ids_equal"] and info["forward_masks_equal"])
        self.assertTrue(result["raw_output"]["forward_executed"])
        self.assertEqual(pipe.decoder.calls, 1)
        self.assertIsNone(pipe.decoder.hook)

    def test_context_overflow_or_reserved_markers_never_forward(self):
        for value in ({**INPUT, "context": "x" * 5000},
                      {**INPUT, "question": "Which <<SEP>> action?"},
                      {**INPUT, "context": "A <<LABEL>> marker"},
                      {**INPUT, "context": "An <<EXAMPLE>> marker"}):
            with self.subTest(value=value["context"][:30]):
                engine, pipe = make()
                result = engine.predict(value)
                self.assertEqual((result["status"], result["error"]),
                                 ("unsupported", "gliclass_context_overflow"))
                self.assertEqual(pipe.decoder.calls, 0)
                self.assertFalse(result["raw_output"]["forward_executed"])
                self.assertEqual(result["raw_output"]["encoding_info"]["forward_count"], 0)

    def test_native_silent_truncation_is_rejected_before_forward(self):
        engine, pipe = make("truncated")
        result = engine.predict(INPUT)
        self.assertEqual(result["status"], "unsupported")
        self.assertTrue(result["raw_output"]["encoding_info"]["truncated"])
        self.assertEqual(pipe.decoder.calls, 0)

    def test_wrong_actual_encoder_inputs_are_rejected_before_encoder(self):
        for mode in ("wrong_ids", "wrong_mask", "wrong_device", "cached"):
            with self.subTest(mode=mode):
                engine, pipe = make(mode)
                result = engine.predict(INPUT)
                self.assertEqual((result["status"], result["error"]),
                                 ("error", "gliclass_forward_encoding_mismatch"))
                self.assertEqual(pipe.decoder.calls, 0)
                self.assertFalse(result["raw_output"]["forward_executed"])
                self.assertIsNone(pipe.decoder.hook)

    def test_missing_or_extra_forward_is_not_a_valid_prediction(self):
        for mode, error, calls in (("no_forward", "gliclass_forward_count_mismatch", 0),
                                    ("double_forward", "gliclass_forward_encoding_mismatch", 1)):
            with self.subTest(mode=mode):
                engine, pipe = make(mode)
                result = engine.predict(INPUT)
                self.assertEqual((result["status"], result["error"]), ("error", error))
                self.assertEqual(pipe.decoder.calls, calls)

    def test_gpu_failure_removes_native_forward_hook(self):
        engine, pipe = make()
        def failed_sync():
            raise RuntimeError("synthetic GPU error")
        engine.torch.mps.synchronize = failed_sync
        with patch.object(backend.traceback, "print_exc"):
            result = engine.predict(INPUT)
        self.assertEqual((result["status"], result["error"]), ("error", "gliclass_inference_failed"))
        self.assertIsNone(pipe.decoder.hook)
        self.assertEqual(pipe.decoder.calls, 0)

    def test_invalid_distributions_are_errors_without_repair(self):
        for native in ([], [{}], [{"Search": .2}], [{"Count": .75, "Search": .25}],
                       [{"Search": .9, "Count": .9}], [{"Search": float("nan"), "Count": .8}],
                       [{"Search": True, "Count": 0.0}], [{"Search": -0.1, "Count": 1.1}]):
            with self.subTest(native=native):
                engine, _pipe = make(native=native)
                result = engine.predict(INPUT)
                self.assertEqual((result["status"], result["error"]),
                                 ("error", "gliclass_distribution_invalid"))
                self.assertIsNone(result["output"])
                json.dumps(result, allow_nan=False)

    def test_ties_choose_first_original_option(self):
        engine, _pipe = make(native=[{"Search": .5, "Count": .5}])
        self.assertEqual(engine.predict(INPUT)["output"], {"choice_id": "opaque-b"})

    def test_cpu_or_changed_model_mode_is_rejected(self):
        engine, pipe = make()
        pipe.device.type = "cpu"
        result = engine.predict(INPUT)
        self.assertEqual((result["status"], result["error"]), ("error", "gliclass_model_mode_changed"))
        self.assertEqual(pipe.decoder.calls, 0)

    def test_bounded_json_protocol_rejects_duplicate_nonfinite_and_oversized(self):
        for payload in (b'{"op":"predict","op":"predict"}\n', b'{"sequence":NaN}\n',
                        b"{}", b"x" * (worker.MAX_LINE + 1) + b"\n"):
            with self.subTest(length=len(payload)), patch.object(
                    worker.sys, "stdin", io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8")):
                with self.assertRaises(ValueError):
                    worker._read()

    def test_initialization_forbids_cpu_fallback_and_wrong_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {"source_dir": tmp, "local_dir": tmp, "max_length": 4096, "threads": 2,
                      "pins": {"python": sys.version.split()[0]}, "device": "mps",
                      "dtype": "bfloat16", "backend": "eager"}
            with patch.dict(worker.os.environ, {"PYTORCH_ENABLE_MPS_FALLBACK": "0"}):
                self.assertEqual(worker._config(config), config)
                for change in ({"backend": "sdpa"}, {"device": "cpu"}, {"threads": True},
                               {"max_length": 8192}, {"dtype": "float32"}):
                    with self.subTest(change=change), self.assertRaises(worker.WorkerError):
                        worker._config({**config, **change})
            with patch.dict(worker.os.environ, {"PYTORCH_ENABLE_MPS_FALLBACK": "1"}):
                with self.assertRaisesRegex(worker.WorkerError, "cpu_fallback_forbidden"):
                    worker._config(config)

    def test_runtime_pin_mismatch_does_not_load_backend(self):
        with patch.object(worker.importlib.metadata, "version", return_value="0.0"):
            with self.assertRaisesRegex(worker.WorkerError, "runtime_lock_mismatch"):
                worker._versions({"python": sys.version.split()[0], "torch": "2.14.0"})


if __name__ == "__main__":
    unittest.main()
