"""Model-free checks of ModernJEV's native pair preflight and ID mapping."""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import unittest


BACKEND = Path(__file__).resolve().parents[1] / "bridges/modernjev-backend.py"
spec = importlib.util.spec_from_file_location("modernjev_backend_under_test", BACKEND)
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

CHOICE = {"context": "Visible text.", "question": "Which action?",
          "options": [{"id": "opaque-b", "description": "Search"},
                      {"id": "opaque-a", "description": "Count"}]}


class FakeTokenizer:
    def __init__(self, *, empty=False, pair_extra=False):
        self.calls = []
        self.empty = empty
        self.pair_extra = pair_extra

    def num_special_tokens_to_add(self, *, pair):
        assert pair is True
        return 3

    def __call__(self, text_a, text_b=None, **kwargs):
        self.calls.append((text_a, text_b, kwargs))
        if self.empty:
            return {"input_ids": []}
        first = [ord(character) for character in text_a]
        if text_b is None:
            assert kwargs["add_special_tokens"] is False
            return {"input_ids": first}
        second = [ord(character) for character in text_b]
        assert kwargs["truncation"] in (False, "only_first")
        assert kwargs["padding"] in (False, True)
        return {"input_ids": [1, *first, 2, *second, 3] + ([4] if self.pair_extra else [])}


