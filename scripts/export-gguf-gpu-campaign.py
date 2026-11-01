#!/usr/bin/env python3
"""Export reviewed public aggregates for one small D3 GGUF model on a GPU backend; no inference.

Each `--phase PACK=PILOT_ARCHIVE[=CPU_ARCHIVE]` names a sealed archive written
by `scripts/run-upstream-native-pilot.py` on a frozen pack, optionally paired
with the same model's sealed macOS CPU archive on that pack. The pilot seal,
the inner campaign seal, the tracked pack bytes, the tracked asset manifest,
the native revision and the full offload to the declared backend are
verified. Only counts, paired agreement with the CPU row, latency, sampled
RSS and identity hashes are written; inputs, raw responses, token IDs, paths
and process data stay in the local archives.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
import importlib.util
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.campaigns import _encode  # noqa: E402

SCHEMA = "deposium.gguf-gpu-campaign-public/v1"
PIN = "efe3626b119ff81033e309c3ba07a770bef2c546"
CHOICE_PACKS = {"context": ("context-choice-v1", 132, 66), "capability": ("capability-choice-v1", 192, 48),
                "physics": ("physics-choice-v1", 48, 24)}
AXES_GROUPS = ("benchmark_pack", "task_type", "use_case", "catalogue_variant", "language", "split", "difficulty", "domain")
PASSAGE_PACK = "passage-evidence-v1"
AXES = ("relevance", "support", "answerability")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def stats(values):
    if not values:
        return {"count": 0, "median": None, "p95": None, "max": None}
    ordered = sorted(values)
    return {"count": len(ordered), "median": statistics.median(ordered),
            "p95": ordered[max(0, int(round(0.95 * len(ordered))) - 1)], "max": ordered[-1]}


def verify_seal(root: Path):
    seal = load(root / "seal.json")
    require(seal.get("schema_version") == "deposium.archive-seal/v1" and isinstance(seal.get("files"), dict), "invalid seal")
    require(seal.get("sha256") == sha(_encode(seal["files"])), "seal digest mismatch")
    require({p.name for p in root.iterdir() if p.is_file()} == set(seal["files"]) | {"seal.json"}, "archive inventory changed")
    for name, digest in seal["files"].items():
        require(sha((root / name).read_bytes()) == digest, f"sealed file changed: {name}")


def verify_pilot(pilot: Path, assets: dict, backend: str) -> dict:
    seal = load(pilot / "pilot-seal.json")
    require(seal.get("schema_version") == "deposium.native-pilot-seal/v1", "invalid pilot seal")
    files = {str(p.relative_to(pilot)) for p in pilot.rglob("*") if p.is_file()} - {"pilot-seal.json"}
    require(files == set(seal["files"]), "pilot inventory changed")
    for name, digest in seal["files"].items():
        require(sha((pilot / name).read_bytes()) == digest, f"pilot file changed: {name}")
    verify_seal(pilot / "campaign")
    result = load(pilot / "pilot.json")
    actual = result["actual_backend"]
    require(result["completed"] is True and result["runtime"]["revision"] == PIN, "incomplete pilot or wrong native revision")
    require(actual["kind"] == backend and actual["offloaded_layers"] == actual["total_layers"] > 0,
            "model not fully offloaded to the declared backend")
    require(result["model_assets"] == assets, "archive model differs from the tracked asset manifest")
    return result


def tracked_pack(name: str):
    payload = (ROOT / "datasets" / name / "cases.jsonl").read_bytes()
    return sha(payload), {c["case_id"]: c for c in map(json.loads, payload.decode("utf-8").splitlines())}


def helpers():
    spec = importlib.util.spec_from_file_location("flash_export_helpers", ROOT / "scripts/export-capability-flash.py")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def export_choice(pack: str, pilot: Path, cpu: Path | None, result: dict, private: Path):
    """Same phase format as the Flash Metal and macOS CPU pack exports, through a derived rescore."""
    from deposium_bench.campaigns import rescore_campaign
    from deposium_bench.context_analysis import analyze_context, _stats
    flash = helpers()
    name, total, families = CHOICE_PACKS[pack]
    expected, cases = tracked_pack(name)
    require(result["dataset"]["sha256"] == expected and result["dataset"]["validated_cases"] == total == len(cases),
            "pilot dataset differs from the tracked pack")
    campaign = pilot / "campaign"
    summary, raw = load(campaign / "summary.json"), rows(campaign / "raw.jsonl")
    require(summary["completion_status"] == "complete" and len(raw) == total, "incomplete campaign")
    # The archive keeps its original scorer; a derived rescore (no inference) aligns it with the current scorer.
    derived = private / f"{pack}-rescore"
    rescore_campaign(campaign, derived)
    rescored = load(derived / "summary.json")["metrics"]
    require(rescored["passed_cases"] == summary["metrics"]["passed_cases"]
            and rescored["scored_cases"] == summary["metrics"]["scored_cases"], "rescore changed the score")
    analysis = analyze_context(derived, private / f"{pack}-analysis")
    flash.validate_counts(analysis["counts"], total)
    require(analysis["dataset_sha256"] == expected, "analysis dataset differs")
    groups = {axis: {key: flash.public_counts(value) for key, value in analysis["groups"][axis].items()}
              for axis in AXES_GROUPS if axis in analysis["groups"]}
    by_id = cases
    tracks = {}
    for row in analysis["rows"]:
        track = by_id[row["case_id"]]["evaluation"]["oracle"]["params"].get("track")
        if track:
            tracks.setdefault(track, []).append(row)
    if tracks:
        from deposium_bench.context_analysis import _counts
        groups["track"] = {key: flash.public_counts(_counts(items)) for key, items in sorted(tracks.items())}
    ok_rows = [r for r in raw if r["status"] == "ok"]
    out = {"role": "full_frozen_pack", "pack": name, "completion_status": "complete",
           "counts": flash.public_counts(analysis["counts"]), "groups": groups,
           "identity": {"dataset_sha256": expected, "manifest_sha256": sha((campaign / "manifest.json").read_bytes()),
                        "raw_sha256": sha((campaign / "raw.jsonl").read_bytes()),
                        "outer_seal_sha256": sha((campaign / "seal.json").read_bytes()),
                        "rescore_seal_sha256": sha((derived / "seal.json").read_bytes()),
                        "scorer_sha256": load(derived / "manifest.json")["scorer"]["sha256"],
                        "analysis_sha256": sha(json.dumps(analysis, sort_keys=True, ensure_ascii=False).encode())},
           "included_in_full_pack_quality_denominator": True,
           "latency_ms": flash.stats(_stats([r["duration_ms"] for r in ok_rows])),
           "actual_backend": dict(result["actual_backend"]),
           "resources": {"rss_peak_mib": result["resources"]["rss_peak_mib"], "stop_reason": None,
                         "rss_scope": "Sampled owned process-group peak over fresh session startup, controls, warm-up and this pack; unified memory, not GPU allocation"}}
    passed = {r["case_id"]: r["passed"] for r in analysis["rows"]}
    if cpu is not None:
        verify_seal(cpu)
        require(load(cpu / "manifest.json")["dataset_sha256"] == expected, "CPU archive is not on the same pack")
        cpu_summary, cpu_raw = load(cpu / "summary.json"), rows(cpu / "raw.jsonl")
        cpu_passed = {r["case_id"]: r["passed"] for r in cpu_summary["metrics"]["rows"]}
        gpu_out = {r["case_id"]: r["output"] for r in raw}
        cpu_out = {r["case_id"]: r["output"] for r in cpu_raw}
        require(set(cpu_passed) == set(passed) == set(gpu_out) == set(cpu_out), "CPU archive covers other cases")
        out["paired_with_cpu"] = {
            "identical_answers": sum(gpu_out[c] == cpu_out[c] for c in gpu_out), "cases": len(gpu_out),
            "both": sum(passed[c] and cpu_passed[c] for c in passed),
            "gpu_only": sum(passed[c] and not cpu_passed[c] for c in passed),
            "cpu_only": sum(cpu_passed[c] and not passed[c] for c in passed),
            "neither": sum(not passed[c] and not cpu_passed[c] for c in passed),
            "cpu_correct": cpu_summary["metrics"]["passed_cases"],
            "cpu_latency_ms": stats([r["duration_ms"] for r in cpu_raw if r["status"] == "ok"])}
    return out


def export_passages(pilot: Path, cpu: Path | None, result: dict):
    expected, _ = tracked_pack(PASSAGE_PACK)
    require(result["dataset"]["sha256"] == expected and result["dataset"]["split"] == "test"
            and result["dataset"]["physical_calls"] == 728 and not result["dataset"]["technical_only"],
            "pilot passage selection differs from rotation-0 test")
    campaign = pilot / "campaign"
    summary, scores = load(campaign / "summary.json"), load(campaign / "scores.json")
    require(summary["completion_status"] == "complete" and summary["physical_attempted"] == 728, "incomplete passage campaign")
    raw = rows(campaign / "raw.jsonl")
    out = {"pack": PASSAGE_PACK, "dataset_sha256": expected, "rotation": 0, "split": "test",
           "choice_scores": {axis: {k: v for k, v in scores[axis].items() if k != "rows"} for axis in AXES},
           "physical_statuses": summary["physical_statuses"], "logical_statuses": summary["logical_statuses"],
           "latency_ms": stats([r["adapter_wall_ms"] for r in raw])}
    if cpu is not None:
        verify_seal(cpu)
        require(load(cpu / "manifest.json")["dataset_sha256"] == expected, "CPU archive is not on the same pack")
        key = lambda r: (r["axis"], r["case_id"], r.get("passage_id"), r.get("call_id"))
        gpu = {key(r): r.get("choice_id") for r in rows(campaign / "logical-predictions.jsonl")}
        cpu_rows = {key(r): r.get("choice_id") for r in rows(cpu / "logical-predictions.jsonl")}
        require(set(gpu) == set(cpu_rows), "CPU passage archive covers other decisions")
        cpu_scores = load(cpu / "scores.json")
        out["paired_with_cpu"] = {"identical_decisions": sum(gpu[k] == cpu_rows[k] for k in gpu), "decisions": len(gpu),
                                  "cpu_correct": {a: round(cpu_scores[a]["accuracy_over_all"] * cpu_scores[a]["total_cases"]) for a in AXES},
                                  "cpu_latency_ms": stats([r["adapter_wall_ms"] for r in rows(cpu / "raw.jsonl")])}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--assets", required=True, help="tracked profiles/*-assets.json of the GGUF file")
    parser.add_argument("--backend", required=True, choices=("metal", "cuda", "rocm", "vulkan"))
    parser.add_argument("--hardware", required=True, help="public hardware class, e.g. 'Apple M5 Pro GPU; 64 GiB unified memory'")
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--phase", action="append", required=True, help="PACK=PILOT_ARCHIVE[=CPU_ARCHIVE]")
    parser.add_argument("--private-analysis", required=True, type=Path, help="new ignored directory for derived rescores and analyses")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        require(not args.output.exists(), "refusing to overwrite the output")
        private = args.private_analysis.absolute()
        require(private.resolve().is_relative_to((ROOT / "results").resolve()) and not private.exists(),
                "private analysis must be a new directory under results/")
        private.mkdir(parents=True)
        assets_path = (ROOT / args.assets).resolve()
        require(assets_path.is_relative_to(ROOT / "profiles"), "asset manifest must be tracked under profiles/")
        assets = load(assets_path)
        require((ROOT / args.protocol).is_file(), "protocol must be a tracked document")
        phases, identity = {}, None
        for spec in args.phase:
            parts = spec.split("=")
            require(len(parts) in (2, 3), "phase must be PACK=PILOT[=CPU]")
            pack, pilot = parts[0], Path(parts[1])
            cpu = Path(parts[2]) if len(parts) == 3 else None
            require(pack in CHOICE_PACKS or pack == "passages", f"unknown pack {pack}")
            require(pack not in phases, f"duplicate pack {pack}")
            result = verify_pilot(pilot, assets, args.backend)
            runtime = {"native_revision": PIN, "binary_sha256": result["runtime"]["binary_sha256"],
                       "backend": args.backend, "decision_type": result["actual_backend"]["decision_type"],
                       "layers": result["actual_backend"]["total_layers"]}
            require(identity is None or identity == runtime, "phases ran on different runtimes")
            identity = runtime
            body = (export_passages(pilot, cpu, result) if pack == "passages"
                    else export_choice(pack, pilot, cpu, result, args.private_analysis.absolute()))
            body.update(attempt=pilot.name.rsplit("-", 1)[-1],
                        envelope=(result.get("execution_envelope") or {"name": "flash-clef-18g-v1"})["name"],
                        rss_peak_mib=result["resources"]["rss_peak_mib"],
                        pilot_seal_sha256=sha((pilot / "pilot-seal.json").read_bytes()),
                        campaign_seal_sha256=sha((pilot / "campaign" / "seal.json").read_bytes()))
            phases[pack] = body
        out = {"schema_version": SCHEMA, "label": args.label, "hardware": args.hardware, "protocol": args.protocol,
               "model": {"repo_id": assets["repo_id"], "revision": assets["revision"], "file": assets["files"][0]["path"],
                         "sha256": assets["files"][0]["sha256"], "assets_manifest": str(assets_path.relative_to(ROOT))},
               "runtime": identity, "phases": phases,
               "qualification": "exploratory; agent-authored references pending human review"}
        text = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        for forbidden in ("/Users/", "/private/", "/tmp/", "/home/"):
            require(forbidden not in text, "local path in public aggregate")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(json.dumps({"status": "aggregate_written", "label": args.label,
                          **{p: (v["counts"]["passed_cases"] if "counts" in v else "passages") for p, v in phases.items()}}))
    except (ValueError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
