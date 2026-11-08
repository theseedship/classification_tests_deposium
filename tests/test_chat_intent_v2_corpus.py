"""Synthetic contract/mutation controls; no production messages or inference."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import chat_intent_v2_corpus as corpus
from deposium_bench.cases import candidate_request, validate_cases
from deposium_bench.scoring import score_case


def row(**changes):
    value = {"message_preview": "Synthetic request for a fact in a document.",
             "label": "search_query", "decision": "labeled",
             "reviewed_at": "2026-11-08T23:30:00-05:00", "split_group_id": "synthetic-family-01",
             "source_environment": "synthetic", "source_record_id": "synthetic-record",
             "annotation_policy_id": "rubric-v2-draft", "annotation_policy_sha256": "a" * 64,
             "external_voter_eligible": False}
    value.update(changes)
    return value


def case(**changes):
    return corpus.make_case(row(**changes), 0, "en", "synthetic-pack", "test")


class ChatIntentV2Tests(unittest.TestCase):
    def test_shared_harness_and_literal_review_provenance(self):
        value = case()
        validate_cases([value])
        params = value["evaluation"]["oracle"]["params"]
        self.assertEqual(params["reviewed_at"], row()["reviewed_at"])
        self.assertEqual(params["reviewed_date"], "2026-11-08")
        self.assertEqual(params["decision"], "labeled")
        self.assertEqual(params["policy_id"], corpus.POLICY_ID)
        self.assertEqual(params["annotation_policy_id"], "rubric-v2-draft")

    def test_all_labels_languages_and_splits(self):
        for language in ("fr", "en"):
            for split in ("calibration", "test"):
                for index, (label, letter) in enumerate(zip(corpus.INTENTS, corpus.LETTERS)):
                    value = corpus.make_case(row(label=label), index, language, "synthetic-pack", split)
                    validate_cases([value])
                    self.assertEqual(value["reference"]["assertions"][0]["value"], letter)
                    self.assertEqual(value["split"], split)

    def test_candidate_has_only_preview_and_frozen_generic_cards(self):
        value = case(message_preview="synthetic-visible-token",
                     hidden_joined_field="synthetic-hidden-token",
                     source="synthetic-report-only-token")
        request = candidate_request(value)
        self.assertEqual(set(request), {"case_id", "contract_id", "input"})
        self.assertEqual(set(request["input"]), {"context", "question", "options"})
        serialized = json.dumps(request)
        self.assertIn("synthetic-visible-token", serialized)
        self.assertNotIn("synthetic-hidden-token", serialized)
        self.assertNotIn("synthetic-report-only-token", serialized)
        self.assertNotIn("synthetic-record", serialized)
        self.assertNotIn("reviewed_at", serialized)
        self.assertNotIn("split_group_id", serialized)
        self.assertEqual([x["id"] for x in request["input"]["options"]], list("abcdefghij"))

    def test_preview_truncation_is_exact_and_no_metadata_fallback(self):
        value = case(message_preview="x" * 1500 + "not-candidate-visible")
        self.assertNotIn("not-candidate-visible", value["input"]["context"])
        for invalid in (None, "", "   ", " " * 1500 + "x"):
            with self.subTest(invalid_type=type(invalid).__name__), self.assertRaises(ValueError):
                case(message_preview=invalid, full_message="synthetic fallback forbidden")

    def test_manual_labels_are_required_not_prelabels_or_fake_confirmations(self):
        for changes in ({"label": None, "production_intent": "search_query"},
                        {"decision": "confirmed"}, {"decision": "corrected"},
                        {"decision": None}, {"alternatives": ["search_query"]},
                        {"reviewed_at": "not-an-iso-date"}):
            with self.subTest(keys=list(changes)), self.assertRaises(ValueError):
                case(**changes)
        for changes in ({"external_voter_eligible": 0},
                        {"annotation_policy_sha256": "invalid"},
                        {"source": float("nan")}, {"split_group_id": "contains spaces"}):
            with self.subTest(keys=list(changes)), self.assertRaises(ValueError):
                case(**changes)

    def test_family_cannot_cross_split_even_with_different_indices_languages(self):
        calibration = corpus.make_case(row(), 0, "fr", "synthetic-pack", "calibration")
        test = corpus.make_case(row(), 1, "en", "synthetic-pack", "test")
        with self.assertRaisesRegex(ValueError, "cross-split"):
            validate_cases([calibration, test])
        test["split"] = "calibration"
        validate_cases([calibration, test])
        with self.assertRaises(ValueError):
            corpus.make_case(row(), 0, "en", "synthetic-pack", "train")

    def test_one_sided_or_coordinated_input_and_option_mutation_rejected(self):
        mutations = []
        changed = case()
        changed["input"]["context"] += " alteration"
        mutations.append(changed)
        changed = case()
        changed["input"]["options"].reverse()
        changed["evaluation"]["oracle"]["base_input"] = deepcopy(changed["input"])
        mutations.append(changed)
        changed = case()
        changed["input"]["question"] = "Synthetic altered policy question"
        changed["evaluation"]["oracle"]["base_input"] = deepcopy(changed["input"])
        mutations.append(changed)
        for changed in mutations:
            with self.subTest(), self.assertRaises(ValueError):
                validate_cases([changed])

    def test_reference_policy_identity_and_provenance_mutations_rejected(self):
        paths = [(("reference", "assertions", 0, "value"), "a"),
                 (("reference", "abstention_allowed"), True),
                 (("evaluation", "oracle", "params", "policy_id"), "different-policy"),
                 (("evaluation", "oracle", "params", "cards_sha256"), "0" * 64),
                 (("evaluation", "oracle", "params", "reviewed_date"), "2026-11-09"),
                 (("evaluation", "oracle", "params", "decision"), "confirmed"),
                 (("evaluation", "oracle", "params", "label"), "instruction"),
                 (("scenario_id",), "different-family"),
                 (("case_id",), "cir2-00000-en"),
                 (("evaluation", "base_case_id"), "unrelated-dispatch"),
                 (("evaluation", "oracle", "choices", "a"), "search_query")]
        for path, replacement in paths:
            changed = case()
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = replacement
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_cases([changed])
        changed = case()
        changed["evaluation"]["oracle"]["params"]["unexpected"] = "metadata"
        with self.assertRaises(ValueError):
            corpus.validate_oracle(changed)

    def test_frozen_card_file_changes_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cards.json"
            path.write_bytes(corpus.CARDS_PATH.read_bytes() + b" ")
            with patch.object(corpus, "CARDS_PATH", path), self.assertRaises(ValueError):
                corpus.load_cards()
        first = corpus.load_cards()
        first["intents"][0]["id"] = "changed"
        self.assertEqual(corpus.load_cards()["intents"][0]["id"], "greeting")

    def test_scorer_rejects_empty_and_wrong_outputs_retains_failures(self):
        value = case()
        for output in (None, {}, {"choice_id": "a"}, {"choice_id": "unknown"}):
            with self.subTest(output=output):
                result = score_case(value, {"status": "ok", "output": output})
                self.assertFalse(result["passed"])
        result = score_case(value, {"status": "ok", "output": {"choice_id": "c"}})
        self.assertTrue(result["scored"])
        self.assertTrue(result["passed"])
        for status in ("missing", "error", "timeout", "unsupported", "abstain"):
            result = score_case(value, {"status": status, "output": None})
            self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
