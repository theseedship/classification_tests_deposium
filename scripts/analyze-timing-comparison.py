"""Recompute aggregate observations from sealed timing archives, without inference."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from deposium_bench import campaigns
from deposium_bench.cases import candidate_request, validate_cases
from deposium_bench.context_analysis import _stats
from deposium_bench.scoring import STATUSES, score_case, summarize
from deposium_bench.timing import _distribution

SCHEMA = "deposium.timing-comparison-analysis/v1"
DATASETS = ("context", "task")
SOURCES = ("scripts/analyze-timing-comparison.py", "deposium_bench/timing.py",
           "deposium_bench/scoring.py", "deposium_bench/campaigns.py",
           "deposium_bench/context_analysis.py")
SAFE_LABEL = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,95}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")


class AnalysisError(ValueError):
    pass


def _decode(data: bytes):
    try:
        return campaigns._decode(data)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise AnalysisError("invalid_json") from exc


def _jsonl(data: bytes) -> list[dict]:
    if not data or not data.endswith(b"\n") or b"\n\n" in data:
        raise AnalysisError("invalid_jsonl")
    return [_decode(line) for line in data.splitlines()]


def _files(archive: Path) -> tuple[dict[str, bytes], dict, str]:
    if archive.is_symlink() or not archive.is_dir():
        raise AnalysisError("archive_missing")
    seal_bytes = (archive / "seal.json").read_bytes()
    seal = _decode(seal_bytes)
    if (not isinstance(seal, dict) or set(seal) != {"schema_version", "files", "sha256"}
            or seal["schema_version"] != "deposium.timing-seal/v1"
            or not isinstance(seal["files"], dict)
            or seal["sha256"] != campaigns._hash(campaigns._encode(seal["files"]))):
        raise AnalysisError("seal_invalid")
    entries = list(archive.rglob("*"))
    if any(p.is_symlink() or (not p.is_file() and not p.is_dir()) for p in entries):
        raise AnalysisError("inventory_invalid")
    inventory = {str(p.relative_to(archive)) for p in entries if p.is_file()}
    if inventory != set(seal["files"]) | {"seal.json"}:
        raise AnalysisError("inventory_invalid")
    required = {"cases.jsonl", "timing-manifest.json", "trials.jsonl", "summary.json", "report.md"}
    if not required <= set(seal["files"]):
        raise AnalysisError("inventory_missing")
    payload = {}
    for name, digest in seal["files"].items():
        parts = Path(name).parts
        if (not parts or any(part in {".", ".."} for part in parts) or Path(name).is_absolute()
                or not isinstance(digest, str) or not SHA.fullmatch(digest)):
            raise AnalysisError("inventory_invalid")
        path = archive / name
        if path.is_symlink() or not path.is_file():
            raise AnalysisError("inventory_invalid")
        data = path.read_bytes()
        if campaigns._hash(data) != digest:
            raise AnalysisError("seal_mismatch")
        payload[name] = data
    return payload, seal, campaigns._hash(seal_bytes)


def _safe_provenance(value: dict) -> dict:
    """Explicit scalar allowlist; never copy raw settings, paths or secrets."""
    if not isinstance(value, dict):
        raise AnalysisError("provenance_invalid")
    answer = {}
    for key in ("identity_sha256", "adapter_sha256", "model_assets_sha256",
                "runtime_lock_sha256", "source_manifest_sha256", "binary_sha256",
                "choice_protocol_sha256", "worker_sha256", "prompt_sha256",
                "bridge_sha256", "resident_bridge_sha256", "build_manifest_sha256",
                "helper_sha256", "budget_helper_sha256", "budget_policy_sha256"):
        item = value.get(key)
        if isinstance(item, str) and SHA.fullmatch(item):
            answer[key] = item
    for key in ("model_revision", "source_revision"):
        item = value.get(key)
        if isinstance(item, str) and re.fullmatch(r"[0-9a-f]{7,64}", item):
            answer[key] = item
    runtime = value.get("runtime")
    if isinstance(runtime, dict):
        answer["runtime"] = {key: item for key, item in runtime.items()
                             if key in {"python", "node", "torch", "transformers", "onnxruntime",
                                        "llama_cpp", "gliner", "gliner2", "indecis", "numpy",
                                        "tokenizers", "openssl", "go", "goarch", "goos",
                                        "indecis_revision", "backbone_revision", "parent_python",
                                        "tsx", "zod"}
                             and isinstance(item, str) and len(item) <= 80
                             and re.fullmatch(r"[A-Za-z0-9 ._+:-]+", item)}
    return answer


def _validate_sequence(trials: list[dict], cases: list[dict], profiles: list[dict], protocol: dict) -> None:
    names = [profile["candidate"] for profile in profiles]
    expected = []
    for launch in range(protocol["launches"]):
        for candidate in (names if launch % 2 == 0 else names[::-1]):
            expected.append((launch, candidate, "cold", None, cases[0]["case_id"]))
            for index in range(protocol["warmup"]):
                expected.append((launch, candidate, "warmup", index,
                                 cases[index % len(cases)]["case_id"]))
            for index in range(protocol["passes"]):
                expected.extend((launch, candidate, "measured", index, case["case_id"])
                                for case in cases)
    actual = []
    case_map = {case["case_id"]: case for case in cases}
    result_fields = {"schema_version", "case_id", "contract_id", "request_sha256", "status",
                     "output", "raw_output", "error", "duration_ms"}
    for trial in trials:
        if not isinstance(trial, dict) or set(trial) != {"launch", "candidate", "phase", "pass_index", "result"}:
            raise AnalysisError("trial_shape_invalid")
        result = trial["result"]
        if (not isinstance(result, dict) or set(result) != result_fields
                or not isinstance(result.get("case_id"), str)
                or result["case_id"] not in case_map):
            raise AnalysisError("trial_result_invalid")
        case = case_map[result["case_id"]]
        duration = result["duration_ms"]
        if (result["schema_version"] != campaigns.RESULT_VERSION
                or result["contract_id"] != case["contract_id"]
                or result["request_sha256"] != campaigns._hash(campaigns._encode(candidate_request(case)))
                or result["status"] not in STATUSES
                or result["error"] is not None and not isinstance(result["error"], str)
                or type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0):
            raise AnalysisError("trial_result_contract_mismatch")
        actual.append((trial["launch"], trial["candidate"], trial["phase"],
                       trial["pass_index"], result["case_id"]))
    if actual != expected or protocol["total_planned_calls"] != len(expected):
        raise AnalysisError("trial_protocol_mismatch")


def _historical_distribution_matches(archived: dict, computed: dict) -> bool:
    """Older summaries use null for HTTP/provider fields absent from that runner."""
    for field in ("recorded_calls", "counts_by_status", "rss_mib"):
        if archived.get(field) != computed[field]:
            return False
    for section in ("latency", "successful_latency"):
        for field in ("adapter_duration_ms", "decision_ms", "inference_ms", "http_ms"):
            old, new = archived[section].get(field), computed[section][field]
            if old is None and field == "http_ms" and new["count"] == 0:
                continue
            if old != new:
                return False
    if archived.get("provider_usage") is not None and archived["provider_usage"] != computed["provider_usage"]:
        return False
    return True


def analyze_one(label: str, archive: Path) -> dict:
    if not SAFE_LABEL.fullmatch(label):
        raise AnalysisError("invalid_label")
    payload, seal, seal_sha = _files(archive)
    manifest = _decode(payload["timing-manifest.json"])
    summary = _decode(payload["summary.json"])
    cases, trials = _jsonl(payload["cases.jsonl"]), _jsonl(payload["trials.jsonl"])
    validate_cases(cases)
    if (manifest.get("schema_version") != "deposium.timing/v1"
            or summary.get("schema_version") != "deposium.timing-summary/v1"
            or summary.get("completion_status") != "complete" or summary.get("error_type") is not None
            or manifest.get("dataset_sha256") != campaigns._hash(payload["cases.jsonl"])
            or manifest.get("case_ids") != [case["case_id"] for case in cases]
            or manifest.get("independent_families") != len({case["translation_family"] for case in cases})
            or summary.get("trials_sha256") != campaigns._hash(payload["trials.jsonl"])
            or summary.get("recorded_calls") != len(trials)
            or summary.get("planned_calls") != len(trials)
            or summary.get("independent_families") != manifest["independent_families"]
            or manifest.get("scorer") != campaigns._scorer_fingerprint()):
        raise AnalysisError("timing_manifest_summary_mismatch")
    assertion_paths = {tuple(assertion["path"] for assertion in case["reference"]["assertions"])
                       for case in cases}
    dataset = ({("/choice_id",): "context", ("/task",): "task"}.get(next(iter(assertion_paths)))
               if len(assertion_paths) == 1 else None)
    if dataset is None:
        raise AnalysisError("dataset_unknown")
    profiles, protocol = manifest["profiles"], manifest["protocol"]
    if (not isinstance(profiles, list) or not 1 <= len(profiles) <= 10
            or len({p["candidate"] for p in profiles}) != len(profiles)
            or any(not SAFE_LABEL.fullmatch(p["candidate"]) for p in profiles)
            or any(type(protocol.get(key)) is not int for key in ("launches", "warmup", "passes", "total_planned_calls"))
            or not 1 <= protocol["launches"] <= 10 or not 0 <= protocol["warmup"] <= 100
            or not 1 <= protocol["passes"] <= 100
            or not 1 <= protocol["total_planned_calls"] <= 100_000
            or set(summary.get("candidates", {})) != {p["candidate"] for p in profiles}):
        raise AnalysisError("protocol_invalid")
    computed_calls = protocol["launches"] * len(profiles) * (
        1 + protocol["warmup"] + protocol["passes"] * len(cases))
    if computed_calls != protocol["total_planned_calls"] or computed_calls > 100_000:
        raise AnalysisError("protocol_budget_invalid")
    _validate_sequence(trials, cases, profiles, protocol)
    observations = {}
    for index, profile in enumerate(profiles):
        name = profile["candidate"]
        archived_profile = _decode(payload[f"candidate-{index}/profile.json"])
        if (archived_profile.get("profile_id") != name
                or campaigns._hash(campaigns._encode(archived_profile)) != profile.get("profile_sha256")):
            raise AnalysisError("profile_identity_mismatch")
        asset_name = f"candidate-{index}/assets-manifest.json"
        if profile.get("assets_manifest_sha256") is not None and (
                asset_name not in payload or campaigns._hash(payload[asset_name]) != profile["assets_manifest_sha256"]):
            raise AnalysisError("profile_assets_mismatch")
        selected = [trial for trial in trials if trial["candidate"] == name]
        launches = [_decode(payload[f"launch-{launch}-{index}.json"])
                    for launch in range(protocol["launches"])]
        if (any(item.get("candidate") != name or item.get("launch") != launch
                for launch, item in enumerate(launches))
                or len({item.get("adapter_provenance", {}).get("identity_sha256") for item in launches}) != 1
                or not launches[0].get("adapter_provenance", {}).get("identity_sha256")
                or any(item.get("adapter_provenance", {}).get("adapter") != archived_profile.get("adapter")
                       or (item.get("adapter_provenance", {}).get("model_revision") is not None
                           and item["adapter_provenance"]["model_revision"] != archived_profile.get("revision"))
                       for item in launches)):
            raise AnalysisError("launch_identity_mismatch")
        archived = summary["candidates"][name]
        phases = {phase: _distribution([t for t in selected if t["phase"] == phase])
                  for phase in ("cold", "warmup", "measured")}
        initialization = _stats([item["init_wall_ms"] for item in launches])
        per_pass = []
        for launch in range(protocol["launches"]):
            for iteration in range(protocol["passes"]):
                records = [t["result"] for t in selected if t["phase"] == "measured"
                           and t["launch"] == launch and t["pass_index"] == iteration]
                per_pass.append({"launch": launch, "pass_index": iteration,
                                 "metrics": summarize(cases, records)})
        by_launch = {str(launch): _distribution([t for t in selected if t["phase"] == "measured"
                                                 and t["launch"] == launch])
                     for launch in range(protocol["launches"])}
        if (any(not _historical_distribution_matches(archived["phases"][phase], value)
                for phase, value in phases.items())
                or archived["initialization_ms"] != initialization
                or archived["per_pass_quality"] != per_pass
                or any(not _historical_distribution_matches(archived["by_launch"][launch], value)
                       for launch, value in by_launch.items())
                or archived["launches"] != launches):
            raise AnalysisError("summary_recalculation_mismatch")
        measured = [t for t in selected if t["phase"] == "measured"]
        choices = defaultdict(set)
        case_results = defaultdict(list)
        for trial in measured:
            result = trial["result"]
            case_results[result["case_id"]].append(result)
            if result["status"] == "ok" and isinstance(result.get("output"), dict):
                choice = result["output"].get("choice_id" if dataset == "context" else "task")
                if isinstance(choice, str):
                    choices[result["case_id"]].add(choice)
        scored = [score_case(case, result) for case in cases
                  for result in case_results[case["case_id"]]]
        if not any(item["scored"] for item in scored):
            raise AnalysisError("zero_scored_calls")
        distributions = {phase: {"calls": item["recorded_calls"], "statuses": item["counts_by_status"],
                                  "adapter_ms": item["latency"]["adapter_duration_ms"],
                                  "decision_ms": item["latency"]["decision_ms"],
                                  "inference_ms": item["latency"]["inference_ms"],
                                  "http_ms": item["latency"]["http_ms"], "rss_mib": item["rss_mib"]}
                         for phase, item in phases.items()}
        observations[name] = {"profile_sha256": profile["profile_sha256"],
                              "source_profile_sha256": profile["source_profile_sha256"],
                              "declared_revision": (archived_profile.get("revision")
                                                    if isinstance(archived_profile.get("revision"), str)
                                                    and re.fullmatch(r"[A-Za-z0-9_.+-]{1,80}", archived_profile["revision"])
                                                    else None),
                              "provenance": _safe_provenance(launches[0]["adapter_provenance"]),
                              "initialization_ms": initialization,
                              "reported_load_ms": _stats([item["adapter_provenance"].get("load_ms",
                                                              item["adapter_provenance"].get("worker_load_ms"))
                                                          for item in launches]),
                              "reported_load_rss_mib": _stats([item["adapter_provenance"].get("load_rss_mb")
                                                               for item in launches]),
                              "phases": distributions,
                              "measured_by_launch": {launch: {"decision_ms": item["latency"]["decision_ms"],
                                                               "inference_ms": item["latency"]["inference_ms"],
                                                               "http_ms": item["latency"]["http_ms"]}
                                                     for launch, item in by_launch.items()},
                              "per_pass": [{"launch": row["launch"], "pass_index": row["pass_index"],
                                            "total_cases": row["metrics"]["total_cases"],
                                            "scored_cases": row["metrics"]["scored_cases"],
                                            "passed_cases": row["metrics"]["passed_cases"],
                                            "coverage": row["metrics"]["coverage"]} for row in per_pass],
                              "repeated_quality": {"measured_calls": len(measured),
                                                   "scored_calls": sum(x["scored"] for x in scored),
                                                   "passed_calls": sum(x["passed"] for x in scored),
                                                   "cases_with_variable_choice": sum(len(v) > 1 for v in choices.values()),
                                                   "cases_with_observed_choice": len(choices),
                                                   "independent_cases": len(cases),
                                                   "independent_families": manifest["independent_families"]}}
    return {"label": label, "dataset": dataset, "archive_seal_sha256": seal_sha,
            "dataset_sha256": manifest["dataset_sha256"], "trials_sha256": summary["trials_sha256"],
            "bench_sha256": manifest["bench"].get("sha256"),
            "scorer_sha256": manifest["scorer"].get("sha256"),
            "platform": {key: manifest.get("platform", {}).get(key) for key in ("system", "machine", "python", "logical_cpus")},
            "protocol": {key: protocol[key] for key in ("launches", "warmup", "passes", "total_planned_calls")},
            "cases": len(cases), "independent_families": manifest["independent_families"],
            "candidates": observations}


def analyze(timings: list[tuple[str, Path]], output_dir: Path) -> dict:
    if not timings or len({label for label, _ in timings}) != len(timings):
        raise AnalysisError("timing_labels_invalid")
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(output_dir)
    if any(output_dir.is_relative_to(path.resolve()) for _, path in timings):
        raise AnalysisError("output_inside_input")
    source_hashes = {name: campaigns._hash((ROOT / name).read_bytes()) for name in SOURCES}
    results = [analyze_one(label, path.resolve()) for label, path in timings]
    groups = {kind: [item for item in results if item["dataset"] == kind] for kind in DATASETS}
    for group in groups.values():
        if len({item["dataset_sha256"] for item in group}) > 1:
            raise AnalysisError("mixed_dataset")
    analysis = {"schema_version": SCHEMA, "producer_sha256": source_hashes,
                "groups": groups, "not_measured": ["EOS", "Noma", "Laya"],
                "limits": ["Repeated calls do not increase the independent case or family denominator.",
                           "Cold means first adapter call; OS caches and remote server state were not reset.",
                           "HTTP is client-side timing; server timing and remote RSS are unobserved.",
                           "Context choice and document task corpora are separate and have no combined ranking."]}
    raw = campaigns._encode(analysis)
    report = render(analysis).encode("utf-8")
    if any(campaigns._hash((ROOT / name).read_bytes()) != digest for name, digest in source_hashes.items()):
        raise AnalysisError("producer_changed")
    if any(campaigns._hash((path.resolve() / "seal.json").read_bytes()) != result["archive_seal_sha256"]
           for (_, path), result in zip(timings, results)):
        raise AnalysisError("input_seal_changed")
    output_dir.mkdir(parents=True, exist_ok=False)
    campaigns._write_new(output_dir / "analysis.json", raw)
    campaigns._write_new(output_dir / "report.md", report)
    return analysis


def render(analysis: dict) -> str:
    def cell(stat):
        return ("unobserved (n=0)" if stat["count"] == 0 else
                f"{stat['count']}/{stat['min']:.3f}/{stat['median']:.3f}/{stat['p95']:.3f}/{stat['max']:.3f}")
    lines = ["# Repeated timing archive comparison", "",
             "Timing cells show n/min/median/p95/max in milliseconds; RSS cells show observed n and max MiB.",
             "Cold, warmup and measured calls are separate. Warmup never enters measured-pass quality.", ""]
    for kind, title in (("context", "Context choice"), ("task", "Document task")):
        group = analysis["groups"][kind]
        suffix = f": {group[0]['cases']} cases, {group[0]['independent_families']} families" if group else ": not measured"
        lines += [f"## {title}{suffix}", "", "| Archive | Candidate | Phase | Calls | OK | Adapter | Decision | Inference | HTTP | RSS n/max |",
                  "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
        for item in analysis["groups"][kind]:
            for candidate, info in sorted(item["candidates"].items()):
                for phase in ("cold", "warmup", "measured"):
                    dist = info["phases"][phase]
                    rss = dist["rss_mib"]
                    rss_text = f"{rss['count']}/{rss['max']:.3f}" if rss["count"] else "0/unobserved"
                    lines.append(f"| {item['label']} | {candidate} | {phase} | {dist['calls']} | "
                                 f"{dist['statuses']['ok']} | {cell(dist['adapter_ms'])} | "
                                 f"{cell(dist['decision_ms'])} | {cell(dist['inference_ms'])} | "
                                 f"{cell(dist['http_ms'])} | {rss_text} |")
        lines += ["", "| Archive | Candidate | Initialization ms | Reported load ms | Load RSS n/max MiB | Passed / scored calls | Passed per pass | Variable choice cases | Decision medians by launch ms |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---|"]
        for item in analysis["groups"][kind]:
            for candidate, info in sorted(item["candidates"].items()):
                q = info["repeated_quality"]
                passes = info["per_pass"]
                pass_range = (f"{min(p['passed_cases'] for p in passes)}–{max(p['passed_cases'] for p in passes)}"
                              if passes else "unobserved")
                launch_medians = [value["decision_ms"]["median"]
                                  for value in info["measured_by_launch"].values()
                                  if value["decision_ms"]["median"] is not None]
                load_rss = info["reported_load_rss_mib"]
                load_rss_text = (f"{load_rss['count']}/{load_rss['max']:.3f}"
                                 if load_rss["count"] else "0/unobserved")
                lines.append(f"| {item['label']} | {candidate} | {cell(info['initialization_ms'])} | "
                             f"{cell(info['reported_load_ms'])} | {load_rss_text} | "
                             f"{q['passed_calls']}/{q['scored_calls']} | {pass_range}/{q['independent_cases']} | "
                             f"{q['cases_with_variable_choice']}/{q['independent_cases']} | "
                             f"{', '.join(f'{value:.3f}' for value in launch_medians) or 'unobserved'} |")
        lines.append("")
    lines += ["EOS, Noma and Laya: not measured in these archives.", "",
              "These are historical local/API observations, not a new model run or product qualification.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timing", action="append", required=True, metavar="LABEL=ARCHIVE")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    timings = []
    for spec in args.timing:
        label, separator, path = spec.partition("=")
        if not separator or not path:
            parser.error("--timing requires LABEL=ARCHIVE")
        timings.append((label, Path(path)))
    analyze(timings, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
