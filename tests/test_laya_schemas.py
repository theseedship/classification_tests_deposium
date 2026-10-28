"""Pinned profiles and unavailable provenance validate without weights or services."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench.adapters import parse_profile
from deposium_bench.campaigns import _prepare_profile
from deposium_bench.laya_adapter import LayaAdapter, PATH_FIELDS

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles/laya-multilingual-cpu-context.json"


@unittest.skipUnless(Draft202012Validator, "optional jsonschema is not installed")
class LayaSchemaTests(unittest.TestCase):
    def test_profile_parser_and_schema_refuse_wrong_checkpoint_and_limits(self):
        schema = json.loads((ROOT / "schemas/candidate-v1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        profile = json.loads(PROFILE.read_text())
        validator.validate(profile)
        parse_profile(PROFILE.read_bytes())
        changes = [lambda p: p.update(revision="0" * 40),
                   lambda p: p["model"].update(repo_id="convaiinnovations/laya"),
                   lambda p: p["model"].update(source_revision="0" * 40),
                   lambda p: p["model"].update(head_length=512),
                   lambda p: p["model"].update(max_length=8192),
                   lambda p: p["model"].update(max_rss_mb=3073),
                   lambda p: p["model"].update(threads=True),
                   lambda p: p.update(timeout_seconds=31),
                   lambda p: p.update(qualification="component_replay")]
        for change in changes:
            changed = deepcopy(profile)
            change(changed)
            with self.subTest(changed=changed):
                self.assertFalse(validator.is_valid(changed))
                with self.assertRaises(ValueError):
                    parse_profile(json.dumps(changed).encode())

    def test_campaign_paths_preserve_the_runtime_executable_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "python").symlink_to("/usr/bin/python3")
            profile = json.loads(PROFILE.read_text())
            profile["model"]["runtime_python"] = "python"
            source = root / "profile.json"
            source.write_text(json.dumps(profile))
            prepared, _, _ = _prepare_profile(source)
            for name in PATH_FIELDS:
                self.assertTrue(os.path.isabs(prepared["model"][name]))
            self.assertEqual(prepared["model"]["runtime_python"], str(root / "python"))
            self.assertTrue(Path(prepared["model"]["runtime_python"]).is_symlink())

    def test_unavailable_provenance_requires_explicit_error(self):
        profile = json.loads(PROFILE.read_text())
        with patch.object(LayaAdapter, "_prepare", side_effect=FileNotFoundError), \
             patch("deposium_bench.laya_adapter.subprocess.Popen", side_effect=AssertionError("child spawned")):
            adapter = LayaAdapter(profile, PROFILE)
        schema = json.loads((ROOT / "schemas/campaign-v1.schema.json").read_text())
        validator = Draft202012Validator({**schema["properties"]["adapter_provenance"], "$defs": schema["$defs"]})
        validator.validate(adapter.provenance)
        missing = deepcopy(adapter.provenance)
        missing.pop("availability_error")
        self.assertFalse(validator.is_valid(missing))


if __name__ == "__main__":
    unittest.main()
