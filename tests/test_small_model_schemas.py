"""Small-model profile and archived provenance contracts, without model weights."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench.adapters import parse_profile
from deposium_bench.campaigns import _prepare_profile
from deposium_bench.small_model_adapter import SmallModelAdapter, REPOS, COMMON_PATHS

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {mode: ROOT / f"profiles/{name}-cpu-context.json" for mode, name in (
    ("omni", "omni"), ("muose", "muose"), ("modernjev", "modernjev"))}
SHA = "a" * 64


def campaign_validator():
    schema = json.loads((ROOT / "schemas/campaign-v1.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator({**schema["properties"]["adapter_provenance"],
                                 "$defs": schema["$defs"]})


def asset_manifest(mode):
    repo, revision, _ = REPOS[mode]
    return {"schema_version": "deposium.model-assets/v1", "repo_id": repo,
            "revision": revision, "files": [{"path": "config.json", "size": 1, "sha256": SHA}]}


@unittest.skipUnless(Draft202012Validator, "optional jsonschema is not installed")
class SmallModelSchemaTests(unittest.TestCase):
    def test_pinned_profiles_parse_and_reject_crossed_identities(self):
        candidate = json.loads((ROOT / "schemas/candidate-v1.schema.json").read_text())
        candidate.pop("$id", None)
        Draft202012Validator.check_schema(candidate)
        validator = Draft202012Validator(candidate)
        for mode, path in PROFILES.items():
            with self.subTest(mode=mode):
                profile = json.loads(path.read_text())
                validator.validate(profile)
                parse_profile(path.read_bytes())
                bad = deepcopy(profile)
                bad["model"]["repo_id"] = REPOS["omni" if mode != "omni" else "muose"][0]
                self.assertFalse(validator.is_valid(bad))
                with self.assertRaises(ValueError):
                    parse_profile(json.dumps(bad).encode())

    def test_prepare_profile_keeps_runtime_executable_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "python").symlink_to("/usr/bin/python3")
            for mode, path in PROFILES.items():
                profile = json.loads(path.read_text())
                profile["model"]["runtime_python"] = "python"
                source = root / f"{mode}.json"
                source.write_text(json.dumps(profile))
                prepared, _, _ = _prepare_profile(source)
                for name in COMMON_PATHS | {"prompt_path" if mode == "omni" else "template_path"}:
                    self.assertTrue(os.path.isabs(prepared["model"][name]))
                self.assertEqual(prepared["model"]["runtime_python"], str(root / "python"))
                self.assertTrue(Path(prepared["model"]["runtime_python"]).is_symlink())

    def test_unavailable_and_available_provenance_have_distinct_requirements(self):
        validator = campaign_validator()
        for mode, path in PROFILES.items():
            profile = json.loads(path.read_text())
            with self.subTest(mode=mode), patch.object(SmallModelAdapter, "_prepare",
                                                       side_effect=FileNotFoundError), \
                    patch("deposium_bench.small_model_adapter.subprocess.Popen",
                          side_effect=AssertionError("child spawned")):
                adapter = SmallModelAdapter(profile, path)
            unavailable = adapter.provenance
            validator.validate(unavailable)
            missing = deepcopy(unavailable)
            missing.pop("availability_error")
            self.assertFalse(validator.is_valid(missing))

            ready = deepcopy(unavailable)
            ready.pop("availability_error")
            ready.update(available=True, model_assets=asset_manifest(mode),
                         source_assets=asset_manifest(mode), runtime_pins={"python": "3.12.3"},
                         runtime={"python": "3.12.3"}, device="cpu", dtype="float32",
                         backend={"omni": "system_one", "muose": "muose_native",
                                  "modernjev": "modernjev_native"}[mode],
                         effective_max_input_tokens=REPOS[mode][2], load_ms=1.0,
                         load_rss_mb=100.0,
                         settings={"device": "cpu", "dtype": "float32", "threads": 2,
                                   "max_length": REPOS[mode][2], "max_rss_mb": 4096,
                                   "encoding_preflight": "native-lossless"})
            for key in ("assets_manifest_sha256", "model_assets_sha256", "source_manifest_sha256",
                        "source_assets_sha256", "runtime_lock_sha256", "runtime_python_sha256",
                        "prompt_sha256" if mode == "omni" else "template_sha256"):
                ready[key] = SHA
            validator.validate(ready)
            crossed = deepcopy(ready)
            crossed["source_assets"]["revision"] = REPOS["muose" if mode != "muose" else "omni"][1]
            self.assertFalse(validator.is_valid(crossed))
            promoted = deepcopy(unavailable)
            promoted["available"] = True
            promoted.pop("availability_error")
            self.assertFalse(validator.is_valid(promoted))

    def test_decision2_kai_eos_pairing_in_campaign_archive(self):
        validator = campaign_validator()
        for profile_name, native_limit in (("decision2-eos-cpu-context.json", 16384),
                                           ("decision2-kai-cpu-context.json", 8192)):
            from deposium_bench.decision2_adapter import Decision2Adapter
            path = ROOT / "profiles" / profile_name
            profile = json.loads(path.read_text())
            with patch("deposium_bench.decision2_adapter.subprocess.Popen",
                       side_effect=AssertionError("child spawned")):
                adapter = Decision2Adapter(profile, path)
            base = deepcopy(adapter.provenance)
            base.pop("availability_error")
            base.update(available=True, model_assets={
                "schema_version": "deposium.model-assets/v1", "repo_id": profile["model"]["repo_id"],
                "revision": profile["revision"],
                "files": [{"path": "config.json", "size": 1, "sha256": SHA}]},
                assets_manifest_sha256=SHA, model_assets_sha256=SHA,
                prompt_sha256=SHA, runtime_lock_sha256=SHA, runtime_python_sha256=SHA,
                runtime_pins={"torch": "1"}, runtime={"torch": "1"},
                settings={"device": "cpu", "dtype": "float32", "threads": 2,
                          "max_length": profile["model"]["max_length"],
                          "max_rss_mb": profile["model"]["max_rss_mb"],
                          "encoding_preflight": "official-decision2-encode", "shared_context": False},
                device="cpu", dtype="float32", native_max_input_tokens=native_limit,
                effective_max_input_tokens=profile["model"]["max_length"],
                load_ms=1.0, load_rss_mb=100.0)
            with self.subTest(profile=profile_name):
                validator.validate(base)
                crossed = deepcopy(base)
                crossed["model_revision"] = ("cd49ea3813fd8ba0928a9a23ef6c9a0f2f0cd764"
                                              if native_limit == 16384 else
                                              "3594047d69f476f1d01cf84c593e213fc3a4dfe0")
                self.assertFalse(validator.is_valid(crossed))


if __name__ == "__main__":
    unittest.main()
