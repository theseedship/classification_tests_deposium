"""Typed exact assertions and coverage accounting; no external judge or model."""

from __future__ import annotations

import re
from typing import Any

from .cases import CaseError, _empty, _json, pointer_tokens, typed_equal, validate_cases

SCORER_VERSION = "deposium.exact/v1"
STATUSES = ("ok", "unsupported", "missing", "error", "timeout", "abstain")


def _resolve(output: Any, pointer: str) -> Any:
    value = output
    for token in pointer_tokens(pointer):
        if isinstance(value, dict):
            if token not in value:
                raise KeyError(token)
            value = value[token]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", token):
            # An index longer than the array length cannot resolve. Bound the
            # conversion as well, so arbitrarily long valid pointers fail cleanly.
            if len(token) > len(str(len(value))):
                raise IndexError(token)
            value = value[int(token)]
        else:
            raise KeyError(token)
    return value


def score_case(case: dict, result: dict) -> dict:
    """Score ok/abstain, keeping execution failures outside the scored denominator."""
    validate_cases([case])
    if not isinstance(result, dict) or result.get("status") not in STATUSES:
        raise ValueError("result: unknown status")
    if "case_id" in result and result["case_id"] != case["case_id"]:
        raise ValueError("result: mismatching case_id")
    status = result["status"]
    if status not in {"ok", "abstain"}:
        return {"scored": False, "passed": False, "checks": [], "reason": status}
    if status == "abstain":
        allowed = case["reference"]["abstention_allowed"]
        return {"scored": True, "passed": allowed, "checks": [],
                "reason": "allowed_abstention" if allowed else "forbidden_abstention"}
    output = result.get("output")
    try:
        _json(output)
    except CaseError:
        return {"scored": True, "passed": False, "checks": [], "reason": "invalid_json_output"}
    if _empty(output):
        return {"scored": True, "passed": False, "checks": [], "reason": "empty_output"}
    if case["contract_id"] == "bench.tool-arguments":
        from .tool_arguments import validate_receipt
        try:
            validate_receipt(case["input"], output)
        except (CaseError, KeyError, TypeError):
            return {"scored": True, "passed": False, "checks": [], "reason": "invalid_tool_arguments_receipt"}
    if case["contract_id"] == "bench.tool-discovery":
        from .tool_discovery import score_output
        return score_output(case, output)
    checks = []
    for assertion in case["reference"]["assertions"]:
        try:
            actual = _resolve(output, assertion["path"])
        except (KeyError, IndexError):
            checks.append({"path": assertion["path"], "passed": False, "reason": "missing_path"})
            continue
        expected = assertion["value"]
        operation = assertion["op"]
        if operation == "equals":
            passed = typed_equal(actual, expected)
        elif operation == "one_of":
            passed = any(typed_equal(actual, option) for option in expected)
        else:
            passed = (isinstance(actual, list) and len(actual) == len(expected)
                      and all(any(typed_equal(item, option) for option in actual) for item in expected)
                      and not any(typed_equal(a, b) for i, a in enumerate(actual)
                                  for b in actual[i + 1:]))
        checks.append({"path": assertion["path"], "passed": passed,
                       "reason": "matched" if passed else "mismatch"})
    passed = all(check["passed"] for check in checks)
    return {"scored": True, "passed": passed, "checks": checks,
            "reason": "all_assertions_matched" if passed else "assertion_failed"}


def _counts(rows: list[dict]) -> dict:
    total = len(rows)
    scored = sum(row["scored"] for row in rows)
    passed = sum(row["passed"] for row in rows)
    return {"total_cases": total, "scored_cases": scored, "passed_cases": passed,
            "failed_cases": scored - passed,
            "counts_by_status": {status: sum(row["status"] == status for row in rows)
                                 for status in STATUSES},
            "accuracy_over_all": passed / total if total else None,
            "accuracy_scored": passed / scored if scored else None,
            "coverage": scored / total if total else 0.0,
            "verdict": "invalid" if scored == 0 else "pass" if passed == total else "fail"}


def summarize(cases: list[dict], results: list[dict]) -> dict:
    """Join by identity, synthesize missing rows, and show every denominator."""
    validate_cases(cases)
    if not isinstance(results, list):
        raise ValueError("results: expected list")
    known = {case["case_id"] for case in cases}
    indexed = {}
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get("case_id"), str):
            raise ValueError("result: missing case_id")
        identity = result["case_id"]
        if identity not in known or identity in indexed:
            raise ValueError("results: unknown or duplicate case_id")
        if result.get("status") not in STATUSES:
            raise ValueError("result: unknown status")
        indexed[identity] = result
    rows = []
    for case in cases:
        result = indexed.get(case["case_id"], {"status": "missing", "output": None,
                                               "raw_output": None, "error": None})
        rows.append({"case_id": case["case_id"], "pack": case["pack"],
                     "language": case["language"], "status": result["status"],
                     **score_case(case, result)})
    report = {**_counts(rows),
            "by_pack": {pack: _counts([row for row in rows if row["pack"] == pack])
                        for pack in sorted({row["pack"] for row in rows})},
            "by_language": {language: _counts([row for row in rows if row["language"] == language])
                            for language in sorted({row["language"] for row in rows})},
            "rows": rows}
    if any(case["contract_id"] == "bench.tool-discovery" for case in cases):
        from .tool_discovery import CONTRACT, summarize_metrics
        report["task_metrics"] = {CONTRACT: summarize_metrics(cases, rows)}
    if any(case["contract_id"] == "bench.tool-arguments" for case in cases):
        from .tool_arguments import CONTRACT, summarize_metrics
        report.setdefault("task_metrics", {})[CONTRACT] = summarize_metrics(cases, rows, results)
    return report
