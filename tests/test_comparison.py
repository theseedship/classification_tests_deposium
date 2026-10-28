"""Comparison contracts use validated recorded archives without model inference."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import campaigns
from deposium_bench.cases import DEFAULT_DATASET
from deposium_bench.comparison import compare_campaigns

ROOT = Path(__file__).resolve().parents[1]


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.baseline = self.root / "baseline"
        self.candidate = self.root / "candidate"
        for path in (self.baseline, self.candidate):
            campaigns.run_campaign(DEFAULT_DATASET, ROOT / "profiles/fixture-control.json", path)
        self.original_archive = campaigns._archive

    def loader(self, path):
        # These are test metadata roles around genuine validated control bytes,
        # not claimed model/component runs. All output/scoring data are genuine.
        archive = list(self.original_archive(path))
        archive[1] = deepcopy(archive[1])
        if Path(path) == self.baseline:
            archive[1].update(qualification="component_replay", proof_level="A")
        else:
            archive[1].update(qualification="model_isolated", proof_level="A")
        archive[1]["input_protocol"] = "current_equivalent"
        return tuple(archive)

    def compare(self, loader=None, output=None):
        with patch.object(campaigns, "_archive", side_effect=loader or self.loader), \
                patch.object(campaigns, "create_adapter", side_effect=AssertionError("no inference")), \
                patch.object(campaigns, "build_preflight", side_effect=AssertionError("no live stack")):
            return compare_campaigns(self.baseline, self.candidate, output or self.root / "comparison")

    def test_complete_comparison_retains_failures_statuses_and_denominators(self):
        before = snapshot(self.baseline), snapshot(self.candidate)
        summary = self.compare()
        self.assertEqual(summary["counts"]["total_cases"], 36)
        self.assertEqual(len(summary["rows"]), 36)
        self.assertGreater(summary["counts"]["outcomes"]["both_fail"], 0)
        self.assertGreater(summary["counts"]["outcomes"]["unpaired"], 0)
        self.assertEqual(summary["counts"]["outcomes"]["improved"], 0)
        self.assertEqual(summary["counts"]["outcomes"]["regressed"], 0)
        self.assertTrue(all(n > 0 for n in summary["candidate_metrics"]["counts_by_status"].values()))
        self.assertEqual(sum(g["total_cases"] for g in summary["groups"]["split"].values()), 36)
        self.assertEqual(sum(g["total_cases"] for g in summary["groups"]["language"].values()), 36)
        self.assertFalse(summary["timings"]["baseline"]["cross_candidate_comparable"])
        self.assertEqual(json.loads((self.root / "comparison/comparison.json").read_bytes()), summary)
        self.assertEqual(before, (snapshot(self.baseline), snapshot(self.candidate)))

    def test_mismatched_dataset_ids_scorer_protocol_or_proof_refused_before_write(self):
        changes = [("dataset_sha256", "0" * 64), ("case_ids", ["wrong"]),
                   ("scorer", {"sha256": "wrong"}), ("input_protocol", "extended"),
                   ("qualification", "harness_control"), ("proof_level", "model_isolated")]
        for field, value in changes:
            with self.subTest(field=field):
                def loader(path):
                    archive = list(self.loader(path))
                    if Path(path) == self.candidate:
                        archive[1][field] = value
                    return tuple(archive)
                output = self.root / f"reject-{field}"
                with self.assertRaises(campaigns.CampaignError):
                    self.compare(loader, output)
                self.assertFalse(output.exists())

    def test_same_obsolete_scorer_requires_explicit_rescore(self):
        def loader(path):
            archive = list(self.loader(path))
            archive[1]["scorer"]["sha256"] = "0" * 64
            return tuple(archive)
        with self.assertRaisesRegex(campaigns.CampaignError, "rescore"):
            self.compare(loader)

    def test_model_model_comparison_reports_successful_common_subset(self):
        def loader(path):
            archive = list(self.loader(path))
            archive[1].update(qualification="model_isolated", proof_level="A")
            return tuple(archive)
        summary = self.compare(loader)
        counts = summary["counts"]
        common = [row for row in summary["rows"]
                  if all(row[side]["status"] == "ok" and row[side]["scored"]
                         for side in ("baseline", "candidate"))]
        self.assertEqual(summary["comparison_kind"], "model_vs_model")
        self.assertEqual(counts["common_ok_cases"], len(common))
        self.assertGreater(len(common), 0)
        self.assertLess(len(common), counts["paired_scored_cases"])
        self.assertEqual(sum(counts["common_ok_outcomes"].values()), len(common))
        for side in ("baseline", "candidate"):
            detail = counts["accuracy"][side]
            correct = sum(row[side]["passed"] for row in common)
            self.assertEqual(detail["all"], 36)
            self.assertEqual(detail["common_ok_correct"], correct)
            self.assertEqual(detail["common_ok_accuracy"], correct / len(common))
            self.assertEqual(detail["accuracy_scored"], detail["correct"] / detail["scored"])
            self.assertEqual(detail["accuracy_all"], detail["correct"] / 36)

    def test_unsealed_archive_and_unqualified_left_model_refused(self):
        for field in ("sealed", "proof_level"):
            def loader(path):
                archive = list(self.loader(path))
                if Path(path) == self.baseline:
                    if field == "sealed":
                        archive[4] = {**archive[4], "sealed": False}
                    else:
                        archive[1].update(qualification="model_isolated", proof_level="harness_control")
                return tuple(archive)
            with self.subTest(field=field), self.assertRaises(campaigns.CampaignError):
                self.compare(loader)
            self.assertFalse((self.root / "comparison").exists())

    def test_research_domain_and_difficulty_groups_include_all_unscored_cases(self):
        for path in (self.root / "research-left", self.root / "research-right"):
            campaigns.run_campaign(ROOT / "datasets/context-choice-v1/cases.jsonl",
                                   ROOT / "profiles/fixture-control.json", path, max_new_cases=0)
        self.baseline, self.candidate = self.root / "research-left", self.root / "research-right"
        def loader(path):
            archive = list(self.loader(path))
            archive[1].update(qualification="model_isolated", proof_level="A", input_protocol="context_choice")
            return tuple(archive)
        summary = self.compare(loader)
        self.assertEqual({key: value["total_cases"] for key, value in summary["groups"]["domain"].items()},
                         {"documentary": 76, "mathematics": 28, "chemistry": 28})
        self.assertEqual({key: value["total_cases"] for key, value in summary["groups"]["difficulty"].items()},
                         {"D1": 40, "D2": 40, "D3": 52})
        self.assertEqual(summary["counts"]["common_ok_cases"], 0)
        for side in ("baseline", "candidate"):
            self.assertEqual(summary["counts"]["accuracy"][side]["all"], 132)
            self.assertIsNone(summary["counts"]["accuracy"][side]["accuracy_scored"])
            self.assertIsNone(summary["counts"]["accuracy"][side]["common_ok_accuracy"])

    def test_incomplete_candidate_missing_and_zero_pairs_are_visible(self):
        sparse = self.root / "sparse"
        campaigns.run_campaign(DEFAULT_DATASET, ROOT / "profiles/fixture-control.json", sparse, max_new_cases=0)
        sparse_archive = self.original_archive(sparse)
        def loader(path):
            archive = list(self.loader(path))
            if Path(path) == self.candidate:
                archive[3] = sparse_archive[3]
                archive[4] = sparse_archive[4]
                archive[5] = sparse_archive[5]
            return tuple(archive)
        summary = self.compare(loader)
        self.assertEqual(summary["comparison_status"], "no_paired_scores")
        self.assertEqual(summary["counts"]["paired_scored_cases"], 0)
        self.assertEqual(summary["candidate_metrics"]["counts_by_status"]["missing"], 36)
        self.assertEqual(summary["candidate_metrics"]["verdict"], "invalid")
        self.assertEqual(summary["counts"]["outcomes"]["unpaired"], 36)

    def test_paired_transitions_are_classified_without_dropping_others(self):
        def loader(path):
            archive = list(self.loader(path))
            if Path(path) == self.candidate:
                archive[3] = deepcopy(archive[3])
                metrics = campaigns.summarize(archive[2], archive[3])
                passing = next(row["case_id"] for row in metrics["rows"] if row["passed"] and row["status"] == "ok")
                failing = "doc-compound-fr"
                for record in archive[3]:
                    if record["case_id"] == passing:
                        record["output"] = {}
                    if record["case_id"] == failing:
                        record["output"] = {"schema_version": "chat-document-request/v1",
                                            "task": "stored_summaries", "source": "documents",
                                            "coverage": "all", "format": "text", "count_only": False,
                                            "basis": "explicit", "include_connector_count": True}
            return tuple(archive)
        summary = self.compare(loader)
        self.assertEqual(summary["counts"]["outcomes"]["improved"], 1)
        self.assertEqual(summary["counts"]["outcomes"]["regressed"], 1)
        self.assertEqual(sum(summary["counts"]["outcomes"].values()), 36)

    def test_output_cannot_overwrite_sources_or_write_into_stack(self):
        before = snapshot(self.baseline), snapshot(self.candidate)
        for destination in (self.baseline, self.baseline / "child", self.candidate / "child"):
            with self.subTest(destination=destination), self.assertRaises(campaigns.CampaignError):
                self.compare(output=destination)
        self.compare()
        with self.assertRaises(FileExistsError):
            self.compare()
        def loader(path):
            archive = list(self.loader(path))
            archive[1]["stack_root"] = str(self.root / "stack")
            return tuple(archive)
        with self.assertRaises(campaigns.CampaignError):
            self.compare(loader, self.root / "stack/output")
        self.assertEqual(before, (snapshot(self.baseline), snapshot(self.candidate)))

    def test_uses_validated_snapshot_hashes_after_parent_changes(self):
        saved = self.original_archive(self.candidate)
        def loader(path):
            archive = self.loader(path)
            if Path(path) == self.candidate:
                (self.candidate / "raw.jsonl").write_bytes(b"concurrent replacement")
            return archive
        summary = self.compare(loader)
        self.assertEqual(summary["candidate_archive"]["raw_sha256"], saved[4]["raw_sha256"])
        self.assertEqual(summary["candidate_metrics"], campaigns.summarize(saved[2], saved[3]))


if __name__ == "__main__":
    unittest.main()
