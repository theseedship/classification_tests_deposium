import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fetch_gguf", ROOT / "scripts/fetch-gguf.py")
fetch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch)


class FetchGgufTests(unittest.TestCase):
    def test_verify_checks_size_and_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.gguf"
            path.write_bytes(b"weights")
            digest = hashlib.sha256(b"weights").hexdigest()
            self.assertTrue(fetch.verify(path, 7, digest))
            self.assertFalse(fetch.verify(path, 8, digest))
            self.assertFalse(fetch.verify(path, 7, "0" * 64))
            self.assertFalse(fetch.verify(Path(tmp) / "absent", 7, digest))

    def test_refuses_untracked_manifest_and_output_outside_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "x-assets.json"
            manifest.write_text(json.dumps({"schema_version": "deposium.model-assets/v1"}))
            with patch("sys.stderr"):
                self.assertEqual(fetch.main(["--assets", str(manifest), "--output-dir", "results/models"]), 2)
                self.assertEqual(fetch.main(["--assets", "profiles/d3-lite-q8-assets.json", "--output-dir", tmp]), 2)

    def test_every_runbook_manifest_is_a_pinned_single_file(self):
        for name in ("d3-lite-q8", "d3-nano-q8", "d3-mini-q8", "d3-mini-q4", "d3-flash-q4",
                     "lfm3-1.7b-q4", "bge-reranker-v2-m3-q8"):
            assets = json.loads((ROOT / "profiles" / f"{name}-assets.json").read_text())
            self.assertEqual(assets["schema_version"], "deposium.model-assets/v1")
            self.assertRegex(assets["revision"], r"^[0-9a-f]{40}$")
            self.assertEqual(len(assets["files"]), 1)
            self.assertRegex(assets["files"][0]["sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
