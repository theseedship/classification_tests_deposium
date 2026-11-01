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
import posixpath
import re
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
D3LITE_MACOS = EVIDENCE + "d3-lite-macos-20261030/analysis.json"
VELA03_MACOS = EVIDENCE + "vela2-03-macos-20261030/analysis.json"
D3NANO_MACOS = EVIDENCE + "d3-nano-macos-20261031/analysis.json"
D3MINI_MACOS = EVIDENCE + "d3-mini-macos-20261031/analysis.json"
CHOICE_EPISODES = EVIDENCE + "choice-episodes-20261031/analysis.json"
CHOICE_EPISODES_REPORT = "TOOL_EPISODES_CHOICE_PILOT_RESULTS_20261031.md"
FACADE = EVIDENCE + "facade-routing-20261101/analysis.json"
FACADE_REPORT = "FACADE_ROUTING_RESULTS_20261101.md"
FACADE_ROUTER = ("FacadeRouterReplay", "Production router · private replay")
FACADE_DATASET_SHA256 = "03f30a621298ecb45f78aefc50e048b6737024245a49a347dd982e28bca72c18"
# Q8 Metal rows on the easy tier, and every candidate on the advanced and complex tiers.
FACADE_EASY_METAL = EVIDENCE + "facade-routing-tiers-20261101/easy-metal.json"
FACADE_TIERS = {"advanced": (EVIDENCE + "facade-routing-tiers-20261101/advanced.json",
                             "42364fed544e842a02f68314242b767a7c3fae0dde8505bd66499063930337f3"),
                "complex": (EVIDENCE + "facade-routing-tiers-20261101/complex.json",
                            "389d362dafa7696b3cb4fb18f0d44a1ae98569a1ae661133f7ec9db44b6930d6")}
FACADE_TIERS_REPORT = "FACADE_ROUTING_TIERS_RESULTS_20261101.md"
# Deployment variants of the small D3 models: Q8 and Q4 GGUF on Metal, Mirai's 4-bit D3 Flash on Uzu.
DEPLOYMENT = EVIDENCE + "deployment-variants-20261101/analysis.json"
DEPLOYMENT_REPORT = "DEPLOYMENT_VARIANTS_RESULTS_20261101.md"
CAPABILITY = EVIDENCE + "capability-flash-20261029/analysis.json"
LOCAL_POLICY = (EVIDENCE + "local-tool-policy-20261030/analysis.json",
                EVIDENCE + "local-tool-policy-v2-train-20261030/analysis.json",
                EVIDENCE + "local-tool-policy-heldout-20261030/analysis.json",
                EVIDENCE + "local-tool-policy-v2-train-cache-off-20261030/analysis.json",
                EVIDENCE + "local-tool-policy-heldout-002-20261030/analysis.json")
NATIVE_SESSION = EVIDENCE + "native-model-comparison-20261016/native-sessions.json"
GLICLASS_SESSION = EVIDENCE + "gliclass-model-comparison-20261017/gliclass-session.json"
CAMPAIGN_MODULE = "scripts/consolidated-campaigns.py"
OTHER_GUIDE = "docs/leaderboard/other-benchmarks.md"
OTHER_SOURCES = {"passage_order": EVIDENCE + "passage-order-control-20261015/analysis.json",
                 "length": EVIDENCE + "length-comparison-20261004/analysis.json",
                 "repeated_timing": EVIDENCE + "timing-comparison-20261004/analysis.json"}
RECENT_INPUTS = (CAMPAIGN_MODULE, EVIDENCE + "clef-flash-20261029/analysis.json",
                 EVIDENCE + "physics-flash-20261029/analysis.json",
                 EVIDENCE + "passage-flash-20261029/analysis.json",
                 EVIDENCE + "passage-clef-flash-20261029/analysis.json",
                 EVIDENCE + "passage-cpu-20261015/analysis.json",
                 EVIDENCE + "passage-jev-20261015/analysis.json",
                 "profiles/d3-flash-q8-assets.json", "profiles/clef-flash-q8-assets.json",
                 EVIDENCE + "d3-lite-macos-20261030/capability.json", EVIDENCE + "d3-lite-macos-20261030/physics.json",
                 "profiles/d3-lite-assets.json", "profiles/d3-lite-macos-cpu.json", "runtimes/d3-macos/runtime.lock",
                 "docs/D3_LITE_MACOS_RESULTS_20261030.md",
                 EVIDENCE + "vela2-03-macos-20261030/capability.json", EVIDENCE + "vela2-03-macos-20261030/physics.json",
                 "profiles/vela2-03-assets.json", "profiles/vela2-03-macos-cpu.json", "docs/VELA2_03_MACOS_RESULTS_20261030.md",
                 EVIDENCE + "d3-nano-macos-20261031/capability.json", EVIDENCE + "d3-nano-macos-20261031/capability-002.json",
                 EVIDENCE + "d3-nano-macos-20261031/physics.json", "profiles/d3-nano-assets.json", "profiles/d3-nano-macos-cpu.json",
                 "profiles/d3-nano-macos-cpu-capability.json", "docs/D3_NANO_MACOS_RESULTS_20261031.md",
                 EVIDENCE + "d3-mini-macos-20261031/context.json", EVIDENCE + "d3-mini-macos-20261031/capability.json",
                 EVIDENCE + "d3-mini-macos-20261031/physics.json", "profiles/d3-mini-assets.json", "profiles/d3-mini-macos-cpu.json",
                 "profiles/d3-mini-macos-cpu-capability.json", "docs/D3_MINI_MACOS_RESULTS_20261031.md",
                 EVIDENCE + "choice-episodes-20261031/analysis.json", "docs/TOOL_EPISODES_CHOICE_PILOT_RESULTS_20261031.md",
                 "profiles/d3-lite-macos-choice-episodes.json", "profiles/vela2-03-macos-choice-episodes.json",
                 "profiles/d3-nano-macos-choice-episodes.json", "profiles/d3-mini-macos-choice-episodes.json",
                 "profiles/vela2-03-macos-cpu.json",
                 "docs/PASSAGE_CPU_RESULTS_20261015.md", "docs/PASSAGE_JEV_RESULTS_20261015.md",
                 "docs/PASSAGE_FLASH_RESULTS_20261029.md", "docs/PASSAGE_CLEF_RESULTS_20261029.md",
                 EVIDENCE + "passage-small-cpu-20261031/d3-lite.json", EVIDENCE + "passage-small-cpu-20261031/vela2-03.json",
                 EVIDENCE + "passage-small-cpu-20261031/d3-nano.json", EVIDENCE + "passage-small-cpu-20261031/d3-mini.json",
                 "docs/PASSAGE_SMALL_CPU_RESULTS_20261031.md", "docs/PASSAGE_SMALL_CPU_PROTOCOL_20261031.md",
                 EVIDENCE + "facade-routing-20261101/analysis.json", "docs/FACADE_ROUTING_RESULTS_20261101.md",
                 "docs/FACADE_ROUTING_DESIGN_20261031.md",
                 EVIDENCE + "d3-small-gguf-metal-20261101/d3-lite.json", EVIDENCE + "d3-small-gguf-metal-20261101/d3-nano.json",
                 EVIDENCE + "d3-small-gguf-metal-20261101/d3-mini.json", "docs/D3_SMALL_GGUF_METAL_RESULTS_20261101.md",
                 "docs/D3_SMALL_GGUF_GPU_PROTOCOL_20261101.md", "profiles/d3-lite-q8-assets.json",
                 "profiles/d3-nano-q8-assets.json", "profiles/d3-mini-q8-assets.json",
                 EVIDENCE + "facade-routing-tiers-20261101/easy-metal.json", EVIDENCE + "facade-routing-tiers-20261101/advanced.json",
                 EVIDENCE + "facade-routing-tiers-20261101/complex.json", "docs/FACADE_ROUTING_TIERS_RESULTS_20261101.md",
                 EVIDENCE + "deployment-variants-20261101/analysis.json", "docs/DEPLOYMENT_VARIANTS_RESULTS_20261101.md",
                 "profiles/d3-mini-q4-assets.json", "profiles/d3-flash-m-uzu-assets.json")
# Constant majority-class answer on passage-evidence-v1, rotation 0 (dataset sha pinned in campaigns).
PASSAGE_MAJORITY = {"relevance": ("grade 1", 224, 512), "support": ("`insufficient`", 584, 768),
                    "answerability": ("`answerable`", 88, 128)}
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


def facade_join(run, observations, inputs):
    """A facade run joins an observation only with the same weights and runtime, never by label alone."""
    if run["kind"] != "classifier":
        return
    target = observations.get(run["label"])
    identity = run["identity"]
    if "backend" in identity:
        # GPU rows: the same GGUF file, native binary and backend as their context observation.
        runtime = (target or {}).get("identity", {}).get("runtime", {})
        require(target is not None and target["identity"].get("model_assets_sha256") == identity["model_sha256"]
                and runtime.get("binary_sha256") == identity["binary_sha256"] and runtime.get("backend") == identity["backend"],
                f"facade routing: identity join failed for {run['label']}")
        inputs.read(identity["assets_manifest"])
    else:
        require(target is not None and target["identity"].get("model_revision") == identity["model_revision"]
                and identity.get("runtime_lock_sha256") is not None
                and target["identity"].get("hashes", {}).get("runtime_lock_sha256") == identity["runtime_lock_sha256"],
                f"facade routing: identity join failed for {run['label']}")
        inputs.read(identity["profile"])


