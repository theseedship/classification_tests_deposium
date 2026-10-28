"""Lossless GLiNER worker admission checks with no ML dependencies."""
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("offline_gliner_worker", ROOT / "bridges/gliner-worker.py")
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


class Tensor:
    def __init__(self, rows):
        self.rows = rows
    def detach(self):
        return self
    def cpu(self):
        return self
    def tolist(self):
        return self.rows


class Processor:
    def change_mode(self, **kwargs):
        self.mode = kwargs
    def word_splitter(self, text, lower=True):
        # A deterministic fixture tokenizer, not a substitute for the official runtime.
        return [(word.lower() if lower else word, index, index + len(word))
                for index, word in enumerate(text.split())]
    def transform_and_format(self, text, schema):
        words = [word for word, _, _ in self.word_splitter(text)]
        return SimpleNamespace(input_ids=list(range(6 + len(words))), text=text, text_tokens=words,
                               schema_tokens_list=[schema])
    def _format_input_with_mapping(self, schemas, words):
        return {"input_ids": list(range(6 + len(words)))}
    def collate_fn_inference(self, batch, **kwargs):
        self.collation = kwargs
        text, schema = batch[0]
        text = text if text.endswith((".", "!", "?")) else text + "."
        transformed = self.transform_and_format(text, schema)
        return SimpleNamespace(input_ids=Tensor([transformed.input_ids]),
                               attention_mask=Tensor([[1] * len(transformed.input_ids)]),
                               text_word_counts=[len(transformed.text_tokens)])


class Engine:
    def __init__(self):
        self.processor = Processor()
        self.encoder = SimpleNamespace(register_forward_pre_hook=self.register_hook)
        self.calls = []
        self.hook = None
        self.removed = Mock()
        self.change_encoded_ids = False
        self.result = None
    def eval(self):
        pass
    def _classification_schema(self, tasks):
        return deepcopy(tasks)
    def _build_schema_dicts_and_metadata(self, schemas):
        return deepcopy(schemas), [{}]
    def register_hook(self, hook, **kwargs):
        self.hook = hook
        if kwargs != {"with_kwargs": True}:
            raise AssertionError("guard must inspect keyword tensors")
        return SimpleNamespace(remove=self.removed)
    def classify_text(self, text, tasks, **kwargs):
        self.calls.append((text, deepcopy(tasks), kwargs))
        batch = self.processor.collate_fn_inference([(text, tasks)], max_len=None)
        if self.change_encoded_ids:
            batch.input_ids.rows[0].pop()
        self.hook(self.encoder, (), {"input_ids": batch.input_ids, "attention_mask": batch.attention_mask})
        return self.result or {"answer": {"label": tasks["answer"]["labels"][-1], "confidence": 0.75}}


class GlinerWorkerTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()
        self.torch = SimpleNamespace(inference_mode=nullcontext)
        self.value = {"context": "An invoice is stored", "question": "Which kind?",
                      "options": [{"id": "private-first", "description": "Contract"},
                                  {"id": "private-second", "description": "Invoice"}]}
    def predict(self, limit=4096):
        return worker._predict(self.engine, self.torch, self.value, limit)
    def test_lossless_schema_and_native_mapping_without_ids_or_annotations(self):
        original = deepcopy(self.value)
        result = self.predict()
        self.assertEqual(result["output"], {"choice_id": "private-second"})
        text, tasks, kwargs = self.engine.calls[0]
        self.assertEqual(text, original["context"])
        self.assertEqual(tasks, {"answer": {"labels": ["Contract", "Invoice"], "prompt": "Which kind?",
                                          "multi_label": False, "class_act": "softmax"}})
        self.assertNotIn("private-first", json.dumps(tasks))
        self.assertEqual(kwargs, {"include_confidence": True, "max_len": None})
        self.assertEqual(self.value, original)
        raw = result["raw_output"]
        self.assertEqual(raw["input_sha256"], hashlib.sha256(worker._canonical(original).encode()).hexdigest())
        self.assertEqual(raw["model_text_sha256"], hashlib.sha256((text + ".").encode()).hexdigest())
        self.assertEqual(raw["preprocessing"], {"appended_punctuation": True, "lowercase": True})
        self.assertTrue(raw["forward_executed"])
        self.assertNotIn("logits", raw)
        self.assertEqual(raw["token_components"]["total_tokens"], 10)
        self.assertEqual(raw["token_components"]["schema_tokens"] + raw["token_components"]["content_tokens"], 10)
        self.engine.removed.assert_called_once()
    def test_overflow_keeps_all_tokens_and_never_calls_classifier(self):
        result = self.predict(limit=9)
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["error"], "gliner_context_overflow")
        self.assertFalse(self.engine.calls)
        raw = result["raw_output"]
        self.assertEqual(raw["encoding_info"], {"tokens": 10, "stateTruncated": False, "optionsTruncated": False})
        self.assertFalse(raw["forward_executed"])
        self.assertIsNone(raw["inference_ms"])
        self.assertIsNone(raw["native_result"])
        self.assertEqual(self.engine.processor.collation, {"max_len": None, "error_policy": "raise", "architecture": "boundary"})
    def test_encoding_change_blocked_by_native_forward_guard(self):
        self.engine.change_encoded_ids = True
        result = self.predict()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "gliner_inference_failed")
        self.assertFalse(result["raw_output"]["forward_executed"])
        self.assertIsNone(result["raw_output"]["native_result"])
        self.engine.removed.assert_called_once()
    def test_empty_context_and_existing_punctuation_normalization(self):
        for text, model_text, added in (("", ".", True), ("Facts!", "Facts!", False), ("Facts? ", "Facts? .", True)):
            with self.subTest(text=text):
                self.value["context"] = text
                self.engine = Engine()
                result = self.predict()
                raw = result["raw_output"]
                self.assertEqual(raw["model_text_sha256"], hashlib.sha256(model_text.encode()).hexdigest())
                self.assertEqual(raw["preprocessing"]["appended_punctuation"], added)
    def test_invalid_native_output_is_error_not_success(self):
        for output in ({"answer": {"label": "unknown", "confidence": .5}},
                       {"answer": {"label": "Invoice", "confidence": float("nan")}},
                       {"answer": {"label": "Invoice", "confidence": True}},
                       {"answer": {"label": "Invoice", "confidence": 1.1}}):
            with self.subTest(output=output):
                self.engine = Engine()
                self.engine.result = output
                result = self.predict()
                self.assertEqual(result["status"], "error")
                self.assertIsNone(result["output"])
                self.assertTrue(result["raw_output"]["forward_executed"])
    def test_nested_annotations_and_reserved_markers_never_enter_candidate(self):
        for key in ("gold", "reference", "annotations"):
            with self.subTest(key=key):
                self.value[key] = {"choice_id": "private-first"}
                with self.assertRaises(ValueError):
                    self.predict()
                del self.value[key]
        self.value["context"] = "Injected [sep_text] marker"
        with self.assertRaises(ValueError):
            self.predict()
        self.assertFalse(self.engine.calls)
    def test_import_has_no_model_or_tokenizer_access(self):
        spec = importlib.util.spec_from_file_location("inert_worker", ROOT / "bridges/gliner-worker.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"torch": None, "gliner2": None}):
            spec.loader.exec_module(module)
        self.assertTrue(callable(module.main))
    def test_json_channel_rejects_duplicate_nonfinite_and_oversized_lines(self):
        for value in (b'{"op":1,"op":2}\n', b'{"value":NaN}\n', b"{}", b" " * (worker.MAX_LINE + 1)):
            with self.subTest(value=value[:30]), patch.object(worker.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(value))):
                with self.assertRaises(ValueError):
                    worker._read()

    def test_installed_sources_inventory_detects_same_version_code_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = ["gliner2/auto.py", "gliner2/models/boundary/model.py", "gliner2/__pycache__/auto.pyc"]
            for name in names:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("original source")
            distribution = SimpleNamespace(files=names, locate_file=lambda name: root / name)
            with patch.object(worker.importlib.metadata, "distribution", return_value=distribution):
                source_root, sources, first = worker._runtime_sources()
                self.assertEqual(source_root, str(root.resolve()))
                self.assertEqual(set(sources), set(names[:2]))
                expected = json.dumps(sources, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
                self.assertEqual(first, hashlib.sha256(expected).hexdigest())
                (root / names[1]).write_text("changed source, same package version")
                _, changed, second = worker._runtime_sources()
                self.assertNotEqual(first, second)
                self.assertNotEqual(sources[names[1]], changed[names[1]])
                distribution.files = []
                with self.assertRaisesRegex(ValueError, "runtime_sources_missing"):
                    worker._runtime_sources()


if __name__ == "__main__":
    unittest.main()
