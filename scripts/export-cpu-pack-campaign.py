#!/usr/bin/env python3
"""Export a reviewed public aggregate from a sealed CPU-worker pack campaign; no inference.

For the context, capability and physics packs run through a `d3` or `vela2` CPU worker with the
shared engine (`python3 -m deposium_bench run`). The archive's seal, dataset,
scorer, profile, asset and runtime-lock identities are verified against the
tracked public files, then only aggregate counts, group breakdowns, timing
statistics, sampled worker RSS and safe identity hashes are written. Raw
outputs, local paths and process identifiers never leave the private archive.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DATASETS = {"context": ("datasets/context-choice-v1/cases.jsonl", 132, 66,
                        "767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616"),
            "capability": ("datasets/capability-choice-v1/cases.jsonl", 192, 48,
                           "0b409a09bb5358b5c8d7574cbd330799511851a2acd90676e2f092f3d3c75eb0"),
            "physics": ("datasets/physics-choice-v1/cases.jsonl", 48, 24,
                        "e21cd2e0f4e35465b56158ba1fa07c8d8203be81a969c6edf4b7630d2f0d7307")}
AXES = ("benchmark_pack", "task_type", "use_case", "catalogue_variant", "language", "split", "difficulty", "domain")
RUNTIME_NAMES = ("python", "torch", "transformers", "tokenizers", "safetensors", "numpy", "accelerate", "einops")
STATUSES = ("ok", "unsupported", "missing", "error", "timeout", "abstain")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def module(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def verify_seal(root):
    """Every sealed member must match its hash; the inventory must be exactly the sealed set."""
    require(root.is_dir() and not root.is_symlink(), "invalid archive root")
    path = root / "seal.json"
    seal = load(path)
    require(seal.get("schema_version") == "deposium.archive-seal/v1" and isinstance(seal.get("files"), dict)
            and bool(seal["files"]), "seal schema")
    for relative, expected in seal["files"].items():
        member = Path(relative)
        require(not member.is_absolute() and ".." not in member.parts and relative != "seal.json", "unsafe seal member")
        target = root / member
        require(target.is_file() and not target.is_symlink() and re.fullmatch(r"[0-9a-f]{64}", expected)
                and sha(target.read_bytes()) == expected, "sealed file changed")
    entries = [p for p in root.rglob("*") if p.is_file()]
    require(not any(p.is_symlink() for p in root.rglob("*")), "symlink archive entry")
    require({str(p.relative_to(root)) for p in entries} == set(seal["files"]) | {"seal.json"}, "archive inventory changed")
    return sha(path.read_bytes())


def numeric(value):
    return value is None or (type(value) in (int, float) and math.isfinite(value) and value >= 0)


def export(args):
    flash = module("scripts/export-capability-flash.py", "capability_flash_export_helpers")
    sys.path.insert(0, str(ROOT))
    from deposium_bench import campaigns
    from deposium_bench.context_analysis import analyze_context, _stats
    from deposium_bench.worker_transport import wire

    relative, total, families, dataset_sha = DATASETS[args.pack]
    archive = args.archive.resolve(strict=True)
    outer_seal = verify_seal(archive)
    manifest, summary = load(archive / "manifest.json"), load(archive / "summary.json")
    cases = [json.loads(line) for line in (archive / "cases.jsonl").read_text().splitlines()]
    records = [json.loads(line) for line in (archive / "raw.jsonl").read_text().splitlines()]
    require((archive / "cases.jsonl").read_bytes() == (ROOT / relative).read_bytes()
            and manifest["dataset_sha256"] == dataset_sha and len(cases) == total, "frozen dataset differs")
    require(manifest["qualification"] == "model_isolated" and manifest["input_protocol"] == "context_choice"
            and manifest["mode"] == "run" and summary["completion_status"] == "complete", "not a complete isolated run")
    require(manifest["scorer"] == campaigns._scorer_fingerprint(), "scorer differs; explicit derived rescore required")

    profile_path = args.profile.resolve(strict=True)
    require(profile_path.is_relative_to(ROOT / "profiles"), "profile must be a tracked public profile")
    profile = load(profile_path)
    _, normalized_hash, _ = campaigns._prepare_profile(profile_path)
    require(manifest["source_profile_sha256"] == normalized_hash, "archive profile differs from the tracked profile")
    provenance = manifest["adapter_provenance"]
    adapter = provenance["adapter"]
    require(adapter in ("d3", "vela2") and adapter == profile["adapter"] and provenance["available"] is True
            and provenance["device"] == "cpu" and provenance["model_repo_id"] == profile["model"]["repo_id"]
            and provenance["model_revision"] == profile["revision"], "adapter provenance differs from the profile")
    if adapter == "d3":
        require(provenance["backbone_dtype"] == "bfloat16" and provenance["readout_dtype"] == "float32", "unexpected D3 dtypes")
        precision = {"backbone_dtype": "bfloat16", "readout_dtype": "float32"}
    else:
        require(provenance["dtype"] == "float32", "unexpected Vela2 dtype")
        precision = {"dtype": "float32"}
    assets = load(ROOT / "profiles" / profile["model"]["assets_manifest"])
    indexed = {f["path"]: {"sha256": f["sha256"], "size": f["size"]} for f in assets["files"]}
    require(assets["repo_id"] == profile["model"]["repo_id"] and assets["revision"] == profile["revision"]
            and provenance["model_assets_sha256"] == sha(wire(indexed)), "asset manifest differs from the run")
    lock_path = (profile_path.parent / profile["model"]["runtime_lock"]).resolve()
    require(lock_path.is_relative_to(ROOT / "runtimes"), "runtime lock must be tracked")
    lock_bytes = lock_path.read_bytes()
    require(provenance["runtime_lock_sha256"] == sha(lock_bytes), "runtime lock differs from the run")
    pins = provenance["runtime_pins"]
    require(all(provenance["runtime"].get(k) == pins.get(k) for k in pins), "worker runtime differs from the lock")

    analysis = analyze_context(archive, args.private_analysis)
    flash.validate_counts(analysis["counts"], total)
    require(analysis["dataset_sha256"] == dataset_sha, "analysis dataset differs")
    groups = {axis: {key: flash.public_counts(value) for key, value in analysis["groups"][axis].items()}
              for axis in AXES if axis in analysis["groups"]}
    by_id = {c["case_id"]: c for c in cases}
    tracks = defaultdict(list)
    for row in analysis["rows"]:
        track = by_id[row["case_id"]]["evaluation"]["oracle"]["params"].get("track")
        if track:
            tracks[track].append(row)
    if tracks:
        from deposium_bench.context_analysis import _counts
        groups["track"] = {key: flash.public_counts(_counts(rows)) for key, rows in sorted(tracks.items())}

    ok_rows = [r for r in records if r["status"] == "ok"]
    # A CPU worker fails closed: after its first timeout/error every later case
    # returns a cached failure without an attempt. Keep statuses as archived, but
    # say how many unsuccessful cases were actually attempted.
    cached = [r for r in records if (r.get("raw_output") or {}).get("cached_failure") is True]
    unsuccessful = [r for r in records if r["status"] != "ok"]
    generations = [(r.get("raw_output") or {}).get("worker_generation") for r in records]
    restarts = max([g for g in generations if type(g) is int] or [0])
    final_path = archive / "adapter-final.json"
    restart_events = []
    if final_path.is_file():
        final = load(final_path)
        restart_events = final.get("worker_restarts") or []
        require(len(restart_events) == restarts, "restart events in the final provenance differ from the raw records")
    attempts = {"recorded_cases": len(records), "attempted_cases": len(records) - len(cached),
                "worker_restarts": restarts,
                "worker_restart_events": [{k: e.get(k) for k in ("after_sequence", "restart", "reason", "relaunch_ms")}
                                          for e in restart_events],
                "unsuccessful_attempted": len(unsuccessful) - len(cached), "cached_unattempted": len(cached),
                "fail_closed_after_first_failure": bool(cached),
                "first_failure_case_index": next((i for i, r in enumerate(records) if r["status"] != "ok"), None),
                "note": "cached_unattempted cases keep their archived status in every denominator; they are unobserved, not measured"}
    rss = [((r.get("raw_output") or {}).get("rss_mb")) for r in records]
    rss = [v for v in rss if type(v) in (int, float) and math.isfinite(v)]
    peak = max([provenance.get("load_rss_mb") or 0, *rss])
    require(peak > 0 and peak <= profile["model"]["max_rss_mb"], "worker RSS missing or above the profile ceiling")
    first = records[0] if records else None
    later = [r for r in records[1:] if r["status"] == "ok"]
    phase = {
        "role": "full_frozen_pack", "attempt": int(archive.name.rsplit("-", 1)[1]),
        "completion_status": summary["completion_status"],
        "counts": flash.public_counts(analysis["counts"]), "groups": groups,
        "identity": {"dataset_sha256": dataset_sha, "manifest_sha256": sha((archive / "manifest.json").read_bytes()),
                     "raw_sha256": sha((archive / "raw.jsonl").read_bytes()), "outer_seal_sha256": outer_seal,
                     "scorer_sha256": manifest["scorer"]["sha256"],
                     "analysis_sha256": sha(json.dumps(analysis, sort_keys=True, ensure_ascii=False).encode())},
        "included_in_full_pack_quality_denominator": True,
        "attempts": attempts,
        "latency_ms": flash.stats(_stats([r["duration_ms"] for r in ok_rows])),
        "actual_backend": {"kind": "cpu", "device": "cpu", "threads": profile["model"]["threads"], **precision,
                           "loading_mode": provenance["loading_mode"]},
        "resources": {"rss_peak_mib": round(peak, 1), "stop_reason": None,
                      "rss_scope": "maximum of the worker's own ru_maxrss after loading and after each case; single CPU worker process, not a process-group sample",
                      "load_ms": provenance.get("load_ms"), "adapter_initialization_ms": provenance.get("init_wall_ms")},
        "timing": {"scope": "corpus calls through the persistent CPU worker; no synthetic warm-up precedes the first case",
                   "first_corpus_call": {"status": first["status"] if first else None,
                                         "adapter_ms": first["duration_ms"] if first else None},
                   "successful_after_first": {"adapter_ms": flash.stats(_stats([r["duration_ms"] for r in later]))}},
        "paired_catalogue_views": flash.paired_views(cases, analysis["rows"], records) if args.pack == "capability" else [],
        "paired_language_views": flash.paired_views(cases, analysis["rows"], records, axis="language") if args.pack == "capability" else [],
        "families": flash.family_groups(cases, analysis["rows"]),
    }
    git = manifest["bench"]["git"]
    return {
        "schema_version": "deposium.cpu-pack-campaign-public/v1",
        "report_date": manifest["created_at"][:10],
        "reference_review": "agent_only_pending_human",
        "execution_scope": "isolated_cpu_worker_no_application_gateway",
        "model": {"model_repo_id": assets["repo_id"], "model_revision": assets["revision"],
                  "model_assets_sha256": provenance["model_assets_sha256"],
                  "assets_manifest": "profiles/" + profile["model"]["assets_manifest"],
                  "backbone_parameters": provenance.get("backbone_parameters"), "readout_shape": provenance.get("readout_shape")},
        "runtime": {"adapter": adapter, "device": "cpu", "platform": args.platform,
                    "pins": {k: pins.get(k) for k in RUNTIME_NAMES},
                    "runtime_lock": str(lock_path.relative_to(ROOT)), "runtime_lock_sha256": sha(lock_bytes),
                    "profile": str(profile_path.relative_to(ROOT)), "profile_id": profile["profile_id"],
                    "max_length": profile["model"]["max_length"], "threads": profile["model"]["threads"],
                    "max_rss_mb": profile["model"]["max_rss_mb"], "loading_mode": provenance["loading_mode"]},
        "source": {"bench_head": git.get("head"), "local_changes_present": bool(git.get("dirty")),
                   "scorer_sha256": manifest["scorer"]["sha256"], "protocol": args.protocol},
        "phases": {args.pack: phase},
        "aggregate_producer_sha256": sha(Path(__file__).read_bytes()),
        "limits": [
            "Agent-authored references and translations await independent human review.",
            "Closed choice among supplied proposals; no tools, executable arguments, agent loop or product journey.",
            "A new macOS CPU runtime identity: not comparable to the historical Linux/WSL CPU row as if the runtime were the same.",
            "Worker RSS is the process's own ru_maxrss, not a process-group or unified-memory sample.",
            "Single pass per case; latency is descriptive, not a production guarantee.",
            "Language and catalogue variants are correlated within families; no post-hoc confidence interval is fitted."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--pack", choices=sorted(DATASETS), required=True)
    parser.add_argument("--protocol", required=True, help="tracked protocol document path, e.g. docs/D3_LITE_MACOS_CPU_PROTOCOL_20261030.md")
    parser.add_argument("--platform", default="macOS arm64")
    parser.add_argument("--private-analysis", type=Path, required=True, help="new ignored directory for the full per-case analysis")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        require((ROOT / args.protocol).is_file(), "protocol document must exist")
        require(not args.output.exists() and not args.private_analysis.exists(), "refusing to overwrite outputs")
        document = export(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")
        counts = document["phases"][args.pack]["counts"]
        print(json.dumps({"status": "aggregate_written", "pack": args.pack, "passed": counts["passed_cases"],
                          "scored": counts["scored_cases"], "total": counts["total_cases"]}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, StopIteration):
        print("Aggregate export refused; preserve the original archive and inspect integrity.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
