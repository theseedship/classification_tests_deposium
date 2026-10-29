"""Offline controls for preparation, not actual human review or inference."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reference_review", ROOT / "scripts/reference_review.py")
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


class ReferenceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = review.validate_plan()
        cls.inputs, cls.blank, cls.references = review.packet(cls.plan)

    def test_fixed_counts_strata_and_pending_state(self):
        coverage = review.coverage(self.plan)
        self.assertEqual(coverage["selected_inputs"], 48)
        self.assertEqual(coverage["assessment_slots"], 368)
        self.assertEqual(coverage["by_dataset"], {"physics": 16, "passage": 32})
        self.assertEqual(coverage["families_by_dataset"], {"physics": 8, "passage": 8})
        self.assertEqual(coverage["language"], {"fr": 24, "en": 24})
        self.assertEqual(coverage["passage_view"], {"full": 16, "head_384": 16})
        self.assertEqual(coverage["authored_relevance_strata"], {"0": 38, "1": 56, "2": 8, "3": 26})
        self.assertEqual(coverage["authored_support_strata"], {"supports": 26, "refutes": 20, "insufficient": 146})
        self.assertEqual(coverage["authored_answerability_strata"], {
            "answerable": 22, "insufficient_visible_evidence": 6, "conflicting_visible_evidence": 4})
        self.assertEqual(coverage["human_judgments"], 0)
        self.assertFalse(self.plan["fresh_held_out"])
        self.assertEqual({c["review_status"] for c in self.plan["cases"]}, {"not_started"})

    def test_translations_views_and_original_splits_are_retained(self):
        data, _ = review.sources()
        for row in self.plan["cases"]:
            source = next(c for c in data[row["dataset"]] if c["case_id"] == row["case_id"])
            self.assertEqual(row["split"], source["split"])
        cases = self.plan["cases"]
        for family in {c["family_id"] for c in cases}:
            family_cases = [c for c in cases if c["family_id"] == family]
            self.assertEqual({c["language"] for c in family_cases}, {"fr", "en"})
            self.assertEqual(len({c["split"] for c in family_cases}), 1)
            if family_cases[0]["dataset"] == "passage":
                self.assertEqual(len(family_cases), 4)
                self.assertEqual({c["view"] for c in family_cases}, {"full", "head_384"})
        physics = [c for c in data["physics"] if c["case_id"] in {r["case_id"] for r in cases}]
        self.assertEqual({c["evaluation"]["difficulty"] for c in physics}, {"D1", "D2", "D3"})

    def test_selection_ignores_data_order_and_unapproved_model_fields(self):
        data, hashes = review.sources()
        for rows in data.values():
            rows.reverse()
            for row in rows:
                row["model_prediction"] = "NEVER_EXPORT_THIS_VALUE"
                row["raw_output"] = "NEVER_EXPORT_THIS_VALUE"
        with patch.object(review, "sources", return_value=(data, hashes)):
            self.assertEqual(review.build_plan(), self.plan)
            inputs, _, _ = review.packet(self.plan)
        self.assertNotIn("NEVER_EXPORT_THIS_VALUE", review.jsonl(inputs))

    def test_reviewer_packet_is_allowlisted_and_separate_from_references(self):
        serialized = review.jsonl(self.inputs)
        for row in self.inputs:
            allowed = {"review_id", "task", "language", "view"}
            allowed |= {"input"} if row["task"] == "physics" else {"query", "passages", "claims"}
            self.assertEqual(set(row), allowed)
            if row["task"] == "passage":
                self.assertTrue(all(set(p) == {"id", "text"} for p in row["passages"]))
                self.assertTrue(all(set(c) == {"id", "text"} for c in row["claims"]))
        for selected in self.plan["cases"]:
            self.assertNotIn(selected["case_id"], serialized)
            self.assertNotIn(selected["family_id"], serialized)
        for key in ("authored_reference", "annotations", "reference", "split", "rationale",
                    "spans", "model_prediction", "raw_output", "oracle"):
            self.assertNotIn(f'"{key}"', serialized)
        self.assertTrue(all(r["reference_method"] == "agent_authored_pending_human" for r in self.references))

    def test_manifest_source_hash_or_roster_change_is_rejected(self):
        altered = copy.deepcopy(self.plan)
        altered["source_sha256"][next(iter(altered["source_sha256"]))] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(review.encode(altered))
            with self.assertRaises(review.ReviewError):
                review.validate_plan(path)
            altered = copy.deepcopy(self.plan)
            altered["cases"].pop()
            path.write_text(review.encode(altered))
            with self.assertRaises(review.ReviewError):
                review.validate_plan(path)

    def test_empty_and_blank_forms_never_complete_review(self):
        for rows in ([], self.blank):
            report = review.audit(self.plan, rows)
            self.assertEqual(report["review_status"], "not_started")
            self.assertEqual(report["human_declared_judgments"], 0)
            self.assertEqual(report["pending_judgments"], 368)
        report = review.audit(self.plan, [])
        self.assertEqual(report["missing_rows"], 368)

    def declared_row(self, row=None):
        # Test fixture only: these declarations are NOT actual human judgments.
        result = copy.deepcopy(row or self.blank[0])
        result.update(status="completed", actor_type="human", reviewer_alias="reviewer-T01",
                      judgment="a", explanation="Test-only declared explanation.",
                      wording_status="acceptable", prior_exposure="unknown")
        return result

    def test_partial_forms_are_in_progress_and_disagreement_can_be_recorded(self):
        row = self.declared_row()
        expected = self.references[0]["judgments"][0]["authored_reference"]
        row["judgment"] = next(v for v in ("a", "b", "c", "d") if v != expected)
        report = review.audit(self.plan, [row])
        self.assertEqual(report["review_status"], "in_progress")
        self.assertEqual(report["human_declared_judgments"], 1)
        self.assertEqual(report["pending_judgments"], 367)
        self.assertEqual(report["reference_approval"], "not_implied_by_assessment_completion")

    def test_complete_declarations_validate_but_do_not_approve_references(self):
        # Artificial test fixtures, never exported as real review findings.
        expected = {j["judgment_id"]: j for r in self.references for j in r["judgments"]}
        rows = []
        for blank in self.blank:
            row = self.declared_row(blank)
            reference = expected[row["judgment_id"]]
            row["judgment"] = reference["authored_reference"]
            if ".support." in row["judgment_id"] and row["judgment"] in ("supports", "refutes"):
                row["evidence_quotes"] = [reference["evidence_text"]]
            rows.append(row)
        report = review.audit(self.plan, rows)
        self.assertEqual(report["review_status"], "completed")
        self.assertEqual(report["human_declared_judgments"], 368)
        self.assertEqual(report["missing_rows"], 0)
        self.assertEqual(report["reference_approval"], "not_implied_by_assessment_completion")
        self.assertEqual(self.plan["human_judgments"], 0)

    def test_empty_completed_agent_fake_quote_or_invalid_label_rejected(self):
        malformed = copy.deepcopy(self.blank[0])
        malformed["status"] = "completed"
        invalid = [malformed]
        for key, value in (("actor_type", "agent"), ("explanation", ""),
                           ("reviewer_alias", "person@example.invalid"), ("judgment", True),
                           ("prior_exposure", None), ("wording_status", None)):
            row = self.declared_row()
            row[key] = value
            invalid.append(row)
        pending_with_answer = copy.deepcopy(self.blank[0])
        pending_with_answer["judgment"] = "a"
        invalid.append(pending_with_answer)
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(review.ReviewError):
                review.audit(self.plan, [row])
        support_blank = next(row for row in self.blank if ".support." in row["judgment_id"])
        row = self.declared_row(support_blank)
        row["judgment"] = "supports"
        with self.assertRaises(review.ReviewError):
            review.audit(self.plan, [row])
        row["evidence_quotes"] = ["invented quotation absent from this passage"]
        with self.assertRaises(review.ReviewError):
            review.audit(self.plan, [row])

    def test_duplicate_or_unknown_rows_rejected(self):
        with self.assertRaises(review.ReviewError):
            review.audit(self.plan, [self.blank[0], self.blank[0]])
        unknown = copy.deepcopy(self.blank[0])
        unknown["judgment_id"] = "V999.choice"
        with self.assertRaises(review.ReviewError):
            review.audit(self.plan, [unknown])

    def test_export_is_ignored_blanks_stay_pending_and_overwrite_refused(self):
        results = ROOT / "results"
        results.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=results) as directory:
            output = Path(directory) / "packet"
            review.export_packet(self.plan, output)
            self.assertEqual(review.read_rows(output / "reviewer/inputs.jsonl"), self.inputs)
            self.assertEqual(review.read_rows(output / "reviewer/assessments.jsonl"), self.blank)
            self.assertEqual(len(review.read_rows(output / "coordinator/authored-references.jsonl")), 48)
            ignored = subprocess.run(["git", "check-ignore", str(output)], cwd=ROOT, capture_output=True)
            self.assertEqual(ignored.returncode, 0)
            command = [sys.executable, "-B", str(ROOT / "scripts/reference_review.py"), "audit",
                       "--assessments", str(output / "reviewer/assessments.jsonl")]
            audited = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(audited.returncode, 1, audited.stderr)
            self.assertEqual(json.loads(audited.stdout)["human_declared_judgments"], 0)
            with self.assertRaises(review.ReviewError):
                review.export_packet(self.plan, output)
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(review.ReviewError):
                review.export_packet(self.plan, Path(outside) / "packet")


if __name__ == "__main__":
    unittest.main()
