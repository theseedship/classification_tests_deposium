"""Controlled argument execution adapter and pure archived-receipt validation."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

from .cases import CaseError, typed_equal
from .synthetic_tools import FixtureStore, ToolError, artifact_id, canonical, validate_fixture

CONTRACT = "bench.tool-arguments"
INPUT_VERSION = "deposium.tool-arguments-input/v1"
OUTPUT_VERSION = "deposium.tool-arguments-output/v1"
PROJECTION_VERSION = "deposium.tool-arguments-candidate-input/v1"
METRICS_VERSION = "deposium.tool-arguments-metrics/v1"
STAGES = ("tool", "arguments", "binding", "execution", "result")
STAGE_PATHS = {"tool": {"/checks/tool_selected"}, "arguments": {"/checks/arguments_valid"},
               "binding": {"/checks/binding_valid"},
               "execution": {"/execution/executed", "/execution/status"},
               "result": {"/execution/value", "/execution/unit"}}


def validate_input(value):
    if not isinstance(value, dict) or set(value) != {"schema_version", "request", "scope_id", "dataset"}:
        raise CaseError("tool-arguments: invalid input fields")
    if value["schema_version"] != INPUT_VERSION:
        raise CaseError("tool-arguments: invalid input version")
    request = value["request"]
    if (not isinstance(request, str) or not request.strip() or len(request) > 8192
            or any(ord(c) < 32 for c in request)):
        raise CaseError("tool-arguments: invalid request")
    try:
        validate_fixture(value["scope_id"], value["dataset"])
    except ToolError as exc:
        raise CaseError("tool-arguments: " + str(exc)) from None


def expected_lookup(task):
    """Pure consistency reconstruction; never calls an executable tool."""
    return {"tool_id": "fixture.lookup", "tool_call": 1, "status": "ok",
            "arguments": {"dataset_id": task["dataset"]["dataset_id"], "scope_id": task["scope_id"]},
            "artifact": {"artifact_id": artifact_id(task), "scope_id": task["scope_id"], **deepcopy(task["dataset"])}}


def candidate_input(task, lookup):
    return {"schema_version": PROJECTION_VERSION, "request": task["request"],
            "scope_id": task["scope_id"],
            "tool_schema": {"tool_id": "fixture.sum", "arguments": {
                "artifact_id": "string", "column": "string", "unit": "string", "scope_id": "string"}},
            "observation": deepcopy(lookup)}


def proposal_checks(proposal, task, lookup):
    flags = {"tool_selected": False, "arguments_valid": False, "binding_valid": False}
    if not isinstance(proposal, dict) or set(proposal) != {"tool_id", "arguments"}:
        return flags
    flags["tool_selected"] = proposal["tool_id"] == "fixture.sum"
    args = proposal["arguments"]
    if (not flags["tool_selected"] or not isinstance(args, dict)
            or set(args) != {"artifact_id", "column", "unit", "scope_id"}
            or any(not isinstance(v, str) or not v or len(v) > 128 for v in args.values())):
        return flags
    flags["arguments_valid"] = (args["scope_id"] == task["scope_id"]
                                and args["column"] == task["dataset"]["column"]
                                and args["unit"] == task["dataset"]["unit"])
    flags["binding_valid"] = args["artifact_id"] == lookup["artifact"]["artifact_id"]
    return flags


def validate_case(case):
    validate_input(case["input"])
    expected = {"/checks/tool_selected": True, "/checks/arguments_valid": True,
                "/checks/binding_valid": True, "/execution/executed": True,
                "/execution/status": "ok", "/execution/value": sum(case["input"]["dataset"]["values"]),
                "/execution/unit": case["input"]["dataset"]["unit"]}
    assertions = case["reference"]["assertions"]
    if (case["reference"]["abstention_allowed"] or len(assertions) != len(expected)
            or any(a["op"] != "equals" or a["path"] not in expected
                   or not typed_equal(a["value"], expected[a["path"]]) for a in assertions)
            or {a["path"] for a in assertions} != set(expected)):
        raise CaseError("tool-arguments: incomplete or inconsistent fixed result oracle")


def validate_diagnostic(task, value):
    if not isinstance(value, dict) or set(value) != {"candidate_input", "candidate_input_sha256", "trace"}:
        raise CaseError("tool-arguments: invalid retained diagnostic")
    lookup = expected_lookup(task)
    projected = candidate_input(task, lookup)
    if (not typed_equal(value["candidate_input"], projected)
            or value["candidate_input_sha256"] != hashlib.sha256(canonical(projected)).hexdigest()
            or not typed_equal(value["trace"], [lookup])):
        raise CaseError("tool-arguments: inconsistent lookup/projection diagnostic")


def validate_receipt(task, output):
    validate_input(task)
    if not isinstance(output, dict) or set(output) != {
            "schema_version", "candidate_input", "candidate_input_sha256", "proposal", "checks", "execution", "trace"}:
        raise CaseError("tool-arguments: invalid execution output fields")
    if output["schema_version"] != OUTPUT_VERSION:
        raise CaseError("tool-arguments: invalid execution version")
    lookup = expected_lookup(task)
    projected = candidate_input(task, lookup)
    if (not typed_equal(output["candidate_input"], projected)
            or output["candidate_input_sha256"] != hashlib.sha256(canonical(projected)).hexdigest()):
        raise CaseError("tool-arguments: projection mismatch")
    flags = proposal_checks(output["proposal"], task, lookup)
    if not typed_equal(output["checks"], flags):
        raise CaseError("tool-arguments: guard result mismatch")
    if all(flags.values()):
        receipt = {"tool_id": "fixture.sum", "tool_call": 2, "status": "ok",
                   "arguments": deepcopy(output["proposal"]["arguments"]),
                   "value": sum(task["dataset"]["values"]), "unit": task["dataset"]["unit"]}
        execution = {"executed": True, "status": "ok", "value": receipt["value"], "unit": receipt["unit"]}
        trace = [lookup, receipt]
    else:
        execution = {"executed": False, "status": "blocked", "value": None, "unit": None}
        trace = [lookup]
    if not typed_equal(output["execution"], execution) or not typed_equal(output["trace"], trace):
        raise CaseError("tool-arguments: execution receipt mismatch")


class FixtureArgumentsAdapter:
    """A proposal replay around two genuinely executed local fixture functions."""
    def __init__(self, profile, profile_path, recordings_data=None):
        from .adapters import RecordedAdapter, _identity
        self.control = RecordedAdapter(profile, profile_path, recordings_data)
        self.capabilities = list(profile["capabilities"])
        self.provenance = deepcopy(self.control.provenance)
        sources = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                   for name in ("adapters.py", "synthetic_tools.py", "tool_arguments.py")}
        # This is the reviewed Python adapter/runtime closure, not a single file.
        self.provenance["adapter_sha256"] = _identity(sources)
        self.provenance["identity_sha256"] = _identity({
            "control_identity": self.control.provenance["identity_sha256"], "runtime_sources": sources})

    def predict(self, request):
        from .adapters import _envelope, _request
        request = _request(request)
        if request["contract_id"] != CONTRACT:
            return _envelope("unsupported", error="unsupported_contract")
        task = request["input"]
        validate_input(task)
        store = FixtureStore(task)
        lookup = store.lookup()
        projected = candidate_input(task, lookup)
        projection_hash = hashlib.sha256(canonical(projected)).hexdigest()
        response = self.control.predict({"case_id": request["case_id"], "contract_id": CONTRACT, "input": projected})
        diagnostic = {"candidate_input": projected, "candidate_input_sha256": projection_hash,
                      "trace": deepcopy(store.trace)}
        if response["status"] != "ok":
            return _envelope(response["status"], raw_output=diagnostic, error=response["error"])
        proposal = response["output"]
        flags = proposal_checks(proposal, task, lookup)
        execution = {"executed": False, "status": "blocked", "value": None, "unit": None}
        if all(flags.values()):
            result = store.sum(proposal["arguments"])
            execution = {"executed": True, "status": result["status"], "value": result["value"], "unit": result["unit"]}
        output = {"schema_version": OUTPUT_VERSION, "candidate_input": projected,
                  "candidate_input_sha256": projection_hash, "proposal": deepcopy(proposal),
                  "checks": flags, "execution": execution, "trace": deepcopy(store.trace)}
        return _envelope("ok", output=output, raw_output=deepcopy(proposal))


def summarize_metrics(cases, rows, results):
    selected = [case for case in cases if case["contract_id"] == CONTRACT]
    indexed = {row["case_id"]: row for row in rows}
    raw = {row["case_id"]: row for row in results}
    def group(items):
        report = {"schema_version": METRICS_VERSION, "eligible_cases": len(items),
                  "scored_cases": sum(indexed[c["case_id"]]["scored"] for c in items),
                  "cases_with_execution_trace": 0, "tool_calls_observed": 0}
        for stage in STAGES:
            report[stage + "_correct_cases"] = 0
        for case in items:
            row = indexed[case["case_id"]]
            checks = {c["path"]: c["passed"] for c in row["checks"]}
            for stage, paths in STAGE_PATHS.items():
                report[stage + "_correct_cases"] += all(checks.get(path, False) for path in paths)
            result = raw.get(case["case_id"], {})
            output = result.get("output")
            try:
                if result.get("status") == "ok":
                    validate_receipt(case["input"], output)
                    calls = len(output["trace"])
                else:
                    validate_diagnostic(case["input"], result.get("raw_output"))
                    calls = 1
            except (CaseError, KeyError, TypeError):
                continue
            report["cases_with_execution_trace"] += 1
            report["tool_calls_observed"] += calls
        report["cases_without_execution_trace"] = len(items) - report["cases_with_execution_trace"]
        for stage in STAGES:
            report[stage + "_over_all_eligible"] = report[stage + "_correct_cases"] / len(items) if items else None
        return report
    report = group(selected)
    report["by_language"] = {v: group([c for c in selected if c["language"] == v]) for v in sorted({c["language"] for c in selected})}
    report["by_split"] = {v: group([c for c in selected if c["split"] == v]) for v in sorted({c["split"] for c in selected})}
    return report
