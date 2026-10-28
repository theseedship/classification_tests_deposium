"""Schema contracts and runtime parity, without a mandatory JSON Schema library.

The standard-library guards inspect declarations and emitted field shapes; they
are not a general JSON Schema validator. If jsonschema is already installed,
additional Draft 2020-12 validation runs against good and malformed records.
Cross-record identities, hashes and arithmetic remain engine responsibilities.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench.adapters import CONTRACTS, load_profile
from deposium_bench.campaigns import rescore_campaign, resume_campaign, run_campaign
from deposium_bench.cases import load_cases
from deposium_bench.choice_protocol import CONTEXT_CHOICE_PROMPT, validate_choice_input
from deposium_bench.registry import PACKS
from deposium_bench.scoring import STATUSES

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    Draft202012Validator = FormatChecker = None

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("case", "candidate", "result", "campaign", "campaign-summary", "archive-seal", "runtime-artifacts")


def load_schema(name: str, version: int = 1) -> dict:
    return json.loads((ROOT / "schemas" / f"{name}-v{version}.schema.json").read_text())


def research_case():
    """A schema fixture, without evaluating an oracle or loading any model."""
    value = deepcopy(load_cases()[0][0])
    value.update(schema_version="deposium.case/v2", pack="RESEARCH", language="de",
                 contract_id="bench.context-choice",
                 input={"context": "x = 2", "question": "x + 1?",
                        "options": [{"id": "a", "description": "3"},
                                    {"id": "unknown", "description": "Unknown"}]},
                 evaluation={"domain": "mathematics", "difficulty": "D1",
                             "base_case_id": "schema-math", "related_contract_ids": ["mcps.document-plan"],
                             "review": "agent_only", "task_type": "arithmetic",
                             "oracle": {"kind": "human_reference", "params": {"task": "catalog"},
                                        "choices": {"a": "catalog", "unknown": "unknown"},
                                        "base_input": {"context": "x = 2", "question": "x + 1?",
                                                       "options": [{"id": "a", "description": "3"},
                                                                   {"id": "unknown", "description": "Unknown"}]}},
                             "length": None})
    value["reference"]["assertions"] = [{"path": "/choice_id", "op": "equals", "value": "a"}]
    value["reference"]["abstention_allowed"] = False
    return value


def length_metadata():
    return {"target_tokens": 100, "actual_tokens": 100, "content_tokens": 60,
            "head_tokens": 40, "padded_tokens": 104, "position": "middle",
            "order": "reversed", "tokenizer_sha256": "0" * 64,
            "tokenizer_revision": "1" * 40, "base_input_sha256": "0" * 64,
            "generator_version": "deposium.length-generator/v1", "within_target": True}


def candidate_profiles():
    """Prompt and assets manifests may share the profiles directory."""
    for path in sorted((ROOT / "profiles").glob("*.json")):
        if json.loads(path.read_text()).get("schema_version") == "deposium.candidate/v1":
            yield load_profile(path)[0]


def isolated_profile():
    """Syntactic configuration fixture; these locations are never loaded."""
    return {"schema_version": "deposium.candidate/v1", "profile_id": "schema-model",
            "adapter": "julia", "qualification": "model_isolated",
            "capabilities": ["mcps.document-plan"], "revision": "1" * 40,
            "timeout_seconds": 10, "recordings": None,
            "model": {"repo_id": "SupersonicLabs/Julia-1", "local_dir": "missing/model",
                      "runtime_python": "/missing/python", "assets_manifest": "assets.json",
                      "prompt_path": "prompt.json", "runtime_lock": "runtime.lock",
                      "max_length": 1024, "head_length": 512, "threads": 2,
                      "max_rss_mb": 3072}}


def gliner_profile():
    value = isolated_profile()
    value.update(adapter="gliner", capabilities=["bench.context-choice"])
    value["model"].update(repo_id="fastino/GLiNER2.5-multi-Decide", max_length=4096)
    value["model"].pop("head_length")
    return value


def indecis_profile():
    """Syntactic isolated untrained configuration; no Go worker is launched."""
    return {"schema_version": "deposium.candidate/v1", "profile_id": "schema-indecis",
            "adapter": "indecis", "qualification": "model_isolated",
            "capabilities": ["bench.context-choice"], "revision": "c721113d59a1d91b447450324f51c4b3332c924a",
            "timeout_seconds": 30, "recordings": None,
            "model": {"repo_id": "hotchpotch/bekko-embedding-v1-a8m", "local_dir": "missing/model",
                      "assets_manifest": "assets.json", "prompt_path": "prompt.json",
                      "source_dir": "missing/source", "source_manifest": "source.json",
                      "source_revision": "339e191405ac9be90f6857f810f478b3312b7f35",
                      "worker_binary": "/missing/worker", "build_manifest": "build.json",
                      "max_length": 4096, "threads": 2, "max_rss_mb": 3072}}


def nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


class SchemaContracts(unittest.TestCase):
    def test_versioned_closed_roots_and_local_references(self):
        for name, version in [(name, 1) for name in NAMES] + [("case", 2)]:
            with self.subTest(schema=name, version=version):
                schema = load_schema(name, version)
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertEqual(schema["$id"], f"deposium.{name}/v{version}")
                self.assertEqual(schema["properties"]["schema_version"]["const"], schema["$id"])
                self.assertEqual(schema["type"], "object")
                self.assertIs(schema["additionalProperties"], False)
                self.assertEqual(set(schema["required"]), set(schema["properties"]))
                self.assertIn("description", schema)
                for node in nodes(schema):
                    if "$ref" in node:
                        self.assertTrue(node["$ref"].startswith("#/$defs/"))
                        self.assertIn(node["$ref"].split("/")[-1], schema["$defs"])
                    if node.get("type") == "object" and "properties" in node:
                        self.assertIs(node["additionalProperties"], False)
                        self.assertLessEqual(set(node["required"]), set(node["properties"]))

    def test_case_assertions_and_supported_enumerations(self):
        schema = load_schema("case")
        self.assertEqual(set(schema["properties"]["pack"]["enum"]), PACKS)
        self.assertEqual(set(schema["properties"]["language"]["enum"]), {"fr", "en"})
        assertions = schema["$defs"]["reference"]["properties"]["assertions"]
        self.assertEqual(assertions["minItems"], 1)
        self.assertEqual(assertions["items"]["$ref"], "#/$defs/assertion")
        self.assertEqual(set(schema["$defs"]["assertion"]["properties"]["op"]["enum"]),
                         {"equals", "one_of", "set_equals"})
        self.assertIs(schema["properties"]["document_ids"]["uniqueItems"], True)

    def test_candidate_and_result_match_runtime_statuses_and_capabilities(self):
        candidate = load_schema("candidate")
        self.assertEqual(set(candidate["properties"]["capabilities"]["items"]["enum"]),
                         set(CONTRACTS) | {"mcps.search", "bench.context-choice"})
        self.assertIn({"type": "null"}, candidate["properties"]["model"]["anyOf"])
        mcps = candidate["allOf"][0]["then"]["properties"]
        self.assertEqual(set(mcps["capabilities"]["items"]["enum"]), set(CONTRACTS))
        self.assertEqual(mcps["model"], {"type": "null"})
        julia = candidate["allOf"][2]["then"]["properties"]
        self.assertEqual(julia["capabilities"],
                         {"enum": [["mcps.document-plan"], ["bench.context-choice"]]})
        self.assertEqual(julia["qualification"], {"const": "model_isolated"})
        result = load_schema("result")
        self.assertEqual(set(result["properties"]["status"]["enum"]), set(STATUSES))
        self.assertEqual(result["properties"]["duration_ms"], {"type": "number", "minimum": 0})
        # Empty/incorrect outputs are archiveable evidence, not schema successes.
        self.assertEqual(result["properties"]["output"], {})
        self.assertEqual(result["properties"]["raw_output"], {})

    def test_model_schema_bounds_and_success_provenance_requirements(self):
        schema = load_schema("candidate")
        config = schema["$defs"]["model_config"]
        self.assertEqual(set(config["required"]), set(isolated_profile()["model"]))
        self.assertEqual(config["properties"]["threads"],
                         {"type": "integer", "minimum": 1, "maximum": 4})
        self.assertEqual(config["properties"]["max_rss_mb"]["maximum"], 3072)
        self.assertEqual(config["properties"]["max_length"]["maximum"], 8192)
        self.assert_emitted_shape(isolated_profile(), schema, schema)
        provenance = load_schema("campaign")["$defs"]["adapter_provenance"]
        ready = next(branch for branch in provenance["allOf"]
                     if branch["if"]["properties"] ==
                     {"adapter": {"const": "julia"}, "available": {"const": True}})
        self.assertEqual(ready["if"]["properties"],
                         {"adapter": {"const": "julia"}, "available": {"const": True}})
        self.assertLessEqual({"assets_manifest_sha256", "model_assets_sha256", "runtime",
                             "settings", "load_ms", "load_rss_mb", "model_revision",
                             "prompt", "assets_manifest", "runtime_lock"},
                            set(ready["then"]["required"]))

    def test_gliner_profile_uses_its_native_bounded_configuration(self):
        schema = load_schema("candidate")
        model = schema["$defs"]["gliner_model_config"]
        self.assertEqual(set(model["required"]), set(gliner_profile()["model"]))
        self.assertNotIn("head_length", model["properties"])
        self.assertEqual(model["properties"]["max_length"]["maximum"], 4096)
        self.assert_emitted_shape(gliner_profile(), schema, schema)
        branch = next(item for item in schema["allOf"]
                      if item["if"]["properties"]["adapter"] == {"const": "gliner"})
        self.assertEqual(branch["then"]["properties"]["capabilities"],
                         {"const": ["bench.context-choice"]})

    def test_indecis_declaration_pins_backbone_and_source_without_training(self):
        schema = load_schema("candidate")
        model = schema["$defs"]["indecis_model_config"]
        profile = indecis_profile()
        self.assertEqual(set(model["required"]), set(profile["model"]))
        self.assertEqual(model["properties"]["max_length"]["maximum"], 4096)
        self.assertEqual(model["properties"]["source_revision"], {"const": profile["model"]["source_revision"]})
        self.assert_emitted_shape(profile, schema, schema)
        branch = next(item for item in schema["allOf"]
                      if item["if"]["properties"]["adapter"] == {"const": "indecis"})
        self.assertEqual(branch["then"]["properties"]["revision"], {"const": profile["revision"]})
        self.assertEqual(branch["then"]["properties"]["capabilities"], {"const": ["bench.context-choice"]})
        self.assertEqual(branch["then"]["properties"]["timeout_seconds"], {"maximum": 30})

    def test_indecis_provenance_ready_and_failed_contracts_are_separate(self):
        schema = load_schema("campaign")
        provenance = schema["$defs"]["adapter_provenance"]
        base = next(item for item in provenance["allOf"]
                    if item["if"]["properties"] == {"adapter": {"const": "indecis"}})
        ready = next(item for item in provenance["allOf"]
                     if item["if"]["properties"] == {"adapter": {"const": "indecis"}, "available": {"const": True}})
        self.assertEqual(set(base["then"]["required"]), {"model_revision", "source_revision", "init_wall_ms"})
        self.assertLessEqual({"assets_manifest", "source_manifest", "build_manifest", "helper_sha256",
                             "runtime", "binary_sha256", "worker_sha256", "load_ms", "load_rss_mb"},
                            set(ready["then"]["required"]))
        self.assertIs(base["then"]["properties"]["runtime_python_sha256"], False)
        self.assertIs(base["then"]["properties"]["runtime_lock_verified"], False)
        helpers = provenance["properties"]["helper_sha256"]
        self.assertEqual(set(helpers["required"]), {"julia_adapter.py", "cases.py", "choice_protocol.py"})

    def test_indecis_missing_worker_emits_archiveable_provenance_without_execution(self):
        from deposium_bench.indecis_adapter import INDECIS_CHOICE_PROMPT, IndecisAdapter
        schema = load_schema("campaign")
        declared_prompt = schema["$defs"]["indecis_choice_prompt"]
        self.assertEqual({key: value["const"] for key, value in declared_prompt["properties"].items()},
                         INDECIS_CHOICE_PROMPT)
        with tempfile.TemporaryDirectory() as folder:
            profile = indecis_profile()
            profile["model"]["worker_binary"] = str(Path(folder) / "not-built-worker")
            with patch("deposium_bench.indecis_adapter.subprocess.Popen", side_effect=AssertionError("no worker execution")) as launch:
                adapter = IndecisAdapter(profile, Path(folder) / "profile.json")
            launch.assert_not_called()
            self.assertFalse(adapter.provenance["available"])
            self.assertEqual(adapter.provenance["availability_error"], "indecis_assets_or_runtime_missing")
            self.assertNotIn("runtime", adapter.provenance)
            self.assertNotIn("load_ms", adapter.provenance)
            self.assertNotIn("load_rss_mb", adapter.provenance)
            self.assert_emitted_shape(adapter.provenance, schema["$defs"]["adapter_provenance"], schema)
            if Draft202012Validator:
                Draft202012Validator({"$ref": "#/$defs/adapter_provenance", "$defs": schema["$defs"]}).validate(adapter.provenance)
            adapter.close()

    def test_research_shapes_and_protocol_parity(self):
        schema = load_schema("case", 2)
        case = research_case()
        validate_choice_input(case["input"])
        self.assert_emitted_shape(case, schema, schema)
        case["evaluation"]["length"] = length_metadata()
        self.assert_emitted_shape(case, schema, schema)
        self.assertEqual(schema["properties"]["pack"], {"const": "RESEARCH"})
        self.assertEqual(schema["properties"]["contract_id"], {"const": "bench.context-choice"})
        self.assertEqual(set(schema["properties"]["language"]["enum"]),
                         {"fr", "en", "de", "es", "it", "pt"})
        self.assertEqual(schema["$defs"]["context_choice_input"]["properties"]["options"]["maxItems"], 20)
        prompt = load_schema("campaign")["$defs"]["context_choice_prompt"]
        self.assertEqual({key: value["const"] for key, value in prompt["properties"].items()},
                         CONTEXT_CHOICE_PROMPT)
        summary = load_schema("campaign-summary")["$defs"]["metrics"]["properties"]
        self.assertIn("RESEARCH", summary["by_pack"]["propertyNames"]["enum"])
        self.assertEqual(set(summary["by_language"]["propertyNames"]["enum"]),
                         set(schema["properties"]["language"]["enum"]))

    def test_zero_scored_cases_are_declared_invalid(self):
        counts = load_schema("campaign-summary")["$defs"]["counts"]
        zero = counts["allOf"][0]
        self.assertEqual(zero["if"]["properties"]["scored_cases"], {"const": 0})
        self.assertEqual(zero["then"]["properties"]["verdict"], {"const": "invalid"})
        self.assertEqual(zero["then"]["properties"]["accuracy_scored"], {"type": "null"})
        self.assertEqual(set(counts["properties"]["counts_by_status"]["properties"]), set(STATUSES))

    def assert_emitted_shape(self, value, declaration, schema):
        """Inspect required/allowed fields and nested shapes, not full validation."""
        if "$ref" in declaration:
            declaration = schema["$defs"][declaration["$ref"].split("/")[-1]]
        if "anyOf" in declaration:
            if value is None:
                self.assertIn({"type": "null"}, declaration["anyOf"])
                return
            alternatives = [item for item in declaration["anyOf"] if item.get("type") != "null"]
            if isinstance(value, dict):
                expanded = [schema["$defs"][item["$ref"].split("/")[-1]]
                            if "$ref" in item else item for item in alternatives]
                def matches_discriminators(item):
                    # Local-model configs can share all field names. Their
                    # repo_id/adapter literals identify the intended branch.
                    return all(
                        not isinstance(child, dict) or key not in value
                        or (("const" not in child or value[key] == child["const"])
                            and ("enum" not in child or value[key] in child["enum"]))
                        for key, child in item.get("properties", {}).items())
                declaration = next((item for item in expanded
                                    if set(item.get("required", [])) <= set(value)
                                    and matches_discriminators(item)), expanded[0])
            else:
                declaration = alternatives[0]
            return self.assert_emitted_shape(value, declaration, schema)
        declared_types = declaration.get("type")
        if declared_types:
            declared_types = [declared_types] if isinstance(declared_types, str) else declared_types
            kinds = {"null": value is None, "boolean": type(value) is bool,
                     "integer": type(value) is int, "number": type(value) in (int, float),
                     "string": isinstance(value, str), "array": isinstance(value, list),
                     "object": isinstance(value, dict)}
            self.assertTrue(any(kinds[kind] for kind in declared_types),
                            f"{value!r} has no declared type in {declared_types!r}")
        if declaration.get("type") == "object":
            self.assertIsInstance(value, dict)
            self.assertLessEqual(set(declaration.get("required", [])), set(value))
            props = declaration.get("properties", {})
            if declaration.get("additionalProperties") is False:
                self.assertLessEqual(set(value), set(props))
            for key, item in value.items():
                child = props.get(key, declaration.get("additionalProperties", {}))
                if isinstance(child, dict):
                    self.assert_emitted_shape(item, child, schema)
        elif declaration.get("type") == "array":
            self.assertIsInstance(value, list)
            for item in value:
                self.assert_emitted_shape(item, declaration["items"], schema)
        if "const" in declaration:
            self.assertEqual(value, declaration["const"])
        if "enum" in declaration:
            self.assertIn(value, declaration["enum"])

    def test_real_offline_artifacts_have_declared_fields(self):
        cases, _ = load_cases()
        profiles = list(candidate_profiles())
        for case in cases:
            self.assert_emitted_shape(case, load_schema("case"), load_schema("case"))
        research, _ = load_cases(ROOT / "datasets/context-choice-v1/cases.jsonl")
        for case in research:
            self.assert_emitted_shape(case, load_schema("case", 2), load_schema("case", 2))
        for profile in profiles:
            self.assert_emitted_shape(profile, load_schema("candidate"), load_schema("candidate"))
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "control"
            run_campaign(ROOT / "datasets/decisions-v1/cases.jsonl",
                         ROOT / "profiles/fixture-control.json", archive, max_new_cases=3)
            for name, filename in (("campaign", "manifest.json"), ("campaign-summary", "summary.json"),
                                   ("archive-seal", "seal.json")):
                schema = load_schema(name)
                self.assert_emitted_shape(json.loads((archive / filename).read_text()), schema, schema)
            schema = load_schema("result")
            records = [json.loads(line) for line in (archive / "raw.jsonl").read_text().splitlines()]
            self.assertEqual(len(records), 3)
            for record in records:
                self.assert_emitted_shape(record, schema, schema)


@unittest.skipUnless(Draft202012Validator, "optional jsonschema is not installed")
class OptionalDraftValidation(unittest.TestCase):
    def validator(self, name, version=1):
        return Draft202012Validator(load_schema(name, version), format_checker=FormatChecker())

    def test_indecis_profile_rejects_revision_drift_and_unbounded_configuration(self):
        validator = self.validator("candidate")
        profile = indecis_profile()
        validator.validate(profile)
        for mutate in (lambda v: v.update(revision="1" * 40),
                       lambda v: v.update(revision=None),
                       lambda v: v.update(capabilities=["mcps.document-plan"]),
                       lambda v: v.update(timeout_seconds=31),
                       lambda v: v.update(qualification="component_replay"),
                       lambda v: v.update(recordings="recorded.jsonl"),
                       lambda v: v["model"].update(source_revision="1" * 40),
                       lambda v: v["model"].update(repo_id="SupersonicLabs/Julia-1"),
                       lambda v: v["model"].update(max_length=4097),
                       lambda v: v["model"].update(max_length=True),
                       lambda v: v["model"].update(threads=5),
                       lambda v: v["model"].update(max_rss_mb=3073),
                       lambda v: v["model"].update(worker_binary=""),
                       lambda v: v["model"].update(build_manifest="bad\npath"),
                       lambda v: v["model"].update(head_length=512),
                       lambda v: v["model"].update(training_data="test.jsonl")):
            value = deepcopy(profile)
            mutate(value)
            with self.subTest(value=value):
                self.assertFalse(validator.is_valid(value))

    def test_indecis_provenance_requires_exact_untrained_prompt_source_build_and_runtime(self):
        profile = indecis_profile()
        schema = load_schema("campaign")
        validator = Draft202012Validator({"$ref": "#/$defs/adapter_provenance", "$defs": schema["$defs"]})
        missing = {"profile_sha256": "0" * 64, "adapter_sha256": "0" * 64,
                   "qualification": "model_isolated", "adapter": "indecis", "model": profile["model"],
                   "model_revision": profile["revision"], "source_revision": profile["model"]["source_revision"],
                   "capabilities": ["bench.context-choice"], "available": False, "init_wall_ms": 1,
                   "identity_sha256": "0" * 64, "availability_error": "indecis_worker_missing"}
        validator.validate(missing)
        for key in ("source_revision", "model_revision", "init_wall_ms"):
            malformed = deepcopy(missing)
            malformed.pop(key)
            self.assertFalse(validator.is_valid(malformed))
        source_revision = profile["model"]["source_revision"]
        prompt = {key: item["const"] for key, item in
                  schema["$defs"]["indecis_choice_prompt"]["properties"].items()}
        ready = {**missing, "available": True,
                 "prompt": prompt, "prompt_schema_version": prompt["schema_version"], "input_protocol": "context_choice",
                 "runtime": {"parent_python": "fixture", "go": "go1.27.1-X:simd", "goos": "linux", "goarch": "amd64",
                             "indecis_revision": source_revision, "backbone_revision": profile["revision"]},
                 "load_ms": 1, "load_rss_mb": 1,
                 "settings": {"mode": "open_untrained", "trained": False, "max_length": 4096,
                              "threads": 2, "max_rss_mb": 3072, "strict_encoding": True, "cache_policy": "request_local"},
                 "helper_sha256": {name: "0" * 64 for name in ("julia_adapter.py", "cases.py", "choice_protocol.py")},
                 "assets_manifest": {"schema_version": "deposium.model-assets/v1", "repo_id": profile["model"]["repo_id"],
                                     "revision": profile["revision"], "files": [
                                         {"path": name, "size": 1, "sha256": "0" * 64}
                                         for name in ("config.json", "model.safetensors", "tokenizer.json")]},
                 "source_manifest": {"schema_version": "deposium.indecis-source/v1", "repo_id": "github.com/bornholm/indecis",
                                     "revision": source_revision, "total_bytes": 4,
                                     "files": [{"path": name, "size": 1, "sha256": "0" * 64}
                                               for name in ("go.mod", "model.go", "decide_open.go", "open.go")]},
                 "build_manifest": {"schema_version": "deposium.indecis-build/v1", "source_revision": source_revision,
                                    "source_manifest_sha256": "0" * 64, "worker_source_sha256": "0" * 64,
                                    "binary_sha256": "0" * 64, "go_version": "go1.27.1-X:simd",
                                    "build_flags": ["-p", "2", "-trimpath", "-buildvcs=false"],
                                    "go_env": {"GOOS": "linux", "GOARCH": "amd64", "CGO_ENABLED": "0",
                                               "GOTOOLCHAIN": "local", "GOEXPERIMENT": "simd", "GOPROXY": "off", "GOSUMDB": "off"}}}
        ready.pop("availability_error")
        for name in ("assets_manifest", "model_assets", "source_manifest", "source_files", "prompt",
                     "build_manifest", "binary", "worker"):
            ready[name + "_sha256"] = "0" * 64
        # These are declaration fixtures only; no ready worker or prediction is claimed.
        validator.validate(ready)
        base_go = deepcopy(ready)
        base_go["runtime"]["go"] = "go1.27.1"
        base_go["build_manifest"]["go_version"] = "go1.27.1"
        base_go["build_manifest"]["go_env"]["GOEXPERIMENT"] = ""
        self.assertFalse(validator.is_valid(base_go))
        partial = deepcopy(ready)
        partial.update(available=False, availability_error="indecis_setup_failed")
        for key in ("runtime", "load_ms", "load_rss_mb"):
            partial.pop(key)
        validator.validate(partial)
        for mutate in (lambda v: v.pop("source_manifest"),
                       lambda v: v.pop("build_manifest"),
                       lambda v: v.pop("binary_sha256"),
                       lambda v: v.pop("helper_sha256"),
                       lambda v: v["helper_sha256"].pop("cases.py"),
                       lambda v: v["helper_sha256"].update({"extra.py": "0" * 64}),
                       lambda v: v["runtime"].pop("parent_python"),
                       lambda v: v["runtime"].update(go="go1.26.0"),
                       lambda v: v["runtime"].update(backbone_revision="1" * 40),
                       lambda v: v["settings"].update(trained=True),
                       lambda v: v["settings"].update(cache_policy="persistent"),
                       lambda v: v["settings"].update(strict_encoding=False),
                       lambda v: v["settings"].update(max_length=4097),
                       lambda v: v["prompt"].update(option_serialization="id_newline_question"),
                       lambda v: v["prompt"].update(trained=True),
                       lambda v: v["prompt"].update(extra=True),
                       lambda v: v["assets_manifest"]["files"].pop(),
                       lambda v: v["assets_manifest"]["files"][0].update(path="../config.json"),
                       lambda v: v["source_manifest"].update(total_bytes=10485761),
                       lambda v: v["source_manifest"]["files"][0].update(path="../main.go"),
                       lambda v: v["build_manifest"].update(source_revision="1" * 40),
                       lambda v: v["build_manifest"].update(build_flags=["-race"]),
                       lambda v: v["build_manifest"].update(go_version="go1.27.1"),
                       lambda v: v["build_manifest"]["go_env"].update(GOEXPERIMENT=""),
                       lambda v: v["build_manifest"]["go_env"].update(GOPROXY="https://proxy.example"),
                       lambda v: v.update(runtime_python_sha256="0" * 64),
                       lambda v: v.update(runtime_lock_verified=True),
                       lambda v: v.update(transport="https_post_json")):
            malformed = deepcopy(ready)
            mutate(malformed)
            with self.subTest(value=malformed):
                self.assertFalse(validator.is_valid(malformed))
        for extra in ({"available": True}, {"load_ms": 1}, {"load_rss_mb": 1}, {"runtime": ready["runtime"]}):
            self.assertFalse(validator.is_valid({**missing, **extra}))
        # The new fields must not become accepted metadata for older candidates.
        from deposium_bench.adapters import create_adapter
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.json"
            recorded = json.loads((ROOT / "profiles/fixture-control.json").read_text())
            recording_path = (ROOT / "profiles" / recorded["recordings"]).resolve()
            recorded["recordings"] = str(recording_path)
            # Use the real control's recording bytes, with no candidate inference.
            adapter = create_adapter(recorded, path, recordings_data=recording_path.read_bytes())
            legacy = adapter.provenance
            validator.validate(legacy)
            for field in ("source_revision", "source_manifest", "build_manifest", "binary_sha256", "helper_sha256"):
                self.assertFalse(validator.is_valid({**legacy, field: ready[field]}))
            if hasattr(adapter, "close"):
                adapter.close()

    def test_gliner_configuration_and_unavailable_provenance(self):
        profile = gliner_profile()
        self.validator("candidate").validate(profile)
        mutations = [lambda v: v.update(capabilities=["mcps.document-plan"]),
                     lambda v: v["model"].update(head_length=512),
                     lambda v: v["model"].update(max_length=4097),
                     lambda v: v["model"].update(repo_id="SupersonicLabs/Julia-1"),
                     lambda v: v["model"].update(max_length=True)]
        for mutate in mutations:
            value = deepcopy(profile)
            mutate(value)
            with self.subTest(value=value):
                self.assertFalse(self.validator("candidate").is_valid(value))
        provenance = {"profile_sha256": "0" * 64, "adapter_sha256": "0" * 64,
                      "qualification": "model_isolated", "adapter": "gliner",
                      "model": profile["model"], "model_revision": profile["revision"],
                      "capabilities": ["bench.context-choice"], "available": False,
                      "identity_sha256": "0" * 64, "availability_error": "gliner_asset_missing"}
        schema = load_schema("campaign")
        validator = Draft202012Validator({"$ref": "#/$defs/adapter_provenance", "$defs": schema["$defs"]})
        validator.validate(provenance)
        for extra in ({"runtime_lock_verified": True}, {"runtime_packages": {"torch": "0"}},
                      {"load_ms": 1}, {"available": True},
                      {"prompt_schema_version": "deposium.context-choice-prompt/v1"}):
            with self.subTest(extra=extra):
                self.assertFalse(validator.is_valid({**provenance, **extra}))
        # Complete ready declaration fixture, without runtime execution/predictions.
        from deposium_bench.gliner_adapter import GLINER_CHOICE_PROMPT
        ready = {**provenance, "available": True,
                 "runtime": {name: "fixture" for name in
                             ("python", "torch", "transformers", "tokenizers", "numpy", "gliner2")},
                 "runtime_packages": {"gliner2": "fixture", "torch": "fixture"},
                 "runtime_lock_verified": True, "runtime_lock": "gliner2==fixture\n",
                 "runtime_sources": {"gliner2/__init__.py": "0" * 64},
                 "runtime_sources_sha256": "0" * 64, "runtime_sources_root": "/fixture/site-packages",
                 "init_wall_ms": 1, "load_ms": 1, "load_rss_mb": 1,
                 "input_protocol": "context_choice", "prompt": GLINER_CHOICE_PROMPT,
                 "prompt_schema_version": GLINER_CHOICE_PROMPT["schema_version"],
                 "settings": {"device": "cpu", "backend": "torch", "max_length": 4096,
                              "threads": 2, "max_rss_mb": 3072, "multi_label": False, "strict_encoding": True},
                 "assets_manifest": {"schema_version": "deposium.model-assets/v1",
                                     "repo_id": profile["model"]["repo_id"], "revision": profile["revision"],
                                     "files": [{"path": "config.json", "size": 1, "sha256": "0" * 64}]}}
        ready.pop("availability_error")
        for name in ("assets_manifest", "model_assets", "prompt", "runtime_lock", "worker",
                     "runtime_python", "choice_protocol"):
            ready[name + "_sha256"] = "0" * 64
        validator.validate(ready)
        mutations = [lambda v: v.pop("runtime_packages"),
                     lambda v: v.update(runtime_lock_verified=False),
                     lambda v: v.pop("runtime_sources"),
                     lambda v: v["runtime_sources"].update({"gliner2/../escape.py": "0" * 64}),
                     lambda v: v["settings"].update(head_length=512),
                     lambda v: v["settings"].update(max_length=4097),
                     lambda v: v["settings"].update(multi_label=True),
                     lambda v: v["runtime"].pop("gliner2"),
                     lambda v: v["assets_manifest"].update(repo_id="SupersonicLabs/Julia-1"),
                     lambda v: v.update(prompt=deepcopy(CONTEXT_CHOICE_PROMPT))]
        for mutate in mutations:
            value = deepcopy(ready)
            mutate(value)
            with self.subTest(value=value):
                self.assertFalse(validator.is_valid(value))

    def test_research_v2_boundaries(self):
        case = research_case()
        validator = self.validator("case", 2)
        validator.validate(case)
        case["input"]["context"] = "long context\n" * 2000
        case["evaluation"]["length"] = length_metadata()
        validator.validate(case)
        mutations = [lambda v: v.update(pack="DOC"),
                     lambda v: v.update(contract_id="mcps.document-plan"),
                     lambda v: v.update(language="xx"),
                     lambda v: v.pop("evaluation"),
                     lambda v: v["input"].update(reference="a"),
                     lambda v: v["input"].update(question="  "),
                     lambda v: v["input"].update(options=[]),
                     lambda v: v["input"]["options"][0].update(gold=True),
                     lambda v: v["evaluation"].update(review="human_reviewed"),
                     lambda v: v["evaluation"].update(oracle={}),
                     lambda v: v["evaluation"]["oracle"].update(kind="unsupported"),
                     lambda v: v["evaluation"]["oracle"].pop("base_input"),
                     lambda v: v["evaluation"]["oracle"].update(extra=True),
                     lambda v: v["reference"].update(abstention_allowed=True),
                     lambda v: v["reference"]["assertions"][0].update(path="/task"),
                     lambda v: v["evaluation"].update(extra=True),
                     lambda v: v["evaluation"]["length"].update(target_tokens=True),
                     lambda v: v["evaluation"]["length"].update(actual_tokens=131073),
                     lambda v: v["evaluation"]["length"].update(position="random"),
                     lambda v: v["evaluation"]["length"].update(within_target=1),
                     lambda v: v["evaluation"]["length"].pop("tokenizer_sha256")]
        for mutate in mutations:
            value = deepcopy(case)
            mutate(value)
            with self.subTest(value=value):
                self.assertFalse(validator.is_valid(value))

    def test_generic_profiles_and_prompt_provenance_are_consistent(self):
        profile = isolated_profile()
        profile.update(capabilities=["bench.context-choice"])
        profile["model"].update(max_length=8192)
        self.validator("candidate").validate(profile)
        # A syntactic ready declaration fixture: no model or runtime is executed.
        provenance = {"profile_sha256": "0" * 64, "adapter_sha256": "0" * 64,
                      "qualification": "model_isolated", "adapter": "julia",
                      "model": profile["model"], "model_revision": profile["revision"],
                      "capabilities": profile["capabilities"], "available": True,
                      "identity_sha256": "0" * 64, "input_protocol": "context_choice",
                      "prompt_schema_version": CONTEXT_CHOICE_PROMPT["schema_version"],
                      "prompt": deepcopy(CONTEXT_CHOICE_PROMPT),
                      "assets_manifest": {"schema_version": "deposium.model-assets/v1",
                                          "repo_id": profile["model"]["repo_id"],
                                          "revision": profile["revision"],
                                          "files": [{"path": "config.json", "size": 1,
                                                     "sha256": "0" * 64}]},
                      "runtime_lock": "torch==0\n", "load_ms": 1, "load_rss_mb": 1,
                      "init_wall_ms": 2,
                      "runtime": {name: "fixture" for name in
                                  ("python", "torch", "transformers", "tokenizers", "numpy")},
                      "settings": {"device": "cpu", "backend": "torch", "max_length": 8192,
                                   "head_length": 512, "threads": 2, "max_rss_mb": 3072,
                                   "strict_encoding": True, "marker_only_head": False}}
        for name in ("assets_manifest", "model_assets", "prompt", "runtime_lock", "worker",
                     "runtime_python", "choice_protocol"):
            provenance[name + "_sha256"] = "0" * 64
        schema = load_schema("campaign")
        validator = Draft202012Validator({"$ref": "#/$defs/adapter_provenance",
                                          "$defs": schema["$defs"]})
        validator.validate(provenance)
        mutations = [lambda v: v.update(input_protocol="current_equivalent"),
                     lambda v: v.update(prompt_schema_version="deposium.document-task-prompt/v1"),
                     lambda v: v["prompt"].update(order="reversed"),
                     lambda v: v.pop("choice_protocol_sha256"),
                     lambda v: v.pop("init_wall_ms"),
                     lambda v: v.update(worker_load_ms=1),
                     lambda v: v.update(transport="resident_process_jsonl")]
        for mutate in mutations:
            value = deepcopy(provenance)
            mutate(value)
            with self.subTest(value=value):
                self.assertFalse(validator.is_valid(value))
        # The old document pilot did not record the new helper/init fields.
        document = deepcopy(provenance)
        document.update(capabilities=["mcps.document-plan"], input_protocol="current_equivalent",
                        prompt_schema_version="deposium.document-task-prompt/v1",
                        prompt={"schema_version": "deposium.document-task-prompt/v1",
                                "input_protocol": "current_equivalent", "question": "Task?",
                                "options": [{"id": task, "description": task} for task in
                                            ("catalog", "stored_summaries", "retrieve_answer", "abstain")],
                                "order": "canonical"})
        document.pop("choice_protocol_sha256")
        document.pop("init_wall_ms")
        validator.validate(document)

    def test_unavailable_resident_records_transport_and_setup_timing(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "resident"
            run_campaign(ROOT / "datasets/decisions-v1/cases.jsonl",
                         ROOT / "profiles/mcps-document-task-resident.json", archive,
                         max_new_cases=1)
            manifest = json.loads((archive / "manifest.json").read_text())
        validator = self.validator("campaign")
        validator.validate(manifest)
        provenance = manifest["adapter_provenance"]
        self.assertIs(provenance["available"], False)
        self.assertEqual(provenance["transport"], "resident_process_jsonl")
        self.assertGreaterEqual(provenance["init_wall_ms"], 0)
        mutations = [lambda v: v["adapter_provenance"].pop("resident_bridge_sha256"),
                     lambda v: v["adapter_provenance"].pop("init_wall_ms"),
                     lambda v: v["adapter_provenance"].update(available=True),
                     lambda v: v["adapter_provenance"].update(worker_load_ms=1),
                     lambda v: v["adapter_provenance"].update(transport="one_process_per_request_json_stdin"),
                     lambda v: v["adapter_provenance"].update(choice_protocol_sha256="0" * 64)]
        for mutate in mutations:
            value = deepcopy(manifest)
            mutate(value)
            with self.subTest(value=value):
                self.assertFalse(validator.is_valid(value))
        # A handshake can fail after the delegate observed its runtime. These
        # partial observations must remain archiveable with available:false.
        observed = deepcopy(manifest)
        props = observed["adapter_provenance"]
        props.update(component={"root": "/fixture", "head": "1" * 40,
                                "dirty": False, "canonical": True},
                     sources={"source.ts": "0" * 64},
                     lockfiles={"component.lock": "0" * 64, "workspace.lock": "0" * 64},
                     runtime={"node": "fixture", "tsx": "fixture", "zod": "fixture"},
                     bridge_sha256="0" * 64,
                     entrypoints={key: {"module": entry[0], "export": entry[1]}
                                  for key, entry in CONTRACTS.items()},
                     guards="isolated_function_only",
                     runtime_artifacts={"schema_version": "deposium.runtime-artifacts/v1",
                                        "hash_scope": "node_executable; selected_whole_package_js_json_native; esbuild_binaries",
                                        "total_bytes": 1,
                                        "packages": {"tsx": {"root": "/fixture/tsx", "version": "fixture"}},
                                        "files": [{"owner": "node", "path": "/fixture/node", "size": 1,
                                                   "sha256": "0" * 64, "mtime_ns": "0", "ctime_ns": "0",
                                                   "device": "0", "inode": "0"}],
                                        "limits": {"max_bytes": 209715200, "max_files": 5000}})
        validator.validate(observed)
        ready = deepcopy(observed)
        ready["adapter_provenance"].update(available=True, worker_load_ms=1)
        ready["adapter_provenance"].pop("availability_error")
        validator.validate(ready)
        ready["adapter_provenance"].pop("worker_load_ms")
        self.assertFalse(validator.is_valid(ready))

    def test_meta_schema_and_actual_offline_artifacts(self):
        for name in NAMES:
            Draft202012Validator.check_schema(load_schema(name))
        Draft202012Validator.check_schema(load_schema("case", 2))
        cases, _ = load_cases()
        for case in cases:
            self.validator("case").validate(case)
        research, _ = load_cases(ROOT / "datasets/context-choice-v1/cases.jsonl")
        for case in research:
            self.validator("case", 2).validate(case)
        for profile in candidate_profiles():
            self.validator("candidate").validate(profile)
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "control"
            run_campaign(ROOT / "datasets/decisions-v1/cases.jsonl",
                         ROOT / "profiles/fixture-control.json", archive)
            for name, filename in (("campaign", "manifest.json"), ("campaign-summary", "summary.json"),
                                   ("archive-seal", "seal.json")):
                self.validator(name).validate(json.loads((archive / filename).read_text()))
            for line in (archive / "raw.jsonl").read_text().splitlines():
                self.validator("result").validate(json.loads(line))

    def test_isolated_profile_rejects_unsupported_configuration(self):
        profile = isolated_profile()
        self.validator("candidate").validate(profile)
        mutations = [lambda v: v.update(model=None),
                     lambda v: v.update(revision=None),
                     lambda v: v.update(qualification="component_replay"),
                     lambda v: v.update(recordings="responses.jsonl"),
                     lambda v: v.update(capabilities=["mcps.document-followup"]),
                     lambda v: v["model"].update(repo_id="unreviewed/model"),
                     lambda v: v["model"].update(threads=True),
                     lambda v: v["model"].update(threads=5),
                     lambda v: v["model"].update(max_rss_mb=3073),
                     lambda v: v["model"].update(head_length=0),
                     lambda v: v["model"].update(max_length=8193),
                     lambda v: v["model"].update(prompt_path="  "),
                     lambda v: v["model"].update(extra="unexpected")]
        for mutate in mutations:
            value = deepcopy(profile)
            mutate(value)
            with self.subTest(value=value):
                self.assertFalse(self.validator("candidate").is_valid(value))

    def test_isolated_unavailable_archive_schema_and_metadata_boundaries(self):
        # Generate a zero-inference control archive, then validate a declaration
        # fixture for an unavailable model. No successful prediction is invented.
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "control"
            summary = run_campaign(ROOT / "datasets/decisions-v1/cases.jsonl",
                                   ROOT / "profiles/fixture-control.json", archive,
                                   max_new_cases=0)
            manifest = json.loads((archive / "manifest.json").read_text())
        profile = isolated_profile()
        manifest.update(qualification="model_isolated", proof_level="A",
                        input_protocol="current_equivalent")
        provenance = {"profile_sha256": "0" * 64, "adapter_sha256": "0" * 64,
                      "qualification": "model_isolated", "adapter": "julia",
                      "model": profile["model"], "model_revision": profile["revision"],
                      "capabilities": ["mcps.document-plan"], "available": False,
                      "identity_sha256": "0" * 64, "availability_error": "model_assets_missing"}
        manifest["adapter_provenance"] = provenance
        summary["qualification"] = "model_isolated"
        for component in manifest["stack_context"]["components"]:
            component.update(selected=False, omission_reason="model_isolated_only")
        for component in summary["stack_coverage"]:
            component.update(selected=False, omission_reason="model_isolated_only")
        self.validator("campaign").validate(manifest)
        self.validator("campaign-summary").validate(summary)
        self.assertEqual(summary["metrics"]["scored_cases"], 0)
        self.assertEqual(summary["metrics"]["verdict"], "invalid")
        # Partly completed setup may already retain exact prompt/assets/lock,
        # while runtime readiness and load measurements remain absent.
        partial = deepcopy(manifest)
        prompt = {"schema_version": "deposium.document-task-prompt/v1",
                  "input_protocol": "current_equivalent", "question": "Choose the task.",
                  "options": [{"id": task, "description": task} for task in
                              ("catalog", "stored_summaries", "retrieve_answer", "abstain")],
                  "order": "canonical"}
        assets = {"schema_version": "deposium.model-assets/v1", "repo_id": "SupersonicLabs/Julia-1",
                  "revision": "1" * 40,
                  "files": [{"path": "config.json", "size": 1, "sha256": "0" * 64}]}
        partial["adapter_provenance"].update(prompt=prompt, assets_manifest=assets,
                                              runtime_lock="torch==0\ntransformers==0\n")
        self.validator("campaign").validate(partial)
        invalid_prompt = deepcopy(partial)
        invalid_prompt["adapter_provenance"]["prompt"]["order"] = "reversed"
        self.assertFalse(self.validator("campaign").is_valid(invalid_prompt))
        reverse = deepcopy(partial)
        reverse["adapter_provenance"]["prompt"]["order"] = "reversed"
        reverse["adapter_provenance"]["prompt"]["options"].reverse()
        self.validator("campaign").validate(reverse)
        invalid_asset = deepcopy(partial)
        invalid_asset["adapter_provenance"]["assets_manifest"]["files"][0]["path"] = "../escape"
        self.assertFalse(self.validator("campaign").is_valid(invalid_asset))
        mutations = [lambda v: v.update(proof_level="harness_control"),
                     lambda v: v.update(input_protocol="recorded_control"),
                     lambda v: v["adapter_provenance"].update(available=True),
                     lambda v: v["adapter_provenance"].pop("model_revision"),
                     lambda v: v["adapter_provenance"].update(recordings_count=1),
                     lambda v: v["adapter_provenance"].update(load_ms=1),
                     lambda v: v["adapter_provenance"].update(runtime={"node": "x", "tsx": "x", "zod": "x"}),
                     lambda v: v["stack_context"]["components"][0].update(selected=True)]
        for mutate in mutations:
            value = deepcopy(manifest)
            mutate(value)
            with self.subTest(value=value):
                self.assertFalse(self.validator("campaign").is_valid(value))
        summary["stack_coverage"][0]["omission_reason"] = "recorded_control_only"
        self.assertFalse(self.validator("campaign-summary").is_valid(summary))

    def test_resume_rescore_and_unavailable_component_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run_campaign(ROOT / "datasets/decisions-v1/cases.jsonl",
                         ROOT / "profiles/fixture-control.json", root / "original", max_new_cases=1)
            resume_campaign(root / "original", root / "resumed", max_new_cases=1)
            rescore_campaign(root / "original", root / "rescored")
            run_campaign(ROOT / "datasets/decisions-v1/cases.jsonl",
                         ROOT / "profiles/mcps-current.json", root / "unavailable", max_new_cases=1)
            for archive in (root / "resumed", root / "rescored", root / "unavailable"):
                self.validator("campaign").validate(json.loads((archive / "manifest.json").read_text()))
                self.validator("campaign-summary").validate(json.loads((archive / "summary.json").read_text()))
            manifest = json.loads((root / "unavailable/manifest.json").read_text())
            self.assertIs(manifest["adapter_provenance"]["available"], False)
            self.assertEqual(manifest["proof_level"], "A")
            self.assertEqual(manifest["stack_context"]["inventory_status"], "not_observed")
            value = deepcopy(manifest)
            value["stack_context"]["inventory_status"] = "observed"
            self.assertFalse(self.validator("campaign").is_valid(value))
            value = deepcopy(manifest)
            value["mode"] = "resume"
            self.assertFalse(self.validator("campaign").is_valid(value))
            value = deepcopy(manifest)
            value["adapter_provenance"]["available"] = True
            self.assertFalse(self.validator("campaign").is_valid(value))

    def test_negative_case_profile_and_raw_shapes(self):
        case = load_cases()[0][0]
        profile = load_profile(ROOT / "profiles/mcps-current.json")[0]
        result = {"schema_version": "deposium.result/v1", "case_id": "case", "contract_id": "contract",
                  "request_sha256": "0" * 64, "status": "ok", "output": {}, "raw_output": {},
                  "error": None, "duration_ms": 1}
        self.validator("result").validate(result)
        mutations = [("case", case, lambda value: value["reference"].update(assertions=[])),
                     ("case", case, lambda value: value["reference"]["assertions"][0].update(path="/~2")),
                     ("case", case, lambda value: value["reference"]["assertions"][0].update(op="one_of", value=[])),
                     ("candidate", profile, lambda value: value.update(qualification="harness_control")),
                     ("candidate", profile, lambda value: value.update(capabilities=["mcps.search"])),
                     ("candidate", profile, lambda value: value.update(timeout_seconds=True)),
                     ("candidate", profile, lambda value: value.update(profile_id="  ")),
                     ("result", result, lambda value: value.update(duration_ms=-1)),
                     ("result", result, lambda value: value.update(duration_ms=True)),
                     ("result", result, lambda value: value.update(status="unknown")),
                     ("result", result, lambda value: value.update(error={"provider_log": "bad"})),
                     ("result", result, lambda value: value.pop("raw_output")),
                     ("result", result, lambda value: value.update(extra=True))]
        for name, original, mutate in mutations:
            value = deepcopy(original)
            mutate(value)
            with self.subTest(schema=name, value=value):
                self.assertFalse(self.validator(name).is_valid(value))

    def test_summary_rejects_a_pass_without_scored_cases(self):
        with tempfile.TemporaryDirectory() as folder:
            summary = run_campaign(ROOT / "datasets/decisions-v1/cases.jsonl",
                                   ROOT / "profiles/fixture-control.json", Path(folder) / "empty",
                                   max_new_cases=0)
        self.validator("campaign-summary").validate(summary)
        self.assertEqual(summary["metrics"]["scored_cases"], 0)
        summary["metrics"]["verdict"] = "pass"
        self.assertFalse(self.validator("campaign-summary").is_valid(summary))
