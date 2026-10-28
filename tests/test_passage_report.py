import importlib.util
from copy import deepcopy
from pathlib import Path
import unittest

from deposium_bench.campaigns import _encode, _hash
from deposium_bench.passage_dataset import load_dataset, export_requests
from deposium_bench.passage_observation import select_pilot

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/analyze-passage-pilot.py"
spec = importlib.util.spec_from_file_location("passage_pilot_report", SCRIPT)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class PassageReportTests(unittest.TestCase):
    def test_frozen_selection_rejects_wrong_cases_or_claimed_split(self):
        cases, sha = load_dataset()
        selected = select_pilot(cases, "test")
        manifest = {"case_ids": [case["case_id"] for case in selected],
                    "split": "test", "dataset_sha256": sha}
        ranking = b"".join(_encode(row) for row in export_requests(selected, "ranking"))
        report.validate_frozen_selection(selected, manifest, ranking)
        wrong = deepcopy(selected)
        wrong[0]["annotations"]["query_status"] = "insufficient_visible_evidence"
        with self.assertRaisesRegex(ValueError, "Archived selection"):
            report.validate_frozen_selection(wrong, manifest, ranking)
        wrong_manifest = {**manifest, "split": "calibration"}
        with self.assertRaisesRegex(ValueError, "Archived selection"):
            report.validate_frozen_selection(selected, wrong_manifest, ranking)

    def test_physical_trace_requires_order_hash_and_finite_latency(self):
        requests = [{"case_id": "call-a", "contract_id": "bench.context-choice", "input": {"x": 1}},
                    {"case_id": "call-b", "contract_id": "bench.context-choice", "input": {"x": 2}}]
        records = [{"call_id": row["case_id"], "request_sha256": _hash(_encode(row)),
                    "adapter_wall_ms": 1.5, "response": {"status": "ok"}} for row in requests]
        report.validate_choice_trace(requests, records)
        # A valid failed call must remain publishable with its distinct status.
        for status in ("error", "timeout", "unsupported", "abstain"):
            report.validate_choice_trace(requests, [{**records[0], "response": {"status": status}}, records[1]])
        for changed in (
            records[:-1],
            [records[1], records[0]],
            [{**records[0], "request_sha256": "0" * 64}, records[1]],
            [{**records[0], "adapter_wall_ms": float("nan")}, records[1]],
            [records[0], {**records[1], "call_id": "call-a"}],
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                report.validate_choice_trace(requests, changed)

    def test_native_costs_require_complete_matching_cpu_trace(self):
        cases = [{"case_id": "a"}, {"case_id": "b"}]
        inputs = [{"case_id": "a"}, {"case_id": "b"}]
        predictions = [{"case_id": cid, "status": "ok", "ranking": ["p0", "p1", "p2", "p3"]}
                       for cid in ("a", "b")]
        native = [{**row, "latency_ms": 15.0} for row in predictions]
        manifest = {"status": "complete", "scores_observed": 2,
                    "input_sha256": report.RANKING_INPUT_SHA256, "image": report.IMAGE,
                    "model": "bge-reranker-v2-m3", "running_binary_sha256": report.CPU_BINARY_SHA256,
                    "cpu_binary": {"sha256": report.CPU_BINARY_SHA256,
                                   "fingerprint_sha256": report.CPU_FINGERPRINT_SHA256},
                    "cpu_proof": {"provider": "cpu"}, "container_cleanup": "removed_with_anonymous_volumes",
                    "mounted_artifact_sha256": {report.NATIVE_BINARY_PATH: report.CPU_BINARY_SHA256,
                                                report.MODEL_PATH: report.MODEL_SHA256},
                    "profile": {"top_k": 4, "max_seq_len": 512, "cpus": 2,
                                "memory_bytes": 4 * 1024 ** 3, "network": "none",
                                "gpu_devices": 0, "rerank_session_pool": 1}}
        report.validate_baseline_trace(cases, inputs, predictions, native, manifest)
        failures = (
            (inputs, predictions, native[:-1], manifest),
            (inputs, predictions, [native[0], {**native[1], "case_id": "a"}], manifest),
            (inputs, predictions, [native[0], {**native[1], "latency_ms": float("nan")}], manifest),
            (inputs, predictions, [native[0], {**native[1], "ranking": ["p3", "p2", "p1", "p0"]}], manifest),
            (inputs, predictions, native, {**manifest, "cpu_proof": {"provider": "cuda"}}),
        )
        for args in failures:
            with self.subTest(args=args), self.assertRaises(ValueError):
                report.validate_baseline_trace(cases, *args)

    def test_distributed_evidence_requires_whole_set_and_penalizes_missing(self):
        cases = [{"case_id": cid, "annotations": {"query_status": "answerable",
                  "minimal_evidence_sets": [["a", "b"]]}} for cid in ("one", "missing")]
        predictions = [{"case_id": "one", "status": "ok", "ranking": ["a", "x", "b", "y"]}]
        result = report.evidence_capture(cases, predictions)
        self.assertEqual(result["sufficient_set@1"]["correct"], 0)
        self.assertEqual(result["sufficient_set@3"],
                         {"correct": 1, "observed": 1, "eligible": 2, "rate_over_eligible": .5})
        self.assertIsNone(result["conflict_pair@3"]["rate_over_eligible"])

    def test_conflicting_evidence_must_concern_the_same_claim(self):
        claim = lambda a, b: {"judgments": [{"passage_id": a, "label": "supports"},
                                            {"passage_id": b, "label": "refutes"}]}
        cases = [{"case_id": "c", "annotations": {"query_status": "conflicting_visible_evidence",
                  "claims": [claim("a", "c"), claim("c", "b")]}}]
        ranking = lambda ids: [{"case_id": "c", "status": "ok", "ranking": ids}]
        # One support and an unrelated refutation do not form a conflict pair.
        two = report.evidence_capture(cases, ranking(["a", "x", "b", "c"]))
        self.assertEqual(two["conflict_pair@3"]["correct"], 0)
        paired = report.evidence_capture(cases, ranking(["a", "x", "c", "b"]))
        self.assertEqual(paired["conflict_pair@3"]["correct"], 1)

    def test_resource_statistics_do_not_invent_empty_measurements(self):
        self.assertEqual(report.stats([]), {"count": 0, "median": None, "p95": None, "max": None})
        self.assertEqual(report.stats([9, 1, 4])["median"], 4)


if __name__ == "__main__":
    unittest.main()
