"""Model-free checks for Muose's complete-sequence gate and native mapping."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


BACKEND = Path(__file__).resolve().parents[1] / "bridges/muose-backend.py"
spec = importlib.util.spec_from_file_location("muose_backend_under_test", BACKEND)
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

CHOICE = {"context": "Visible text.", "question": "Which action?",
          "options": [{"id": "opaque-b", "description": "Search"},
                      {"id": "opaque-a", "description": "Count"}]}


class FakeEncoding:
    def __init__(self, ids):
        self.ids = ids


class FakeTokenizer:
    def __init__(self, *, empty=False):
        self.prompts = []
        self.empty = empty

    def encode(self, text, *, add_special_tokens):
        self.prompts.append(text)
        assert add_special_tokens is False
        return FakeEncoding([] if self.empty else [ord(character) for character in text])


class FakeModel:
    def __init__(self):
        self.forward_calls = []
        self.raise_after_forward = False

    def __call__(self, rows, lengths):
        return self.forward(rows, lengths)

    def forward(self, rows, lengths):
        self.forward_calls.append((rows, lengths))
        if self.raise_after_forward:
            raise RuntimeError("failure after native forward")
        return [2.0 if "CRITERION:\nCount" in "".join(map(chr, row)) else -1.0
                for row in rows]


class FakeBackend(backend.MuoseBackend):
    def __init__(self, *, empty=False):
        super().__init__(FakeModel(), FakeTokenizer(empty=empty))
        self.forward_calls = self.model.forward_calls

    def _score_sequences(self, rows, lengths):
        return self.model(rows, lengths)


class MuoseBackendTests(unittest.TestCase):
    def test_independent_rows_hide_ids_and_map_supplied_order(self):
        for options in (CHOICE["options"], list(reversed(CHOICE["options"]))):
            with self.subTest(order=[option["id"] for option in options]):
                model = FakeBackend()
                result = model.predict({**CHOICE, "options": options})
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["output"], {"choice_id": "opaque-a"})
                self.assertEqual(len(model.forward_calls), 1)
                self.assertNotIn("forward", vars(model.model))
                self.assertEqual(len(model.tokenizer.prompts), 2)
                for prompt, option in zip(model.tokenizer.prompts, options):
                    self.assertEqual(prompt, backend.TEMPLATE["format"].format(
                        context=CHOICE["context"], question=CHOICE["question"],
                        description=option["description"]))
                    self.assertNotIn("opaque-", prompt)
                raw = result["raw_output"]
                self.assertEqual(raw["ordered_ids"], [option["id"] for option in options])
                self.assertEqual(raw["native_result"]["scores"],
                                 [2.0 if option["description"] == "Count" else -1.0
                                  for option in options])
                self.assertAlmostEqual(sum(raw["native_result"]["probabilities"]), 1.0)
                info = raw["encoding_info"]
                self.assertEqual(info["max_sequence_tokens"], max(info["tokens_per_option"]))
                self.assertEqual(info["sum_sequence_tokens"], sum(info["tokens_per_option"]))
                self.assertEqual(info["padded_batch_tokens"],
                                 2 * info["max_sequence_tokens"])

    def test_over_budget_context_or_candidate_never_forwards(self):
        for value in (
            {**CHOICE, "context": "x" * 512},
            {**CHOICE, "question": "x" * 512},
            {**CHOICE, "options": [{"id": "opaque-b", "description": "x" * 512},
                                    CHOICE["options"][1]]},
        ):
            with self.subTest(value=value["options"][0]["description"][:8]):
                model = FakeBackend()
                result = model.predict(value)
                self.assertEqual((result["status"], result["error"]),
                                 ("unsupported", "muose_context_overflow"))
                self.assertEqual(model.forward_calls, [])
                self.assertFalse(result["raw_output"]["forward_executed"])
                self.assertGreater(result["raw_output"]["encoding_info"]["max_sequence_tokens"], 512)

    def test_exact_512_is_allowed_without_truncation(self):
        base = backend.TEMPLATE["format"].format(
            context="", question="Q", description="A")
        long_option = "A" * (512 - len(base) + 1)
        model = FakeBackend()
        result = model.predict({"context": "", "question": "Q",
                                "options": [{"id": "a", "description": long_option},
                                            {"id": "b", "description": "B"}]})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["raw_output"]["encoding_info"]["max_sequence_tokens"], 512)
        self.assertEqual(len(model.forward_calls), 1)
        self.assertEqual(model.forward_calls[0][1][0], 512)
        self.assertFalse(result["raw_output"]["encoding_info"]["truncated"])

    def test_empty_encoding_and_invalid_input_refuse_without_forward(self):
        for model, value, status, error in (
            (FakeBackend(empty=True), CHOICE, "unsupported", "muose_empty_encoding"),
            (FakeBackend(), {**CHOICE, "options": []}, "error", "muose_input_invalid"),
            (FakeBackend(), {**CHOICE, "options": [{"id": "a", "description": ""},
                                                   CHOICE["options"][1]]},
             "error", "muose_input_invalid"),
        ):
            with self.subTest(error=error):
                result = model.predict(value)
                self.assertEqual((result["status"], result["error"]), (status, error))
                self.assertEqual(model.forward_calls, [])

    def test_right_padding_preserves_real_positions(self):
        self.assertEqual(backend._pad_rows([[7, 8, 9], [4]], [3, 1]),
                         [[7, 8, 9], [4, 0, 0]])
        with self.assertRaises(backend.MuoseBackendError):
            backend._pad_rows([[1] * 513], [513])

    def test_nonfinite_scores_rejected(self):
        model = FakeBackend()
        model.model.forward = lambda _rows, _lengths: [float("nan"), 1.0]
        result = model.predict(CHOICE)
        self.assertEqual((result["status"], result["error"]),
                         ("error", "muose_distribution_invalid"))

    def test_post_forward_exception_retains_observed_flag_and_restores_hook(self):
        model = FakeBackend()
        model.model.raise_after_forward = True
        result = model.predict(CHOICE)
        self.assertEqual((result["status"], result["error"]),
                         ("error", "muose_inference_failed"))
        self.assertEqual(len(model.forward_calls), 1)
        self.assertTrue(result["raw_output"]["forward_executed"])
        self.assertIsNone(result["raw_output"]["native_result"])
        self.assertNotIn("forward", vars(model.model))

    def test_exception_before_model_forward_keeps_flag_false(self):
        model = FakeBackend()
        model._score_sequences = lambda _rows, _lengths: (_ for _ in ()).throw(
            RuntimeError("tensor preparation failed"))
        result = model.predict(CHOICE)
        self.assertEqual((result["status"], result["error"]),
                         ("error", "muose_inference_failed"))
        self.assertEqual(model.forward_calls, [])
        self.assertFalse(result["raw_output"]["forward_executed"])
        self.assertNotIn("forward", vars(model.model))


if __name__ == "__main__":
    unittest.main()
