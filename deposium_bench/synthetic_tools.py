"""Two bounded, local synthetic tools. Importing this module performs no work."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json


class ToolError(ValueError):
    """An independent fixture guard refused an operation."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode()


def validate_fixture(scope_id, dataset):
    def text(value):
        return (isinstance(value, str) and 0 < len(value) <= 128
                and value.strip() and not any(ord(c) < 32 for c in value))
    if not text(scope_id) or not isinstance(dataset, dict) or set(dataset) != {
            "dataset_id", "column", "unit", "values"}:
        raise ToolError("invalid_fixture")
    if not all(text(dataset[k]) for k in ("dataset_id", "column", "unit")):
        raise ToolError("invalid_fixture_text")
    if dataset["unit"] not in {"EUR", "USD", "kg", "m"}:
        raise ToolError("invalid_fixture_unit")
    values = dataset["values"]
    if (not isinstance(values, list) or not 1 <= len(values) <= 32
            or any(type(v) is not int or abs(v) > 10**9 for v in values)):
        raise ToolError("invalid_fixture_values")


def artifact_id(task_input):
    """Public content-addressing rule; this computes an ID, not a tool call."""
    validate_fixture(task_input["scope_id"], task_input["dataset"])
    payload = {"scope_id": task_input["scope_id"], "dataset": task_input["dataset"]}
    return "artifact:" + hashlib.sha256(canonical(payload)).hexdigest()


class FixtureStore:
    """Case-local artifact store; no filesystem, network, code evaluation or RNG."""
    def __init__(self, task_input, max_calls=2):
        validate_fixture(task_input["scope_id"], task_input["dataset"])
        if type(max_calls) is not int or not 1 <= max_calls <= 8:
            raise ToolError("invalid_call_budget")
        self.task = deepcopy(task_input)
        self.max_calls, self.calls, self.trace = max_calls, 0, []
        self.artifacts = {}

    def _admit(self):
        if self.calls >= self.max_calls:
            raise ToolError("call_budget_exhausted")
        self.calls += 1

    def lookup(self):
        self._admit()
        data = self.task["dataset"]
        artifact = {"artifact_id": artifact_id(self.task), "scope_id": self.task["scope_id"],
                    **deepcopy(data)}
        self.artifacts[artifact["artifact_id"]] = artifact
        receipt = {"tool_id": "fixture.lookup", "tool_call": self.calls, "status": "ok",
                   "arguments": {"dataset_id": data["dataset_id"], "scope_id": self.task["scope_id"]},
                   "artifact": deepcopy(artifact)}
        self.trace.append(receipt)
        return deepcopy(receipt)

    def sum(self, arguments):
        if not isinstance(arguments, dict) or set(arguments) != {"artifact_id", "column", "unit", "scope_id"}:
            raise ToolError("invalid_arguments")
        if any(not isinstance(v, str) for v in arguments.values()):
            raise ToolError("invalid_argument_type")
        artifact = self.artifacts.get(arguments["artifact_id"])
        if artifact is None:
            raise ToolError("artifact_binding_mismatch")
        if arguments["scope_id"] != self.task["scope_id"] or artifact["scope_id"] != self.task["scope_id"]:
            raise ToolError("scope_mismatch")
        if arguments["column"] != artifact["column"] or arguments["unit"] != artifact["unit"]:
            raise ToolError("column_or_unit_mismatch")
        self._admit()
        value = 0
        for number in artifact["values"]:
            value += number
        receipt = {"tool_id": "fixture.sum", "tool_call": self.calls, "status": "ok",
                   "arguments": deepcopy(arguments), "value": value, "unit": artifact["unit"]}
        self.trace.append(receipt)
        return deepcopy(receipt)
