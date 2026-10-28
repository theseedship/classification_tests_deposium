"""Paired, descriptive comparison of validated archived outputs; no inference."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path

from . import campaigns
from .scoring import summarize
from .context_analysis import _measurements, _stats, _provider_usage


def _source(parent: dict, manifest: dict, payloads: dict[str, bytes]) -> dict:
    return {**parent, "qualification": manifest["qualification"],
            "proof_level": manifest["proof_level"],
            "adapter_provenance": manifest["adapter_provenance"],
            "files": {name: campaigns._hash(data) for name, data in sorted(payloads.items())}}


def _counts(rows: list[dict]) -> dict:
    outcomes = ("improved", "regressed", "both_pass", "both_fail", "unpaired")
    paired = sum(row["outcome"] != "unpaired" for row in rows)
    common_ok = [row for row in rows if all(row[side]["status"] == "ok" and row[side]["scored"]
                                          for side in ("baseline", "candidate"))]
    details = {}
    for side in ("baseline", "candidate"):
        scored = sum(row[side]["scored"] for row in rows)
        correct = sum(row[side]["passed"] for row in rows)
        common_correct = sum(row[side]["passed"] for row in common_ok)
        details[side] = {"correct": correct, "scored": scored, "all": len(rows),
                         "accuracy_scored": correct / scored if scored else None,
                         "accuracy_all": correct / len(rows) if rows else None,
                         "common_ok_correct": common_correct,
                         "common_ok_accuracy": common_correct / len(common_ok) if common_ok else None}
    return {"total_cases": len(rows), "paired_scored_cases": paired,
            "common_ok_cases": len(common_ok), "accuracy": details,
            "common_ok_coverage": len(common_ok) / len(rows) if rows else 0.0,
            "common_ok_outcomes": {kind: sum(row["outcome"] == kind for row in common_ok)
                                   for kind in outcomes if kind != "unpaired"},
            "paired_coverage": paired / len(rows) if rows else 0.0,
            "translation_families": len({row["translation_family"] for row in rows}),
            "scenarios": len({row["scenario_id"] for row in rows}),
            "outcomes": {kind: sum(row["outcome"] == kind for row in rows) for kind in outcomes},
            "baseline_scored_cases": sum(row["baseline"]["scored"] for row in rows),
            "candidate_scored_cases": sum(row["candidate"]["scored"] for row in rows),
            "baseline_passed_cases": sum(row["baseline"]["passed"] for row in rows),
            "candidate_passed_cases": sum(row["candidate"]["passed"] for row in rows)}


def _timings(records: list[dict]) -> dict:
    values = sorted(record["duration_ms"] for record in records)
    measurements = [_measurements(record) for record in records]
    return {"http_ms": _stats([item["http_ms"] for item in measurements]),
            "provider_usage": _provider_usage(measurements),
            "measurement": "archived adapter call duration; different execution boundaries",
            "cross_candidate_comparable": False, "recorded_cases": len(values),
            "p50_ms": values[math.ceil(len(values) * .5) - 1] if values else None,
            "p95_ms": values[math.ceil(len(values) * .95) - 1] if values else None,
            "total_ms": sum(values)}


def _side(score: dict, record: dict | None) -> dict:
    result = {key: score[key] for key in ("status", "scored", "passed", "reason", "checks")}
    result["duration_ms"] = record["duration_ms"] if record else None
    raw = record.get("raw_output") if record else None
    # Preserve explicit runtime observations without guessing the units of scores.
    result["runtime_observations"] = ({key: value for key, value in raw.items()
                                       if key in {"runtime", "timings", "inference_ms", "load_ms", "http_ms", "requested_model", "observed_model", "usage", "http_status", "http_attempted", "cached_failure", "cause_attempt_id"}}
                                      if isinstance(raw, dict) else {})
    return result


def compare_campaigns(baseline_archive: str | Path, candidate_archive: str | Path,
                      output_dir: str | Path) -> dict:
    """Compare byte snapshots scored by the same current scorer and protocol."""
    baseline = campaigns._archive(baseline_archive)
    candidate = campaigns._archive(candidate_archive)
    left_root, left, cases, left_records, left_parent, left_payloads = baseline
    right_root, right, other_cases, right_records, right_parent, right_payloads = candidate
    if not left_parent.get("sealed") or not right_parent.get("sealed"):
        raise campaigns.CampaignError("Comparison requires two sealed archives.")
    for field in ("dataset_sha256", "case_ids", "input_protocol"):
        if not left.get(field) or left.get(field) != right.get(field):
            raise campaigns.CampaignError(f"Comparison requires identical {field}.")
    current_scorer = campaigns._scorer_fingerprint()
    if (left.get("scorer") != right.get("scorer") or left.get("scorer") != current_scorer):
        raise campaigns.CampaignError("Comparison scorer differs; explicitly rescore both archives first.")
    if left.get("qualification") not in {"component_replay", "model_isolated"} or left.get("proof_level") != "A":
        raise campaigns.CampaignError("Comparison baseline must be a component replay or isolated model at proof level A.")
    if right.get("qualification") != "model_isolated" or right.get("proof_level") != "A":
        raise campaigns.CampaignError("Comparison candidate must be an isolated model at proof level A.")
    model_comparison = left["qualification"] == "model_isolated"
    left_scores, right_scores = summarize(cases, left_records), summarize(other_cases, right_records)
    left_map = {record["case_id"]: record for record in left_records}
    right_map = {record["case_id"]: record for record in right_records}
    rows = []
    for case, before, after in zip(cases, left_scores["rows"], right_scores["rows"]):
        if not before["scored"] or not after["scored"]:
            outcome = "unpaired"
        elif before["passed"] and after["passed"]:
            outcome = "both_pass"
        elif before["passed"]:
            outcome = "regressed"
        elif after["passed"]:
            outcome = "improved"
        else:
            outcome = "both_fail"
        evaluation = case.get("evaluation", {})
        context_groups = {key: evaluation[key] for key in ("domain", "difficulty") if key in evaluation}
        if isinstance(evaluation.get("length"), dict):
            context_groups.update({key: evaluation["length"][key]
                                   for key in ("target_tokens", "position", "order")})
        rows.append({key: case[key] for key in ("case_id", "split", "language", "pack",
                                                "translation_family", "scenario_id")} |
                    context_groups |
                    {"outcome": outcome, "baseline": _side(before, left_map.get(case["case_id"])),
                     "candidate": _side(after, right_map.get(case["case_id"]))})
    counts = _counts(rows)
    summary = {"schema_version": "deposium.comparison/v1",
               "created_at": datetime.now(timezone.utc).isoformat(),
               "comparison_kind": "model_vs_model" if model_comparison else "component_vs_model",
               "comparison_status": "paired_observations" if counts["paired_scored_cases"] else "no_paired_scores",
               "dataset_sha256": left["dataset_sha256"], "input_protocol": left["input_protocol"],
               "scorer": current_scorer, "baseline_archive": _source(left_parent, left, left_payloads),
               "candidate_archive": _source(right_parent, right, right_payloads),
               "counts": counts, "baseline_metrics": left_scores, "candidate_metrics": right_scores,
               "groups": {field: {str(value): _counts([row for row in rows if row[field] == value])
                                   for value in sorted({row[field] for row in rows})}
                          for field in ("split", "language", "pack", "domain", "difficulty",
                                        "target_tokens", "position", "order")
                          if all(field in row for row in rows)},
               "timings": {"baseline": _timings(left_records), "candidate": _timings(right_records)},
               "rows": rows,
               "limitations": ["Descriptive isolated-model comparison." if model_comparison else
                               "Descriptive isolated-model versus component-function replay comparison.",
                               "No integrated routing, product qualification, or promotion verdict.",
                               "Translation variants are correlated; family counts are reported.",
                               "Missing, unsupported, errors, timeouts and abstention stay distinct.",
                               "Adapter durations are not an equivalent-boundary latency benchmark.",
                               "HTTP latency is client/network time, provider usage is post-hoc, and returned model versions are per-response observations."]}
    destination = Path(output_dir).expanduser().resolve()
    for root, manifest in ((left_root, left), (right_root, right)):
        if destination.is_relative_to(root):
            raise campaigns.CampaignError("Comparison output must be outside both source archives.")
        stack = manifest.get("stack_root")
        if stack and destination.is_relative_to(Path(stack).resolve()):
            raise campaigns.CampaignError("Comparison output must be outside the application stack.")
    output = campaigns._destination(output_dir, None)
    campaigns._write_new(output / "comparison.json", campaigns._encode(summary))
    report = ["# Archived candidate comparison", "", "Descriptive comparison; no promotion verdict.", "",
              f"All cases: {counts['total_cases']}; paired scored: {counts['paired_scored_cases']}; common successful calls: {counts['common_ok_cases']}.",
              f"Translation families: {counts['translation_families']}; scenarios: {counts['scenarios']}.", "",
              *[f"{side.title()}: correct {counts['accuracy'][side]['correct']} / scored {counts['accuracy'][side]['scored']} / all {counts['accuracy'][side]['all']}; common successful calls correct {counts['accuracy'][side]['common_ok_correct']} / {counts['common_ok_cases']}."
                for side in ("baseline", "candidate")], "",
              "| Case | Split | Language | Pack | Baseline | Candidate | Outcome |",
              "|---|---|---|---|---|---|---|"]
    for row in rows:
        render = lambda side: f"{side['status']} / " + ("pass" if side["passed"] else "fail" if side["scored"] else "unscored")
        report.append(f"| {row['case_id']} | {row['split']} | {row['language']} | {row['pack']} | "
                      f"{render(row['baseline'])} | {render(row['candidate'])} | {row['outcome']} |")
    for side, records in (("baseline", left_records), ("candidate", right_records)):
        timings = summary["timings"][side]
        usage = timings["provider_usage"]
        report += ["", f"{side.title()} HTTP attempts: {usage['http_attempted_calls']}; cached failures: {usage['cached_failure_calls']}; attempt flag unreported: {usage['http_attempt_unreported_calls']}.",
                   f"{side.title()} client HTTP observations: {timings['http_ms']['count']}; median ms {timings['http_ms']['median']}.",
                   *[f"{field}: reported {usage[field]['count']} / {usage['recorded_calls']} calls; declared total {usage[field]['total']}."
                     for field in ("provider_input_tokens", "provider_output_tokens")]]
    report += ["", "Unsupported and missing cases remain in the all-case denominator.",
               "Recorded adapter durations have different execution boundaries and are not compared as latency gains.",
               "See comparison.json for hashes, grouped denominators, raw runtime observations and exact checks.", ""]
    campaigns._write_new(output / "report.md", "\n".join(report).encode("utf-8"))
    return summary