def build(root=ROOT):
    inputs = PublicInputs(root)
    composer = load_composer(inputs)
    frozen, _ = composer.historical(inputs.root / HISTORICAL)
    current = inputs.load(CPU)
    base, routes, _ = composer.compose(current, frozen)
    require(len(base) == 22, "historical roster changed")
    for path, selected in ((NATIVE, {"D3Q4", "D3FlashQ4", "D3FlashQ8", "EosQ8"}),
                           (GLICLASS, {"GLiClass9B"}), (FAST, {"Vela3Fast"}), (D3LITE_MACOS, {"D3liteMacos"}),
                           (VELA03_MACOS, {"Vela03Macos"}), (D3NANO_MACOS, {"D3nanoMacos"}),
                           (D3MINI_MACOS, {"D3miniMacos"})):
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
    inputs.read(CAMPAIGN_MODULE)
    spec = importlib.util.spec_from_file_location("public_campaigns", inputs.root / CAMPAIGN_MODULE)
    campaigns = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(campaigns)
    require(set(base) == set(routes) and set(metadata["observations"]) == set(base) | campaigns.NEW_CONTEXT_IDS,
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
        require(len({row[phase]["source"]["seal_sha256"] for row in rows}) == len(rows),
                f"duplicate observation seals: {phase}")
        require(len({row[phase]["source"]["dataset_sha256"] for row in rows}) == 1,
                f"mixed datasets: {phase}")
    complementary = capability_campaign(inputs, base["D3FlashQ8"], metadata["observations"]["D3FlashQ8"])
    recent_context, campaign_rows = campaigns.Campaigns(inputs, require).load(metadata["observations"], complementary)
    rows.extend(recent_context)
    rows.sort(key=lambda row: (-row["context"]["counts"]["correct"], row["id"]))
    for row in rows:
        if row["id"] not in campaigns.NEW_CONTEXT_IDS:
            row["historical_rank_all_splits"] = row["rank_all_splits"]
        row["rank_all_splits"] = 1 + sum(r["context"]["counts"]["correct"] > row["context"]["counts"]["correct"] for r in rows)
        row["rank_test_splits"] = 1 + sum(r["context"]["groups"]["split"]["test"]["correct"] > row["context"]["groups"]["split"]["test"]["correct"] for r in rows)
    require(len({r["context"]["source"]["seal_sha256"] for r in rows}) == len(rows), "duplicate observation seals: consolidated context")
    other_guide = inputs.read(OTHER_GUIDE).decode("utf-8")
    def summary_only(value):
        if isinstance(value, dict):
            return {k: summary_only(v) for k, v in value.items() if k not in
                    {"rows", "replacement_predictions", "complement_predictions", "full_pool_answerability_gate"}}
        if isinstance(value, list):
            return [summary_only(v) for v in value]
        return value
    others = {}
    for key, path in OTHER_SOURCES.items():
        summary = summary_only(inputs.load(path))
        if key == "length":
            for model in summary["models"].values():
                model["groups"] = {"target": model["groups"]["target"]}
        elif key == "passage_order":
            summary.pop("by_rotation", None)
            summary.pop("original_rotation_zero", None)
        others[key] = {"source": path, "summary": summary,
                       "scope": "Published overall, per-target or balanced-ranking summaries; detailed cross-groups, rotations and per-case rows remain in the linked source"}
    coverage = build_coverage(rows, campaign_rows, others, inputs)
    names = {r["id"]: r["metadata"]["display_name"] for r in rows}
    choice_episodes = []
    for run in inputs.load(CHOICE_EPISODES)["runs"]:
        choice_episodes.append({"observation": run["label"], "model": names[run["label"]], "counts": run["counts"],
                                "stages": run["stages"], "execution": run["execution"],
                                "chosen_position": run["chosen_position"], "report": CHOICE_EPISODES_REPORT})
    for row in choice_episodes:
        row["rank_all"] = 1 + sum(o["counts"]["all"]["procedure_correct_cases"] > row["counts"]["all"]["procedure_correct_cases"] for o in choice_episodes)
        row["rank_test"] = 1 + sum(o["counts"]["test"]["procedure_correct_cases"] > row["counts"]["test"]["procedure_correct_cases"] for o in choice_episodes)
    choice_episodes.sort(key=lambda r: (r["rank_all"], r["model"]))
    facade = inputs.load(FACADE)
    facade_names = {**names, FACADE_ROUTER[0]: FACADE_ROUTER[1]}
    easy_metal = inputs.load(FACADE_EASY_METAL)
    require(easy_metal.get("pack") == "facade-routing-v1" and easy_metal["dataset_sha256"] == FACADE_DATASET_SHA256
            and easy_metal["router"]["identity"] == facade["router"]["identity"], "facade routing: Metal export uses another router replay")
    facade_routing = [{"observation": run["label"], "model": facade_names[run["label"]], "kind": run["kind"],
                       "counts": run["counts"], "paired": run.get("paired_with_router"),
                       "inference_ms": run.get("inference_ms"),
                       "report": FACADE_TIERS_REPORT if run in easy_metal["runs"] else FACADE_REPORT}
                      for run in (facade["router"], *facade["runs"], *easy_metal["runs"])]
    for row in facade_routing:
        row["rank_all"] = 1 + sum(o["counts"]["all"]["correct"] > row["counts"]["all"]["correct"] for o in facade_routing)
        row["rank_test"] = 1 + sum(o["counts"]["by_split"]["test"]["correct"] > row["counts"]["by_split"]["test"]["correct"]
                                   for o in facade_routing)
    facade_routing.sort(key=lambda r: (r["rank_all"], r["model"]))
    tiers = {row["observation"]: {"model": row["model"], "easy": row["counts"]} for row in facade_routing}
    for tier, (path, digest_) in FACADE_TIERS.items():
        data_ = inputs.load(path)
        require(data_.get("pack") == f"facade-routing-{tier}-v1" and data_["dataset_sha256"] == digest_ and data_["cases"] == 96
                and data_["router"]["identity"]["router_source_revision"] == facade["router"]["identity"]["router_source_revision"],
                f"facade tiers: changed {tier} pack or router revision")
        observations = {r["id"]: r for r in rows}
        for run in (data_["router"], *data_["runs"]):
            require(run["label"] in tiers, f"facade tiers: {run['label']} has no easy-tier row")
            facade_join(run, observations, inputs)
            tiers[run["label"]][tier] = run["counts"]
            tiers[run["label"]].setdefault("latency", run.get("inference_ms"))
    inputs.read("docs/" + FACADE_TIERS_REPORT)
    facade_tiers = [{"observation": k, **v} for k, v in tiers.items() if all(t_ in v for t_ in FACADE_TIERS)]
    for tier in ("easy", *FACADE_TIERS):
        for row in facade_tiers:
            row["rank_" + tier] = 1 + sum(o[tier]["all"]["correct"] > row[tier]["all"]["correct"] for o in facade_tiers)
            row["rank_test_" + tier] = 1 + sum(o[tier]["by_split"]["test"]["correct"] > row[tier]["by_split"]["test"]["correct"]
                                               for o in facade_tiers)
    facade_tiers.sort(key=lambda r: (r["rank_complex"], r["model"]))
    deployment = inputs.load(DEPLOYMENT)
    require(deployment.get("schema_version") == "deposium.deployment-variants-public/v1"
            and set(deployment["variants"]) == {"D3miniQ8Metal", "D3miniQ4Metal", "D3FlashMUzu"},
            "deployment variants: changed schema or variants")
    for variant in deployment["variants"].values():
        inputs.read(variant["assets_manifest"])
    inputs.read("docs/" + DEPLOYMENT_REPORT)
    inputs.read("scripts/build-full-results.py")
    coverage["sources_sha256"] = dict(sorted(inputs.hashes.items()))
    return {"schema_version": "deposium.public-results/v1", "observations": rows,
            "campaigns": campaign_rows, "coverage": coverage, "historical_context_observations": len(base),
            "choice_episodes": choice_episodes, "facade_routing": facade_routing, "facade_tiers": facade_tiers,
            "deployment": deployment,
            "other_campaigns": others, "other_benchmarks_markdown": other_guide,
            "capability_campaign": complementary,
            "scope": "aggregate_presentation_only_no_inference_or_raw_archive_verification",
            "reference_review": "agent_only_pending_human",
            "ranking": "Competition rank by correct/132, all splits; ties ordered by observation ID",
            "sources_sha256": dict(sorted(inputs.hashes.items()))}


COVERAGE_TASKS = (
    ("context", "Context", 132, "context-choice-v1; all splits; test=66"),
    ("tool_proposal", "Tool proposal", 24, "mastra-read-pilot-v0; provisional agreement; zero qualified cases"),
    ("capability", "Capability", 192, "capability-choice-v1; four supplied proposals; test=96"),
    ("physics", "Physics", 48, "physics-choice-v1; calibration+test; test=36"),
    ("choice_episodes", "Episodes (choice)", 32,
     "tool-episodes-choice-v1; executed fixture tools; closed-choice step menu; train 20 + test 12; procedure-correct cases"),
    ("facade_routing", "Facade routing", 80,
     "facade-routing-v1; eight tool categories including none; train 16 + calibration 16 + test 48; compared with a private router replay"),
    ("passage_relevance", "Relevance R0", 512, "passage-evidence-v1; test; rotation 0; 128 pools"),
    ("passage_support", "Support R0", 768, "passage-evidence-v1; test; rotation 0; 128 pools"),
    ("passage_answerability", "Answerability R0", 128, "passage-evidence-v1; test; rotation 0; 128 pools"),
    ("passage_relevance_four_rotations", "Relevance R0–3", 2048,
     "passage-evidence-v1; four replayed rotations; 512 pools; not independent calls"),
    ("passage_ranking", "Ranking R0–3", 512,
     "passage-evidence-v1; four balanced rotations; nDCG@1 defined/eligible=480/480; 512 total pools"),
    # Generated-JSON tool tasks: a different candidate output path from the closed
    # choices above. Denominators join the TRAIN canary and the held-out TEST pack.
    ("tool_discovery", "Discovery (JSON)", 10,
     "tool-policy-canary-v1 train 2 + tool-policy-heldout-v1 test 8; generated shortlist/selection; prompt v2"),
    ("tool_arguments", "Arguments (JSON)", 6,
     "tool-policy-canary-v1 train 2 + tool-policy-heldout-v1 test 4; generated arguments, actual lookup/sum; prompt v2"),
    ("tool_episodes", "Episodes (JSON)", 18,
     "tool-policy-canary-v1 train 6 + tool-policy-heldout-v1 test 12; generated actions, actual bounded feedback; prompt v2"),
)
# Generated-JSON columns; every other task belongs to the classifier matrix. Partition by ID, never by position.
GENERATED_TASKS = {"tool_discovery", "tool_arguments", "tool_episodes"}
ISSUES = "https://github.com/theseedship/classification_tests_deposium/issues/"


LOCAL_POLICY_EXPECTED = (
    # (relative path, split, eligible, collection complete, prompt version, report)
    (LOCAL_POLICY[0], "train", 10, True, "deposium.local-tool-policy-prompt/v1", "LOCAL_TOOL_POLICY_RESULTS_20261030.md"),
    (LOCAL_POLICY[1], "train", 10, True, "deposium.local-tool-policy-prompt/v2", "LOCAL_TOOL_POLICY_V2_RESULTS_20261030.md"),
    (LOCAL_POLICY[2], "test", 24, False, "deposium.local-tool-policy-prompt/v2", "LOCAL_TOOL_POLICY_V2_RESULTS_20261030.md"),
    (LOCAL_POLICY[3], "train", 10, True, "deposium.local-tool-policy-prompt/v2", "LOCAL_TOOL_POLICY_HELDOUT_RESULTS_20261030.md"),
    (LOCAL_POLICY[4], "test", 24, True, "deposium.local-tool-policy-prompt/v2", "LOCAL_TOOL_POLICY_HELDOUT_RESULTS_20261030.md"),
)


def local_policy_observation(source, split, eligible, complete, prompt, report):
    """Validate one public local tool-policy aggregate; both aggregate layouts are accepted."""
    require(source.get("schema_version") == "deposium.local-tool-policy-results/v1"
            and source.get("review") == "agent_only_pending_human"
            and source.get("qualification") in (f"model_isolated_generated_json_{split}",
                                                 "model_isolated_generated_json_train_canary" if split == "train" else None)
            and source.get("prompt_version", "deposium.local-tool-policy-prompt/v1") == prompt,
            "unexpected local tool-policy aggregate")
    coverage, tasks = source["coverage"], source["results"]["by_task"]
    scored_of = lambda cell: cell.get("scored", cell["eligible"])
    require(coverage["eligible_cases"] == eligible > 0
            and 0 < coverage["scored_cases"] <= eligible
            and 0 <= coverage["passed_cases"] <= coverage["scored_cases"]
            and coverage.get("collection_complete", True) is complete
            and (coverage["scored_cases"] == eligible) is complete
            and sum(coverage["counts_by_status"].values()) == eligible
            and coverage["counts_by_status"]["ok"] >= coverage["scored_cases"]
            and sum(t["eligible"] for t in tasks.values()) == eligible
            and sum(scored_of(t) for t in tasks.values()) == coverage["scored_cases"]
            and sum(t["correct"] for t in tasks.values()) == coverage["passed_cases"],
            "inconsistent local tool-policy denominators")
    if not complete:
        require(coverage.get("stop_reason") in ("rss_guard", "host_reserve", "time_limit", "native_supervision_lost")
                and len(coverage.get("unobserved_cases", [])) == eligible - coverage["counts_by_status"]["ok"],
                "partial local tool-policy aggregate without an accounted stop")
    cells = ", ".join(f"{tasks[n]['correct']}/{scored_of(tasks[n])} {n}" for n in ("discovery", "arguments", "episodes"))
    text = f"{coverage['passed_cases']}/{coverage['scored_cases']} scored of {eligible} ({cells})"
    if not complete:
        text += f", {eligible - coverage['scored_cases']} unobserved after `{coverage['stop_reason']}`"
    return {"report": report, "passed": coverage["passed_cases"], "scored": coverage["scored_cases"],
            "eligible": eligible, "complete": complete, "text": text,
            "by_task": {n: {"correct": tasks[n]["correct"], "scored": scored_of(tasks[n]), "eligible": tasks[n]["eligible"]}
                        for n in ("discovery", "arguments", "episodes")},
            "all_ok": coverage["counts_by_status"]["ok"] == eligible}


def local_policy_observations(inputs):
    sources = [inputs.load(path) for path, *_ in LOCAL_POLICY_EXPECTED]
    rows = [local_policy_observation(source, *rest) for source, (_, *rest) in zip(sources, LOCAL_POLICY_EXPECTED)]
    named = dict(zip(("train_v1", "train_v2", "heldout", "train_v2_cache_off", "heldout_002"), rows))
    # The cache amendment is admitted as generation-neutral only if the TRAIN control matches.
    require(named["train_v2"]["passed"] == named["train_v2_cache_off"]["passed"]
            and sources[3]["envelope"].get("host_prompt_cache_mib") == 0
            and sources[4]["envelope"].get("host_prompt_cache_mib") == 0
            and "host_prompt_cache_mib" not in sources[1]["envelope"],
            "prompt-cache amendment control does not match")
    return named


def coverage_cell(counts, total, source=None, *, metric="correct_choice", statuses=None):
    """Execution coverage is independent of accuracy and reference approval."""
    empty = {"status": "not_run", "source": None, "evidence_present": False,
             "scored_or_valid": None, "total": total, "numerator": None,
             "metric": metric, "outcomes": None, "review_pending": True}
    if counts is None:
        return empty
    n = counts["valid_decisions" if metric == "provisional_agreement" else "scored"]
    correct = counts["agreement_count" if metric == "provisional_agreement" else "correct"]
    outcomes = statuses if statuses is not None else counts["statuses"]
    require(counts["total"] == total and all(type(v) is int for v in (n, correct))
            and 0 <= correct <= n <= total, "coverage: inconsistent denominator")
    require(set(outcomes) == STATUS_KEYS and all(type(v) is int and v >= 0 for v in outcomes.values())
            and sum(outcomes.values()) == total and n == outcomes["ok"] + outcomes["abstain"],
            "coverage: inconsistent outcomes")
    require(source is not None, "coverage: observed result lacks a source")
    require(n > 0 or outcomes["missing"] == total, "coverage: zero scored campaign")
    return {**empty, "status": "complete" if n == total else "partial" if n else "not_run",
            "source": source, "evidence_present": True, "scored_or_valid": n,
            "numerator": correct if n else None, "outcomes": dict(outcomes)}


def build_coverage(observations, campaigns, others, inputs):
    """Join exact public observation identities; never fill a gap by model name."""
    totals = {key: total for key, _, total, _ in COVERAGE_TASKS}
    policy = local_policy_observations(inputs)
    def unobserved():
        return {key: coverage_cell(None, total, metric="provisional_agreement" if key == "tool_proposal"
                                   else "ndcg@1" if key == "passage_ranking"
                                   else "case_pass" if key.startswith("tool_") or key == "choice_episodes" else "correct_choice")
                for key, total in totals.items()}
    by_id = {}
    for row in observations:
        meta = row["metadata"]
        cells = unobserved()
        cells["context"] = coverage_cell(row["context"]["counts"], 132, meta["source_analysis"])
        if row["tool_proposal"] is not None:
            tool = row["tool_proposal"]
            cells["tool_proposal"] = coverage_cell(tool["counts"], 24, meta["source_analysis"],
                                                  metric="provisional_agreement", statuses=tool["statuses"])
        by_id[row["id"]] = {"id": row["id"], "model": meta["display_name"],
                            "size": meta["model_size"]["label"], "runtime": meta["runtime_group"],
                            "context_observation": True, "generative_observation": False, "cells": cells}

    # These are separate runtime fingerprints, not additional context models.
    supplemental = (
        ("D3litePassage", "D3 lite · CPU passage session", "0.853B backbone", "historical_cpu"),
        ("Jev114", "Jev 1.14 · HTTP API", "Unreported", "remote_api"),
        ("BGEPassage", "BGE v2-m3 · INT8 CPU", "Unreported", "native_cpu_reranker"),
        ("D3liteBGE", "D3 lite + BGE tie-break · CPU", "Two-model method", "offline_ranking_projection"),
        ("Jev114BGE", "Jev 1.14 + BGE tie-break", "Two-model method", "offline_ranking_projection"),
    )
    for key, model, size, runtime in supplemental:
        by_id[key] = {"id": key, "model": model, "size": size, "runtime": runtime,
                      "context_observation": False, "generative_observation": False,
                      "cells": unobserved()}
    # One generative candidate on the generated-JSON tasks: the complete prompt-v2
    # observations (TRAIN control with the cache amendment, held-out attempt 002).
    # Per-task statuses are exact only because every case in both archives is `ok`.
    train, test = policy["train_v2_cache_off"], policy["heldout_002"]
    require(train["all_ok"] and test["all_ok"] and train["complete"] and test["complete"],
            "coverage: generative cells require complete all-ok observations")
    generative = {"id": "QwenToolPolicyV2", "model": "Qwen3-4B Instruct 2507 · Q8 Metal · generated JSON, prompt v2",
                  "size": "4B class", "runtime": "native_metal_generated_json",
                  "context_observation": False, "generative_observation": True, "cells": unobserved()}
    for task, name in (("tool_discovery", "discovery"), ("tool_arguments", "arguments"), ("tool_episodes", "episodes")):
        a, b = train["by_task"][name], test["by_task"][name]
        total = a["eligible"] + b["eligible"]
        counts = {"total": total, "scored": a["scored"] + b["scored"], "correct": a["correct"] + b["correct"],
                  "statuses": {**{k: 0 for k in STATUS_KEYS}, "ok": total}}
        generative["cells"][task] = coverage_cell(counts, totals[task], LOCAL_POLICY[3] + " + " + LOCAL_POLICY[4],
                                                  metric="case_pass")
    by_id[generative["id"]] = generative
    context_ids = {r["id"]: r for r in observations}
    cpu = inputs.load(EVIDENCE + "passage-cpu-20261015/analysis.json")
    require(all(cpu["choice_model"][key] == context_ids["D3lite"]["identity"][key]
                for key in ("model_repo_id", "model_revision")),
            "coverage: D3-lite passage model identity mismatch")
    require(cpu["choice_model"]["identity_sha256"] != context_ids["D3lite"]["identity"]["identity_sha256"],
            "coverage: D3-lite passage/context identity boundary changed; review join")
    for row in campaigns:
        target = "D3litePassage" if row["observation"] == "D3lite" else row["observation"]
        require(target in by_id and row["task"] in totals, "coverage: unknown campaign observation/task")
        if target in {"D3FlashQ8Upstream", "ClefFlashQ8"}:
            expected = context_ids[target]["identity"]
            identity = row.get("model_identity", row["identity"])
            require(all(identity.get(k) == expected.get(k) for k in
                        ("model_repo_id", "model_revision", "model_assets_sha256"))
                    and all(identity.get("runtime", {}).get(k) == v for k, v in expected["runtime"].items()),
                    f"coverage: campaign/context runtime identity mismatch: {target}/{row['task']}")
        cell = by_id[target]["cells"][row["task"]]
        require(not cell["evidence_present"], "coverage: duplicate task observation")
        by_id[target]["cells"][row["task"]] = coverage_cell(row["counts"], totals[row["task"]], row["source"])

    # Closed-choice executed episodes: joined to a context observation only when the
    # inner model revision and runtime lock are those of that observation's runtime.
    episodes = inputs.load(CHOICE_EPISODES)
    require(episodes.get("schema_version") == "deposium.choice-episodes-public/v1"
            and episodes.get("reference_review") == "agent_only_pending_human", "choice episodes: changed qualification")
    inputs.read("docs/" + CHOICE_EPISODES_REPORT)
    for run in episodes["runs"]:
        target = context_ids.get(run["label"])
        require(target is not None and target["identity"].get("model_revision") == run["identity"]["model_revision"],
                f"choice episodes: identity join failed for {run['label']}")
        inputs.read(run["identity"]["profile"])
        inputs.read(run["identity"]["inner_profile"])
        c = run["counts"]["all"]
        statuses = {**{k: 0 for k in STATUS_KEYS}, **c["statuses"]}
        cell = by_id[run["label"]]["cells"]["choice_episodes"]
        require(not cell["evidence_present"], "choice episodes: duplicate observation")
        by_id[run["label"]]["cells"]["choice_episodes"] = coverage_cell(
            {"total": c["total_cases"], "scored": statuses["ok"] + statuses["abstain"], "correct": c["procedure_correct_cases"],
             "statuses": statuses}, totals["choice_episodes"], CHOICE_EPISODES, metric="case_pass")

    # Facade routing: classifier rows join their context observation by model revision; the
    # production router is a separate private-replay row with only this cell.
    facade = inputs.load(FACADE)
    require(facade.get("schema_version") == "deposium.facade-routing-public/v1"
            and facade.get("dataset_sha256") == FACADE_DATASET_SHA256 and facade.get("cases") == 80
            and facade["router"]["label"] == FACADE_ROUTER[0] and facade["router"]["kind"] == "private_router_replay",
            "facade routing: changed pack, schema or router row")
    inputs.read("docs/" + FACADE_REPORT)
    by_id[FACADE_ROUTER[0]] = {"id": FACADE_ROUTER[0], "model": FACADE_ROUTER[1], "size": "Deterministic rules",
                               "runtime": "private_replay", "context_observation": False,
                               "generative_observation": False, "router_observation": True, "cells": unobserved()}
    easy_metal = inputs.load(FACADE_EASY_METAL)
    sourced = [(run, FACADE) for run in (facade["router"], *facade["runs"])] + [(run, FACADE_EASY_METAL) for run in easy_metal["runs"]]
    for run, source in sourced:
        facade_join(run, context_ids, inputs)
        c = run["counts"]["all"]
        statuses = {**{k: 0 for k in STATUS_KEYS}, **c["statuses"]}
        require(c["total"] == 80 and sum(statuses.values()) == 80, f"facade routing: denominator for {run['label']}")
        require(not by_id[run["label"]]["cells"]["facade_routing"]["evidence_present"], "facade routing: duplicate observation")
        by_id[run["label"]]["cells"]["facade_routing"] = coverage_cell(
            {"total": 80, "scored": statuses["ok"] + statuses["abstain"], "correct": c["correct"], "statuses": statuses},
            totals["facade_routing"], source)

    # Ranking is a distinct task, including derived class-order and tie-break methods.
    order = others["passage_order"]["summary"]
    jev_path = EVIDENCE + "passage-jev-20261015/analysis.json"
    jev = inputs.load(jev_path)
    require(order["source"]["choice_seal_sha256"] == cpu["source"]["choice_seal_sha256"],
            "coverage: ranking/classification source mismatch")
    require(jev["jev_http"]["returned_model"] == "jev-1.14.0"
            and context_ids["Jev"]["identity"]["model_id"] == "jev-1.13.0",
            "coverage: Jev version boundary changed; review join")
    require(order["baseline_profile"]["running_binary_sha256"] == jev["baseline_profile"]["cpu_binary_sha256"]
            and order["source"]["balanced_baseline_seal_sha256"] == jev["source"]["balanced_baseline_seal_sha256"],
            "coverage: ranking baseline source mismatch")
    for data in (order, jev):
        require(data["dataset_sha256"] == cpu["dataset_sha256"] and data["cases"] == 512
                and data["rotations"] == [0, 1, 2, 3] and data["families"] == 8 and data["split"] == "test",
                "coverage: ranking protocol mismatch")
    replay = order["relevance_scores"]
    numerator = replay["accuracy_over_all"] * replay["total_cases"]
    require(type(numerator) in (int, float) and math.isfinite(numerator)
            and abs(numerator - round(numerator)) < 1e-9, "coverage: nonintegral replay numerator")
    by_id["D3litePassage"]["cells"]["passage_relevance_four_rotations"] = coverage_cell(
        {"correct": round(numerator), "scored": replay["scored_cases"], "total": replay["total_cases"],
         "statuses": replay["counts_by_status"]}, 2048, others["passage_order"]["source"])
    for target, data, method, source in (
        ("D3litePassage", order, "replacement", others["passage_order"]["source"]),
        ("BGEPassage", order, "baseline", others["passage_order"]["source"]),
        ("D3liteBGE", order, "complement", others["passage_order"]["source"]),
        ("Jev114", jev, "replacement", jev_path), ("Jev114BGE", jev, "complement", jev_path),
    ):
        score = data["rankings"][method]
        counts = {"correct": 0, "scored": score["scored_cases"], "total": score["total_cases"],
                  "statuses": score["counts_by_status"]}
        cell = coverage_cell(counts, 512, source, metric="ndcg@1")
        metric = score["metrics"]["ndcg@1"]
        require(type(metric["defined_cases"]) is int and type(metric["eligible_cases"]) is int
                and 0 < metric["defined_cases"] <= metric["eligible_cases"] == 480
                and metric["defined_cases"] <= score["scored_cases"]
                and metric["total_cases"] == 512, "coverage: ranking metric denominator mismatch")
        value = metric["mean_over_eligible_missing_zero"]
        require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
                "coverage: invalid ranking metric")
        cell.update(numerator=None, metric_value=value, metric_defined=metric["defined_cases"],
                    metric_eligible=metric["eligible_cases"])
        by_id[target]["cells"]["passage_ranking"] = cell

    harness = [
        ("closed_choices", "Closed context, first-tool, capability and physics choices", "implemented",
         "Observed only on supplied alternatives; tool/24 remains provisional and executes no tool.", []),
        ("passage_tasks", "Fixed-pool relevance, support, answerability and ranking", "implemented",
         "Separate rotation/metric scopes above; no live retrieval or final answers.", []),
        ("task_contract", "Versioned task contract beyond supplied proposals", "fixture_only",
         "[Bounded contract](TOOL_PLAN_CONTRACT_V1.md) and two recorded FR/EN training controls; no qualified model output path, model result or executed tools.", [9]),
        ("discovery", "Open catalogue discovery and sufficient tool sets", "model_observed",
         "[Tool-discovery contract](TOOL_DISCOVERY_CONTRACT_V1.md): 12 FR/EN recorded-control cases, separate shortlist/final-set metrics. One generative candidate observed through the local JSON route on the canary/held-out packs (see the generated-JSON coverage row); no executed tools, no application integration.", [10]),
        ("arguments", "Executable arguments and artifact bindings", "model_observed",
         "[Argument-execution contract](TOOL_ARGUMENTS_CONTRACT_V1.md): four FR/EN training controls with actual bounded lookup/sum and artifact guards. One generative candidate observed on the canary/held-out argument cases (6/6); no application integration.", [11]),
        ("episodes", "Bounded episodes with executed tools and feedback", "model_observed",
         "[Episode contract](TOOL_EPISODES_CONTRACT_V1.md): 14 FR/EN training controls with actual observations, retry/stopping guards and separate stage metrics. One generative candidate observed on the canary/held-out episodes (7/18): positive paths pass, stop/clarify outcomes mostly fail; no application qualification.", [12]),
        ("local_json_policy", "Generated JSON proposals from a local model", "model_observed",
         f"Qwen3-4B Q8, five observations: [TRAIN prompt v1]({policy['train_v1']['report']}) {policy['train_v1']['text']}; "
         f"[TRAIN prompt v2]({policy['train_v2']['report']}) {policy['train_v2']['text']}, identical generated content with the "
         f"[host prompt cache disabled]({policy['train_v2_cache_off']['report']}); "
         f"[held-out prompt v2]({policy['heldout']['report']}) attempt 1 {policy['heldout']['text']}, "
         f"[attempt 2]({policy['heldout_002']['report']}) {policy['heldout_002']['text']}. "
         "One model, correlated FR/EN pairs; no ranking, live MCP or product qualification.", [35]),
        ("order_retention", "Order robustness and evidence retention", "partial_coverage",
         "[Offline order/retention analysis](PASSAGE_ORDER_RETENTION_V1.md) covers four rotations and both views (920 distinct test inputs); historical ranking exists, while new Flash classifications still cover rotation 0 only. No new model calls.", [13]),
        ("cohort", "Remaining cohort on new packs", "not_run",
         "[Historical 27B readiness](D3_27B_CAPABILITY_PROTOCOL_20261030.md) has a candidate-bound offline envelope; execution is deferred with zero new cases. Historical context scores cannot fill new task cells.", [14]),
        ("large_envelope", "Clef 27B candidate envelope", "not_run",
         "Separate runtime/resource qualification is required.", [15]),
        ("small_large", "Empirical small/large allocation and replay", "not_implemented",
         "Authored difficulty strata and confidence are not model-size ground truth.", [16]),
        ("application", "Pinned application harness integration", "not_implemented",
         "An integration registry or isolated model run does not establish live application behavior.", [17]),
        ("rag_final", "Evidence-to-answer generation and citation fidelity", "not_implemented",
         "No complete retrieval-to-answer campaign is qualified.", [18]),
    ]
    return {"schema_version": "deposium.public-coverage/v1", "review_pending": True,
            "tasks": [{"id": k, "label": label, "total": total, "protocol": protocol}
                      for k, label, total, protocol in COVERAGE_TASKS],
            "observations": list(by_id.values()),
            "harness": [{"id": k, "capability": label, "status": status, "boundary": boundary,
                         "issues": [ISSUES + str(n) for n in issues]}
                        for k, label, status, boundary, issues in harness]}


