"""Bounded executed fixture episodes, with pure retained-transcript checking.

Only the dedicated scripted control adapter is qualified. Policy invocations
receive actual observations; rescore never invokes a policy, clock or tool.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import math
from pathlib import Path
import time

from .cases import CaseError, typed_equal
from .synthetic_tools import FixtureStore, ToolError, artifact_id, canonical, validate_fixture

CONTRACT = "bench.tool-episode"
INPUT_VERSION = "deposium.tool-episode-input/v1"
INPUT_VERSION_V2 = "deposium.tool-episode-input/v2"
OUTPUT_VERSION = "deposium.tool-episode-output/v1"
PROJECTION_VERSION = "deposium.tool-episode-candidate-input/v1"
METRICS_VERSION = "deposium.tool-episode-metrics/v1"
STAGES = ("tool", "arguments", "binding", "execution", "result", "stopping", "budget")


def _object(value, fields, where):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise CaseError("tool-episode: invalid " + where + " fields")


def validate_input(task):
    _object(task, {"schema_version", "request", "scope_id", "dataset", "known_dataset_id", "faults", "budgets"}, "input")
    if task["schema_version"] not in (INPUT_VERSION, INPUT_VERSION_V2):
        raise CaseError("tool-episode: invalid input version")
    request = task["request"]
    if (not isinstance(request, str) or not request.strip() or len(request) > 8192
            or any(ord(c) < 32 for c in request)):
        raise CaseError("tool-episode: invalid request")
    try:
        validate_fixture(task["scope_id"], task["dataset"], allow_empty=True)
    except ToolError as exc:
        raise CaseError("tool-episode: " + str(exc)) from None
    if task["known_dataset_id"] not in (None, task["dataset"]["dataset_id"]):
        raise CaseError("tool-episode: unknown dataset fixture")
    _object(task["faults"], {"lookup_events", "disable_sum_after_lookup"}, "fault schedule")
    events = task["faults"]["lookup_events"]
    if (not isinstance(events, list) or not 1 <= len(events) <= 2
            or any(event not in ("ok", "transient_error", "partial") for event in events)
            or type(task["faults"]["disable_sum_after_lookup"]) is not bool):
        raise CaseError("tool-episode: invalid bounded faults")
    if not task["dataset"]["values"] and "partial" in events:
        raise CaseError("tool-episode: empty data cannot have a partial view")
    # v1 stays at its original one-second fixture limit. A separately versioned
    # input permits a predeclared real-policy envelope; elapsed model time is
    # still counted by the same state machine and retained receipt checker.
    elapsed_bound = 1000 if task["schema_version"] == INPUT_VERSION else 60000
    bounds = {"max_steps": 5, "max_tool_calls": 3, "max_lookup_attempts": 2, "max_elapsed_ms": elapsed_bound}
    _object(task["budgets"], bounds, "budget")
    if any(type(task["budgets"][k]) is not int or not 1 <= task["budgets"][k] <= v for k, v in bounds.items()):
        raise CaseError("tool-episode: invalid bounded budget")


def expected_outcome(task):
    """Authored fixture oracle, not an observation or a tool execution."""
    if task["known_dataset_id"] is None:
        return {"decision": "clarify", "reason": "missing_information", "value": None, "unit": None}
    events = task["faults"]["lookup_events"]
    event = next((events[min(i, len(events) - 1)] for i in range(task["budgets"]["max_lookup_attempts"])
                  if events[min(i, len(events) - 1)] != "transient_error"), "transient_error")
    if event == "transient_error":
        reason, decision = "persistent_error", "stop"
    elif not task["dataset"]["values"]:
        reason, decision = "no_data", "stop"
    elif event == "partial":
        reason, decision = "partial_data", "clarify"
    elif task["faults"]["disable_sum_after_lookup"]:
        reason, decision = "unavailable", "stop"
    else:
        return {"decision": "success", "reason": "complete", "value": sum(task["dataset"]["values"]), "unit": task["dataset"]["unit"]}
    return {"decision": decision, "reason": reason, "value": None, "unit": None}


def validate_case(case):
    validate_input(case["input"])
    outcome = expected_outcome(case["input"])
    expected = {"/checks/budgets_respected": True, "/checks/stopping_valid": True,
                "/checks/procedure_valid": True, "/checks/task_success": outcome["decision"] == "success",
                **{"/outcome/" + k: v for k, v in outcome.items()}}
    assertions = case["reference"]["assertions"]
    if (case["reference"]["abstention_allowed"] or len(assertions) != len(expected)
            or {a["path"] for a in assertions} != set(expected)
            or any(a["op"] != "equals" or not typed_equal(a["value"], expected[a["path"]]) for a in assertions)):
        raise CaseError("tool-episode: incomplete or inconsistent eight-assertion oracle")


def _lookup_receipt(task, event, call, available):
    """Pure reconstruction used to validate an archived receipt only."""
    common = {"tool_id": "fixture.lookup", "tool_call": call,
              "arguments": {"dataset_id": task["known_dataset_id"], "scope_id": task["scope_id"]}}
    if event == "transient_error":
        return {**common, "status": "controlled_error", "error": "transient_error",
                "availability": {"fixture.lookup": True, "fixture.sum": available}}
    data = deepcopy(task["dataset"])
    if event == "partial":
        data["values"] = data["values"][:max(1, len(data["values"]) // 2)]
    artifact = {"artifact_id": artifact_id({"scope_id": task["scope_id"], "dataset": data}, allow_empty=True),
                "scope_id": task["scope_id"], **data, "complete": event == "ok"}
    return {**common, "status": "ok", "artifact": artifact,
            "availability": {"fixture.lookup": True, "fixture.sum": available}}


class EpisodeRuntime:
    """Actual bounded fault functions around the shared case-local store."""
    def __init__(self, task):
        self.task = deepcopy(task)
        self.store = FixtureStore(task, task["budgets"]["max_tool_calls"], allow_empty=True)
        self.lookup_calls = 0
        self.sum_available = True
        self.complete = {}

    def lookup(self, arguments):
        events = self.task["faults"]["lookup_events"]
        event = events[min(self.lookup_calls, len(events) - 1)]
        self.lookup_calls += 1
        if event == "transient_error":
            self.store._admit()
            # This error is returned by an invoked fixture function, not by a
            # pre-recorded observation or an unexecuted hypothetical forward.
            receipt = {"tool_id": "fixture.lookup", "tool_call": self.store.calls,
                       "arguments": deepcopy(arguments), "status": "controlled_error", "error": "transient_error"}
        else:
            original = deepcopy(self.store.task["dataset"])
            if event == "partial":
                self.store.task["dataset"]["values"] = original["values"][:max(1, len(original["values"]) // 2)]
            try:
                receipt = self.store.lookup()
            finally:
                self.store.task["dataset"] = original
            receipt["artifact"]["complete"] = event == "ok"
            self.complete[receipt["artifact"]["artifact_id"]] = event == "ok"
            if self.task["faults"]["disable_sum_after_lookup"]:
                self.sum_available = False
        receipt["availability"] = {"fixture.lookup": True, "fixture.sum": self.sum_available}
        return receipt

    def sum(self, arguments):
        artifact = self.store.artifacts.get(arguments["artifact_id"])
        if (not self.sum_available or artifact is None or not artifact["values"]
                or not self.complete.get(arguments["artifact_id"], False)):
            raise ToolError("episode_sum_not_eligible")
        return self.store.sum(arguments)


class _State:
    """Pure transition state used by execution and archive checking alike."""
    def __init__(self, task):
        self.task = task
        self.attempts = self.lookups = self.calls = self.lookup_calls = 0
        self.available = True
        self.artifact = self.result = None
        self.observations, self.history = [], []
        self.procedure = self.budgets = True
        self.tool_ok = self.args_ok = self.binding_ok = True
        self.binding_checks = self.valid_calls = 0
        self.finished = self.stopping = False
        self.outcome = None

    def projection(self, elapsed, steps):
        task = self.task
        full = self.artifact is not None and self.artifact["complete"] and bool(self.artifact["values"])
        return {"schema_version": PROJECTION_VERSION, "request": task["request"], "scope_id": task["scope_id"],
                "known_parameters": {"dataset_id": task["known_dataset_id"], "column": task["dataset"]["column"], "unit": task["dataset"]["unit"]},
                "tools": [{"tool_id": "fixture.lookup", "available": True,
                           "eligible": task["known_dataset_id"] is not None and not (self.artifact is not None and not self.artifact["complete"]),
                           "arguments": ["dataset_id", "scope_id"]},
                          {"tool_id": "fixture.sum", "available": self.available, "eligible": self.available and full,
                           "arguments": ["artifact_id", "column", "unit", "scope_id"]}],
                "observations": deepcopy(self.observations), "history": deepcopy(self.history),
                "remaining_budget": {"policy_steps": max(0, task["budgets"]["max_steps"] - steps),
                                     "tool_calls": max(0, task["budgets"]["max_tool_calls"] - self.attempts),
                                     "lookup_attempts": max(0, task["budgets"]["max_lookup_attempts"] - self.lookups),
                                     "elapsed_ms": max(0.0, task["budgets"]["max_elapsed_ms"] - elapsed)}}

    def finish_valid(self, outcome):
        decision, reason, value, unit = (outcome[k] for k in ("decision", "reason", "value", "unit"))
        if decision == "success":
            return (reason == "complete" and self.result is not None
                    and type(value) is int and value == self.result["value"] and unit == self.result["unit"])
        if value is not None or unit is not None:
            return False
        if decision == "clarify" and reason == "missing_information":
            return self.task["known_dataset_id"] is None and self.calls == 0
        if decision == "clarify" and reason == "partial_data":
            return self.artifact is not None and not self.artifact["complete"]
        if decision == "stop" and reason == "no_data":
            return self.artifact is not None and self.artifact["complete"] and not self.artifact["values"]
        if decision == "stop" and reason == "unavailable":
            return not self.available and self.artifact is not None
        if decision == "stop" and reason == "persistent_error":
            return (self.lookup_calls >= self.task["budgets"]["max_lookup_attempts"]
                    and self.observations and self.observations[-1]["status"] == "controlled_error")
        return False

    def transition(self, proposal, after_policy, actual=None, runtime=None):
        """Validate action and consume a receipt; pure when runtime is absent."""
        is_call = isinstance(proposal, dict) and proposal.get("action") == "call"
        if is_call:
            self.attempts += 1
            self.lookups += proposal.get("tool_id") == "fixture.lookup"
        if after_policy > self.task["budgets"]["max_elapsed_ms"]:
            self.budgets = self.procedure = False
            return {"allowed": False, "code": "time_limit"}, None
        # Every proposed call consumes an attempt, including calls whose tool
        # or shape is invalid. Check these independent limits before rejecting
        # malformed actions so their attempts cannot escape budget accounting.
        if is_call and (self.attempts > self.task["budgets"]["max_tool_calls"]
                        or self.lookups > self.task["budgets"]["max_lookup_attempts"]):
            self.budgets = self.procedure = False
            return {"allowed": False, "code": "call_or_retry_limit"}, None
        if not isinstance(proposal, dict) or len(canonical(proposal)) > 8192:
            self.procedure = self.tool_ok = self.args_ok = False
            return {"allowed": False, "code": "invalid_action"}, None
        if proposal.get("action") == "finish":
            try:
                _object(proposal, {"action", "decision", "reason", "value", "unit"}, "finish")
            except CaseError:
                self.procedure = False
                return {"allowed": False, "code": "invalid_action"}, None
            self.outcome = {k: deepcopy(proposal[k]) for k in ("decision", "reason", "value", "unit")}
            self.finished = True
            self.stopping = bool(self.finish_valid(self.outcome))
            self.procedure &= self.stopping
            return {"allowed": self.stopping, "code": "finish" if self.stopping else "invalid_finish"}, None
        if (not is_call or set(proposal) != {"action", "tool_id", "arguments"}
                or proposal.get("tool_id") not in ("fixture.lookup", "fixture.sum")):
            self.procedure = self.tool_ok = self.args_ok = False
            return {"allowed": False, "code": "invalid_action"}, None
        tool, args = proposal["tool_id"], proposal["arguments"]
        fields = {"dataset_id", "scope_id"} if tool == "fixture.lookup" else {"artifact_id", "column", "unit", "scope_id"}
        shape = isinstance(args, dict) and set(args) == fields and all(isinstance(v, str) and 0 < len(v) <= 128 for v in args.values())
        args_ok = shape and args["scope_id"] == self.task["scope_id"]
        if tool == "fixture.lookup":
            eligible = self.task["known_dataset_id"] is not None and not (self.artifact is not None and not self.artifact["complete"])
            args_ok = args_ok and args["dataset_id"] == self.task["known_dataset_id"]
            binding_ok = True
        else:
            eligible = self.available and self.artifact is not None and self.artifact["complete"] and bool(self.artifact["values"])
            args_ok = args_ok and args["column"] == self.task["dataset"]["column"] and args["unit"] == self.task["dataset"]["unit"]
            self.binding_checks += 1
            binding_ok = shape and self.artifact is not None and args["artifact_id"] == self.artifact["artifact_id"]
            self.binding_ok &= bool(binding_ok)
        self.tool_ok &= bool(eligible)
        self.args_ok &= bool(args_ok)
        if not eligible or not args_ok or not binding_ok:
            self.procedure = False
            return {"allowed": False, "code": "tool_argument_or_binding_guard"}, None
        self.calls += 1
        if tool == "fixture.lookup":
            events = self.task["faults"]["lookup_events"]
            event = events[min(self.lookup_calls, len(events) - 1)]
            self.lookup_calls += 1
            available = self.available and not (event != "transient_error" and self.task["faults"]["disable_sum_after_lookup"])
            expected = _lookup_receipt(self.task, event, self.calls, available)
        else:
            expected = {"tool_id": "fixture.sum", "tool_call": self.calls, "status": "ok",
                        "arguments": deepcopy(args), "value": sum(self.artifact["values"]), "unit": self.artifact["unit"]}
        receipt = getattr(runtime, "lookup" if tool == "fixture.lookup" else "sum")(args) if runtime is not None else actual
        if not typed_equal(receipt, expected):
            raise CaseError("tool-episode: inconsistent actual observation")
        self.valid_calls += 1
        self.observations.append(deepcopy(receipt))
        if tool == "fixture.lookup":
            self.available = receipt["availability"]["fixture.sum"]
            if receipt["status"] == "ok":
                self.artifact = deepcopy(receipt["artifact"])
        else:
            self.result = deepcopy(receipt)
        return {"allowed": True, "code": "executed"}, receipt

    def output(self, steps, termination, elapsed):
        if termination != "finished":
            self.procedure = self.stopping = False
            if termination in ("time_limit", "step_limit"):
                self.budgets = False
            self.outcome = {"decision": "stop", "reason": termination, "value": None, "unit": None}
        success = bool(self.finished and self.stopping and self.procedure and self.budgets
                       and self.outcome and self.outcome["decision"] == "success" and self.result is not None)
        checks = {"procedure_valid": bool(self.procedure), "budgets_respected": bool(self.budgets),
                  "stopping_valid": bool(self.stopping), "task_success": success,
                  "tool_valid": bool(self.tool_ok and self.valid_calls > 0),
                  "arguments_valid": bool(self.args_ok and self.valid_calls > 0),
                  "binding_valid": bool(self.binding_ok and self.binding_checks > 0),
                  "execution_valid": bool(self.valid_calls > 0 and self.procedure)}
        return {"schema_version": OUTPUT_VERSION, "steps": steps, "termination": termination,
                "elapsed_ms": elapsed, "checks": checks, "outcome": self.outcome,
                "usage": {"policy_steps": len(steps), "tool_call_attempts": self.attempts,
                          "tool_calls_executed": self.calls, "lookup_attempts": self.lookups},
                "tool_status_counts": {s: sum(o["status"] == s for o in self.observations) for s in ("ok", "controlled_error")}}


class ReplayPolicy:
    """Called after each actual observation; scripted control, not adaptation evidence."""
    def __init__(self, transport, case_id):
        self.transport, self.case_id, self.index = transport, case_id, 0

    def predict(self, projected):
        from .adapters import _envelope
        response = self.transport.predict({"case_id": self.case_id, "contract_id": CONTRACT, "input": projected})
        if response["status"] != "ok":
            return response
        program = response["output"]
        if (not isinstance(program, dict) or set(program) != {"actions"} or not isinstance(program["actions"], list)
                or len(program["actions"]) > 16):
            return _envelope("error", error="invalid_episode_control")
        if self.index >= len(program["actions"]):
            return _envelope("missing", error="episode_control_exhausted")
        action = deepcopy(program["actions"][self.index])
        self.index += 1
        return _envelope("ok", output=action)


def run_episode(task, policy, *, clock=None):
    validate_input(task)
    clock = clock or time.monotonic
    started = clock()
    state, runtime, steps = _State(task), EpisodeRuntime(task), []
    status, error, termination, last = "ok", None, "step_limit", 0.0
    def elapsed():
        nonlocal last
        value = (clock() - started) * 1000
        if not math.isfinite(value) or value < last:
            raise CaseError("tool-episode: nonmonotonic clock")
        last = value
        return value
    for index in range(task["budgets"]["max_steps"]):
        before = elapsed()
        if before > task["budgets"]["max_elapsed_ms"]:
            last, termination = before, "time_limit"
            break
        projected = state.projection(before, index)
        response = policy.predict(deepcopy(projected))
        after_policy = elapsed()
        status, error = response["status"], response["error"]
        proposal = response["output"]
        if status != "ok":
            guard, observation = {"allowed": False, "code": "candidate_" + status}, None
            state.procedure = False
        else:
            guard, observation = state.transition(proposal, after_policy, runtime=runtime)
        after_action = elapsed()
        step = {"index": index + 1, "elapsed_before_ms": before, "elapsed_after_policy_ms": after_policy,
                "elapsed_after_action_ms": after_action, "candidate_input": projected,
                "candidate_input_sha256": hashlib.sha256(canonical(projected)).hexdigest(),
                "policy_status": status, "proposal": deepcopy(proposal), "guard": guard, "observation": observation}
        steps.append(step)
        state.history.append({"proposal": deepcopy(proposal), "guard": deepcopy(guard)})
        last = after_action
        if status != "ok":
            termination = "time_limit" if after_action > task["budgets"]["max_elapsed_ms"] else "candidate_" + status
            break
        if after_action > task["budgets"]["max_elapsed_ms"]:
            termination = "time_limit"
            break
        if state.finished:
            termination = "finished"
            break
    return status, error, state.output(steps, termination, last)


def validate_receipt(task, output):
    """Check retained transitions; no tool, policy, timer or runtime is invoked."""
    validate_input(task)
    _object(output, {"schema_version", "steps", "termination", "elapsed_ms", "checks", "outcome", "usage", "tool_status_counts"}, "receipt")
    if output["schema_version"] != OUTPUT_VERSION or not isinstance(output["steps"], list) or len(output["steps"]) > task["budgets"]["max_steps"]:
        raise CaseError("tool-episode: invalid bounded transcript")
    state, last, terminal = _State(task), 0.0, None
    for index, step in enumerate(output["steps"]):
        _object(step, {"index", "elapsed_before_ms", "elapsed_after_policy_ms", "elapsed_after_action_ms",
                       "candidate_input", "candidate_input_sha256", "policy_status", "proposal", "guard", "observation"}, "step")
        times = [step[k] for k in ("elapsed_before_ms", "elapsed_after_policy_ms", "elapsed_after_action_ms")]
        if (terminal is not None or any(type(v) not in (int, float) or abs(v) > 10**12 or not math.isfinite(v) for v in times)
                or not last <= times[0] <= times[1] <= times[2] or times[0] > task["budgets"]["max_elapsed_ms"]
                or type(step["index"]) is not int or step["index"] != index + 1):
            raise CaseError("tool-episode: invalid timing/order")
        projected = state.projection(times[0], index)
        if (not typed_equal(step["candidate_input"], projected)
                or step["candidate_input_sha256"] != hashlib.sha256(canonical(projected)).hexdigest()):
            raise CaseError("tool-episode: actual input projection mismatch")
        status = step["policy_status"]
        if status not in ("ok", "unsupported", "missing", "error", "timeout", "abstain"):
            raise CaseError("tool-episode: invalid policy status")
        if status != "ok":
            guard, observation = {"allowed": False, "code": "candidate_" + status}, None
            state.procedure = False
            terminal = "time_limit" if times[2] > task["budgets"]["max_elapsed_ms"] else "candidate_" + status
        else:
            guard, observation = state.transition(step["proposal"], times[1], actual=step["observation"])
            if times[2] > task["budgets"]["max_elapsed_ms"]:
                terminal = "time_limit"
            elif state.finished:
                terminal = "finished"
        if not typed_equal(step["guard"], guard) or not typed_equal(step["observation"], observation):
            raise CaseError("tool-episode: guard/observation mismatch")
        state.history.append({"proposal": deepcopy(step["proposal"]), "guard": deepcopy(guard)})
        last = times[2]
    final = output["elapsed_ms"]
    if type(final) not in (int, float) or abs(final) > 10**12 or not math.isfinite(final) or final < last or terminal is not None and final != last:
        raise CaseError("tool-episode: invalid final timing")
    if terminal is None:
        if final > task["budgets"]["max_elapsed_ms"]:
            terminal = "time_limit"
        elif len(output["steps"]) == task["budgets"]["max_steps"]:
            terminal = "step_limit"
        else:
            raise CaseError("tool-episode: unexplained unfinished transcript")
    expected = state.output(output["steps"], terminal, final)
    if not typed_equal(output, expected):
        raise CaseError("tool-episode: retained outcome/counters mismatch")


class FixtureEpisodeAdapter:
    def __init__(self, profile, profile_path, recordings_data=None):
        from .adapters import RecordedAdapter, _identity
        self.transport = RecordedAdapter(profile, profile_path, recordings_data)
        self.capabilities = list(profile["capabilities"])
        self.provenance = deepcopy(self.transport.provenance)
        sources = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                   for name in ("adapters.py", "synthetic_tools.py", "tool_arguments.py", "tool_episodes.py")}
        self.provenance["adapter_sha256"] = _identity(sources)
        self.provenance["identity_sha256"] = _identity({"control_identity": self.transport.provenance["identity_sha256"], "runtime_sources": sources})

    def predict(self, request):
        from .adapters import _envelope, _request
        request = _request(request)
        if request["contract_id"] != CONTRACT:
            return _envelope("unsupported", error="unsupported_contract")
        status, error, output = run_episode(request["input"], ReplayPolicy(self.transport, request["case_id"]))
        if status != "ok":
            return _envelope(status, raw_output={"episode": output}, error=error)
        return _envelope("ok", output=output)


def summarize_metrics(cases, rows, results):
    selected = [case for case in cases if case["contract_id"] == CONTRACT]
    indexed, raw = {r["case_id"]: r for r in rows}, {r["case_id"]: r for r in results}
    def group(items):
        report = {"schema_version": METRICS_VERSION, "eligible_cases": len(items),
                  "scored_cases": sum(indexed[c["case_id"]]["scored"] for c in items),
                  "procedure_correct_cases": sum(indexed[c["case_id"]]["passed"] for c in items),
                  "cases_with_execution_trace": 0, "tool_calls_observed": 0,
                  "tool_call_attempts_observed": 0, "policy_steps_observed": 0,
                  "tool_status_counts": {"ok": 0, "controlled_error": 0},
                  **{stage + "_eligible_cases": 0 for stage in STAGES},
                  **{stage + "_correct_cases": 0 for stage in STAGES}}
        for case in items:
            success_eligible = expected_outcome(case["input"])["decision"] == "success"
            eligible = {stage: (success_eligible if stage in ("binding", "result") else
                       case["input"]["known_dataset_id"] is not None if stage in ("tool", "arguments", "execution") else True) for stage in STAGES}
            for stage in STAGES:
                report[stage + "_eligible_cases"] += eligible[stage]
            result = raw.get(case["case_id"], {})
            output = result.get("output") if result.get("status") == "ok" else (result.get("raw_output") or {}).get("episode") if isinstance(result.get("raw_output"), dict) else None
            try:
                retained = result.get("raw_output")
                if isinstance(retained, dict) and retained.get("schema_version") == "deposium.local-tool-model-trace/v1":
                    from .local_tool_policy import validate_trace
                    validate_trace(case, result)
                validate_receipt(case["input"], output)
            except (CaseError, TypeError, KeyError):
                continue
            report["cases_with_execution_trace"] += 1
            usage = output["usage"]
            report["tool_calls_observed"] += usage["tool_calls_executed"]
            report["tool_call_attempts_observed"] += usage["tool_call_attempts"]
            report["policy_steps_observed"] += usage["policy_steps"]
            for status in report["tool_status_counts"]:
                report["tool_status_counts"][status] += output["tool_status_counts"][status]
            if result.get("status") != "ok":
                continue
            flags = output["checks"]
            for stage in STAGES:
                flag = flags["task_success"] if stage == "result" else flags["stopping_valid"] if stage == "stopping" else flags["budgets_respected"] if stage == "budget" else flags[stage + "_valid"]
                report[stage + "_correct_cases"] += eligible[stage] and flag
        report["cases_without_execution_trace"] = len(items) - report["cases_with_execution_trace"]
        for stage in STAGES:
            n = report[stage + "_eligible_cases"]
            report[stage + "_over_all_eligible"] = report[stage + "_correct_cases"] / n if n else None
        report["task_success_cases"] = report["result_correct_cases"]
        report["task_success_eligible_cases"] = report["result_eligible_cases"]
        return report
    report = group(selected)
    report["by_language"] = {v: group([c for c in selected if c["language"] == v]) for v in sorted({c["language"] for c in selected})}
    report["by_split"] = {v: group([c for c in selected if c["split"] == v]) for v in sorted({c["split"] for c in selected})}
    return report
