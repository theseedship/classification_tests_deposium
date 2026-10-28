"""Focused regressions for graph archive parsing, Git path guards, and summaries."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import graph_comparison, graph_evidence, graph_review, graph_snapshot


class GraphFollowupTests(unittest.TestCase):
    def test_graph_archive_readers_reject_duplicate_keys_and_nonfinite_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for raw in ('{"outer":{"key":1,"key":2}}', '{"score":NaN}', '{"score":Infinity}'):
                path.write_text(raw, encoding="utf-8")
                with self.subTest(raw=raw):
                    with self.assertRaises(ValueError):
                        graph_snapshot._json(path)
                    with self.assertRaises(graph_evidence.GraphEvidenceError):
                        graph_evidence._read(path)
                    with self.assertRaises(graph_review.GraphReviewError):
                        graph_review._read_json(path)

    def test_private_path_guard_ignores_ambient_git_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (root / ".gitignore").write_text("results/\n", encoding="utf-8")
            private = root / "results" / "private.json"
            private.parent.mkdir()
            private.write_text("{}", encoding="utf-8")
            with patch.object(graph_evidence, "ROOT", root), patch.dict(
                    os.environ, {"GIT_DIR": str(root / "nonexistent-git-dir"),
                                 "GIT_INDEX_FILE": str(root / "wrong-index")}, clear=False):
                self.assertEqual(graph_evidence._private(private), private.resolve())

    def test_result_classes_separate_zero_edges_from_nonresults(self):
        classify = graph_comparison._result_class
        self.assertEqual(classify({"status": "ok", "outcome": "ok", "output": {"edges": []}}), "ok_zero_edges")
        self.assertEqual(classify({"status": "ok", "outcome": "ok", "output": {"edge_count": 0}}), "ok_zero_edges")
        self.assertEqual(classify({"status": "ok", "outcome": "ok", "output": {"path": {"edges": [{}]}}}), "ok_with_edges")
        self.assertEqual(classify({"status": "ok", "outcome": "ok", "output": {"nodes": []}}), "ok_edge_count_unknown")
        for outcome in ("not_implemented", "ambiguous", "error", "empty"):
            with self.subTest(outcome=outcome):
                self.assertEqual(classify({"status": "ok", "outcome": outcome, "output": {}}), outcome)
        self.assertEqual(classify({"status": "error", "outcome": "ok"}), "error")


if __name__ == "__main__":
    unittest.main()
