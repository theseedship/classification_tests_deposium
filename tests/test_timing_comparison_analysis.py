"""Offline, sealed-fixture tests for the historical timing aggregator."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import campaigns
from deposium_bench.cases import load_cases
from deposium_bench.timing import benchmark_timing

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("analyze_timing_comparison",
                                              ROOT / "scripts/analyze-timing-comparison.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class TimingComparisonAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        cases, _ = load_cases(ROOT / "datasets/document-task-v1/cases.jsonl")
        self.cases = cases[:2]
        self.dataset = self.root / "cases.jsonl"
        self.dataset.write_bytes(b"".join(campaigns._encode(case) for case in self.cases))
        profile = json.loads((ROOT / "profiles/fixture-control.json").read_bytes())
        profile.update(profile_id="offline-control", recordings=str(ROOT / "fixtures/control-responses.jsonl"))
        self.profile = self.root / "profile.json"
        self.profile.write_bytes(campaigns._encode(profile))
        self.archive = self.root / "timing"
        benchmark_timing(self.dataset, [self.profile], self.archive, launches=2, warmup=1, passes=2)

    def test_recomputes_scored_passes_and_writes_only_aggregates(self):
        output = self.root / "analysis"
        result = analysis.analyze([("fixture", self.archive)], output)
        item = result["groups"]["task"][0]
        candidate = item["candidates"]["offline-control"]
        self.assertEqual(candidate["phases"]["cold"]["calls"], 2)
        self.assertEqual(candidate["phases"]["warmup"]["calls"], 2)
        self.assertEqual(candidate["phases"]["measured"]["calls"], 8)
        self.assertEqual(len(candidate["per_pass"]), 4)
        self.assertEqual(candidate["repeated_quality"]["independent_cases"], 2)
        self.assertEqual(analysis.render(result).encode(), (output / "report.md").read_bytes())
        self.assertEqual(campaigns._encode(result), (output / "analysis.json").read_bytes())
        self.assertEqual(analysis.render(json.loads((output / "analysis.json").read_bytes())).encode(),
                         (output / "report.md").read_bytes())
        published = (output / "analysis.json").read_bytes() + (output / "report.md").read_bytes()
        for case in self.cases:
            self.assertNotIn(case["case_id"].encode(), published)
        self.assertNotIn(b"reference", published)
        self.assertNotIn(b"recordings", published)
        with self.assertRaises(FileExistsError):
            analysis.analyze([("fixture", self.archive)], output)

    def test_rejects_seal_mutation(self):
        with (self.archive / "trials.jsonl").open("ab") as stream:
            stream.write(b"{}\n")
        with self.assertRaisesRegex(analysis.AnalysisError, "seal_mismatch"):
            analysis.analyze_one("fixture", self.archive)

    def test_rejects_unsealed_symlink_inventory(self):
        (self.archive / "external").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(analysis.AnalysisError, "inventory_invalid"):
            analysis.analyze_one("fixture", self.archive)

    def test_rejects_validly_resealed_trial_order_and_score_summary(self):
        trials_path = self.archive / "trials.jsonl"
        trials = trials_path.read_bytes().splitlines(keepends=True)
        trials[0], trials[1] = trials[1], trials[0]
        trials_path.write_bytes(b"".join(trials))
        self._reseal("trials.jsonl")
        summary_path = self.archive / "summary.json"
        summary = json.loads(summary_path.read_bytes())
        summary["trials_sha256"] = campaigns._hash(trials_path.read_bytes())
        summary_path.write_bytes(campaigns._encode(summary))
        self._reseal("summary.json")
        with self.assertRaisesRegex(analysis.AnalysisError, "trial_protocol_mismatch"):
            analysis.analyze_one("fixture", self.archive)

    def test_rejects_resealed_wrong_request_hash_with_unchanged_statistics(self):
        trials_path = self.archive / "trials.jsonl"
        trials = [json.loads(line) for line in trials_path.read_bytes().splitlines()]
        trials[0]["result"]["request_sha256"] = "0" * 64
        trials_path.write_bytes(b"".join(campaigns._encode(trial) for trial in trials))
        self._reseal("trials.jsonl")
        summary_path = self.archive / "summary.json"
        summary = json.loads(summary_path.read_bytes())
        summary["trials_sha256"] = campaigns._hash(trials_path.read_bytes())
        summary_path.write_bytes(campaigns._encode(summary))
        self._reseal("summary.json")
        with self.assertRaisesRegex(analysis.AnalysisError, "trial_result_contract_mismatch"):
            analysis.analyze_one("fixture", self.archive)

    def test_rejects_resealed_scorer_mismatch(self):
        manifest_path = self.archive / "timing-manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["scorer"]["sha256"] = "0" * 64
        manifest_path.write_bytes(campaigns._encode(manifest))
        self._reseal("timing-manifest.json")
        with self.assertRaisesRegex(analysis.AnalysisError, "timing_manifest_summary_mismatch"):
            analysis.analyze_one("fixture", self.archive)

    def test_rejects_resealed_protocol_budget_before_expanding_trials(self):
        manifest_path = self.archive / "timing-manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["protocol"]["total_planned_calls"] = 100_001
        manifest_path.write_bytes(campaigns._encode(manifest))
        self._reseal("timing-manifest.json")
        with self.assertRaisesRegex(analysis.AnalysisError, "protocol_invalid"):
            analysis.analyze_one("fixture", self.archive)

    def test_rejects_resealed_wrong_summary(self):
        summary_path = self.archive / "summary.json"
        summary = json.loads(summary_path.read_bytes())
        summary["candidates"]["offline-control"]["per_pass_quality"][0]["metrics"]["passed_cases"] += 1
        summary_path.write_bytes(campaigns._encode(summary))
        self._reseal("summary.json")
        with self.assertRaisesRegex(analysis.AnalysisError, "summary_recalculation_mismatch"):
            analysis.analyze_one("fixture", self.archive)

    def test_rejects_duplicate_labels_and_output_inside_input(self):
        with self.assertRaisesRegex(analysis.AnalysisError, "timing_labels_invalid"):
            analysis.analyze([("same", self.archive), ("same", self.archive)], self.root / "out")
        with self.assertRaisesRegex(analysis.AnalysisError, "output_inside_input"):
            analysis.analyze([("fixture", self.archive)], self.archive / "derived")

    def test_rejects_seal_changed_after_read_before_output(self):
        original = analysis.analyze_one
        def changing(label, archive):
            result = original(label, archive)
            with (archive / "seal.json").open("ab") as stream:
                stream.write(b" ")
            return result
        output = self.root / "analysis"
        with patch.object(analysis, "analyze_one", side_effect=changing):
            with self.assertRaisesRegex(analysis.AnalysisError, "input_seal_changed"):
                analysis.analyze([("fixture", self.archive)], output)
        self.assertFalse(output.exists())

    def _reseal(self, name):
        seal_path = self.archive / "seal.json"
        seal = json.loads(seal_path.read_bytes())
        seal["files"][name] = campaigns._hash((self.archive / name).read_bytes())
        seal["sha256"] = campaigns._hash(campaigns._encode(seal["files"]))
        seal_path.write_bytes(campaigns._encode(seal))


if __name__ == "__main__":
    unittest.main()
