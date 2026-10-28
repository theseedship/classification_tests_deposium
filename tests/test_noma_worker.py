"""Offline tests for Noma's exact choice projection and forward audit."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import types
import unittest
from unittest.mock import patch


WORKER = Path(__file__).resolve().parents[1] / "bridges/noma-worker.py"
spec = importlib.util.spec_from_file_location("noma_worker_under_test", WORKER)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class FakeTensor:
    def __init__(self, ids):
        self.ids = ids
        self.shape = (1, len(ids))

    def detach(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return [self.ids]


class FakeSerializer:
    def __init__(self, tokenizer, max_prefix_tokens=4096, use_facts=True):
        self.tokenizer = tokenizer
        self.max_prefix = max_prefix_tokens
        self.use_facts = use_facts

    def prefix(self, state, questions, reference_time):
        assert reference_time == worker.REFERENCE_TIME
        assert questions[0]["type"] == "choice"
        ids = [11, 12]
        truncated = False
        if self.tokenizer.truncate and self.max_prefix == 4096:
            ids = [11]
            truncated = True
        if self.tokenizer.long:
            ids = list(range(1025))
        return types.SimpleNamespace(ids=ids, truncated=truncated)

    def block(self, question):
        return types.SimpleNamespace(ids=[21, 22])


class FakeModel:
    def __init__(self, mode="ok"):
        self.mode = mode
        self.tok = types.SimpleNamespace(truncate=mode == "truncated", long=mode == "long")
        self.ser = FakeSerializer(self.tok)
        self.cfg = types.SimpleNamespace(use_facts=True, facts_version="facts-0.2")
        self.bucket = None
        self._graphs = None
        self.forward_count = 0
        self.hidden = self._hidden
        self.last_question = None

    def _hidden(self, _ids, **_kwargs):
        self.forward_count += 1

    def decide(self, state, questions, reference_time=None, fork=None):
        assert reference_time == worker.REFERENCE_TIME
        assert fork is False
        assert state == "Texte visible\u2028avec saut."
        self.last_question = questions["answer"]
        ids = [11, 12, 21, 22] if self.mode != "wrong_ids" else [11, 12, 21, 99]
        self.hidden(FakeTensor(ids))
        probabilities = {"c0": 0.25, "c1": 0.75}
        if self.mode == "nan":
            probabilities["c1"] = math.nan
        if self.mode == "bad_sum":
            probabilities["c1"] = 0.5
        if self.mode == "bad_order":
            probabilities = {"c1": 0.75, "c0": 0.25}
        answer = (probabilities, 0.99, 0.05)
        return {"answer": answer}, (3 if self.mode == "wrong_tokens" else 4)


INPUT = {
    "context": "Texte visible\u2028avec saut.",
    "question": "Quelle action ?",
    "options": [{"id": "opaque-b", "description": "Rechercher"},
                {"id": "opaque-a", "description": "Compter"}],
}
FACTS = types.SimpleNamespace(facts=lambda state, questions, time: ["F1: fixture"])


def predict(model, cap=1024):
    with patch.object(worker, "_rss", return_value=12.5):
        return worker._predict(model, INPUT, cap, serializer_cls=FakeSerializer,
                               fact_channel=FACTS)


class NomaWorkerTests(unittest.TestCase):
    def test_ordinals_preserve_descriptions_and_return_opaque_id(self):
        model = FakeModel()
        result = predict(model)
        self.assertEqual((result["status"], result["output"]), ("ok", {"choice_id": "opaque-a"}))
        self.assertEqual(model.forward_count, 1)
        self.assertEqual(model.last_question["criteria"], {"c0": "Rechercher", "c1": "Compter"})
        raw = result["raw_output"]
        self.assertEqual(set(raw), {"native_result", "native_tokens", "input_sha256",
                                    "ordered_ids", "encoding_info", "forward_executed",
                                    "decision_ms", "inference_ms", "rss_mb"})
        self.assertEqual(raw["ordered_ids"], ["opaque-b", "opaque-a"])
        self.assertEqual(raw["native_result"],
                         {"probabilities": {"c0": 0.25, "c1": 0.75},
                          "abstain": 0.99, "uncertainty": 0.05})
        self.assertTrue(raw["forward_executed"])
        self.assertEqual(raw["encoding_info"],
                         {"tokens": 4, "prefix_tokens": 2, "block_tokens": 2,
                          "prefix_truncated": False, "prefix_uncapped_equal": True,
                          "forward_count": 1, "forward_ids_equal": True,
                          "facts_version": "facts-0.2", "reference_time": worker.REFERENCE_TIME,
                          "fact_lines": ["F1: fixture"]})
        canonical = json.dumps(INPUT, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False) + "\n"
        self.assertEqual(raw["input_sha256"], hashlib.sha256(canonical.encode()).hexdigest())
        self.assertIn("\u2028", canonical)

    def test_truncation_and_token_ceiling_never_forward(self):
        for mode, cap in (("truncated", 1024), ("long", 1024), ("ok", 3)):
            with self.subTest(mode=mode, cap=cap):
                model = FakeModel(mode)
                result = predict(model, cap)
                self.assertEqual((result["status"], result["error"]),
                                 ("unsupported", "noma_context_overflow"))
                self.assertEqual(model.forward_count, 0)
                self.assertFalse(result["raw_output"]["forward_executed"])
                self.assertEqual(result["raw_output"]["native_tokens"], 0)
                self.assertIsNone(result["raw_output"]["inference_ms"])
                if mode == "truncated":
                    self.assertTrue(result["raw_output"]["encoding_info"]["prefix_truncated"])
                    self.assertFalse(result["raw_output"]["encoding_info"]["prefix_uncapped_equal"])
                    info = result["raw_output"]["encoding_info"]
                    self.assertEqual(info["tokens"], info["prefix_tokens"] + info["block_tokens"])
                    self.assertFalse(info["forward_ids_equal"])

    def test_forward_and_native_token_mismatch_fail_closed(self):
        for mode, error in (("wrong_ids", "noma_forward_ids_mismatch"),
                            ("wrong_tokens", "noma_native_tokens_mismatch")):
            with self.subTest(mode=mode):
                model = FakeModel(mode)
                result = predict(model)
                self.assertEqual((result["status"], result["error"]), ("error", error))
                self.assertEqual(result["raw_output"]["forward_executed"], mode != "wrong_ids")
                self.assertEqual(result["raw_output"]["encoding_info"]["forward_count"], 1)

    def test_invalid_native_distributions_fail_closed(self):
        for mode in ("nan", "bad_sum", "bad_order"):
            with self.subTest(mode=mode):
                result = predict(FakeModel(mode))
                self.assertEqual((result["status"], result["error"]),
                                 ("error", "noma_distribution_invalid"))
                self.assertTrue(result["raw_output"]["forward_executed"])

    def test_duplicate_and_nonfinite_json_rejected_without_model(self):
        for payload in (b'{"op":"predict","op":"predict"}\n',
                        b'{"op":"predict","sequence":NaN}\n'):
            with self.subTest(payload=payload), patch.object(
                    worker.sys, "stdin", io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8")):
                with self.assertRaises(worker.NomaWorkerError):
                    worker._read()

    def test_runtime_pins_checked_without_model_import(self):
        package = "synthetic-runtime"
        with patch.object(worker.importlib.metadata, "version", return_value="1.2.3"):
            pins = {"python": worker.sys.version.split()[0], package: "1.2.3"}
            self.assertEqual(worker._versions(pins), pins)
            with self.assertRaisesRegex(worker.NomaWorkerError, "noma_runtime_lock_mismatch"):
                worker._versions({package: "2.0"})


if __name__ == "__main__":
    unittest.main()
