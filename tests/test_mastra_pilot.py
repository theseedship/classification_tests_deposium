"""Offline tests; no application checkout, model or Node dependency required."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import mastra_pilot as pilot


class MastraPilotTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.digest = pilot.load_review_dataset()

    def write_cases(self, root, rows):
        path = Path(root) / "cases.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        return path

    def test_review_remains_unscored(self):
        summary = pilot.review_summary()
        self.assertEqual((summary["cases"], summary["families"]), (24, 12))
        self.assertEqual(summary["cases_scored"], 0)
        self.assertEqual(summary["human_approved"], 0)
        self.assertEqual(summary["evaluation_status"], "not_run")

    def test_reference_changes_cannot_change_candidate_payload(self):
        row = deepcopy(self.rows[0])
        original = pilot.candidate_request(row)
        row["reference"] = {"acceptable_choices": ["unrelated"], "rationale": "SECRET GOLD"}
        row["split"] = "test"
        row["execution"] = {"fixture_id": "HIDDEN FIXTURE"}
        self.assertEqual(original, pilot.candidate_request(row))
        self.assertNotIn("SECRET GOLD", json.dumps(original))
        self.assertNotIn("HIDDEN FIXTURE", json.dumps(original))
        self.assertEqual(set(original["input"]), {"context", "question", "options"})
        self.assertIn(row["candidate_input"]["message"], original["input"]["context"])
        self.assertNotEqual(row["candidate_input"]["message"], original["input"]["question"])

    def test_rotation_maps_ids_without_reference(self):
        row = deepcopy(self.rows[0])
        row["reference"] = None
        row["candidate_input"]["options"].reverse()
        for item in row["candidate_input"]["options"]:
            answer = pilot.resolve_choice(row, {"choice_id": item["id"]})
            self.assertEqual(answer["action"], item["action"])
            self.assertIsNone(answer["semantic_score"])

    def test_empty_unknown_and_argument_injection_choices_rejected(self):
        for response in ({}, {"choice_id": ""}, {"choice_id": "not-an-option"},
                         {"choice_id": "a", "tenant_id": "spoof"}):
            with self.subTest(response=response), self.assertRaises(ValueError):
                pilot.resolve_choice(self.rows[0], response)

    def test_cross_split_translation_rejected(self):
        rows = deepcopy(self.rows)
        rows[1]["split"] = "test" if rows[0]["split"] == "calibration" else "calibration"
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "leakage"):
                pilot.load_review_dataset(self.write_cases(root, rows))

    def test_empty_duplicate_and_claimed_human_gold_rejected(self):
        approved = deepcopy(self.rows[:1])
        approved[0]["reference"]["review"] = "approved"
        for rows in ([], [self.rows[0], self.rows[0]], approved):
            with tempfile.TemporaryDirectory() as root:
                with self.assertRaises(ValueError):
                    pilot.load_review_dataset(self.write_cases(root, rows))

    def test_manifest_drift_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.write_cases(root, self.rows)
            (Path(root) / "manifest.json").write_text(json.dumps({"cases_file": path.name, "cases_sha256": "0"*64}))
            with self.assertRaisesRegex(ValueError, "manifest mismatch"):
                pilot.load_review_dataset(path)

    def test_preparation_is_immutable_and_has_separate_references(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "prepared"
            report = pilot.prepare_review(pilot.DATASET, target)
            raw = (target / "requests.jsonl").read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), report["requests_sha256"])
            for line in raw.splitlines():
                value = json.loads(line)
                self.assertEqual(set(value), {"case_id", "contract_id", "input"})
                self.assertNotIn("reference", value)
            with self.assertRaises(FileExistsError):
                pilot.prepare_review(pilot.DATASET, target)
            self.assertEqual(raw, (target / "requests.jsonl").read_bytes())

    def test_contract_oracle_rejects_empty_wrong_and_bool_outputs(self):
        control = {"expected": {"status": "ok", "output": {"documents": 1}}}
        for result in ({}, {"status": "ok", "output": None},
                       {"status": "ok", "output": {"documents": 0}},
                       {"status": "ok", "output": {"documents": True}}):
            self.assertFalse(pilot.check_control(control, result)["passed"])
        with self.assertRaises(ValueError):
            pilot.check_control({"expected": {}}, {})

    def test_native_timeout_is_distinct(self):
        with patch.object(pilot.subprocess, "run", side_effect=subprocess.TimeoutExpired("node", 30)):
            result = pilot._native({}, Path("/unused"))
        self.assertEqual(result["status"], "timeout")

    def test_native_response_cannot_belong_to_another_case(self):
        completed = subprocess.CompletedProcess([], 0, stdout=b'{"status":"ok","case_id":"other"}')
        with patch.object(pilot.subprocess, "run", return_value=completed):
            result = pilot._native({"case_id": "wanted"}, Path("/unused"))
        self.assertEqual(result["status"], "error")

    def test_refuses_output_in_application_before_snapshot(self):
        with tempfile.TemporaryDirectory() as root, patch.object(pilot, "_snapshot") as snapshot:
            with self.assertRaisesRegex(ValueError, "inside application"):
                pilot.run_native_controls(root, "0" * 40, Path(root) / "unsafe")
            snapshot.assert_not_called()

    def test_snapshot_uses_commit_even_when_worktree_differs(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root) / "app"
            repo.mkdir()
            def git(*args):
                return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL)
            git("init", "-q")
            git("config", "user.name", "fixture")
            git("config", "user.email", "fixture@example.invalid")
            for name in pilot.SOURCES:
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("committed bytes\n")
            git("add", ".")
            git("commit", "-qm", "fixture")
            revision = git("rev-parse", "HEAD").decode().strip()
            (repo / "node_modules").mkdir()
            changed = repo / pilot.SOURCES[0]
            changed.write_text("unrelated work in progress\n")
            target = Path(root) / "snapshot"
            target.mkdir()
            provenance = pilot._snapshot(repo, revision, target)
            self.assertEqual((target / pilot.SOURCES[0]).read_text(), "committed bytes\n")
            self.assertEqual(changed.read_text(), "unrelated work in progress\n")
            self.assertFalse(provenance["application_worktree_executed"])

    def graph_snapshot_fixture(self, root, include_helper=True):
        repo = Path(root) / "app"
        repo.mkdir()
        def git(*args):
            return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL)
        git("init", "-q")
        git("config", "user.name", "fixture")
        git("config", "user.email", "fixture@example.invalid")
        for name in pilot.SOURCES:
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("committed bytes\n")
        (repo / pilot.SOURCES[0]).write_text("import { execute } from './deposium-graph-tool.js'\n")
        if include_helper:
            (repo / pilot.GRAPH_HELPER).write_text("export const execute = () => 'pinned'\n")
        git("add", ".")
        git("commit", "-qm", "fixture")
        (repo / "node_modules").mkdir()
        (repo / "node_modules/.package-lock.json").write_text('{}\n')
        target = Path(root) / "snapshot"
        target.mkdir()
        return repo, git("rev-parse", "HEAD").decode().strip(), target

    def test_new_factory_requires_committed_graph_helper_even_if_wip_has_it(self):
        with tempfile.TemporaryDirectory() as root:
            repo, revision, target = self.graph_snapshot_fixture(root, include_helper=False)
            (repo / pilot.GRAPH_HELPER).write_text("uncommitted repair")
            with self.assertRaisesRegex(ValueError, "pinned Git source"):
                pilot._snapshot(repo, revision, target)

    def test_new_helper_and_installed_lock_are_hashed(self):
        with tempfile.TemporaryDirectory() as root:
            repo, revision, target = self.graph_snapshot_fixture(root)
            provenance = pilot._snapshot(repo, revision, target)
            self.assertIn(pilot.GRAPH_HELPER, provenance["files_sha256"])
            self.assertEqual(provenance["installed_package_lock_sha256"], hashlib.sha256(b'{}\n').hexdigest())
            manifest = json.loads((target / ".deposium-snapshot.json").read_text())
            self.assertEqual(manifest["files_sha256"], provenance["files_sha256"])

    @unittest.skipUnless(shutil.which("node"), "optional Node snapshot verifier")
    def test_bridge_refuses_missing_or_modified_source_and_dependency_lock(self):
        for change in ("helper_missing", "helper_changed", "installed_lock_changed", "manifest_changed"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as root:
                repo, revision, target = self.graph_snapshot_fixture(root)
                pilot._snapshot(repo, revision, target)
                script = (f"import {{loadSnapshotIdentity}} from {json.dumps(pilot.SNAPSHOT_HELPER.as_uri())};"
                          "loadSnapshotIdentity(process.argv[1]).verify();")
                command = ["node", "--input-type=module", "-e", script, str(target)]
                self.assertEqual(subprocess.run(command, capture_output=True, timeout=10).returncode, 0)
                if change == "helper_missing":
                    (target / pilot.GRAPH_HELPER).unlink()
                elif change == "helper_changed":
                    (target / pilot.GRAPH_HELPER).write_text("changed committed code")
                elif change == "installed_lock_changed":
                    (repo / "node_modules/.package-lock.json").write_text('{"changed":true}')
                else:
                    manifest = json.loads((target / ".deposium-snapshot.json").read_text())
                    del manifest["files_sha256"][pilot.GRAPH_HELPER]
                    (target / ".deposium-snapshot.json").write_text(json.dumps(manifest))
                self.assertNotEqual(subprocess.run(command, capture_output=True, timeout=10).returncode, 0)


if __name__ == "__main__":
    unittest.main()
