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
    inputs.read("scripts/build-full-results.py")
    return {"schema_version": "deposium.public-results/v1", "observations": rows,
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


def render(data):
    lines = ["# Full results", "", "[README](../README.md) · [Quality](#model-quality) · [Language and task complexity](#language-and-task-complexity) ·",
             "[Speed and memory](#speed-and-memory) · [Passages and other campaigns](leaderboard/other-benchmarks.md) ·",
             "[Proposed tool and model routing](INTENT_AND_MODEL_ROUTING.md)", "",
             "**28 model/runtime observations**, consolidated from the public frozen exports through 28 October 2026.",
             "Rows identify observations, not 28 independent model families. Repeated exports of the same sealed run are deduplicated;",
             "quantizations and devices remain separate. This page is generated offline; no model was rerun or rescored.", "",
             "**Exploratory evidence:** synthetic, agent-authored references and translations await human review.",
             "The ranking uses all 132 cases (train + calibration + test); the separate test column uses 66 cases.",
             "FR/EN translations form 66 families. Differences of a few answers do not establish a general model ranking.", "",
             "## What was actually tested?", "",
             "| Task | Common input and denominator | Status |", "|---|---|---|",
             "| Documentary text and choices | 76 context-dependent choices | Scored exploratory decisions |",
             "| Mathematics / chemistry | 28 / 28 constrained choices | Scored synthetic probes, not expert scientific qualification |",
             "| First tool proposal | 24 search / statistics / fallback choices | Provisional agreement only; no tool execution; **0 semantically qualified cases** |",
             "| Physics | No dedicated pack | **Not run** |",
             "| Passage ranking, relevance, support, answerability | Separate fixed-passage campaigns | [Full tables and coverage](leaderboard/other-benchmarks.md) |",
             "| General plugin/MCP selection, execution loop, difficulty prediction, adaptive model routing | Proposed feature | **Not run**; [experiment design](INTENT_AND_MODEL_ROUTING.md) |",
             "| End-to-end RAG and generated-answer quality | No campaign qualified here | **Not run** |", "",
             "## Model quality", "",
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
