"""Public result joins preserve evidence and reject misleading presentation inputs.

Every Git-dependent check uses a temporary, explicitly populated repository. The
source tree itself may be a source export without .git, weights or raw archives.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("public_full_results", ROOT / "scripts/build-full-results.py")
results = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(results)

EXPECTED_LABELS = {
    "D3edge", "D3flash", "D3lite", "D3mini", "D3nano", "Eos", "GLiNER",
    "Indecis", "Jev", "Julia", "Kai", "Laya", "Liquid3", "ModernJEV",
    "Muose", "Noma", "Nox", "Omni", "Sol", "Vela03", "Vela08", "Vela4",
    "D3FlashQ4", "D3FlashQ8", "D3Q4", "EosQ8", "GLiClass9B", "Vela3Fast",
}


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.STDOUT)


def public_fixture(root):
    """Copy named release inputs, never discover local files by filesystem glob."""
    metadata = json.loads((ROOT / results.METADATA).read_text())
    paths = {
        "scripts/build-full-results.py", "scripts/compose-larger-cpu-comparison.py",
        "scripts/compose-d3-comparison.py", results.METADATA, results.HISTORICAL,
        results.HISTORICAL.replace("manifest.json", "report.md"), results.CPU,
        results.NATIVE, results.GLICLASS, results.FAST,
        results.NATIVE_SESSION, results.GLICLASS_SESSION,
        "docs/evidence/model-comparison-d3-larger-20261011/analysis.json",
        "docs/evidence/model-comparison-complete-20261010-sol/analysis.json",
        "docs/evidence/model-comparison-vela2-20261011/analysis.json",
        "docs/evidence/model-comparison-d3-20261011/analysis.json",
    }
    for row in metadata["observations"].values():
        paths.add(row["source_analysis"])
        paths.update(evidence["path"] for evidence in row["evidence"])
        if row["model_size"]["source"]:
            paths.add(row["model_size"]["source"]["path"])
    for relative in paths:
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise AssertionError("fixture metadata escaped public source tree")
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    (root / ".gitignore").write_text("local-only/\n")
    git(root, "init", "-q")
    git(root, "add", "--", ".gitignore", *sorted(paths))
    return paths


class PublicInputTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        git(self.root, "init", "-q")
        (self.root / ".gitignore").write_text("ignored.json\n")
        (self.root / "public.json").write_text('{"value": 0}\n')
        git(self.root, "add", "--", ".gitignore", "public.json")

    def test_reads_only_tracked_public_paths_and_records_actual_byte_hash(self):
        inputs = results.PublicInputs(self.root)
        self.assertEqual(inputs.load("public.json"), {"value": 0})
        self.assertEqual(inputs.hashes, {"public.json": hashlib.sha256(
            (self.root / "public.json").read_bytes()).hexdigest()})
        for relative in ("ignored.json", "untracked.json"):
            (self.root / relative).write_text('{"synthetic_local_only": true}\n')
            with self.subTest(path=relative), self.assertRaises(results.ResultError):
                inputs.read(relative)
        self.assertEqual(set(inputs.hashes), {"public.json"})

    def test_rejects_absolute_traversal_and_tracked_symlink_inputs(self):
        (self.root / "link.json").symlink_to("public.json")
        git(self.root, "add", "--", "link.json")
        inputs = results.PublicInputs(self.root)
        for path in (str(self.root / "public.json"), "../public.json", "link.json"):
            with self.subTest(path=path), self.assertRaises(results.ResultError):
                inputs.read(path)

    def test_rejects_empty_input_and_non_object_json(self):
        inputs = results.PublicInputs(self.root)
        for content in ("", "[]", "null"):
            (self.root / "public.json").write_text(content)
            with self.subTest(content=content), self.assertRaises(results.ResultError):
                inputs.load("public.json")


class FullResultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.root = Path(temp.name)
        cls.public_paths = public_fixture(cls.root)
        cls.inputs = results.PublicInputs(cls.root)
        cls.composer = results.load_composer(cls.inputs)
        cls.data = results.build(cls.root)
        cls.by_id = {row["id"]: row for row in cls.data["observations"]}
        export = json.loads((cls.root / results.NATIVE).read_text())
        cls.base = export["base"]["D3Q4"]
        cls.route = export["mastra"]["D3Q4"]

    @contextmanager
    def changed_json(self, relative, change):
        path = self.root / relative
        original = path.read_bytes()
        data = json.loads(original)
        change(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        try:
            yield
        finally:
            path.write_bytes(original)

    def reject_pair(self, change):
        base, route = deepcopy(self.base), deepcopy(self.route)
        change(base, route)
        with self.assertRaises(ValueError):
            results.validate_pair("D3Q4", base, route, self.composer.legacy)

    def test_join_contains_28_unique_observations_and_preserves_known_scores(self):
        self.assertEqual(set(self.by_id), EXPECTED_LABELS)
        self.assertEqual(len(self.data["observations"]), 28)
        for phase in ("context", "tool_proposal"):
            self.assertEqual(len({r[phase]["source"]["seal_sha256"] for r in self.by_id.values()}), 28)
            self.assertEqual(len({r[phase]["source"]["dataset_sha256"] for r in self.by_id.values()}), 1)
        self.assertEqual(self.by_id["D3Q4"]["context"]["counts"]["correct"], 128)
        self.assertEqual(self.by_id["GLiClass9B"]["context"]["groups"]["split"]["test"]["correct"], 63)
        self.assertEqual(self.by_id["Vela3Fast"]["context"]["counts"]["correct"], 57)
        self.assertNotIn("physics", self.by_id["D3Q4"]["context"]["groups"]["domain"])

    def test_repeated_exports_are_not_additional_models_and_conflicts_are_rejected(self):
        gli = json.loads((self.root / results.GLICLASS).read_text())
        self.assertTrue({"D3FlashQ4", "D3FlashQ8", "D3Q4", "EosQ8"} <= set(gli["base"]))
        def change(data):
            data["base"]["D3FlashQ8"]["source"]["raw_sha256"] = "a" * 64
        with self.changed_json(results.GLICLASS, change):
            with self.assertRaisesRegex(results.ResultError, "conflicting repeated observation"):
                results.build(self.root)

    def test_same_observation_tolerates_added_measurements_but_not_identity_or_source_drift(self):
        original = deepcopy(self.base)
        measured = deepcopy(original)
        measured["extra_measurement"] = {"calls": 132}
        self.assertTrue(results.same_observation(original, measured))
        for field, value in (("model_revision", "a" * 40), ("identity_sha256", "b" * 64),
                             ("runtime", {"synthetic_runtime": "changed"}),
                             ("settings", {"device": "different"})):
            changed = deepcopy(original)
            changed["identity"][field] = value
            with self.subTest(field=field):
                self.assertFalse(results.same_observation(original, changed))
        changed = deepcopy(original)
        changed["source"]["seal_sha256"] = "c" * 64
        self.assertFalse(results.same_observation(original, changed))

    def test_all_denominators_and_qualifications_remain_explicit(self):
        for row in self.by_id.values():
            context, tool = row["context"], row["tool_proposal"]
            self.assertEqual(context["counts"]["total"], 132)
            self.assertEqual(context["groups"]["split"]["test"]["total"], 66)
            self.assertEqual({k: v["total"] for k, v in context["groups"]["domain"].items()},
                             {"documentary": 76, "mathematics": 28, "chemistry": 28})
            self.assertEqual(sum(context["counts"]["statuses"].values()), 132)
            self.assertEqual(tool["counts"]["total"], 24)
            self.assertEqual(tool["cases_scored"], 0)
            self.assertEqual(tool["qualification"], "provisional_agreement_pending_human_review")
            self.assertEqual(sum(tool["statuses"].values()), 24)

    def test_valid_pair_is_accepted_but_wrong_denominators_and_group_totals_are_not(self):
        results.validate_pair("D3Q4", deepcopy(self.base), deepcopy(self.route), self.composer.legacy)
        mutations = [
            lambda b, r: b["counts"].update(total=131),
            lambda b, r: b["counts"].update(translation_families=65),
            lambda b, r: b["groups"]["split"]["test"].update(total=65),
            lambda b, r: b["groups"]["language"]["fr"].update(correct=63),
            lambda b, r: r["by_language"]["fr"].update(valid_decisions=11, agreement_count=11),
            lambda b, r: r["by_proposed_action"]["search"].update(total=7),
            lambda b, r: r.update(cases_scored=24),
        ]
        for index, change in enumerate(mutations):
            with self.subTest(mutation=index):
                self.reject_pair(change)

    def test_rejects_zero_scored_cases_wrong_source_hash_and_cross_model_tool_pair(self):
        mutations = [
            lambda b, r: b["counts"].update(scored=0, correct=0),
            lambda b, r: b["source"].update(dataset_sha256="not-a-hash"),
            lambda b, r: r["identity"].update(model_revision="a" * 40),
            lambda b, r: r.update(reference_review="approved"),
        ]
        for index, change in enumerate(mutations):
            with self.subTest(mutation=index):
                self.reject_pair(change)

    def test_rejects_negative_boolean_and_misrepresented_status_coverage(self):
        mutations = [
            lambda b, r: r["statuses"].update(ok=25, error=-1),
            lambda b, r: r["statuses"].update(ok=23, error=True),
            lambda b, r: r["statuses"].update(ok=23, error=1),
            lambda b, r: b["counts"]["statuses"].update(ok=0, error=132),
        ]
        for index, change in enumerate(mutations):
            with self.subTest(mutation=index):
                self.reject_pair(change)

    def test_valid_partial_coverage_keeps_failures_in_original_denominators(self):
        # A synthetic aggregate mutation tests presentation semantics, not a rescore.
        base, route = deepcopy(self.base), deepcopy(self.route)
        base["counts"].update(scored=131, correct=127)
        base["counts"]["statuses"].update(ok=131, error=1)
        base["groups"] = {axis: base["groups"][axis] for axis in
                          ("domain", "split", "language", "difficulty")}
        for groups in base["groups"].values():
            count = next(v for v in groups.values() if v["correct"] > 0)
            count["correct"] -= 1
            count["scored"] -= 1
            count["statuses"]["ok"] -= 1
            count["statuses"]["error"] += 1
        base["timing"]["successful_adapter_ms"]["count"] = 131
        route["coverage"].update(valid_decisions=23, agreement_count=23)
        route["statuses"].update(ok=23, timeout=1)
        for axis in self.composer.legacy.MASTRA_GROUPS:
            group = next(iter(route[axis].values()))
            group["valid_decisions"] -= 1
            group["agreement_count"] -= 1
        route["timing"]["successful_adapter_ms"]["count"] = 23
        results.validate_pair("synthetic-partial", base, route, self.composer.legacy)
        count = results.compact_counts(base["counts"])
        self.assertEqual((count["correct"], count["scored"], count["total"]), (127, 131, 132))
        self.assertEqual(count["statuses"]["error"], 1)
        tool = results.compact_counts(route["coverage"], route=True)
        self.assertEqual((tool["agreement_count"], tool["valid_decisions"], tool["total"]), (23, 23, 24))

    def test_missing_memory_is_not_zero_and_gpu_allocation_is_not_added_to_rss(self):
        remote = self.by_id["Jev"]["resources"]
        self.assertIsNone(remote["worker_rss_mib"]["max"])
        self.assertEqual(remote["worker_rss_mib"]["count"], 0)
        self.assertIsNone(remote["session_process_group_peak_rss_mib"])
        self.assertIsNone(remote["sampled_gpu_allocated_peak_mib"])
        gli = self.by_id["GLiClass9B"]["resources"]
        session = json.loads((self.root / results.GLICLASS_SESSION).read_text())["observations"]["base"]
        self.assertEqual(gli["worker_rss_mib"]["max"], session["max_reported_rss_mib"])
        self.assertEqual(gli["sampled_gpu_allocated_peak_mib"], session["max_sampled_gpu_allocated_mib"])
        self.assertIsNone(gli["session_process_group_peak_rss_mib"])
        self.assertEqual(results.number(None), "NR")
        self.assertEqual(results.number(0), "0.0")
        models, tasks = results.flat_rows(self.data)
        csv_rows = {r["observation"]: r for r in csv.DictReader(io.StringIO(results.csv_text(models)))}
        self.assertEqual(csv_rows["Jev"]["worker_peak_rss_mib"], "")
        self.assertEqual(csv_rows["GLiClass9B"]["tool_qualified_cases"], "0")
        self.assertTrue(any(t["task"] == "tool_proposal" and t["ok"] is None for t in tasks))
        self.assertTrue(any(t["task"] == "context" and t["error"] == 0 for t in tasks))

    def test_native_process_group_peaks_use_session_identity_and_seals(self):
        sessions = json.loads((self.root / results.NATIVE_SESSION).read_text())["observations"]
        for label, native in sessions.items():
            res = self.by_id[label]["resources"]
            self.assertEqual(res["session_process_group_peak_rss_mib"], native["resources"]["rss_peak_mib"])
            self.assertIsNone(res["sampled_gpu_allocated_peak_mib"])
            self.assertIn("context + tool session", res["rss_scope"])
        for field, value in (("revision", "a" * 40), ("sha256", "b" * 64)):
            def change(data):
                data["observations"]["D3Q4"]["model"][field] = value
            with self.subTest(field=field), self.changed_json(results.NATIVE_SESSION, change):
                with self.assertRaisesRegex(results.ResultError, "native resource identity"):
                    results.build(self.root)
        def wrong_seal(data):
            data["observations"]["D3Q4"]["files_sha256"]["bases/seal.json"] = "a" * 64
        with self.changed_json(results.NATIVE_SESSION, wrong_seal):
            with self.assertRaisesRegex(results.ResultError, "native resource seals"):
                results.build(self.root)

    def test_rejects_nonfinite_or_negative_resource_measurements(self):
        for value in (float("nan"), float("inf"), -1, True, None):
            with self.subTest(value=value), self.assertRaises(results.ResultError):
                results.measured_number(value, "synthetic")
        self.assertEqual(results.measured_number(0, "synthetic"), 0)

    def test_rejects_duplicate_seal_and_mixed_dataset_on_new_observation(self):
        for field, value, message in (
            ("seal_sha256", self.by_id["D3Q4"]["context"]["source"]["seal_sha256"], "duplicate observation seals"),
            ("dataset_sha256", "a" * 64, "mixed datasets"),
        ):
            def change(data):
                data["base"]["Vela3Fast"]["source"][field] = value
            with self.subTest(field=field), self.changed_json(results.FAST, change):
                with self.assertRaisesRegex(results.ResultError, message):
                    results.build(self.root)

    def test_metadata_cannot_introduce_a_missing_model_or_untracked_evidence(self):
        def remove(data):
            del data["observations"]["Jev"]
        with self.changed_json(results.METADATA, remove):
            with self.assertRaisesRegex(results.ResultError, "roster mismatch"):
                results.build(self.root)
        local = self.root / "local-only" / "synthetic.json"
        local.parent.mkdir(exist_ok=True)
        local.write_text('{"synthetic_local_only": true}\n')
        self.addCleanup(local.unlink)
        def untracked(data):
            data["observations"]["Jev"]["evidence"].append({"path": "local-only/synthetic.json"})
        with self.changed_json(results.METADATA, untracked):
            with self.assertRaisesRegex(results.ResultError, "not a tracked public file"):
                results.build(self.root)

    def test_source_manifest_hashes_actual_tracked_inputs_and_never_discovers_local_overlay(self):
        local = self.root / "local-only" / "synthetic-overlay.json"
        local.parent.mkdir(exist_ok=True)
        local.write_text('{"synthetic_local_only": true}\n')
        self.addCleanup(local.unlink)
        rebuilt = results.build(self.root)
        self.assertEqual(rebuilt, self.data)
        self.assertNotIn("local-only/synthetic-overlay.json", rebuilt["sources_sha256"])
        tracked = results.PublicInputs(self.root).tracked
        for relative, expected in rebuilt["sources_sha256"].items():
            self.assertIn(relative, tracked)
            self.assertEqual(hashlib.sha256((self.root / relative).read_bytes()).hexdigest(), expected)
        self.assertIn("scripts/build-full-results.py", rebuilt["sources_sha256"])
        self.assertIn(results.METADATA, rebuilt["sources_sha256"])
        self.assertIn("no_inference_or_raw_archive_verification", rebuilt["scope"])

    def test_competition_ranks_share_ties_and_export_rows_keep_task_denominators(self):
        rows = self.data["observations"]
        self.assertEqual([r["id"] for r in rows], sorted(
            self.by_id, key=lambda label: (-self.by_id[label]["context"]["counts"]["correct"], label)))
        for row in rows:
            correct = row["context"]["counts"]["correct"]
            expected = 1 + sum(r["context"]["counts"]["correct"] > correct for r in rows)
            self.assertEqual(row["rank_all_splits"], expected)
        models, tasks = results.flat_rows(self.data)
        self.assertEqual(len(models), 28)
        test_tasks = [r for r in tasks if r["task"] == "context" and r["axis"] == "split" and r["group"] == "test"]
        self.assertEqual(len(test_tasks), 28)
        self.assertEqual({r["total"] for r in test_tasks}, {66})
        self.assertEqual({r["metric"] for r in tasks if r["task"] == "tool_proposal"}, {"provisional_agreement"})

    def test_outputs_are_deterministic_across_builds_and_hash_seeds(self):
        first = results.outputs(self.data)
        self.assertEqual(first, results.outputs(results.build(self.root)))
        self.assertEqual(set(first), {"docs/RESULTS.md", "docs/leaderboard/models.csv",
                                      "docs/leaderboard/task-breakdown.csv", "docs/leaderboard/results.json"})
        code = (
            "import hashlib,json,pathlib,runpy,sys;root=pathlib.Path(sys.argv[1]);"
            "m=runpy.run_path(str(root/'scripts/build-full-results.py'));"
            "views=m['outputs'](m['build'](root));"
            "print(json.dumps({k:hashlib.sha256(v.encode()).hexdigest() for k,v in views.items()},sort_keys=True))"
        )
        expected = json.dumps({k: hashlib.sha256(v.encode()).hexdigest() for k, v in first.items()}, sort_keys=True)
        for seed in ("1", "79"):
            env = {**os.environ, "PYTHONHASHSEED": seed,
                   "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
            actual = subprocess.check_output([sys.executable, "-c", code, str(self.root)], env=env, text=True)
            self.assertEqual(actual.strip(), expected)


if __name__ == "__main__":
    unittest.main()
