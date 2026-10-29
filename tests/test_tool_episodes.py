"""Executed feedback, bounded fault handling and archive-only episode scoring."""
from copy import deepcopy
from contextlib import ExitStack, redirect_stderr, redirect_stdout
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

from deposium_bench import campaigns, tool_episodes as episodes
from deposium_bench.adapters import AdapterError, _envelope, _identity, create_adapter, load_profile, parse_profile
from deposium_bench.cases import CaseError, candidate_request, load_cases, validate_cases
from deposium_bench.scoring import score_case, summarize
from deposium_bench.synthetic_tools import FixtureStore, ToolError, artifact_id, canonical, validate_fixture

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datasets/tool-episodes-v1/cases.jsonl"
PROFILE = ROOT / "profiles/tool-episodes-control.json"


class Policy:
    def __init__(self, actions, status="missing"):
        self.actions, self.status, self.inputs = deepcopy(actions), status, []

    def predict(self, projected):
        self.inputs.append(deepcopy(projected))
        index = len(self.inputs) - 1
        if index >= len(self.actions):
            return _envelope(self.status, error="control_exhausted")
        return _envelope("ok", output=deepcopy(self.actions[index]))


class EpisodeTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.digest = load_cases(DATASET)
        self.profile, _ = load_profile(PROFILE)
        self.programs = {r["case_id"]: r["output"]["actions"] for r in
                         map(json.loads, (ROOT / "fixtures/tool-episodes-control.jsonl").read_text().splitlines())}
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)

    def case(self, family=1):
        return next(c for c in self.cases if c["case_id"] == f"ep{family:03}-en")

    def actions(self, family=1):
        return deepcopy(self.programs[self.case(family)["case_id"]])

    def execute(self, case=None, actions=None, *, clock=None, status="missing"):
        case = case or self.case()
        policy = Policy(self.programs[case["case_id"]] if actions is None else actions, status)
        state, error, output = episodes.run_episode(case["input"], policy, clock=clock)
        response = _envelope(state, output=output if state == "ok" else None,
                             raw_output=None if state == "ok" else {"episode": output}, error=error)
        episodes.validate_receipt(case["input"], output)
        return response, output, policy

    def test_frozen_public_pack_has_fourteen_train_cases_and_eight_nonusage_assertions(self):
        manifest = json.loads(DATASET.with_name("manifest.json").read_text())
        self.assertEqual(manifest["cases_sha256"], self.digest)
        self.assertEqual(len(self.cases), 14)
        self.assertEqual(len({c["translation_family"] for c in self.cases}), 7)
        self.assertEqual({c["split"] for c in self.cases}, {"train"})
        self.assertEqual({c["language"] for c in self.cases}, {"fr", "en"})
        for case in self.cases:
            self.assertEqual(len(case["reference"]["assertions"]), 8)
            self.assertFalse(any(a["path"].startswith("/usage/") for a in case["reference"]["assertions"]))

    def test_actual_seven_trajectories_pass_procedure_but_only_four_task_results(self):
        adapter = create_adapter(self.profile, PROFILE)
        responses = [{"case_id": c["case_id"], **adapter.predict(candidate_request(c))} for c in self.cases]
        report = summarize(self.cases, responses)
        metrics = report["task_metrics"][episodes.CONTRACT]
        self.assertEqual(report["passed_cases"], 14)
        self.assertEqual(metrics["procedure_correct_cases"], 14)
        self.assertEqual(metrics["task_success_cases"], 4)
        self.assertEqual(metrics["task_success_eligible_cases"], 4)
        self.assertEqual(metrics["policy_steps_observed"], 34)
        self.assertEqual(metrics["tool_calls_observed"], 20)
        self.assertEqual(metrics["tool_status_counts"], {"ok": 14, "controlled_error": 6})
        for row, case in zip(responses, self.cases):
            episodes.validate_receipt(case["input"], row["output"])
            self.assertTrue(score_case(case, row)["passed"])
        partial = next(r["output"] for r in responses if r["case_id"] == "ep005-en")["steps"][0]["observation"]["artifact"]
        self.assertFalse(partial["complete"])
        self.assertEqual(partial["values"], [10])
        partial_task = deepcopy(self.case(5)["input"])
        partial_task["dataset"]["values"] = [10]
        self.assertEqual(partial["artifact_id"], artifact_id(partial_task))

    def test_projection_receives_live_observations_without_source_faults_or_gold(self):
        _, output, policy = self.execute(self.case(2))
        self.assertEqual(len(policy.inputs), 4)
        self.assertEqual(policy.inputs[1]["observations"][0]["status"], "controlled_error")
        self.assertEqual(policy.inputs[2]["observations"][1]["artifact"]["values"], [10, 15, 35])
        for index, projected in enumerate(policy.inputs):
            self.assertEqual(projected, output["steps"][index]["candidate_input"])
            self.assertEqual(hashlib.sha256(canonical(projected)).hexdigest(), output["steps"][index]["candidate_input_sha256"])
            self.assertEqual(projected["observations"], [s["observation"] for s in output["steps"][:index] if s["observation"] is not None])
            encoded = json.dumps(projected)
            for forbidden in ("reference", "assertions", "faults", "lookup_events", "translation_family", "split", "case_id"):
                self.assertNotIn('"' + forbidden + '"', encoded)
        _, _, missing = self.execute(self.case(6))
        self.assertIsNone(missing.inputs[0]["known_parameters"]["dataset_id"])
        self.assertNotIn(self.case(6)["input"]["dataset"]["dataset_id"], json.dumps(missing.inputs[0]))
        initial = policy.inputs[0]["tools"]
        self.assertTrue(initial[1]["available"])
        self.assertFalse(initial[1]["eligible"])
        _, _, unavailable = self.execute(self.case(7))
        self.assertTrue(unavailable.inputs[0]["tools"][1]["available"])
        self.assertFalse(unavailable.inputs[1]["tools"][1]["available"])

    def test_correct_terminal_outcome_before_evidence_fails_all_nonmissing_scenarios(self):
        for family in (1, 2, 3, 4, 5, 7):
            with self.subTest(family=family):
                action = self.actions(family)[-1]
                response, output, _ = self.execute(self.case(family), [action])
                self.assertFalse(output["checks"]["stopping_valid"])
                self.assertFalse(output["checks"]["procedure_valid"])
                self.assertFalse(score_case(self.case(family), response)["passed"])
                self.assertEqual(output["usage"]["tool_calls_executed"], 0)
        response, output, _ = self.execute(self.case(6))
        self.assertTrue(score_case(self.case(6), response)["passed"])
        self.assertEqual(output["usage"]["tool_calls_executed"], 0)
        self.assertEqual(output["usage"]["policy_steps"], 1)

    def test_legal_additional_lookup_is_accepted_without_matching_control_counts(self):
        actions = self.actions()
        actions.insert(1, deepcopy(actions[0]))
        response, output, _ = self.execute(actions=actions)
        self.assertTrue(score_case(self.case(), response)["passed"])
        self.assertEqual(output["usage"], {"policy_steps": 4, "tool_call_attempts": 3, "tool_calls_executed": 3, "lookup_attempts": 2})

    def test_wrong_arguments_stale_bindings_and_fake_execution_fields_are_guarded(self):
        mutations = {
            "unit": lambda p: p["arguments"].update(unit="USD"),
            "scope": lambda p: p["arguments"].update(scope_id="foreign"),
            "column": lambda p: p["arguments"].update(column="another-column"),
            "stale": lambda p: p["arguments"].update(artifact_id="artifact:" + "0" * 64),
            "type": lambda p: p["arguments"].update(column=True),
            "missing": lambda p: p["arguments"].pop("column"),
            "fake_execution": lambda p: p.update(observation={"status": "ok", "value": 60}),
            "unknown": lambda p: p.update(tool_id="external.run"),
        }
        for label, mutate in mutations.items():
            actions = self.actions()
            mutate(actions[1])
            with self.subTest(label=label), patch.object(episodes.EpisodeRuntime, "sum", side_effect=AssertionError("guard must precede sum")):
                response, output, _ = self.execute(actions=actions)
            self.assertFalse(score_case(self.case(), response)["passed"])
            self.assertEqual(output["usage"]["tool_calls_executed"], 1)
            self.assertFalse(output["steps"][1]["guard"]["allowed"])

    def test_sum_requires_a_full_nonempty_available_actual_artifact(self):
        normal_sum = self.actions()[1]
        for family in (1, 4, 5, 7):
            actions = [normal_sum, self.actions(family)[-1]] if family == 1 else [self.actions(family)[0], normal_sum, self.actions(family)[-1]]
            with self.subTest(family=family), patch.object(episodes.EpisodeRuntime, "sum", side_effect=AssertionError("ineligible sum")):
                _, output, _ = self.execute(self.case(family), actions)
            self.assertFalse(output["checks"]["procedure_valid"])
            self.assertFalse(output["checks"]["task_success"])
        runtime = episodes.EpisodeRuntime(self.case(5)["input"])
        receipt = runtime.lookup(self.actions(5)[0]["arguments"])
        args = {**normal_sum["arguments"], "artifact_id": receipt["artifact"]["artifact_id"], "scope_id": self.case(5)["input"]["scope_id"]}
        with self.assertRaises(ToolError):
            runtime.sum(args)
        self.assertEqual(runtime.store.calls, 1)

    def test_invalid_action_cannot_be_erased_by_later_valid_success(self):
        actions = [None, *self.actions()]
        response, output, _ = self.execute(actions=actions)
        self.assertTrue(output["checks"]["stopping_valid"])
        self.assertFalse(output["checks"]["procedure_valid"])
        self.assertFalse(output["checks"]["task_success"])
        self.assertFalse(score_case(self.case(), response)["passed"])
        for value in (61, True, "60", None):
            actions = self.actions()
            actions[-1]["value"] = value
            response, output, _ = self.execute(actions=actions)
            self.assertFalse(output["checks"]["stopping_valid"])
            self.assertFalse(score_case(self.case(), response)["passed"])

    def test_changed_fault_schedule_with_same_policy_cannot_replay_fake_observations(self):
        case = deepcopy(self.case())
        case["input"]["faults"]["lookup_events"] = ["transient_error"]
        with patch.object(episodes.EpisodeRuntime, "sum", side_effect=AssertionError("missing real artifact")):
            _, output, _ = self.execute(case, self.actions())
        self.assertFalse(output["checks"]["procedure_valid"])
        self.assertEqual(output["steps"][0]["observation"]["status"], "controlled_error")
        case = deepcopy(self.case())
        case["input"]["dataset"]["values"][0] += 1
        with patch.object(episodes.EpisodeRuntime, "sum", side_effect=AssertionError("stale literal ID")):
            _, output, _ = self.execute(case, self.actions())
        self.assertFalse(output["checks"]["binding_valid"])

    def test_step_call_and_lookup_budgets_are_independent_and_precede_dispatch(self):
        actions = self.actions()
        programs = {
            "fourth_call": [actions[0], actions[0], actions[1], actions[1], actions[2]],
            "third_lookup": [actions[0], actions[0], actions[0], actions[2]],
            "sixth_step": [None] * 6,
        }
        for name, program in programs.items():
            response, output, policy = self.execute(actions=program)
            with self.subTest(name=name):
                self.assertFalse(output["checks"]["budgets_respected"])
                self.assertFalse(score_case(self.case(), response)["passed"])
                self.assertLessEqual(output["usage"]["tool_calls_executed"], 3)
                self.assertLessEqual(len(policy.inputs), 5)
        _, output, _ = self.execute(actions=programs["fourth_call"])
        self.assertEqual(output["usage"]["tool_calls_executed"], 3)
        self.assertEqual(output["usage"]["tool_call_attempts"], 4)
        _, output, _ = self.execute(actions=programs["third_lookup"])
        self.assertEqual(output["usage"]["tool_calls_executed"], 2)
        self.assertEqual(output["usage"]["lookup_attempts"], 3)

    def test_elapsed_budget_checks_before_policy_dispatch_and_after_actual_call(self):
        for times, actual in (([0, 1.001], 0), ([0, 0, 1.001, 1.001], 0), ([0, 0, 0, 1.001], 1)):
            with self.subTest(times=times):
                response, output, _ = self.execute(clock=iter(times).__next__)
                self.assertEqual(output["termination"], "time_limit")
                self.assertEqual(output["usage"]["tool_calls_executed"], actual)
                self.assertFalse(output["checks"]["budgets_respected"])
                self.assertFalse(score_case(self.case(), response)["passed"])
        with self.assertRaisesRegex(CaseError, "nonmonotonic"):
            self.execute(clock=iter([0, 0, -1]).__next__)

    def test_malformed_calls_cannot_bypass_attempt_or_lookup_budgets(self):
        case = self.case(6)
        finish = self.actions(6)[0]
        variants = {
            "unknown_tool": ({"action": "call", "tool_id": "unknown.tool", "arguments": {}}, 4, 0),
            "extra_fields": ({"action": "call", "tool_id": "fixture.sum", "arguments": {}, "extra": True}, 4, 0),
            "oversized_call": ({"action": "call", "tool_id": "fixture.sum", "arguments": {"extra": "x" * 8192}}, 4, 0),
            "malformed_lookup": ({"action": "call", "tool_id": "fixture.lookup", "arguments": None, "extra": True}, 3, 3),
        }
        for label, (call, attempts, lookups) in variants.items():
            with self.subTest(label=label), patch.object(episodes.EpisodeRuntime, "lookup", side_effect=AssertionError("invalid call executed")), \
                    patch.object(episodes.EpisodeRuntime, "sum", side_effect=AssertionError("invalid call executed")):
                response, output, _ = self.execute(case, [deepcopy(call) for _ in range(attempts)] + [finish])
            self.assertTrue(output["checks"]["stopping_valid"])
            self.assertFalse(output["checks"]["procedure_valid"])
            self.assertFalse(output["checks"]["budgets_respected"])
            self.assertEqual(output["steps"][attempts - 1]["guard"]["code"], "call_or_retry_limit")
            self.assertEqual(output["usage"]["tool_call_attempts"], attempts)
            self.assertEqual(output["usage"]["lookup_attempts"], lookups)
            self.assertEqual(output["usage"]["tool_calls_executed"], 0)
            with patch.object(episodes.EpisodeRuntime, "__init__", side_effect=AssertionError("pure receipt validation")), \
                    patch.object(episodes.ReplayPolicy, "predict", side_effect=AssertionError("pure policy validation")):
                episodes.validate_receipt(case["input"], output)
                metric = summarize([case], [{"case_id": case["case_id"], **response}])["task_metrics"][episodes.CONTRACT]
                self.assertEqual(metric["budget_eligible_cases"], 1)
                self.assertEqual(metric["budget_correct_cases"], 0)
                self.assertEqual(metric["budget_over_all_eligible"], 0)
                self.assertEqual(metric["cases_with_execution_trace"], 1)
                self.assertFalse(score_case(case, response)["passed"])
                forged = deepcopy(output)
                forged["checks"]["budgets_respected"] = True
                with self.assertRaises(CaseError):
                    episodes.validate_receipt(case["input"], forged)

    def test_nonok_policy_statuses_retain_observed_execution_and_zero_stage_credit(self):
        for status in ("missing", "unsupported", "error", "timeout", "abstain"):
            with self.subTest(status=status):
                response, output, _ = self.execute(actions=self.actions()[:1], status=status)
                self.assertEqual(response["status"], status)
                self.assertIsNone(response["output"])
                self.assertEqual(output["usage"]["tool_calls_executed"], 1)
                report = summarize([self.case()], [{"case_id": self.case()["case_id"], **response}])
                metric = report["task_metrics"][episodes.CONTRACT]
                self.assertEqual(metric["tool_calls_observed"], 1)
                self.assertEqual(metric["cases_with_execution_trace"], 1)
                self.assertEqual(metric["result_correct_cases"], 0)
                self.assertEqual(metric["execution_correct_cases"], 0)
                self.assertNotEqual(report["verdict"], "pass")

    def test_source_eligibility_and_unobserved_denominators_do_not_depend_on_outputs(self):
        metrics = summarize(self.cases, [])["task_metrics"][episodes.CONTRACT]
        self.assertEqual(metrics["cases_without_execution_trace"], 14)
        self.assertEqual(metrics["tool_calls_observed"], 0)
        for stage, n in (("tool", 12), ("arguments", 12), ("execution", 12), ("binding", 4), ("result", 4), ("stopping", 14), ("budget", 14)):
            self.assertEqual(metrics[stage + "_eligible_cases"], n)
            self.assertEqual(metrics[stage + "_over_all_eligible"], 0)
        missing = summarize([self.case(6)], [])["task_metrics"][episodes.CONTRACT]
        for stage in ("tool", "arguments", "execution", "binding", "result"):
            self.assertIsNone(missing[stage + "_over_all_eligible"])

    def test_receipt_projection_observations_counters_flags_and_timing_cannot_be_forged(self):
        response, _, _ = self.execute()
        mutations = (
            lambda o: o["steps"][1].update(candidate_input_sha256="0" * 64),
            lambda o: o["steps"][1]["candidate_input"]["observations"][0]["artifact"].update(values=[999]),
            lambda o: o["steps"][0]["observation"]["artifact"].update(values=[999]),
            lambda o: o["steps"][1]["observation"].update(value=999),
            lambda o: o["usage"].update(tool_calls_executed=0),
            lambda o: o["checks"].update(procedure_valid=False),
            lambda o: o["steps"][0]["guard"].update(allowed=False),
            lambda o: o["steps"][0].update(elapsed_after_policy_ms=-1),
            lambda o: o.update(elapsed_ms=float("inf")),
        )
        for mutate in mutations:
            changed = deepcopy(response)
            mutate(changed["output"])
            with self.subTest(mutate=mutate), patch.object(episodes.EpisodeRuntime, "__init__", side_effect=AssertionError("pure scoring")):
                self.assertFalse(score_case(self.case(), changed)["passed"])

    def test_source_validation_preserves_old_empty_default_and_rejects_inconsistent_bounds(self):
        empty = self.case(4)["input"]
        episodes.validate_input(empty)
        with self.assertRaises(ToolError):
            validate_fixture(empty["scope_id"], empty["dataset"])
        with self.assertRaises(ToolError):
            FixtureStore(empty)
        for values in ([True], [1.5], [0] * 33, [10**9 + 1]):
            case = deepcopy(self.case())
            case["input"]["dataset"]["values"] = values
            with self.subTest(values=values), self.assertRaises(CaseError):
                episodes.validate_input(case["input"])
        for mutate in (lambda t: t["faults"].update(lookup_events=["partial"]),
                       lambda t: t["budgets"].update(max_steps=6),
                       lambda t: t["budgets"].update(max_tool_calls=4),
                       lambda t: t["budgets"].update(max_lookup_attempts=3),
                       lambda t: t["budgets"].update(max_elapsed_ms=1001)):
            task = deepcopy(empty)
            mutate(task)
            with self.assertRaises(CaseError):
                episodes.validate_input(task)
        for mutate in (lambda c: c["reference"]["assertions"].pop(),
                       lambda c: c["reference"]["assertions"][0].update(value=False)):
            case = deepcopy(self.case())
            mutate(case)
            with self.assertRaises(CaseError):
                validate_cases([case])

    def test_only_dedicated_control_adapter_can_claim_executed_episode_capability(self):
        for name in ("recorded", "fixture_arguments", "systemone_local", "mcps", "gliclass"):
            profile = deepcopy(self.profile)
            profile["adapter"] = name
            with self.subTest(adapter=name), self.assertRaises(AdapterError):
                parse_profile(json.dumps(profile).encode())
        for changes in ({"qualification": "model_isolated"}, {"model": {"repo_id": "fake"}}, {"timeout_seconds": 0.5}, {"capabilities": ["bench.tool-arguments"]}):
            profile = {**deepcopy(self.profile), **changes}
            with self.subTest(changes=changes), self.assertRaises(AdapterError):
                parse_profile(json.dumps(profile).encode())
        adapter = create_adapter(self.profile, PROFILE)
        request = candidate_request(self.case())
        request["contract_id"] = "bench.tool-arguments"
        self.assertEqual(adapter.predict(request)["status"], "unsupported")

    def test_malformed_scripted_programs_do_not_become_execution_receipts(self):
        for program in (None, {}, {"actions": None}, {"actions": [], "observations": []}, {"actions": [None] * 17}):
            class Transport:
                def predict(self, request):
                    return _envelope("ok", output=program)
            status, _, output = episodes.run_episode(self.case()["input"], episodes.ReplayPolicy(Transport(), "opaque"))
            self.assertEqual(status, "error")
            self.assertEqual(output["usage"]["tool_calls_executed"], 0)
            episodes.validate_receipt(self.case()["input"], output)

    def test_actual_runtime_and_policy_modules_are_in_adapter_and_scorer_fingerprints(self):
        adapter = create_adapter(self.profile, PROFILE)
        names = ("adapters.py", "synthetic_tools.py", "tool_arguments.py", "tool_episodes.py")
        hashes = {n: hashlib.sha256((ROOT / "deposium_bench" / n).read_bytes()).hexdigest() for n in names}
        self.assertEqual(adapter.provenance["adapter_sha256"], _identity(hashes))
        for name in names:
            (self.tmp / name).write_bytes((ROOT / "deposium_bench" / name).read_bytes())
        (self.tmp / "synthetic_tools.py").write_text("changed actual tool source bytes\n")
        with patch.object(episodes, "__file__", str(self.tmp / "tool_episodes.py")):
            changed = create_adapter(self.profile, PROFILE)
        self.assertNotEqual(changed.provenance["identity_sha256"], adapter.provenance["identity_sha256"])

    def test_shared_archive_rescore_never_invokes_tools_policy_or_clock_or_changes_original(self):
        run = self.tmp / "run"
        summary = campaigns.run_campaign(DATASET, PROFILE, run)
        original = {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}
        manifest = json.loads(original["manifest.json"])
        self.assertEqual(manifest["input_protocol"], "fixture_episode_control")
        self.assertIn("tool_episodes.py", manifest["scorer"]["files"])
        with ExitStack() as stack:
            for owner, name in ((episodes, "run_episode"), (episodes.EpisodeRuntime, "__init__"), (episodes.EpisodeRuntime, "lookup"),
                                (episodes.EpisodeRuntime, "sum"), (episodes.ReplayPolicy, "predict"),
                                (FixtureStore, "lookup"), (FixtureStore, "sum"), (episodes.time, "monotonic")):
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError("rescore executed " + name)))
            rescored = campaigns.rescore_campaign(run, self.tmp / "rescore")
        self.assertEqual(rescored["metrics"], summary["metrics"])
        self.assertEqual({p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}, original)
        (run / "recordings.jsonl").write_text("tampered\n")
        with self.assertRaises(campaigns.CampaignError):
            campaigns.rescore_campaign(run, self.tmp / "tampered")

    def test_time_limit_and_nonok_archives_rescore_without_reexecution(self):
        original = episodes.run_episode
        def deadline(task, policy):
            return original(task, policy, clock=iter([0, 0, 0, 1.001]).__next__)
        with patch.object(episodes, "run_episode", side_effect=deadline):
            first = campaigns.run_campaign(DATASET, PROFILE, self.tmp / "deadline")
        self.assertEqual(first["metrics"]["passed_cases"], 0)
        with patch.object(episodes, "run_episode", side_effect=AssertionError("rescore loop")), \
                patch.object(episodes.EpisodeRuntime, "lookup", side_effect=AssertionError("rescore lookup")):
            second = campaigns.rescore_campaign(self.tmp / "deadline", self.tmp / "deadline-rescore")
        self.assertEqual(first["metrics"], second["metrics"])
        rows = [{"case_id": c["case_id"], "status": "missing", "output": None, "raw_output": None, "error": "fixture_unavailable"} for c in self.cases]
        recording = self.tmp / "missing.jsonl"
        recording.write_text("".join(json.dumps(row) + "\n" for row in rows))
        profile = {**self.profile, "recordings": recording.name}
        path = self.tmp / "missing-profile.json"
        path.write_text(json.dumps(profile))
        first = campaigns.run_campaign(DATASET, path, self.tmp / "missing")
        with patch.object(episodes, "run_episode", side_effect=AssertionError("rescore missing policy")):
            second = campaigns.rescore_campaign(self.tmp / "missing", self.tmp / "missing-rescore")
        self.assertEqual(first["metrics"], second["metrics"])

    def test_actual_candidate_manifest_summary_and_raw_schemas_reject_provenance_spoofs(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is optional")
        run = self.tmp / "schema-run"
        summary = campaigns.run_campaign(DATASET, PROFILE, run)
        manifest = json.loads((run / "manifest.json").read_text())
        for name, artifact in (("candidate", self.profile), ("campaign", manifest), ("campaign-summary", summary)):
            schema = json.loads((ROOT / "schemas" / (name + "-v1.schema.json")).read_text())
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.validate(artifact, schema)
        schema = json.loads((ROOT / "schemas/result-v1.schema.json").read_text())
        for line in (run / "raw.jsonl").read_text().splitlines():
            jsonschema.validate(json.loads(line), schema)
        schema = json.loads((ROOT / "schemas/candidate-v1.schema.json").read_text())
        for changes in ({"adapter": "recorded"}, {"qualification": "model_isolated"}, {"timeout_seconds": 0.5}, {"capabilities": ["bench.tool-arguments"]}):
            with self.subTest(changes=changes), self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate({**deepcopy(self.profile), **changes}, schema)
        schema = json.loads((ROOT / "schemas/campaign-v1.schema.json").read_text())
        for adapter in ("recorded", "fixture_arguments", "mcps"):
            spoof = deepcopy(manifest)
            spoof["adapter_provenance"]["adapter"] = adapter
            with self.subTest(adapter=adapter), self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(spoof, schema)
        spoof = deepcopy(manifest)
        spoof["input_protocol"] = "recorded_control"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(spoof, schema)

    def test_import_and_prediction_require_no_network_external_process_or_import_side_effects(self):
        spec = importlib.util.spec_from_file_location("deposium_bench._episode_import_control", ROOT / "deposium_bench/tool_episodes.py")
        module = importlib.util.module_from_spec(spec)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("deposium_bench.adapters.RecordedAdapter", side_effect=AssertionError("import transport")), \
                patch.object(FixtureStore, "lookup", side_effect=AssertionError("import lookup")), \
                patch.object(FixtureStore, "sum", side_effect=AssertionError("import sum")), \
                patch("socket.create_connection", side_effect=AssertionError("import network")), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            spec.loader.exec_module(module)
        self.assertEqual(stdout.getvalue() + stderr.getvalue(), "")
        with patch("socket.create_connection", side_effect=AssertionError("network")), \
                patch("subprocess.Popen", side_effect=AssertionError("external process")):
            adapter = create_adapter(self.profile, PROFILE)
            self.assertTrue(all(score_case(c, adapter.predict(candidate_request(c)))["passed"] for c in self.cases))

    def test_real_shared_cli_reports_procedure_and_task_success_separately(self):
        command = [sys.executable, "-B", "-m", "deposium_bench", "run", "--dataset", str(DATASET),
                   "--profile", str(PROFILE), "--output", str(self.tmp / "cli"), "--format", "json"]
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["metrics"]["passed_cases"], 14)
        self.assertEqual(report["metrics"]["task_metrics"][episodes.CONTRACT]["task_success_cases"], 4)
        text = (self.tmp / "cli/report.md").read_text()
        self.assertIn("Procedure correctness: 14 / 14", text)
        self.assertIn("task success: 4 / 14 overall", text)


if __name__ == "__main__":
    unittest.main()
