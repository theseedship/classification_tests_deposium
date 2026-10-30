"""Controlled native JSON generation through real fixture guards; no model runs."""
import base64
from contextlib import contextmanager, ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
from http.client import IncompleteRead
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from deposium_bench import campaigns, local_tool_policy as local, native_supervision as supervision
from deposium_bench import tool_arguments, tool_episodes
from deposium_bench.adapters import create_adapter, parse_profile
from deposium_bench.cases import CaseError, candidate_request, load_cases, validate_cases
from deposium_bench.scoring import score_case, summarize
from deposium_bench.synthetic_tools import FixtureStore, artifact_id, canonical

ROOT = Path(__file__).resolve().parents[1]


class LocalToolPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)
        self.key = "unit-test-ephemeral-local-key"
        self.settings = {"model_id": "synthetic-json-policy", "max_length": 4096, "max_output_tokens": 256,
                         "seed": 7, "prompt_version": local.PROMPT_VERSION}
        self.files = {}
        for name in ("model.gguf", "llama-server", "harness.py", "runtime.json", "template.jinja"):
            path = self.tmp / name
            path.write_text("synthetic inert unit fixture for " + name)
            self.files[name] = path
        record = lambda name: {"path": str(self.files[name]), "sha256": local.digest(self.files[name])}
        self.session = {"schema_version": local.SESSION_VERSION,
            "endpoint": "http://127.0.0.1:11438/v1/chat/completions",
            "model": {"repo_id": "synthetic/model", "revision": "a" * 40, "path": str(self.files["model.gguf"]),
                "sha256": local.digest(self.files["model.gguf"]), "alias": self.settings["model_id"],
                "size": self.files["model.gguf"].stat().st_size, "quantization": "Q8_0"},
            "runtime": {"repository": "https://github.com/ggml-org/llama.cpp.git", "revision": local.PIN,
                "binary": str(self.files["llama-server"]), "sha256": local.digest(self.files["llama-server"]), "backend_requested": "metal"},
            "harness": record("harness.py"), "runtime_pin": record("runtime.json"), "template": record("template.jinja"),
            "settings": {**self.settings, "parallel": 1, "concurrency": 1, "truncation": "reject_in_pinned_native_engine"},
            "max_rss_mb": 1024, "pid": 424242,
            "supervisor": {"pid": os.getpid(), **record("harness.py")}}
        self.session_path = self.tmp / "session.json"
        self.session_path.write_bytes(canonical(self.session))
        self.profile = {"schema_version": "deposium.candidate/v1", "profile_id": "synthetic-local-json",
            "adapter": local.ADAPTER, "qualification": "model_isolated", "capabilities": list(local.CONTRACTS),
            "model": {"endpoint": self.session["endpoint"], **self.settings, "repo_id": "synthetic/model",
                "session_manifest": str(self.session_path), "session_sha256": local.digest(self.session_path),
                "max_rss_mb": 1024, "credential_env": local.AUTH_ENV},
            "timeout_seconds": 30, "revision": "a" * 40, "recordings": None}
        self.path = self.tmp / "profile.json"
        self.path.write_bytes(canonical(self.profile))
        self.process = Mock(pid=424242)
        self.process.poll.return_value = None
        self.watcher = Mock()
        self.watcher.is_alive.return_value = True
        self.stop = threading.Event()
        self.guard = {"stop_reason": None, "last_observed_monotonic": time.monotonic(),
                      "rss_peak_mib": 10, "min_available_mib": 50000}
        self.cases = {}
        for name in ("tool-discovery", "tool-arguments", "tool-episodes"):
            self.cases[name] = load_cases(ROOT / "datasets" / (name + "-v1") / "cases.jsonl")[0]
        self.argument = next(c for c in self.cases["tool-arguments"] if c["language"] == "en")
        self.discovery = next(c for c in self.cases["tool-discovery"] if c["split"] == "train" and c["language"] == "en")
        self.episode = next(c for c in self.cases["tool-episodes"] if c["case_id"] == "ep001-en")
        self.discovery_controls = {r["case_id"]: r["output"] for r in
            map(json.loads, (ROOT / "fixtures/tool-discovery-control.jsonl").read_text().splitlines())}
        self.episode_controls = {r["case_id"]: r["output"]["actions"] for r in
            map(json.loads, (ROOT / "fixtures/tool-episodes-control.jsonl").read_text().splitlines())}

    @contextmanager
    def owned(self):
        self.guard["last_observed_monotonic"] = time.monotonic()
        with patch.dict(os.environ, {local.AUTH_ENV: self.key}), \
                patch.object(supervision.os, "getpgid", return_value=self.process.pid), \
                supervision.native_supervision(self.path, process=self.process, watcher=self.watcher,
                    stop=self.stop, guard=self.guard, max_rss_mb=1024, min_free_mb=8192):
            yield

    def proposal(self, case=None):
        task = (case or self.argument)["input"]
        return {"tool_id": "fixture.sum", "arguments": {"artifact_id": artifact_id(task),
                "column": task["dataset"]["column"], "unit": task["dataset"]["unit"], "scope_id": task["scope_id"]}}

    def native(self, proposal, *, content=None):
        content = json.dumps(proposal) if content is None else content
        return {"model": self.settings["model_id"], "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}

    def respond(self, proposal):
        return 200, canonical(self.native(proposal))

    def predict(self, case, proposal):
        with self.owned(), patch.object(local, "http_request", return_value=self.respond(proposal)):
            adapter = create_adapter(self.profile, self.path)
            self.assertTrue(adapter.provenance["available"], adapter.provenance)
            response = adapter.predict(candidate_request(case))
            adapter.close()
        return response

    def test_real_json_parse_drives_actual_lookup_sum_and_discovery_without_gold_in_http(self):
        for case, proposal in ((self.argument, self.proposal()), (self.discovery, self.discovery_controls[self.discovery["case_id"]])):
            with self.subTest(contract=case["contract_id"]), self.owned(), \
                    patch.object(local, "http_request", return_value=self.respond(proposal)) as http:
                adapter = create_adapter(self.profile, self.path)
                result = adapter.predict(candidate_request(case))
                self.assertTrue(score_case(case, result)["passed"])
                local.validate_trace(case, result, self.settings)
                sent = json.loads(http.call_args.args[3])
                projected = json.loads(sent["messages"][1]["content"])
                self.assertEqual(projected, result["raw_output"]["calls"][0]["projection"])
                encoded = json.dumps(sent)
                for forbidden in ("reference", "assertions", "translation_family", "case_id", "split", "gold", "rationale"):
                    self.assertNotIn('"' + forbidden + '"', encoded)
                self.assertNotIn(case["case_id"], encoded)
                self.assertNotIn(self.key, json.dumps(result))
                self.assertEqual(sent["seed"], 7)
                self.assertTrue(sent["response_format"]["json_schema"]["strict"])
                self.assertFalse(sent["cache_prompt"])
                self.assertEqual(http.call_args.args[2], "/v1/chat/completions")
                adapter.close()
        result = self.predict(self.argument, self.proposal())
        self.assertEqual([r["tool_id"] for r in result["output"]["trace"]], ["fixture.lookup", "fixture.sum"])
        self.assertEqual(result["output"]["execution"]["value"], 60)

    def test_json_syntax_is_not_repaired_and_schema_wrong_json_remains_a_failed_proposal(self):
        for content in ("", "not JSON", "```json\n{}\n```", '{"a":1,"a":2}'):
            with self.subTest(content=content), self.owned(), \
                    patch.object(local, "http_request", return_value=(200, canonical(self.native(None, content=content)))):
                adapter = create_adapter(self.profile, self.path)
                result = adapter.predict(candidate_request(self.argument))
                self.assertEqual(result["status"], "error")
                self.assertIsNone(result["output"])
                self.assertEqual(len(result["raw_output"]["argument_diagnostic"]["trace"]), 1)
                local.validate_trace(self.argument, result)
                adapter.close()
        for proposal in ({}, [], None, {"execution": {"executed": True, "value": 60}}):
            result = self.predict(self.argument, proposal)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["raw_output"]["calls"][0]["output"], proposal)
            self.assertFalse(score_case(self.argument, result)["passed"])
            self.assertFalse(result["output"]["execution"]["executed"])

    def test_incomplete_wrong_model_and_usage_responses_fail_with_original_bytes(self):
        native = self.native(self.proposal())
        for mutate in (lambda n: n.update(model="foreign-model"),
                       lambda n: n["choices"][0].update(finish_reason="length"),
                       lambda n: n["usage"].update(prompt_tokens=4097),
                       lambda n: n["usage"].update(completion_tokens=0),
                       lambda n: n["usage"].update(total_tokens=999),
                       lambda n: n.update(truncated=True),
                       lambda n: n.update(truncated="false"),
                       lambda n: n["usage"].update(truncated=True),
                       lambda n: n["usage"].update(truncated="false")):
            changed = deepcopy(native)
            mutate(changed)
            data = canonical(changed)
            with self.owned(), patch.object(local, "http_request", return_value=(200, data)):
                result = create_adapter(self.profile, self.path).predict(candidate_request(self.argument))
            self.assertEqual(result["status"], "error")
            call = result["raw_output"]["calls"][0]
            self.assertEqual(base64.b64decode(call["response_base64"]), data)
            self.assertEqual(call["response_sha256"], hashlib.sha256(data).hexdigest())
            local.validate_trace(self.argument, result)
        with self.owned(), patch.object(local, "http_request", return_value=(200, b"\xff\xfe")):
            result = create_adapter(self.profile, self.path).predict(candidate_request(self.argument))
        self.assertEqual(base64.b64decode(result["raw_output"]["calls"][0]["response_base64"]), b"\xff\xfe")
        local.validate_trace(self.argument, result)
        for location in ("native", "usage"):
            native = self.native(self.proposal())
            (native if location == "native" else native["usage"])["truncated"] = False
            with self.subTest(truncation_location=location), self.owned(), \
                    patch.object(local, "http_request", return_value=(200, canonical(native))):
                result = create_adapter(self.profile, self.path).predict(candidate_request(self.argument))
            self.assertEqual(result["status"], "ok")
            self.assertTrue(score_case(self.argument, result)["passed"])
            local.validate_trace(self.argument, result)

    def test_wrong_unit_and_premature_finish_cannot_execute_or_claim_success(self):
        proposal = self.proposal()
        proposal["arguments"]["unit"] = "USD"
        with patch.object(FixtureStore, "sum", side_effect=AssertionError("wrong unit executed")):
            result = self.predict(self.argument, proposal)
        self.assertFalse(result["output"]["execution"]["executed"])
        self.assertFalse(score_case(self.argument, result)["passed"])
        finish = deepcopy(self.episode_controls[self.episode["case_id"]][-1])
        with patch.object(FixtureStore, "lookup", side_effect=AssertionError("premature finish called tool")), \
                patch.object(FixtureStore, "sum", side_effect=AssertionError("premature finish called tool")):
            result = self.predict(self.episode, finish)
        self.assertFalse(result["output"]["checks"]["task_success"])
        self.assertFalse(result["output"]["checks"]["stopping_valid"])
        self.assertFalse(score_case(self.episode, result)["passed"])

    def test_timeout_keeps_executed_first_lookup_and_original_status_denominators(self):
        with self.owned(), patch.object(local, "http_request", side_effect=TimeoutError()), \
                patch.object(FixtureStore, "sum", side_effect=AssertionError("timeout executed sum")):
            result = create_adapter(self.profile, self.path).predict(candidate_request(self.argument))
        self.assertEqual(result["status"], "timeout")
        self.assertIsNone(result["output"])
        self.assertEqual(len(result["raw_output"]["argument_diagnostic"]["trace"]), 1)
        self.assertTrue(result["raw_output"]["calls"][0]["http_attempted"])
        local.validate_trace(self.argument, result)
        metric = summarize([self.argument], [{"case_id": self.argument["case_id"], **result}])["task_metrics"][tool_arguments.CONTRACT]
        self.assertEqual(metric["tool_calls_observed"], 1)
        self.assertEqual(metric["cases_with_execution_trace"], 1)
        self.assertEqual(metric["result_correct_cases"], 0)

    def test_incomplete_http_transport_keeps_first_lookup_and_attempt_ledger(self):
        with self.owned(), patch.object(local, "http_request", side_effect=IncompleteRead(b"partial", 100)), \
                patch.object(FixtureStore, "sum", side_effect=AssertionError("incomplete response executed sum")):
            result = create_adapter(self.profile, self.path).predict(candidate_request(self.argument))
        self.assertEqual(result["status"], "error")
        self.assertEqual(len(result["raw_output"]["argument_diagnostic"]["trace"]), 1)
        call = result["raw_output"]["calls"][0]
        self.assertTrue(call["http_attempted"])
        self.assertEqual(call["error"], "local_json_transport_error")
        self.assertIsNone(call["response_base64"])
        local.validate_trace(self.argument, result)

    def test_http_overflow_and_post_response_guard_loss_keep_their_actual_ledger(self):
        overflow = canonical({"error": {"type": "exceed_context_size_error", "n_prompt_tokens": 4097, "n_ctx": 4096}})
        for code, data, expected in ((400, overflow, "unsupported"), (500, b"server failure", "error")):
            with self.subTest(code=code), self.owned(), patch.object(local, "http_request", return_value=(code, data)):
                result = create_adapter(self.profile, self.path).predict(candidate_request(self.argument))
            self.assertEqual(result["status"], expected)
            self.assertEqual(base64.b64decode(result["raw_output"]["calls"][0]["response_base64"]), data)
            self.assertEqual(len(result["raw_output"]["argument_diagnostic"]["trace"]), 1)
            local.validate_trace(self.argument, result)
        def lose_watcher(*args):
            self.watcher.is_alive.return_value = False
            return self.respond(self.proposal())
        with self.owned(), patch.object(local, "http_request", side_effect=lose_watcher), \
                patch.object(FixtureStore, "sum", side_effect=AssertionError("lost supervision executed sum")):
            result = create_adapter(self.profile, self.path).predict(candidate_request(self.argument))
        self.assertEqual(result["status"], "error")
        call = result["raw_output"]["calls"][0]
        self.assertEqual(call["guard_error"], "local_json_supervision_lost")
        self.assertIsNotNone(call["response_base64"])
        self.assertIsNone(call["output"])
        local.validate_trace(self.argument, result)

    def test_v1_stays_one_second_and_v2_counts_each_model_invocation_in_deadline(self):
        case = deepcopy(self.episode)
        case["input"]["budgets"]["max_elapsed_ms"] = 60000
        with self.assertRaises(CaseError):
            validate_cases([case])
        case["input"]["schema_version"] = tool_episodes.INPUT_VERSION_V2
        validate_cases([case])
        case["input"]["budgets"]["max_elapsed_ms"] = 60001
        with self.assertRaises(CaseError):
            validate_cases([case])
        case["input"]["budgets"]["max_elapsed_ms"] = 60000
        for candidate, successful in ((self.episode, False), (case, True)):
            clock = [1000.0]
            actions = iter(self.episode_controls[self.episode["case_id"]])
            observed_timeouts = []
            def http(*args):
                observed_timeouts.append(args[-1])
                clock[0] += 2
                self.guard["last_observed_monotonic"] = clock[0]
                return self.respond(next(actions))
            with patch.object(local.time, "monotonic", side_effect=lambda: clock[0]), self.owned(), \
                    patch.object(local, "http_request", side_effect=http):
                result = create_adapter(self.profile, self.path).predict(candidate_request(candidate))
            local.validate_trace(candidate, result)
            self.assertEqual(result["output"]["checks"]["task_success"], successful)
            self.assertEqual(result["output"]["elapsed_ms"], 6000 if successful else 2000)
            self.assertEqual(result["output"]["usage"]["tool_calls_executed"], 2 if successful else 0)
            self.assertEqual(observed_timeouts[0], 30 if successful else 1)

    def test_raw_generation_cannot_be_replaced_by_a_different_proposal_or_receipt(self):
        original = self.predict(self.argument, self.proposal())
        mutations = (lambda r: r["raw_output"]["calls"][0]["output"]["arguments"].update(unit="USD"),
                     lambda r: r["raw_output"]["calls"][0].update(response_sha256="0" * 64),
                     lambda r: r["raw_output"]["calls"][0].update(request_sha256="0" * 64),
                     lambda r: r["raw_output"]["calls"][0]["projection"].update(scope_id="foreign"),
                     lambda r: r["output"]["trace"][1].update(value=999),
                     lambda r: r["raw_output"]["calls"][0].update(response_base64=base64.b64encode(b"{}").decode()))
        for mutate in mutations:
            response = deepcopy(original)
            mutate(response)
            with patch.object(FixtureStore, "lookup", side_effect=AssertionError("pure checking executed")), \
                    patch.object(local, "http_request", side_effect=AssertionError("pure checking called model")):
                self.assertFalse(score_case(self.argument, response)["passed"])
                with self.assertRaises(CaseError):
                    local.validate_trace(self.argument, response)

    def test_credential_echo_is_redacted_and_can_never_be_a_scored_proposal(self):
        data = canonical(self.native(self.key))
        with self.owned(), patch.object(local, "http_request", return_value=(200, data)):
            result = create_adapter(self.profile, self.path).predict(candidate_request(self.argument))
        self.assertEqual(result["status"], "error")
        self.assertNotIn(self.key, json.dumps(result))
        call = result["raw_output"]["calls"][0]
        self.assertTrue(call["response_redacted"])
        self.assertIsNone(call["response_base64"])
        self.assertEqual(call["response_sha256"], hashlib.sha256(data).hexdigest())
        local.validate_trace(self.argument, result)
        forged = deepcopy(result)
        forged["raw_output"]["calls"][0]["output"] = self.proposal()
        with self.assertRaises(CaseError):
            local.validate_trace(self.argument, forged)

    def test_json_escaped_credential_is_redacted_before_decoding_or_retaining_a_proposal(self):
        escaped = "".join("\\u%04x" % ord(char) for char in self.key)
        content = '{"secret":"' + escaped + '"}'
        embedded = canonical(self.native(None, content=content))
        metadata = canonical({**self.native(self.proposal()), "diagnostic": self.key})
        metadata = metadata.replace(self.key.encode(), escaped.encode())
        for data in (embedded, metadata):
            with self.subTest(data=data), self.owned(), \
                    patch.object(local, "http_request", return_value=(200, data)), \
                    patch.object(FixtureStore, "sum", side_effect=AssertionError("credential response executed sum")):
                self.assertNotIn(self.key.encode(), data)
                result = create_adapter(self.profile, self.path).predict(candidate_request(self.argument))
            self.assertEqual(result["status"], "error")
            self.assertIsNone(result["output"])
            self.assertNotIn(self.key, json.dumps(result))
            call = result["raw_output"]["calls"][0]
            self.assertTrue(call["response_redacted"])
            self.assertIsNone(call["response_base64"])
            self.assertIsNone(call["output"])
            self.assertEqual(call["response_sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(len(result["raw_output"]["argument_diagnostic"]["trace"]), 1)
            local.validate_trace(self.argument, result)
            self.assertFalse(score_case(self.argument, result)["passed"])

    def test_model_duration_cannot_contradict_passing_episode_or_case_intervals(self):
        clock = [1000.0]
        actions = iter(self.episode_controls[self.episode["case_id"]])
        sum_values = FixtureStore.sum

        def http(*args):
            clock[0] += .1
            self.guard["last_observed_monotonic"] = clock[0]
            return self.respond(next(actions))

        def timed_sum(store, arguments):
            result = sum_values(store, arguments)
            clock[0] += .5
            self.guard["last_observed_monotonic"] = clock[0]
            return result

        run = self.tmp / "episode-timing"
        with patch.object(local.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(local.time, "perf_counter", side_effect=lambda: clock[0]), \
                self.owned(), patch.object(local, "http_request", side_effect=http), \
                patch.object(FixtureStore, "sum", timed_sum):
            first = campaigns.run_campaign(self.dataset([self.episode]), self.path, run)
        self.assertEqual(first["metrics"]["passed_cases"], 1)
        original = json.loads((run / "raw.jsonl").read_text())
        self.assertTrue(original["output"]["checks"]["budgets_respected"])
        self.assertAlmostEqual(original["duration_ms"], 800)
        self.assertAlmostEqual(original["output"]["elapsed_ms"], 800)
        self.assertAlmostEqual(sum(call["duration_ms"] for call in original["raw_output"]["calls"]), 300)
        local.validate_trace(self.episode, original)
        for mutate in (lambda r: r["raw_output"]["calls"][0].update(duration_ms=2000),
                       lambda r: r.update(duration_ms=50),
                       lambda r: r.update(duration_ms=400)):
            changed = deepcopy(original)
            mutate(changed)
            with self.subTest(mutate=mutate), \
                    patch.object(local, "http_request", side_effect=AssertionError("timing validation called model")), \
                    patch.object(FixtureStore, "lookup", side_effect=AssertionError("timing validation executed lookup")), \
                    patch.object(FixtureStore, "sum", side_effect=AssertionError("timing validation executed sum")):
                with self.assertRaisesRegex(CaseError, "duration_exceeds"):
                    local.validate_trace(self.episode, changed)
                self.assertFalse(score_case(self.episode, changed)["passed"])
                metric = summarize([self.episode], [changed])["task_metrics"][tool_episodes.CONTRACT]
                self.assertEqual(metric["budget_eligible_cases"], 1)
                self.assertEqual(metric["budget_correct_cases"], 0)

    def test_final_error_must_match_the_last_actual_model_call(self):
        valid = self.predict(self.argument, self.proposal())
        with self.owned(), patch.object(local, "http_request", side_effect=TimeoutError()):
            timeout = create_adapter(self.profile, self.path).predict(candidate_request(self.argument))
        for result in (valid, timeout):
            local.validate_trace(self.argument, result)
            changed = deepcopy(result)
            changed["error"] = "local_json_execution_or_guard_invalid"
            with self.subTest(status=result["status"]), \
                    patch.object(local, "http_request", side_effect=AssertionError("error validation called model")), \
                    patch.object(FixtureStore, "lookup", side_effect=AssertionError("error validation executed lookup")):
                with self.assertRaisesRegex(CaseError, "final_status_or_output"):
                    local.validate_trace(self.argument, changed)
                self.assertFalse(score_case(self.argument, changed)["passed"])

    def test_prepolicy_deadline_keeps_a_zero_call_failure_and_rescores_without_execution(self):
        clock = [1000.0]
        initialize = tool_episodes.EpisodeRuntime.__init__

        def initialize_after_deadline(runtime, task):
            initialize(runtime, task)
            clock[0] += 2
            self.guard["last_observed_monotonic"] = clock[0]

        run = self.tmp / "episode-prepolicy-deadline"
        with patch.object(local.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(local.time, "perf_counter", side_effect=lambda: clock[0]), \
                self.owned(), patch.object(tool_episodes.EpisodeRuntime, "__init__", initialize_after_deadline), \
                patch.object(local, "http_request", side_effect=AssertionError("expired episode called model")), \
                patch.object(FixtureStore, "lookup", side_effect=AssertionError("expired episode executed lookup")), \
                patch.object(FixtureStore, "sum", side_effect=AssertionError("expired episode executed sum")):
            first = campaigns.run_campaign(self.dataset([self.episode]), self.path, run)
        result = json.loads((run / "raw.jsonl").read_text())
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["error"])
        self.assertEqual(result["raw_output"]["calls"], [])
        self.assertEqual(result["output"]["steps"], [])
        self.assertEqual(result["output"]["termination"], "time_limit")
        self.assertFalse(result["output"]["checks"]["budgets_respected"])
        self.assertEqual(first["metrics"]["scored_cases"], 1)
        self.assertEqual(first["metrics"]["passed_cases"], 0)
        self.assertNotEqual(first["metrics"]["verdict"], "pass")
        metric = first["metrics"]["task_metrics"][tool_episodes.CONTRACT]
        self.assertEqual(metric["tool_calls_observed"], 0)
        self.assertEqual(metric["policy_steps_observed"], 0)
        self.assertEqual(metric["budget_eligible_cases"], 1)
        self.assertEqual(metric["budget_correct_cases"], 0)
        original = {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}
        with ExitStack() as stack:
            for owner, name in ((local.LocalToolPolicyAdapter, "__init__"), (local, "http_request"),
                                (local.time, "monotonic"), (tool_episodes, "run_episode"),
                                (tool_episodes.EpisodeRuntime, "__init__"), (FixtureStore, "lookup"), (FixtureStore, "sum")):
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError("deadline rescore executed " + name)))
            second = campaigns.rescore_campaign(run, self.tmp / "prepolicy-deadline-rescore")
        self.assertEqual(first["metrics"], second["metrics"])
        self.assertEqual({p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}, original)

    def test_live_owned_scope_required_and_lost_or_changed_assets_prevent_http(self):
        with patch.object(local, "http_request", side_effect=AssertionError("unowned model called")):
            adapter = create_adapter(self.profile, self.path)
            self.assertFalse(adapter.provenance["available"])
            self.assertEqual(adapter.predict(candidate_request(self.argument))["status"], "error")
        with self.owned(), patch.object(local, "http_request", side_effect=AssertionError("changed asset called")):
            adapter = create_adapter(self.profile, self.path)
            self.assertTrue(adapter.provenance["available"])
            self.files["template.jinja"].write_text("changed synthetic template")
            self.assertEqual(adapter.predict(candidate_request(self.argument))["status"], "error")
        self.assertEqual(adapter.predict(candidate_request(self.argument))["status"], "error")

    def dataset(self, cases):
        path = self.tmp / "cases.jsonl"
        path.write_bytes(b"".join(campaigns._encode(c) for c in cases))
        return path

    def test_actual_archive_and_rescore_are_pure_and_preserve_all_original_bytes(self):
        run = self.tmp / "run"
        dataset = self.dataset([self.argument])
        with self.owned(), patch.object(local, "http_request", return_value=self.respond(self.proposal())):
            first = campaigns.run_campaign(dataset, self.path, run)
        self.assertEqual(first["metrics"]["passed_cases"], 1)
        original = {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}
        with ExitStack() as stack:
            for owner, name in ((local.LocalToolPolicyAdapter, "__init__"), (local, "http_request"),
                                (local.time, "monotonic"), (FixtureStore, "lookup"), (FixtureStore, "sum"),
                                (tool_episodes, "run_episode")):
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError("rescore executed " + name)))
            second = campaigns.rescore_campaign(run, self.tmp / "rescore")
        self.assertEqual(first["metrics"], second["metrics"])
        self.assertEqual({p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}, original)
        manifest = json.loads(original["manifest.json"])
        self.assertEqual(manifest["input_protocol"], "generated_tool_proposals_v1")
        self.assertEqual(manifest["qualification"], "model_isolated")
        self.assertIn("local_tool_policy.py", manifest["scorer"]["files"])

    def test_archive_rejects_resealed_raw_generation_misbinding(self):
        run = self.tmp / "tamper"
        with self.owned(), patch.object(local, "http_request", return_value=self.respond(self.proposal())):
            campaigns.run_campaign(self.dataset([self.argument]), self.path, run)
        rows = [json.loads(line) for line in (run / "raw.jsonl").read_bytes().splitlines()]
        rows[0]["raw_output"]["calls"][0]["output"]["arguments"]["unit"] = "USD"
        (run / "raw.jsonl").write_bytes(b"".join(campaigns._encode(r) for r in rows))
        seal = json.loads((run / "seal.json").read_bytes())
        seal["files"]["raw.jsonl"] = local.digest(run / "raw.jsonl")
        seal["sha256"] = campaigns._hash(campaigns._encode(seal["files"]))
        (run / "seal.json").write_bytes(campaigns._encode(seal))
        with patch.object(local, "http_request", side_effect=AssertionError("tampered rescore called model")), \
                self.assertRaisesRegex(campaigns.CampaignError, "generated proposal trace"):
            campaigns.rescore_campaign(run, self.tmp / "tamper-rescore")

    def test_executed_episode_and_partial_timeout_archives_rescore_without_policy_or_tools(self):
        case = deepcopy(self.episode)
        case["input"]["schema_version"] = tool_episodes.INPUT_VERSION_V2
        case["input"]["budgets"]["max_elapsed_ms"] = 60000
        for timeout in (False, True):
            actions = iter(self.episode_controls[case["case_id"]])
            calls = []
            def http(*args):
                calls.append(json.loads(args[3]))
                if timeout and len(calls) == 2:
                    raise TimeoutError()
                return self.respond(next(actions))
            run = self.tmp / ("episode-timeout" if timeout else "episode-success")
            with self.subTest(timeout=timeout), self.owned(), patch.object(local, "http_request", side_effect=http):
                first = campaigns.run_campaign(self.dataset([case]), self.path, run)
            metric = first["metrics"]["task_metrics"][tool_episodes.CONTRACT]
            self.assertEqual(metric["tool_calls_observed"], 1 if timeout else 2)
            self.assertEqual(metric["task_success_cases"], 0 if timeout else 1)
            self.assertEqual(len(calls), 2 if timeout else 3)
            second_projection = json.loads(calls[1]["messages"][1]["content"])
            self.assertEqual(second_projection["observations"][0]["tool_id"], "fixture.lookup")
            original = {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}
            with patch.object(local.LocalToolPolicyAdapter, "__init__", side_effect=AssertionError("rescore model")), \
                    patch.object(local, "http_request", side_effect=AssertionError("rescore HTTP")), \
                    patch.object(local.time, "monotonic", side_effect=AssertionError("rescore clock")), \
                    patch.object(tool_episodes.EpisodeRuntime, "lookup", side_effect=AssertionError("rescore lookup")), \
                    patch.object(tool_episodes.EpisodeRuntime, "sum", side_effect=AssertionError("rescore sum")), \
                    patch.object(tool_episodes, "run_episode", side_effect=AssertionError("rescore loop")):
                second = campaigns.rescore_campaign(run, self.tmp / (run.name + "-rescore"))
            self.assertEqual(first["metrics"], second["metrics"])
            self.assertEqual({p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}, original)

    def test_actual_available_and_missing_campaign_artifacts_validate_strict_schemas(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is optional")
        for available in (True, False):
            with self.subTest(available=available), self.owned(), \
                    patch.object(local, "http_request", return_value=self.respond(self.proposal())):
                if not available:
                    self.files["model.gguf"].unlink()
                run = self.tmp / ("available" if available else "missing")
                summary = campaigns.run_campaign(self.dataset([self.argument]), self.path, run)
            manifest = json.loads((run / "manifest.json").read_bytes())
            self.assertEqual(manifest["adapter_provenance"]["available"], available)
            for name, value in (("candidate", self.profile), ("campaign", manifest), ("campaign-summary", summary)):
                schema = json.loads((ROOT / "schemas" / (name + "-v1.schema.json")).read_text())
                jsonschema.Draft202012Validator.check_schema(schema)
                jsonschema.validate(value, schema)
            schema = json.loads((ROOT / "schemas/result-v1.schema.json").read_text())
            for line in (run / "raw.jsonl").read_bytes().splitlines():
                jsonschema.validate(json.loads(line), schema)
        candidate_schema = json.loads((ROOT / "schemas/candidate-v1.schema.json").read_text())
        for changes in ({"adapter": "recorded"}, {"adapter": "systemone_local"}, {"qualification": "harness_control"},
                        {"model": None}, {"revision": None}, {"capabilities": ["bench.context-choice"]}, {"timeout_seconds": 31}):
            with self.subTest(changes=changes), self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate({**deepcopy(self.profile), **changes}, candidate_schema)
        campaign_schema = json.loads((ROOT / "schemas/campaign-v1.schema.json").read_text())
        available = json.loads((self.tmp / "available/manifest.json").read_bytes())
        for mutate in (lambda m: m.update(qualification="harness_control"),
                       lambda m: m.update(input_protocol="current_equivalent"),
                       lambda m: m["adapter_provenance"].update(adapter="recorded"),
                       lambda m: m["adapter_provenance"]["identity"]["runtime"].update(revision="f" * 40),
                       lambda m: m["adapter_provenance"]["identity"]["model"].pop("sha256"),
                       lambda m: m["adapter_provenance"]["identity"]["adapter_sources"].pop("synthetic_tools.py")):
            spoof = deepcopy(available)
            mutate(spoof)
            with self.subTest(mutate=mutate), self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(spoof, campaign_schema)
        with patch.object(local, "http_request", side_effect=AssertionError("unowned campaign called model")):
            summary = campaigns.run_campaign(self.dataset([self.argument]), self.path, self.tmp / "unowned")
        unowned = json.loads((self.tmp / "unowned/manifest.json").read_bytes())
        self.assertFalse(unowned["adapter_provenance"]["available"])
        self.assertEqual(summary["metrics"]["counts_by_status"]["error"], 1)
        jsonschema.validate(unowned, campaign_schema)

    def test_all_ten_new_canary_inputs_load_without_a_runtime_or_model(self):
        cases, digest = load_cases(ROOT / "datasets/tool-policy-canary-v1/cases.jsonl")
        self.assertEqual(len(cases), 10)
        self.assertEqual(digest, "6add6d14904e16cc39449368ff932316409c294dd43674f4fb9a1a1fcdbc2a6d")
        self.assertEqual({c["split"] for c in cases}, {"train"})
        self.assertEqual(len({c["translation_family"] for c in cases}), 5)
        for case in cases:
            self.assertIsInstance(local.output_schema(case["contract_id"]), dict)

    def test_import_is_inert_and_profile_rejects_wrong_endpoints_resource_or_generation_bounds(self):
        name = "deposium_bench._local_tool_import_control"
        spec = importlib.util.spec_from_file_location(name, ROOT / "deposium_bench/local_tool_policy.py")
        module = importlib.util.module_from_spec(spec)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(FixtureStore, "lookup", side_effect=AssertionError("import tool")), \
                patch.object(local, "http_request", side_effect=AssertionError("import HTTP")), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            spec.loader.exec_module(module)
        self.assertEqual(stdout.getvalue() + stderr.getvalue(), "")
        parse_profile(canonical(self.profile))
        for key, value in (("endpoint", "http://example.test/v1/chat/completions"), ("endpoint", "http://127.0.0.1:80/v1/chat/completions"),
                           ("max_length", 8192), ("max_rss_mb", 8193), ("max_output_tokens", 513), ("seed", -1),
                           ("prompt_version", "unknown"), ("session_sha256", "bad")):
            profile = deepcopy(self.profile)
            profile["model"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_profile(canonical(profile))


if __name__ == "__main__":
    unittest.main()
