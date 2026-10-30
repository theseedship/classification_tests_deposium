"""Publication controls for the local tool-policy aggregate; no archive or model needed."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
AGGREGATE = ROOT / "docs/evidence/local-tool-policy-20261030/analysis.json"


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


exporter = module("export_local_tool_policy", "scripts/export-local-tool-policy.py")
results = module("build_full_results_for_policy", "scripts/build-full-results.py")


class FakeInputs:
    def __init__(self, value):
        self.value = value

    def load(self, relative):
        assert relative == results.LOCAL_POLICY
        return self.value


class SealTests(unittest.TestCase):
    def archive(self, root, members):
        files = {}
        for name, raw in members.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            files[name] = hashlib.sha256(raw).hexdigest()
        (root / "seal.json").write_text(json.dumps({"schema_version": "synthetic/v1", "files": files}))

    def test_intact_archive_is_accepted_and_changed_member_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.archive(root, {"a.txt": b"alpha", "nested/b.txt": b"beta"})
            self.assertEqual(len(exporter.verify_seal(root, "seal.json", "synthetic/v1")), 64)
            (root / "nested/b.txt").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                exporter.verify_seal(root, "seal.json", "synthetic/v1")

    def test_wrong_schema_traversal_and_missing_members_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.archive(root, {"a.txt": b"alpha"})
            with self.assertRaises(ValueError):
                exporter.verify_seal(root, "seal.json", "other/v1")
            (root / "seal.json").write_text(json.dumps(
                {"schema_version": "synthetic/v1", "files": {"../escape.txt": "0" * 64}}))
            with self.assertRaises(ValueError):
                exporter.verify_seal(root, "seal.json", "synthetic/v1")
            (root / "a.txt").unlink()
            self.archive(root, {"a.txt": b"alpha"})
            (root / "a.txt").unlink()
            with self.assertRaises(ValueError):
                exporter.verify_seal(root, "seal.json", "synthetic/v1")

    def test_counts_and_durations_reject_negative_missing_and_nonfinite_values(self):
        for bad in (-1, True, 1.5, None):
            with self.assertRaises(ValueError):
                exporter.count(bad)
        with self.assertRaises(ValueError):
            exporter.count(5, 4)
        for bad in ([], [1.0, float("nan")], [1.0, -2.0]):
            with self.assertRaises(ValueError):
                exporter.milliseconds(bad)


class PublishedAggregateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.aggregate = json.loads(AGGREGATE.read_text())

    def test_denominators_are_closed_and_failures_stay_visible(self):
        a = self.aggregate
        coverage, by_task = a["coverage"], a["results"]["by_task"]
        self.assertEqual(coverage["eligible_cases"], 10)
        self.assertEqual(sum(coverage["counts_by_status"].values()), 10)
        self.assertEqual(sum(t["eligible"] for t in by_task.values()), 10)
        self.assertEqual(sum(t["correct"] for t in by_task.values()), coverage["passed_cases"])
        self.assertEqual(sum(g["eligible"] for g in a["results"]["by_language"].values()), 10)
        self.assertEqual(a["evaluation_status"], "train_canary_collected_quality_fail")
        self.assertEqual(a["review"], "agent_only_pending_human")
        self.assertEqual(a["dataset"]["splits"], {"train": 10})
        self.assertFalse(a["technical_controls"]["counted_as_benchmark_predictions"])
        self.assertFalse(a["technical_controls"]["native_request_alias_enforcement"])

    def test_discovery_without_valid_observations_reports_zero_not_a_perfect_score(self):
        discovery = self.aggregate["results"]["discovery"]
        self.assertEqual(discovery["valid_select_observations"], 0)
        self.assertEqual(discovery["final_sufficient"]["correct"], 0)
        self.assertEqual(discovery["final_minimal"]["eligible"], 2)

    def test_public_file_contains_no_paths_template_or_raw_output(self):
        text = AGGREGATE.read_text()
        for forbidden in ("/Users/", "/private/", "/tmp/", "raw_output", "response_base64",
                          "api_key", "Bearer ", "@", "{%"):
            self.assertNotIn(forbidden, text)

    def test_generator_accepts_the_aggregate_and_refuses_inconsistent_ones(self):
        row = results.local_policy_canary(FakeInputs(deepcopy(self.aggregate)))
        self.assertEqual((row["passed"], row["scored"], row["eligible"]), (5, 10, 10))
        mutations = [
            lambda d: d["coverage"].update(scored_cases=0),
            lambda d: d["coverage"].update(passed_cases=d["coverage"]["passed_cases"] + 1),
            lambda d: d["coverage"]["counts_by_status"].update(missing=3),
            lambda d: d["results"]["by_task"]["episodes"].update(eligible=5),
            lambda d: d.update(review="human_approved"),
            lambda d: d.update(qualification="product"),
        ]
        for mutate in mutations:
            broken = deepcopy(self.aggregate)
            mutate(broken)
            with self.assertRaises(results.ResultError):
                results.local_policy_canary(FakeInputs(broken))


if __name__ == "__main__":
    unittest.main()
