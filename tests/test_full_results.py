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
import re
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
    "ClefFlashQ8", "D3FlashQ8Upstream", "D3liteMacos", "Vela03Macos", "D3nanoMacos", "D3miniMacos",
    "D3liteQ8Metal", "D3nanoQ8Metal", "D3miniQ8Metal",
    "D3miniQ4Metal", "D3FlashQ4Metal", "D3FlashMUzu",
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
        results.NATIVE, results.GLICLASS, results.FAST, results.D3LITE_MACOS, results.VELA03_MACOS, results.D3NANO_MACOS, results.CAPABILITY, *results.LOCAL_POLICY,
        results.NATIVE_SESSION, results.GLICLASS_SESSION,
        "docs/evidence/model-comparison-d3-larger-20261011/analysis.json",
        "docs/evidence/model-comparison-complete-20261010-sol/analysis.json",
        "docs/evidence/model-comparison-vela2-20261011/analysis.json",
        "docs/evidence/model-comparison-d3-20261011/analysis.json",
    }
    paths.update(results.RECENT_INPUTS)
    paths.add(results.OTHER_GUIDE)
    paths.update(results.OTHER_SOURCES.values())
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

    def test_join_contains_30_unique_context_observations_and_preserves_historical_scores(self):
        self.assertEqual(set(self.by_id), EXPECTED_LABELS)
        self.assertEqual(len(self.data["observations"]), 40)
        self.assertEqual(self.data["historical_context_observations"], 32)
        for phase in ("context", "tool_proposal"):
            observed = [r[phase] for r in self.by_id.values() if r[phase] is not None]
            self.assertEqual(len({r["source"]["seal_sha256"] for r in observed}), 40 if phase == "context" else 32)
            self.assertEqual(len({r["source"]["dataset_sha256"] for r in observed}), 1)
        self.assertEqual(self.by_id["D3Q4"]["context"]["counts"]["correct"], 128)
        self.assertEqual(self.by_id["GLiClass9B"]["context"]["groups"]["split"]["test"]["correct"], 63)
        self.assertEqual(self.by_id["Vela3Fast"]["context"]["counts"]["correct"], 57)
        self.assertNotIn("physics", self.by_id["D3Q4"]["context"]["groups"]["domain"])

    def test_new_campaign_tables_show_fresh_packs_tracks_views_and_measurements_separately(self):
        campaign = self.data["capability_campaign"]
        anchor, capability = (campaign["phases"][key] for key in ("anchor", "capability"))
        self.assertEqual(set(campaign["phases"]), {"anchor", "capability"})
        self.assertFalse(campaign["canary_in_quality_denominators"])
        self.assertEqual((anchor["counts"]["correct"], anchor["counts"]["total"]), (124, 132))
        self.assertEqual((anchor["counts"]["by_split"]["test"]["correct"],
                          anchor["counts"]["by_split"]["test"]["total"]), (61, 66))
        self.assertEqual((capability["counts"]["correct"], capability["counts"]["total"]), (192, 192))
        self.assertEqual(capability["counts"]["by_split"]["test"], {"correct": 96, "scored": 96, "total": 96})
        for track in ("selection", "arguments", "observations"):
            group = capability["groups"]["track"][track]
            self.assertEqual((group["correct"], group["scored"], group["total"]), (64, 64, 64))
            self.assertEqual(group["by_split"]["test"], {"correct": 32, "scored": 32, "total": 32})
        for axis, keys in (("language", ("fr", "en")), ("catalogue_variant", ("compact", "expanded"))):
            for key in keys:
                group = capability["groups"][axis][key]
                self.assertEqual((group["correct"], group["total"]), (96, 96))
        self.assertAlmostEqual(anchor["adapter_ms"]["median"], 196.31710400426527)
        self.assertAlmostEqual(capability["adapter_ms"]["p95"], 985.788958001649)
        self.assertEqual(capability["session_group_peak_rss_mib"], 9704.375)
        self.assertEqual((anchor["counts"]["families"], capability["counts"]["families"],
                          capability["groups"]["split"]["test"]["families"]), (66, 48, 24))
        self.assertIn(results.CAPABILITY, self.data["sources_sha256"])
        rendered = results.render(self.data)
        for text in ("| 1 | 1 | D3 Flash Q8 · gateway Metal | 192/192 | 192/192 | 96/96 |",
                     "| D3 Flash Q8 · gateway Metal | Capability selection | 64/64 | 32/32 |",
                     "| D3 Flash Q8 · gateway Metal | capability | 192 | 576.9 | 985.8 | 9.48 |",
                     "Canaries and repeated context anchors do not add quality cases",
                     "[D3 capability report](CAPABILITY_FLASH_RESULTS_20261029.md)",
                     "## Coverage overview", "66 families"):
            self.assertIn(text, rendered)
        self.assertNotIn("## Complementary capability campaign", rendered)
        # Fine-grained language/catalogue data remain in the structured download.
        structured = json.loads(results.outputs(self.data)["docs/leaderboard/results.json"])
        self.assertEqual(structured["capability_campaign"], campaign)

    def test_new_campaign_rejects_inconsistent_groups_identity_dataset_and_resource_scope(self):
        mutations = [
            lambda data: data["phases"]["capability"]["counts"].update(total_cases=191),
            lambda data: data["phases"]["capability"]["groups"]["track"]["selection"].update(passed_cases=63),
            lambda data: data["phases"]["capability"]["groups"]["catalogue_variant"]["expanded"].update(total_cases=95),
            lambda data: data["phases"]["anchor"]["groups"]["split"]["test"].update(total_cases=65),
            lambda data: data["phases"]["capability"]["counts"].update(independent_families=47),
            lambda data: data["phases"]["capability"]["groups"]["split"]["test"].update(independent_families=23),
            lambda data: data["phases"]["capability"]["identity"].update(model_sha256="a" * 64),
            lambda data: data["phases"]["capability"]["sources"].update(dataset_sha256="a" * 64),
            lambda data: data["phases"]["capability"]["session_resources"].update(rss_scope="total GPU memory"),
            lambda data: data["phases"]["capability"]["counts"]["successful_latency"]["adapter_duration_ms"].update(median=float("nan")),
        ]
        for index, change in enumerate(mutations):
            with self.subTest(mutation=index), self.changed_json(results.CAPABILITY, change):
                with self.assertRaises(results.ResultError):
                    results.build(self.root)

    def test_new_campaign_zero_scored_cases_never_produce_a_summary_pass(self):
        def zero_scored(data):
            counts = data["phases"]["capability"]["counts"]
            counts.update(scored_cases=0, passed_cases=0)
            counts["counts_by_status"].update(ok=0, error=192)
            for group in counts["counts_by_split"].values():
                group.update(scored_cases=0, passed_cases=0)
        with self.changed_json(results.CAPABILITY, zero_scored):
            with self.assertRaisesRegex(results.ResultError, "zero scored cases"):
                results.build(self.root)

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
            if tool is None:
                self.assertIn(row["id"], {"ClefFlashQ8", "D3FlashQ8Upstream", "D3liteQ8Metal", "D3nanoQ8Metal", "D3miniQ8Metal", "D3miniQ4Metal", "D3FlashQ4Metal", "D3FlashMUzu"})
                self.assertEqual(row["tool_proposal_status"], "not_run")
                continue
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
        self.assertEqual(len(models), 40)
        test_tasks = [r for r in tasks if r["task"] == "context" and r["axis"] == "split" and r["group"] == "test"]
        self.assertEqual(len(test_tasks), 40)
        self.assertEqual({r["total"] for r in test_tasks}, {66})
        self.assertEqual({r["metric"] for r in tasks if r["task"] == "tool_proposal"}, {"provisional_agreement"})

    def test_outputs_are_deterministic_across_builds_and_hash_seeds(self):
        first = results.outputs(self.data)
        self.assertEqual(first, results.outputs(results.build(self.root)))
        fixed = {"docs/RESULTS.md", "docs/leaderboard/models.csv", "docs/leaderboard/task-breakdown.csv",
                 "docs/leaderboard/results.json", "docs/leaderboard/campaigns.csv", "docs/leaderboard/coverage.csv",
                 "docs/leaderboard/coverage.json"}
        pages = {k for k in first if k.startswith(results.MODEL_PAGES_DIR)}
        self.assertEqual(set(first) - pages, fixed)
        self.assertEqual(len(pages), len(self.data["coverage"]["observations"]) + 1)
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

    def test_clef_is_in_main_ranking_and_downloads_without_a_fabricated_tool_score(self):
        row = self.by_id["ClefFlashQ8"]
        self.assertEqual(row["context"]["counts"]["correct"], 110)
        self.assertEqual(row["context"]["groups"]["split"]["test"]["correct"], 59)
        self.assertIsNone(row["tool_proposal"])
        self.assertEqual(row["tool_proposal_status"], "not_run")
        views = results.outputs(self.data)
        csv_rows = {r["observation"]: r for r in csv.DictReader(io.StringIO(views["docs/leaderboard/models.csv"]))}
        self.assertEqual(csv_rows["ClefFlashQ8"]["tool_agreement"], "")
        self.assertEqual(csv_rows["ClefFlashQ8"]["tool_status"], "not_run")
        self.assertEqual(csv_rows["ClefFlashQ8"]["all_correct"], "110")
        main_table = views["docs/RESULTS.md"].split("## Model quality\n", 1)[1].split("## Language", 1)[0]
        self.assertIn("Clef Flash · Q8 direct Metal", main_table)
        self.assertIn("| 110 | 59 | 63 | 25 | 22 | Not run |", main_table)
        task_rows = list(csv.DictReader(io.StringIO(views["docs/leaderboard/task-breakdown.csv"])))
        self.assertFalse(any(r["observation"] == "ClefFlashQ8" and r["task"] == "tool_proposal" for r in task_rows))

    def test_independent_task_rankings_keep_physics_test_reversal_and_capability_tie(self):
        rows = {(r["task"], r["observation"]): r for r in self.data["campaigns"]}
        clef, d3 = rows["physics", "ClefFlashQ8"], rows["physics", "D3FlashQ8Upstream"]
        self.assertEqual((clef["rank_all"], clef["rank_test"]), (1, 6))
        self.assertEqual((d3["rank_all"], d3["rank_test"]), (3, 1))
        self.assertEqual((clef["counts"]["correct"], clef["counts"]["by_split"]["test"]["correct"]), (41, 31))
        for key in ("ClefFlashQ8", "D3FlashQ8"):
            row = rows["capability", key]
            self.assertEqual((row["rank_all"], row["rank_test"]), (1, 1))
            self.assertEqual((row["counts"]["correct"], row["counts"]["total"]), (192, 192))
        records = list(csv.DictReader(io.StringIO(results.outputs(self.data)["docs/leaderboard/campaigns.csv"])))
        self.assertTrue(any(r["observation"] == "ClefFlashQ8" and r["task"] == "physics"
                            and r["test_correct"] == "31" and r["test_total"] == "36" for r in records))

    def test_passage_rankings_retain_partial_and_unrun_cases_and_separate_rotations(self):
        rows = {(r["task"], r["observation"]): r for r in self.data["campaigns"]}
        for obs, correct, rank in (("D3FlashQ4Metal", 126, 1), ("D3FlashQ8Upstream", 122, 2), ("ClefFlashQ8", 109, 3),
                                   ("D3miniMacos", 104, 4), ("D3miniQ8Metal", 102, 5), ("D3miniQ4Metal", 100, 6),
                                   ("D3nanoQ8Metal", 94, 7), ("D3nanoMacos", 93, 8), ("Vela03Macos", 93, 8), ("D3lite", 88, 10),
                                   ("D3liteMacos", 88, 10), ("D3liteQ8Metal", 88, 10)):
            row = rows["passage_answerability", obs]
            self.assertEqual((row["counts"]["correct"], row["counts"]["total"], row["rank_all"]), (correct, 128, rank))
        for task, obs, correct, total in (("passage_relevance", "D3miniMacos", 266, 512),
                                          ("passage_support", "D3miniMacos", 527, 768),
                                          ("passage_support", "Vela03Macos", 151, 768)):
            row = rows[task, obs]
            self.assertEqual((row["counts"]["correct"], row["counts"]["scored"], row["counts"]["total"]), (correct, total, total))
            self.assertEqual(row["status"], "complete")
        # The constant majority-class baselines quoted on the page match the scored class distribution.
        for change in ({"completion_status": "incomplete", "stop_reason": "bench_source_changed"},
                       {"stop_reason": "bench_source_changed"}):
            with self.changed_json(results.EVIDENCE + "passage-small-cpu-20261031/d3-lite.json",
                                   lambda d, change=change: d.update(change)):
                with self.assertRaisesRegex(ValueError, "not a complete verified run: D3liteMacos"):
                    results.build(self.root)
        score = json.loads((self.root / results.EVIDENCE / "passage-small-cpu-20261031/d3-mini.json").read_text())
        for axis, (_, hits, total) in results.PASSAGE_MAJORITY.items():
            classes = [v["total_decisions"] for v in score["choice_scores"][axis]["by_expected_label"].values()]
            self.assertEqual((max(classes), sum(classes)), (hits, total))
        partial = rows["passage_support", "Jev114"]
        self.assertEqual(partial["status"], "partial")
        self.assertIsNone(partial["rank_all"])
        self.assertEqual((partial["counts"]["correct"], partial["counts"]["scored"], partial["counts"]["total"]), (394, 514, 768))
        unrun = rows["passage_answerability", "Jev114"]
        self.assertEqual(unrun["status"], "not_run")
        self.assertIsNone(unrun["rank_all"])
        self.assertEqual(unrun["counts"]["statuses"]["missing"], 128)
        self.assertEqual(rows["passage_relevance_four_rotations", "Jev114"]["counts"]["total"], 2048)
        self.assertNotIn(("passage_relevance", "Jev114"), rows)

    def test_contents_and_at_a_glance_open_the_page_and_every_anchor_resolves(self):
        text = results.render(self.data)
        lines = text.splitlines()
        self.assertLess(lines.index("## Contents"), lines.index("## At a glance"))
        self.assertLess(lines.index("## At a glance"), lines.index("## Coverage overview"))
        headings = {results.anchor(l[3:] if l.startswith("## ") else l[4:]) for l in lines if l.startswith(("## ", "### "))}
        anchors = re.findall(r"\]\(#([a-z0-9-]+)\)", text)
        self.assertTrue(anchors)
        self.assertEqual(set(anchors) - headings, set())
        glance = [l for l in lines if l.startswith("| ") and "| 192 (96 test) |" in l]
        self.assertEqual(len(glance), 1)
        self.assertIn("D3 mini · macOS CPU (192/192)", glance[0])
        self.assertIn("(tie)", glance[0])

    def test_facade_routing_ranks_models_with_the_private_router_row(self):
        rows = {r["observation"]: r for r in self.data["facade_routing"]}
        self.assertEqual(set(rows), {"FacadeRouterReplay", "D3liteMacos", "Vela03Macos", "D3nanoMacos", "D3miniMacos", "D3liteQ8Metal", "D3nanoQ8Metal", "D3miniQ8Metal",
                                     "D3miniQ4Metal", "D3FlashQ4Metal", "D3FlashMUzu"})
        router = rows["FacadeRouterReplay"]
        self.assertEqual((router["kind"], router["counts"]["all"]["correct"], router["paired"]), ("private_router_replay", 28, None))
        for row in rows.values():
            above = sum(o["counts"]["all"]["correct"] > row["counts"]["all"]["correct"] for o in rows.values())
            self.assertEqual(row["rank_all"], 1 + above)
            if row["kind"] == "classifier":
                pair = row["paired"]["all"]
                self.assertEqual(pair["both"] + pair["router_only"], 28)
                self.assertEqual(pair["both"] + pair["model_only"], row["counts"]["all"]["correct"])
        coverage = {r["id"]: r for r in self.data["coverage"]["observations"]}
        self.assertTrue(coverage["FacadeRouterReplay"]["router_observation"])
        self.assertEqual([k for k, c in coverage["FacadeRouterReplay"]["cells"].items() if c["evidence_present"]], ["facade_routing"])
        self.assertEqual(coverage["D3Q4"]["cells"]["facade_routing"]["status"], "not_run")
        text = results.render(self.data)
        self.assertIn("### Facade routing (model vs router)", text)
        self.assertIn("| Tool routing | Facade routing (model vs router) | 80 (48 test) | 11 |", text)
        passage_table = text.split("### Passage-only observations and ranking methods")[1].split("###")[0]
        self.assertNotIn("Production router", passage_table)
        self.assertNotIn("Facade routing", passage_table)
        page = results.render_model_pages(self.data)[results.MODEL_PAGES_DIR + "FacadeRouterReplay.md"]
        self.assertIn("not externally reproducible", page)
        self.assertIn("| Tool routing | [Facade routing (model vs router)](../../RESULTS.md#facade-routing-model-vs-router) | 28/80 | 10/48 |", page)
        with self.changed_json(results.FACADE, lambda d: d["runs"][0]["identity"].update(model_revision="0" * 40)):
            with self.assertRaisesRegex(ValueError, "identity join failed"):
                results.build(self.root)
        with self.changed_json(results.FACADE, lambda d: d["runs"][0]["identity"].update(runtime_lock_sha256="0" * 64)):
            with self.assertRaisesRegex(ValueError, "identity join failed"):
                results.build(self.root)
        def abstain_once(d):
            c = d["runs"][0]["counts"]["all"]
            c["statuses"] = {"ok": 79, "abstain": 1}
        with self.changed_json(results.FACADE, abstain_once):
            data = results.build(self.root)
            cell = next(r for r in data["coverage"]["observations"] if r["id"] == "D3liteMacos")["cells"]["facade_routing"]
            self.assertEqual((cell["scored_or_valid"], cell["outcomes"]["abstain"]), (80, 1))
        # Ranking stays a passage column: adding a task must not shift it into the generated-JSON columns.
        bge = text.split("### Passage-only observations and ranking methods")[1].split("###")[0]
        self.assertIn("BGE v2-m3", bge)
        self.assertIn("Ranking R0–3 /512", bge)
        self.assertNotIn("ranking None/None", text)
        with self.changed_json(results.FACADE, lambda d: d.update(dataset_sha256="0" * 64)):
            with self.assertRaisesRegex(ValueError, "changed pack"):
                results.build(self.root)

    def test_metal_gguf_rows_join_by_file_and_binary_and_tiers_are_ranked(self):
        mini = self.by_id["D3miniQ8Metal"]
        self.assertEqual((mini["context"]["counts"]["correct"], mini["identity"]["runtime"]["backend"]), (119, "metal"))
        rows = {(r["task"], r["observation"]): r for r in self.data["campaigns"]}
        self.assertEqual((rows["capability", "D3miniQ8Metal"]["counts"]["correct"], rows["capability", "D3miniQ8Metal"]["rank_all"]), (192, 1))
        tiers = {r["observation"]: r for r in self.data["facade_tiers"]}
        self.assertEqual(set(tiers), {"FacadeRouterReplay", "Vela03Macos", "D3liteQ8Metal", "D3nanoQ8Metal", "D3miniQ8Metal", "D3miniQ4Metal", "D3FlashQ4Metal", "D3FlashMUzu"})
        self.assertEqual((tiers["D3miniQ4Metal"]["rank_complex"], tiers["D3miniQ8Metal"]["rank_complex"],
                          tiers["FacadeRouterReplay"]["rank_complex"]), (1, 2, 8))
        for row in tiers.values():
            self.assertEqual((row["advanced"]["all"]["total"], row["complex"]["all"]["total"]), (96, 96))
        coverage = {r["id"]: r for r in self.data["coverage"]["observations"]}
        self.assertEqual(coverage["D3miniQ8Metal"]["cells"]["facade_routing"]["numerator"], 79)
        text = results.render(self.data)
        self.assertIn("### Facade routing: harder tiers", text)
        source = results.EVIDENCE + "d3-small-gguf-metal-20261101/d3-mini.json"
        with self.changed_json(source, lambda d: d["model"].update(sha256="0" * 64)):
            with self.assertRaisesRegex(ValueError, "GGUF model/asset identity mismatch"):
                results.build(self.root)
        with self.changed_json(results.FACADE_EASY_METAL, lambda d: d["runs"][0]["identity"].update(binary_sha256="0" * 64)):
            with self.assertRaisesRegex(ValueError, "identity join failed"):
                results.build(self.root)
        cells = {r["id"]: r["cells"]["facade_routing"] for r in self.data["coverage"]["observations"]}
        self.assertEqual(cells["D3nanoQ8Metal"]["source"], results.FACADE_EASY_METAL)
        self.assertEqual(cells["D3nanoMacos"]["source"], results.FACADE)
        tier_path = results.FACADE_TIERS["complex"][0]
        for field, value in (("model_sha256", "0" * 64), ("binary_sha256", "0" * 64), ("backend", "cuda")):
            def change(d, field=field, value=value):
                next(r for r in d["runs"] if r["label"] == "D3miniQ8Metal")["identity"][field] = value
            with self.subTest(field=field), self.changed_json(tier_path, change):
                with self.assertRaisesRegex(ValueError, "identity join failed for D3miniQ8Metal"):
                    results.build(self.root)
        def vela(d):
            next(r for r in d["runs"] if r["label"] == "Vela03Macos")["identity"]["runtime_lock_sha256"] = "0" * 64
        with self.changed_json(results.FACADE_TIERS["advanced"][0], vela):
            with self.assertRaisesRegex(ValueError, "identity join failed for Vela03Macos"):
                results.build(self.root)
        with self.changed_json(tier_path, lambda d: d.update(dataset_sha256="0" * 64)):
            with self.assertRaisesRegex(ValueError, "changed complex pack"):
                results.build(self.root)

    def test_review_packs_render_and_join_by_identity(self):
        review = self.data["review_packs"]
        rel = {r["observation"]: r for r in review["relevance"]["rows"]}
        self.assertEqual((rel["D3miniQ8Metal"]["counts"]["all"]["correct"], rel["D3miniQ8Metal"]["counts"]["majority_baseline"]), (406, 384))
        hitl = {r["observation"]: r for r in review["hitl"]["rows"]}
        self.assertEqual(hitl["D3miniQ8Metal"]["explicit_option"]["test_by_kind"]["hitl_confirm"]["asks_human"], 9)
        self.assertIsNone(hitl["FacadeRouterReplay"]["own_confidence"]["threshold"])
        text = results.render(self.data)
        self.assertIn("### Passage relevance v2 (three levels)", text)
        self.assertIn("### Facade routing: human confirmation", text)
        def change(d):
            d["candidates"][-1]["identities"][0]["model_sha256"] = "0" * 64
        with self.changed_json(results.REVIEW_HITL, change):
            with self.assertRaisesRegex(ValueError, "identity join failed"):
                results.build(self.root)
        with self.changed_json(results.REVIEW_RELEVANCE, lambda d: d["packs"].update({"passage-relevance-v2": "0" * 64})):
            with self.assertRaisesRegex(ValueError, "changed relevance pack"):
                results.build(self.root)

    def test_deployment_variants_render_and_reject_changed_variants(self):
        deployment = self.data["deployment"]
        self.assertEqual(set(deployment["variants"]), set(results.DEPLOYMENT_VARIANTS))
        facade = deployment["packs"]["facade-routing-v1"]["variants"]
        self.assertEqual((facade["D3miniQ4Metal"]["correct"], facade["D3FlashMUzu"]["correct"]), (79, 78))
        self.assertEqual(facade["D3FlashMUzu"]["paired_with_same_model"]["variant"], "D3FlashQ4Metal")
        self.assertEqual({len(v["rounds"]) for t_ in deployment["timing"].values() for v in t_.values()}, {3})
        text = results.render(self.data)
        self.assertIn("### Deployment variants: Q4 and Uzu", text)
        self.assertIn("**Repeated timing.**", text)
        with self.changed_json(results.DEPLOYMENT, lambda d: d["variants"].pop("D3FlashMUzu")):
            with self.assertRaisesRegex(ValueError, "changed schema or variants"):
                results.build(self.root)
        with self.changed_json(results.DEPLOYMENT, lambda d: d["variants"]["D3FlashMUzu"]["runtime"].update(binary_sha256="0" * 64)):
            with self.assertRaisesRegex(ValueError, "another runtime than its observation"):
                results.build(self.root)

    def test_deployment_variants_are_observations_joined_on_every_pack(self):
        uzu = self.by_id["D3FlashMUzu"]
        self.assertEqual(uzu["identity"]["runtime"]["backend"], "uzu")
        self.assertIsNone(uzu["identity"]["runtime"]["backend_observed"])
        self.assertEqual(uzu["metadata"]["runtime_group"], "apple_uzu")
        tiers = {r["observation"]: r for r in self.data["facade_tiers"]}
        self.assertTrue({"D3miniQ4Metal", "D3FlashQ4Metal", "D3FlashMUzu"} <= set(tiers))
        rel = {r["observation"] for r in self.data["review_packs"]["relevance"]["rows"]}
        hitl = {r["observation"] for r in self.data["review_packs"]["hitl"]["rows"]}
        self.assertTrue({"D3miniQ4Metal", "D3FlashQ4Metal", "D3FlashMUzu"} <= rel & hitl)
        page = results.render_model_pages(self.data)[results.MODEL_PAGES_DIR + "D3FlashMUzu.md"]
        self.assertIn("## Routing tiers, relevance v2 and human confirmation", page)
        def change(d):
            d["runs"][-1]["identity"]["binary_sha256"] = "0" * 64
        with self.changed_json(results.FACADE_VARIANTS["complex"], change):
            with self.assertRaisesRegex(ValueError, "identity join failed"):
                results.build(self.root)
        with self.changed_json(results.REVIEW_VARIANTS["hitl"], lambda d: d["candidates"].pop()):
            with self.assertRaisesRegex(ValueError, "changed hitl variant roster"):
                results.build(self.root)
        uzu_export = "docs/evidence/deployment-variants-20261101/uzu-d3-flash-m.json"
        with self.changed_json(uzu_export, lambda d: d["runtime"].update(backend_observed="metal")):
            with self.assertRaisesRegex(ValueError, "Uzu runtime identity mismatch"):
                results.build(self.root)

    def test_executed_episodes_join_by_identity_and_rank_procedure_correct_cases(self):
        rows = {r["observation"]: r for r in self.data["choice_episodes"]}
        self.assertEqual(set(rows), {"D3liteMacos", "Vela03Macos", "D3nanoMacos", "D3miniMacos"})
        self.assertEqual(rows["Vela03Macos"]["counts"]["all"]["procedure_correct_cases"], 0)
        self.assertEqual(rows["Vela03Macos"]["execution"]["tool_calls_executed"], 0)
        for row in rows.values():
            ranked_above = sum(o["counts"]["all"]["procedure_correct_cases"] > row["counts"]["all"]["procedure_correct_cases"] for o in rows.values())
            self.assertEqual(row["rank_all"], 1 + ranked_above)
        coverage = {r["id"]: r for r in self.data["coverage"]["observations"]}
        for oid, row in rows.items():
            cell = coverage[oid]["cells"]["choice_episodes"]
            self.assertEqual((cell["numerator"], cell["total"]), (row["counts"]["all"]["procedure_correct_cases"], 32))
        self.assertEqual(coverage["D3Q4"]["cells"]["choice_episodes"]["status"], "not_run")
        text = results.render(self.data)
        self.assertIn("### Executed tool episodes (closed choice)", text)
        self.assertIn("| Tool workflow, executed | Executed tool episodes (closed choice) | 32 (12 test) | 4 |", text)
        with self.changed_json(results.CHOICE_EPISODES, lambda d: d["runs"][0]["identity"].update(model_revision="0" * 40)):
            with self.assertRaisesRegex(ValueError, "identity join failed"):
                results.build(self.root)

    def test_model_pages_show_every_task_with_ranks_execution_and_reports(self):
        pages = results.render_model_pages(self.data)
        index = pages[results.MODEL_PAGES_DIR + "README.md"]
        self.assertIn("| [D3 mini · macOS CPU](D3miniMacos.md) | 119/132 (#", index)
        self.assertIn("| 192/192 (#1) | 39/48 (#3) |", index)
        mini = pages[results.MODEL_PAGES_DIR + "D3miniMacos.md"]
        self.assertIn("| Tool workflow | [Capability and workflow choices](../../RESULTS.md#capability-choices) | 192/192 | 96/96 | 1 | 1 | all `ok` | [report](../../D3_MINI_MACOS_RESULTS_20261031.md) |", mini)
        self.assertIn("| Retrieved evidence | [Passage relevance](../../RESULTS.md#passage-relevance) | 266/512 | no split ranking | 2 | — | all `ok` | [report](../../PASSAGE_SMALL_CPU_RESULTS_20261031.md) |", mini)
        self.assertIn("| Retrieved evidence | [Passage ranking](../../leaderboard/other-benchmarks.md#passage-ranking-and-evidence) | not run | — | — | — | — | — |", mini)
        nano = pages[results.MODEL_PAGES_DIR + "D3nanoMacos.md"]
        self.assertIn("| 188/192 | 92/96 |", nano)
        jev = pages[results.MODEL_PAGES_DIR + "Jev114.md"]
        self.assertIn("partial", jev)
        # An attempted campaign with nothing scored keeps its outcomes; it is not "not run".
        self.assertIn("| 0/128 scored (attempted, nothing scored) | — | — | — | 128 `missing` |", jev)
        bge = pages[results.MODEL_PAGES_DIR + "BGEPassage.md"]
        self.assertIn("nDCG@1 0.922 (480/480 defined of 512)", bge)
        self.assertNotIn("0/512", bge)
        self.assertNotIn("0/512", index)
        for path in pages:
            self.assertFalse(results.MODEL_PAGES_DIR.rstrip("/").endswith("/models"))
            ignored = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0
            self.assertFalse(ignored, f"generated page would be ignored by git: {path}")
        for path, text in pages.items():
            for link in re.findall(r"\]\((\.\./\.\./[^)#]+)", text):
                target = ROOT / link[9:] if link.startswith("../../../") else ROOT / "docs" / link[6:]
                self.assertTrue(target.exists(), (path, link))

    def test_coverage_matrix_keeps_runtime_boundaries_and_actual_missing_examples(self):
        coverage = self.data["coverage"]
        rows = {r["id"]: r for r in coverage["observations"]}
        self.assertEqual({k for k, r in rows.items() if r["context_observation"]}, EXPECTED_LABELS)
        # 40 context rows, five passage-only methods, one generative candidate, one private router replay.
        self.assertEqual(len(rows), 47)
        self.assertEqual({len(r["cells"]) for r in rows.values()}, {14})
        generative = rows["QwenToolPolicyV2"]
        self.assertTrue(generative["generative_observation"])
        self.assertFalse(generative["context_observation"])
        for task, numerator, total in (("tool_discovery", 3, 10), ("tool_arguments", 6, 6), ("tool_episodes", 7, 18)):
            cell = generative["cells"][task]
            self.assertEqual((cell["status"], cell["numerator"], cell["scored_or_valid"], cell["total"], cell["metric"]),
                             ("complete", numerator, total, total, "case_pass"))
        self.assertEqual(generative["cells"]["context"]["status"], "not_run")
        self.assertEqual(rows["D3FlashQ8Upstream"]["cells"]["tool_discovery"]["status"], "not_run")
        self.assertEqual(rows["D3FlashQ8Upstream"]["cells"]["tool_discovery"]["metric"], "case_pass")
        gateway, direct = rows["D3FlashQ8"]["cells"], rows["D3FlashQ8Upstream"]["cells"]
        self.assertEqual(gateway["capability"]["status"], "complete")
        self.assertEqual(direct["capability"]["status"], "not_run")
        self.assertEqual(gateway["physics"]["status"], "not_run")
        self.assertEqual(direct["physics"]["status"], "complete")
        # Same model name/weights do not merge different runtime fingerprints.
        self.assertEqual(rows["D3lite"]["cells"]["passage_relevance"]["status"], "not_run")
        self.assertEqual(rows["D3litePassage"]["cells"]["passage_relevance"]["scored_or_valid"], 512)
        self.assertEqual(rows["Jev"]["cells"]["passage_support"]["status"], "not_run")
        partial = rows["Jev114"]["cells"]["passage_support"]
        self.assertEqual((partial["status"], partial["scored_or_valid"], partial["total"]), ("partial", 514, 768))
        self.assertEqual((partial["outcomes"]["error"], partial["outcomes"]["missing"]), (2, 252))
        explicit = rows["Jev114"]["cells"]["passage_answerability"]
        absent = rows["ClefFlashQ8"]["cells"]["tool_proposal"]
        self.assertEqual((explicit["status"], explicit["scored_or_valid"], explicit["evidence_present"]),
                         ("not_run", 0, True))
        self.assertIsNone(explicit["numerator"])
        self.assertEqual(explicit["outcomes"]["missing"], 128)
        self.assertEqual((absent["status"], absent["evidence_present"]), ("not_run", False))
        for field in ("scored_or_valid", "numerator", "outcomes", "source"):
            self.assertIsNone(absent[field])
        self.assertEqual(absent["metric"], "provisional_agreement")
        self.assertTrue(direct["physics"]["review_pending"])
        self.assertTrue(absent["review_pending"])
        self.assertEqual({c["status"] for r in rows.values() for c in r["cells"].values()},
                         {"complete", "partial", "not_run"})
        rendered = results.render(self.data)
        self.assertLess(rendered.index("## Coverage overview"), rendered.index("## Updated task rankings"))
        csv_rows = list(csv.DictReader(io.StringIO(results.outputs(self.data)["docs/leaderboard/coverage.csv"])))
        self.assertEqual(len(csv_rows), 47 * 14)
        self.assertIn("### Generated-JSON tool-policy observations", rendered)
        self.assertNotIn("| Discovery (JSON) /10 | Arguments", rendered.split("### Passage-only")[0])
        blank = next(r for r in csv_rows if r["observation"] == "ClefFlashQ8" and r["task"] == "tool_proposal")
        self.assertEqual((blank["scored_or_valid"], blank["unsupported"], blank["review_pending"]), ("", "", "True"))

    def test_coverage_ranking_is_not_classification_or_a_different_rotation_denominator(self):
        rows = {r["id"]: r["cells"] for r in self.data["coverage"]["observations"]}
        for key in ("D3litePassage", "Jev114"):
            self.assertEqual(rows[key]["passage_relevance_four_rotations"]["total"], 2048)
            ranking = rows[key]["passage_ranking"]
            self.assertEqual((ranking["total"], ranking["metric_defined"], ranking["metric_eligible"]), (512, 480, 480))
            self.assertEqual(ranking["metric"], "ndcg@1")
            self.assertIsNone(ranking["numerator"])
        self.assertEqual(rows["Jev114"]["passage_relevance"]["status"], "not_run")
        self.assertEqual(rows["ClefFlashQ8"]["passage_ranking"]["status"], "not_run")

    def test_harness_gaps_are_global_and_do_not_invent_model_unsupported_results(self):
        harness = {r["id"]: r for r in self.data["coverage"]["harness"]}
        self.assertEqual(harness["task_contract"]["status"], "fixture_only")
        self.assertEqual(harness["task_contract"]["issues"], [results.ISSUES + "9"])
        self.assertIn("no qualified model", harness["task_contract"]["boundary"])
        for key, issue in (("discovery", 10), ("arguments", 11), ("episodes", 12)):
            self.assertEqual(harness[key]["status"], "model_observed")
            self.assertEqual(harness[key]["issues"], [results.ISSUES + str(issue)])
            self.assertIn("One generative candidate", harness[key]["boundary"])
            self.assertIn("no application", harness[key]["boundary"].lower().replace("no application qualification", "no application"))
        self.assertIn("actual bounded lookup/sum", harness["arguments"]["boundary"])
        self.assertIn("7/18", harness["episodes"]["boundary"])
        for key, issue in (("small_large", 16), ("application", 17), ("rag_final", 18)):
            self.assertEqual(harness[key]["status"], "not_implemented")
            self.assertEqual(harness[key]["issues"], [results.ISSUES + str(issue)])
        self.assertEqual(harness["order_retention"]["status"], "partial_coverage")
        self.assertTrue(self.data["coverage"]["review_pending"])
        for row in self.data["coverage"]["observations"]:
            self.assertNotIn("discovery", row["cells"])
            self.assertNotIn("episodes", row["cells"])
            self.assertNotIn("rag_final", row["cells"])

    def test_coverage_rejects_zero_scored_and_inconsistent_denominators(self):
        zero = {"correct": 0, "scored": 0, "total": 48,
                "statuses": {s: (48 if s == "error" else 0) for s in results.STATUS_KEYS}}
        with self.assertRaisesRegex(results.ResultError, "zero scored"):
            results.coverage_cell(zero, 48, "synthetic-public-source.json")
        with self.assertRaisesRegex(results.ResultError, "denominator"):
            results.coverage_cell(zero, 47, "synthetic-public-source.json")
        observed = {"correct": 41, "scored": 48, "total": 48,
                    "statuses": {s: (48 if s == "ok" else 0) for s in results.STATUS_KEYS}}
        with self.assertRaisesRegex(results.ResultError, "lacks a source"):
            results.coverage_cell(observed, 48)
        # Unsupported is a recorded outcome only, never the label for a missing task.
        observed.update(scored=47)
        observed["statuses"].update(ok=47, unsupported=1)
        cell = results.coverage_cell(observed, 48, "synthetic-public-source.json")
        self.assertEqual((cell["status"], cell["outcomes"]["unsupported"]), ("partial", 1))

    def test_coverage_rejects_ranking_protocol_metric_and_source_mismatches(self):
        path = results.OTHER_SOURCES["passage_order"]
        mutations = [
            lambda a: a.update(cases=511),
            lambda a: a.update(rotations=[0]),
            lambda a: a["source"].update(choice_seal_sha256="a" * 64),
            lambda a: a["baseline_profile"].update(running_binary_sha256="a" * 64),
            lambda a: a["rankings"]["replacement"]["metrics"]["ndcg@1"].update(eligible_cases=512),
            lambda a: a["rankings"]["replacement"].update(scored_cases=0),
            lambda a: a["relevance_scores"].update(total_cases=2047),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.changed_json(path, mutation):
                with self.assertRaises(results.ResultError):
                    results.build(self.root)
        cpu = "docs/evidence/passage-cpu-20261015/analysis.json"
        with self.changed_json(cpu, lambda a: a["choice_model"].update(model_revision="a" * 40)):
            with self.assertRaisesRegex(results.ResultError, "passage model identity mismatch"):
                results.build(self.root)

    def test_recent_campaigns_fail_closed_on_identity_counts_macro_and_confusion_drift(self):
        clef = "docs/evidence/clef-flash-20261029/analysis.json"
        passage = "docs/evidence/passage-clef-flash-20261029/analysis.json"
        mutations = [
            (clef, lambda a: a["model"].update(model_sha256="a" * 64)),
            (clef, lambda a: a["runtime"].update(binary_sha256="b" * 64)),
            (clef, lambda a: a["phases"]["context"]["identity"].update(dataset_sha256="c" * 64)),
            (clef, lambda a: a["phases"]["context"]["counts"].update(scored_cases=0, passed_cases=0)),
            (clef, lambda a: a["phases"]["physics"]["groups"]["language"]["fr"].update(passed_cases=19)),
            (passage, lambda a: a["axes"]["support"].update(macro_accuracy_scored=float("nan"))),
            (passage, lambda a: a["axes"]["answerability"]["confusion"]["answerable"].update(answerable=86)),
            (passage, lambda a: a["coverage"].update(logical_decisions=1407)),
        ]
        for path, change in mutations:
            with self.subTest(path=path, mutation=change), self.changed_json(path, change):
                with self.assertRaises(results.ResultError):
                    results.build(self.root)

    def test_main_hub_includes_other_protocol_tables_with_working_relative_links(self):
        rendered = results.render(self.data)
        for heading in ("### Passage ranking and evidence", "### Longer contexts",
                        "### Repeated timing and stability", "### Initial documentary routing pilot"):
            self.assertIn(heading, rendered)
        self.assertIn("[passage dataset](../datasets/passage-evidence-v1/README.md)", rendered)
        self.assertIn("(evidence/passage-order-control-20261015/analysis.json)", rendered)
        self.assertNotIn("(../../datasets/", rendered)
        self.assertEqual(set(self.data["other_campaigns"]), {"passage_order", "length", "repeated_timing"})
        for item in self.data["other_campaigns"].values():
            self.assertIn(item["source"], self.data["sources_sha256"])
        self.assertNotIn('"rows":', json.dumps(self.data["other_campaigns"]))


if __name__ == "__main__":
    unittest.main()
