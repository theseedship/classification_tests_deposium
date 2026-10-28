"""Model-free checks of Laya's lossless gate and exact forward observation."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch


WORKER = Path(__file__).resolve().parents[1] / "bridges/laya-worker.py"
spec = importlib.util.spec_from_file_location("laya_worker_under_test", WORKER)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

INPUT = {"context": "Visible text.", "question": "Which action?",
         "options": [{"id": "opaque-b", "description": "Search"},
                     {"id": "opaque-a", "description": "Count"}]}


class FakeTensor:
    def __init__(self, rows):
        self.rows = rows

    def detach(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return self.rows


class FakeTokenizer:
    mask_token = "<mask>"


class FakeCommon:
    mode = "ok"

    @staticmethod
    def encode_text(_tok, text, **_kwargs):
        return {"input_ids": [ord(char) for char in text]}

    @staticmethod
    def serialize_state(state):
        return state

    @classmethod
    def build_head(cls, _tok, _question, head_max_len):
        head = [101, 102, 103]
        if cls.mode == "head_cut" and head_max_len == 256:
            head = [101, 103]
        return head, [1, 2], {"options_distinct": 1 if cls.mode == "collision" else 2}

    @classmethod
    def build_sequence(cls, tok, state, question, max_len, head_max_len,
                       state_ids, return_stats, return_truncation_stats):
        head, markers, stats = cls.build_head(tok, question, head_max_len)
        used = state_ids[:max(0, max_len - len(head) - 1)]
        return head + used + [104], markers, stats, {
            "state_tokens": len(state_ids), "state_tokens_dropped": len(state_ids) - len(used),
            "truncated": len(used) < len(state_ids)}


class FakeAgent:
    def __init__(self, *, mode="ok", cap=1024):
        self.mode = mode
        self.cfg = {"max_len": cap, "head_max_len": 256}
        self.device = types.SimpleNamespace(type="cpu")
        self.backend = "eager"
        self.amp_enabled = False
        self.tok = FakeTokenizer()
        self.forward_calls = 0
        self.last_question = None

    def _check_question(self, _name, _question):
        pass

    def _to_internal(self, question):
        return question

    def _encode_state(self, state, _ids, internal, max_len, head_max_len):
        state_ids = FakeCommon.encode_text(self.tok, state)["input_ids"]
        ids, markers, stats, state_stats = FakeCommon.build_sequence(
            self.tok, state, internal["answer"], max_len, head_max_len,
            state_ids=state_ids, return_stats=True, return_truncation_stats=True)
        return [{"ids": ids, "markers": markers, "options": stats,
                 "state_stats": state_stats}]

    def _forward(self, _batch):
        self.forward_calls += 1

    def predict(self, state, questions, max_len, head_max_len):
        self.last_question = questions["answer"]
        item = self._encode_state(state, ["answer"], questions, max_len, head_max_len)[0]
        ids = list(item["ids"])
        if self.mode == "wrong_ids":
            ids[-1] = 999
        batch = {"input_ids": FakeTensor([ids]),
                 "attention_mask": FakeTensor([[1] * len(ids)]),
                 "marker_pos": FakeTensor([item["markers"]]),
                 "marker_mask": FakeTensor([[True] * len(item["markers"])]),
                 "qtype": FakeTensor([0])}
        self._forward(batch)
        return {"model": "laya-rl-agent",
                "answers": {"answer": {"type": "choice", "choice": "Count",
                                       "probabilities": {"Search": 0.25, "Count": 0.75}}},
                "usage": {"truncated": False, "state_tokens_dropped": 0,
                          "truncated_questions": [], "input_tokens": len(item["ids"]),
                          "output_tokens": 0}}


def predict(agent, value=INPUT, cap=1024, mode="ok"):
    FakeCommon.mode = mode
    with patch.object(worker, "_rss", return_value=1000.0):
        return worker._predict(agent, value, cap, 256, common=FakeCommon)


class LayaWorkerTests(unittest.TestCase):
    def test_native_projection_hides_ids_and_maps_back_to_supplied_order(self):
        agent = FakeAgent()
        result = predict(agent)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"], {"choice_id": "opaque-a"})
        self.assertEqual(agent.last_question["criteria"], {"Search": None, "Count": None})
        self.assertEqual(agent.forward_calls, 1)
        info = result["raw_output"]["encoding_info"]
        self.assertEqual(info["forward_count"], 1)
        self.assertEqual(info["actual_sha256"], info["expected_sha256"])
        self.assertTrue(info["forward_masks_equal"])

    def test_head_option_collision_and_state_overflow_never_forward(self):
        for mode, value, cap in (("head_cut", INPUT, 1024), ("collision", INPUT, 1024),
                                 ("ok", {**INPUT, "context": "x" * 200}, 50),
                                 ("ok", {**INPUT, "options": [
                                     {"id": "a", "description": "x" * 60},
                                     {"id": "b", "description": "Count"}]}, 1024)):
            with self.subTest(mode=mode, cap=cap):
                agent = FakeAgent(cap=cap)
                result = predict(agent, value, cap, mode)
                self.assertEqual((result["status"], result["error"]),
                                 ("unsupported", "laya_context_overflow"))
                self.assertEqual(agent.forward_calls, 0)
                self.assertFalse(result["raw_output"]["forward_executed"])

    def test_reserved_mask_marker_is_not_silently_rewritten(self):
        agent = FakeAgent()
        result = predict(agent, {**INPUT, "context": "Visible <mask> text."})
        self.assertEqual((result["status"], result["error"]),
                         ("unsupported", "laya_context_overflow"))
        self.assertTrue(result["raw_output"]["encoding_info"]["reserved_marker"])
        self.assertEqual(agent.forward_calls, 0)

    def test_mismatched_forward_is_rejected_before_native_forward(self):
        agent = FakeAgent(mode="wrong_ids")
        result = predict(agent)
        self.assertEqual((result["status"], result["error"]),
                         ("error", "laya_forward_encoding_mismatch"))
        self.assertEqual(agent.forward_calls, 0)
        self.assertFalse(result["raw_output"]["forward_executed"])

    def test_duplicate_and_nonfinite_protocol_rejected(self):
        for payload in (b'{"op":"predict","op":"predict"}\n',
                        b'{"sequence":NaN}\n'):
            with self.subTest(payload=payload), patch.object(
                    worker.sys, "stdin", io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8")):
                with self.assertRaises(worker.LayaWorkerError):
                    worker._read()


if __name__ == "__main__":
    unittest.main()
