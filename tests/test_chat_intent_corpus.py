"""Synthetic construction and mutation controls, never production examples."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from deposium_bench import chat_intent_corpus as corpus
from deposium_bench.cases import candidate_request, validate_cases


def reviewed_row(**changes):
    row = {"message_preview": "Synthetic message for a document assistant.",
           "label": "search_query", "decision": "corrected",
           "reviewed_at": "2026-11-07T23:12:00+01:00", "source": "owner",
           "tier_used": "synthetic-tier", "method": "synthetic-method", "day": "2026-11-01",
           "version_period": "synthetic-period", "terminal_state": "synthetic-stop",
           "retrieval_outcome": "synthetic-outcome", "production_intent": "greeting",
           "prelabel": {"label": "meta_question"}, "classification_id": "synthetic-hidden-id"}
    row.update(changes)
    return row


class ChatIntentCorpusTests(unittest.TestCase):
    def test_three_synthetic_review_rows_validate_and_preserve_input_rows(self):
        rows = [reviewed_row(label=label, decision=decision)
                for label, decision in (("search_query", "corrected"), ("greeting", "confirmed"),
                                        ("geo_analysis", "corrected"))]
        snapshot = deepcopy(rows)
        cases = [corpus.make_case(row, i, language, "synthetic-review-test")
                 for i, row in enumerate(rows) for language in ("fr", "en")]
        self.assertEqual(len(validate_cases(cases)), 6)
        self.assertEqual(rows, snapshot)
        for case in cases:
            self.assertEqual(case["split"], "test")
            self.assertEqual(case["scenario_id"], case["translation_family"])
            self.assertIn("2026-11-07.", case["reference"]["rationale"])
        self.assertEqual(cases[0]["reference"]["assertions"][0]["value"], "c")

    def test_metadata_and_predictions_stay_outside_input(self):
        case = corpus.make_case(reviewed_row(), 2, "en", "synthetic-review-test")
        visible = json.dumps(candidate_request(case)["input"])
        for marker in ("synthetic-tier", "synthetic-method", "synthetic-period", "synthetic-stop",
                       "synthetic-outcome", "synthetic-hidden-id", "production_intent", "prelabel",
                       "benchmark_pack", "reviewed_at", "choice_id"):
            self.assertNotIn(marker, visible)
        self.assertEqual(set(case["input"]), {"context", "question", "options"})

    def test_preview_truncates_unicode_characters_only(self):
        preview = "🌿" * 1499 + "é" + "hidden suffix"
        case = corpus.make_case(reviewed_row(message_preview=preview), 1, "fr", "synthetic-test")
        expected = corpus.load_cards()["intro"]["fr"].format(message=preview[:1500])
        self.assertEqual(case["input"]["context"], expected)
        self.assertNotIn("hidden suffix", case["input"]["context"])
        case["input"]["context"] += " changed"
        self.assertNotEqual(case["input"], case["evaluation"]["oracle"]["base_input"])

    def test_deterministic_date_and_no_prediction_fallback(self):
        row = reviewed_row(reviewed_at="2024-02-29")
        self.assertEqual(corpus.make_case(row, 0, "en", "synthetic-test"),
                         corpus.make_case(deepcopy(row), 0, "en", "synthetic-test"))
        for changes in ({"reviewed_at": "2025-02-29"}, {"reviewed_at": None},
                        {"reviewed_at": "yesterday"}, {"reviewed_at": "20261107"},
                        {"label": None}, {"label": "invalid"}, {"decision": "ambiguous"},
                        {"decision": None}, {"alternatives": ["search_query"]},
                        {"message_preview": " "}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                corpus.make_case(reviewed_row(**changes), 0, "en", "synthetic-test")
        for index, language, pack in ((-1, "en", "pack"),
                                      (True, "en", "pack"), (1, "other", "pack"), (1, "fr", "bad:pack")):
            with self.assertRaises(ValueError):
                corpus.make_case(row, index, language, pack)

    def test_index_above_ten_thousand_uses_canonical_minimum_width(self):
        for builder, prefix in ((corpus.make_case, "cir1"), (corpus.make_fixture_case, "cif1")):
            case = builder(reviewed_row(), 10000, "en", "synthetic-test")
            validate_cases([case])
            self.assertEqual(case["case_id"], f"{prefix}-10000-en")
            self.assertEqual(case["scenario_id"], f"{prefix}-10000")
            self.assertTrue(case["document_ids"][0].endswith(":10000"))
            case["case_id"] = f"{prefix}-010000-en"
            case["evaluation"]["base_case_id"] = case["case_id"]
            with self.assertRaisesRegex(ValueError, "Noncanonical"):
                validate_cases([case])

    def test_reference_context_options_or_identity_mutations_fail(self):
        original = corpus.make_case(reviewed_row(), 7, "fr", "synthetic-test")
        mutations = (
            lambda c: c["reference"]["assertions"][0].update(value="z"),
            lambda c: c["reference"]["assertions"][0].update(value="a"),
            lambda c: c["input"].update(context="changed context"),
            lambda c: c["input"]["options"].reverse(),
            lambda c: c["input"]["options"][0].update(description="changed"),
            lambda c: c["evaluation"]["oracle"]["choices"].update(a="search_query"),
            lambda c: c["evaluation"]["oracle"]["base_input"].update(context="changed snapshot"),
            lambda c: c.update(case_id="cir1-0008-fr"),
            lambda c: c.update(case_id="cir1-00007-fr"),
            lambda c: c.update(scenario_id="changed"),
            lambda c: c.update(translation_family="changed"),
            lambda c: c.update(document_ids=["private:changed:0007"]),
            lambda c: c.update(split="calibration"),
            lambda c: c.update(language="en"),
            lambda c: c["evaluation"].update(task_type="routing.chat-intent.fixture"),
            lambda c: c["evaluation"]["oracle"]["params"].update(label="invalid"),
            lambda c: c["reference"].update(rationale="Human review assumed"),
        )
        for i, mutate in enumerate(mutations):
            case = deepcopy(original)
            mutate(case)
            with self.subTest(mutation=i), self.assertRaises(ValueError):
                validate_cases([case])

    def test_synthetic_fixtures_and_alternatives(self):
        row = {"message_preview": "Synthetic request with two authored interpretations.",
               "label": "search_query", "alternatives": ["search_query", "complex_analysis"]}
        case = corpus.make_fixture_case(row, 3, "en", "synthetic-fixture-test")
        validate_cases([case])
        self.assertEqual(case["case_id"], "cif1-0003-en")
        self.assertEqual(case["split"], "calibration")
        self.assertEqual(case["document_ids"], ["synthetic:synthetic-fixture-test:0003"])
        self.assertEqual(case["reference"]["assertions"], [
            {"path": "/choice_id", "op": "one_of", "value": ["c", "d"]}])
        self.assertEqual(case["reference"]["rationale"], corpus.FIXTURE_RATIONALE)
        altered = deepcopy(case)
        altered["reference"]["assertions"][0]["value"] = ["a", "d"]
        with self.assertRaises(ValueError):
            validate_cases([altered])
        for alternatives in ([], ["invalid"], ["greeting"], ["search_query", "search_query"], "search_query"):
            with self.assertRaises(ValueError):
                corpus.make_fixture_case(dict(row, alternatives=alternatives), 3, "en", "synthetic-test")
        row.pop("alternatives")
        validate_cases([corpus.make_fixture_case(row, 4, "fr", "synthetic-test")])

    def test_equals_cases_match_frozen_json_schema_if_available(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("Optional JSON Schema validator not installed")
        schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/case-v2.schema.json").read_text())
        # Some installed validators cannot resolve the repository's custom
        # deposium.case URI. All references here are local fragments.
        schema.pop("$id")
        jsonschema.validate(corpus.make_case(reviewed_row(), 1, "fr", "synthetic-test"), schema)
        jsonschema.validate(corpus.make_fixture_case({"message_preview": "Synthetic greeting.", "label": "greeting"},
                                                   1, "en", "synthetic-test"), schema)


if __name__ == "__main__":
    unittest.main()
