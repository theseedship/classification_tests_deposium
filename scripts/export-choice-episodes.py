#!/usr/bin/env python3
"""Export reviewed public aggregates from sealed closed-choice episode archives; no inference.

Each `--run LABEL=ARCHIVE=PROFILE` names a sealed archive produced by
`python3 -m deposium_bench run` with a tracked `choice_episode` profile on the
frozen tool-episodes-choice-v1 pack. The seal, the dataset bytes, the tracked
outer profile hash and the inner model revision are verified; then only
aggregate counts, stage metrics, outcome matrices, chosen-position
distributions, inner-call latency and worker statistics are written. Menus,
rendered inputs, raw responses, local paths and process data stay private.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.campaigns import _encode  # noqa: E402
from deposium_bench.tool_episodes import expected_outcome  # noqa: E402

DATASET = "datasets/tool-episodes-choice-v1/cases.jsonl"
MANIFEST = "datasets/tool-episodes-choice-v1/manifest.json"
SCHEMA = "deposium.choice-episodes-public/v1"
STAGES = ("tool", "arguments", "binding", "execution", "result", "stopping", "budget")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_seal(root: Path) -> dict:
    seal = load(root / "seal.json")
    require(seal.get("schema_version") == "deposium.archive-seal/v1" and isinstance(seal.get("files"), dict), "invalid seal")
    require(seal.get("sha256") == sha(_encode(seal["files"])), "seal digest mismatch")
    entries = {p.name for p in root.iterdir() if p.is_file()}
    require(entries == set(seal["files"]) | {"seal.json"}, "archive inventory changed")
    for name, digest in seal["files"].items():
        require(sha((root / name).read_bytes()) == digest, f"sealed file changed: {name}")
    return seal


def stats(values):
    if not values:
        return {"count": 0, "median": None, "p95": None, "max": None}
    ordered = sorted(values)
    return {"count": len(ordered), "median": statistics.median(ordered),
            "p95": ordered[max(0, int(round(0.95 * len(ordered))) - 1)], "max": ordered[-1]}


def counts(rows, cases, pick=lambda c: True):
    selected = [r for r in rows if pick(cases[r["case_id"]])]
    ok = [r for r in selected if r["status"] == "ok"]
    def flag(r, *keys):
        return all(r["output"]["checks"][k] for k in keys)
    eligible = [r for r in selected if expected_outcome(cases[r["case_id"]]["input"])["decision"] == "success"]
    return {"total_cases": len(selected),
            "procedure_correct_cases": sum(flag(r, "procedure_valid", "stopping_valid", "budgets_respected") for r in ok),
            "task_success_cases": sum(flag(r, "task_success") for r in ok if r in eligible),
            "task_success_eligible_cases": len(eligible),
            "statuses": dict(sorted(Counter(r["status"] for r in selected).items()))}


def export_run(label, archive: Path, profile: Path, cases: dict, dataset_sha: str) -> dict:
    verify_seal(archive)
    manifest, summary, final = load(archive / "manifest.json"), load(archive / "summary.json"), load(archive / "adapter-final.json")
    require(manifest["dataset_sha256"] == dataset_sha, "dataset hash differs from the frozen pack")
    require(manifest["input_protocol"] == "closed_choice_episode_v1", "not a closed-choice episode archive")
    require(profile.resolve().is_relative_to(ROOT / "profiles"), "profile must be tracked under profiles/")
    require(manifest["source_profile_sha256"] == sha(profile.read_bytes()), "archive was not produced by this tracked profile")
    tracked = load(profile)
    inner = final["inner"]
    require(final["policy_mode"] == "closed_choice_step_menu_v1" and inner["model_revision"] == tracked["revision"], "inner identity mismatch")
    require(summary["completion_status"] == "complete", "incomplete archive")
    rows = [json.loads(line) for line in (archive / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
    require([r["case_id"] for r in rows] == manifest["case_ids"] and len(rows) == len(cases), "case order or count differs")
    metrics = summary["metrics"]["task_metrics"]["bench.tool-episode"]
    positions, first_steps, inner_status, latency, rss = Counter(), Counter(), Counter(), [], []
    matrix, families = Counter(), {}
    for r in rows:
        case = cases[r["case_id"]]
        expected = expected_outcome(case["input"])
        for index, step in enumerate(r["raw_output"]["steps"]):
            ids = [item["id"] for item in step["menu"]]
            response = step["response"]
            inner_status[response["status"]] += 1
            chosen = (response.get("output") or {}).get("choice_id")
            if chosen in ids:
                positions[str(ids.index(chosen) + 1)] += 1
                if index == 0:
                    first_steps[chosen] += 1
            raw = response.get("raw_output") or {}
            if isinstance(raw.get("inference_ms"), (int, float)):
                latency.append(raw["inference_ms"])
            if isinstance(raw.get("rss_mb"), (int, float)):
                rss.append(raw["rss_mb"])
        outcome = r["output"]["outcome"] if r["status"] == "ok" else None
        final_reason = outcome["reason"] if outcome else "candidate_" + r["status"]
        matrix[(expected["reason"], final_reason)] += 1
        family = families.setdefault(case["translation_family"], {"expected": expected["reason"], "split": case["split"], "passed": 0, "total": 0})
        family["total"] += 1
        family["passed"] += bool(outcome and all(r["output"]["checks"][k] for k in ("procedure_valid", "stopping_valid", "budgets_respected")))
    return {
        "label": label, "display_name": tracked["profile_id"],
        "identity": {"outer_identity_sha256": final["identity_sha256"], "inner_identity_sha256": inner["identity_sha256"],
                     "model_repo_id": inner["model_repo_id"], "model_revision": inner["model_revision"],
                     "runtime_lock_sha256": inner.get("runtime_lock_sha256"), "profile": str(profile.relative_to(ROOT)),
                     "inner_profile": "profiles/" + tracked["model"]["inner_profile"], "seal_sha256": sha((archive / "seal.json").read_bytes()),
                     "raw_sha256": summary["raw_sha256"], "dataset_sha256": dataset_sha},
        "counts": {"all": counts(rows, cases), "train": counts(rows, cases, lambda c: c["split"] == "train"),
                   "test": counts(rows, cases, lambda c: c["split"] == "test"),
                   "fr": counts(rows, cases, lambda c: c["language"] == "fr"), "en": counts(rows, cases, lambda c: c["language"] == "en")},
        "stages": {stage: {"correct": metrics[stage + "_correct_cases"], "eligible": metrics[stage + "_eligible_cases"]} for stage in STAGES},
        "execution": {"policy_steps": metrics["policy_steps_observed"], "tool_call_attempts": metrics["tool_call_attempts_observed"],
                      "tool_calls_executed": metrics["tool_calls_observed"], "cases_with_execution_trace": metrics["cases_with_execution_trace"],
                      "inner_call_statuses": dict(sorted(inner_status.items())),
                      "inner_inference_ms": stats(latency), "inner_worker_rss_mib_max": max(rss) if rss else None,
                      "worker_restarts": len(inner.get("worker_restarts") or []), "load_ms": inner.get("load_ms")},
        "chosen_position": dict(sorted(positions.items())), "first_step_choice": dict(sorted(first_steps.items())),
        "expected_to_final_reason": [{"expected": e, "final": f, "cases": n} for (e, f), n in sorted(matrix.items())],
        "families": [{"family": k, **v} for k, v in sorted(families.items())],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, help="LABEL=ARCHIVE=PROFILE")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        require(not args.output.exists(), "refusing to overwrite the output")
        data = (ROOT / DATASET).read_bytes()
        dataset_sha = sha(data)
        require(load(ROOT / MANIFEST)["cases_sha256"] == dataset_sha, "frozen pack manifest mismatch")
        cases = {c["case_id"]: c for c in map(json.loads, data.decode("utf-8").splitlines())}
        runs = []
        for spec in args.run:
            label, archive, profile = spec.split("=", 2)
            runs.append(export_run(label, Path(archive).resolve(), (ROOT / profile).resolve(), cases, dataset_sha))
        document = {"schema_version": SCHEMA, "pack": "tool-episodes-choice-v1", "dataset_sha256": dataset_sha,
                    "policy_mode": "closed_choice_step_menu_v1", "reference_review": "agent_only_pending_human",
                    "limits": ["32 correlated synthetic cases on seven fault routes; 20 TRAIN, 12 TEST",
                               "menu and wording are fixed by the harness; premature success and malformed actions are impossible by construction",
                               "not comparable with the generated-JSON contract; no live service or product workflow"],
                    "runs": runs}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
        for forbidden in ("/Users/", "/private/", "/tmp/", "/home/"):
            require(forbidden not in text, "local path in public aggregate")
        args.output.write_text(text, encoding="utf-8")
        print(json.dumps({"status": "aggregate_written", "runs": [(r["label"], r["counts"]["all"]["procedure_correct_cases"]) for r in runs]}))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Export refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
