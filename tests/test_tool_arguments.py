"""Actual local tool execution, guards and archive-only rescore controls."""
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import campaigns, tool_arguments
from deposium_bench.adapters import AdapterError, create_adapter, load_profile, parse_profile, _identity
from deposium_bench.cases import CaseError, candidate_request, load_cases, validate_cases
from deposium_bench.scoring import score_case, summarize
from deposium_bench.synthetic_tools import FixtureStore, ToolError, artifact_id, canonical

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datasets/tool-arguments-v1/cases.jsonl"
PROFILE = ROOT / "profiles/tool-arguments-control.json"
DEFAULT_PROPOSAL = object()


class ToolArgumentsTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.digest = load_cases(DATASET)
        self.profile, _ = load_profile(PROFILE)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)

    def proposal(self, case=None):
        case = case or self.cases[0]
        task = case["input"]
        return {"tool_id": "fixture.sum", "arguments": {
            "artifact_id": artifact_id(task), "column": task["dataset"]["column"],
            "unit": task["dataset"]["unit"], "scope_id": task["scope_id"]}}

    def adapter(self, output=DEFAULT_PROPOSAL, status="ok"):
        responses = self.tmp / "responses.jsonl"
        rows = [{"case_id": case["case_id"], "status": status,
                 "output": self.proposal(case) if output is DEFAULT_PROPOSAL else deepcopy(output),
                 "raw_output": None, "error": None} for case in self.cases]
        if status != "ok":
            for row in rows:
                row["output"] = None
        responses.write_text("".join(json.dumps(row) + "\n" for row in rows))
        profile = deepcopy(self.profile)
        profile["recordings"] = responses.name
        path = self.tmp / "profile.json"
        path.write_text(json.dumps(profile))
        return create_adapter(profile, path)

    def test_four_train_cases_literals_and_frozen_manifest(self):
        manifest = json.loads(DATASET.with_name("manifest.json").read_text())
        self.assertEqual(len(self.cases), 4)
        self.assertEqual(manifest["cases_sha256"], self.digest)
        self.assertEqual({c["split"] for c in self.cases}, {"train"})
        self.assertEqual({c["language"] for c in self.cases}, {"fr", "en"})
        self.assertEqual(len({c["translation_family"] for c in self.cases}), 2)
        self.assertEqual({c["input"]["dataset"]["unit"]: next(a["value"] for a in c["reference"]["assertions"]
                         if a["path"] == "/execution/value") for c in self.cases}, {"EUR": 60, "kg": 12})

    def test_actual_lookup_and_sum_produce_known_results_and_literal_binding(self):
        adapter = create_adapter(self.profile, PROFILE)
        for case in self.cases:
            response = adapter.predict(candidate_request(case))
            output = response["output"]
            self.assertEqual(response["status"], "ok")
            self.assertEqual([step["tool_id"] for step in output["trace"]], ["fixture.lookup", "fixture.sum"])
            self.assertEqual(output["trace"][0]["artifact"]["artifact_id"],
                             output["trace"][1]["arguments"]["artifact_id"])
            self.assertEqual(output["execution"]["value"], 60 if case["input"]["dataset"]["unit"] == "EUR" else 12)
            self.assertTrue(score_case(case, response)["passed"])
            tool_arguments.validate_receipt(case["input"], output)

    def test_projection_is_actual_observation_without_annotations_or_identity(self):
        case = self.cases[0]
        response = self.adapter().predict(candidate_request(case))
        projected = response["output"]["candidate_input"]
        self.assertEqual(set(projected), {"schema_version", "request", "scope_id", "tool_schema", "observation"})
        self.assertEqual(projected["observation"], response["output"]["trace"][0])
        encoded = json.dumps(projected)
        for forbidden in ("reference", "assertions", "translation_family", "case_id", "split", "rationale"):
            self.assertNotIn('"' + forbidden + '"', encoded)
        self.assertNotIn(case["case_id"], encoded)
        self.assertEqual(response["output"]["candidate_input_sha256"], hashlib.sha256(canonical(projected)).hexdigest())

    def test_wrong_values_types_scope_and_bindings_never_execute_sum(self):
        mutations = {
            "wrong_unit": lambda p: p["arguments"].update(unit="USD"),
            "wrong_column": lambda p: p["arguments"].update(column="different"),
            "wrong_scope": lambda p: p["arguments"].update(scope_id="other-synthetic-scope"),
            "invented_id": lambda p: p["arguments"].update(artifact_id="artifact:" + "0" * 64),
            "missing": lambda p: p["arguments"].pop("column"),
            "wrong_type": lambda p: p["arguments"].update(column=True),
            "wrong_tool": lambda p: p.update(tool_id="fixture.lookup"),
            "fake_receipt": lambda p: p.update(execution={"executed": True, "value": 60}),
        }
        for name, mutate in mutations.items():
            proposal = self.proposal()
            mutate(proposal)
            with self.subTest(failure=name), patch.object(FixtureStore, "sum", side_effect=AssertionError("sum must be guarded")):
                response = self.adapter(proposal).predict(candidate_request(self.cases[0]))
                self.assertEqual(len(response["output"]["trace"]), 1)
                self.assertFalse(response["output"]["execution"]["executed"])
                self.assertFalse(score_case(self.cases[0], response)["passed"])

    def test_empty_candidate_and_extra_execution_fields_cannot_forge_success(self):
        for output in (None, {}, [], "success", {"execution": {"executed": True}}):
            with self.subTest(output=output):
                response = self.adapter(output).predict(candidate_request(self.cases[0]))
                self.assertFalse(score_case(self.cases[0], response)["passed"])
                self.assertEqual(len(response["output"]["trace"]), 1)

    def test_changed_source_and_live_lookup_id_invalidate_fixed_proposal(self):
        request = candidate_request(self.cases[0])
        request["input"]["dataset"]["values"][0] += 1
        with patch.object(FixtureStore, "sum", side_effect=AssertionError("stale binding must block")):
            response = self.adapter().predict(request)
        self.assertFalse(response["output"]["checks"]["binding_valid"])
        original = FixtureStore.lookup
        def shifted(store):
            receipt = original(store)
            receipt["artifact"]["artifact_id"] = "artifact:" + "f" * 64
            return receipt
        with patch.object(FixtureStore, "lookup", shifted), patch.object(FixtureStore, "sum", side_effect=AssertionError("actual ID must bind")):
            response = self.adapter().predict(candidate_request(self.cases[0]))
        self.assertFalse(response["output"]["checks"]["binding_valid"])
        self.assertFalse(score_case(self.cases[0], response)["passed"])

    def test_dependency_order_and_resource_budget_are_independent(self):
        store = FixtureStore(self.cases[0]["input"])
        args = self.proposal()["arguments"]
        with self.assertRaises(ToolError):
            store.sum(args)
        self.assertEqual(store.calls, 0)
        store.lookup()
        store.sum(args)
        self.assertEqual(store.calls, 2)
        with self.assertRaisesRegex(ToolError, "budget"):
            store.sum(args)
        self.assertEqual(store.calls, 2)

    def test_nonok_transport_keeps_actual_lookup_and_status_denominators(self):
        case = self.cases[0]
        for status in ("missing", "unsupported", "error", "timeout", "abstain"):
            response = self.adapter(status=status).predict(candidate_request(case))
            self.assertEqual(response["status"], status)
            self.assertIsNone(response["output"])
            self.assertEqual(len(response["raw_output"]["trace"]), 1)
            report = summarize([case], [{"case_id": case["case_id"], **response}])
            metrics = report["task_metrics"][tool_arguments.CONTRACT]
            self.assertEqual(metrics["tool_calls_observed"], 1)
            self.assertEqual(metrics["eligible_cases"], 1)
            self.assertEqual(metrics["result_correct_cases"], 0)
            self.assertNotEqual(report["verdict"], "pass")
        report = summarize([case], [])
        self.assertEqual(report["verdict"], "invalid")
        self.assertEqual(report["task_metrics"][tool_arguments.CONTRACT]["cases_without_execution_trace"], 1)

    def test_receipt_mutations_fail_without_tool_reexecution(self):
        case = self.cases[0]
        original = self.adapter().predict(candidate_request(case))
        for field in ("value", "unit", "executed"):
            output = deepcopy(original)
            output["output"]["execution"][field] = "wrong"
            with patch.object(FixtureStore, "lookup", side_effect=AssertionError("scoring must not execute")), \
                    patch.object(FixtureStore, "sum", side_effect=AssertionError("scoring must not execute")):
                self.assertFalse(score_case(case, output)["passed"])
        for mutate in (lambda p: p["checks"].update(binding_valid=False),
                       lambda p: p.update(candidate_input_sha256="0" * 64),
                       lambda p: p["trace"][1].update(value=999)):
            response = deepcopy(original)
            mutate(response["output"])
            with patch.object(FixtureStore, "lookup", side_effect=AssertionError("scoring must not execute")), \
                    patch.object(FixtureStore, "sum", side_effect=AssertionError("scoring must not execute")):
                self.assertFalse(score_case(case, response)["passed"])

    def test_case_oracle_cannot_omit_checks_or_change_expected_result(self):
        for variant in ("missing", "wrong", "empty_fixture", "bool_fixture"):
            case = deepcopy(self.cases[0])
            if variant == "missing":
                case["reference"]["assertions"].pop()
            elif variant == "wrong":
                next(a for a in case["reference"]["assertions"] if a["path"] == "/execution/value")["value"] = 999
            else:
                case["input"]["dataset"]["values"] = [] if variant == "empty_fixture" else [True]
            with self.subTest(variant=variant), self.assertRaises(CaseError):
                validate_cases([case])
        for values in ([0] * 33, [10**9 + 1], [1.5]):
            case = deepcopy(self.cases[0])
            case["input"]["dataset"]["values"] = values
            with self.subTest(values=values), self.assertRaises(CaseError):
                validate_cases([case])
        case = deepcopy(self.cases[0])
        case["input"]["request"] = "x" * 8193
        with self.assertRaises(CaseError):
            validate_cases([case])

    def test_only_fixture_adapter_can_claim_execution_contract(self):
        for name in ("recorded", "systemone_local", "mcps", "gliclass", "fixture_arguments"):
            profile = deepcopy(self.profile)
            profile["adapter"] = name
            if name == "fixture_arguments":
                profile["qualification"] = "model_isolated"
            with self.subTest(adapter=name), self.assertRaises(AdapterError):
                parse_profile(json.dumps(profile).encode())

    def test_closure_hashes_and_changed_runtime_bytes_change_identity(self):
        adapter = create_adapter(self.profile, PROFILE)
        names = ("adapters.py", "synthetic_tools.py", "tool_arguments.py")
        hashes = {name: hashlib.sha256((ROOT / "deposium_bench" / name).read_bytes()).hexdigest() for name in names}
        self.assertEqual(adapter.provenance["adapter_sha256"], _identity(hashes))
        for name in names:
            (self.tmp / name).write_bytes((ROOT / "deposium_bench" / name).read_bytes())
        (self.tmp / "synthetic_tools.py").write_text("changed fixture source bytes\n")
        with patch.object(tool_arguments, "__file__", str(self.tmp / "tool_arguments.py")):
            changed = create_adapter(self.profile, PROFILE)
        self.assertNotEqual(changed.provenance["identity_sha256"], adapter.provenance["identity_sha256"])

    def test_shared_campaign_archive_rescore_and_recording_integrity(self):
        run = self.tmp / "run"
        first = campaigns.run_campaign(DATASET, PROFILE, run)
        self.assertEqual(first["metrics"]["passed_cases"], 4)
        self.assertEqual(first["qualification"], "harness_control")
        self.assertEqual(first["metrics"]["task_metrics"][tool_arguments.CONTRACT]["tool_calls_observed"], 8)
        original = {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}
        with patch.object(FixtureStore, "lookup", side_effect=AssertionError("rescore reexecuted lookup")), \
                patch.object(FixtureStore, "sum", side_effect=AssertionError("rescore reexecuted sum")):
            rescored = campaigns.rescore_campaign(run, self.tmp / "rescore")
        self.assertEqual(rescored["metrics"], first["metrics"])
        self.assertEqual({p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}, original)
        manifest = json.loads(original["manifest.json"])
        self.assertEqual(manifest["input_protocol"], "fixture_arguments_control")
        self.assertIn("synthetic_tools.py", manifest["scorer"]["files"])
        self.assertTrue((run / "recordings.jsonl").exists())
        (run / "recordings.jsonl").write_text("tampered\n")
        with self.assertRaises(campaigns.CampaignError):
            campaigns.rescore_campaign(run, self.tmp / "tampered")

    def test_optional_schema_contracts_accept_real_artifacts_and_reject_spoofs(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is optional")
        summary = campaigns.run_campaign(DATASET, PROFILE, self.tmp / "schema-run")
        artifacts = {"candidate": self.profile, "campaign-summary": summary,
                     "campaign": json.loads((self.tmp / "schema-run/manifest.json").read_text())}
        for name, artifact in artifacts.items():
            schema = json.loads((ROOT / "schemas" / (name + "-v1.schema.json")).read_text())
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.validate(artifact, schema)
        raw_schema = json.loads((ROOT / "schemas/result-v1.schema.json").read_text())
        for line in (self.tmp / "schema-run/raw.jsonl").read_text().splitlines():
            jsonschema.validate(json.loads(line), raw_schema)
        profile = deepcopy(self.profile)
        profile["adapter"] = "recorded"
        schema = json.loads((ROOT / "schemas/candidate-v1.schema.json").read_text())
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(profile, schema)

    def test_fixture_adapter_runs_without_network_or_external_processes(self):
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")), \
                patch("subprocess.Popen", side_effect=AssertionError("external execution forbidden")):
            adapter = create_adapter(self.profile, PROFILE)
            responses = [adapter.predict(candidate_request(case)) for case in self.cases]
        self.assertTrue(all(response["output"]["execution"]["executed"] for response in responses))

    def test_real_shared_cli_executes_the_fixture_campaign(self):
        command = [sys.executable, "-B", "-m", "deposium_bench", "run", "--dataset", str(DATASET),
                   "--profile", str(PROFILE), "--output", str(self.tmp / "cli"), "--format", "json"]
        run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(run.stdout)
        self.assertEqual(report["metrics"]["passed_cases"], 4)
        self.assertEqual(report["metrics"]["task_metrics"][tool_arguments.CONTRACT]["tool_calls_observed"], 8)

    def test_import_does_not_construct_transport_or_execute_tools(self):
        name = "deposium_bench._tool_arguments_import_control"
        spec = importlib.util.spec_from_file_location(name, ROOT / "deposium_bench/tool_arguments.py")
        module = importlib.util.module_from_spec(spec)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("deposium_bench.adapters.RecordedAdapter", side_effect=AssertionError("transport on import")), \
                patch.object(FixtureStore, "lookup", side_effect=AssertionError("lookup on import")), \
                patch.object(FixtureStore, "sum", side_effect=AssertionError("sum on import")), \
                patch("socket.create_connection", side_effect=AssertionError("network on import")), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            spec.loader.exec_module(module)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
