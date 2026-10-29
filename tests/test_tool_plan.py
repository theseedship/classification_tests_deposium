"""Structured proposal controls using the existing case/adapter/campaign engine."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import campaigns
from deposium_bench.adapters import AdapterError, create_adapter, load_profile, parse_profile
from deposium_bench.cases import CaseError, candidate_request, load_cases, validate_cases
from deposium_bench.scoring import score_case, summarize
from deposium_bench.tool_plan import CONTRACT, validate_input, validate_output

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datasets/tool-plan-pilot-v1/cases.jsonl"
PROFILE = ROOT / "profiles/tool-plan-control.json"


def malformed_proposals(case):
    """Named independent counterexamples to the complete two-call proposal."""
    original = case["reference"]["assertions"][0]["value"][0]
    variants = {"empty": {}, "null": None, "text": "success", "array": []}
    changes = {
        "wrong_version": lambda p: p.update(schema_version="deposium.tool-plan-output/v2"),
        "premature_success": lambda p: p.update(decision="success"),
        "no_calls": lambda p: p.update(calls=[]),
        "missing_result": lambda p: p.pop("result_artifact_id"),
        "extra_field": lambda p: p.update(answer=42),
        "overcalling": lambda p: p["calls"].append(deepcopy(p["calls"][1])),
        "unknown_tool": lambda p: p["calls"][0].update(tool_id="private.real-tool"),
        "missing_argument": lambda p: p["calls"][0]["arguments"].pop("field"),
        "extra_argument": lambda p: p["calls"][0]["arguments"].update(tenant="fictional"),
        "bad_enum": lambda p: p["calls"][0]["arguments"].update(field="unknown"),
        "wrong_enum_type": lambda p: p["calls"][0]["arguments"].update(field=True),
        "forward_binding": lambda p: p["calls"][1]["arguments"].update(values="a3"),
        "self_binding": lambda p: p["calls"][1]["arguments"].update(values="a2"),
        "bad_binding_type": lambda p: p["calls"][1]["arguments"].update(values={"artifact": "a1"}),
        "renamed_artifact": lambda p: p["calls"][0].update(output_artifact_id="lookup-output"),
        "reused_artifact": lambda p: p["calls"][1].update(output_artifact_id="a1"),
        "wrong_result": lambda p: p.update(result_artifact_id="a1"),
    }
    for name, mutate in changes.items():
        proposal = deepcopy(original)
        mutate(proposal)
        variants[name] = proposal
    return variants


class ToolPlanTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.digest = load_cases(DATASET)
        self.profile, _ = load_profile(PROFILE)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.tmp = Path(self.temporary.name)

    def control_profile(self, outputs):
        recordings = self.tmp / "responses.jsonl"
        rows = [{"case_id": case["case_id"], "status": "ok", "output": output,
                 "raw_output": None, "error": None}
                for case, output in zip(self.cases, outputs, strict=True)]
        recordings.write_text("".join(json.dumps(row) + "\n" for row in rows))
        profile = deepcopy(self.profile)
        profile["recordings"] = recordings.name
        destination = self.tmp / "control.json"
        destination.write_text(json.dumps(profile))
        return destination

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "deposium_bench", *map(str, args)],
                              cwd=ROOT, text=True, capture_output=True, check=False)

    def test_manifest_has_one_materialized_train_family_and_only_proposed_other_splits(self):
        manifest = json.loads(DATASET.with_name("manifest.json").read_text())
        self.assertEqual(len(self.cases), 2)
        self.assertEqual({case["language"] for case in self.cases}, {"fr", "en"})
        self.assertEqual({case["split"] for case in self.cases}, {"train"})
        self.assertEqual(len({case["translation_family"] for case in self.cases}), 1)
        self.assertEqual(len({case["scenario_id"] for case in self.cases}), 1)
        self.assertEqual(manifest["cases_sha256"], self.digest)
        self.assertEqual(manifest["materialized"]["by_split"],
                         {"train": 2, "calibration": 0, "test": 0})
        self.assertEqual(manifest["review"], "agent_only_pending_human")
        proposal = manifest["proposal"]
        self.assertEqual(proposal["status"], "proposed_not_frozen")
        self.assertEqual(len(proposal["families"]), 12)
        self.assertEqual(proposal["families_by_planned_split"],
                         {"train": 4, "calibration": 4, "test": 4})
        for split in ("train", "calibration", "test"):
            self.assertEqual(sum(row["planned_split"] == split for row in proposal["families"]), 4)
        self.assertEqual(sum(row["status"] == "materialized_train_only"
                             for row in proposal["families"]), 1)

    def test_both_complete_alternatives_pass_the_shared_exact_scorer_in_both_languages(self):
        for case in self.cases:
            alternatives = case["reference"]["assertions"][0]["value"]
            self.assertEqual(len(alternatives), 2)
            self.assertEqual({p["calls"][1]["tool_id"] for p in alternatives},
                             {"numeric.sum", "numeric.aggregate"})
            for proposal in alternatives:
                with self.subTest(language=case["language"], tool=proposal["calls"][1]["tool_id"]):
                    validate_output(proposal, case["input"])
                    self.assertEqual(proposal["decision"], "propose")
                    score = score_case(case, {"status": "ok", "output": proposal})
                    self.assertTrue(score["scored"])
                    self.assertTrue(score["passed"])

    def test_structurally_valid_wrong_source_field_and_operation_still_fail_semantically(self):
        case = self.cases[0]
        for field, value in (("dataset_id", "quarterly-sales"), ("field", "quantity")):
            wrong = deepcopy(case["reference"]["assertions"][0]["value"][0])
            wrong["calls"][0]["arguments"][field] = value
            validate_output(wrong, case["input"])
            self.assertFalse(score_case(case, {"status": "ok", "output": wrong})["passed"])
        wrong = deepcopy(case["reference"]["assertions"][0]["value"][1])
        wrong["calls"][1]["arguments"]["operation"] = "mean"
        validate_output(wrong, case["input"])
        self.assertFalse(score_case(case, {"status": "ok", "output": wrong})["passed"])
        one_call = deepcopy(case["reference"]["assertions"][0]["value"][0])
        one_call["calls"] = one_call["calls"][:1]
        one_call["result_artifact_id"] = "a1"
        validate_output(one_call, case["input"])
        self.assertFalse(score_case(case, {"status": "ok", "output": one_call})["passed"])

    def test_empty_malformed_unknown_overcalling_and_premature_success_cannot_pass(self):
        for case in self.cases:
            for name, output in malformed_proposals(case).items():
                with self.subTest(language=case["language"], failure=name):
                    with self.assertRaises(CaseError):
                        validate_output(output, case["input"])
                    score = score_case(case, {"status": "ok", "output": output})
                    self.assertTrue(score["scored"])
                    self.assertFalse(score["passed"])

    def test_artifact_advertised_type_and_call_order_are_checked(self):
        task_input = deepcopy(self.cases[0]["input"])
        task_input["catalogue"].append({"tool_id": "metadata.lookup", "description": "Metadata only",
                                       "arguments": {}, "output_type": "metadata"})
        proposal = deepcopy(self.cases[0]["reference"]["assertions"][0]["value"][0])
        proposal["calls"][0] = {"tool_id": "metadata.lookup", "arguments": {},
                                 "output_artifact_id": "a1"}
        with self.assertRaisesRegex(CaseError, "artifact binding"):
            validate_output(proposal, task_input)
        proposal = deepcopy(self.cases[0]["reference"]["assertions"][0]["value"][0])
        proposal["calls"].reverse()
        with self.assertRaises(CaseError):
            validate_output(proposal, task_input)

    def test_input_bounds_and_invalid_reference_outputs_are_refused(self):
        original = self.cases[0]["input"]
        inputs = []
        for budget in (0, 3, True, 2.0):
            bad = deepcopy(original)
            bad["max_calls"] = budget
            inputs.append(bad)
        duplicate = deepcopy(original)
        duplicate["catalogue"].append(deepcopy(duplicate["catalogue"][0]))
        inputs.append(duplicate)
        bad = deepcopy(original)
        bad["request"] = "x" * 8193
        inputs.append(bad)
        bad = deepcopy(original)
        bad["catalogue"][0]["arguments"]["field"]["values"] = ["x"] * 33
        inputs.append(bad)
        bad = deepcopy(original)
        bad["catalogue"][0]["arguments"]["field"] = {"type": "free_text"}
        inputs.append(bad)
        for bad in inputs:
            with self.subTest(input=bad):
                with self.assertRaises(CaseError):
                    validate_input(bad)
        for name, output in malformed_proposals(self.cases[0]).items():
            bad_case = deepcopy(self.cases[0])
            bad_case["reference"]["assertions"][0]["value"] = [output]
            with self.subTest(reference=name), self.assertRaises(CaseError):
                validate_cases([bad_case])

    def test_annotations_are_not_projected_and_requests_are_independent_copies(self):
        case = self.cases[0]
        request = candidate_request(case)
        self.assertEqual(set(request), {"case_id", "contract_id", "input"})
        self.assertEqual(request["input"], case["input"])
        for key in ("reference", "split", "rationale", "scenario_id", "translation_family", "document_ids"):
            self.assertNotIn(key, request)
            self.assertNotIn(key, request["input"])
        request["input"]["catalogue"][0]["description"] = "Changed copy"
        self.assertNotEqual(request["input"], case["input"])
        for forbidden in ("reference", "gold", "rationale", "annotations"):
            invalid = deepcopy(case)
            invalid["input"]["catalogue"][0]["arguments"][forbidden] = {"type": "enum", "values": ["x"]}
            with self.subTest(forbidden=forbidden), self.assertRaises(CaseError):
                candidate_request(invalid)

    def test_research_application_links_refuse_benchmark_native_contract(self):
        research, _ = load_cases(ROOT / "datasets/context-choice-v1/cases.jsonl")
        case = deepcopy(research[0])
        case["evaluation"]["related_contract_ids"] = [CONTRACT]
        with self.assertRaisesRegex(CaseError, "existing application contracts"):
            validate_cases([case])

    def test_existing_model_and_application_profiles_cannot_claim_the_new_capability(self):
        checked = set()
        for path in sorted((ROOT / "profiles").glob("*.json")):
            profile = json.loads(path.read_text())
            if (profile.get("schema_version") != "deposium.candidate/v1"
                    or profile.get("adapter") == "recorded"):
                continue
            checked.add(profile["adapter"])
            profile["capabilities"] = [CONTRACT]
            with self.subTest(profile=path.name), self.assertRaises(AdapterError):
                parse_profile(json.dumps(profile).encode())
        self.assertTrue({"gliclass", "jev_http", "decision3_http", "mcps"} <= checked)
        # Native profiles are captured dynamically, rather than checked in.
        native = {"schema_version": "deposium.candidate/v1", "profile_id": "native-control",
                  "adapter": "systemone_local", "qualification": "model_isolated",
                  "capabilities": ["bench.context-choice"], "revision": "a" * 40,
                  "recordings": None, "timeout_seconds": 1,
                  "model": {"endpoint": "http://127.0.0.1:11438/v1/systemone",
                            "model_id": "fixture-model", "repo_id": "fixture/model",
                            "session_manifest": "session.json", "session_sha256": "b" * 64,
                            "max_length": 4096, "max_rss_mb": 20480,
                            "credential_env": "DEPOSIUM_BENCH_LOCAL_KEY"}}
        parse_profile(json.dumps(native).encode())
        native["capabilities"] = [CONTRACT]
        with self.assertRaises(AdapterError):
            parse_profile(json.dumps(native).encode())

    def test_optional_candidate_json_schema_agrees_with_recorded_only_runtime_gate(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is optional")
        schema = json.loads((ROOT / "schemas/candidate-v1.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        validator.validate(self.profile)
        for adapter in schema["properties"]["adapter"]["enum"]:
            if adapter == "recorded":
                continue
            profile = deepcopy(self.profile)
            profile["adapter"] = adapter
            with self.subTest(adapter=adapter):
                self.assertFalse(validator.is_valid(profile))
                with self.assertRaises(AdapterError):
                    parse_profile(json.dumps(profile).encode())

    def test_recorded_shared_campaign_and_rescore_are_control_evidence_only(self):
        seen = []
        def factory(*args, **kwargs):
            adapter = create_adapter(*args, **kwargs)
            predict = adapter.predict
            def capture(request):
                self.assertEqual(set(request), {"case_id", "contract_id", "input"})
                self.assertNotIn("reference", request)
                seen.append(request)
                return predict(request)
            adapter.predict = capture
            return adapter
        with patch.object(campaigns, "create_adapter", side_effect=factory):
            summary = campaigns.run_campaign(DATASET, PROFILE, self.tmp / "run")
        self.assertEqual(len(seen), 2)
        self.assertEqual(summary["qualification"], "harness_control")
        self.assertEqual(summary["completion_status"], "complete")
        self.assertEqual(summary["metrics"]["passed_cases"], 2)
        self.assertEqual(summary["metrics"]["scored_cases"], 2)
        self.assertEqual(summary["metrics"]["verdict"], "pass")
        manifest = json.loads((self.tmp / "run/manifest.json").read_text())
        self.assertEqual(manifest["proof_level"], "harness_control")
        self.assertIsNone(manifest["adapter_provenance"]["model"])
        self.assertEqual(manifest["stack_context"]["inventory_status"], "not_observed")
        self.assertFalse(any(row["selected"] for row in summary["stack_coverage"]))
        self.assertEqual(manifest["scorer"]["files"]["tool_plan.py"],
                         hashlib.sha256((ROOT / "deposium_bench/tool_plan.py").read_bytes()).hexdigest())
        original = (self.tmp / "run/raw.jsonl").read_bytes()
        with patch.object(campaigns, "create_adapter", side_effect=AssertionError("no inference during rescore")):
            rescored = campaigns.rescore_campaign(self.tmp / "run", self.tmp / "rescored")
        self.assertEqual(rescored["metrics"], summary["metrics"])
        self.assertEqual((self.tmp / "rescored/raw.jsonl").read_bytes(), original)
        self.assertEqual((self.tmp / "run/raw.jsonl").read_bytes(), original)

    def test_cli_validates_and_replays_both_positive_alternatives(self):
        validated = self.cli("validate-cases", "--dataset", DATASET)
        self.assertEqual(validated.returncode, 0, validated.stderr)
        self.assertEqual(json.loads(validated.stdout)["cases"], 2)
        for alternative in (0, 1):
            outputs = [case["reference"]["assertions"][0]["value"][alternative] for case in self.cases]
            profile = self.control_profile(outputs)
            run = self.cli("run", "--dataset", DATASET, "--profile", profile,
                           "--output", self.tmp / f"valid-{alternative}", "--format", "json")
            self.assertEqual(run.returncode, 0, run.stderr)
            summary = json.loads(run.stdout)
            self.assertEqual(summary["metrics"]["passed_cases"], 2)
            self.assertEqual(summary["qualification"], "harness_control")

    def test_cli_negative_controls_fail_without_dropping_bad_outputs(self):
        valid = self.cases[1]["reference"]["assertions"][0]["value"][1]
        wrong = deepcopy(valid)
        wrong["calls"][0]["arguments"]["field"] = "quantity"
        validate_output(wrong, self.cases[0]["input"])
        negatives = {**malformed_proposals(self.cases[0]), "well_typed_wrong_field": wrong}
        for name, invalid in negatives.items():
            with self.subTest(failure=name):
                profile = self.control_profile([invalid, valid])
                run = self.cli("run", "--dataset", DATASET, "--profile", profile,
                               "--output", self.tmp / ("bad-" + name), "--format", "json")
                self.assertEqual(run.returncode, 1, run.stderr)
                summary = json.loads(run.stdout)
                self.assertEqual(summary["completion_status"], "complete")
                self.assertEqual(summary["metrics"]["scored_cases"], 2)
                self.assertEqual(summary["metrics"]["passed_cases"], 1)
                self.assertEqual(summary["metrics"]["failed_cases"], 1)
                self.assertEqual(summary["metrics"]["counts_by_status"]["ok"], 2)
                self.assertEqual(summary["metrics"]["verdict"], "fail")

    def test_abstention_and_no_scored_cases_do_not_pass(self):
        self.assertFalse(score_case(self.cases[0], {"status": "abstain"})["passed"])
        summary = summarize(self.cases, [{"case_id": self.cases[0]["case_id"], "status": "unsupported"}])
        self.assertEqual(summary["scored_cases"], 0)
        self.assertEqual(summary["passed_cases"], 0)
        self.assertEqual(summary["counts_by_status"]["unsupported"], 1)
        self.assertEqual(summary["counts_by_status"]["missing"], 1)
        self.assertEqual(summary["verdict"], "invalid")


if __name__ == "__main__":
    unittest.main()