def csv_text(records):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue()


def coverage_csv_rows(coverage):
    records = []
    for row in coverage["observations"]:
        for task in coverage["tasks"]:
            cell = row["cells"][task["id"]]
            records.append({"observation": row["id"], "model": row["model"], "size": row["size"],
                            "runtime": row["runtime"], "context_observation": row["context_observation"],
                            "generative_observation": row.get("generative_observation", False),
                            "task": task["id"], "protocol": task["protocol"],
                            **{k: cell.get(k) for k in ("status", "evidence_present", "review_pending",
                               "scored_or_valid", "total", "metric", "numerator", "metric_value",
                               "metric_defined", "metric_eligible", "source")},
                            **{s: cell["outcomes"].get(s) if cell["outcomes"] is not None else None
                               for s in sorted(STATUS_KEYS)}})
    return records


def render_coverage(coverage):
    def cell_text(cell):
        status, n, total = cell["status"], cell["scored_or_valid"], cell["total"]
        if status == "not_run":
            return "not_run" + (f" 0/{total}" if cell["evidence_present"] else "")
        return f"{status} {n}/{total}"
    all_tasks = coverage["tasks"]
    tasks = [t for t in all_tasks if t["id"] not in GENERATED_TASKS]
    generated = [t for t in all_tasks if t["id"] in GENERATED_TASKS]
    lines = ["## Coverage overview", "",
             "**Execution coverage, not accuracy.** Each cell is `complete`, `partial`, or `not_run`, "
             "followed by scored/valid decisions over the planned denominator when observed. "
             "All references remain **review_pending**, independently of execution. "
             "No overall accuracy combines these tasks.", "",
             "`not_run` means no matching public observation; it does not mean unsupported or zero accuracy. "
             "A source with no attempted answerability decisions explicitly shows `not_run 0/128`. "
             "Unreported measurements remain NR in the [speed and memory table](#speed-and-memory). "
             "Recorded `missing`, `unsupported`, `error`, `timeout`, and `abstain` outcomes remain separate in the "
             "[coverage CSV](leaderboard/coverage.csv) and [JSON](leaderboard/coverage.json).", "",
             "### Context model/runtime observations", "",
             f"The {sum(1 for r in coverage['observations'] if r['context_observation'])} rows below preserve quantization and runtime identities; sizes are publisher classes or declared counts, not independent measurements. **Metal gateway** and "
             "**direct Metal** are different paths; scores and task rankings follow below. "
             "Context/132 contains text/76, mathematics/28 and chemistry/28; "
             "[their scores and held-out test results](#model-quality) remain separate.", "",
             "| Model / runtime observation | Size | " + " | ".join(f"{t['label']} /{t['total']}" for t in tasks) + " |",
             "|---|---|" + "---|" * len(tasks)]
    for row in coverage["observations"]:
        if not row["context_observation"] or row.get("generative_observation"):
            continue
        label = row["model"]
        if row["id"] == "D3FlashQ8":
            label += " (gateway)"
        lines.append(f"| {label} | {row['size'] or 'NR'} | " +
                     " | ".join(cell_text(row["cells"][t["id"]]) for t in tasks) + " |")
    # Columns of the passage-only table: every task except the closed-choice packs of the context rows.
    passage_tasks = [t for t in tasks if t["id"] not in
                     {"context", "tool_proposal", "capability", "physics", "choice_episodes", "facade_routing"}]
    lines += ["", "### Passage-only observations and ranking methods", "",
              "These do not add context models. D3-lite's passage session has a different runtime/settings "
              "identity fingerprint from its historical context session. Jev 1.14 is distinct from context "
              "Jev 1.13. BGE and tie-break methods are ranking observations, not newly evaluated context models.", "",
              "| Model / method | " + " | ".join(f"{t['label']} /{t['total']}" for t in passage_tasks) + " |",
              "|---|" + "---|" * len(passage_tasks)]
    for row in coverage["observations"]:
        if row["context_observation"] or row.get("generative_observation") or row.get("router_observation"):
            continue
        lines.append(f"| {row['model']} | " + " | ".join(cell_text(row["cells"][t["id"]]) for t in passage_tasks) + " |")
    lines += ["", "R0 means rotation 0 (128 pools, eight families, two correlated views). "
              "Relevance/512 and replayed relevance/2048 have different protocols; neither is ranking/512. "
              "Ranking cells cover 512 pools over four balanced rotations; nDCG@1 is defined on 480/480 eligible pools. "
              "D3-lite/Jev ranking replays existing relevance decisions; rotations add no model calls. "
              "Tie-break rows are offline combined methods, with projected sequential cost rather than a measured integrated pipeline. "
              "[Ranking scores, controls and evidence retention](#passage-ranking-and-evidence) remain separate from classification.", "",
              "### Generated-JSON tool-policy observations", "",
              "A different candidate output path: the model generates a shortlist/selection, sum arguments or one episode "
              "action per step, and the runtime executes the synthetic tools. Cells count passed/scored cases over the "
              "TRAIN canary plus the held-out TEST pack under prompt v2 (complete observations only; the 30 classifier rows "
              "have no observation on these columns). Scores, failure modes and the partial first held-out attempt are in the "
              "[dated reports](LOCAL_TOOL_POLICY_HELDOUT_RESULTS_20261030.md).", "",
              "| Model / runtime observation | Size | " + " | ".join(f"{t['label']} /{t['total']}" for t in generated) + " |",
              "|---|---|" + "---|" * len(generated)]
    passed = []
    for row in coverage["observations"]:
        if not row.get("generative_observation"):
            continue
        lines.append(f"| {row['model']} | {row['size']} | " + " | ".join(cell_text(row["cells"][t["id"]]) for t in generated) + " |")
        passed.append(f"{row['model']}: " + ", ".join(
            f"{t['label'].split(' ')[0].lower()} {row['cells'][t['id']]['numerator']}/{row['cells'][t['id']]['scored_or_valid']} passed"
            for t in generated))
    lines += ["", "Cells are execution coverage, as above. Passed cases over scored cases: " + "; ".join(passed) + ". "
              "A passed case is an exact match of the authored outcome (and minimal tool set, or actual execution receipt); "
              "a correct clarification or stop is procedure handling, not task success."]
    lines += ["",
              "The 24-case tool column reports valid provisional proposals: **zero human-approved references "
              "and zero semantically qualified cases**. Complete coverage does not qualify routing or tool execution. "
              "See [task-specific rankings](#updated-task-rankings), [historical context quality](#model-quality), "
              "[full task CSV](leaderboard/task-breakdown.csv), and the dated "
              "[D3 capability report](CAPABILITY_FLASH_RESULTS_20261029.md) for scores and source details.", "",
              "## Harness coverage", "",
              "A missing model observation and a missing harness capability are different gaps. "
              "The global boundaries below apply to every model; they are not model `unsupported` outcomes. "
              "[Reference review #8](" + ISSUES + "8) remains pending even where execution is complete.", "",
              "| Capability | Harness / campaign status | What remains unqualified | Next issue |",
              "|---|---|---|---|"]
    for row in coverage["harness"]:
        links = ", ".join(f"[#{url.rsplit('/', 1)[1]}]({url})" for url in row["issues"]) or "—"
        lines.append(f"| {row['capability']} | {row['status']} | {row['boundary']} | {links} |")
    lines += ["", "The initial contract, discovery, arguments and episode fixtures are implemented as scripted controls. "
              "The [local JSON route](LOCAL_TOOL_POLICY_V1.md) has TRAIN canary observations (prompt v1 5/10, prompt v2 7/10, "
              "unchanged with the host prompt cache disabled) and a complete held-out observation of 9/24 "
              "([report](LOCAL_TOOL_POLICY_HELDOUT_RESULTS_20261030.md)) after a first partial attempt. "
              "Every declared contract outcome has now been observed at least once; most nonselection and stop outcomes fail. See [campaign status](CAMPAIGN_STATUS.md) for the working sequence.", ""]
    return lines


