#!/usr/bin/env python3
"""Export a reviewed public aggregate from a sealed CPU passage-choice archive; no inference.

For the macOS CPU D3 and Vela 2.0 rows observed with
`python3 -m deposium_bench.passage_observation choice`. The seal, the frozen
passage pack, the tracked profile bytes and the model revision are verified;
only per-axis scores and groups, statuses, latency, worker RSS and safe
identity hashes are written. Per-case rows, inputs, raw responses, local paths
and process data stay in the private archive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.campaigns import _encode  # noqa: E402

DATASET_SHA256 = "35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476"
AXES = ("relevance", "support", "answerability")
EXPECTED = {"relevance": 512, "support": 768, "answerability": 128}
SCHEMA = "deposium.passage-cpu-public/v1"


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        require(not args.output.exists(), "refusing to overwrite the output")
        require((ROOT / args.protocol).is_file(), "protocol document must exist")
        archive = args.archive.resolve()
        verify_seal(archive)
        manifest, summary = load(archive / "manifest.json"), load(archive / "summary.json")
        profile_path = (ROOT / args.profile).resolve()
        require(profile_path.is_relative_to(ROOT / "profiles"), "profile must be tracked under profiles/")
        profile = load(profile_path)
        require(manifest["dataset_sha256"] == DATASET_SHA256, "passage pack differs from the frozen one")
        require(manifest["source_profile_sha256"] == sha(profile_path.read_bytes()), "archive was not produced by this tracked profile")
        require(manifest["split"] == "test", "not the test split")
        final = summary["adapter_final"]
        require(final.get("model_revision") == profile["revision"] and final.get("model_repo_id") == profile["model"]["repo_id"],
                "model identity mismatch")
        require(summary["logical_decisions"] == 1408 and summary["physical_planned"] == 728, "unexpected plan size")
        scores = load(archive / "scores.json")
        public_scores = {}
        for axis in AXES:
            score = {k: v for k, v in scores[axis].items() if k != "rows"}
            require(score["total_cases"] == EXPECTED[axis], f"{axis}: denominator changed")
            public_scores[axis] = score
        latency, inference, rss = [], [], []
        for line in (archive / "raw.jsonl").read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            latency.append(record["adapter_wall_ms"])
            raw = (record["response"] or {}).get("raw_output") or {}
            if isinstance(raw.get("inference_ms"), (int, float)):
                inference.append(raw["inference_ms"])
            if isinstance(raw.get("rss_mb"), (int, float)):
                rss.append(raw["rss_mb"])
        document = {
            "schema_version": SCHEMA, "label": args.label, "protocol": args.protocol,
            "dataset_sha256": DATASET_SHA256, "split": "test", "rotation": 0, "cases": 128, "families": 8,
            "logical_choices": 1408, "physical_calls": 728, "qualification": "synthetic_isolated_pending_human_review",
            "completion_status": summary["completion_status"], "stop_reason": summary["stop_reason"],
            "physical_statuses": summary["physical_statuses"], "logical_statuses": summary["logical_statuses"],
            "choice_model": {"adapter": final["adapter"], "model_repo_id": final["model_repo_id"],
                             "model_revision": final["model_revision"], "identity_sha256": final.get("identity_sha256"),
                             "runtime_lock_sha256": final.get("runtime_lock_sha256"), "profile": args.profile,
                             "worker_restarts": len(final.get("worker_restarts") or [])},
            "choice_scores": public_scores,
            "physical_call_ms": stats(latency), "inference_ms": stats(inference),
            "worker_rss_mib_max": max(rss) if rss else None, "model_phase_wall_ms": summary["model_phase_wall_ms"],
            "source": {"seal_sha256": sha((archive / "seal.json").read_bytes()), "manifest_sha256": sha((archive / "manifest.json").read_bytes()),
                       "scores_sha256": sha((archive / "scores.json").read_bytes())},
        }
        text = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
        for forbidden in ("/Users/", "/private/", "/tmp/", "/home/"):
            require(forbidden not in text, "local path in public aggregate")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(json.dumps({"status": "aggregate_written", "label": args.label,
                          **{axis: f"{round(public_scores[axis]['accuracy_over_all'] * EXPECTED[axis])}/{EXPECTED[axis]}" for axis in AXES}}))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Export refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
