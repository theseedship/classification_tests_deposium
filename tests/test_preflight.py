from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from deposium_bench.cli import main
from deposium_bench.preflight import build_preflight, write_manifest
from deposium_bench.registry import RegistryError, load_registry, validate_registry


def small_registry() -> dict:
    return {
        "schema_version": "deposium.stack-registry/v1",
        "components": [{"id": "component", "path": "component", "owner": "fixture",
                        "role": "Offline fixture", "packs": ["DOC"], "notes": "Synthetic source only.",
                        "contracts": [{"id": "document.plan", "entrypoint": {"path": "source.py"},
                                       "kind": "function", "levels": ["A"], "adapter_status": "planned",
                                       "assertions": ["Preserve document IDs."], "tests": []}]}],
        "external_dependencies": [],
    }


class RegistryTests(unittest.TestCase):
    def test_bundled_registry_identifies_only_four_available_function_bridges(self):
        registry, digest = load_registry()
        self.assertEqual(len(registry["components"]), 15)
        self.assertEqual(len(digest), 64)
        available = {c["id"] for item in registry["components"] for c in item["contracts"]
                     if c["adapter_status"] == "available"}
        self.assertEqual(available, {"mcps.document-plan", "mcps.document-followup",
                                     "mcps.scope-dispatch", "mcps.semantic-source-route"})

    def test_incomplete_or_ambiguous_registries_fail(self):
        invalid = []
        value = small_registry(); value["components"] = []; invalid.append(value)
        value = small_registry(); value["extra"] = True; invalid.append(value)
        value = small_registry(); value["components"] *= 2; invalid.append(value)
        value = small_registry(); value["components"][0]["contracts"] *= 2; invalid.append(value)
        value = small_registry(); value["components"][0]["contracts"][0]["assertions"] = []; invalid.append(value)
        value = small_registry(); value["components"][0]["contracts"][0]["levels"] = ["D"]; invalid.append(value)
        value = small_registry(); value["external_dependencies"] = [{"id": "db", "kind": "service", "description": "test", "required_by": ["absent"]}]; invalid.append(value)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(RegistryError):
                validate_registry(value)

    def test_paths_are_normalized_and_scoped(self):
        for path in ("../secret", "/tmp/secret", "a/../b", "a//b", "./a", ".git/config", "a\\b", "C:/data", "."):
            with self.subTest(path=path), self.assertRaises(RegistryError):
                value = small_registry()
                value["components"][0]["path"] = path
                validate_registry(value)

    def test_duplicate_json_keys_are_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "registry.json"
            path.write_text('{"schema_version":"old","schema_version":"new"}')
            with self.assertRaises(RegistryError):
                load_registry(path)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="deposium-preflight-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.root = self.folder / "stack"
        self.root.mkdir()
        self.git(self.root, "init", "-q")
        self.child = self.root / "component"
        self.child.mkdir()
        self.git(self.child, "init", "-q")
        (self.child / "source.py").write_text("raise RuntimeError('must never be imported')\n")
        self.git(self.child, "add", "source.py")
        self.git(self.child, "commit", "-qm", "source fixture")
        sha = self.git(self.child, "rev-parse", "HEAD").strip()
        (self.root / ".gitmodules").write_text('[submodule "component"]\n path = component\n')
        self.git(self.root, "add", ".gitmodules")
        self.git(self.root, "update-index", "--add", "--cacheinfo", f"160000,{sha},component")
        self.git(self.root, "commit", "-qm", "stack fixture")
        self.registry_path = self.folder / "registry.json"
        self.set_registry(small_registry())

    def git(self, root, *args):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
        return subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                               "-c", f"core.hooksPath={os.devnull}", "-C", str(root), *args],
                              check=True, capture_output=True, text=True, env=env).stdout

    def set_registry(self, value):
        self.registry_path.write_text(json.dumps(value))

    def inspect(self, **kwargs):
        return build_preflight(self.root, registry_path=self.registry_path, **kwargs)

    def test_clean_inspection_is_not_a_passed_evaluation(self):
        report = self.inspect()
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["evaluation"], {"status": "not_run", "cases_scored": 0, "campaign_ready": False})
        self.assertEqual(report["coverage"]["selected_contracts"], 1)
        self.assertEqual(report["coverage"]["source_files_present"], 1)
        self.assertEqual(report["runtime_provenance"]["status"], "not_observed")
        self.assertEqual(report["components"][0]["contracts"][0]["case_ids"], [])

    def test_changed_source_has_new_hash_without_exposing_content(self):
        before = self.inspect()
        sentinel = "PRIVATE_SENTINEL_DO_NOT_EMIT"
        (self.child / "source.py").write_text(sentinel)
        after = self.inspect()
        old_hash = before["components"][0]["contracts"][0]["entrypoint_file"]["sha256"]
        new_hash = after["components"][0]["contracts"][0]["entrypoint_file"]["sha256"]
        self.assertNotEqual(old_hash, new_hash)
        self.assertEqual(new_hash, hashlib.sha256(sentinel.encode()).hexdigest())
        self.assertNotIn(sentinel, json.dumps(after))
        self.assertEqual(after["status"], "attention")

    def test_source_absence_is_an_error_with_a_denominator(self):
        (self.child / "source.py").unlink()
        report = self.inspect()
        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["coverage"]["selected_contracts"], 1)
        self.assertEqual(report["coverage"]["source_files_present"], 0)
        self.assertIn("entrypoint_unavailable", {i["code"] for i in report["issues"]})

    def test_added_component_and_missing_registration_are_both_visible(self):
        value = small_registry()
        value["components"][0]["path"] = "old-path"
        self.set_registry(value)
        report = self.inspect()
        self.assertEqual(report["status"], "invalid")
        self.assertEqual({c["registry_status"] for c in report["components"]}, {"missing", "unregistered"})

    def test_omitted_component_is_visible_and_not_scored(self):
        value = small_registry()
        missing = deepcopy(value["components"][0])
        missing.update(id="optional", path="optional")
        missing["contracts"][0]["id"] = "optional.plan"
        value["components"].append(missing)
        self.set_registry(value)
        report = self.inspect(selected_components=["component"])
        omitted = next(c for c in report["components"] if c["id"] == "optional")
        self.assertFalse(omitted["selected"])
        self.assertEqual(omitted["omission_reason"], "not_selected")
        self.assertEqual(report["coverage"]["selected_contracts"], 1)
        self.assertFalse(report["evaluation"]["campaign_ready"])
        self.assertEqual(report["status"], "attention")

    def test_empty_stack_is_not_success(self):
        empty = self.folder / "empty"
        empty.mkdir()
        self.git(empty, "init", "-q")
        self.git(empty, "commit", "--allow-empty", "-qm", "empty")
        report = build_preflight(empty, registry_path=self.registry_path)
        self.assertEqual(report["status"], "invalid")
        self.assertIn("empty_stack", {i["code"] for i in report["issues"]})

    def test_unknown_and_duplicate_selections_fail(self):
        for selection in ([], ["absent"], ["component", "component"]):
            with self.subTest(selection=selection), self.assertRaises(RegistryError):
                self.inspect(selected_components=selection)

    def test_secret_and_symlink_entrypoints_are_not_read(self):
        (self.child / ".env").write_text("PRIVATE_SENTINEL")
        (self.child / "alias.py").symlink_to(self.child / ".env")
        for path in (".env", "alias.py"):
            value = small_registry()
            value["components"][0]["contracts"][0]["entrypoint"]["path"] = path
            self.set_registry(value)
            report = self.inspect()
            self.assertEqual(report["status"], "invalid")
            self.assertNotIn("PRIVATE_SENTINEL", json.dumps(report))
            self.assertIsNone(report["components"][0]["contracts"][0]["entrypoint_file"]["sha256"])

    def test_archive_is_exclusive_and_outside_the_stack(self):
        report = self.inspect()
        destination = self.folder / "archives" / "run.json"
        write_manifest(report, destination)
        original = destination.read_bytes()
        with self.assertRaises(FileExistsError):
            write_manifest(report, destination)
        self.assertEqual(destination.read_bytes(), original)
        with self.assertRaises(ValueError):
            write_manifest(report, self.root / "result.json")
        self.assertFalse((self.root / "result.json").exists())

    def test_cli_reports_warnings_and_strict_exit_without_execution(self):
        (self.child / "untracked.txt").write_text("fixture")
        args = ["preflight", "--stack-root", str(self.root), "--registry", str(self.registry_path), "--format", "json"]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "attention")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args + ["--strict"]), 2)
        with redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(main(args + ["--component", "wrong"]), 2)
        self.assertIn("unknown component", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