def flat_rows(data):
    models, tasks = [], []
    for row in data["observations"]:
        meta, ctx, tool, res = row["metadata"], row["context"], row["tool_proposal"], row["resources"]
        groups = ctx["groups"]
        models.append({
            "rank_all_splits": row["rank_all_splits"], "rank_test_splits": row["rank_test_splits"],
            "observation": row["id"], "model": meta["display_name"],
            "size": meta["model_size"]["label"], "parameters": meta["model_size"]["parameters"],
            "size_basis": meta["model_size"]["basis"], "runtime_group": meta["runtime_group"],
            "hardware": meta["hardware_group"], "precision": meta["precision"],
            "all_correct": ctx["counts"]["correct"], "all_scored": ctx["counts"]["scored"], "all_total": 132,
            **{f"{key}_correct": groups[axis][group]["correct"] for key, axis, group in
               (("test", "split", "test"), ("documentary", "domain", "documentary"),
                ("math", "domain", "mathematics"), ("chemistry", "domain", "chemistry"),
                ("en", "language", "en"), ("fr", "language", "fr"))},
            "tool_status": "observed_provisional" if tool else "not_run",
            "tool_agreement": tool["counts"]["agreement_count"] if tool else None,
            "tool_valid": tool["counts"]["valid_decisions"] if tool else None,
            "tool_total": 24 if tool else None, "tool_qualified_cases": 0,
            "adapter_median_ms": res["adapter_ms"]["median"], "adapter_p95_ms": res["adapter_ms"]["p95"],
            "timed_calls": res["adapter_ms"]["count"], "initialization_ms": res["initialization_ms"],
            "worker_peak_rss_mib": res["worker_rss_mib"]["max"], "rss_reported_calls": res["worker_rss_mib"]["count"],
            "session_process_group_peak_rss_mib": res["session_process_group_peak_rss_mib"],
            "sampled_gpu_allocated_peak_mib": res["sampled_gpu_allocated_peak_mib"],
            "rss_scope": res["rss_scope"], "source_analysis": meta["source_analysis"],
        })
        for phase in ("context", "tool_proposal"):
            if row[phase] is None:
                continue
            for axis, values in row[phase]["groups"].items():
                for group, count in sorted(values.items()):
                    route = phase == "tool_proposal"
                    tasks.append({"observation": row["id"], "task": phase, "axis": axis, "group": group,
                                  "metric": "provisional_agreement" if route else "correct_choice",
                                  "numerator": count["agreement_count" if route else "correct"],
                                  "scored_or_valid": count["valid_decisions" if route else "scored"],
                                  "total": count["total"],
                                  **{status: count.get("statuses", {}).get(status) for status in sorted(STATUS_KEYS)}})
    for row in data["campaigns"]:
        for axis, values in {"all": {"all": row["counts"]}, **row["groups"]}.items():
            for group, count in sorted(values.items()):
                tasks.append({"observation": row["observation"], "task": row["task"], "axis": axis, "group": group,
                              "metric": "correct_choice", "numerator": count["correct"],
                              "scored_or_valid": count["scored"], "total": count["total"],
                              **{status: count["statuses"][status] for status in sorted(STATUS_KEYS)}})
    return models, tasks


