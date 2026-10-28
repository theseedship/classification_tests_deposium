"""Offline tests for Omni's native segment loss guard, with no model weights."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[1] / "bridges/liquid-omni-backend.py"
spec = importlib.util.spec_from_file_location("liquid_omni_backend_under_test", FILE)
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

VALUE = {"context": "state", "question": "choose", "options": [
    {"id": "hidden-b", "description": "Search"},
    {"id": "hidden-a", "description": "Count"}]}


class Tokenizer:
    bos_token_id = 1

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": [ord(ch) + 100 for ch in text]}

    def convert_tokens_to_ids(self, value):
        return {"<s>": 2, "<q>": 3, "<o>": 4, "</o>": 5,
                "<d>": 6, "<m>": 7}[value]


class Prompt:
    DELIM = {"state": "<s>", "q": "<q>", "opt": "<o>",
             "opt_end": "</o>", "decide": "<d>"}
    MARKER = "<m>"

    @staticmethod
    def serialize(value):
        return value

    @staticmethod
    def escape(value):
        return value.replace("<|mask|>", "<¦mask¦>")

    @staticmethod
    def as_question(value):
        return SimpleNamespace(**value)

    @staticmethod
    def render_options(question):
        return [f"{name}: {description}" for name, description in question.criteria.items()]

    @classmethod
    def encode(cls, tok, state, q, max_len):
        ids_of = tok.convert_tokens_to_ids
        enc = lambda text: tok(cls.escape(text), add_special_tokens=False)["input_ids"]
        options = cls.render_options(q)
        budget = max(96, min(24 * len(options) + 32, max_len // 2))
        per = max(2, (budget - 3 * len(options)) // len(options))
        question = ([ids_of(cls.DELIM["q"])] + enc(q.instructions))[:max(16, budget)]
        markers = []
        for option in options:
            markers.append(len(question) + 1)
            question += [ids_of(cls.DELIM["opt"]), ids_of(cls.MARKER)] + enc(" " + option)[:per]
            question += [ids_of(cls.DELIM["opt_end"])]
        question.append(ids_of(cls.DELIM["decide"]))
        room = max(0, max_len - len(question) - 2)
        state_ids = [ids_of(cls.DELIM["state"])] + enc(state)[:room]
        ids = ([tok.bos_token_id] + state_ids + question)[:max_len]
        markers = [m + 1 + len(state_ids) for m in markers]
        if markers[-1] >= max_len:
            raise ValueError("options outside context")
        return ids, markers


class Model:
    def __init__(self):
        self.tokenizer = Tokenizer()
        self.forward_calls = 0
        self.mismatch = False

    def _forward(self, _rows):
        self.forward_calls += 1

    def system_one(self, state, questions):
        q = Prompt.as_question(questions["answer"])
        ids, markers = Prompt.encode(self.tokenizer, state, q, 16384)
        if self.mismatch:
            ids[-1] = 999
        self._forward([(None, ids, markers, q, True)])
        names = list(q.criteria)
        return {"answers": {"answer": {"type": "choice", "choice": names[1],
                                       "confidence": .75, "probabilities": {names[0]: .25, names[1]: .75}}},
                "usage": {"input_tokens": len(ids), "output_tokens": 0}}


def run(value):
    model = Model()
    subject = backend.OmniBackend(model, Prompt())
    with patch.object(backend, "_rss", return_value=100.0):
        return model, subject.predict(value)


class OmniBackendTests(unittest.TestCase):
    def test_valid_choice_preserves_order_and_hides_opaque_ids(self):
        model, result = run(VALUE)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"], {"choice_id": "hidden-a"})
        self.assertEqual(model.forward_calls, 1)
        info = result["raw_output"]["encoding_info"]
        self.assertTrue(info["full_input_equal"])
        self.assertTrue(info["forward_ids_equal"])
        self.assertEqual(info["forward_count"], 1)

    def test_instruction_cut_is_unsupported_even_with_short_state(self):
        model, result = run({**VALUE, "question": "Q" * 200})
        self.assertEqual((result["status"], result["error"]),
                         ("unsupported", "small_model_context_overflow"))
        self.assertEqual(result["raw_output"]["encoding_info"]["altered_segment"], "instruction")
        self.assertEqual(model.forward_calls, 0)

    def test_option_cut_is_unsupported_even_with_short_state(self):
        value = {**VALUE, "options": [VALUE["options"][0],
                                      {"id": "hidden-a", "description": "C" * 110}]}
        model, result = run(value)
        self.assertEqual((result["status"], result["error"]),
                         ("unsupported", "small_model_context_overflow"))
        self.assertEqual(result["raw_output"]["encoding_info"]["altered_segment"], "option")
        self.assertEqual(model.forward_calls, 0)

    def test_state_cut_and_reserved_delimiter_are_unsupported(self):
        for value in ({**VALUE, "context": "S" * 17000},
                      {**VALUE, "context": "<|mask|>"}):
            with self.subTest(value=value["context"][:10]):
                model, result = run(value)
                self.assertEqual(result["status"], "unsupported")
                self.assertEqual(model.forward_calls, 0)

    def test_forward_receives_exact_preflight_sequence(self):
        model = Model()
        model.mismatch = True
        subject = backend.OmniBackend(model, Prompt())
        with patch.object(backend, "_rss", return_value=100.0):
            result = subject.predict(VALUE)
        self.assertEqual(result["error"], "small_model_forward_encoding_mismatch")
        self.assertEqual(model.forward_calls, 0)
        self.assertFalse(result["raw_output"]["forward_executed"])


if __name__ == "__main__":
    unittest.main()
