"""Adversarial publication checks against real temporary Git indexes."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "public_content_guard", ROOT / "scripts/check-public-content.py")
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class PublicContentGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve()
        self.git("init", "--quiet")
        self.write(".gitignore", ".private/\n")
        self.write("README.md", "Synthetic public benchmark fixture.\n")
        self.git("add", "--", ".gitignore", "README.md")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def write(self, name, value):
        target = self.repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)

    @staticmethod
    def fake_provider_value():
        # Construct a nonfunctional test marker without publishing a token-like
        # literal in this test's own indexed source.
        return "gh" + "p_" + "Z" * 40

    def check(self):
        stdout, stderr = StringIO(), StringIO()
        with patch.object(GUARD, "ROOT", self.repo), redirect_stdout(stdout), redirect_stderr(stderr):
            result = GUARD.main()
        printed = stdout.getvalue()
        self.assertEqual(stderr.getvalue(), "")
        report = json.loads(printed)
        self.assertEqual(report["status"], "failed" if result else "passed")
        return result, report, printed

    def test_ignored_confidential_file_stays_local_and_is_not_scanned(self):
        private_name = ".private/never-disclose.txt"
        payload = self.fake_provider_value()
        self.write(private_name, payload)
        self.assertEqual(self.git("check-ignore", "--", private_name).strip(), private_name.encode())
        result, report, printed = self.check()
        self.assertEqual(result, 0)
        self.assertEqual(report["findings"], {})
        self.assertNotIn(private_name, printed)
        self.assertNotIn(payload, printed)

    def test_forced_ignored_index_entry_fails_without_disclosing_name_or_value(self):
        private_name = ".private/never-disclose.txt"
        payload = self.fake_provider_value()
        self.write(private_name, payload)
        # Deliberate misuse only inside this disposable, synthetic Git fixture.
        self.git("add", "--force", "--", private_name)
        result, report, printed = self.check()
        self.assertEqual(result, 1)
        self.assertEqual(report["findings"].get("ignored_path_in_index"), 1)
        self.assertNotIn("provider_token", report["findings"])
        self.assertNotIn(private_name, printed)
        self.assertNotIn(payload, printed)

    def test_staged_provider_marker_fails_without_disclosing_name_or_value(self):
        name = "public-accidental-value.txt"
        payload = self.fake_provider_value()
        self.write(name, payload)
        self.git("add", "--", name)
        result, report, printed = self.check()
        self.assertEqual(result, 1)
        self.assertEqual(report["findings"].get("provider_token"), 1)
        self.assertNotIn(name, printed)
        self.assertNotIn(payload, printed)

    def test_unstaged_provider_marker_does_not_change_the_safe_index_result(self):
        name = "public-note.txt"
        self.write(name, "Reviewed public content.\n")
        self.git("add", "--", name)
        payload = self.fake_provider_value()
        self.write(name, payload)
        result, report, printed = self.check()
        self.assertEqual(result, 0)
        self.assertEqual(report["findings"], {})
        self.assertNotIn(name, printed)
        self.assertNotIn(payload, printed)

    def test_staged_personal_home_path_fails_without_disclosing_it(self):
        name = "public-accidental-path.txt"
        payload = "/home/" + "private-operator" + "/project"
        self.write(name, payload)
        self.git("add", "--", name)
        result, report, printed = self.check()
        self.assertEqual(result, 1)
        self.assertEqual(report["findings"].get("personal_home_path"), 1)
        self.assertNotIn(name, printed)
        self.assertNotIn(payload, printed)

    def test_unstaged_ignore_rule_removal_cannot_hide_a_forced_private_entry(self):
        private_name = ".private/never-disclose.txt"
        payload = "Synthetic confidential material without a token pattern.\n"
        self.write(private_name, payload)
        self.git("add", "--force", "--", private_name)
        # The committed policy still excludes this path, but a worktree-only
        # edit would make a naive check-ignore call accept it.
        self.write(".gitignore", "")
        unprotected = subprocess.run(
            ["git", "-C", str(self.repo), "check-ignore", "--no-index", "--", private_name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(unprotected.returncode, 1)
        result, report, printed = self.check()
        self.assertEqual(result, 1)
        self.assertEqual(report["findings"], {"ignore_policy_drift": 1})
        self.assertNotIn(private_name, printed)
        self.assertNotIn(payload.strip(), printed)

    def test_unindexed_nested_rule_cannot_reinclude_a_forced_private_entry(self):
        private_name = ".private/never-disclose.txt"
        policy_name = ".private/.gitignore"
        payload = "Synthetic confidential material without a token pattern.\n"
        # Exclude directory contents while allowing Git to read a nested policy.
        self.write(".gitignore", ".private/*\n")
        self.git("add", "--", ".gitignore")
        self.write(private_name, payload)
        self.git("add", "--force", "--", private_name)
        self.write(policy_name, "!never-disclose.txt\n")
        unprotected = subprocess.run(
            ["git", "-C", str(self.repo), "check-ignore", "--no-index", "--", private_name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(unprotected.returncode, 1)
        result, report, printed = self.check()
        self.assertEqual(result, 1)
        self.assertEqual(report["findings"], {"ignore_policy_drift": 1})
        self.assertNotIn(private_name, printed)
        self.assertNotIn(policy_name, printed)
        self.assertNotIn(payload.strip(), printed)


if __name__ == "__main__":
    unittest.main()
