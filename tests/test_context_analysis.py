"""Archived context reports preserve denominators and never fit a fallback threshold."""
import csv
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import campaigns
from deposium_bench.cases import DEFAULT_DATASET
from deposium_bench.context_analysis import _counts, _measurements, _stats, analyze_context

ROOT = Path(__file__).resolve().parents[1]


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


class ContextAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "run"
        campaigns.run_campaign(DEFAULT_DATASET, ROOT / "profiles/fixture-control.json", self.archive)

    def analyze(self, name="analysis"):
        with patch.object(campaigns, "create_adapter", side_effect=AssertionError("no inference")), \
                patch.object(campaigns, "build_preflight", side_effect=AssertionError("no stack")):
            return analyze_context(self.archive, self.root / name)

    def test_report_retains_all_states_and_denominators_without_threshold(self):
        before = snapshot(self.archive)
        summary = self.analyze()
        self.assertEqual(summary["counts"]["total_cases"], 36)
        self.assertEqual(len(summary["rows"]), 36)
        self.assertTrue(all(value > 0 for value in summary["counts"]["counts_by_status"].values()))
        self.assertEqual(summary["groups"]["target"]["base"]["total_cases"], 36)
        self.assertEqual(sum(cell["total_cases"] for cell in summary["cells"]), 36)
        self.assertLess(summary["counts"]["scored_cases"], 36)
        self.assertIsNone(summary["fallback_threshold"]["value"])
        self.assertEqual(summary["fallback_threshold"]["status"], "not_qualified")
        self.assertEqual(summary["counts"]["latency"]["adapter_duration_ms"]["count"], 36)
        self.assertEqual(summary["counts"]["latency"]["decision_ms"]["count"], 0)
        self.assertIsNone(summary["counts"]["latency"]["decision_ms"]["median"])
        self.assertEqual(snapshot(self.archive), before)
        self.assertEqual(json.loads((self.root / "analysis/analysis.json").read_bytes()), summary)
        rows = list(csv.DictReader(io.StringIO((self.root / "analysis/rows.csv").read_text())))
        self.assertEqual(len(rows), 36)
        self.assertEqual({row["status"] for row in rows}, set(summary["counts"]["counts_by_status"]))
        self.assertTrue((self.root / "analysis/report.md").read_text().startswith("# Context analysis"))

    def test_nearest_rank_percentile_and_arithmetic_median_are_explicit(self):
        value = _stats([4, 2, 1, 3, None, True, -1, "invalid"])
        self.assertEqual(value["count"], 4)
        self.assertEqual(value["median"], 2.5)
        self.assertEqual(value["p95"], 4)
        self.assertEqual(_stats([])["count"], 0)
        self.assertIsNone(_stats([])["median"])

    def test_worker_measurements_keep_native_reference_and_engine_boundaries_separate(self):
        julia = {"duration_ms": 12, "raw_output": {"decision_ms": 9, "inference_ms": 8,
                                                  "rss_mb": 123, "encoding_info": {"tokens": 103,
                                                      "stateTruncated": False, "optionsTruncated": False},
                                                  "token_components": {"padded": 104}}}
        measured = _measurements(julia)
        self.assertEqual(measured["adapter_duration_ms"], 12)
        self.assertEqual(measured["decision_ms"], 9)
        self.assertEqual(measured["inference_ms"], 8)
        self.assertEqual(measured["native_tokens"], 103)
        self.assertEqual(measured["native_padded_tokens"], 104)
        gliner = _measurements({"duration_ms": 5, "raw_output": {
            "encoding_info": {"tokens": 105}, "token_components": {"padded_tokens": 105},
            "forward_executed": False, "inference_ms": None}})
        self.assertEqual(gliner["native_padded_tokens"], 105)
        self.assertFalse(gliner["forward_executed"])
        resident = _measurements({"duration_ms": 5, "raw_output": {"decision": {}, "timings": {"decision_ms": 1}}})
        self.assertEqual(resident["decision_ms"], 1)
        self.assertIsNone(resident["inference_ms"])
        overflow = _measurements({"duration_ms": 6, "raw_output": {"decision_ms": 2,
                                                     "inference_ms": None, "forward_executed": False}})
        self.assertFalse(overflow["forward_executed"])
        self.assertIsNone(overflow["inference_ms"])

    def test_native_usage_truncation_accepts_only_bool_and_extracts_nested_legacy_declarations(self):
        for flag in (True, False, None, 0, 1, "false", "true", [], {}):
            record = {"duration_ms": 5, "raw_output": {"native_result": {"usage": {"truncated": flag}}}}
            with self.subTest(flag=flag):
                measurement = _measurements(record)
                self.assertIs(measurement["native_usage_truncated"], flag if type(flag) is bool else None)
                self.assertIsNone(measurement["forward_executed"])
        for raw in ({}, {"native_result": {}}, {"native_result": {"usage": {}}},
                    {"native_result": {"usage": None}}, {"native_usage_truncated": None}):
            self.assertIsNone(_measurements({"duration_ms": 1, "raw_output": raw})["native_usage_truncated"])
        for flag in (True, False):
            self.assertIs(_measurements({"duration_ms": 1, "raw_output": {
                "native_usage_truncated": flag}})["native_usage_truncated"], flag)

    def test_truncation_counts_keep_false_unknown_cached_and_unrecorded_in_full_denominator(self):
        template = self.analyze()["rows"][0]
        raw_outputs = [
            {"native_usage_truncated": True, "native_result": {"usage": {"truncated": True}}},
            {"native_result": {"usage": {"truncated": False}}},
            {"native_usage_truncated": None, "native_result": {"usage": {"truncated": True}}},
            {}, {"native_result": {"usage": {"truncated": 0}}},
            {"cached_failure": True, "http_attempted": False, "native_usage_truncated": None},
            None,
        ]
        rows = []
        for index, raw in enumerate(raw_outputs):
            row = deepcopy(template)
            row.update(case_id=f"synthetic-truncation-{index}", recorded=raw is not None,
                       status="missing" if raw is None else "error", scored=False, passed=False,
                       measurements=_measurements({"duration_ms": 1, "raw_output": raw} if raw is not None else None))
            rows.append(row)
        counts = _counts(rows)
        self.assertEqual(counts["total_cases"], 7)
        self.assertEqual(counts["recorded_cases"], 6)
        self.assertEqual(counts["counts_by_status"]["missing"], 1)
        self.assertEqual(counts["truncation_observations"], {"state_truncated": 0, "options_truncated": 0})
        self.assertEqual(counts["truncation_observation_counts"]["native_usage_truncated"],
                         {"true": 2, "false": 1, "unknown": 4})
        for observations in counts["truncation_observation_counts"].values():
            self.assertEqual(sum(observations.values()), counts["total_cases"])

    def test_zero_scored_and_incomplete_archive_stay_invalid_and_missing(self):
        zero = self.root / "zero"
        campaigns.run_campaign(DEFAULT_DATASET, ROOT / "profiles/fixture-control.json", zero, max_new_cases=0)
        summary = analyze_context(zero, self.root / "zero-analysis")
        self.assertEqual(summary["analysis_status"], "no_scored_cases")
        self.assertEqual(summary["counts"]["counts_by_status"]["missing"], 36)
        self.assertEqual(summary["counts"]["latency"]["adapter_duration_ms"]["count"], 0)
        self.assertIsNone(summary["counts"]["accuracy_scored"])

    def test_research_pack_identity_survives_zero_scored_analysis_and_csv_export(self):
        profile = json.loads((ROOT / "profiles/fixture-control.json").read_bytes())
        profile.update(capabilities=["bench.context-choice"],
                       recordings=str(ROOT / "fixtures/control-responses.jsonl"))
        profile_path = self.root / "research-profile.json"
        profile_path.write_bytes(campaigns._encode(profile))
        for pack, total, families, test_total in (
                ("context-choice-v1", 132, 66, 66),
                ("capability-choice-v1", 192, 48, 96),
                ("physics-choice-v1", 48, 24, 36)):
            with self.subTest(pack=pack):
                archive = self.root / (pack + "-run")
                campaigns.run_campaign(ROOT / "datasets" / pack / "cases.jsonl",
                                       profile_path, archive, max_new_cases=0)
                before = snapshot(archive)
                output = self.root / (pack + "-analysis")
                with patch.object(campaigns, "create_adapter", side_effect=AssertionError("no inference")):
                    summary = analyze_context(archive, output)
                self.assertEqual(set(summary["groups"]["benchmark_pack"]), {pack})
                counts = summary["groups"]["benchmark_pack"][pack]
                self.assertEqual(counts["total_cases"], total)
                self.assertEqual(counts["independent_families"], families)
                self.assertEqual(counts["counts_by_split"]["test"]["total_cases"], test_total)
                self.assertEqual(counts["counts_by_status"]["missing"], total)
                self.assertEqual(counts["scored_cases"], 0)
                self.assertIsNone(counts["accuracy_scored"])
                self.assertEqual(summary["analysis_status"], "no_scored_cases")
                rows = list(csv.DictReader(io.StringIO((output / "rows.csv").read_text())))
                self.assertEqual({row["benchmark_pack"] for row in rows}, {pack})
                self.assertEqual(len(rows), total)
                self.assertEqual(snapshot(archive), before)

    def test_modified_unsealed_or_obsolete_archive_is_rejected(self):
        original_scorer = campaigns._scorer_fingerprint()
        with patch.object(campaigns, "_scorer_fingerprint", return_value={**original_scorer, "sha256": "0" * 64}):
            with self.assertRaisesRegex(campaigns.CampaignError, "rescore"):
                self.analyze("obsolete")
        self.assertFalse((self.root / "obsolete").exists())
        for name in ("raw.jsonl", "seal.json"):
            data = (self.archive / name).read_bytes()
            altered = campaigns._encode({**json.loads(data), "sha256": "0" * 64}) if name == "seal.json" else data + b" "
            (self.archive / name).write_bytes(altered)
            with self.assertRaises(campaigns.CampaignError):
                self.analyze(f"bad-{name}")
            (self.archive / name).write_bytes(data)
        for name in ("seal.json", "summary.json", "report.md"):
            (self.archive / name).unlink()
        with self.assertRaisesRegex(campaigns.CampaignError, "sealed"):
            self.analyze("unsealed")
        self.assertFalse((self.root / "unsealed").exists())

    def test_destinations_cannot_overwrite_archive_or_application_stack(self):
        before = snapshot(self.archive)
        with self.assertRaises(campaigns.CampaignError):
            analyze_context(self.archive, self.archive / "child")
        self.analyze()
        with self.assertRaises(FileExistsError):
            self.analyze()
        loader = campaigns._archive
        def with_stack(path):
            archive = list(loader(path))
            archive[1] = {**archive[1], "stack_root": str(self.root / "stack")}
            return tuple(archive)
        with patch.object(campaigns, "_archive", side_effect=with_stack), self.assertRaises(campaigns.CampaignError):
            analyze_context(self.archive, self.root / "stack/output")
        self.assertEqual(snapshot(self.archive), before)

    def test_uses_validated_byte_snapshots_after_source_changes(self):
        loader = campaigns._archive
        validated = loader(self.archive)
        def change_parent(path):
            archive = loader(path)
            (Path(path) / "raw.jsonl").write_bytes(b"concurrent replacement")
            return archive
        with patch.object(campaigns, "_archive", side_effect=change_parent):
            summary = self.analyze()
        self.assertEqual(summary["source_archive"]["raw_sha256"], validated[4]["raw_sha256"])
        self.assertEqual(summary["counts"]["passed_cases"], campaigns.summarize(validated[2], validated[3])["passed_cases"])

    def test_equal_family_variants_do_not_multiply_independence(self):
        summary = self.analyze()
        one = deepcopy(summary["rows"][0])
        two = deepcopy(one)
        two["case_id"] = "variant"
        two["target"] = "1000"
        one["status"] = "unsupported"
        one["failure_kind"] = "target_unattainable"
        one["scored"] = one["passed"] = one["supported"] = False
        two["status"] = "error"
        two["failure_kind"] = "typed_overflow"
        two["scored"] = two["passed"] = False
        two["supported"] = True
        counts = _counts([one, two])
        self.assertEqual(counts["independent_families"], 1)
        self.assertEqual(counts["total_cases"], 2)
        self.assertEqual(counts["unsupported_target_unattainable"], 1)
        self.assertEqual(counts["typed_overflow_errors"], 1)
        self.assertEqual(counts["supported_cases"], 1)
        self.assertEqual(counts["accuracy_supported"], 0)
        two["status"] = "unsupported"
        counts = _counts([one, two])
        self.assertEqual(counts["typed_overflow_errors"], 0)
        self.assertEqual(counts["typed_native_overflows"], 1)

    def test_v2_base_and_length_cells_keep_unattainable_overflow_and_missing_separate(self):
        from deposium_bench.research_corpus import build_cases
        from deposium_bench.lengths import make_variant
        class WordCounter:
            provenance = {"sha256": "a" * 64, "revision": "b" * 40}
            def measure(self, value):
                content = len(value["context"].split())
                head = len(value["question"].split()) + sum(len(option["description"].split()) for option in value["options"]) + 8
                actual = content + head
                return {"content_tokens": content, "head_tokens": head, "actual_tokens": actual,
                        "padded_tokens": (actual + 7) // 8 * 8}
        base = build_cases()[0]
        cases = [base]
        for target in (1, 500, 1000, 2000):
            cases.append(make_variant(base, target, "middle", "original", WordCounter()))
        dataset = self.root / "v2.jsonl"
        dataset.write_bytes(b"".join(campaigns._encode(case) for case in cases))
        correct = base["reference"]["assertions"][0]["value"]
        wrong = next(option["id"] for option in base["input"]["options"] if option["id"] != correct)
        records = [{"case_id": base["case_id"], "status": "ok", "output": {"choice_id": correct},
                    "error": None, "raw_output": {"decision_ms": 2, "inference_ms": 1}},
                   {"case_id": cases[2]["case_id"], "status": "ok", "output": {"choice_id": wrong},
                    "error": None, "raw_output": {"decision_ms": 4, "inference_ms": 3,
                                                  "encoding_info": {"tokens": 490}, "rss_mb": 321}},
                   {"case_id": cases[3]["case_id"], "status": "error", "output": None,
                    "error": "julia_context_overflow", "raw_output": {"decision_ms": .5,
                                                                "inference_ms": None, "forward_executed": False}}]
        recordings = self.root / "v2-recordings.jsonl"
        recordings.write_bytes(b"".join(campaigns._encode(record) for record in records))
        profile = json.loads((ROOT / "profiles/fixture-control.json").read_bytes())
        profile.update(capabilities=["bench.context-choice"], recordings=recordings.name)
        profile_path = self.root / "v2-profile.json"
        profile_path.write_bytes(campaigns._encode(profile))
        archive = self.root / "v2-run"
        campaigns.run_campaign(dataset, profile_path, archive, max_new_cases=4)
        summary = analyze_context(archive, self.root / "v2-analysis")
        self.assertEqual(summary["counts"]["total_cases"], 5)
        self.assertEqual(summary["counts"]["independent_families"], 1)
        self.assertEqual(summary["counts"]["supported_cases"], 4)
        self.assertEqual(summary["counts"]["unsupported_target_unattainable"], 1)
        self.assertEqual(summary["counts"]["typed_overflow_errors"], 1)
        self.assertEqual(summary["counts"]["counts_by_status"]["missing"], 1)
        self.assertEqual(summary["groups"]["target"]["base"]["passed_cases"], 1)
        length500 = summary["groups"]["target"]["500"]
        self.assertEqual(length500["reference_tokens"]["median"], cases[2]["evaluation"]["length"]["actual_tokens"])
        self.assertEqual(length500["resources"]["native_tokens"]["median"], 490)
        self.assertIsNone(summary["groups"]["target"]["1000"]["latency"]["inference_ms"]["median"])

        # Eos rejects an over-budget sequence before forward; retain unsupported
        # separately from a runtime error and an unattainable reference target.
        records[-1].update(status="unsupported", error="decision2_context_overflow")
        recordings.write_bytes(b"".join(campaigns._encode(record) for record in records))
        eos_archive = self.root / "v2-eos-overflow-run"
        campaigns.run_campaign(dataset, profile_path, eos_archive, max_new_cases=4)
        eos = analyze_context(eos_archive, self.root / "v2-eos-overflow-analysis")
        self.assertEqual(eos["counts"]["typed_native_overflows"], 1)
        self.assertEqual(eos["counts"]["typed_overflow_errors"], 0)
        self.assertEqual(eos["counts"]["unsupported_target_unattainable"], 1)
        self.assertEqual(eos["counts"]["counts_by_status"]["unsupported"], 2)
        self.assertEqual(eos["counts"]["counts_by_status"]["missing"], 1)
        self.assertIsNone(eos["groups"]["target"]["1000"]["latency"]["inference_ms"]["median"])

        # The Go worker emits typed unsupported overflows too: they must not fall into "other".
        for code in ("indecis_context_overflow", "indecis_option_overflow"):
            records[-1].update(status="unsupported", error=code)
            recordings.write_bytes(b"".join(campaigns._encode(record) for record in records))
            indecis_archive = self.root / f"v2-{code}-run"
            campaigns.run_campaign(dataset, profile_path, indecis_archive, max_new_cases=4)
            indecis = analyze_context(indecis_archive, self.root / f"v2-{code}-analysis")
            self.assertEqual(indecis["counts"]["typed_native_overflows"], 1, code)
            self.assertEqual(indecis["counts"]["typed_overflow_errors"], 0, code)


if __name__ == "__main__":
    unittest.main()
