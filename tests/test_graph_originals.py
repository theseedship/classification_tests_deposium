"""Offline guards for the private graph-original collection command."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/collect-graph-originals.py"
SPEC = importlib.util.spec_from_file_location("collect_graph_originals", SCRIPT)
assert SPEC and SPEC.loader
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


def synthetic_metadata() -> tuple[list[dict], dict]:
    owner = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    folders = [str(1001 + number) for number in range(9)]
    files = [
        {
            "document_id": f"document-{number:02d}",
            "file_name": f"document-{number:02d}.pdf",
            "bucket_name": "test-bucket",
            "filepath": f"{owner}/{folder}/document-{number:02d}.pdf",
            "bucket_path": f"{owner}/{folder}",
            "user_id": owner,
            "mime_type": "application/pdf",
            "active": True,
            "size": 100,
            "num_pages": 44,
        }
        for number, folder in enumerate(folders)
    ]
    return files, {"owner_tenant_id": owner, "folder_ids": folders}


class MetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.files_path = self.base / "files.json"
        self.scope_path = self.base / "scope.json"

    def parse(self, files: list[dict], scope: dict) -> list[dict]:
        self.files_path.write_text(json.dumps(files), encoding="utf-8")
        self.scope_path.write_text(json.dumps(scope), encoding="utf-8")
        return collector.parse_sources(self.files_path, self.scope_path)

    def test_valid_nine_pdf_corpus(self) -> None:
        files, scope = synthetic_metadata()
        sources = self.parse(files, scope)
        self.assertEqual(len(sources), 9)
        self.assertEqual(sum(row["num_pages"] for row in sources), 396)

    def test_rejects_wrong_tenant_folder_duplicate_size_type_and_pages(self) -> None:
        files, scope = synthetic_metadata()
        cases = {
            "tenant": lambda rows: rows[0].update(user_id="other-tenant"),
            "folder": lambda rows: rows[0].update(bucket_path=scope["owner_tenant_id"] + "/9999"),
            "duplicate": lambda rows: rows[1].update(document_id=rows[0]["document_id"]),
            "size": lambda rows: rows[0].update(size=collector.MAX_PDF_BYTES + 1),
            "type": lambda rows: rows[0].update(mime_type="image/png"),
            "pages": lambda rows: rows[0].update(num_pages=43),
        }
        for label, change in cases.items():
            with self.subTest(label=label):
                candidate = deepcopy(files)
                change(candidate)
                with self.assertRaises(collector.CollectionError):
                    self.parse(candidate, scope)


class PrivatePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (self.root / ".gitignore").write_text(
            "results/\ndatasets/private/\ndata/private/\n", encoding="utf-8"
        )
        self.output = self.root / "results/run"
        self.output.mkdir(parents=True)
        self.files = self.root / "results/files.json"
        self.scope = self.root / "datasets/private/scope.json"
        self.scope.parent.mkdir(parents=True)
        self.files.write_text("invalid json", encoding="utf-8")
        self.scope.write_text("invalid json", encoding="utf-8")

    def test_private_ignored_paths_accepted_before_metadata_read(self) -> None:
        actual = collector.validate_private_paths(
            self.files, self.scope, self.output, root=self.root
        )
        self.assertEqual(actual, (self.files.resolve(), self.scope.resolve(), self.output.resolve()))

    def test_rejects_public_input_before_parsing(self) -> None:
        public = self.root / "public.json"
        public.write_text("invalid json", encoding="utf-8")
        with self.assertRaisesRegex(collector.CollectionError, "input_not_in_ignored"):
            collector.collect(public, self.scope, self.output, root=self.root)

    def test_rejects_output_outside_results_and_unignored_input(self) -> None:
        wrong_output = self.root / "datasets/private/new-output"
        with self.assertRaisesRegex(collector.CollectionError, "output_not_under_results"):
            collector.validate_private_paths(self.files, self.scope, wrong_output, root=self.root)
        (self.root / ".gitignore").write_text(
            "results/\ndata/private/\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(collector.CollectionError, "private_path_not_git_ignored"):
            collector.validate_private_paths(self.files, self.scope, self.output, root=self.root)

    def test_rejects_symlink_escape_for_input_and_output(self) -> None:
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        external = outside / "private.json"
        external.write_text("{}", encoding="utf-8")
        linked_input = self.root / "results/linked.json"
        linked_input.symlink_to(external)
        with self.assertRaises(collector.CollectionError):
            collector.validate_private_paths(linked_input, self.scope, self.output, root=self.root)
        linked_output = self.root / "results/linked-output"
        linked_output.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(collector.CollectionError):
            collector.validate_private_paths(self.files, self.scope, linked_output, root=self.root)

    def test_rejects_tracked_output(self) -> None:
        tracked = self.output / "tracked.txt"
        tracked.write_text("fixture", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-f", "results/run/tracked.txt"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with self.assertRaises(collector.CollectionError):
            collector.validate_private_paths(self.files, self.scope, self.output, root=self.root)


if __name__ == "__main__":
    unittest.main()
