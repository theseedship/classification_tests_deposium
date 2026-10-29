"""Selection semantics and actual shared-engine replay; no candidate inference."""
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
from deposium_bench.tool_discovery import CONTRACT, OUTPUT_VERSION, validate_input, validate_output

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datasets/tool-discovery-v1/cases.jsonl"
PROFILE = ROOT / "profiles/tool-discovery-control.json"


def proposal(case, index=0):
    selection = deepcopy(case["reference"]["assertions"][0]["value"][index])
    return {"schema_version": OUTPUT_VERSION, "shortlist": list(selection["tool_ids"]),
            "selection": selection}


class ToolDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.digest = load_cases(DATASET)
        self.profile, _ = load_profile(PROFILE)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.tmp = Path(self.temporary.name)

    def score(self, index=0, output=None):
        case = self.cases[index]
        return score_case(case, {"status": "ok", "output": proposal(case) if output is None else output})

    def test_manifest_pins_canonical_catalogue_and_family_splits(self):
        manifest = json.loads(DATASET.with_name("manifest.json").read_text())
        catalogue_path = DATASET.with_name("catalogue.json")
        catalogue = json.loads(catalogue_path.read_text())
        self.assertEqual(manifest["cases_sha256"], self.digest)
        self.assertEqual(manifest["catalogue_sha256"], hashlib.sha256(catalogue_path.read_bytes()).hexdigest())
        self.assertEqual((manifest["case_count"], manifest["family_count"], manifest["catalogue_tool_count"]), (12, 6, 12))
        self.assertEqual(manifest["counts_by_language"], {"fr": 6, "en": 6})
        self.assertEqual(manifest["counts_by_split"], {"train": 4, "calibration": 4, "test": 4})
        self.assertEqual(manifest["review"], "agent_only_pending_human")
        self.assertEqual(manifest["model_cases_scored"], 0)
        for case in self.cases:
            canonical = [{**tool, "description": tool["description"][case["language"]]}
                         for tool in catalogue["tools"]]
            self.assertEqual(case["input"]["catalogue"], canonical)
        for family in manifest["families"]:
            cases = [c for c in self.cases if c["translation_family"] == family["family_id"]]
            self.assertEqual(len(cases), 2)
            self.assertEqual({c["language"] for c in cases}, {"fr", "en"})
            self.assertEqual({c["split"] for c in cases}, {family["split"]})
            self.assertEqual({c["case_id"] for c in cases}, set(family["case_ids"]))
            self.assertEqual(cases[0]["reference"], cases[1]["reference"])

    def test_every_authored_alternative_and_tool_order_is_accepted(self):
        for case in self.cases:
            for alternative in range(len(case["reference"]["assertions"][0]["value"])):
                value = proposal(case, alternative)
                for reverse in (False, True):
                    if reverse:
                        value["selection"]["tool_ids"].reverse()
                        value["shortlist"].reverse()
                    with self.subTest(case=case["case_id"], alternative=alternative, reverse=reverse):
                        validate_output(value, case["input"])
                        self.assertTrue(score_case(case, {"status": "ok", "output": value})["passed"])
        # Permuting catalogue and reference alternatives cannot change a metric.
        case = deepcopy(self.cases[4])
        output = proposal(case)
        before = score_case(case, {"status": "ok", "output": output})
        case["input"]["catalogue"].reverse()
        case["reference"]["assertions"][0]["value"].reverse()
        self.assertEqual(score_case(case, {"status": "ok", "output": output}), before)

    def test_best_alternative_is_not_union_recall(self):
        score = self.score(4)
        self.assertTrue(score["passed"])
        self.assertEqual(score["task_metrics"]["shortlist_recall"], 1)
        self.assertEqual(score["task_metrics"]["shortlist_precision"], 1)
        self.assertEqual(score["task_metrics"]["final_minimal"], True)

    def test_sufficient_superset_fails_minimal_selection_and_counts_extras(self):
        output = proposal(self.cases[0])
        output["shortlist"].append("tool.tables.describe_columns")
        output["selection"]["tool_ids"].append("tool.tables.describe_columns")
        validate_output(output, self.cases[0]["input"])
        score = self.score(0, output)
        self.assertFalse(score["passed"])
        self.assertTrue(score["task_metrics"]["final_sufficient"])
        self.assertFalse(score["task_metrics"]["final_minimal"])
        self.assertEqual(score["task_metrics"]["unnecessary_tools"], 1)
        self.assertEqual(score["task_metrics"]["final_precision"], .5)

    def test_incomplete_dependent_set_and_well_typed_wrong_tool_fail(self):
        for index, ids in ((2, ["tool.tables.lookup_series"]), (0, ["tool.tables.sum_values"])):
            output = proposal(self.cases[index])
            output["shortlist"] = ids
            output["selection"]["tool_ids"] = ids
            validate_output(output, self.cases[index]["input"])
            score = self.score(index, output)
            self.assertFalse(score["passed"])
            self.assertFalse(score["task_metrics"]["final_sufficient"])
        self.assertEqual(self.score(2, {"schema_version": OUTPUT_VERSION,
                                       "shortlist": ["tool.tables.lookup_series"],
                                       "selection": {"decision": "select", "reason": "ready",
                                                     "tool_ids": ["tool.tables.lookup_series"]}})
                         ["task_metrics"]["final_recall"], .5)

    def test_malformed_unknown_wrong_level_forbidden_unavailable_and_budget_controls(self):
        base = proposal(self.cases[0])
        outputs = [None, {}, [], "done"]
        for identity in ("unknown.tool", "plugin.tables", "capability.tables.count_rows",
                         "tool.restricted_tables.lookup_series", "tool.geo.shortest_route"):
            value = deepcopy(base)
            value["shortlist"] = [identity]
            value["selection"]["tool_ids"] = [identity]
            outputs.append(value)
        value = deepcopy(base)
        value["shortlist"] *= 2
        outputs.append(value)
        value = deepcopy(base)
        value["selection"]["tool_ids"] *= 2
        outputs.append(value)
        value = deepcopy(base)
        value["shortlist"] = []
        outputs.append(value)
        value = deepcopy(base)
        value["selection"]["tool_ids"] = []
        outputs.append(value)
        value = deepcopy(base)
        value["shortlist"] = [tool["tool_id"] for tool in self.cases[0]["input"]["catalogue"]
                              if tool["eligible"] and tool["available"]][:5]
        outputs.append(value)
        value = deepcopy(base)
        value["answer"] = "success"
        outputs.append(value)
        value = deepcopy(base)
        value["selection"]["decision"] = "success"
        outputs.append(value)
        for output in outputs:
            with self.subTest(output=output):
                score = score_case(self.cases[0], {"status": "ok", "output": output})
                self.assertTrue(score["scored"])
                self.assertFalse(score["passed"])

    def test_semantic_nonselection_is_substantive_and_differs_from_abstention(self):
        for index in (6, 8, 10):
            case = self.cases[index]
            value = proposal(case)
            self.assertEqual(value["shortlist"], [])
            self.assertEqual(value["selection"]["tool_ids"], [])
            result = self.score(index, value)
            self.assertTrue(result["passed"])
            self.assertIsNone(result["task_metrics"]["shortlist_recall"])
            self.assertFalse(score_case(case, {"status": "abstain"})["passed"])
        output = proposal(self.cases[6])
        output["selection"]["reason"] = "unavailable"
        self.assertFalse(self.score(6, output)["passed"])

    def test_reference_namespace_bounds_and_gold_controls_are_validated(self):
        originals = []
        for budget in (0, 9, True, 4.0):
            value = deepcopy(self.cases[0])
            value["input"]["shortlist_limit"] = budget
            originals.append(value)
        value = deepcopy(self.cases[0])
        value["input"]["catalogue"][0]["plugin_id"] = value["input"]["catalogue"][0]["tool_id"]
        originals.append(value)
        value = deepcopy(self.cases[0])
        value["input"]["catalogue"][0]["eligible"] = 1
        originals.append(value)
        value = deepcopy(self.cases[4])
        value["reference"]["assertions"][0]["value"][1]["tool_ids"] = list(reversed(
            value["reference"]["assertions"][0]["value"][0]["tool_ids"]))
        originals.append(value)
        value = deepcopy(self.cases[0])
        value["reference"]["assertions"][0]["value"].append(
            {"decision": "select", "reason": "ready", "tool_ids": ["tool.tables.count_rows", "tool.tables.describe_columns"]})
        originals.append(value)
        value = deepcopy(self.cases[0])
        value["reference"]["assertions"][0]["value"][0]["tool_ids"] = ["tool.restricted_tables.lookup_series"]
        originals.append(value)
        for case in originals:
            with self.subTest(case=case), self.assertRaises(CaseError):
                validate_cases([case])

    def test_candidate_projection_copies_only_allowed_task_input(self):
        case = self.cases[0]
        request = candidate_request(case)
        self.assertEqual(set(request), {"case_id", "contract_id", "input"})
        self.assertEqual(request["input"], case["input"])
        request["input"]["catalogue"][0]["description"] = "Changed copy"
        self.assertNotEqual(request["input"], case["input"])
        for key in ("gold", "reference", "rationale", "annotations"):
            value = deepcopy(case)
            value["input"][key] = "Never candidate-visible"
            with self.subTest(key=key), self.assertRaises(CaseError):
                candidate_request(value)
        research, _ = load_cases(ROOT / "datasets/context-choice-v1/cases.jsonl")
        value = deepcopy(research[0])
        value["evaluation"]["related_contract_ids"] = [CONTRACT]
        with self.assertRaises(CaseError):
            validate_cases([value])

    def test_all_failure_states_and_missing_cases_remain_in_select_denominators(self):
        for status in ("unsupported", "error", "timeout", "missing", "abstain"):
            results = [] if status == "missing" else [{"case_id": c["case_id"], "status": status} for c in self.cases]
            report = summarize(self.cases, results)
            metrics = report["task_metrics"][CONTRACT]
            with self.subTest(status=status):
                self.assertEqual(report["total_cases"], 12)
                self.assertEqual(report["counts_by_status"][status], 12)
                self.assertEqual(metrics["eligible_select_cases"], 6)
                self.assertEqual(metrics["observed_select_cases"], 0)
                self.assertEqual(metrics["shortlist_recall_over_all_eligible"], 0)
                self.assertEqual(metrics["final_minimal_over_all_eligible"], 0)
                self.assertIsNone(metrics["unnecessary_tools_mean_observed"])
                self.assertIn(report["verdict"], {"invalid", "fail"})
        cases = [c for c in self.cases if c["reference"]["assertions"][0]["value"][0]["decision"] != "select"]
        results = [{"case_id": c["case_id"], "status": "ok", "output": proposal(c)} for c in cases]
        report = summarize(cases, results)
        self.assertEqual(report["passed_cases"], 6)
        self.assertIsNone(report["task_metrics"][CONTRACT]["shortlist_recall_over_all_eligible"])

    def test_one_missing_output_reduces_all_eligible_mean_and_mixed_tasks_are_not_pooled(self):
        results = [{"case_id": c["case_id"], "status": "ok", "output": proposal(c)} for c in self.cases[1:]]
        legacy, _ = load_cases(ROOT / "datasets/context-choice-v1/cases.jsonl")
        report = summarize(self.cases + legacy[:1], results)
        metric = report["task_metrics"][CONTRACT]
        self.assertEqual((metric["total_cases"], metric["eligible_select_cases"], metric["observed_select_cases"]), (12, 6, 5))
        self.assertAlmostEqual(metric["shortlist_recall_over_all_eligible"], 5 / 6)
        self.assertEqual(report["counts_by_status"]["missing"], 2)
        self.assertNotIn("task_metrics", summarize(legacy[:1], []))

    def test_real_model_and_application_profiles_refuse_unqualified_output_capability(self):
        for path in (ROOT / "profiles").glob("*.json"):
            value = json.loads(path.read_text())
            if value.get("schema_version") != "deposium.candidate/v1" or value.get("adapter") == "recorded":
                continue
            value["capabilities"] = [CONTRACT]
            with self.subTest(profile=path.name), self.assertRaises(AdapterError):
                parse_profile(json.dumps(value).encode())
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

    def test_shared_campaign_archives_metrics_and_rescores_without_inference(self):
        seen = []
        def factory(*args, **kwargs):
            adapter = create_adapter(*args, **kwargs)
            predict = adapter.predict
            def capture(request):
                self.assertEqual(set(request), {"case_id", "contract_id", "input"})
                seen.append(request)
                return predict(request)
            adapter.predict = capture
            return adapter
        with patch.object(campaigns, "create_adapter", side_effect=factory):
            summary = campaigns.run_campaign(DATASET, PROFILE, self.tmp / "control")
        self.assertEqual(len(seen), 12)
        self.assertEqual(summary["qualification"], "harness_control")
        self.assertEqual(summary["metrics"]["passed_cases"], 12)
        metric = summary["metrics"]["task_metrics"][CONTRACT]
        self.assertEqual((metric["eligible_select_cases"], metric["observed_select_cases"]), (6, 6))
        self.assertAlmostEqual(metric["shortlist_precision_over_all_eligible"], 2 / 3)
        self.assertEqual(metric["final_minimal_over_all_eligible"], 1)
        self.assertEqual({split: group["eligible_select_cases"] for split, group in metric["by_split"].items()},
                         {"train": 2, "calibration": 2, "test": 2})
        self.assertEqual(metric["by_split"]["test"]["final_minimal_over_all_eligible"], 1)
        manifest = json.loads((self.tmp / "control/manifest.json").read_text())
        self.assertEqual(manifest["proof_level"], "harness_control")
        self.assertEqual(manifest["stack_context"]["inventory_status"], "not_observed")
        self.assertFalse(any(item["selected"] for item in summary["stack_coverage"]))
        self.assertEqual(manifest["scorer"]["files"]["tool_discovery.py"], hashlib.sha256((ROOT / "deposium_bench/tool_discovery.py").read_bytes()).hexdigest())
        raw = (self.tmp / "control/raw.jsonl").read_bytes()
        with patch.object(campaigns, "create_adapter", side_effect=AssertionError("no inference")):
            rescored = campaigns.rescore_campaign(self.tmp / "control", self.tmp / "rescore")
        self.assertEqual(rescored["metrics"], summary["metrics"])
        self.assertEqual((self.tmp / "control/raw.jsonl").read_bytes(), raw)
        self.assertEqual((self.tmp / "rescore/raw.jsonl").read_bytes(), raw)
        self.assertIn("Tool discovery (tool-ID level)", (self.tmp / "control/report.md").read_text())

    def test_optional_schema_validates_actual_metrics_and_recorded_only_capability(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is optional; runtime guards are tested separately")
        summary = campaigns.run_campaign(DATASET, PROFILE, self.tmp / "schema-control")
        schema = json.loads((ROOT / "schemas/campaign-summary-v1.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(summary)
        invalid = deepcopy(summary)
        invalid["metrics"]["task_metrics"][CONTRACT]["unknown"] = 1
        self.assertFalse(jsonschema.Draft202012Validator(schema).is_valid(invalid))
        candidate_schema = json.loads((ROOT / "schemas/candidate-v1.schema.json").read_text())
        candidate_validator = jsonschema.Draft202012Validator(candidate_schema)
        candidate_validator.validate(self.profile)
        for adapter in candidate_schema["properties"]["adapter"]["enum"]:
            if adapter == "recorded":
                continue
            candidate = deepcopy(self.profile)
            candidate["adapter"] = adapter
            with self.subTest(adapter=adapter):
                self.assertFalse(candidate_validator.is_valid(candidate))

    def test_optional_campaign_schema_accepts_actual_native_controls_and_rejects_false_provenance(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is optional; runtime guards are tested separately")
        schema = json.loads((ROOT / "schemas/campaign-v1.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        for pack, profile, count in (("tool-discovery-v1", "tool-discovery-control", 12),
                                     ("tool-plan-pilot-v1", "tool-plan-control", 2)):
            destination = self.tmp / profile
            summary = campaigns.run_campaign(ROOT / "datasets" / pack / "cases.jsonl",
                                              ROOT / "profiles" / (profile + ".json"), destination)
            self.assertEqual(summary["metrics"]["scored_cases"], count)
            manifest = json.loads((destination / "manifest.json").read_text())
            with self.subTest(pack=pack):
                validator.validate(manifest)
                for field, value in (("adapter", "mcps"), ("qualification", "model_isolated"),
                                     ("model", {"id": "invented-model"}),
                                     ("recordings_sha256", "invalid"),
                                     ("capabilities", ["bench.unregistered"])):
                    invalid = deepcopy(manifest)
                    invalid["adapter_provenance"][field] = value
                    self.assertFalse(validator.is_valid(invalid), (pack, field))

    def test_cli_complete_control_and_negative_superset_keep_every_case(self):
        result = subprocess.run([sys.executable, "-m", "deposium_bench", "run", "--dataset", str(DATASET),
                                 "--profile", str(PROFILE), "--output", str(self.tmp / "cli"), "--format", "json"],
                                cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["metrics"]["total_cases"], 12)
        recording_path = ROOT / "fixtures/tool-discovery-control.jsonl"
        records = [json.loads(line) for line in recording_path.read_text().splitlines()]
        records[0]["output"]["selection"]["tool_ids"].append("tool.tables.describe_columns")
        # The positive FR shortlist already contains describe_columns.
        (self.tmp / "recordings.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
        profile = deepcopy(self.profile)
        profile["recordings"] = "recordings.jsonl"
        (self.tmp / "profile.json").write_text(json.dumps(profile))
        failed = campaigns.run_campaign(DATASET, self.tmp / "profile.json", self.tmp / "negative")
        self.assertEqual(failed["completion_status"], "complete")
        self.assertEqual(failed["metrics"]["scored_cases"], 12)
        self.assertEqual(failed["metrics"]["passed_cases"], 11)
        metric = failed["metrics"]["task_metrics"][CONTRACT]
        self.assertEqual(metric["final_sufficient_cases"], 6)
        self.assertEqual(metric["final_minimal_cases"], 5)
        self.assertEqual(metric["unnecessary_tools_sum"], 1)


if __name__ == "__main__":
    unittest.main()
