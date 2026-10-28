"""Profile/schema agreement and archiveability without weights or services."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench.adapters import parse_profile
from deposium_bench.decision2_adapter import Decision2Adapter

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

ROOT = Path(__file__).resolve().parents[1]


def _candidate_schema():
    schema = json.loads((ROOT / "schemas/candidate-v1.schema.json").read_text())
    # The repository's symbolic $id is not an absolute URI for older jsonschema.
    schema.pop("$id", None)
    return schema


@unittest.skipUnless(Draft202012Validator, "optional jsonschema is not installed")
class Decision2SchemaTests(unittest.TestCase):
    def test_kai_profile_requires_matching_revision(self):
        schema = _candidate_schema()
        validator = Draft202012Validator(schema)
        kai = json.loads((ROOT / "profiles/decision2-kai-cpu-context.json").read_text())
        validator.validate(kai)
        parse_profile(json.dumps(kai).encode())
        for repo, revision in (("vllm-sr/Decision-2.0-Eos-0.8B", kai["revision"]),
                               (kai["model"]["repo_id"], "3594047d69f476f1d01cf84c593e213fc3a4dfe0")):
            changed = deepcopy(kai)
            changed["model"]["repo_id"] = repo
            changed["revision"] = revision
            self.assertFalse(validator.is_valid(changed))
            with self.assertRaises(ValueError):
                parse_profile(json.dumps(changed).encode())

    def test_profile_and_parser_reject_unsupported_runtime_and_capabilities(self):
        profile = json.loads((ROOT / "profiles/decision2-eos-cpu-context.json").read_text())
        schema = _candidate_schema()
        validator = Draft202012Validator(schema)
        validator.validate(profile)
        parse_profile(json.dumps(profile).encode())
        mutations = [
            lambda p: p["model"].update(max_rss_mb=6145),
            lambda p: p["model"].update(max_length=4097),
            lambda p: p["model"].update(threads=True),
            lambda p: p["model"].update(repo_id="vllm-sr/Decision-2.0-Sol-2B"),
            lambda p: p.update(capabilities=["mcps.document-plan"]),
            lambda p: p.update(qualification="component_replay"),
            lambda p: p.update(timeout_seconds=31),
        ]
        for mutate in mutations:
            candidate = deepcopy(profile)
            mutate(candidate)
            with self.subTest(candidate=candidate):
                self.assertFalse(validator.is_valid(candidate))
                with self.assertRaises(ValueError):
                    parse_profile(json.dumps(candidate).encode())

    def test_missing_model_provenance_cannot_be_promoted_to_available(self):
        profile = json.loads((ROOT / "profiles/decision2-eos-cpu-context.json").read_text())
        schema = json.loads((ROOT / "schemas/campaign-v1.schema.json").read_text())
        validator = Draft202012Validator({
            **schema["properties"]["adapter_provenance"], "$defs": schema["$defs"]})
        with tempfile.TemporaryDirectory() as folder:
            profile["model"]["local_dir"] = str(Path(folder) / "missing-model")
            with patch("deposium_bench.decision2_adapter.subprocess.Popen",
                       side_effect=AssertionError("No child for a missing model")):
                adapter = Decision2Adapter(profile, ROOT / "profiles/decision2-eos-cpu-context.json")
            try:
                self.assertFalse(adapter.provenance["available"])
                validator.validate(adapter.provenance)
                promoted = deepcopy(adapter.provenance)
                promoted["available"] = True
                promoted.pop("availability_error")
                self.assertFalse(validator.is_valid(promoted))
                promoted = deepcopy(adapter.provenance)
                promoted["qualification"] = "component_replay"
                self.assertFalse(validator.is_valid(promoted))
            finally:
                adapter.close()


if __name__ == "__main__":
    unittest.main()
