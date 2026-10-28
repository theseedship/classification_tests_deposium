import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from deposium_bench.campaigns import _encode, _hash
from deposium_bench.passage_dataset import export_requests, score_rankings
from deposium_bench.passage_observation import compose_rankings

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/analyze-passage-order-control.py"
spec = importlib.util.spec_from_file_location("passage_order_control", SCRIPT)
order = importlib.util.module_from_spec(spec)
spec.loader.exec_module(order)


class PassageOrderControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, cls.inputs, cls.payload = order.full_test_cases()

    def test_frozen_all_rotations_and_input_digest(self):
        self.assertEqual(len(self.cases), 512)
        self.assertEqual(_hash(self.payload), order.FULL_INPUT_SHA256)
        self.assertEqual([sum(c["provenance"]["position_rotation"] == r for c in self.cases)
                          for r in order.ROTATIONS], [128] * 4)

    def test_relevance_reuse_keys_exact_visible_input_not_logical_id(self):
        case = self.cases[0]
        request = export_requests([case], "relevance")[0]
        digest = _hash(_encode({"contract_id": request["contract_id"], "input": request["input"]}))
        call_id = "call-" + digest
        physical = {call_id: {"case_id": call_id, "contract_id": request["contract_id"], "input": request["input"]}}
        calls = {call_id: {"call_id": call_id, "response": {"status": "ok", "output": {"choice_id": "o3"}}}}
        rotated_id = {**request, "case_id": "different-logical-id"}
        self.assertEqual(order.reuse_relevance_request(rotated_id, physical, calls), (call_id, "o3"))
        with self.assertRaisesRegex(ValueError, "never physically observed"):
            order.reuse_relevance_request({**request, "input": {**request["input"], "context": "changed"}}, physical, calls)
        with self.assertRaisesRegex(ValueError, "never physically observed"):
            order.reuse_relevance_request(request, {}, calls)

    def test_ties_and_order_controls_do_not_depend_on_gold(self):
        case = self.cases[0]
        original = [passage["id"] for passage in case["passages"]]
        reversed_ids = list(reversed(original))
        rows = [{"case_id": case["case_id"], "axis": "relevance", "passage_id": pid,
                 "status": "ok", "choice_id": "o1"} for pid in original]
        comparison = compose_rankings([case], rows, [{"case_id": case["case_id"], "status": "ok", "ranking": reversed_ids}])
        self.assertEqual(comparison["replacement_predictions"][0]["ranking"], original)
        self.assertEqual(comparison["complement_predictions"][0]["ranking"], reversed_ids)
        ties = order.tie_summary([case], rows)["overall"]
        self.assertEqual(ties, {"cases": 1, "top_grade_ties": 1, "any_grade_ties": 1})
        self.assertEqual(score_rankings([case], [{"case_id": case["case_id"], "status": "ok", "ranking": original}])["total_cases"], 1)

    def test_baseline_trace_rejects_dropped_duplicate_and_nonfinite_cost(self):
        cases, inputs, payload = self.cases, self.inputs, self.payload
        predictions = [{"case_id": case["case_id"], "status": "ok",
                        "ranking": [passage["id"] for passage in case["passages"]]} for case in cases]
        native = [{**row, "latency_ms": 1.0} for row in predictions]
        manifest = {"status": "complete", "scores_observed": 512,
                    "input_sha256": order.FULL_INPUT_SHA256, "image": order.old.IMAGE,
                    "model": "bge-reranker-v2-m3", "running_binary_sha256": order.old.CPU_BINARY_SHA256,
                    "cpu_binary": {"sha256": order.old.CPU_BINARY_SHA256,
                                   "fingerprint_sha256": order.old.CPU_FINGERPRINT_SHA256},
                    "cpu_proof": {"provider": "cpu"}, "container_cleanup": "removed_with_anonymous_volumes",
                    "mounted_artifact_sha256": {order.old.NATIVE_BINARY_PATH: order.old.CPU_BINARY_SHA256,
                                                order.old.MODEL_PATH: order.old.MODEL_SHA256},
                    "profile": {"top_k": 4, "max_seq_len": 512, "cpus": 2,
                                "memory_bytes": 4 * 1024 ** 3, "network": "none",
                                "gpu_devices": 0, "rerank_session_pool": 1}}
        order.validate_full_baseline(cases, inputs, payload, predictions, native, manifest)
        for changed in (native[:-1], [native[0], native[0], *native[2:]],
                        [{**native[0], "latency_ms": float("nan")}, *native[1:]],
                        [{**native[0], "ranking": list(reversed(native[0]["ranking"]))}, *native[1:]]):
            with self.subTest(changed=changed[:2]), self.assertRaises(ValueError):
                order.validate_full_baseline(cases, inputs, payload, predictions, changed, manifest)

    def test_original_support_precision_exposes_false_supports(self):
        source_rows, predictions = {}, []
        for axis, total in (("support", 768), ("answerability", 128)):
            rows = []
            for i in range(total):
                gold = "supports" if axis == "support" and i == 0 else (
                    "insufficient" if axis == "support" else "answerable")
                rows.append({"case_id": str(i), "axis": axis, "status": "ok", "expected_label": gold})
                predictions.append({"case_id": str(i), "axis": axis, "status": "ok", "choice_id": "o1"})
            source_rows[axis] = {"rows": rows}
        files = {"scores.json": json.dumps(source_rows).encode(),
                 "logical-predictions.jsonl": b"".join(_encode(row) for row in predictions)}
        result = order.original_choice_confusion(files)
        self.assertEqual(result["support"]["per_class"]["supports"]["true_positive"], 1)
        self.assertAlmostEqual(result["support"]["per_class"]["supports"]["precision"], 1 / 768)
        self.assertEqual(result["support"]["per_class"]["supports"]["recall_over_all"], 1)
        self.assertIsNone(result["support"]["per_class"]["insufficient"]["precision"])

    def test_render_is_identical_after_sorted_json_roundtrip(self):
        names = ("input_order", "reversed_order", "baseline", "replacement", "complement")
        groups = {axis: {"one": {}} for axis in ("language_direction", "scenario_id", "view")}
        capture = {"sufficient_set@3": {"correct": 1, "eligible": 1},
                   "conflict_pair@3": {"correct": 1, "eligible": 1}}
        cost = {"count": 512, "median": 1000, "p95": 2000}
        data = {"rankings": {name: {"by": groups} for name in names},
                "by_rotation": {"0": {name: {} for name in names}},
                "evidence_capture": {name: capture for name in names},
                "grade_ties": {"overall": {"top_grade_ties": 1, "any_grade_ties": 2, "cases": 512}},
                "cost_ms": {"complement_sequential_projection": cost,
                            "d3_four_relevance_choices_replayed_projection": cost,
                            "bge_one_pool_actual": cost},
                "dataset_sha256": "dataset", "ranking_input_sha256": "ranking",
                "source": {"producer_sha256": "producer"}}
        with patch.object(order.old, "rank_value", return_value="0"):
            before = order.render(data)
            after = order.render(json.loads(json.dumps(data, sort_keys=True)))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