class FakeTensor:
    def __init__(self, rows):
        self.rows = rows

    def detach(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return self.rows


class FakeModel:
    def __init__(self):
        self.native_calls = []

    def __call__(self, **kwargs):
        return self.forward(**kwargs)

    def forward(self, *, input_ids, attention_mask):
        self.native_calls.append((input_ids.tolist(), attention_mask.tolist()))
        return object()


class FakeHelper:
    def __init__(self):
        self.states = []
        self.criteria = []

    def serialize_state(self, state):
        self.states.append(state)
        compact = {"available_tools": state.get("available_tools") or [],
                   "conversation": state.get("conversation") or []}
        return json.dumps(compact, ensure_ascii=False)

    def normalize_criteria(self, criteria):
        self.criteria.append(criteria)
        return {description: description for description in criteria}


class FakeEngine:
    def __init__(self, *, empty=False, pair_extra=False):
        self.tokenizer = FakeTokenizer(empty=empty, pair_extra=pair_extra)
        self.model = FakeModel()
        self.calls = []
        self.wrong_tokens = False
        self.wrong_mask = False
        self.raise_after_forward = False
        self.skip_last_forward = False

    def decide(self, *, state, question, criteria, candidate_batch_size):
        self.calls.append((state, question, criteria, candidate_batch_size))
        compact = {"available_tools": state.get("available_tools") or [],
                   "conversation": state.get("conversation") or []}
        text_a = question + "\n\nSTATE:\n" + json.dumps(compact, ensure_ascii=False)
        for index, description in enumerate(criteria):
            if self.skip_last_forward and index == len(criteria) - 1:
                break
            row = self.tokenizer(text_a, f"{description}: {description}",
                                 truncation="only_first", max_length=4096,
                                 padding=True, return_tensors="pt")["input_ids"]
            if self.wrong_tokens and index == 0:
                row[0] += 1
            mask = [1] * len(row)
            if self.wrong_mask and index == 0:
                mask[-1] = 0
            self.model(input_ids=FakeTensor([row]), attention_mask=FakeTensor([mask]))
        if self.raise_after_forward:
            raise RuntimeError("failure after native forward")
        scores = [2.0 if description == "Count" else -1.0 for description in criteria]
        peak = max(scores)
        weights = [math.exp(score - peak) for score in scores]
        probabilities = [weight / sum(weights) for weight in weights]
        order = sorted(range(len(criteria)), key=lambda index: (-scores[index], criteria[index]))
        return {"predicted_label": criteria[order[0]], "allowed_choices": criteria,
                "candidates": [{"label": criteria[index], "score": probabilities[index],
                                "raw_score": scores[index], "rank": rank+1}
                               for rank, index in enumerate(order)],
                "truncated": False, "max_sequence_length": 4096,
                "note": "Scores rank this supplied choice set; they are not calibrated confidence."}


class ModernJevBackendTests(unittest.TestCase):
    def model(self, *, empty=False, pair_extra=False):
        engine = FakeEngine(empty=empty, pair_extra=pair_extra)
        helper = FakeHelper()
        return backend.ModernJevBackend(engine, helper)

    def test_native_state_serialization_and_permutation_mapping(self):
        for options in (CHOICE["options"], list(reversed(CHOICE["options"]))):
            with self.subTest(order=[option["id"] for option in options]):
                model = self.model()
                result = model.predict({**CHOICE, "options": options})
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["output"], {"choice_id": "opaque-a"})
                self.assertEqual(len(model.engine.calls), 1)
                state, question, criteria, batch_size = model.engine.calls[0]
                self.assertEqual(state, {"conversation": [{"role": "user", "content":
                                                          CHOICE["context"]}],
                                         "available_tools": []})
                self.assertEqual(question, CHOICE["question"])
                self.assertEqual(criteria, [option["description"] for option in options])
                self.assertEqual(batch_size, 1)
                self.assertEqual(model.helper.states, [state])
                self.assertEqual(model.helper.criteria, [criteria])
                pairs = [(first, second) for first, second, kwargs in model.engine.tokenizer.calls
                         if second is not None and kwargs["truncation"] is False]
                self.assertEqual(len(pairs), 2)
                for first, second in pairs:
                    self.assertIn("STATE:\n", first)
                    self.assertNotIn("opaque-", first + second)
                    self.assertEqual(second.split(": "), [second.split(": ")[0]] * 2)
                info = result["raw_output"]["encoding_info"]
                self.assertEqual(info["tokens_per_pair"], info["native_raw_pair_tokens"])
                self.assertEqual(info["max_sequence_tokens"], max(info["tokens_per_pair"]))
                self.assertEqual(info["sum_sequence_tokens"], sum(info["tokens_per_pair"]))
                self.assertEqual(info["forward_count"], 2)
                self.assertTrue(info["forward_ids_equal"])
                self.assertTrue(info["forward_masks_equal"])
                self.assertEqual(info["actual_input_ids_sha256"], info["pair_input_ids_sha256"])
                self.assertEqual(len(model.engine.model.native_calls), 2)
                self.assertNotIn("forward", vars(model.engine.model))

    def test_full_context_question_and_criterion_overflow_never_call_helper(self):
        for value in (
            {**CHOICE, "context": "x" * 4096},
            {**CHOICE, "question": "x" * 4096},
            {**CHOICE, "options": [{"id": "opaque-b", "description": "x" * 4096},
                                    CHOICE["options"][1]]},
        ):
            with self.subTest(area=value["question"][:8], first=value["options"][0]["description"][:8]):
                model = self.model()
                result = model.predict(value)
                self.assertEqual((result["status"], result["error"]),
                                 ("unsupported", "modernjev_context_overflow"))
                self.assertEqual(model.engine.calls, [])
                self.assertFalse(result["raw_output"]["forward_executed"])
                self.assertGreater(result["raw_output"]["encoding_info"]["max_sequence_tokens"], 4096)

    def test_exact_limit_is_allowed_without_truncation(self):
        model = self.model()
        base_state = {"conversation": [{"role": "user", "content": ""}],
                      "available_tools": []}
        state_text = model.helper.serialize_state(base_state)
        question = "Q" if (4096 - len("Q\n\nSTATE:\n" + state_text) - 5) % 2 == 0 else "QQ"
        base = question + "\n\nSTATE:\n" + state_text
        # A list criterion becomes "description: description" in the helper.
        option = "A" * ((4096 - len(base) - 5) // 2)
        value = {"context": "", "question": question,
                 "options": [{"id": "a", "description": option},
                             {"id": "b", "description": "B"}]}
        result = model.predict(value)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["raw_output"]["encoding_info"]["max_sequence_tokens"], 4096)
        self.assertEqual(len(model.engine.calls), 1)

    def test_empty_invalid_and_pair_mismatch_refuse_without_decide(self):
        for model, value, status, error in (
            (self.model(empty=True), CHOICE, "unsupported", "modernjev_empty_encoding"),
            (self.model(pair_extra=True), CHOICE, "unsupported", "modernjev_pair_encoding_mismatch"),
            (self.model(), {**CHOICE, "options": []}, "error", "modernjev_input_invalid"),
            (self.model(), {**CHOICE, "options": [{"id": "a", "description": ""},
                                                  CHOICE["options"][1]]},
             "error", "modernjev_input_invalid"),
        ):
            with self.subTest(error=error):
                result = model.predict(value)
                self.assertEqual((result["status"], result["error"]), (status, error))
                self.assertEqual(model.engine.calls, [])

    def test_native_truncation_and_bad_distribution_rejected(self):
        for defect in ("truncated", "candidate"):
            with self.subTest(defect=defect):
                model = self.model()
                original = model.engine.decide

                def faulty(**kwargs):
                    result = original(**kwargs)
                    if defect == "truncated":
                        result["truncated"] = True
                    else:
                        result["candidates"][0]["score"] = float("nan")
                    return result

                model.engine.decide = faulty
                result = model.predict(CHOICE)
                self.assertEqual((result["status"], result["error"]),
                                 ("error", "modernjev_distribution_invalid"))

    def test_wrong_forward_ids_and_masks_are_rejected_before_native_call(self):
        for defect, field in (("wrong_tokens", "forward_ids_equal"),
                              ("wrong_mask", "forward_masks_equal")):
            with self.subTest(defect=defect):
                model = self.model()
                setattr(model.engine, defect, True)
                result = model.predict(CHOICE)
                self.assertEqual((result["status"], result["error"]),
                                 ("error", "modernjev_forward_encoding_mismatch"))
                self.assertTrue(result["raw_output"]["forward_executed"])
                self.assertEqual(result["raw_output"]["encoding_info"]["forward_count"], 1)
                self.assertFalse(result["raw_output"]["encoding_info"][field])
                self.assertEqual(model.engine.model.native_calls, [])
                self.assertNotIn("forward", vars(model.engine.model))

    def test_exception_after_forward_preserves_flag_and_restores_hook(self):
        model = self.model()
        model.engine.raise_after_forward = True
        result = model.predict(CHOICE)
        self.assertEqual((result["status"], result["error"]),
                         ("error", "modernjev_inference_failed"))
        self.assertTrue(result["raw_output"]["forward_executed"])
        self.assertEqual(result["raw_output"]["encoding_info"]["forward_count"], 2)
        self.assertEqual(len(model.engine.model.native_calls), 2)
        self.assertNotIn("forward", vars(model.engine.model))

    def test_missing_forward_is_not_a_valid_decision(self):
        model = self.model()
        model.engine.skip_last_forward = True
        result = model.predict(CHOICE)
        self.assertEqual((result["status"], result["error"]),
                         ("error", "modernjev_forward_count_mismatch"))
        self.assertTrue(result["raw_output"]["forward_executed"])
        self.assertEqual(result["raw_output"]["encoding_info"]["forward_count"], 1)
        self.assertNotIn("forward", vars(model.engine.model))


if __name__ == "__main__":
    unittest.main()
