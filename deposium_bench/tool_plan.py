"""Experimental bounded plan contract; no tool execution or model transport.

Only the recorded harness control is qualified for this contract. References
use the shared typed exact scorer, including complete alternative outputs.
"""
from __future__ import annotations

from .cases import CaseError, typed_equal

CONTRACT = "bench.tool-plan"
INPUT_VERSION = "deposium.tool-plan-input/v1"
OUTPUT_VERSION = "deposium.tool-plan-output/v1"
MAX_TEXT_CHARS = 8192
MAX_CATALOGUE_TOOLS = 32
MAX_ARGUMENTS = 16
MAX_ENUM_VALUES = 32
MAX_CALLS = 2


def _object(value, fields, where):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise CaseError(f"tool-plan {where}: missing or unknown fields")


def _text(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT_CHARS
            or any(ord(c) < 32 for c in value)):
        raise CaseError("tool-plan: expected bounded non-empty text")


def validate_input(value):
    """Validate the task envelope, not application permissions or semantics."""
    _object(value, {"schema_version", "request", "catalogue", "max_calls"}, "input")
    if value["schema_version"] != INPUT_VERSION:
        raise CaseError("tool-plan: unsupported input version")
    _text(value["request"])
    if type(value["max_calls"]) is not int or not 1 <= value["max_calls"] <= MAX_CALLS:
        raise CaseError("tool-plan: invalid call budget")
    catalogue = value["catalogue"]
    if not isinstance(catalogue, list) or not 1 <= len(catalogue) <= MAX_CATALOGUE_TOOLS:
        raise CaseError("tool-plan: expected bounded non-empty catalogue")
    ids = set()
    for tool in catalogue:
        _object(tool, {"tool_id", "description", "arguments", "output_type"}, "tool")
        for field in ("tool_id", "description", "output_type"):
            _text(tool[field])
        if tool["tool_id"] in ids:
            raise CaseError("tool-plan: duplicate tool identity")
        ids.add(tool["tool_id"])
        if not isinstance(tool["arguments"], dict) or len(tool["arguments"]) > MAX_ARGUMENTS:
            raise CaseError("tool-plan: arguments must be a bounded object")
        for name, spec in tool["arguments"].items():
            _text(name)
            if not isinstance(spec, dict):
                raise CaseError("tool-plan: invalid argument specification")
            if spec.get("type") == "enum":
                _object(spec, {"type", "values"}, "enum argument")
                values = spec["values"]
                if not isinstance(values, list) or not 1 <= len(values) <= MAX_ENUM_VALUES:
                    raise CaseError("tool-plan: invalid argument domain size")
                for item in values:
                    _text(item)
                if len(set(values)) != len(values):
                    raise CaseError("tool-plan: duplicate argument value")
            elif spec.get("type") == "artifact_ref":
                _object(spec, {"type", "artifact_type"}, "artifact argument")
                _text(spec["artifact_type"])
            else:
                raise CaseError("tool-plan: unsupported argument domain")


def validate_output(value, task_input):
    """Check canonical typed proposals and earlier-artifact bindings only.

    Valid structure is insufficient for a passing decision: the shared exact
    oracle additionally checks the complete proposal against fixed alternatives.
    All tools here are synthetic descriptions, never executable handles.
    """
    validate_input(task_input)
    _object(value, {"schema_version", "decision", "calls", "result_artifact_id"}, "output")
    if value["schema_version"] != OUTPUT_VERSION or value["decision"] != "propose":
        raise CaseError("tool-plan: expected a proposal, not execution success")
    calls = value["calls"]
    if not isinstance(calls, list) or not 1 <= len(calls) <= task_input["max_calls"]:
        raise CaseError("tool-plan: invalid number of calls")
    tools = {tool["tool_id"]: tool for tool in task_input["catalogue"]}
    artifacts = {}
    for index, call in enumerate(calls, 1):
        _object(call, {"tool_id", "arguments", "output_artifact_id"}, "call")
        if not isinstance(call["tool_id"], str) or call["tool_id"] not in tools:
            raise CaseError("tool-plan: unknown tool")
        tool = tools[call["tool_id"]]
        args = call["arguments"]
        _object(args, tool["arguments"], "call arguments")
        for name, spec in tool["arguments"].items():
            argument = args[name]
            if spec["type"] == "enum":
                if not any(typed_equal(argument, item) for item in spec["values"]):
                    raise CaseError("tool-plan: argument outside declared domain")
            elif not isinstance(argument, str) or artifacts.get(argument) != spec["artifact_type"]:
                raise CaseError("tool-plan: invalid or forward artifact binding")
        # Canonical names avoid penalizing arbitrary alpha-renaming. Broader
        # unordered/commutative plans need a new, reviewed semantic oracle.
        artifact_id = f"a{index}"
        if call["output_artifact_id"] != artifact_id:
            raise CaseError("tool-plan: output artifacts must use canonical a1, a2, ... IDs")
        artifacts[artifact_id] = tool["output_type"]
    if value["result_artifact_id"] != f"a{len(calls)}":
        raise CaseError("tool-plan: result must bind the last proposed artifact")


def validate_case(case):
    validate_input(case["input"])
    reference = case["reference"]
    assertions = reference["assertions"]
    if (reference["abstention_allowed"] or len(assertions) != 1
            or assertions[0]["path"] != "" or assertions[0]["op"] != "one_of"):
        raise CaseError("tool-plan: expected complete alternative-output oracle")
    for output in assertions[0]["value"]:
        validate_output(output, case["input"])