def campaign_csv_rows(data):
    records = []
    for row in data["campaigns"]:
        c, timing = row["counts"], row.get("adapter_ms", {})
        test = c.get("by_split", {}).get("test", {})
        records.append({"task": row["task"], "observation": row["observation"], "model": row["model"],
                        "status": row["status"], "rank_all": row["rank_all"], "rank_test": row["rank_test"],
                        "correct": c["correct"], "scored": c["scored"], "total": c["total"],
                        "families": c["families"], "test_correct": test.get("correct"),
                        "test_scored": test.get("scored"), "test_total": test.get("total"),
                        "macro_accuracy": row.get("macro_accuracy"),
                        "physical_calls": row.get("physical_calls"), "timed_calls": timing.get("count"),
                        "adapter_median_ms": timing.get("median"), "adapter_p95_ms": timing.get("p95"),
                        "session_group_peak_rss_mib": row.get("session_group_peak_rss_mib"),
                        "rss_scope": row.get("rss_scope"), "source_analysis": row["source"],
                        **c["statuses"]})
    return records


def number(value, places=1):
    return "NR" if value is None else f"{value:,.{places}f}"


def leaders(rows, rank_key, name, score):
    """Names sharing rank 1 under `rank_key`, with their score text; ties are listed together."""
    best = [r for r in rows if r.get(rank_key) == 1]
    if not best:
        return "no completely scored observation"
    return ", ".join(f"{name(r)} ({score(r)})" for r in best) + (" (tie)" if len(best) > 1 else "")


LEGEND_RANKS = ("<sub>**Rank all**: competition rank by correct answers over every case of the pack (all splits); "
                "**Rank test**: the same rank over the held-out test cases only, the better signal against tuning; "
                "equal totals share a rank. **Correct / all** keeps failed, missing and unsupported cases in the denominator; "
                "**Scored / all** shows how many cases produced a valid answer.</sub>")


def render_choice_episodes(data):
    rows = data["choice_episodes"]
    if not rows:
        return []
    lines = ["### Executed tool episodes (closed choice)", "",
             "32 synthetic episodes (20 TRAIN, 12 TEST) run with real fixture tools: at each step the harness lists the possible "
             "next actions, the model picks one, the tool runs and its actual result feeds the next step. A case passes when the "
             "whole procedure is valid, the stop is correct and budgets hold; **task success** counts the twelve episodes whose "
             "correct end is a computed total. Premature success and malformed actions are impossible by construction, so these "
             "scores are not comparable with the generated-JSON policy. [Pilot report](" + rows[0]["report"] + ").", "",
             LEGEND_RANKS, "",
             f"**Leading on held-out test**: {leaders(rows, 'rank_test', lambda r: r['model'], lambda r: str(r['counts']['test']['procedure_correct_cases']) + '/12 test')}; "
             f"**leading over all cases**: {leaders(rows, 'rank_all', lambda r: r['model'], lambda r: str(r['counts']['all']['procedure_correct_cases']) + '/32')}.", "",
             "| Rank all | Rank test | Model / runtime | Procedure correct / all | Test correct / all | Task success / eligible | Stop correct / all | Execution | Steps | Tool calls | Median call s |",
             "|---:|---:|---|---:|---:|---:|---:|---|---:|---:|---:|"]
    for r in rows:
        c, st, ex = r["counts"], r["stages"], r["execution"]
        bad = {k: v for k, v in c["all"]["statuses"].items() if k != "ok" and v}
        execution = "all `ok`" if not bad else ", ".join(f"{v} `{k}`" for k, v in sorted(bad.items()))
        median = ex["inner_inference_ms"]["median"]
        lines.append(f"| {r['rank_all']} | {r['rank_test']} | {r['model']} | {c['all']['procedure_correct_cases']}/{c['all']['total_cases']} | "
                     f"{c['test']['procedure_correct_cases']}/{c['test']['total_cases']} | {c['all']['task_success_cases']}/{c['all']['task_success_eligible_cases']} | "
                     f"{st['stopping']['correct']}/{st['stopping']['eligible']} | {execution} | {ex['policy_steps']} | {ex['tool_calls_executed']} | "
                     f"{number(median / 1000 if median is not None else None)} |")
    lines += ["", "**Steps** counts model decisions; **tool calls** counts actual fixture executions. A model that keeps choosing the first "
              "option or always the same stop shows it in the chosen-position distribution of the report.", ""]
    return lines


def render_deployment(data):
    deployment = data.get("deployment")
    if not deployment:
        return []
    names = {"D3miniQ8Metal": "D3 mini Q8 · Metal", "D3miniQ4Metal": "D3 mini Q4 · Metal", "D3FlashMUzu": "D3 Flash 4-bit · Uzu"}
    lines = ["### Deployment variants: Q4 and Uzu", "",
             "Same packs, three ways to serve a small D3 model on the Mac: D3 mini Q8 and Q4_K_M GGUF on llama.cpp Metal, "
             "and Mirai's 4-bit D3 Flash pack (9B, INT4) on the Uzu engine. Cells: correct / all, median call time, sampled "
             "process RSS. A deployment comparison: weights, quantization and engine change together. "
             f"[Report]({DEPLOYMENT_REPORT}).", "",
             "| Pack | " + " | ".join(names.values()) + " |", "|---|" + "---:|" * len(names)]
    for pack, entry in deployment["packs"].items():
        cells = []
        for key in names:
            v = entry["variants"][key]
            cells.append(f"{v['correct']}/{v['total']} · {number(v['median_call_ms'])} ms · {number(v['rss_peak_mib'] / 1024, 1)} GiB")
        lines.append(f"| {pack} | " + " | ".join(cells) + " |")
    lines += ["", "Uzu does not report its compute backend; Metal is requested, not observed. Its stock CLI fetches an online "
              "catalogue at start (no offline claim). Latency is one pass per case.", ""]
    return lines


