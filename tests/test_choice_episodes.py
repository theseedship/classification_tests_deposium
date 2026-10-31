import hashlib
import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from deposium_bench import choice_episodes as choice, tool_episodes as episodes  # noqa: E402
from deposium_bench.adapters import AdapterError, _envelope, create_adapter, parse_profile  # noqa: E402
from deposium_bench.campaigns import rescore_campaign, run_campaign  # noqa: E402
from deposium_bench.cases import CaseError, candidate_request, load_cases  # noqa: E402

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

DATASET = ROOT / "datasets/tool-episodes-choice-v1/cases.jsonl"
MANIFEST = ROOT / "datasets/tool-episodes-choice-v1/manifest.json"


class RuleInner:
    """Test-only chooser reading the rendered text; stands in for a classifier."""
    provenance = {"identity_sha256": "rule-inner", "available": True}

    def __init__(self):
        self.requests = []

    def predict(self, request):
        self.requests.append(deepcopy(request))
        value = request["input"]
        ids = [o["id"] for o in value["options"]]
        text = value["context"]
        if "finish-success" in ids:
            pick = "finish-success"
        elif "call-sum" in ids:
            last = [line for line in text.splitlines() if "fixture.lookup → ok" in line][-1]
            if "complet / complete = non" in last:
                pick = "finish-partial_data"
            elif " 0 valeurs" in last:
                pick = "finish-no_data"
            elif "available afterwards = non" in last:
                pick = "finish-unavailable"
            else:
                pick = "call-sum"
        elif "call-lookup" in ids:
            pick = "finish-persistent_error" if "consultations / lookups = 0" in text and "erreur contrôlée" in text else "call-lookup"
        else:
            pick = "finish-missing_information"
        return _envelope("ok", output={"choice_id": pick}, raw_output={"forward_executed": True})


class FirstInner:
    provenance = {"identity_sha256": "first-inner", "available": True}

    def predict(self, request):
        return _envelope("ok", output={"choice_id": request["input"]["options"][0]["id"]})


class FailingInner:
    provenance = {"identity_sha256": "failing-inner", "available": True}

    def predict(self, request):
        return _envelope("timeout", error="d3_inference_timeout")


class ChoiceEpisodeTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.digest = load_cases(DATASET)
        self.manifest = json.loads(MANIFEST.read_text())
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)

    def profile(self, inner_name="inner.json", **changes):
        base = {"schema_version": "deposium.candidate/v1", "profile_id": "choice-episodes-test", "adapter": "choice_episode",
                "qualification": "harness_control", "capabilities": ["bench.tool-episode"],
                "model": {"inner_profile": inner_name}, "timeout_seconds": 15, "revision": None, "recordings": None}
        return {**base, **changes}

    def inner_files(self, choice_id="finish-missing_information"):
        recordings = "".join(json.dumps({"case_id": c["case_id"], "status": "ok", "output": {"choice_id": choice_id},
                                         "raw_output": None, "error": None}) + "\n" for c in self.cases)
        (self.tmp / "inner.jsonl").write_text(recordings)
        inner = {"schema_version": "deposium.candidate/v1", "profile_id": "recorded-choice", "adapter": "recorded",
                 "qualification": "harness_control", "capabilities": ["bench.context-choice"], "model": None,
                 "timeout_seconds": 5, "revision": None, "recordings": "inner.jsonl"}
        (self.tmp / "inner.json").write_text(json.dumps(inner))
        (self.tmp / "profile.json").write_text(json.dumps(self.profile()))
        return self.tmp / "profile.json"

    def test_frozen_pack_matches_its_manifest_and_sources(self):
        self.assertEqual(self.manifest["cases_sha256"], self.digest)
        self.assertEqual((self.manifest["case_count"], len(self.cases)), (32, 32))
        self.assertEqual(self.manifest["counts_by_split"], {"train": 20, "calibration": 0, "test": 12})
        self.assertEqual(self.manifest["counts_by_language"], {"en": 16, "fr": 16})
        self.assertTrue(all(c["input"]["schema_version"] == episodes.INPUT_VERSION_V3
                            and c["input"]["budgets"]["max_elapsed_ms"] == 600000 for c in self.cases))
        for source in self.manifest["sources"]:
            _, digest = load_cases(ROOT / "datasets" / source["dataset_id"] / "cases.jsonl")
            self.assertEqual(digest, source["cases_sha256"])
        ids = {c["case_id"] for c in self.cases}
        self.assertEqual(ids, {i for s in self.manifest["sources"] for i in s["episode_case_ids"]})

    def test_menu_is_derived_from_the_projection_only_and_never_offers_success_before_a_sum_receipt(self):
        case = next(c for c in self.cases if c["case_id"] == "ep001-en")
        state = episodes._State(case["input"])
        first = state.projection(0.0, 0)
        items = choice.menu(first)
        self.assertEqual([i["id"] for i in items], ["call-lookup"] + ["finish-" + r for _, r in choice.FINISHES])
        value = choice.render(first, items)
        # The hidden fault schedule, the table values and the reference never reach the text.
        for hidden in ("lookup_events", "disable_sum_after_lookup", "\"values\"", "[10, 15, 35]", "60 EUR", "success/complete"):
            self.assertNotIn(hidden, value["context"])
        missing = next(c for c in self.cases if c["input"]["known_dataset_id"] is None)
        ids = [i["id"] for i in choice.menu(episodes._State(missing["input"]).projection(0.0, 0))]
        self.assertNotIn("call-lookup", ids)
        self.assertNotIn("call-sum", ids)

    def test_rule_inner_passes_every_case_and_reports_task_success_only_where_eligible(self):
        inner = RuleInner()
        passed = success = eligible = 0
        for case in self.cases:
            policy = choice.ChoiceStepPolicy(inner, case["case_id"])
            status, error, output = episodes.run_episode(case["input"], policy)
            self.assertEqual((status, error), ("ok", None), case["case_id"])
            episodes.validate_receipt(case["input"], output)
            expected = episodes.expected_outcome(case["input"])
            self.assertEqual(output["outcome"], expected, case["case_id"])
            passed += output["checks"]["procedure_valid"] and output["checks"]["stopping_valid"]
            success += output["checks"]["task_success"]
            eligible += expected["decision"] == "success"
            result = _envelope("ok", output=output, raw_output={"schema_version": choice.TRACE_VERSION,
                               "inner_identity_sha256": "rule-inner", "steps": policy.steps, "episode": None})
            choice.validate_trace(case, result)
        self.assertEqual((passed, success, eligible), (32, 12, 12))
        self.assertTrue(all(r["contract_id"] == "bench.context-choice" and set(r["input"]) == {"context", "question", "options"}
                            for r in inner.requests))

    def test_position_bias_and_failures_are_recorded_not_hidden(self):
        case = next(c for c in self.cases if c["case_id"] == "ep003-en")
        policy = choice.ChoiceStepPolicy(FirstInner(), case["case_id"])
        status, _, output = episodes.run_episode(case["input"], policy)
        self.assertEqual(status, "ok")
        self.assertFalse(output["checks"]["procedure_valid"])
        self.assertEqual(len(policy.steps), len(output["steps"]))
        policy = choice.ChoiceStepPolicy(FailingInner(), case["case_id"])
        status, error, output = episodes.run_episode(case["input"], policy)
        self.assertEqual((status, error, output["termination"]), ("timeout", "d3_inference_timeout", "candidate_timeout"))
        result = _envelope("timeout", raw_output={"schema_version": choice.TRACE_VERSION, "inner_identity_sha256": "x",
                                                   "steps": policy.steps, "episode": output}, error=error)
        choice.validate_trace(case, result)

    def test_tampered_traces_are_rejected(self):
        case = next(c for c in self.cases if c["case_id"] == "ep001-en")
        policy = choice.ChoiceStepPolicy(RuleInner(), case["case_id"])
        _, _, output = episodes.run_episode(case["input"], policy)
        good = _envelope("ok", output=output, raw_output={"schema_version": choice.TRACE_VERSION,
                         "inner_identity_sha256": "rule-inner", "steps": policy.steps, "episode": None})
        choice.validate_trace(case, good)
        for mutate in (lambda r: r["raw_output"]["steps"][0]["menu"].pop(),
                       lambda r: r["raw_output"]["steps"][0]["choice_input"]["context"].__setitem__ if False else r["raw_output"]["steps"][0].update(choice_input_sha256="0" * 64),
                       lambda r: r["raw_output"]["steps"][0]["response"].update(output={"choice_id": "finish-no_data"}),
                       lambda r: r["raw_output"]["steps"].pop(),
                       lambda r: r["output"]["steps"][0].update(proposal={"action": "finish", "decision": "stop", "reason": "no_data", "value": None, "unit": None})):
            bad = deepcopy(good)
            mutate(bad)
            with self.assertRaises(CaseError):
                choice.validate_trace(case, bad)

    def test_profile_validation_and_schema(self):
        self.inner_files()
        parse_profile(json.dumps(self.profile()).encode())
        for changes in ({"capabilities": ["bench.context-choice"]}, {"recordings": "x.jsonl"}, {"model": None},
                        {"model": {"inner_profile": ""}}, {"qualification": "model_isolated"},
                        {"revision": "a" * 40}, {"timeout_seconds": 0.5}):
            with self.subTest(changes=changes), self.assertRaises(AdapterError):
                parse_profile(json.dumps(self.profile(**changes)).encode())
        with self.assertRaises(AdapterError):
            create_adapter(self.profile(timeout_seconds=1), self.tmp / "profile.json")
        if jsonschema is None:
            self.skipTest("jsonschema not installed")
        schema = json.loads((ROOT / "schemas/candidate-v1.schema.json").read_text())
        jsonschema.validate(self.profile(), schema)
        jsonschema.validate(self.profile(qualification="model_isolated", revision="b" * 40), schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(self.profile(qualification="model_isolated"), schema)

    def test_campaign_archive_rescore_and_trace_metrics_with_a_recorded_inner(self):
        profile_path = self.inner_files()
        selected = [c for c in self.cases if c["case_id"] in {"ep001-en", "ep006-en"}]
        dataset = self.tmp / "two.jsonl"
        dataset.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in selected))
        output = self.tmp / "archive"
        summary = run_campaign(dataset, profile_path, output)
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual(manifest["input_protocol"], "closed_choice_episode_v1")
        self.assertEqual(manifest["adapter_provenance"]["policy_mode"], "closed_choice_step_menu_v1")
        self.assertEqual(manifest["adapter_provenance"]["inner"]["adapter"], "recorded")
        records = [json.loads(line) for line in (output / "raw.jsonl").read_text().splitlines()]
        self.assertEqual([r["status"] for r in records], ["ok", "ok"])
        self.assertEqual([r["raw_output"]["schema_version"] for r in records], [choice.TRACE_VERSION] * 2)
        metrics = summary["metrics"]["task_metrics"]["bench.tool-episode"]
        # ep006 asks for clarification (missing identifier): the fixed recorded answer is right there, wrong for ep001.
        self.assertEqual((metrics["procedure_correct_cases"], metrics["cases_with_execution_trace"], metrics["eligible_cases"]), (1, 2, 2))
        rescored = rescore_campaign(output, self.tmp / "rescored")
        self.assertEqual(rescored["metrics"]["task_metrics"]["bench.tool-episode"]["procedure_correct_cases"], 1)

    def test_adapter_refuses_mismatched_inner_and_unsupported_contract(self):
        profile_path = self.inner_files()
        adapter = create_adapter(self.profile(), profile_path)
        request = candidate_request(self.cases[0])
        request["contract_id"] = "bench.tool-arguments"
        self.assertEqual(adapter.predict(request)["status"], "unsupported")
        with self.assertRaises(AdapterError):
            create_adapter(self.profile(qualification="model_isolated", revision="c" * 40), profile_path)


if __name__ == "__main__":
    unittest.main()
