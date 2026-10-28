"""Exercise inventory provenance using disposable, real Git repositories.

Fixtures use only local Git objects. No checkout outside TemporaryDirectory is
modified, and no user Git configuration, hooks, model or service is required.
"""

from __future__ import annotations

import builtins
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench.git_inventory import InventoryError, inspect_stack


class GitInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="deposium-inventory-")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.repo_counter = 0
        self.root = self.make_repo("stack")

    def git(self, root: Path, *args: str, input: str | None = None) -> str:
        env = os.environ.copy()
        # Ignore process-level overrides as well as configuration on this host.
        for name in list(env):
            if name.startswith("GIT_"):
                del env[name]
        env.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_TERMINAL_PROMPT="0",
        )
        result = subprocess.run(
            [
                "git", "-c", "user.name=Inventory Fixture",
                "-c", "user.email=inventory@example.invalid",
                "-c", "core.hooksPath=" + os.devnull,
                "-C", str(root), *args,
            ],
            input=input, text=True, capture_output=True, env=env, check=True,
        )
        return result.stdout.strip()

    def write(self, root: Path, path: str, content: str) -> Path:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def commit(self, root: Path, message: str = "fixture") -> str:
        self.git(root, "add", "--all")
        self.git(root, "commit", "--quiet", "-m", message)
        return self.git(root, "rev-parse", "HEAD")

    def make_repo(self, name: str | None = None) -> Path:
        self.repo_counter += 1
        root = self.workspace / (name or f"source-{self.repo_counter}")
        root.mkdir()
        self.git(root, "init", "--quiet", "--initial-branch=main")
        self.write(root, "seed.txt", "fixture\n")
        self.commit(root)
        return root

    def add_submodule(
        self, parent: Path, path: str = "component", source: Path | None = None,
    ) -> Path:
        source = source or self.make_repo()
        self.git(
            parent, "-c", "protocol.file.allow=always", "submodule", "add",
            "--quiet", str(source), path,
        )
        self.commit(parent, "add local submodule")
        return parent / path

    def component(self, inventory: dict, path: str) -> dict:
        matches = [row for row in inventory["components"] if row["path"] == path]
        self.assertEqual(len(matches), 1, f"Expected one component at {path!r}")
        return matches[0]

    def test_initialized_submodule_records_both_gitlinks_and_local_head(self) -> None:
        child = self.add_submodule(self.root)
        expected = self.git(child, "rev-parse", "HEAD")

        inventory = inspect_stack(self.root)
        component = self.component(inventory, "component")

        self.assertEqual(inventory["parent"]["head"], self.git(self.root, "rev-parse", "HEAD"))
        self.assertEqual(component["parent_path"], ".")
        self.assertTrue(component["declared"])
        self.assertEqual(component["state"], "initialized")
        self.assertEqual(component["head"], expected)
        self.assertEqual(component["gitlink_head"], expected)
        self.assertEqual(component["gitlink_index"], expected)
        self.assertTrue(component["head_matches_gitlink"])
        self.assertFalse(component["dirty"])

    def test_local_head_drift_does_not_change_recorded_parent_gitlink(self) -> None:
        child = self.add_submodule(self.root)
        recorded = self.git(child, "rev-parse", "HEAD")
        self.write(child, "new.txt", "a new local revision\n")
        actual = self.commit(child)

        component = self.component(inspect_stack(self.root), "component")

        self.assertEqual(component["gitlink_head"], recorded)
        self.assertEqual(component["gitlink_index"], recorded)
        self.assertEqual(component["head"], actual)
        self.assertFalse(component["head_matches_gitlink"])

    def test_empty_uninitialized_child_does_not_inherit_parent_head(self) -> None:
        child = self.add_submodule(self.root)
        recorded = self.git(child, "rev-parse", "HEAD")
        self.git(self.root, "submodule", "deinit", "--force", "--", "component")
        self.assertTrue(child.is_dir())
        self.assertEqual(list(child.iterdir()), [])

        component = self.component(inspect_stack(self.root), "component")

        self.assertEqual(component["state"], "uninitialized")
        self.assertIsNone(component["head"])
        self.assertEqual(component["gitlink_head"], recorded)

    def test_parent_reports_staged_unstaged_and_untracked_separately(self) -> None:
        self.write(self.root, "unstaged.txt", "old\n")
        self.commit(self.root)
        self.write(self.root, "seed.txt", "staged\n")
        self.git(self.root, "add", "--", "seed.txt")
        self.write(self.root, "unstaged.txt", "changed\n")
        self.write(self.root, "new.txt", "untracked\n")

        parent = inspect_stack(self.root)["parent"]

        self.assertTrue(parent["dirty"])
        self.assertEqual(parent["status_counts"], {
            "staged": 1, "unstaged": 1, "untracked": 1, "conflicted": 0,
        })

    def test_child_reports_its_own_worktree_counts(self) -> None:
        child = self.add_submodule(self.root)
        self.write(child, "unstaged.txt", "old\n")
        self.commit(child)
        self.git(self.root, "add", "--", "component")
        self.commit(self.root)
        self.write(child, "seed.txt", "staged\n")
        self.git(child, "add", "--", "seed.txt")
        self.write(child, "unstaged.txt", "changed\n")
        self.write(child, "new.txt", "untracked\n")

        component = self.component(inspect_stack(self.root), "component")

        self.assertTrue(component["dirty"])
        self.assertEqual(component["status_counts"], {
            "staged": 1, "unstaged": 1, "untracked": 1, "conflicted": 0,
        })

    def test_new_gitmodules_declaration_is_visible_without_gitlink(self) -> None:
        self.write(
            self.root, ".gitmodules",
            '[submodule "new capability"]\n\tpath = pending child\n\turl = /unused/local\n',
        )

        component = self.component(inspect_stack(self.root), "pending child")

        self.assertTrue(component["declared"])
        self.assertEqual(component["name"], "new capability")
        self.assertIsNone(component["gitlink_head"])
        self.assertIsNone(component["gitlink_index"])
        self.assertIsNone(component["head"])
        self.assertTrue(component["issues"])

    def test_removed_declaration_keeps_orphan_gitlink_visible(self) -> None:
        child = self.add_submodule(self.root)
        expected = self.git(child, "rev-parse", "HEAD")
        (self.root / ".gitmodules").unlink()

        component = self.component(inspect_stack(self.root), "component")

        self.assertFalse(component["declared"])
        self.assertEqual(component["gitlink_head"], expected)
        self.assertEqual(component["head"], expected)
        self.assertTrue(component["issues"])

    def test_gitlink_without_any_gitmodules_file_is_visible(self) -> None:
        source = self.make_repo()
        revision = self.git(source, "rev-parse", "HEAD")
        self.git(self.root, "update-index", "--add", "--cacheinfo", f"160000,{revision},orphan")
        self.git(self.root, "commit", "--quiet", "-m", "orphan gitlink")

        component = self.component(inspect_stack(self.root), "orphan")

        self.assertFalse(component["declared"])
        self.assertEqual(component["gitlink_head"], revision)
        self.assertIsNone(component["head"])
        self.assertTrue(component["issues"])

    def test_nested_submodules_and_paths_with_spaces_are_discovered(self) -> None:
        middle_source = self.make_repo("middle source")
        self.add_submodule(middle_source, "inner child")
        outer = self.add_submodule(self.root, "outer child", middle_source)
        self.git(
            self.root, "-c", "protocol.file.allow=always", "submodule",
            "update", "--init", "--recursive",
        )

        inventory = inspect_stack(self.root)
        inner = self.component(inventory, "outer child/inner child")

        self.assertEqual(inner["parent_path"], "outer child")
        self.assertEqual(inner["state"], "initialized")
        self.assertEqual(inner["head"], self.git(outer / "inner child", "rev-parse", "HEAD"))
        self.assertTrue(inner["head_matches_gitlink"])

    def test_staged_gitlink_is_distinct_from_gitlink_in_parent_head(self) -> None:
        child = self.add_submodule(self.root)
        recorded = self.git(child, "rev-parse", "HEAD")
        self.write(child, "next.txt", "new child revision\n")
        staged = self.commit(child)
        self.git(self.root, "add", "--", "component")

        inventory = inspect_stack(self.root)
        component = self.component(inventory, "component")

        self.assertEqual(component["gitlink_head"], recorded)
        self.assertEqual(component["gitlink_index"], staged)
        self.assertEqual(component["head"], staged)
        self.assertEqual(inventory["parent"]["status_counts"]["staged"], 1)

    def test_conflicted_gitlink_is_not_reported_as_clean_initialized(self) -> None:
        child = self.add_submodule(self.root)
        first = self.git(child, "rev-parse", "HEAD")
        self.write(child, "next.txt", "second revision\n")
        second = self.commit(child)
        index_info = (
            f"0 {'0' * 40}\tcomponent\n"
            f"160000 {first} 1\tcomponent\n"
            f"160000 {first} 2\tcomponent\n"
            f"160000 {second} 3\tcomponent\n"
        )
        self.git(self.root, "update-index", "--index-info", input=index_info)

        inventory = inspect_stack(self.root)
        component = self.component(inventory, "component")

        self.assertEqual(component["state"], "conflict")
        self.assertTrue(component["issues"])
        self.assertEqual(inventory["parent"]["status_counts"]["conflicted"], 1)
        self.assertTrue(inventory["parent"]["dirty"])

    def test_root_must_be_a_repository_root(self) -> None:
        plain = self.workspace / "not a repository"
        plain.mkdir()
        subdirectory = self.root / "ordinary directory"
        subdirectory.mkdir()

        for candidate in (plain, subdirectory, self.workspace / "absent"):
            with self.subTest(candidate=candidate):
                with self.assertRaises(InventoryError):
                    inspect_stack(candidate)

    def test_unsafe_declared_paths_do_not_traverse_outside_stack(self) -> None:
        outside = self.make_repo("outside")
        (self.root / "escaped link").symlink_to(outside, target_is_directory=True)
        self.write(
            self.root, ".gitmodules",
            '[submodule "parent traversal"]\n\tpath = ../outside\n\turl = /unused\n'
            '[submodule "symlink traversal"]\n\tpath = escaped link\n\turl = /unused\n',
        )

        inventory = inspect_stack(self.root)

        for path in ("../outside", "escaped link"):
            with self.subTest(path=path):
                component = self.component(inventory, path)
                self.assertEqual(component["state"], "invalid")
                self.assertIsNone(component["head"])
                self.assertTrue(component["issues"])

    def test_metadata_fingerprint_is_stable_and_secret_contents_are_never_read(self) -> None:
        child = self.add_submodule(self.root)
        secret = "private-body-must-never-be-read-8f346a"
        protected = {
            self.write(self.root, ".env", "API_TOKEN=" + secret + "\n"),
            self.write(child, ".env", "API_TOKEN=" + secret + "\n"),
        }
        original_builtin_open, original_io_open = builtins.open, io.open

        def guard_open(original):
            def guarded(file, *args, **kwargs):
                if isinstance(file, (str, bytes, os.PathLike)):
                    self.assertNotIn(Path(os.fsdecode(file)).absolute(), protected)
                return original(file, *args, **kwargs)
            return guarded

        with patch("builtins.open", guard_open(original_builtin_open)), patch(
            "io.open", guard_open(original_io_open),
        ):
            first = inspect_stack(self.root)
            second = inspect_stack(self.root)

        self.assertNotIn(secret, json.dumps(first))
        self.assertEqual(first["fingerprint_sha256"], second["fingerprint_sha256"])
        self.assertRegex(first["fingerprint_sha256"], r"^[0-9a-f]{64}$")
        expected_hash = hashlib.sha256((self.root / ".gitmodules").read_bytes()).hexdigest()
        self.assertEqual(first["parent"]["gitmodules_sha256"], expected_hash)
        with (self.root / ".gitmodules").open("a", encoding="utf-8") as handle:
            handle.write("\n# metadata changed\n")
        changed = inspect_stack(self.root)
        self.assertNotEqual(first["fingerprint_sha256"], changed["fingerprint_sha256"])


if __name__ == "__main__":
    unittest.main()