def render_facade_routing(data):
    rows = data["facade_routing"]
    if not rows:
        return []
    def kind(r, name):
        c = r["counts"]["by_kind"].get(name)
        return f"{c['correct']}/{c['total']}" if c else "—"
    lines = ["### Facade routing (model vs router)", "",
             "80 synthetic FR/EN requests to a document assistant (16 TRAIN, 16 calibration, 48 TEST): which of eight tool "
             "categories should handle the request, or *none* (out of scope or too vague). The production router is a deterministic "
             "function replayed privately at a pinned revision; only its aggregate scores are public, so its row is **not externally "
             "reproducible**. References were written without access to its rules. [Report and limits](" + rows[0]["report"] + ").", "",
             LEGEND_RANKS, "",
             f"**Leading on held-out test**: {leaders(rows, 'rank_test', lambda r: r['model'], lambda r: str(r['counts']['by_split']['test']['correct']) + '/48 test')}; "
             f"**leading over all cases**: {leaders(rows, 'rank_all', lambda r: r['model'], lambda r: str(r['counts']['all']['correct']) + '/80')}.", "",
             "| Rank all | Rank test | Model / runtime | Correct / all | Test / 48 | Direct /28 | Paraphrase /28 | Refused alternative /10 | Two-step /4 | Out of scope or vague /10 | Right where router wrong / router right where model wrong | Median call ms |",
             "|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        c = r["counts"]
        scope = [c["by_kind"].get(k) for k in ("out_of_scope", "ambiguous")]
        scope_text = f"{sum(x['correct'] for x in scope if x)}/{sum(x['total'] for x in scope if x)}"
        pair = r["paired"]["all"] if r["paired"] else None
        pair_text = f"{pair['model_only']} / {pair['router_only']}" if pair else "reference"
        median = (r["inference_ms"] or {}).get("median")
        lines.append(f"| {r['rank_all']} | {r['rank_test']} | {r['model']} | {c['all']['correct']}/{c['all']['total']} | "
                     f"{c['by_split']['test']['correct']}/{c['by_split']['test']['total']} | {kind(r, 'direct')} | {kind(r, 'paraphrase')} | "
                     f"{kind(r, 'negation')} | {kind(r, 'multi')} | {scope_text} | {pair_text} | "
                     f"{number(median) if median is not None else 'NR'} |")
    lines += ["", "The router's role in the application is narrower than this pack: a low score here does not mean the application "
              "fails on these requests. Paraphrases avoid the obvious word on purpose; correlated FR/EN pairs and ten requests per "
              "category do not support a general ranking.", ""]
    tiers = data.get("facade_tiers") or []
    if tiers:
        def cell(r, tier):
            c = r[tier]
            return f"{c['all']['correct']}/{c['all']['total']} ({c['by_split']['test']['correct']}/{c['by_split']['test']['total']})"
        lines += ["### Facade routing: harder tiers", "",
                  "Same eight categories on two frozen harder tiers of 96 cases (64 TEST). **Advanced**: implicit requests, lexical "
                  "traps toward another category, near misses, informal or misspelt requests. **Complex**: multi-step requests scored "
                  "on the first step, requests that depend on a previous exchange, compound refusals, goals without the action, "
                  "genuine ambiguity. Cells are correct / all (test). [Tiers report](" + FACADE_TIERS_REPORT + ").", "",
                  f"**Leading on the complex tier (test)**: {leaders(tiers, 'rank_test_complex', lambda r: r['model'], lambda r: str(r['complex']['by_split']['test']['correct']) + '/64 test')}.", "",
                  "| Rank complex | Model / runtime | Easy /80 (test /48) | Advanced /96 (test /64) | Complex /96 (test /64) | Median call ms (advanced) |",
                  "|---:|---|---:|---:|---:|---:|"]
        for r in tiers:
            median = (r.get("latency") or {}).get("median")
            lines.append(f"| {r['rank_complex']} | {r['model']} | {cell(r, 'easy')} | {cell(r, 'advanced')} | {cell(r, 'complex')} | "
                         f"{number(median) if median is not None else 'NR'} |")
        lines += ["", "D3 rows on these tiers ran as Q8 GGUF on Metal (same weights as their CPU rows); Vela 2.0 0.3B ran on CPU. "
                  "Latency scopes differ: Metal rows time the whole adapter call (loopback HTTP included), the CPU row its worker inference. "
                  "The router reads only the latest request, as in the application; the complex tier's previous exchange is "
                  "visible to the classifiers only.", ""]
    return lines


def render_campaign_rankings(data):
    lines = ["## Updated task rankings", "",
             "These tables include every published campaign on these packs. "
             "Each task has its own ranking and denominator; there is no pooled cross-task score. "
             "Ranks use correct/all among completely scored observations on the same task/denominator. "
             "Partial and unrun campaigns remain visible but unranked. Ties share competition ranks. "
             "Canaries and repeated context anchors do not add quality cases.", ""]
    for task, title in (("capability", "Capability choices"), ("physics", "Physics choices")):
        rows = [r for r in data["campaigns"] if r["task"] == task]
        total = rows[0]["counts"]["total"] if rows else 0
        test_total = rows[0]["counts"]["by_split"]["test"]["total"] if rows else 0
        lines += [f"### {title}", "", LEGEND_RANKS, "",
                  f"**Leading on held-out test**: {leaders(rows, 'rank_test', lambda r: r['model'], lambda r: f"{r['counts']['by_split']['test']['correct']}/{test_total} test")}; "
                  f"**leading over all cases**: {leaders(rows, 'rank_all', lambda r: r['model'], lambda r: f"{r['counts']['correct']}/{total}")}. "
                  "A lead of a few cases on correlated FR/EN variants is not a general ranking.", "",
                  "| Rank all | Rank test | Model / execution path | Correct / all | Scored / all | Test correct / all | Source |",
                  "|---:|---:|---|---:|---:|---:|---|"]
        for row in rows:
            c, test = row["counts"], row["counts"]["by_split"]["test"]
            # Partial collections stay visible but unranked; a dash, never a rank or a zero.
            lines.append(f"| {row['rank_all'] or '—'} | {row['rank_test'] or '—'} | {row['model']} | {c['correct']}/{c['total']} | "
                         f"{c['scored']}/{c['total']} | {test['correct']}/{test['total']} | [Report]({row['report']}) |")
        if task == "capability":
            ceiling = [r["model"] for r in rows if r["counts"]["correct"] == r["counts"]["total"]]
            lines += ["", (f"{', '.join(ceiling)} reach the ceiling on these supplied proposals; " if ceiling else "")
                      + "a perfect or near-perfect closed-choice score does not qualify executable tools. "
                      "Runtimes differ per row (gateway-backed Metal, direct native listener, CPU worker) and are not pooled.", "",
                      "<sub>**Track**: the three case families of the pack; selection = choose capabilities/tool sets, "
                      "arguments = bind arguments and dependencies, observations = choose the next step after fixed tool observations.</sub>", "",
                      "| Model | Track | Correct / all | Test correct / all |", "|---|---|---:|---:|"]
            for row in rows:
                for track, title in (("selection", "Capability selection"), ("arguments", "Arguments and dependencies"),
                                     ("observations", "Next step after fixed observations")):
                    c = row["groups"]["track"][track]
                    test = c["by_split"]["test"]
                    lines.append(f"| {row['model']} | {title} | {c['correct']}/{c['total']} | {test['correct']}/{test['total']} |")
        else:
            lines += ["", "Calibration (12) and test (36) are shown separately because the all-case and test leaders can differ; "
                      "with four options, 12/48 is chance level. No result establishes general physics expertise: "
                      "the law and assumptions are supplied in each input."]
        lines.append("")
    for axis, title in (("relevance", "Passage relevance"), ("support", "Claim support"), ("answerability", "Answerability")):
        label, hits, total = PASSAGE_MAJORITY[axis]
        lines += [f"### {title}", "", "Rotation 0: 128 pools, eight families, eight language directions, two correlated views. "
                  f"Classes are imbalanced: always answering {label} scores **{hits}/{total}**, so compare macro class accuracy, "
                  "not totals alone.", "",
                  "<sub>**Rank**: by correct/all among completely scored observations (— when partial or not run); "
                  "**Macro class accuracy**: mean of the per-class accuracies, so a rare class weighs as much as a frequent one.</sub>", "",
                  "| Rank | Model / runtime | Correct / all | Scored / all | Macro class accuracy | Observation |",
                  "|---:|---|---:|---:|---:|---|"]
        for row in data["campaigns"]:
            if row["task"] != "passage_" + axis:
                continue
            c, macro = row["counts"], row.get("macro_accuracy")
            score = f"{c['correct']}/{c['total']}" if c["scored"] else "Not run"
            lines.append(f"| {row['rank_all'] or '—'} | {row['model']} | {score} | {c['scored']}/{c['total']} | "
                         f"{number(100 * macro, 2) + '%' if macro is not None else 'NR'} | {row['status']}; [report]({row['report']}) |")
        lines.append("")
    lines += ["Class macro accuracy averages the scored class accuracies. Jev's partial support macro is conditional "
              "on its observed subset and is not a complete-coverage comparison; unobserved decisions remain missing in the totals.", ""]
    jev = next(r for r in data["campaigns"] if r["task"] == "passage_relevance_four_rotations")
    c = jev["counts"]
    lines += [f"Jev's published relevance export is **{c['correct']}/{c['total']}**, scored {c['scored']}/{c['total']}, "
              "over four rotations. It is retained in the downloads as `passage_relevance_four_rotations`, "
              "outside the 512-decision relevance ranking. Replayed rotations are not extra independent model calls.", "",
              "Support insufficiency/refutation remains weak for both Flash candidates. Clef accepts 12/16 pools annotated "
              "as conflicting as answerable; D3 accepts none in this finite run. See "
              "[paired outcomes and confusion matrices](PASSAGE_CLEF_RESULTS_20261029.md). "
              "This is not factual-verifier or end-to-end qualification. The four macOS CPU rows (D3 lite, nano, mini, "
              "Vela 2.0 0.3B), their per-class errors and their cost per call are in the "
              "[small-CPU passage report](PASSAGE_SMALL_CPU_RESULTS_20261031.md).", "",
              *render_choice_episodes(data),
              *render_facade_routing(data),
              *render_deployment(data),
              "### Campaign latency and memory", "",
              "Physical-call timings are kept separate from reused logical decisions; session RSS scopes differ "
              "from the historical context + tool sessions. NR means unreported. No controlled speed ranking is inferred.", "",
              "| Model / runtime | Task | Timed calls | Median ms | p95 ms | Session RSS GiB |",
              "|---|---|---:|---:|---:|---:|"]
    for row in data["campaigns"]:
        if "adapter_ms" not in row:
            continue
        t = row["adapter_ms"]
        lines.append(f"| {row['model']} | {row['task']} | {t['count']} | {number(t['median'])} | {number(t['p95'])} | "
                     f"{number(row['session_group_peak_rss_mib'] / 1024, 2)} |")
    lines += ["", "[Campaign summary CSV](leaderboard/campaigns.csv) and [task breakdown CSV](leaderboard/task-breakdown.csv) "
              "contain denominators, statuses and all exported groups. Ranking/nDCG, longer contexts and repeated timing "
              "retain their separate protocols in [other campaigns](leaderboard/other-benchmarks.md). "
              "Clef 27B and the six remaining original cohort candidates remain unrun on the new packs.", ""]
    return lines


def render_other_protocols(text):
    """Include the tracked legacy tables, fixing links relative to docs/RESULTS.md."""
    sections = re.split(r"(?m)(?=^## )", text)
    selected = [s for s in sections if s.startswith("## ") and not s.startswith("## Support and answerability decisions")]
    require(len(selected) == 5, "other campaigns: source sections changed; review consolidation")
    def relocate(match):
        href = match.group(1)
        if href.startswith(("https://", "http://", "#")):
            return match.group(0)
        return "](" + posixpath.normpath(posixpath.join("leaderboard", href)) + ")"
    lines = ["## Other evaluated protocols", "",
             "The historical tables below are included from the tracked [other-campaign guide](leaderboard/other-benchmarks.md). "
             "Their original denominators, failure counts and timing scopes are preserved. They are not combined with "
             "the context or rotation-zero evidence rankings. Structured summary metrics and source hashes are also "
              "included under `other_campaigns` in the JSON download; detailed cross-groups, rotations and per-case rows remain in the source exports.", ""]
    for section in selected:
        section = re.sub(r"(?m)^## ", "### ", section)
        lines.append(re.sub(r"\]\(([^)\s]+)\)", relocate, section).rstrip())
        lines.append("")
    return lines



def anchor(title):
    """GitHub-style heading anchor: lowercase, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"[^\w\s-]", "", title.lower().replace("·", " "))
    return re.sub(r"\s+", "-", text.strip())


def render_toc(body):
    lines = ["## Contents", ""]
    # Some sections are rendered as one multi-line string; scan physical lines.
    for line in (part for chunk in body for part in chunk.split("\n")):
        if line.startswith("## "):
            title = line[3:].strip()
            lines.append(f"- [{title}](#{anchor(title)})")
        elif line.startswith("### "):
            title = line[4:].strip()
            lines.append(f"  - [{title}](#{anchor(title)})")
    return lines + [""]


def render_at_a_glance(data):
    """One row per task: cases, observations, who leads over all cases and on the held-out test, where to read more."""
    def name(r):
        return r["metadata"]["display_name"]
    observations = data["observations"]
    campaigns = data["campaigns"]
    rows = []
    rows.append(("RAG decision", "Context choices", "132 (66 test)", len(observations),
                 leaders(observations, "rank_all_splits", name, lambda r: f"{r['context']['counts']['correct']}/132"),
                 leaders(observations, "rank_test_splits", name, lambda r: f"{r['context']['groups']['split']['test']['correct']}/66 test"),
                 "[Model quality](#model-quality)"))
    tools = [r for r in observations if r["tool_proposal"] and r["tool_proposal"]["counts"]["valid_decisions"] == 24]
    best = max((r["tool_proposal"]["counts"]["agreement_count"] for r in tools), default=None)
    tool_leaders = ", ".join(name(r) + f" ({best}/24)" for r in tools if r["tool_proposal"]["counts"]["agreement_count"] == best)
    rows.append(("RAG decision", "First-tool proposals", "24 (no test split)", len([r for r in observations if r["tool_proposal"]]),
                 (tool_leaders + (" (tie)" if tool_leaders.count("(") > 1 else "")) if best is not None else "no complete observation",
                 "provisional agreement, not routing accuracy", "[Model quality](#model-quality)"))
    for family, task, title, total, test_total, section in (("Tool workflow", "capability", "Capability and workflow choices", 192, 96, "#capability-choices"),
                                                            ("Reasoning with a supplied law", "physics", "Physics choices", 48, 36, "#physics-choices")):
        task_rows = [r for r in campaigns if r["task"] == task]
        rows.append((family, title, f"{total} ({test_total} test)", len(task_rows),
                     leaders(task_rows, "rank_all", lambda r: r["model"], lambda r: f"{r['counts']['correct']}/{total}"),
                     leaders(task_rows, "rank_test", lambda r: r["model"], lambda r: f"{r['counts']['by_split']['test']['correct']}/{test_total} test"),
                     f"[{title.split(' and ')[0]}]({section})"))
    episode_rows = data["choice_episodes"]
    if episode_rows:
        rows.append(("Tool workflow, executed", "Executed tool episodes (closed choice)", "32 (12 test)", len(episode_rows),
                     leaders(episode_rows, "rank_all", lambda r: r["model"], lambda r: f"{r['counts']['all']['procedure_correct_cases']}/32"),
                     leaders(episode_rows, "rank_test", lambda r: r["model"], lambda r: f"{r['counts']['test']['procedure_correct_cases']}/12 test"),
                     "[Executed episodes](#executed-tool-episodes-closed-choice)"))
    facade_rows = data["facade_routing"]
    tier_rows = data.get("facade_tiers") or []
    if facade_rows:
        rows.append(("Tool routing", "Facade routing (model vs router)", "80 (48 test)", len(facade_rows),
                     leaders(facade_rows, "rank_all", lambda r: r["model"], lambda r: f"{r['counts']['all']['correct']}/80"),
                     leaders(facade_rows, "rank_test", lambda r: r["model"], lambda r: f"{r['counts']['by_split']['test']['correct']}/48 test"),
                     "[Facade routing](#facade-routing-model-vs-router)"))
    for tier in ("advanced", "complex"):
        if tier_rows:
            rows.append(("Tool routing", f"Facade routing, {tier} tier", "96 (64 test)", len(tier_rows),
                         leaders(tier_rows, "rank_" + tier, lambda r, tier=tier: r["model"], lambda r, tier=tier: f"{r[tier]['all']['correct']}/96"),
                         leaders(tier_rows, "rank_test_" + tier, lambda r, tier=tier: r["model"],
                                 lambda r, tier=tier: f"{r[tier]['by_split']['test']['correct']}/64 test"),
                         "[Harder tiers](#facade-routing-harder-tiers)"))
    for axis, title, total, section in (("relevance", "Passage relevance", 512, "#passage-relevance"),
                                        ("support", "Claim support", 768, "#claim-support"),
                                        ("answerability", "Answerability", 128, "#answerability")):
        task_rows = [r for r in campaigns if r["task"] == "passage_" + axis]
        rows.append(("Retrieved evidence", title, f"{total} (rotation 0)", len(task_rows),
                     leaders(task_rows, "rank_all", lambda r: r["model"], lambda r: f"{r['counts']['correct']}/{total}"),
                     "no split ranking", f"[{title}]({section})"))
    generative = [r for r in data["coverage"]["observations"] if r.get("generative_observation")]
    for r in generative:
        cells = r["cells"]
        text = "; ".join(f"{label} {cells[task]['numerator']}/{cells[task]['total']}"
                         for task, label in (("tool_discovery", "discovery"), ("tool_arguments", "arguments"), ("tool_episodes", "episodes"))
                         if cells[task]["status"] == "complete")
        rows.append(("Tool policy, generated", "Generated-JSON tool policy", "10 + 6 + 18 (TRAIN canary + held-out)", 1,
                     f"{r['model']}: {text} passed (single observation, unranked)", "held-out pack 9/24 over the three contracts; see the report",
                     "[Generated-JSON observations](#generated-json-tool-policy-observations)"))
    lines = ["## At a glance", "",
             "One line per task, grouped by family: **RAG decision** (which source or first tool to use for a request), "
             "**Retrieved evidence** (judging passages: relevance, claim support, answerability), **Tool workflow** (selection, arguments, "
             "next step after observations; **executed** when real fixture tools run step by step), **Tool routing** (which tool category a request needs, small models against the production router), **Reasoning** (physics with the law supplied) and **Tool policy, generated** (free-form JSON actions). "
             "**Leader over all cases** counts every case of the pack, including failures; "
             "**leader on held-out test** uses only the test cases, the better signal against tuning. "
             "Ties are listed together. Tasks are never pooled into one score; a lead of a few cases on correlated FR/EN "
             "variants is not a general ranking. References are agent-authored and pending human review.", "",
             "| Family | Task | Cases | Observations | Leader over all cases | Leader on held-out test | Details |",
             "|---|---|---|---:|---|---|---|"]
    for family, title, cases, count, all_leader, test_leader, link in rows:
        lines.append(f"| {family} | {title} | {cases} | {count} | {all_leader} | {test_leader} | {link} |")
    lines += ["", "Rows further down keep every observation, partial campaigns included, with their denominators and statuses. "
              "For one model across every task, open [Every model, every task](leaderboard/by-model/README.md): one page per observation with scores, ranks, execution outcomes, speed and reports.", ""]
    return lines

def render(data):
    lines = ["# Full results", "", "[README](../README.md) · [At a glance](#at-a-glance) · [Contents](#contents) · [Every model, every task](leaderboard/by-model/README.md) · "
             "[Passages and other campaigns](leaderboard/other-benchmarks.md) · [Proposed tool and model routing](INTENT_AND_MODEL_ROUTING.md)", "",
             f"**{len(data['observations'])} context model/runtime observations through 31 October 2026**: 28 earlier observations, the macOS CPU D3 lite, Vela 2.0 0.3B, D3 nano and D3 mini runtimes, Clef Flash Q8 and the direct upstream D3 Flash Q8 runtime.",
             "Rows identify observations, not independent model families. Gateway-backed and direct native binaries remain distinct. Repeated exports of the same sealed run are deduplicated;",
             "quantizations and devices remain separate. Rendering this page does not rerun or rescore models.", "",
             "**Exploratory evidence:** synthetic, agent-authored references and translations await human review.",
             "The ranking uses all 132 cases (train + calibration + test); the separate test column uses 66 cases.",
             "FR/EN translations form 66 families. Differences of a few answers do not establish a general model ranking.", ""]
    header, lines = lines, []
    lines += render_coverage(data["coverage"])
    lines += render_campaign_rankings(data)
    lines += ["## Model quality", "",
             "Each score is **correct / all cases** in its column, retaining failures in the denominator.",
             "Tool is **agreement / 24 provisional proposals**, not routing accuracy. Full scored/valid counts and separate",
             "`missing`, `unsupported`, `error`, `timeout`, and `abstain` counts are in the downloads.",
             "Equal all-case totals share a competition rank; row order within a tie is alphabetical by observation ID.", "",
             "<sub>**Rank all**: rank by correct answers over all 132 context cases (train + calibration + test); "
             "**Rank test**: rank over the 66 held-out test cases only, the better signal against tuning; "
             "**All / Test**: correct answers over those cases; **Text / Math / Chem**: correct answers within each domain "
             "(76 documentary, 28 mathematics, 28 chemistry cases); **Tool**: provisional agreements over 24 first-tool proposals, "
             "not routing accuracy. Size¹ and Runtime² are explained below the table.</sub>", "",
             f"**Leading on held-out test**: {leaders(data['observations'], 'rank_test_splits', lambda r: r['metadata']['display_name'], lambda r: str(r['context']['groups']['split']['test']['correct']) + '/66')}; "
             f"**leading over all 132 cases**: {leaders(data['observations'], 'rank_all_splits', lambda r: r['metadata']['display_name'], lambda r: str(r['context']['counts']['correct']) + '/132')}. "
             "Larger native models lead; the gap to the best sub-1B CPU candidates is a few dozen cases on correlated FR/EN pairs.", "",
             "| Rank all | Rank test | Model observation | Size¹ | Runtime² | All /132 | Test /66 | Text /76 | Math /28 | Chem /28 | Tool /24 |",
             "|---:|---:|---|---|---|---:|---:|---:|---:|---:|---:|"]
    runtime_codes = {"historical_cpu": "CPU-H", "remote_api": "API", "apple_metal_native": "Metal",
                     "apple_mps": "MPS", "cpu_new": "CPU-N", "apple_metal_upstream": "Metal-U"}
    for row in data["observations"]:
        m, c, g = row["metadata"], row["context"]["counts"], row["context"]["groups"]
        tool = row["tool_proposal"]
        lines.append(f"| {row['rank_all_splits']} | {row['rank_test_splits']} | {m['display_name']} | {m['model_size']['label'] or 'NR'} | "
                     f"{runtime_codes[m['runtime_group']]} | {c['correct']} | {g['split']['test']['correct']} | "
                     f"{g['domain']['documentary']['correct']} | {g['domain']['mathematics']['correct']} | "
                     f"{g['domain']['chemistry']['correct']} | {tool['counts']['agreement_count'] if tool else 'Not run'} |")
    lines += ["", "¹ Sizes describe the observed checkpoint: exact tensor counts, nominal classes, and publisher declarations",
              "are distinguished in [metadata](leaderboard/model-metadata.json). A backbone count may exclude a separate readout;",
              "some counts include vision weights. **NR** means not reported in the selected public evidence, not zero.",
              "The historical 27B D3 is neither an Ultra nor a Turbo observation; neither variant was evaluated here.", "",
              "² CPU-H: historical Linux/WSL CPU runs (processor not identified here); API: remote service with unknown server hardware;",
              "Metal: native llama.cpp on Apple M5 Pro; MPS: official PyTorch pipeline on Apple M5 Pro;",
              "CPU-N: newer macOS CPU run; Metal-U: direct upstream native listener, separate from gateway-backed historical runs. Runtime, readout, serializer, precision, and input lengths differ.",
              "Not run in the tool column means no 24-case first-tool observation was published for that runtime; it is not zero accuracy. "
              "Later passage anchors reproduce the published D3 124/132 (test 61/66) and Clef 110/132 (test 59/66) totals; "
              "those repeated checks are not additional leaderboard models.", "",
              "## Language and task complexity", "",
              "D1/D2/D3 are authored context-task strata, **not predictions of difficulty or evidence that escalation helps**.",
              "A correct choice also does not prove that a plugin was executed or a useful answer generated.", "",
              "| Model observation | FR /66 | EN /66 | D1 /40 | D2 /40 | D3 /52 | Scored /132 | Tool valid /24 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in data["observations"]:
        g = row["context"]["groups"]
        values = [g["language"][key]["correct"] for key in ("fr", "en")] + [g["difficulty"][key]["correct"] for key in ("D1", "D2", "D3")]
        lines.append("| " + row["metadata"]["display_name"] + " | " + " | ".join(map(str, values)) +
                     f" | {row['context']['counts']['scored']} | {row['tool_proposal']['counts']['valid_decisions'] if row['tool_proposal'] else 'Not run'} |")
    lines += ["", "## Speed and memory", "",
              "These are **context-choice adapter observations**, not controlled cross-hardware speed rankings.",
              "Latency includes the adapter's recorded boundary and successful calls only; cold initialization is separate.",
              "Remote latency includes its network/API path; server memory is unknown. One-pass p95 is descriptive, not a tail guarantee.",
              "[Repeated timing and stability](leaderboard/other-benchmarks.md#repeated-timing-and-stability) use separate campaigns.", "",
              "**RSS and GPU allocations are different measurements: never add them.** Neither establishes total unified-memory use.",
              "RSS below is worker peak for the context phase unless marked **S**, which is a sampled process-group peak over",
              "the session specified in the CSV (historical context + tool, or a fresh context-only session). An allocation or peak is not a minimum-memory requirement; allow runtime/OS headroom.",
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
              "NR means unreported; GPU NR must not be read as zero. Sizes, weight-file sizes, RSS, and GPU allocation are different quantities.", ""]
    lines += render_other_protocols(data["other_benchmarks_markdown"])
    lines += [
              "## Every task and downloadable data", "",
              f"- [Model summary CSV](leaderboard/models.csv): all {len(data['observations'])} context observations, model sizes, runtimes, quality, latency, and separate resource measurements.",
              "- [Coverage CSV](leaderboard/coverage.csv) and [coverage JSON](leaderboard/coverage.json): every observation × task cell, explicit execution and review status, protocol denominator, source, and unobserved fields.",
              "- [Campaign summary CSV](leaderboard/campaigns.csv): independent capability, physics and passage rankings, coverage, test scores, class macro scores and measured resource scopes.",
              "- [Task breakdown CSV](leaderboard/task-breakdown.csv): exported context task types/subtypes, domains, languages, splits and difficulty; tool-choice subgroups; plus capability, physics and passage groups, with task-specific denominators.",
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
    glance = render_at_a_glance(data)
    return "\n".join(header + render_toc(glance + lines) + glance + lines)



MODEL_PAGES_DIR = "docs/leaderboard/by-model/"  # not "models/": that name is a privacy ignore rule for weights
RUNTIME_LABELS = {"historical_cpu": "Historical Linux/WSL CPU (processor not identified)", "remote_api": "Remote HTTP API (server hardware unknown)",
                  "apple_metal_native": "Native llama.cpp Metal, Apple M5 Pro", "apple_mps": "PyTorch MPS, Apple M5 Pro",
                  "cpu_new": "macOS arm64 CPU, pinned runtime",
                  "private_replay": "Private local replay at a pinned revision; not externally reproducible", "apple_metal_upstream": "Direct upstream native Metal, Apple M5 Pro"}
PAGE_TASKS = (("context", "Context choices", "RAG decision", "RESULTS.md#model-quality"),
              ("tool_proposal", "First-tool proposals", "RAG decision", "RESULTS.md#model-quality"),
              ("capability", "Capability and workflow choices", "Tool workflow", "RESULTS.md#capability-choices"),
              ("physics", "Physics choices", "Reasoning with a supplied law", "RESULTS.md#physics-choices"),
              ("choice_episodes", "Executed tool episodes (closed choice)", "Tool workflow, executed", "RESULTS.md#executed-tool-episodes-closed-choice"),
              ("facade_routing", "Facade routing (model vs router)", "Tool routing", "RESULTS.md#facade-routing-model-vs-router"),
              ("passage_relevance", "Passage relevance", "Retrieved evidence", "RESULTS.md#passage-relevance"),
              ("passage_support", "Claim support", "Retrieved evidence", "RESULTS.md#claim-support"),
              ("passage_answerability", "Answerability", "Retrieved evidence", "RESULTS.md#answerability"),
              ("passage_relevance_four_rotations", "Passage relevance, four rotations", "Retrieved evidence", "RESULTS.md#passage-relevance"),
              ("passage_ranking", "Passage ranking", "Retrieved evidence", "leaderboard/other-benchmarks.md#passage-ranking-and-evidence"),
              ("tool_discovery", "Tool discovery (generated JSON)", "Tool policy, generated", "RESULTS.md#generated-json-tool-policy-observations"),
              ("tool_arguments", "Tool arguments (generated JSON)", "Tool policy, generated", "RESULTS.md#generated-json-tool-policy-observations"),
              ("tool_episodes", "Tool episodes (generated JSON)", "Tool policy, generated", "RESULTS.md#generated-json-tool-policy-observations"))


def _page_link(path):
    """Relative link from the model-pages directory to a repository path."""
    path = str(path)
    return "../../" + path[len("docs/"):] if path.startswith("docs/") else "../../../" + path


def _score_text(cell):
    """Score of an observed cell; never invent a correct count for a metric that has none."""
    if cell["metric"] == "ndcg@1":
        return f"nDCG@1 {cell['metric_value']:.3f} ({cell['metric_defined']}/{cell['metric_eligible']} defined of {cell['total']})"
    if cell["numerator"] is None:
        return f"0/{cell['total']} scored"
    return f"{cell['numerator']}/{cell['total']}"


def _page_cell(cell, rank=None):
    if not cell["evidence_present"]:
        return "not run"
    text = _score_text(cell)
    if cell["status"] == "partial":
        text += f" (partial, {cell['scored_or_valid']} scored)"
    elif cell["status"] == "not_run":
        text += " (attempted, nothing scored)"
    if rank:
        text += f" · rank {rank}"
    return text


def _outcomes_text(cell):
    if not cell["evidence_present"]:
        return "—"
    bad = {k: v for k, v in cell["outcomes"].items() if k != "ok" and v}
    return "all `ok`" if not bad else ", ".join(f"{v} `{k}`" for k, v in sorted(bad.items()))


def render_model_pages(data):
    """One page per observation with every task, its rank, its execution outcomes and the report links; plus an index."""
    context = {r["id"]: r for r in data["observations"]}
    ranks = {}
    for row in data["campaigns"]:
        ranks[(row["task"], row["observation"])] = row
    def campaign_row(task, oid):
        return ranks.get((task, oid)) or ranks.get((task, oid.removesuffix("Passage")))
    pages, index_rows = {}, []
    for obs in data["coverage"]["observations"]:
        oid, cells = obs["id"], obs["cells"]
        ctx = context.get(oid)
        meta = ctx["metadata"] if ctx else None
        name = meta["display_name"] if meta else obs["model"]
        lines = [f"# {name}", "",
                 f"[All results](../../RESULTS.md) · [All models](README.md) · [Coverage overview](../../RESULTS.md#coverage-overview)", "",
                 "One observation: one checkpoint, one runtime, one pass per case. Scores are **correct / all cases** with "
                 "failures kept in the denominator; **rank** is the competition rank among completely scored observations on the "
                 "same task. References are agent-authored and pending human review; a few-case lead on correlated FR/EN variants "
                 "is not a general ranking.", "",
                 "## Identity", "", "| Item | Value |", "|---|---|",
                 f"| Size | {meta['model_size']['label'] if meta and meta['model_size']['label'] else obs.get('size') or 'NR'} |",
                 f"| Runtime | {RUNTIME_LABELS.get(meta['runtime_group'], meta['runtime_group']) if meta else RUNTIME_LABELS.get(obs.get('runtime'), obs.get('runtime')) or 'NR'} |"]
        if meta:
            lines += [f"| Family | {meta['family']} |", f"| Precision | {meta['precision']} |",
                      f"| Hardware | {meta['hardware_group']} |", f"| Observed | {meta['observed_date']} |",
                      "| Protocol / evidence | " + ", ".join(f"[{Path(e['path']).name}]({_page_link(e['path'])})" for e in meta["evidence"]) + " |"]
        lines += ["", "## Results by task", "",
                  "| Family | Task | Correct / all | Held-out test | Rank all | Rank test | Execution | Report |", "|---|---|---:|---:|---:|---:|---|---|"]
        index = {"name": name, "id": oid, "ctx": ctx}
        for task, title, family, section in PAGE_TASKS:
            cell = cells.get(task)
            if cell is None:
                continue
            if task == "context" and ctx:
                test = f"{ctx['context']['groups']['split']['test']['correct']}/66"
                rank_all, rank_test = ctx["rank_all_splits"], ctx["rank_test_splits"]
                report = ", ".join(f"[{Path(e['path']).stem}]({_page_link(e['path'])})" for e in meta["evidence"])
            elif task == "tool_proposal" and ctx and ctx["tool_proposal"]:
                test, rank_all, rank_test = "no test split", "—", "—"
                report = "provisional agreement, zero qualified cases"
            elif task == "facade_routing":
                row = next((r for r in data["facade_routing"] if r["observation"] == oid), None)
                if row:
                    test = f"{row['counts']['by_split']['test']['correct']}/{row['counts']['by_split']['test']['total']}"
                    rank_all, rank_test = row["rank_all"], row["rank_test"]
                    report = f"[report](../../{row['report']})"
                else:
                    test, rank_all, rank_test, report = "—", "—", "—", "—"
            elif task == "choice_episodes":
                row = next((r for r in data["choice_episodes"] if r["observation"] == oid), None)
                if row:
                    test = f"{row['counts']['test']['procedure_correct_cases']}/{row['counts']['test']['total_cases']}"
                    rank_all, rank_test = row["rank_all"], row["rank_test"]
                    report = f"[report](../../{row['report']})"
                else:
                    test, rank_all, rank_test, report = "—", "—", "—", "—"
            else:
                row = campaign_row(task, oid)
                if row:
                    by_split = row["counts"].get("by_split") or {}
                    test = f"{by_split['test']['correct']}/{by_split['test']['total']}" if "test" in by_split else "no split ranking"
                    rank_all, rank_test = row.get("rank_all") or "—", row.get("rank_test") or "—"
                    report = f"[report](../../{row['report']})" if row.get("report") else "—"
                else:
                    test, rank_all, rank_test, report = "—", "—", "—", "—"
            if cell["status"] == "not_run":
                test, rank_all, rank_test = "—", "—", "—"
                if not cell["evidence_present"]:
                    report = "—"
            section_link = f"[{title}](../../{section})"
            lines.append(f"| {family} | {section_link} | {_page_cell(cell)} | {test} | {rank_all} | {rank_test} | {_outcomes_text(cell)} | {report} |")
            index[task] = (cell, rank_all if cell["status"] == "complete" else None)
        if ctx and ctx.get("resources"):
            r = ctx["resources"]
            gpu = r.get("sampled_gpu_allocated_peak_mib")
            rss = r.get("session_process_group_peak_rss_mib")
            worker = (r.get("worker_rss_mib") or {}).get("max")
            lines += ["", "## Speed and memory (context session)", "", "| Median call ms | p95 call ms | Timed calls | Initialization ms | Session RSS GiB | Worker RSS GiB | GPU allocated GiB |", "|---:|---:|---:|---:|---:|---:|---:|",
                      f"| {number(r['adapter_ms']['median'])} | {number(r['adapter_ms']['p95'])} | {r['adapter_ms']['count']} | {number(r.get('initialization_ms'))} | "
                      f"{number(rss / 1024 if rss is not None else None, 2)} | {number(worker / 1024 if worker is not None else None, 2)} | {number(gpu / 1024 if gpu is not None else None, 2)} |", "",
                      f"Scope: {r.get('rss_scope', 'as recorded in the source aggregate')}. Latency is descriptive, not a throughput guarantee."]
        lines += ["", "## Reading this page", "",
                  "- **Execution** says whether the campaign ran cleanly: `all ok` means every case produced a valid answer; other statuses "
                  "(`timeout`, `error`, `missing`, `unsupported`, `abstain`) are counted and stay in the denominator of the score.",
                  "- **not run** means no public observation for this task on this runtime; it is not a zero.",
                  "- Partial campaigns are shown with their scored count and are never ranked.",
                  "- Generated regularly from the sealed public aggregates by `scripts/build-full-results.py`; nothing here reruns a model.", ""]
        pages[MODEL_PAGES_DIR + oid + ".md"] = "\n".join(lines)
        index_rows.append(index)
    def sort_key(row):
        ctx = row["ctx"]
        return (0 if ctx else 1, ctx["rank_all_splits"] if ctx else 0, row["name"])
    index_rows.sort(key=sort_key)
    def index_cell(row, task):
        entry = row.get(task)
        if entry is None or not entry[0]["evidence_present"]:
            return "—"
        cell, rank = entry
        text = _score_text(cell)
        if cell["status"] == "partial":
            text += " partial"
        elif cell["status"] == "not_run":
            text += ", attempted"
        elif rank and rank != "—":
            text += f" (#{rank})"
        return text
    lines = ["# Every model, every task", "",
             f"[All results](../../RESULTS.md) · [At a glance](../../RESULTS.md#at-a-glance) · [Coverage overview](../../RESULTS.md#coverage-overview)", "",
             f"{len(index_rows)} observations. One line per model/runtime observation; each cell is **correct / all cases** on that task with its "
             "competition rank in parentheses, `partial` when the campaign did not complete, and **—** when the task was not run on that runtime. "
             "Context observations come first, in context rank order; passage-only methods and the generative candidate follow. "
             "Click the model for its page with every task, execution outcomes, speed and reports.", "",
             "| Model / runtime | Context /132 | Tool /24 | Capability /192 | Physics /48 | Episodes (choice) /32 | Facade routing /80 | Relevance /512 | Support /768 | Answerability /128 | Generated JSON (discovery, arguments, episodes) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for row in index_rows:
        generated = ", ".join(index_cell(row, t) for t in ("tool_discovery", "tool_arguments", "tool_episodes"))
        generated = "—" if generated == "—, —, —" else generated
        lines.append(f"| [{row['name']}]({row['id']}.md) | {index_cell(row, 'context')} | {index_cell(row, 'tool_proposal')} | {index_cell(row, 'capability')} | "
                     f"{index_cell(row, 'physics')} | {index_cell(row, 'choice_episodes')} | {index_cell(row, 'facade_routing')} | {index_cell(row, 'passage_relevance')} | {index_cell(row, 'passage_support')} | {index_cell(row, 'passage_answerability')} | {generated} |")
    lines += ["", "Tool /24 is provisional agreement with agent-authored first-tool proposals, not routing accuracy; it has no rank. "
              "Passage scores are rotation 0 (128 pools × decisions); the four-rotation Jev export and the ranking methods are on each model page and in "
              "[other benchmarks](../other-benchmarks.md). Generated regularly by `scripts/build-full-results.py`.", ""]
    pages[MODEL_PAGES_DIR + "README.md"] = "\n".join(lines)
    return pages

def outputs(data):
    models, tasks = flat_rows(data)
    return {"docs/RESULTS.md": render(data), "docs/leaderboard/models.csv": csv_text(models),
            "docs/leaderboard/coverage.csv": csv_text(coverage_csv_rows(data["coverage"])),
            "docs/leaderboard/coverage.json": json.dumps(data["coverage"], ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
            "docs/leaderboard/campaigns.csv": csv_text(campaign_csv_rows(data)),
            "docs/leaderboard/task-breakdown.csv": csv_text(tasks),
            "docs/leaderboard/results.json": json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
            **render_model_pages(data)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    try:
        generated_data = build()
        generated = outputs(generated_data)
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
    print(f"Full results: {len(generated_data['observations'])} context observations; views " + ("written" if args.write else "current"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
