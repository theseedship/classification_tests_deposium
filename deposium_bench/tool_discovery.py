"""Bounded tool discovery and set metrics; no tools or models execute here.

Catalogue eligibility/availability are fixture facts, independent of candidate
predictions. Exact choice tasks keep their existing scorer. This native task
adds unordered-set semantics and explicit diagnostic denominators to that engine.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction

from .cases import CaseError

CONTRACT = "bench.tool-discovery"
INPUT_VERSION = "deposium.tool-discovery-input/v1"
OUTPUT_VERSION = "deposium.tool-discovery-output/v1"
METRICS_VERSION = "deposium.tool-discovery-metrics/v1"
RATIOS = ("shortlist_recall", "shortlist_precision", "final_recall", "final_precision")


def _object(value, fields, where):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise CaseError(f"tool-discovery {where}: missing or unknown fields")


def _text(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 8192
            or any(ord(c) < 32 for c in value)):
        raise CaseError("tool-discovery: expected bounded non-empty text")


def _ids(value, limit, where):
    if not isinstance(value, list) or len(value) > limit:
        raise CaseError(f"tool-discovery {where}: expected bounded ID list")
    for item in value:
        _text(item)
    if len(value) != len(set(value)):
        raise CaseError(f"tool-discovery {where}: duplicate IDs")


def validate_input(value):
    _object(value, {"schema_version", "request", "catalogue", "shortlist_limit"}, "input")
    if value["schema_version"] != INPUT_VERSION:
        raise CaseError("tool-discovery: unsupported input version")
    _text(value["request"])
    if type(value["shortlist_limit"]) is not int or not 1 <= value["shortlist_limit"] <= 8:
        raise CaseError("tool-discovery: invalid shortlist limit")
    catalogue = value["catalogue"]
    if not isinstance(catalogue, list) or not 1 <= len(catalogue) <= 32:
        raise CaseError("tool-discovery: invalid catalogue size")
    plugin_ids, capability_ids, tool_ids, owners = set(), set(), set(), {}
    for tool in catalogue:
        _object(tool, {"plugin_id", "capability_id", "tool_id", "description",
                       "eligible", "available"}, "catalogue entry")
        for field in ("plugin_id", "capability_id", "tool_id", "description"):
            _text(tool[field])
        if type(tool["eligible"]) is not bool or type(tool["available"]) is not bool:
            raise CaseError("tool-discovery: eligibility and availability must be booleans")
        if tool["tool_id"] in tool_ids:
            raise CaseError("tool-discovery: duplicate tool ID")
        if owners.get(tool["capability_id"], tool["plugin_id"]) != tool["plugin_id"]:
            raise CaseError("tool-discovery: capability belongs to different plugins")
        owners[tool["capability_id"]] = tool["plugin_id"]
        plugin_ids.add(tool["plugin_id"])
        capability_ids.add(tool["capability_id"])
        tool_ids.add(tool["tool_id"])
    if plugin_ids & capability_ids or plugin_ids & tool_ids or capability_ids & tool_ids:
        raise CaseError("tool-discovery: plugin, capability and tool namespaces overlap")


def _selection(value, task_input):
    _object(value, {"decision", "tool_ids", "reason"}, "selection")
    if value["decision"] not in ("select", "clarify", "no_suitable"):
        raise CaseError("tool-discovery: unknown semantic decision")
    _ids(value["tool_ids"], task_input["shortlist_limit"], "selected tools")
    tools = {tool["tool_id"]: tool for tool in task_input["catalogue"]}
    for identity in value["tool_ids"]:
        if identity not in tools or not tools[identity]["eligible"] or not tools[identity]["available"]:
            raise CaseError("tool-discovery: unknown, forbidden or unavailable tool")
    if value["decision"] == "select":
        if value["reason"] != "ready" or not value["tool_ids"]:
            raise CaseError("tool-discovery: selection requires a non-empty ready set")
    elif value["tool_ids"]:
        raise CaseError("tool-discovery: nonselection must not propose tools")
    elif value["decision"] == "clarify":
        if value["reason"] != "missing_information":
            raise CaseError("tool-discovery: clarification requires missing information")
    elif value["reason"] not in ("no_capability", "unavailable"):
        raise CaseError("tool-discovery: invalid no-suitable reason")


def validate_output(value, task_input):
    validate_input(task_input)
    _object(value, {"schema_version", "shortlist", "selection"}, "output")
    if value["schema_version"] != OUTPUT_VERSION:
        raise CaseError("tool-discovery: unsupported output version")
    _ids(value["shortlist"], task_input["shortlist_limit"], "shortlist")
    tools = {tool["tool_id"]: tool for tool in task_input["catalogue"]}
    for identity in value["shortlist"]:
        if identity not in tools or not tools[identity]["eligible"] or not tools[identity]["available"]:
            raise CaseError("tool-discovery: unknown, forbidden or unavailable shortlist tool")
    _selection(value["selection"], task_input)
    if not set(value["selection"]["tool_ids"]) <= set(value["shortlist"]):
        raise CaseError("tool-discovery: final tools must be shortlisted")


def alternatives(case):
    return case["reference"]["assertions"][0]["value"]


def validate_case(case):
    validate_input(case["input"])
    reference = case["reference"]
    assertions = reference["assertions"]
    if (reference["abstention_allowed"] or len(assertions) != 1
            or assertions[0]["path"] != "/selection" or assertions[0]["op"] != "one_of"):
        raise CaseError("tool-discovery: expected alternative selection oracle")
    options = alternatives(case)
    decisions, reasons, sets = set(), set(), []
    for option in options:
        _selection(option, case["input"])
        decisions.add(option["decision"])
        reasons.add(option["reason"])
        sets.append(frozenset(option["tool_ids"]))
    if len(decisions) != 1 or len(reasons) != 1:
        raise CaseError("tool-discovery: alternatives must share one semantic outcome")
    if len(sets) != len(set(sets)) or any(a < b for a in sets for b in sets):
        raise CaseError("tool-discovery: alternatives must be unique minimal sets")
    if "unavailable" in reasons and not any(not tool["available"] for tool in case["input"]["catalogue"]):
        raise CaseError("tool-discovery: unavailable reference lacks unavailable catalogue entry")


def _overlap(predicted, allowed):
    """Best recall, then precision, then lexicographic IDs; never a gold union."""
    predicted = set(predicted)
    candidates = [set(option["tool_ids"]) for option in allowed]
    def key(target):
        hit = len(predicted & target)
        return (-Fraction(hit, len(target)),
                -Fraction(hit, len(predicted)) if predicted else Fraction(0), tuple(sorted(target)))
    target = min(candidates, key=key)
    hit = len(predicted & target)
    return hit / len(target), hit / len(predicted) if predicted else 0.0, len(predicted) - hit


def score_output(case, output):
    try:
        validate_output(output, case["input"])
    except CaseError:
        return {"scored": True, "passed": False,
                "checks": [{"path": "", "passed": False, "reason": "mismatch"}],
                "reason": "invalid_tool_discovery_output"}
    allowed = alternatives(case)
    gold = allowed[0]
    selected = output["selection"]
    eligible = gold["decision"] == "select"
    metric = {"schema_version": METRICS_VERSION, "eligible_select": eligible,
              "shortlist_limit": case["input"]["shortlist_limit"],
              "shortlist_size": len(output["shortlist"]), "final_size": len(selected["tool_ids"]),
              **{name: None for name in RATIOS}, "final_sufficient": None,
              "final_minimal": None, "unnecessary_tools": None}
    outcome = selected["decision"] == gold["decision"] and selected["reason"] == gold["reason"]
    minimal = set(selected["tool_ids"]) in [set(a["tool_ids"]) for a in allowed]
    if eligible:
        recall, precision, _ = _overlap(output["shortlist"], allowed)
        final_recall, final_precision, unnecessary = _overlap(selected["tool_ids"], allowed)
        sufficient = any(set(a["tool_ids"]) <= set(selected["tool_ids"]) for a in allowed)
        metric.update(shortlist_recall=recall, shortlist_precision=precision,
                      final_recall=final_recall, final_precision=final_precision,
                      final_sufficient=outcome and sufficient, final_minimal=outcome and minimal,
                      unnecessary_tools=unnecessary)
    passed = outcome and minimal
    return {"scored": True, "passed": passed,
            "checks": [{"path": "/selection", "passed": passed,
                        "reason": "matched" if passed else "mismatch"}],
            "reason": "tool_discovery_matched" if passed else "tool_discovery_mismatch",
            "task_metrics": metric}


def _aggregate(cases, rows):
    indexed = {row["case_id"]: row for row in rows}
    eligible = [c for c in cases if alternatives(c)[0]["decision"] == "select"]
    metrics = [indexed[c["case_id"]].get("task_metrics") for c in eligible]
    observed = [metric for metric in metrics if metric is not None]
    n, count = len(eligible), len(observed)
    report = {"schema_version": METRICS_VERSION, "level": "tool_id",
              "total_cases": len(cases), "scored_cases": sum(indexed[c["case_id"]]["scored"] for c in cases),
              "eligible_select_cases": n, "observed_select_cases": count,
              "shortlist_limits": dict(sorted(Counter(str(c["input"]["shortlist_limit"]) for c in cases).items()))}
    for name in RATIOS:
        numerator = sum(metric[name] for metric in observed)
        report[name + "_sum"] = numerator
        report[name + "_over_all_eligible"] = numerator / n if n else None
    for name in ("final_sufficient", "final_minimal"):
        passed = sum(metric[name] for metric in observed)
        report[name + "_cases"] = passed
        report[name + "_over_all_eligible"] = passed / n if n else None
    unnecessary = sum(metric["unnecessary_tools"] for metric in observed)
    report.update(unnecessary_tools_sum=unnecessary,
                  unnecessary_tools_mean_observed=unnecessary / count if count else None)
    return report


def summarize_metrics(cases, rows):
    selected = [case for case in cases if case["contract_id"] == CONTRACT]
    report = _aggregate(selected, rows)
    report["by_language"] = {language: _aggregate([c for c in selected if c["language"] == language], rows)
                             for language in sorted({c["language"] for c in selected})}
    report["by_split"] = {split: _aggregate([c for c in selected if c["split"] == split], rows)
                          for split in sorted({c["split"] for c in selected})}
    return report
