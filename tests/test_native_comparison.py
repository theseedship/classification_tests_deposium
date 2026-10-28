"""Native archive provenance is normalized offline, with version checks intact."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("native_comparison_analysis",
    Path(__file__).resolve().parents[1] / "scripts/analyze-model-comparison.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class NativeComparisonTests(unittest.TestCase):
    def test_native_version_quantization_and_runtime_remain_separate(self):
        profile = {"adapter": "systemone_local", "profile_id": "fixture", "revision": "a" * 40,
                   "model": {"repo_id": "fixture/gguf", "model_id": "fixture-model"}, "timeout_seconds": 30}
        provenance = {"adapter": "systemone_local", "identity_sha256": "b" * 64, "identity": {
            "model": {"revision": "a" * 40, "repo_id": "fixture/gguf", "sha256": "c" * 64,
                      "path": "/private/synthetic/fixture-Q4_K_M.gguf"},
            "runtime": {"revision": "d" * 40, "sha256": "e" * 64, "backend_requested": "metal"},
            "runtime_pin": {"sha256": "f" * 64}, "adapter_sha256": "0" * 64,
            "settings": {"context": 4096}, "max_rss_mb": 24576}}
        original = deepcopy(provenance)
        result = analysis._identity(profile, provenance)
        self.assertEqual(result["model_revision"], "a" * 40)
        self.assertEqual(result["source_revision"], "d" * 40)
        self.assertEqual(result["device"], "metal")
        self.assertEqual(result["settings"]["dtype"], "Q4_K_M")
        self.assertNotIn("/private", json.dumps(result))
        self.assertEqual(provenance, original)
        provenance["identity"]["model"]["revision"] = "9" * 40
        with self.assertRaisesRegex(analysis.AnalysisError, "model_revision_mismatch"):
            analysis._identity(profile, provenance)
