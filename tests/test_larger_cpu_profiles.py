"""Offline schema checks for the three larger CPU candidates and old ceilings."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

ROOT = Path(__file__).resolve().parents[1]
SHA = "0" * 64
MODEL_ASSET = {"path": "config.json", "size": 2, "sha256": SHA}


def schema(name):
    data = json.loads((ROOT / "schemas" / name).read_text())
    data.pop("$id", None)
    Draft202012Validator.check_schema(data)
    return data


def profile(name):
    return json.loads((ROOT / "profiles" / name).read_text())


def assets(candidate):
    return {"schema_version": "deposium.model-assets/v1",
            "repo_id": candidate["model"]["repo_id"], "revision": candidate["revision"],
            "files": [MODEL_ASSET]}


def provenance(candidate):
    model = candidate["model"]
    kind = candidate["adapter"]
    result = {
        "adapter": kind, "qualification": "model_isolated", "available": True,
        "model": model, "model_revision": candidate["revision"],
        "model_repo_id": model["repo_id"], "profile_sha256": SHA,
        "capabilities": ["bench.context-choice"], "adapter_sha256": SHA,
        "worker_sha256": SHA, "choice_protocol_sha256": SHA,
        "transport_sha256": SHA, "identity_sha256": SHA, "init_wall_ms": 1,
        "assets_manifest_sha256": SHA, "model_assets_sha256": SHA,
        "model_assets": assets(candidate), "runtime_lock_sha256": SHA,
        "runtime_python_sha256": SHA, "runtime_pins": {"torch": "2.14.0+cpu"},
        "runtime": {"torch": "2.14.0+cpu"}, "device": "cpu", "dtype": "float32",
        "effective_max_input_tokens": model["max_length"], "load_ms": 1,
        "load_rss_mb": 1, "settings": {
            "device": "cpu", "dtype": "float32", "threads": model["threads"],
            "max_length": model["max_length"], "max_rss_mb": model["max_rss_mb"]}}
    if kind == "decision2":
        result["prompt_sha256"] = SHA
        result["native_max_input_tokens"] = (
            8192 if model["repo_id"] == "vllm-sr/Decision-2.0-Kai-0.6B" else 16384)
        result["settings"].update(encoding_preflight="official-decision2-encode",
                                  shared_context=False)
    elif kind == "vela2":
        result["prompt_sha256"] = SHA
        small_encoder = model["repo_id"] == "vllm-sr/Vela-2.0-0.3B"
        result["native_max_input_tokens"] = 8192 if small_encoder else 16384
        result["loading_mode"] = "hf-automodel-fp32" if small_encoder else "native-decoder-fp32"
        result["settings"].update(encoding_preflight="official-vela2-assemble-complete",
                                  shared_context=False, loading_mode=result["loading_mode"])
    else:
        result.update(backend_sha256=SHA, asset_helpers_sha256=SHA,
                      source_manifest_sha256=SHA, source_assets_sha256=SHA,
                      source_assets=assets(candidate), prompt_sha256=SHA,
                      backend="system_one")
        result["settings"]["encoding_preflight"] = "native-lossless"
    return result


@unittest.skipUnless(Draft202012Validator, "optional jsonschema is not installed")
class LargerCpuSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate_schema = Draft202012Validator(schema("candidate-v1.schema.json"))
        cls.campaign = schema("campaign-v1.schema.json")
        cls.campaign_adapter_validator = Draft202012Validator({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": cls.campaign["$defs"],
            **cls.campaign["properties"]["adapter_provenance"]})
        cls.provenance_validators = {
            kind: Draft202012Validator({
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$defs": cls.campaign["$defs"],
                **cls.campaign["$defs"][kind + "_provenance"]})
            for kind in ("decision2", "vela2", "small_model")}

    def test_new_profiles_pass_with_exact_pins(self):
        for name in ("decision2-nox-cpu-context.json", "vela2-4-cpu-context.json",
                     "liquid-d1-3b-cpu-context.json"):
            with self.subTest(name=name):
                self.candidate_schema.validate(profile(name))

    def test_new_profiles_reject_crossed_identity_and_relaxed_limits(self):
        for name in ("decision2-nox-cpu-context.json", "vela2-4-cpu-context.json",
                     "liquid-d1-3b-cpu-context.json"):
            original = profile(name)
            mutations = [
                lambda p: p.update(revision="f" * 40),
                lambda p: p["model"].update(max_rss_mb=original["model"]["max_rss_mb"] + 1),
                lambda p: p["model"].update(max_length=4097),
                lambda p: p.update(timeout_seconds=61),
            ]
            if original["adapter"] == "small_model":
                mutations += [
                    lambda p: p["model"].update(repo_id="LiquidAI/d1-omni-600M"),
                    lambda p: p["model"].pop("prompt_path"),
                    lambda p: p["model"].update(template_path="unreviewed.txt"),
                ]
            else:
                mutations.append(lambda p: p["model"].update(repo_id="vllm-sr/unknown"))
            for index, mutate in enumerate(mutations):
                changed = deepcopy(original)
                mutate(changed)
                with self.subTest(name=name, mutation=index):
                    self.assertFalse(self.candidate_schema.is_valid(changed))

    def test_historical_profile_limits_stay_bounded(self):
        for name in ("decision2-eos-cpu-context.json", "decision2-kai-cpu-context.json",
                     "vela2-03-cpu-context.json", "vela2-08-cpu-context.json",
                     "omni-cpu-context.json", "muose-cpu-context.json",
                     "modernjev-cpu-context.json"):
            original = profile(name)
            self.assertTrue(self.candidate_schema.is_valid(original), name)
            raised = deepcopy(original)
            raised["model"]["max_rss_mb"] = 22528
            self.assertFalse(self.candidate_schema.is_valid(raised), name)
            raised = deepcopy(original)
            raised["timeout_seconds"] = 60
            self.assertFalse(self.candidate_schema.is_valid(raised), name)

    def test_campaign_provenance_correlates_repo_revision_assets_and_runtime(self):
        for name in ("decision2-nox-cpu-context.json", "vela2-4-cpu-context.json",
                     "liquid-d1-3b-cpu-context.json"):
            candidate = profile(name)
            valid = provenance(candidate)
            validator = self.provenance_validators[candidate["adapter"]]
            validator.validate(valid)
            self.campaign_adapter_validator.validate(valid)
            for path, replacement in (
                    (("model_repo_id",), "unreviewed/model"),
                    (("model_revision",), "f" * 40),
                    (("model_assets", "repo_id"), "unreviewed/model"),
                    (("model_assets", "revision"), "f" * 40),
                    (("settings", "max_rss_mb"), valid["settings"]["max_rss_mb"] - 1)):
                changed = deepcopy(valid)
                target = changed
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = replacement
                with self.subTest(name=name, path=path):
                    self.assertFalse(validator.is_valid(changed))
            if candidate["adapter"] == "small_model":
                for path, replacement in ((("source_assets", "repo_id"), "unreviewed/model"),
                                          (("source_assets", "revision"), "f" * 40),
                                          (("backend",), "modernjev_native"),
                                          (("settings", "encoding_preflight"), "approximate")):
                    changed = deepcopy(valid)
                    target = changed
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = replacement
                    with self.subTest(name=name, path=path):
                        self.assertFalse(validator.is_valid(changed))

    def test_historical_campaign_provenance_keeps_rss_ceiling(self):
        for name in ("decision2-eos-cpu-context.json", "decision2-kai-cpu-context.json",
                     "vela2-03-cpu-context.json", "vela2-08-cpu-context.json",
                     "omni-cpu-context.json"):
            candidate = profile(name)
            validator = self.provenance_validators[candidate["adapter"]]
            valid = provenance(candidate)
            with self.subTest(name=name):
                validator.validate(valid)
                too_large = deepcopy(valid)
                too_large["settings"]["max_rss_mb"] = 22528
                self.assertFalse(validator.is_valid(too_large))


if __name__ == "__main__":
    unittest.main()
