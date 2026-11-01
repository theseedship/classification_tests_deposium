#!/usr/bin/env python3
"""Export public aggregates for facade-routing-v1 from sealed archives; no inference.

Classifier rows: `--run LABEL=ARCHIVE=PROFILE` with a tracked profile under
`profiles/`. The router row: `--router ARCHIVE --router-revision SHA`, a sealed
`recorded` harness-control archive replaying the production router privately.
Only counts, paired outcomes and hashes are written: no request text, router
code, rule, keyword, configuration, raw output, path or stack inventory.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.campaigns import _encode  # noqa: E402

PACKS = ("facade-routing-v1", "facade-routing-advanced-v1", "facade-routing-complex-v1")
SCHEMA = "deposium.facade-routing-public/v1"
CATEGORIES = ("search", "analyze", "visualize", "graph", "evaluate", "process", "system", "none")
ROUTER_LABEL = "FacadeRouterReplay"


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_seal(root: Path) -> None:
    seal = load(root / "seal.json")
    require(seal.get("schema_version") == "deposium.archive-seal/v1" and isinstance(seal.get("files"), dict), "invalid seal")
    require(seal.get("sha256") == sha(_encode(seal["files"])), "seal digest mismatch")
    entries = {p.name for p in root.iterdir() if p.is_file()}
    require(entries == set(seal["files"]) | {"seal.json"}, "archive inventory changed")
    for name, digest in seal["files"].items():
        require(sha((root / name).read_bytes()) == digest, f"sealed file changed: {name}")


def kind(case):
    return case["evaluation"]["task_type"].rsplit(".", 1)[-1]


def expected(case):
    return case["evaluation"]["oracle"]["choices"][case["reference"]["assertions"][0]["value"]]


def decisions(archive: Path, cases: dict, dataset_sha: str):
    verify_seal(archive)
    manifest, summary = load(archive / "manifest.json"), load(archive / "summary.json")
    require(manifest["dataset_sha256"] == dataset_sha, "dataset hash differs from the frozen pack")
    require(summary["completion_status"] == "complete", "incomplete archive")
    rows = [json.loads(line) for line in (archive / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
    require(sorted(r["case_id"] for r in rows) == sorted(cases) and len(rows) == len(cases), "case set differs")
    out = {}
    for r in rows:
        case = cases[r["case_id"]]
        choice = (r.get("output") or {}).get("choice_id") if r["status"] == "ok" else None
        predicted = case["evaluation"]["oracle"]["choices"].get(choice) if choice else None
        out[r["case_id"]] = {"status": r["status"], "predicted": predicted, "correct": predicted == expected(case)}
    return manifest, summary, rows, out


def tally(result, cases, pick=lambda c: True):
    chosen = [cid for cid in cases if pick(cases[cid])]
    return {"correct": sum(result[c]["correct"] for c in chosen), "total": len(chosen),
            "statuses": dict(sorted(Counter(result[c]["status"] for c in chosen).items()))}


def summarize(result, cases):
    confusion = {e: dict(sorted(Counter(result[c]["predicted"] or result[c]["status"]
                                        for c in cases if expected(cases[c]) == e).items())) for e in CATEGORIES}
    by_kind = sorted({kind(c) for c in cases.values()})
    return {"all": tally(result, cases),
            "by_split": {s: tally(result, cases, lambda c, s=s: c["split"] == s) for s in ("train", "calibration", "test")},
            "by_language": {l: tally(result, cases, lambda c, l=l: c["language"] == l) for l in ("fr", "en")},
            "by_category": {e: tally(result, cases, lambda c, e=e: expected(c) == e) for e in CATEGORIES},
            "by_kind": {k: tally(result, cases, lambda c, k=k: kind(c) == k) for k in by_kind},
            "test_by_category": {e: tally(result, cases, lambda c, e=e: expected(c) == e and c["split"] == "test") for e in CATEGORIES},
            "predicted_distribution": dict(sorted(Counter(r["predicted"] or r["status"] for r in result.values()).items())),
            "confusion": confusion}


def stats(values):
    if not values:
        return None
    ordered = sorted(values)
    return {"count": len(ordered), "median": statistics.median(ordered),
            "p95": ordered[max(0, int(round(0.95 * len(ordered))) - 1)], "max": ordered[-1]}


def paired(result, router, cases):
    def cell(pick):
        return {"both": sum(result[c]["correct"] and router[c]["correct"] for c in pick),
                "model_only": sum(result[c]["correct"] and not router[c]["correct"] for c in pick),
                "router_only": sum(router[c]["correct"] and not result[c]["correct"] for c in pick),
                "neither": sum(not result[c]["correct"] and not router[c]["correct"] for c in pick)}
    return {"all": cell(list(cases)), "test": cell([c for c in cases if cases[c]["split"] == "test"]),
            "by_category": {e: cell([c for c in cases if expected(cases[c]) == e]) for e in CATEGORIES}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", choices=PACKS, default="facade-routing-v1")
    parser.add_argument("--run", action="append", default=[], help="LABEL=ARCHIVE=PROFILE (CPU worker archive)")
    parser.add_argument("--gpu-run", action="append", default=[],
                        help="LABEL=PILOT_ARCHIVE=ASSETS (run-upstream-native-pilot.py archive and tracked asset manifest)")
    parser.add_argument("--uzu-run", action="append", default=[],
                        help="LABEL=PILOT_ARCHIVE=ASSETS (run-uzu-pilot.py archive and tracked asset manifest)")
    parser.add_argument("--backend", choices=("metal", "cuda", "rocm", "vulkan"), default="metal")
    parser.add_argument("--router", required=True, type=Path)
    parser.add_argument("--router-revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        require(not args.output.exists(), "refusing to overwrite the output")
        require(re.fullmatch(r"[0-9a-f]{40}", args.router_revision), "router revision must be a full commit hash")
        require(args.run or args.gpu_run or args.uzu_run, "at least one candidate run is required")
        data = (ROOT / "datasets" / args.pack / "cases.jsonl").read_bytes()
        dataset_sha = sha(data)
        require(load(ROOT / "datasets" / args.pack / "manifest.json")["cases_sha256"] == dataset_sha, "frozen pack manifest mismatch")
        cases = {c["case_id"]: c for c in map(json.loads, data.decode("utf-8").splitlines())}
        _, rsummary, _, router = decisions(args.router, cases, dataset_sha)
        rfinal = load(args.router / "adapter-final.json")
        require(rfinal["adapter"] == "recorded" and rfinal["qualification"] == "harness_control"
                and rfinal["recordings_count"] == len(cases), "router archive is not a complete recorded replay")
        router_row = {"label": ROUTER_LABEL, "kind": "private_router_replay",
                      "identity": {"router_source_revision": args.router_revision,
                                   "recordings_sha256": rfinal["recordings_sha256"],
                                   "identity_sha256": rfinal["identity_sha256"],
                                   "raw_sha256": rsummary["raw_sha256"],
                                   "seal_sha256": sha((args.router / "seal.json").read_bytes())},
                      "counts": summarize(router, cases)}
        runs = []
        for spec in args.run:
            label, archive, profile = spec.split("=")
            archive, profile = Path(archive), (ROOT / profile).resolve()
            require(profile.is_relative_to(ROOT / "profiles"), "profile must be tracked under profiles/")
            manifest, summary, rows, result = decisions(archive, cases, dataset_sha)
            require(manifest["source_profile_sha256"] == sha(profile.read_bytes()), "archive was not produced by this tracked profile")
            final, tracked = load(archive / "adapter-final.json"), load(profile)
            require(final["model_revision"] == tracked["revision"], "model revision mismatch")
            latency = [r["raw_output"]["inference_ms"] for r in rows
                       if isinstance((r.get("raw_output") or {}).get("inference_ms"), (int, float))]
            rss = [r["raw_output"]["rss_mb"] for r in rows if isinstance((r.get("raw_output") or {}).get("rss_mb"), (int, float))]
            runs.append({"label": label, "kind": "classifier",
                         "identity": {"adapter": final["adapter"], "model_repo_id": final["model_repo_id"],
                                      "model_revision": final["model_revision"], "identity_sha256": final["identity_sha256"],
                                      "runtime_lock_sha256": final.get("runtime_lock_sha256"),
                                      "profile": str(profile.relative_to(ROOT)), "raw_sha256": summary["raw_sha256"],
                                      "seal_sha256": sha((archive / "seal.json").read_bytes()),
                                      "worker_restarts": len(final.get("worker_restarts") or [])},
                         "counts": summarize(result, cases), "paired_with_router": paired(result, router, cases),
                         "inference_ms": stats(latency), "worker_rss_mib_max": max(rss) if rss else None})
        if args.gpu_run:
            spec_ = importlib.util.spec_from_file_location("gguf_gpu_export", ROOT / "scripts/export-gguf-gpu-campaign.py")
            gpu = importlib.util.module_from_spec(spec_)
            spec_.loader.exec_module(gpu)
        for spec in args.gpu_run:
            label, pilot, assets_path = spec.split("=")
            pilot, assets_path = Path(pilot), (ROOT / assets_path).resolve()
            require(assets_path.is_relative_to(ROOT / "profiles"), "asset manifest must be tracked under profiles/")
            assets = load(assets_path)
            pilot_result = gpu.verify_pilot(pilot, assets, args.backend)
            require(pilot_result["dataset"]["sha256"] == dataset_sha, "pilot dataset differs from the frozen pack")
            manifest, summary, rows, result = decisions(pilot / "campaign", cases, dataset_sha)
            latency = [r["duration_ms"] for r in rows if r["status"] == "ok"]
            runs.append({"label": label, "kind": "classifier",
                         "identity": {"adapter": "systemone_local", "backend": args.backend,
                                      "model_repo_id": assets["repo_id"], "model_revision": assets["revision"],
                                      "model_sha256": assets["files"][0]["sha256"],
                                      "assets_manifest": str(assets_path.relative_to(ROOT)),
                                      "native_revision": pilot_result["runtime"]["revision"],
                                      "binary_sha256": pilot_result["runtime"]["binary_sha256"],
                                      "layers": pilot_result["actual_backend"]["total_layers"],
                                      "raw_sha256": summary["raw_sha256"],
                                      "seal_sha256": sha((pilot / "pilot-seal.json").read_bytes())},
                         "counts": summarize(result, cases), "paired_with_router": paired(result, router, cases),
                         "inference_ms": stats(latency), "worker_rss_mib_max": pilot_result["resources"]["rss_peak_mib"],
                         "latency_scope": "adapter call duration, including loopback HTTP"})
        if args.uzu_run:
            spec_ = importlib.util.spec_from_file_location("deployment_export", ROOT / "scripts/export-deployment-variants.py")
            uzu = importlib.util.module_from_spec(spec_)
            spec_.loader.exec_module(uzu)
        for spec in args.uzu_run:
            label, pilot, assets_path = spec.split("=")
            pilot, assets_path = Path(pilot), (ROOT / assets_path).resolve()
            require(assets_path.is_relative_to(ROOT / "profiles"), "asset manifest must be tracked under profiles/")
            identity = uzu.verify_uzu(pilot, assets_path)
            require(identity["dataset_sha256"] == dataset_sha, "pilot dataset differs from the frozen pack")
            manifest, summary, rows, result = decisions(pilot / "campaign", cases, dataset_sha)
            latency = [r["duration_ms"] for r in rows if r["status"] == "ok"]
            runs.append({"label": label, "kind": "classifier",
                         "identity": {"adapter": "uzu_local", "backend": "uzu", "backend_requested": "metal",
                                      "model_repo_id": load(assets_path)["repo_id"], "model_revision": load(assets_path)["revision"],
                                      "model_sha256": sha(assets_path.read_bytes()),
                                      "assets_manifest": str(assets_path.relative_to(ROOT)),
                                      "uzu_revision": identity["runtime"]["uzu_revision"],
                                      "binary_sha256": identity["runtime"]["binary_sha256"],
                                      "raw_sha256": summary["raw_sha256"],
                                      "seal_sha256": sha((pilot / "pilot-seal.json").read_bytes())},
                         "counts": summarize(result, cases), "paired_with_router": paired(result, router, cases),
                         "inference_ms": stats(latency), "worker_rss_mib_max": identity["rss_peak_mib"],
                         "latency_scope": "adapter call duration, including loopback HTTP"})
        out = {"schema_version": SCHEMA, "pack": args.pack, "dataset_sha256": dataset_sha, "cases": len(cases),
               "qualification": "exploratory; agent-authored references pending human review",
               "router": router_row, "runs": runs}
        text = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        for forbidden in ("/Users/", "/private/", "/tmp/", "/home/"):
            require(forbidden not in text, "local path in public aggregate")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(json.dumps({"status": "aggregate_written", "router": router_row["counts"]["all"],
                          **{r["label"]: r["counts"]["all"] for r in runs}}))
    except (ValueError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
