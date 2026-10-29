#!/usr/bin/env python3
"""Build public result views from explicitly tracked aggregates; never run inference.

Frozen campaign exports remain unchanged. This is a presentation join, not a
rescore or raw-archive verification. Run --write to refresh, --check to validate.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
METADATA = "docs/leaderboard/model-metadata.json"
EVIDENCE = "docs/evidence/"
HISTORICAL = EVIDENCE + "model-comparison-d3-larger-overview-20261011/manifest.json"
CPU = EVIDENCE + "model-comparison-larger-cpu-20261011/analysis.json"
NATIVE = EVIDENCE + "native-model-comparison-20261016/analysis.json"
GLICLASS = EVIDENCE + "gliclass-model-comparison-20261017/analysis.json"
FAST = EVIDENCE + "vela3-fast-20261028/analysis.json"
CAPABILITY = EVIDENCE + "capability-flash-20261029/analysis.json"
NATIVE_SESSION = EVIDENCE + "native-model-comparison-20261016/native-sessions.json"
GLICLASS_SESSION = EVIDENCE + "gliclass-model-comparison-20261017/gliclass-session.json"
STATUS_KEYS = {"ok", "missing", "unsupported", "error", "timeout", "abstain"}
IDENTITY_KEYS = ("adapter", "profile_id", "device", "model_repo_id", "model_id",
                 "model_revision", "source_revision", "model_assets_sha256",
                 "identity_sha256", "runtime", "settings", "hashes", "revisions")
SOURCE_KEYS = ("dataset_sha256", "manifest_sha256", "raw_sha256", "scorer_sha256",
               "seal_sha256", "seal_fingerprint", "requests_sha256", "projection_version")


class ResultError(ValueError):
    """An aggregate cannot support the claimed public view."""


def require(condition, message):
    if not condition:
        raise ResultError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class PublicInputs:
    """Read named tracked files only, without discovering ignored local material."""

    def __init__(self, root):
        self.root = Path(root)
        raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
        self.tracked = set(raw.decode().split("\0")) - {""}
        self.hashes = {}

    def read(self, relative):
        path = Path(relative)
        require(not path.is_absolute() and ".." not in path.parts
                and relative in self.tracked, f"input is not a tracked public file: {relative}")
        target = self.root / relative
        require(not target.is_symlink() and target.is_file(), f"invalid input: {relative}")
        require(target.resolve().is_relative_to(self.root.resolve()), "input escaped checkout")
        raw = target.read_bytes()
        require(0 < len(raw) <= 32 * 1024 * 1024, f"invalid input size: {relative}")
        self.hashes[relative] = digest(raw)
        return raw

    def load(self, relative):
        value = json.loads(self.read(relative))
        require(isinstance(value, dict), f"expected JSON object: {relative}")
        return value


def load_composer(inputs):
    # Register every dependency before the existing frozen composer reads it.
    for relative in (
        "scripts/compose-larger-cpu-comparison.py", "scripts/compose-d3-comparison.py",
        HISTORICAL, HISTORICAL.replace("manifest.json", "report.md"),
        EVIDENCE + "model-comparison-d3-larger-20261011/analysis.json",
        EVIDENCE + "model-comparison-complete-20261010-sol/analysis.json",
        EVIDENCE + "model-comparison-vela2-20261011/analysis.json",
        EVIDENCE + "model-comparison-d3-20261011/analysis.json",
    ):
        inputs.read(relative)
    path = inputs.root / "scripts/compose-larger-cpu-comparison.py"
    spec = importlib.util.spec_from_file_location("full_results_cpu_composer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def same_observation(left, right):
    # Later exports can add measurement fields to an unchanged archived run.
    return all(left.get(key) == right.get(key) for key in
               ("counts", "groups", "coverage", "source", "identity"))


def validate_pair(label, base, route, legacy):
    require(base.get("qualification") == "model_isolated", f"{label}: model qualification")
    legacy._count(base.get("counts"), total=132, field=label)
    require(base["counts"]["scored"] > 0, f"{label}: no scored cases")
    require(base["counts"]["statuses"]["ok"] == base["counts"]["scored"],
            f"{label}: scored/status mismatch")
    require(base["counts"].get("translation_families") == 66, f"{label}: family count")
    for axis, groups in base.get("groups", {}).items():
        require(isinstance(groups, dict) and groups, f"{label}: empty {axis}")
        for group, count in groups.items():
            require(type(count.get("total")) is int and count["total"] > 0,
                    f"{label}: group denominator")
            legacy._count(count, total=count["total"], field=f"{label}/{axis}/{group}")
            require(count["statuses"]["ok"] == count["scored"], f"{label}: group scored/status mismatch")
        # Documentary_task is the documentary subset, all other axes partition 132.
        expected = base["groups"]["domain"]["documentary"] if axis == "documentary_task" else base["counts"]
        for key in ("correct", "scored", "total"):
            require(sum(v[key] for v in groups.values()) == expected[key],
                    f"{label}: inconsistent {axis}/{key}")
        for status in STATUS_KEYS:
            require(sum(v["statuses"][status] for v in groups.values()) == expected["statuses"][status],
                    f"{label}: inconsistent {axis}/{status}")
    for axis, expected in {
        "domain": {"documentary": 76, "mathematics": 28, "chemistry": 28},
        "split": {"train": 36, "calibration": 30, "test": 66},
        "language": {"en": 66, "fr": 66}, "difficulty": {"D1": 40, "D2": 40, "D3": 52},
    }.items():
        actual = base.get("groups", {}).get(axis, {})
        require({key: value["total"] for key, value in actual.items()} == expected,
                f"{label}: missing or changed {axis}")
    require(route.get("qualification") == "provisional_agreement_pending_human_review"
            and route.get("reference_review") == "pending_human"
            and route.get("cases_scored") == 0, f"{label}: unqualified routing reference")
    legacy._count(route.get("coverage"), total=24, field=f"{label}/tool", qualified="agreement")
    require(set(route.get("statuses", {})) == STATUS_KEYS
            and all(type(v) is int and v >= 0 for v in route["statuses"].values())
            and sum(route["statuses"].values()) == 24
            and route["statuses"]["ok"] == route["coverage"]["valid_decisions"],
            f"{label}: routing statuses")
    for axis, expected in legacy.MASTRA_GROUPS.items():
        groups = route.get(axis, {})
        require(set(groups) == set(expected), f"{label}: missing tool groups {axis}")
        for group, total in expected.items():
            legacy._count(groups[group], total=total, field=f"{label}/{axis}/{group}", qualified="agreement")
        for key in ("agreement_count", "valid_decisions", "total"):
            require(sum(v[key] for v in groups.values()) == route["coverage"][key],
                    f"{label}: inconsistent tool {axis}/{key}")
    for phase, row, total in (("context", base, 132), ("tool", route, 24)):
        legacy._source(row.get("source"), mastra=phase == "tool")
        legacy._stats(row.get("timing", {}).get("successful_adapter_ms"),
                      total=total, field=f"{label}/{phase}/time", unreported=False)
        legacy._stats(row.get("worker_rss_mib"), total=total,
                      field=f"{label}/{phase}/RSS", unreported=True)
    require(all(base["identity"].get(key) == route["identity"].get(key) for key in
                ("adapter", "model_repo_id", "model_revision", "model_assets_sha256")),
            f"{label}: base/tool model mismatch")


def compact_counts(count, route=False):
    keys = ("agreement_count", "valid_decisions", "total") if route else ("correct", "scored", "total", "statuses")
    return {key: count[key] for key in keys}


def measured_number(value, field):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            f"invalid measurement: {field}")
    return value


def campaign_counts(value, total, label, *, require_scored=False):
    """Validate exported denominators without evaluating or rescoring outputs."""
    require(type(total) is int and total > 0, f"{label}: zero denominator")
    for key in ("total_cases", "recorded_cases", "scored_cases", "passed_cases"):
        require(type(value[key]) is int and 0 <= value[key] <= total, f"{label}: invalid count")
    require(value["total_cases"] == total
            and value["passed_cases"] <= value["scored_cases"] <= value["recorded_cases"],
            f"{label}: inconsistent coverage")
    statuses = value["counts_by_status"]
    require(set(statuses) == STATUS_KEYS
            and all(type(n) is int and n >= 0 for n in statuses.values())
            and sum(statuses.values()) == total
            and value["scored_cases"] == statuses["ok"] + statuses["abstain"],
            f"{label}: inconsistent statuses")
    require(not require_scored or value["scored_cases"] > 0, f"{label}: zero scored cases")
    require(type(value["independent_families"]) is int and 1 <= value["independent_families"] <= total,
            f"{label}: invalid family denominator")
    splits = value["counts_by_split"]
    require(bool(splits) and set(splits) <= {"train", "calibration", "test"}, f"{label}: invalid split")
    for group in splits.values():
        require(all(type(group[k]) is int and 0 <= group[k] <= total for k in
                    ("total_cases", "scored_cases", "passed_cases"))
                and group["passed_cases"] <= group["scored_cases"] <= group["total_cases"],
                f"{label}: invalid split counts")
    require(all(sum(group[key] for group in splits.values()) == value[key]
                for key in ("total_cases", "scored_cases", "passed_cases")), f"{label}: inconsistent split sums")
    return {"correct": value["passed_cases"], "scored": value["scored_cases"], "total": total,
            "recorded": value["recorded_cases"], "families": value["independent_families"], "statuses": dict(statuses),
            "by_split": {part: {"correct": group["passed_cases"], "scored": group["scored_cases"],
                                 "total": group["total_cases"]} for part, group in splits.items()}}


def capability_campaign(inputs, historical, metadata):
    """Keep the new two-pack experiment separate from historical ranking rows."""
    source = inputs.load(CAPABILITY)
    require(source.get("schema_version") == "deposium.capability-flash-results/v1"
            and source.get("scope") == "isolated_frozen_closed_choice_observations"
            and source.get("reference_review") == "synthetic_agent_authored_pending_human_review",
            "capability: changed qualification")
    expected = {
        "anchor": {"total": 132, "families": 66, "test_families": 33,
                   "dataset": "767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616",
                   "groups": {"split": {"train": 36, "calibration": 30, "test": 66},
                              "language": {"fr": 66, "en": 66}}},
        "capability": {"total": 192, "families": 48, "test_families": 24,
                       "dataset": "0b409a09bb5358b5c8d7574cbd330799511851a2acd90676e2f092f3d3c75eb0",
                       "groups": {"split": {"train": 48, "calibration": 48, "test": 96},
                                  "language": {"fr": 96, "en": 96},
                                  "track": {"selection": 64, "arguments": 64, "observations": 64},
                                  "catalogue_variant": {"compact": 96, "expanded": 96}}},
    }
    phases = {}
    anchor_identity = source["phases"]["anchor"]["identity"]
    for phase, spec in expected.items():
        item = source["phases"][phase]
        identity = item["identity"]
        require(identity == anchor_identity and identity.get("backend_requested") == "metal",
                f"capability/{phase}: different model/runtime")
        require(all(identity.get(new) == historical["identity"].get(old) for new, old in
                    (("model_repo_id", "model_repo_id"), ("model_revision", "model_revision"),
                     ("model_sha256", "model_assets_sha256"))), f"capability/{phase}: historical identity mismatch")
        require(item["sources"]["dataset_sha256"] == spec["dataset"], f"capability/{phase}: dataset mismatch")
        counts = campaign_counts(item["counts"], spec["total"], phase, require_scored=True)
        groups = {}
        for axis, denominators in spec["groups"].items():
            raw_groups = item["groups"][axis]
            require(set(raw_groups) == set(denominators), f"capability/{phase}: missing {axis}")
            groups[axis] = {key: campaign_counts(raw_groups[key], total, f"{phase}/{axis}/{key}")
                            for key, total in denominators.items()}
            require(all(sum(group[key] for group in groups[axis].values()) == counts[key]
                        for key in ("correct", "scored", "total", "recorded")), f"capability/{phase}: inconsistent {axis}")
            require(all(sum(group["statuses"][status] for group in groups[axis].values()) == counts["statuses"][status]
                        for status in STATUS_KEYS), f"capability/{phase}: inconsistent {axis} statuses")
        require(all(groups["split"][part][key] == group[key] for part, group in counts["by_split"].items()
                    for key in ("correct", "scored", "total")), f"capability/{phase}: split views differ")
        require(counts["families"] == spec["families"]
                and groups["split"]["test"]["families"] == spec["test_families"],
                f"capability/{phase}: family denominator differs")
        timing = item["counts"]["successful_latency"]["adapter_duration_ms"]
        require(type(timing["count"]) is int and 0 <= timing["count"] <= counts["statuses"]["ok"],
                f"capability/{phase}: timing coverage")
        for field in ("min", "median", "p95", "max"):
            require(timing[field] is None or (type(timing[field]) in (int, float)
                    and math.isfinite(timing[field]) and timing[field] >= 0), f"capability/{phase}: timing value")
        resource = item["session_resources"]
        peak = measured_number(resource["rss_peak_mib"], f"capability/{phase}/RSS")
        require(resource["rss_scope"] == "sampled owned process-group peak over startup, synthetic smoke and this phase; not per-case or total unified GPU memory",
                f"capability/{phase}: RSS scope")
        require(item["backend_evidence"]["metal_initialization_observed"] is True,
                f"capability/{phase}: Metal unobserved")
        phases[phase] = {"counts": counts, "groups": groups,
                         "adapter_ms": {key: timing[key] for key in ("count", "min", "median", "p95", "max")},
                         "session_group_peak_rss_mib": peak, "rss_scope": resource["rss_scope"],
                         "source": {key: item["sources"][key] for key in
                                    ("dataset_sha256", "campaign_seal_sha256", "raw_sha256", "bench_head")}}
    return {"source": CAPABILITY, "report": "CAPABILITY_FLASH_RESULTS_20261029.md",
            "model": "D3 Flash Q8", "nominal_size": metadata["model_size"]["label"],
            "runtime": "llama.cpp / Metal", "identity": anchor_identity, "phases": phases,
            "reference_review": source["reference_review"], "canary_in_quality_denominators": False}


def build(root=ROOT):
    inputs = PublicInputs(root)
    composer = load_composer(inputs)
    frozen, _ = composer.historical(inputs.root / HISTORICAL)
    current = inputs.load(CPU)
    base, routes, _ = composer.compose(current, frozen)
    require(len(base) == 22, "historical roster changed")
    for path, selected in ((NATIVE, {"D3Q4", "D3FlashQ4", "D3FlashQ8", "EosQ8"}),
                           (GLICLASS, {"GLiClass9B"}), (FAST, {"Vela3Fast"})):
        export = inputs.load(path)
        require(export.get("scope") == "isolated_model_observations"
                and export.get("base_reference_review") == "agent_only_pending_human",
                f"changed export qualification: {path}")
        for label in set(base) & set(export["base"]):
            require(same_observation(base[label], export["base"][label])
                    and same_observation(routes[label], export["mastra"][label]),
                    f"conflicting repeated observation: {label}")
        require(selected <= set(export["base"]) and not selected & set(base), "new roster overlap")
        for label in selected:
            base[label], routes[label] = export["base"][label], export["mastra"][label]
    metadata = inputs.load(METADATA)
    require(metadata.get("schema_version") == "deposium.public-model-metadata/v1", "metadata version")
    require(set(metadata["observations"]) == set(base) == set(routes) and len(base) == 28,
            "metadata/observation roster mismatch")
    native = inputs.load(NATIVE_SESSION)
    gli = inputs.load(GLICLASS_SESSION)
    rows = []
    for label in sorted(base, key=lambda key: (-base[key]["counts"]["correct"], key)):
        b, r, meta = base[label], routes[label], metadata["observations"][label]
        validate_pair(label, b, r, composer.legacy)
        source = inputs.load(meta["source_analysis"])
        require(same_observation(b, source["base"].get(label, {}))
                and same_observation(r, source["mastra"].get(label, {})), f"{label}: metadata source mismatch")
        for evidence in meta["evidence"] + ([meta["model_size"]["source"]] if meta["model_size"]["source"] else []):
            inputs.read(evidence["path"])
        size = meta["model_size"]
        require(size["parameters"] is None or (type(size["parameters"]) is int and size["parameters"] > 0),
                f"{label}: invalid model size")
        rank = 1 + sum(other["counts"]["correct"] > b["counts"]["correct"] for other in base.values())
        resource = {
            "adapter_ms": b["timing"]["successful_adapter_ms"],
            "initialization_ms": b["timing"]["initialization_ms"],
            "worker_rss_mib": b["worker_rss_mib"],
            "session_process_group_peak_rss_mib": None,
            "sampled_gpu_allocated_peak_mib": None,
            "rss_scope": "Per-response worker RSS, context-choice phase; not total host memory",
        }
        if label in native["observations"]:
            obs = native["observations"][label]
            require(all(obs["model"][k] == b["identity"][v] for k, v in
                        (("repo_id", "model_repo_id"), ("revision", "model_revision"),
                         ("sha256", "model_assets_sha256"))), f"{label}: native resource identity")
            require(obs["files_sha256"]["bases/seal.json"] == b["source"]["seal_sha256"]
                    and obs["files_sha256"]["mastra/seal.json"] == r["source"]["seal_sha256"],
                    f"{label}: native resource seals")
            resource["session_process_group_peak_rss_mib"] = measured_number(
                obs["resources"]["rss_peak_mib"], label)
            resource["rss_scope"] = "Sampled native process-group RSS over context + tool session; not a total unified-memory peak"
        if label == "GLiClass9B":
            require(all(gli["identity"][key] == b["identity"][key] for key in
                        ("model_repo_id", "model_revision", "identity_sha256")), "GLiClass resource identity")
            require(gli["source_files_sha256"]["bases/seal.json"] == b["source"]["seal_sha256"],
                    "GLiClass resource seal")
            obs = gli["observations"]["base"]
            require(obs["calls"] == 132 and obs["max_reported_rss_mib"] == b["worker_rss_mib"]["max"],
                    "GLiClass resource coverage")
            resource["sampled_gpu_allocated_peak_mib"] = measured_number(
                obs["max_sampled_gpu_allocated_mib"], label)
        rows.append({
            "id": label, "rank_all_splits": rank, "metadata": meta,
            "identity": {key: b["identity"].get(key) for key in IDENTITY_KEYS},
            "context": {"counts": compact_counts(b["counts"]),
                        "groups": {axis: {group: compact_counts(count) for group, count in groups.items()}
                                   for axis, groups in b["groups"].items()},
                        "source": {key: b["source"].get(key) for key in SOURCE_KEYS}},
            "tool_proposal": {"counts": compact_counts(r["coverage"], True), "statuses": r["statuses"],
                              "qualification": r["qualification"], "cases_scored": r["cases_scored"],
                              "groups": {axis: {group: compact_counts(count, True) for group, count in r[axis].items()}
                                         for axis in composer.legacy.MASTRA_GROUPS},
                              "source": {key: r["source"].get(key) for key in SOURCE_KEYS}},
            "resources": resource,
        })
    for phase in ("context", "tool_proposal"):
        require(len({row[phase]["source"]["seal_sha256"] for row in rows}) == 28,
                f"duplicate observation seals: {phase}")
        require(len({row[phase]["source"]["dataset_sha256"] for row in rows}) == 1,
                f"mixed datasets: {phase}")
    complementary = capability_campaign(inputs, base["D3FlashQ8"], metadata["observations"]["D3FlashQ8"])
    inputs.read("scripts/build-full-results.py")
    return {"schema_version": "deposium.public-results/v1", "observations": rows,
            "capability_campaign": complementary,
            "scope": "aggregate_presentation_only_no_inference_or_raw_archive_verification",
            "reference_review": "agent_only_pending_human",
            "ranking": "Competition rank by correct/132, all splits; ties ordered by observation ID",
            "sources_sha256": dict(sorted(inputs.hashes.items()))}


def csv_text(records):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue()


def flat_rows(data):
    models, tasks = [], []
    for row in data["observations"]:
        meta, ctx, tool, res = row["metadata"], row["context"], row["tool_proposal"], row["resources"]
        groups = ctx["groups"]
        models.append({
            "rank_all_splits": row["rank_all_splits"], "observation": row["id"], "model": meta["display_name"],
            "size": meta["model_size"]["label"], "parameters": meta["model_size"]["parameters"],
            "size_basis": meta["model_size"]["basis"], "runtime_group": meta["runtime_group"],
            "hardware": meta["hardware_group"], "precision": meta["precision"],
            "all_correct": ctx["counts"]["correct"], "all_scored": ctx["counts"]["scored"], "all_total": 132,
            **{f"{key}_correct": groups[axis][group]["correct"] for key, axis, group in
               (("test", "split", "test"), ("documentary", "domain", "documentary"),
                ("math", "domain", "mathematics"), ("chemistry", "domain", "chemistry"),
                ("en", "language", "en"), ("fr", "language", "fr"))},
            "tool_agreement": tool["counts"]["agreement_count"], "tool_valid": tool["counts"]["valid_decisions"],
            "tool_total": 24, "tool_qualified_cases": 0,
            "adapter_median_ms": res["adapter_ms"]["median"], "adapter_p95_ms": res["adapter_ms"]["p95"],
            "timed_calls": res["adapter_ms"]["count"], "initialization_ms": res["initialization_ms"],
            "worker_peak_rss_mib": res["worker_rss_mib"]["max"], "rss_reported_calls": res["worker_rss_mib"]["count"],
            "session_process_group_peak_rss_mib": res["session_process_group_peak_rss_mib"],
            "sampled_gpu_allocated_peak_mib": res["sampled_gpu_allocated_peak_mib"],
            "rss_scope": res["rss_scope"], "source_analysis": meta["source_analysis"],
        })
        for phase in ("context", "tool_proposal"):
            for axis, values in row[phase]["groups"].items():
                for group, count in sorted(values.items()):
                    route = phase == "tool_proposal"
                    tasks.append({"observation": row["id"], "task": phase, "axis": axis, "group": group,
                                  "metric": "provisional_agreement" if route else "correct_choice",
                                  "numerator": count["agreement_count" if route else "correct"],
                                  "scored_or_valid": count["valid_decisions" if route else "scored"],
                                  "total": count["total"],
                                  **{status: count.get("statuses", {}).get(status) for status in sorted(STATUS_KEYS)}})
    return models, tasks


def number(value, places=1):
    return "NR" if value is None else f"{value:,.{places}f}"


def render_capability(campaign):
    def ratio(count, key="correct"):
        return f"{count[key]}/{count['total']}"
    phases = campaign["phases"]
    lines = ["## Complementary capability campaign: 29 October 2026", "",
             f"**{campaign['model']}**, nominal {campaign['nominal_size']}, {campaign['runtime']}. "
             "The two full packs have separate denominators; canary calls are excluded.",
             "References remain agent-authored and pending human review. A perfect closed-choice score "
             "does not qualify tool execution or product behavior.", "",
             "| Pack / track | Correct / all | Scored / all | Test correct / all |",
             "|---|---:|---:|---:|"]
    for phase, label in (("anchor", "Fresh context anchor"), ("capability", "Capability pack")):
        count = phases[phase]["counts"]
        lines.append(f"| {label} | {ratio(count)} | {ratio(count, 'scored')} | {ratio(count['by_split']['test'])} |")
    for track, label in (("selection", "Capability selection"), ("arguments", "Arguments and dependencies"),
                         ("observations", "Next step after fixed observations")):
        count = phases["capability"]["groups"]["track"][track]
        lines.append(f"| {label} | {ratio(count)} | {ratio(count, 'scored')} | {ratio(count['by_split']['test'])} |")
    lines += ["", "The three track rows partition the 192-case pack; they are not additional cases. "
              f"The fresh anchor has {phases['anchor']['counts']['families']} FR/EN families. "
              f"The new pack's 192 language/catalogue variants belong to {phases['capability']['counts']['families']} "
              f"families, including {phases['capability']['groups']['split']['test']['families']} test families.", "",
              "| Pack | French correct / all | English correct / all | 8-card correct / all | 32-card correct / all |",
              "|---|---:|---:|---:|---:|"]
    for phase, label in (("anchor", "Fresh context anchor"), ("capability", "Capability pack")):
        groups = phases[phase]["groups"]
        catalogue = groups.get("catalogue_variant", {})
        lines.append(f"| {label} | {ratio(groups['language']['fr'])} | {ratio(groups['language']['en'])} | "
                     f"{ratio(catalogue['compact']) if catalogue else 'Not applicable'} | "
                     f"{ratio(catalogue['expanded']) if catalogue else 'Not applicable'} |")
    lines += ["", "| Pack | Timed successful calls / all | Adapter median ms | Adapter p95 ms | Session group RSS GiB |",
              "|---|---:|---:|---:|---:|"]
    for phase, label in (("anchor", "Fresh context anchor"), ("capability", "Capability pack")):
        item = phases[phase]
        timing = item["adapter_ms"]
        lines.append(f"| {label} | {timing['count']}/{item['counts']['total']} | {number(timing['median'])} | "
                     f"{number(timing['p95'])} | {number(item['session_group_peak_rss_mib'] / 1024, 2)} |")
    lines += ["", "Timings follow each session's synthetic warm-up and describe one pass; loading/startup is excluded. "
              "RSS is the sampled owned process-group peak over startup, smoke and that pack, not per-case RSS "
              "or total unified GPU memory. GPU allocation was unreported. Catalogue variants are correlated.",
              f"[Full campaign report]({campaign['report']}) · "
              "[Groups, pairs and source evidence](evidence/capability-flash-20261029/analysis.json). "
              "The 28 historical observations below retain their original rows and ranks.", ""]
    return lines


def render(data):
    lines = ["# Full results", "", "[README](../README.md) · [Quality](#model-quality) · [Language and task complexity](#language-and-task-complexity) ·",
             "[New capability tests](#complementary-capability-campaign-29-october-2026) · "
             "[Speed and memory](#speed-and-memory) · [Passages and other campaigns](leaderboard/other-benchmarks.md) ·",
             "[Proposed tool and model routing](INTENT_AND_MODEL_ROUTING.md)", "",
             "**28 historical model/runtime observations**, consolidated from the public frozen exports through 28 October 2026.",
             "Rows identify observations, not 28 independent model families. Repeated exports of the same sealed run are deduplicated;",
             "quantizations and devices remain separate. Rendering this page does not rerun or rescore models.", "",
             "**Exploratory evidence:** synthetic, agent-authored references and translations await human review.",
             "The ranking uses all 132 cases (train + calibration + test); the separate test column uses 66 cases.",
             "FR/EN translations form 66 families. Differences of a few answers do not establish a general model ranking.", "",
             "## What was actually tested?", "",
             "| Task | Common input and denominator | Status |", "|---|---|---|",
             "| Documentary text and choices | 76 context-dependent choices | Scored exploratory decisions |",
             "| Mathematics / chemistry | 28 / 28 constrained choices | Scored synthetic probes, not expert scientific qualification |",
             "| Clef Flash Q8 context, capabilities and physics | Separate 132-, 192- and 48-case packs | [Completed direct Metal campaign and D3 comparison](CLEF_FLASH_RESULTS_20261029.md); separate from the 28 historical rows |",
             "| First tool proposal | 24 search / statistics / fallback choices | Provisional agreement only; no tool execution; **0 semantically qualified cases** |",
             "| Physics | [48 synthetic choices](../datasets/physics-choice-v1/README.md), 24 FR/EN families | [Flash Q8/direct Metal: 39/48, test 32/36](PHYSICS_FLASH_RESULTS_20261029.md); reported separately, human review pending |",
             "| Passage ranking, relevance, support, answerability | Separate fixed-passage campaigns | [Full tables and coverage](leaderboard/other-benchmarks.md); [D3 Flash evidence observation](PASSAGE_FLASH_RESULTS_20261029.md) and [matched Clef comparison](PASSAGE_CLEF_RESULTS_20261029.md), reported separately |",
             "| Capability/tool-set, argument and fixed-observation choices | [192-case complementary pack](../datasets/capability-choice-v1/README.md) | [First D3 Flash Q8/Metal campaign and fresh context anchor](CAPABILITY_FLASH_RESULTS_20261029.md), reported separately from the 28 historical rows; no tool execution or product qualification |",
             "| Free-form plugin/MCP selection, complete execution loop, difficulty prediction, adaptive model routing | Future harness stages | **Not run**; [experiment design](INTENT_AND_MODEL_ROUTING.md) |",
             "| End-to-end RAG and generated-answer quality | No campaign qualified here | **Not run** |", ""]
    lines += render_capability(data["capability_campaign"])
    lines += ["## Model quality", "",
             "Each score is **correct / all cases** in its column, retaining failures in the denominator.",
             "Tool is **agreement / 24 provisional proposals**, not routing accuracy. Full scored/valid counts and separate",
             "`missing`, `unsupported`, `error`, `timeout`, and `abstain` counts are in the downloads.",
             "Equal all-case totals share a competition rank; row order within a tie is alphabetical by observation ID.", "",
             "| Rank | Model observation | Size¹ | Runtime² | All /132 | Test /66 | Text /76 | Math /28 | Chem /28 | Tool /24 |",
             "|---:|---|---|---|---:|---:|---:|---:|---:|---:|"]
    runtime_codes = {"historical_cpu": "CPU-H", "remote_api": "API", "apple_metal_native": "Metal",
                     "apple_mps": "MPS", "cpu_new": "CPU-N"}
    for row in data["observations"]:
        m, c, g = row["metadata"], row["context"]["counts"], row["context"]["groups"]
        lines.append(f"| {row['rank_all_splits']} | {m['display_name']} | {m['model_size']['label'] or 'NR'} | "
                     f"{runtime_codes[m['runtime_group']]} | {c['correct']} | {g['split']['test']['correct']} | "
                     f"{g['domain']['documentary']['correct']} | {g['domain']['mathematics']['correct']} | "
                     f"{g['domain']['chemistry']['correct']} | {row['tool_proposal']['counts']['agreement_count']} |")
    lines += ["", "¹ Sizes describe the observed checkpoint: exact tensor counts, nominal classes, and publisher declarations",
              "are distinguished in [metadata](leaderboard/model-metadata.json). A backbone count may exclude a separate readout;",
              "some counts include vision weights. **NR** means not reported in the selected public evidence, not zero.",
              "The historical 27B D3 is neither an Ultra nor a Turbo observation; neither variant was evaluated here.", "",
              "² CPU-H: historical Linux/WSL CPU runs (processor not identified here); API: remote service with unknown server hardware;",
              "Metal: native llama.cpp on Apple M5 Pro; MPS: official PyTorch pipeline on Apple M5 Pro;",
              "CPU-N: newer macOS CPU run. Runtime, readout, serializer, precision, and input lengths differ.", "",
              "## Language and task complexity", "",
              "D1/D2/D3 are authored context-task strata, **not predictions of difficulty or evidence that escalation helps**.",
              "A correct choice also does not prove that a plugin was executed or a useful answer generated.", "",
              "| Model observation | FR /66 | EN /66 | D1 /40 | D2 /40 | D3 /52 | Scored /132 | Tool valid /24 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in data["observations"]:
        g = row["context"]["groups"]
        values = [g["language"][key]["correct"] for key in ("fr", "en")] + [g["difficulty"][key]["correct"] for key in ("D1", "D2", "D3")]
        lines.append("| " + row["metadata"]["display_name"] + " | " + " | ".join(map(str, values)) +
                     f" | {row['context']['counts']['scored']} | {row['tool_proposal']['counts']['valid_decisions']} |")
    lines += ["", "## Speed and memory", "",
              "These are **context-choice adapter observations**, not controlled cross-hardware speed rankings.",
              "Latency includes the adapter's recorded boundary and successful calls only; cold initialization is separate.",
              "Remote latency includes its network/API path; server memory is unknown. One-pass p95 is descriptive, not a tail guarantee.",
              "[Repeated timing and stability](leaderboard/other-benchmarks.md#repeated-timing-and-stability) use separate campaigns.", "",
              "**RSS and GPU allocations are different measurements: never add them.** Neither establishes total unified-memory use.",
              "RSS below is worker peak for the context phase unless marked **S**, which is a sampled process-group peak over",
              "the native context + tool session. An allocation or peak is not a minimum-memory requirement; allow runtime/OS headroom.",
              "Metal/MPS observations used a 64 GiB Apple M5 Pro. CPU-H observations are not assumed to share controlled hardware.", "",
              "| Model observation | Runtime | Median ms | p95 ms | Timed /132 | Init ms | RSS GiB³ | GPU alloc GiB |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in data["observations"]:
        r, m = row["resources"], row["metadata"]
        session = r["session_process_group_peak_rss_mib"]
        rss = session if session is not None else r["worker_rss_mib"]["max"]
        gpu = r["sampled_gpu_allocated_peak_mib"]
        lines.append(f"| {m['display_name']} | {runtime_codes[m['runtime_group']]} | {number(r['adapter_ms']['median'])} | "
                     f"{number(r['adapter_ms']['p95'])} | {r['adapter_ms']['count']} | {number(r['initialization_ms'])} | "
                     f"{number(rss / 1024 if rss is not None else None, 2)}{' S' if session is not None else ''} | "
                     f"{number(gpu / 1024 if gpu is not None else None, 2)} |")
    lines += ["", "³ Worker RSS reporting coverage and the exact measurement scope are retained in the CSV/JSON.",
              "NR means unreported; GPU NR must not be read as zero. Sizes, weight-file sizes, RSS, and GPU allocation are different quantities.", "",
              "## Every task and downloadable data", "",
              "- [Model summary CSV](leaderboard/models.csv): all 28 observations, model sizes, runtimes, quality, latency, and separate resource measurements.",
              "- [Task breakdown CSV](leaderboard/task-breakdown.csv): every exported context task type and documentary subtype, domain, language, split, difficulty stratum, domain × language/split, plus tool-choice subgroups.",
              "- [Full structured results](leaderboard/results.json): identities, revisions, model/runtime settings, counts, statuses, all groups, source seals, and input-file SHA-256 hashes.",
              "- [Other benchmark results](leaderboard/other-benchmarks.md): full passage, support, answerability, length, repeated timing, and legacy pilot tables. These use different corpora/metrics and are not merged into one accuracy score.", "",
              "In the task CSV, `numerator` is correct choices or provisional agreement as named by `metric`.",
              "`scored_or_valid` and `total` retain coverage; blank subgroup status cells mean the source did not export those statuses.",
              "FR/EN pairs, passage-order variants, and repeated measurements remain correlated rather than independent evidence.", "",
              "## Provenance and reproduction", "",
              "The join reads only explicitly tracked public sources, validates the frozen historical composer and its hashes,",
              "checks duplicated observations and denominators, and binds separate memory observations to model identities/seals.",
              "It does not verify unavailable raw archives or confer human reference approval. Original campaign exports remain unchanged.", "",
              "```bash", "python3 scripts/build-full-results.py --check", "# After an intentional, reviewed public evidence/metadata update:",
              "python3 scripts/build-full-results.py --write", "```", "",
              "See the [protocol](PROTOCOL.md), [historical campaign archive](RESULTS_INDEX.md), and",
              "[planned intent, MCP-tool, and model-routing experiment](INTENT_AND_MODEL_ROUTING.md).", ""]
    return "\n".join(lines)


def outputs(data):
    models, tasks = flat_rows(data)
    return {"docs/RESULTS.md": render(data), "docs/leaderboard/models.csv": csv_text(models),
            "docs/leaderboard/task-breakdown.csv": csv_text(tasks),
            "docs/leaderboard/results.json": json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    try:
        generated = outputs(build())
        stale = []
        for relative, content in generated.items():
            path = ROOT / relative
            if args.write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="")
            elif not path.is_file() or path.read_bytes() != content.encode("utf-8"):
                stale.append(relative)
        require(not stale, "stale generated views: " + ", ".join(stale))
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as exc:
        print(f"Full results invalid: {exc}", file=sys.stderr)
        return 2
    print("Full results: 28 public observations; views " + ("written" if args.write else "current"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
