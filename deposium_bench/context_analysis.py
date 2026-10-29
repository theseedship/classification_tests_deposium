"""Descriptive context analysis of sealed byte snapshots; no inference or threshold fit."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import math
from pathlib import Path
import statistics

from . import campaigns
from .scoring import STATUSES, summarize

DIMENSIONS = ("domain", "language", "difficulty", "target", "position", "order", "split",
              "benchmark_pack", "task_type", "use_case", "catalogue_variant")
OVERFLOW_ERRORS = {"julia_context_overflow", "julia_head_overflow", "julia_option_overflow",
                   "gliner_context_overflow", "decision2_context_overflow", "noma_context_overflow", "laya_context_overflow",
                   "indecis_context_overflow", "indecis_option_overflow", "small_model_context_overflow",
                   "muose_context_overflow", "modernjev_context_overflow"}


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def _target_order(value):
    return int(value) if value.isdecimal() else 0


def _stats(values: list) -> dict:
    numbers = sorted(number for value in values if (number := _number(value)) is not None)
    count = len(numbers)
    return {"count": count, "min": numbers[0] if count else None,
            "median": statistics.median(numbers) if count else None,
            "p95": numbers[math.ceil(.95 * count) - 1] if count else None,
            "max": numbers[-1] if count else None,
            "interpretation": "exploratory descriptive observations; no repeated-run or tail guarantee"}


def _measurements(record: dict | None) -> dict:
    raw = record.get("raw_output") if record else None
    raw = raw if isinstance(raw, dict) else {}
    timings = raw.get("timings") if isinstance(raw.get("timings"), dict) else {}
    encoding = raw.get("encoding_info") if isinstance(raw.get("encoding_info"), dict) else {}
    tokens = raw.get("token_components") if isinstance(raw.get("token_components"), dict) else {}
    usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
    native = raw.get("native_result") if isinstance(raw.get("native_result"), dict) else {}
    native_usage = native.get("usage") if isinstance(native.get("usage"), dict) else {}
    native_truncated = raw.get("native_usage_truncated")
    if type(native_truncated) is not bool:
        native_truncated = native_usage.get("truncated")
    return {"http_attempted": raw.get("http_attempted") if type(raw.get("http_attempted")) is bool else None,
            "cached_failure": raw.get("cached_failure") if type(raw.get("cached_failure")) is bool else None,
            "http_ms": _number(raw.get("http_ms")),
            "provider_input_tokens": _number(usage.get("input_tokens")),
            "provider_output_tokens": _number(usage.get("output_tokens")),
            "adapter_duration_ms": record["duration_ms"] if record else None,
            "decision_ms": _number(raw.get("decision_ms", timings.get("decision_ms"))),
            "inference_ms": _number(raw.get("inference_ms")),
            "native_tokens": _number(encoding.get("tokens")),
            "native_padded_tokens": _number(tokens.get("padded", tokens.get("padded_tokens"))),
            "rss_mib": _number(raw.get("rss_mb")),
            "forward_executed": raw.get("forward_executed") if type(raw.get("forward_executed")) is bool else None,
            "native_usage_truncated": native_truncated if type(native_truncated) is bool else None,
            "state_truncated": encoding.get("stateTruncated"),
            "options_truncated": encoding.get("optionsTruncated")}


def _provider_usage(measurements: list[dict]) -> dict:
    """Post-hoc provider declarations, separate from native tokenizer observations."""
    result = {"source": "provider response; post-hoc, not native tokenizer or a truncation guarantee",
              "recorded_calls": len(measurements)}
    result.update({"http_attempted_calls": sum(item["http_attempted"] is True for item in measurements),
                   "http_attempt_unreported_calls": sum(item["http_attempted"] is None for item in measurements),
                   "cached_failure_calls": sum(item["cached_failure"] is True for item in measurements)})
    for field in ("provider_input_tokens", "provider_output_tokens"):
        stats = _stats([item[field] for item in measurements])
        result[field] = {**stats, "total": sum(item[field] for item in measurements if item[field] is not None),
                         "unreported_calls": len(measurements) - stats["count"]}
    return result


def _counts(rows: list[dict]) -> dict:
    total = len(rows)
    scored = sum(row["scored"] for row in rows)
    passed = sum(row["passed"] for row in rows)
    supported = sum(row["supported"] for row in rows)
    supported_scored = sum(row["supported"] and row["scored"] for row in rows)
    return {"total_cases": total, "recorded_cases": sum(row["recorded"] for row in rows),
            "supported_cases": supported,
            "supported_scored_cases": supported_scored,
            "supported_definition": "declared profile capability and attainable reference target; native overflow retains the adapter status",
            "scored_cases": scored, "passed_cases": passed, "failed_scored_cases": scored - passed,
            "coverage_over_all": scored / total if total else 0.0,
            "coverage_supported": supported_scored / supported if supported else None,
            "accuracy_over_all": passed / total if total else None,
            "accuracy_scored": passed / scored if scored else None,
            "accuracy_supported": sum(row["passed"] and row["supported"] for row in rows) / supported if supported else None,
            "independent_families": len({row["translation_family"] for row in rows}),
            "scored_families": len({row["translation_family"] for row in rows if row["scored"]}),
            "scenario_count": len({row["scenario_id"] for row in rows}),
            "counts_by_split": {split: {"total_cases": sum(row["split"] == split for row in rows),
                                         "scored_cases": sum(row["split"] == split and row["scored"] for row in rows),
                                         "passed_cases": sum(row["split"] == split and row["passed"] for row in rows)}
                                for split in sorted({row["split"] for row in rows})},
            "counts_by_status": {status: sum(row["status"] == status for row in rows) for status in STATUSES},
            "unsupported_target_unattainable": sum(row["failure_kind"] == "target_unattainable" for row in rows),
            "unsupported_other": sum(row["status"] == "unsupported" and row["failure_kind"] != "target_unattainable" for row in rows),
            "typed_overflow_errors": sum(row["failure_kind"] == "typed_overflow" and row["status"] == "error" for row in rows),
            "typed_native_overflows": sum(row["failure_kind"] == "typed_overflow" for row in rows),
            "counts_by_error": {error: sum(row["error"] == error for row in rows)
                                for error in sorted({row["error"] for row in rows if row["error"] is not None})},
            "latency": {field: {**_stats([row["measurements"][field] for row in rows]),
                                 "counts_by_status": {status: sum(row["status"] == status and
                                                                   row["measurements"][field] is not None for row in rows)
                                                      for status in STATUSES}}
                        for field in ("adapter_duration_ms", "decision_ms", "inference_ms", "http_ms")},
            "successful_latency": {field: _stats([row["measurements"][field] for row in rows if row["status"] == "ok"])
                                   for field in ("adapter_duration_ms", "decision_ms", "inference_ms", "http_ms")},
            "resources": {field: _stats([row["measurements"][field] for row in rows])
                          for field in ("native_tokens", "native_padded_tokens", "rss_mib")},
            "provider_usage": _provider_usage([row["measurements"] for row in rows if row["recorded"]]),
            "reference_tokens": _stats([row["reference_actual_tokens"] for row in rows]),
            "reference_padded_tokens": _stats([row["reference_padded_tokens"] for row in rows]),
            "truncation_observations": {field: sum(row["measurements"][field] is True for row in rows)
                                        for field in ("state_truncated", "options_truncated")},
            "truncation_observation_counts": {
                field: {"true": sum(row["measurements"].get(field) is True for row in rows),
                        "false": sum(row["measurements"].get(field) is False for row in rows),
                        "unknown": sum(type(row["measurements"].get(field)) is not bool for row in rows)}
                for field in ("state_truncated", "options_truncated", "native_usage_truncated")}}


def analyze_context(run_path: str | Path, output_dir: str | Path) -> dict:
    """Write a new JSON/Markdown/CSV analysis of one sealed archive snapshot."""
    root, manifest, cases, records, parent, payloads = campaigns._archive(run_path)
    if not parent["sealed"]:
        raise campaigns.CampaignError("Context analysis requires a sealed campaign archive.")
    scorer = campaigns._scorer_fingerprint()
    if manifest.get("scorer") != scorer:
        raise campaigns.CampaignError("Context analysis scorer differs; explicitly rescore the archive first.")
    scores = summarize(cases, records)
    profile = campaigns._decode(payloads["profile.json"])
    capabilities = set(profile["capabilities"])
    indexed = {record["case_id"]: record for record in records}
    rows = []
    for case, score in zip(cases, scores["rows"]):
        metadata = case.get("evaluation", {})
        params = metadata.get("oracle", {}).get("params", {})
        length = metadata.get("length")
        record = indexed.get(case["case_id"])
        error = record.get("error") if record else None
        failure = ("target_unattainable" if score["status"] == "unsupported" and error == "input_length_target_unattainable"
                   else "typed_overflow" if score["status"] in {"error", "unsupported"} and error in OVERFLOW_ERRORS
                   else score["status"] if score["status"] != "ok" else None)
        row = {"case_id": case["case_id"], "base_case_id": metadata.get("base_case_id", case["case_id"]),
               "translation_family": case["translation_family"], "scenario_id": case["scenario_id"],
               "split": case["split"], "domain": metadata.get("domain", "unannotated"),
               "benchmark_pack": params.get("benchmark_pack", "context-choice-v1" if metadata else "legacy_typed_decisions"),
               "task_type": metadata.get("task_type", "unannotated"),
               "use_case": params.get("use_case", "not_annotated"),
               "catalogue_variant": params.get("catalogue_variant", "not_applicable"),
               "language": case["language"], "difficulty": metadata.get("difficulty", "unannotated"),
               "target": str(length["target_tokens"]) if length else "base",
               "position": length["position"] if length else "base",
               "order": length["order"] if length else "base",
               "within_reference_target": length["within_target"] if length else None,
               "reference_actual_tokens": length["actual_tokens"] if length else None,
               "reference_padded_tokens": length["padded_tokens"] if length else None,
               "tokenizer_revision": length["tokenizer_revision"] if length else None,
               "tokenizer_sha256": length["tokenizer_sha256"] if length else None,
               "supported": case["contract_id"] in capabilities and (not length or length["within_target"]),
               "review": metadata.get("review", "not_recorded"), "recorded": record is not None,
               "status": score["status"], "scored": score["scored"], "passed": score["passed"],
               "score_reason": score["reason"], "error": error, "failure_kind": failure,
               "measurements": _measurements(record)}
        rows.append(row)
    cells = []
    combinations = sorted({tuple(row[field] for field in DIMENSIONS) for row in rows},
                          key=lambda key: (*key[:3], _target_order(key[3]), *key[4:]))
    for key in combinations:
        cells.append({"dimensions": dict(zip(DIMENSIONS, key)),
                      **_counts([row for row in rows if tuple(row[field] for field in DIMENSIONS) == key])})
    summary = {"schema_version": "deposium.context-analysis/v1",
               "created_at": datetime.now(timezone.utc).isoformat(),
               "analysis_status": "exploratory" if scores["scored_cases"] else "no_scored_cases",
               "fallback_threshold": {"status": "not_qualified", "value": None,
                                      "reason": "No qualified LLM baseline, independent human review or frozen cascade test."},
               "source_archive": {**parent, "files_sha256": {
                   name: campaigns._hash(data) for name, data in sorted(payloads.items())}},
               "qualification": manifest["qualification"], "input_protocol": manifest["input_protocol"],
               "dataset_sha256": manifest["dataset_sha256"], "scorer": scorer,
               "adapter_provenance": manifest["adapter_provenance"],
               "timing_freshness": {"campaign_mode": manifest["mode"],
                                    "rescore_creates_new_measurements": False,
                                    "resume_may_include_inherited_recorded_calls": True},
               "statistics_protocol": {"median": "arithmetic midpoint of central pair for even counts",
                                       "p95": "nearest rank ceil(0.95*n); for 1<=n<20 equals the maximum",
                                       "latencies": "recorded calls only; include failures and censored timeout durations by status",
                                       "successful_latency": "status ok only; does not imply a correct answer",
                                       "independence": "translation_family; variants and repeated calls do not add families"},
               "counts": _counts(rows), "cells": cells,
               "groups": {field: {value: _counts([row for row in rows if row[field] == value])
                                   for value in sorted({row[field] for row in rows})}
                          for field in DIMENSIONS},
               "rows": rows,
               "limitations": ["Descriptive isolated observations, not production qualification or a fitted threshold.",
                               "Accuracy includes all cases; missing, unsupported, errors, timeout and abstention remain distinct.",
                               "Target tokens use the archived reference tokenizer; native tokens are separate observations.",
                               "Base cases have no target-length annotation and remain in the base bucket.",
                               "Adapter, decision, inference and client HTTP durations have distinct boundaries; historical adapters may differ.",
                               "HTTP duration includes client networking/TLS/queue; server time, RSS and native tokens are unobserved for HTTP.",
                               "Provider usage is a post-hoc declaration; absent truncation metadata establishes no truncation guarantee.",
                               "Failures without engine timing do not receive invented engine latency.",
                               "Worker RSS may be a cumulative process high-water mark, not a per-case peak or whole-system memory.",
                               "Resumed rows may inherit measured calls; rescore creates no new timing measurements.",
                               "Independent family counts are shown; no confidence interval or stable p95 is asserted."]}
    output = campaigns._destination(output_dir, manifest.get("stack_root"), root)
    campaigns._write_new(output / "analysis.json", campaigns._encode(summary))
    report = ["# Context analysis", "", "Exploratory archived observations; no qualified LLM fallback threshold.", "",
              f"Scored: {scores['scored_cases']} / {len(cases)}; passed: {scores['passed_cases']} / {len(cases)}.",
              f"Independent families: {summary['counts']['independent_families']}.", "",
              "| Split | Domain | Target | Passed / scored / total | Families | Decision median ms | P95 ms | Timing count | Peak RSS MiB |",
              "|---|---|---|---|---|---|---|---|---|"]
    aggregates = sorted({(row["split"], row["domain"], row["target"]) for row in rows},
                        key=lambda key: (*key[:2], _target_order(key[2])))
    def render_number(value):
        return "unobserved" if value is None else f"{value:.3f}"
    for split, domain, target in aggregates:
        stats = _counts([row for row in rows if (row["split"], row["domain"], row["target"]) == (split, domain, target)])
        timing = stats["latency"]["decision_ms"]
        report.append(f"| {split} | {domain} | {target} | {stats['passed_cases']} / {stats['scored_cases']} / {stats['total_cases']} | "
                      f"{stats['independent_families']} | {render_number(timing['median'])} | {render_number(timing['p95'])} | "
                      f"{timing['count']} | {render_number(stats['resources']['rss_mib']['max'])} |")
    http = summary["counts"]["latency"]["http_ms"]
    usage = summary["counts"]["provider_usage"]
    report += ["", f"HTTP attempts explicitly reported: {usage['http_attempted_calls']}; cached failures: {usage['cached_failure_calls']}; calls with no attempt flag: {usage['http_attempt_unreported_calls']}.",
               f"Client HTTP: median {render_number(http['median'])} ms; p95 {render_number(http['p95'])} ms; observations {http['count']}.",
               *[f"{field}: reported {usage[field]['count']} / {usage['recorded_calls']} calls; declared total {usage[field]['total']}."
                 for field in ("provider_input_tokens", "provider_output_tokens")],
               "Provider usage is post-hoc; server timings, RSS, native token counts and truncation are not inferred.",
               "", "Detailed cells (split retained):", "",
               "| " + " | ".join(field.replace("_", " ").title() for field in DIMENSIONS) + " | Scored / total | Passed / total | Families |",
               "|" + "---|" * (len(DIMENSIONS) + 3)]
    for cell in cells:
        labels = " | ".join(str(cell["dimensions"][field]).replace("|", "\\|") for field in DIMENSIONS)
        report.append(f"| {labels} | {cell['scored_cases']} / {cell['total_cases']} | "
                      f"{cell['passed_cases']} / {cell['total_cases']} | {cell['independent_families']} |")
    report += ["", "All unsupported and unrecorded cases stay in the denominator.",
               "Unattainable reference targets and typed native overflows are separate in analysis.json.",
               "Latency distributions include their counts and status denominators; adapter and engine times are distinct.",
               "Median uses the arithmetic central pair; p95 uses nearest rank and is exploratory.",
               "Target lengths use reference tokens; reported native tokens and padding may differ.", ""]
    campaigns._write_new(output / "report.md", "\n".join(report).encode())
    csv_buffer = io.StringIO(newline="")
    fields = ["case_id", "translation_family", *DIMENSIONS, "status", "supported", "scored", "passed",
              "error", "failure_kind", "reference_actual_tokens", "reference_padded_tokens",
              "adapter_duration_ms", "decision_ms", "inference_ms", "http_ms", "http_attempted", "cached_failure", "provider_input_tokens", "provider_output_tokens", "native_tokens", "native_padded_tokens", "rss_mib", "native_usage_truncated"]
    writer = csv.DictWriter(csv_buffer, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row["measurements"].get(field) if field in row["measurements"] else row.get(field)
                         for field in fields})
    campaigns._write_new(output / "rows.csv", csv_buffer.getvalue().encode())
    return summary
