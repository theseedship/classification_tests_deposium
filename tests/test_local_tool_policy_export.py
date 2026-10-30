"""Publication controls for the local tool-policy aggregates; no archive or model needed."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
AGGREGATES = {"train_v1": ROOT / "docs/evidence/local-tool-policy-20261030/analysis.json",
              "train_v2": ROOT / "docs/evidence/local-tool-policy-v2-train-20261030/analysis.json",
              "heldout": ROOT / "docs/evidence/local-tool-policy-heldout-20261030/analysis.json"}


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


exporter = module("export_local_tool_policy", "scripts/export-local-tool-policy.py")
results = module("build_full_results_for_policy", "scripts/build-full-results.py")


class FakeInputs:
    def __init__(self, values):
        self.values = values

    def load(self, relative):
        return self.values[relative]


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

    def test_dataset_identity_accepts_both_receipt_layouts_and_refuses_unknown_or_mismatched(self):
        cases = [{"case_id": f"c{i}", "split": "train", "translation_family": f"f{i // 2}"} for i in range(10)]
        sha = "6add6d14904e16cc39449368ff932316409c294dd43674f4fb9a1a1fcdbc2a6d"
        legacy = {"sha256": sha, "cases": 10, "train_families": 5}
        bound = {"sha256": sha, "cases": 10, "families": 5, "counts_by_split": {"train": 10, "calibration": 0, "test": 0}}
        for layout in (legacy, bound):
            identity, split = exporter.dataset_identity(layout, cases)
            self.assertEqual((identity["id"], identity["families"], split), ("tool-policy-canary-v1", 5, "train"))
        for bad in ({**legacy, "sha256": "0" * 64}, {**legacy, "cases": 9}, {**legacy, "train_families": 4},
                    {**bound, "counts_by_split": {"train": 0, "calibration": 0, "test": 10}}):
            with self.assertRaises(ValueError):
                exporter.dataset_identity(bad, cases)


class PublishedAggregateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.aggregates = {name: json.loads(path.read_text()) for name, path in AGGREGATES.items()}

    def test_denominators_are_closed_and_failures_stay_visible(self):
        expected = {"train_v1": (10, 10, 5, True), "train_v2": (10, 10, 7, True), "heldout": (24, 18, 9, False)}
        for name, a in self.aggregates.items():
            coverage, by_task = a["coverage"], a["results"]["by_task"]
            eligible, scored, passed, complete = expected[name]
            self.assertEqual((coverage["eligible_cases"], coverage["scored_cases"], coverage["passed_cases"]),
                             (eligible, scored, passed), name)
            self.assertEqual(coverage.get("collection_complete", True), complete, name)
            self.assertEqual(sum(coverage["counts_by_status"].values()), eligible, name)
            self.assertEqual(sum(t["eligible"] for t in by_task.values()), eligible, name)
            self.assertEqual(sum(t.get("scored", t["eligible"]) for t in by_task.values()), scored, name)
            self.assertEqual(sum(t["correct"] for t in by_task.values()), passed, name)
            self.assertEqual(sum(g.get("eligible_all", g["eligible"]) for g in a["results"]["by_language"].values()), eligible, name)
            self.assertEqual(a["review"], "agent_only_pending_human")
            self.assertFalse(a["technical_controls"]["counted_as_benchmark_predictions"])
            self.assertFalse(a["technical_controls"]["native_request_alias_enforcement"])

    def test_partial_heldout_accounts_for_every_unobserved_case_and_the_guard_stop(self):
        a = self.aggregates["heldout"]
        coverage = a["coverage"]
        self.assertEqual(coverage["stop_reason"], "rss_guard")
        self.assertEqual(a["evaluation_status"], "test_partial_quality_fail")
        self.assertEqual(a["dataset"], {"id": "tool-policy-heldout-v1", "cases": 24, "families": 12,
                                        "sha256": "7f7ed8f08fe15d5b897744fe71f2a5ed76344b5ccd7a0df43492b2dc3371bac7",
                                        "splits": {"train": 0, "calibration": 0, "test": 24}})
        self.assertEqual(len(coverage["unobserved_cases"]), 6)
        self.assertEqual({u["status"] for u in coverage["unobserved_cases"]}, {"missing", "error"})
        self.assertEqual(coverage["counts_by_status"]["missing"] + coverage["counts_by_status"]["error"], 6)
        self.assertGreater(a["resources"]["rss_peak_mib"], a["resources"]["rss_limit_mib"])
        self.assertEqual(a["results"]["by_task"]["episodes"], {"correct": 3, "scored": 6, "eligible": 12})
        self.assertEqual(a["results"]["episodes"]["task_success"], {"correct": 3, "eligible": 4, "over_all_cases": 12})

    def test_prompt_versions_and_dataset_identities_are_recorded(self):
        self.assertNotIn("prompt_version", self.aggregates["train_v1"])  # first layout; v1 by construction
        self.assertEqual(self.aggregates["train_v2"]["prompt_version"], "deposium.local-tool-policy-prompt/v2")
        self.assertEqual(self.aggregates["heldout"]["prompt_version"], "deposium.local-tool-policy-prompt/v2")
        self.assertEqual(self.aggregates["train_v2"]["dataset"]["id"], "tool-policy-canary-v1")
        self.assertEqual(self.aggregates["train_v2"]["results"]["by_task"]["discovery"], {"correct": 1, "scored": 2, "eligible": 2})

    def test_public_files_contain_no_paths_template_or_raw_output(self):
        for name, path in AGGREGATES.items():
            text = path.read_text()
            for forbidden in ("/Users/", "/private/", "/tmp/", "raw_output", "response_base64",
                              "api_key", "Bearer ", "@", "{%"):
                self.assertNotIn(forbidden, text, (name, forbidden))

    def test_generator_accepts_the_three_aggregates_and_refuses_inconsistent_ones(self):
        inputs = FakeInputs({path: deepcopy(self.aggregates[name])
                             for path, name in zip(results.LOCAL_POLICY, ("train_v1", "train_v2", "heldout"))})
        rows = results.local_policy_observations(inputs)
        self.assertEqual([(r["passed"], r["scored"], r["eligible"], r["complete"]) for r in rows.values()],
                         [(5, 10, 10, True), (7, 10, 10, True), (9, 18, 24, False)])
        self.assertIn("6 unobserved after `rss_guard`", rows["heldout"]["text"])
        mutations = [
            ("heldout", lambda d: d["coverage"].update(scored_cases=0)),
            ("heldout", lambda d: d["coverage"].update(passed_cases=d["coverage"]["passed_cases"] + 1)),
            ("heldout", lambda d: d["coverage"].update(collection_complete=True)),
            ("heldout", lambda d: d["coverage"].update(stop_reason=None)),
            ("heldout", lambda d: d["coverage"]["unobserved_cases"].pop()),
            ("heldout", lambda d: d["results"]["by_task"]["episodes"].update(scored=7)),
            ("train_v2", lambda d: d.update(prompt_version="deposium.local-tool-policy-prompt/v1")),
            ("train_v2", lambda d: d["coverage"]["counts_by_status"].update(missing=3)),
            ("train_v1", lambda d: d.update(review="human_approved")),
            ("train_v1", lambda d: d.update(qualification="product")),
        ]
        for name, mutate in mutations:
            broken = {path: deepcopy(self.aggregates[n])
                      for path, n in zip(results.LOCAL_POLICY, ("train_v1", "train_v2", "heldout"))}
            target = broken[results.LOCAL_POLICY[("train_v1", "train_v2", "heldout").index(name)]]
            mutate(target)
            with self.subTest(name=name), self.assertRaises(results.ResultError):
                results.local_policy_observations(FakeInputs(broken))


if __name__ == "__main__":
    unittest.main()
