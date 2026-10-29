"""Offline reference-grid controls are implementation checks, never model results."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check-reference-grids.py"


def import_grid(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


grids = import_grid("reference_grids_under_test")


class ReferenceGridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The real audit must complete without constructing execution adapters,
        # invoking a policy, or executing even the local synthetic tools.
        forbidden = (
            "socket.create_connection", "urllib.request.urlopen", "subprocess.Popen",
            "deposium_bench.adapters.create_adapter",
            "deposium_bench.synthetic_tools.FixtureStore.lookup",
            "deposium_bench.synthetic_tools.FixtureStore.sum",
            "deposium_bench.tool_episodes.EpisodeRuntime.lookup",
            "deposium_bench.tool_episodes.EpisodeRuntime.sum",
            "deposium_bench.tool_episodes.ReplayPolicy.predict",
            "deposium_bench.tool_episodes.run_episode",
            "deposium_bench.tool_episodes.FixtureEpisodeAdapter.predict",
        )
        with ExitStack() as stack:
            for target in forbidden:
                stack.enter_context(patch(target, side_effect=AssertionError(f"audit must not call {target}")))
            cls.report = grids.audit()
        cls.cases, cls.digest = grids.load_cases(ROOT / "datasets/physics-choice-v1/cases.jsonl")

    def check_small_pack(self, cases=None):
        return grids.check_choice_pack(
            self.cases[:1] if cases is None else cases,
            source="datasets/physics-choice-v1/cases.jsonl", digest=self.digest,
            reference_check="test_fixture_only")

    def test_actual_audit_has_nonzero_controls_and_separate_qualifications(self):
        report = self.report
        self.assertEqual(report["status"], "implementation_checks_passed")
        self.assertEqual(report["control_kind"], "scripted_not_model")
        self.assertEqual(report["semantic_truth"], "not_established_by_this_check")
        self.assertEqual(report["human_review"],
                         {"provided_by_this_check": 0, "status": "not_provided"})
        packs = report["choice_packs"]
        self.assertEqual(len(packs), 5)
        self.assertEqual(sorted(pack["cases"] for pack in packs), [2, 12, 48, 132, 192])
        self.assertEqual(sum(pack["cases"] for pack in packs), 386)
        self.assertEqual(sum(pack["positive_controls"] for pack in packs), 390)
        self.assertEqual(sum(pack["wrong_controls"] for pack in packs), 1144)
        self.assertEqual(sum(pack["empty_controls"] for pack in packs), 772)
        self.assertEqual(sum(pack["unscored_controls"] for pack in packs), 1544)
        execution = report["execution_fixtures"]
        self.assertEqual(len(execution), 2)
        for row, stem, count, families, adapter in zip(
                execution, ("tool-arguments", "tool-episodes"), (4, 14), (2, 7),
                ("fixture_arguments", "fixture_episode")):
            self.assertEqual(row["source"], f"datasets/{stem}-v1/cases.jsonl")
            self.assertEqual((row["cases"], row["families"]), (count, families))
            self.assertEqual(row["languages"], {"en": families, "fr": families})
            self.assertEqual(row["counts_by_split"], {"train": count, "calibration": 0, "test": 0})
            self.assertEqual(row["profile_adapter"], adapter)
            for key in ("tool_execution", "policy_execution", "scorer_controls"):
                self.assertEqual(row[key], "not_run_by_this_check")
        for pack in packs:
            self.assertEqual(pack["sha256"], hashlib.sha256((ROOT / pack["source"]).read_bytes()).hexdigest())

    def test_passage_denominators_match_public_rows_and_control_scope_is_bounded(self):
        cases = [json.loads(line) for line in
                 (ROOT / "datasets/passage-evidence-v1/cases.jsonl").read_text().splitlines()]
        counts = {
            "ranking": len(cases),
            "relevance": sum(len(case["passages"]) for case in cases),
            "support": sum(len(case["passages"]) * len(case["annotations"]["claims"]) for case in cases),
            "answerability": len(cases),
        }
        passage = self.report["passage_pack"]
        self.assertEqual(passage["cases"], 1536)
        self.assertEqual(passage["projection_decisions"], counts)
        self.assertEqual(passage["control_subset"]["cases"], 32)
        self.assertEqual(passage["control_subset"]["families"], 8)
        self.assertEqual(passage["control_subset"]["source"], "plans/reference-review-pilot-v1.json")
        for axis, total, alternatives in (("relevance", 128, 4), ("support", 192, 3),
                                          ("answerability", 32, 3)):
            controls = passage["choice_controls"][axis]
            self.assertEqual(controls["total_decisions"], total)
            self.assertEqual(controls["positive_controls"], total)
            self.assertEqual(controls["wrong_controls"], (alternatives - 1) * total)
            self.assertEqual(controls["empty_controls"], 2)
            self.assertEqual(controls["unscored_controls"], 4 * total)

    def test_falsely_permissive_scorer_cannot_certify_grid(self):
        fake = {"scored": True, "passed": True, "checks": [], "reason": "fake"}
        with patch.object(grids, "score_case", return_value=fake), self.assertRaises(grids.AuditError):
            self.check_small_pack()

    def test_report_fingerprints_executed_sources_and_runtime(self):
        hashes = self.report["sources_sha256"]
        for path in ("scripts/check-reference-grids.py", "deposium_bench/scoring.py",
                     "deposium_bench/physics_corpus.py", "deposium_bench/passage_dataset.py",
                     "deposium_bench/tool_episodes.py", "deposium_bench/adapters.py",
                     "datasets/tool-episodes-v1/cases.jsonl", "datasets/tool-episodes-v1/manifest.json",
                     "profiles/tool-episodes-control.json", "fixtures/tool-episodes-control.jsonl"):
            self.assertEqual(hashes[path], hashlib.sha256((ROOT / path).read_bytes()).hexdigest())
        self.assertEqual(self.report["runtime"]["python"], ".".join(map(str, sys.version_info[:3])))
        self.assertEqual(self.report["scorer_version"], "deposium.exact/v1")

    def test_episode_inventory_rejects_reference_missing_mandatory_budget_guard(self):
        source = ROOT / "datasets/tool-episodes-v1/cases.jsonl"
        cases = [json.loads(line) for line in source.read_text().splitlines()]
        cases[0]["reference"]["assertions"] = [
            item for item in cases[0]["reference"]["assertions"]
            if item["path"] != "/checks/budgets_respected"]
        load_cases = grids.load_cases
        with tempfile.TemporaryDirectory() as directory:
            malformed = Path(directory) / "cases.jsonl"
            malformed.write_text("".join(json.dumps(case) + "\n" for case in cases))

            def load(path):
                return load_cases(malformed if path == source else path)

            with patch.object(grids, "load_cases", side_effect=load), self.assertRaises(grids.AuditError):
                grids.execution_fixture_inventory(ROOT, {})

    def test_episode_inventory_rejects_stale_manifest_and_control_hashes(self):
        read_json = grids.read_json
        manifest_path = "datasets/tool-episodes-v1/manifest.json"
        for key in ("cases_sha256", "control_profile_sha256", "control_recordings_sha256"):
            with self.subTest(field=key):
                def read(root, path):
                    value = read_json(root, path)
                    if path == manifest_path:
                        value[key] = "0" * 64
                    return value

                with patch.object(grids, "read_json", side_effect=read), self.assertRaises(grids.AuditError):
                    grids.execution_fixture_inventory(ROOT, {})

    def test_episode_inventory_requires_explicit_harness_control_profile(self):
        load_profile = grids.load_profile

        def load(path):
            profile, digest = load_profile(path)
            if path.name == "tool-episodes-control.json":
                profile["qualification"] = "model_run"
            return profile, digest

        with patch.object(grids, "load_profile", side_effect=load), self.assertRaises(grids.AuditError):
            grids.execution_fixture_inventory(ROOT, {})

    def test_rejecting_everything_is_also_an_audit_failure(self):
        fake = {"scored": True, "passed": False, "checks": [], "reason": "fake"}
        with patch.object(grids, "score_case", return_value=fake), self.assertRaises(grids.AuditError):
            self.check_small_pack()

    def test_falsely_permissive_passage_scorer_cannot_certify_grid(self):
        cases, digest = grids.passages.load_dataset(ROOT / "datasets/passage-evidence-v1/cases.jsonl")
        plan = json.loads((ROOT / "plans/reference-review-pilot-v1.json").read_text())
        selected_ids = {row["case_id"] for row in plan["cases"] if row["dataset"] == "passage"}
        score_choices = grids.passages.score_choices

        def lie(*args, **kwargs):
            report = deepcopy(score_choices(*args, **kwargs))
            if report["scored_cases"]:
                for row in report["rows"]:
                    if row["status"] == "ok":
                        row["accuracy"] = 1
                report["accuracy_over_all"] = 1
            return report

        with patch.object(grids.passages, "score_choices", side_effect=lie), self.assertRaises(grids.AuditError):
            grids.check_passage_pack(cases, digest, selected_ids)

    def test_empty_scorer_result_does_not_pass(self):
        with patch.object(grids, "score_case", return_value={}), self.assertRaises(grids.AuditError):
            self.check_small_pack()

    def test_zero_case_pack_cannot_certify_grid(self):
        with self.assertRaises(grids.AuditError):
            self.check_small_pack([])

    def test_missing_corpora_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(grids.AuditError):
            grids.audit(Path(directory))

    def test_false_pass_for_missing_results_is_rejected(self):
        summarize = grids.summarize

        def lie(cases, results):
            report = deepcopy(summarize(cases, results))
            if report["scored_cases"] == 0:
                report["verdict"] = "pass"
            return report

        with patch.object(grids, "summarize", side_effect=lie), self.assertRaises(grids.AuditError):
            self.check_small_pack()

    def test_main_emits_json_report_without_creating_files(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            previous = Path.cwd()
            try:
                os.chdir(directory)
                with patch.object(grids, "audit", return_value=self.report), \
                        redirect_stdout(stdout), redirect_stderr(stderr):
                    status = grids.main([])
                self.assertEqual(list(Path(directory).iterdir()), [])
            finally:
                os.chdir(previous)
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(stdout.getvalue()), self.report)
        self.assertEqual(stderr.getvalue(), "")

    def test_main_does_not_emit_success_after_audit_failure(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(grids, "audit", side_effect=grids.AuditError("deliberate audit failure")), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                status = grids.main([])
            except SystemExit as error:
                status = error.code
        self.assertNotEqual(status, 0)
        self.assertNotIn("implementation_checks_passed", stdout.getvalue())

    def test_import_is_silent_and_does_not_read_datasets_or_run_controls(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("deposium_bench.cases.load_cases", side_effect=AssertionError("dataset read on import")), \
                patch("deposium_bench.scoring.score_case", side_effect=AssertionError("scoring on import")), \
                patch("deposium_bench.passage_dataset.load_dataset", side_effect=AssertionError("passages read on import")), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            module = import_grid("reference_grids_import_check")
        self.assertTrue(callable(module.audit))
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
