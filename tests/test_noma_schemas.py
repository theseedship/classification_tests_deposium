"""Noma profile, path and provenance contracts without loading any model."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench.adapters import parse_profile
from deposium_bench.campaigns import _prepare_profile
from deposium_bench.decision2_adapter import Decision2Adapter
from deposium_bench.noma_adapter import NomaAdapter, REPO_ID, REVISION, SOURCE_REPO, SOURCE_REVISION

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles/noma-cpu-context.json"


def profile():
    return json.loads(PROFILE.read_text())


def provenance_validator():
    schema = json.loads((ROOT / "schemas/campaign-v1.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator({**schema["properties"]["adapter_provenance"], "$defs": schema["$defs"]})


@unittest.skipUnless(Draft202012Validator, "optional jsonschema is not installed")
class NomaSchemaTests(unittest.TestCase):
    def test_profile_parser_and_schema_have_same_pinned_scope(self):
        schema = json.loads((ROOT / "schemas/candidate-v1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        valid = profile()
        validator.validate(valid)
        parse_profile(json.dumps(valid).encode())
        mutations = [
            lambda p: p["model"].update(max_rss_mb=8193),
            lambda p: p["model"].update(max_length=1025),
            lambda p: p["model"].update(threads=True),
            lambda p: p["model"].update(source_revision="0" * 40),
            lambda p: p["model"].update(repo_id="other/noma"),
            lambda p: p.update(revision="0" * 40),
            lambda p: p.update(capabilities=["mcps.document-plan"]),
            lambda p: p.update(qualification="component_replay"),
            lambda p: p.update(timeout_seconds=31),
        ]
        for mutate in mutations:
            candidate = deepcopy(valid)
            mutate(candidate)
            with self.subTest(candidate=candidate):
                self.assertFalse(validator.is_valid(candidate))
                with self.assertRaises(ValueError):
                    parse_profile(json.dumps(candidate).encode())

    def test_campaign_profile_absolutizes_paths_without_resolving_venv_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "bin").mkdir()
            (root / "bin/python").symlink_to(sys.executable)
            candidate = profile()
            candidate["model"]["runtime_python"] = "bin/python"
            source = root / "profile.json"
            source.write_text(json.dumps(candidate))
            prepared, _, _ = _prepare_profile(source)
            for key in ("local_dir", "source_dir", "runtime_python", "assets_manifest",
                        "source_manifest", "prompt_path", "runtime_lock"):
                self.assertTrue(os.path.isabs(prepared["model"][key]))
            self.assertEqual(prepared["model"]["runtime_python"], str(root / "bin/python"))
            self.assertTrue(Path(prepared["model"]["runtime_python"]).is_symlink())
            Draft202012Validator(json.loads((ROOT / "schemas/candidate-v1.schema.json").read_text())).validate(prepared)

    def test_missing_assets_do_not_spawn_or_gain_success_provenance(self):
        candidate = profile()
        validator = provenance_validator()
        with tempfile.TemporaryDirectory() as folder:
            candidate["model"]["local_dir"] = str(Path(folder) / "missing-model")
            with patch("deposium_bench.noma_adapter.subprocess.Popen",
                       side_effect=AssertionError("No child for missing model")):
                adapter = NomaAdapter(candidate, PROFILE)
            try:
                self.assertFalse(adapter.provenance["available"])
                validator.validate(adapter.provenance)
                promoted = deepcopy(adapter.provenance)
                promoted["available"] = True
                promoted.pop("availability_error")
                self.assertFalse(validator.is_valid(promoted))
                self.assertEqual(adapter.predict({"contract_id": "bench.context-choice", "input": {
                    "context": "x", "question": "y", "options": [
                        {"id": "a", "description": "A"}, {"id": "b", "description": "B"}]}})["status"], "missing")
            finally:
                adapter.close()

    def test_available_provenance_requires_source_runtime_and_exact_settings(self):
        candidate = profile()
        validator = provenance_validator()
        with tempfile.TemporaryDirectory() as folder:
            candidate["model"]["local_dir"] = str(Path(folder) / "missing-model")
            with patch("deposium_bench.noma_adapter.subprocess.Popen", side_effect=AssertionError("spawn")):
                adapter = NomaAdapter(candidate, PROFILE)
            success = deepcopy(adapter.provenance)
            adapter.close()
        h = "a" * 64
        def assets(repo, revision):
            return {"schema_version": "deposium.model-assets/v1", "repo_id": repo,
                    "revision": revision, "files": [{"path": "fixture.txt", "size": 1, "sha256": h}]}
        success.pop("availability_error")
        success.update(available=True, model_assets=assets(REPO_ID, REVISION),
                       source_assets=assets(SOURCE_REPO, SOURCE_REVISION),
                       assets_manifest_sha256=h, model_assets_sha256=h,
                       source_manifest_sha256=h, source_assets_sha256=h,
                       prompt_sha256=h, runtime_lock_sha256=h, runtime_python_sha256=h,
                       runtime_pins={"torch": "2.14.0+cpu"}, runtime={"torch": "2.14.0+cpu"},
                       settings={"device": "cpu", "dtype": "bfloat16", "threads": 2,
                                 "max_length": 1024, "max_rss_mb": 8192, "facts": True,
                                 "reference_time": "2026-10-03T00:00:00Z", "fork": False,
                                 "encoding_preflight": "official-noma-serializer"},
                       device="cpu", dtype="bfloat16", native_max_prefix_tokens=4096,
                       effective_max_input_tokens=1024, load_ms=1.0, load_rss_mb=6000.0)
        validator.validate(success)
        mutations = [
            lambda p: p.pop("source_assets"),
            lambda p: p.pop("runtime"),
            lambda p: p.pop("transport_sha256"),
            lambda p: p.pop("asset_helpers_sha256"),
            lambda p: p["source_assets"].update(revision="0" * 40),
            lambda p: p["model_assets"].update(repo_id="other/noma"),
            lambda p: p.update(source_revision="0" * 40),
            lambda p: p.update(native_max_prefix_tokens=2048),
            lambda p: p["settings"].update(facts=False),
            lambda p: p["settings"].update(fork=True),
            lambda p: p["settings"].update(threads=True),
        ]
        for mutate in mutations:
            bad = deepcopy(success)
            mutate(bad)
            with self.subTest(mutation=str(mutate)):
                self.assertFalse(validator.is_valid(bad))

    def test_legacy_decision2_archive_may_omit_new_transport_hash(self):
        source = ROOT / "profiles/decision2-eos-cpu-context.json"
        candidate = json.loads(source.read_text())
        with tempfile.TemporaryDirectory() as folder:
            candidate["model"]["local_dir"] = str(Path(folder) / "missing-model")
            with patch("deposium_bench.decision2_adapter.subprocess.Popen", side_effect=AssertionError("spawn")):
                adapter = Decision2Adapter(candidate, source)
            try:
                self.assertIn("transport_sha256", adapter.provenance)
                legacy = deepcopy(adapter.provenance)
                legacy.pop("transport_sha256")
                provenance_validator().validate(legacy)
            finally:
                adapter.close()


if __name__ == "__main__":
    unittest.main()
