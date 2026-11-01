#!/usr/bin/env python3
"""Export public aggregates for passage-relevance-v2 and the human-confirmation facade packs; no inference.

`relevance` mode: `--run LABEL=ARCHIVE=PROFILE` (CPU worker archive) and
`--gpu-run LABEL=PILOT=ASSETS` (run-upstream-native-pilot.py archive) and
`--uzu-run LABEL=PILOT=ASSETS` (run-uzu-pilot.py archive).
`hitl` mode: the same candidate on both variants, `--run LABEL=ARCH9=ARCH8=PROFILE`,
`--gpu-run LABEL=PILOT9=PILOT8=ASSETS`, plus `--router R9=R8 --router-revision SHA`.
Seals, tracked pack bytes, tracked profiles or asset manifests, model revisions
and full GPU offload are verified. For the eight-option variant, a model's
top-1 probability is thresholded with the rule fixed in
docs/FACADE_ROUTING_HITL_DESIGN_20261101.md (τ chosen on TRAIN + calibration by
balanced accuracy, lowest τ on ties, applied unchanged to TEST). Only counts,
rates and hashes are written; inputs, outputs, probabilities and paths stay local.
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
SCHEMA = "deposium.review-packs-public/v1"
PACKS = {"relevance": ("passage-relevance-v2",), "hitl": ("facade-routing-hitl-v1", "facade-routing-hitl-8opt-v1")}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def module(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


facade = module("scripts/export-facade-routing.py", "facade_export")
gpu = module("scripts/export-gguf-gpu-campaign.py", "gguf_export")


def tracked(pack):
    payload = (ROOT / "datasets" / pack / "cases.jsonl").read_bytes()
    digest = sha(payload)
    require(load(ROOT / "datasets" / pack / "manifest.json")["cases_sha256"] == digest, f"{pack}: manifest mismatch")
    return digest, {c["case_id"]: c for c in map(json.loads, payload.decode("utf-8").splitlines())}


def top_probability(raw):
    answers = ((raw or {}).get("native_result") or {}).get("answers") or {}
    for answer in answers.values():
        probabilities = answer.get("probabilities")
        if isinstance(probabilities, dict) and probabilities:
            return max(probabilities.values())
    return None


def campaign_rows(archive: Path, cases: dict, digest: str):
    facade.verify_seal(archive)
    manifest, summary = load(archive / "manifest.json"), load(archive / "summary.json")
    require(manifest["dataset_sha256"] == digest and summary["completion_status"] == "complete", "incomplete archive or other pack")
    passed = {r["case_id"]: r["passed"] for r in summary["metrics"]["rows"]}
    raw = [json.loads(line) for line in (archive / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
    require(set(passed) == set(cases) == {r["case_id"] for r in raw}, "case set differs")
    rows = {}
    for r in raw:
        case = cases[r["case_id"]]
        choice = (r.get("output") or {}).get("choice_id") if r["status"] == "ok" else None
        rows[r["case_id"]] = {"status": r["status"], "passed": passed[r["case_id"]],
                              "predicted": case["evaluation"]["oracle"]["choices"].get(choice) if choice else None,
                              "top": top_probability(r.get("raw_output")), "ms": r.get("duration_ms")}
    return rows, summary


def cpu_candidate(archive: Path, profile_path: str, cases: dict, digest: str):
    profile = (ROOT / profile_path).resolve()
    require(profile.is_relative_to(ROOT / "profiles"), "profile must be tracked under profiles/")
    rows, summary = campaign_rows(archive, cases, digest)
    manifest, final, tracked_profile = load(archive / "manifest.json"), load(archive / "adapter-final.json"), load(profile)
    require(manifest["source_profile_sha256"] == sha(profile.read_bytes()) and final["model_revision"] == tracked_profile["revision"],
            "archive was not produced by this tracked profile")
    identity = {"adapter": final["adapter"], "model_repo_id": final["model_repo_id"], "model_revision": final["model_revision"],
                "runtime_lock_sha256": final.get("runtime_lock_sha256"), "profile": str(profile.relative_to(ROOT)),
                "raw_sha256": summary["raw_sha256"], "seal_sha256": sha((archive / "seal.json").read_bytes())}
    return rows, identity


def gpu_candidate(pilot: Path, assets_path: str, cases: dict, digest: str, backend: str):
    assets_file = (ROOT / assets_path).resolve()
    require(assets_file.is_relative_to(ROOT / "profiles"), "asset manifest must be tracked under profiles/")
    assets = load(assets_file)
    result = gpu.verify_pilot(pilot, assets, backend)
    require(result["dataset"]["sha256"] == digest, "pilot dataset differs from the frozen pack")
    rows, summary = campaign_rows(pilot / "campaign", cases, digest)
    identity = {"adapter": "systemone_local", "backend": backend, "model_repo_id": assets["repo_id"],
                "model_revision": assets["revision"], "model_sha256": assets["files"][0]["sha256"],
                "assets_manifest": str(assets_file.relative_to(ROOT)), "native_revision": result["runtime"]["revision"],
                "binary_sha256": result["runtime"]["binary_sha256"], "raw_sha256": summary["raw_sha256"],
                "seal_sha256": sha((pilot / "pilot-seal.json").read_bytes()), "rss_peak_mib": result["resources"]["rss_peak_mib"]}
    return rows, identity


def uzu_candidate(pilot: Path, assets_path: str, cases: dict, digest: str):
    assets_file = (ROOT / assets_path).resolve()
    require(assets_file.is_relative_to(ROOT / "profiles"), "asset manifest must be tracked under profiles/")
    deployment = module("scripts/export-deployment-variants.py", "deployment_export")
    verified = deployment.verify_uzu(pilot, assets_file)
    require(verified["dataset_sha256"] == digest, "pilot dataset differs from the frozen pack")
    rows, summary = campaign_rows(pilot / "campaign", cases, digest)
    assets = load(assets_file)
    identity = {"adapter": "uzu_local", "backend": "uzu", "backend_requested": "metal", "model_repo_id": assets["repo_id"],
                "model_revision": assets["revision"], "model_sha256": sha(assets_file.read_bytes()),
                "assets_manifest": str(assets_file.relative_to(ROOT)), "uzu_revision": verified["runtime"]["uzu_revision"],
                "binary_sha256": verified["runtime"]["binary_sha256"], "raw_sha256": summary["raw_sha256"],
                "seal_sha256": sha((pilot / "pilot-seal.json").read_bytes()), "rss_peak_mib": verified["rss_peak_mib"]}
    return rows, identity


def router_candidate(archive: Path, cases: dict, digest: str):
    rows, summary = campaign_rows(archive, cases, digest)
    final = load(archive / "adapter-final.json")
    require(final["adapter"] == "recorded" and final["qualification"] == "harness_control"
            and final["recordings_count"] == len(cases), "router archive is not a complete recorded replay")
    return rows, {"recordings_sha256": final["recordings_sha256"], "raw_sha256": summary["raw_sha256"],
                  "seal_sha256": sha((archive / "seal.json").read_bytes())}


def ratio(rows, pick):
    chosen = [r for r in rows if pick(r)]
    return {"correct": sum(r["passed"] for r in chosen), "total": len(chosen)}


def latency(rows):
    values = [r["ms"] for r in rows.values() if r["status"] == "ok" and isinstance(r["ms"], (int, float))]
    return statistics.median(values) if values else None


def relevance_counts(rows, cases):
    items = [{**rows[c], "label": cases[c]["evaluation"]["oracle"]["params"]["task"], "split": cases[c]["split"],
              "role": cases[c]["evaluation"]["oracle"]["params"]["kind"]} for c in rows]
    labels = ("direct", "partial", "no_usable_evidence")
    per_class = {label: ratio(items, lambda r, label=label: r["label"] == label) for label in labels}
    test_class = {label: ratio(items, lambda r, label=label: r["label"] == label and r["split"] == "test") for label in labels}
    return {"all": ratio(items, lambda r: True), "test": ratio(items, lambda r: r["split"] == "test"),
            "by_class": per_class, "test_by_class": test_class,
            "macro_accuracy": sum(v["correct"] / v["total"] for v in per_class.values()) / len(labels),
            "test_macro_accuracy": sum(v["correct"] / v["total"] for v in test_class.values()) / len(labels),
            "by_role": {role: ratio(items, lambda r, role=role: r["role"] == role) for role in sorted({i["role"] for i in items})},
            "statuses": dict(sorted(Counter(r["status"] for r in items).items())),
            "majority_baseline": per_class["no_usable_evidence"]["total"], "median_call_ms": latency(rows)}


def hitl_items(rows, cases, prefix_len=5):
    out = {}
    for case_id, row in rows.items():
        params = cases[case_id]["evaluation"]["oracle"]["params"]
        out[case_id[prefix_len:]] = {**row, "split": cases[case_id]["split"], "kind": params["kind"],
                                     "needs_human": params["needs_human"], "candidates": params["candidates"]}
    return out


KINDS = ("hitl_choose", "hitl_confirm", "control", "out_of_scope", "ambiguous")


def explicit_counts(items):
    def outcome(r):
        p = r["predicted"]
        return ("asks_human" if p == "hitl" else "none" if p == "none" else "candidate" if p in r["candidates"]
                else "other" if p else r["status"])
    test = [r for r in items.values() if r["split"] == "test"]
    return {"all": ratio(items.values(), lambda r: True), "test": ratio(test, lambda r: True),
            "test_by_kind": {k: dict(sorted(Counter(outcome(r) for r in test if r["kind"] == k).items())) for k in KINDS},
            "statuses": dict(sorted(Counter(r["status"] for r in items.values()).items()))}


def threshold_counts(items, explicit=None):
    fit = [r for r in items.values() if r["split"] != "test"]
    test = [r for r in items.values() if r["split"] == "test"]
    out = {"routing_all": ratio(items.values(), lambda r: True), "routing_test": ratio(test, lambda r: True)}
    if any(r["top"] is None for r in items.values()):
        out["threshold"] = None
        return out
    def balanced(xs, tau):
        pos = [x for x in xs if x["needs_human"]]
        neg = [x for x in xs if not x["needs_human"]]
        return (sum(x["top"] < tau for x in pos) / len(pos) + sum(x["top"] >= tau for x in neg) / len(neg)) / 2
    candidates = sorted({x["top"] for x in fit}) + [1.0 + 1e-9]
    tau = max(candidates, key=lambda t: (balanced(fit, t), -t))
    pos = [x for x in test if x["needs_human"]]
    neg = [x for x in test if not x["needs_human"]]
    auc = sum((p["top"] < n["top"]) + 0.5 * (p["top"] == n["top"]) for p in pos for n in neg) / (len(pos) * len(neg))
    kept = [x for x in test if x["top"] >= tau]
    out["threshold"] = {"tau": tau, "fit_cases": len(fit), "test_needs_human": len(pos), "test_clear": len(neg),
                        "test_detected": sum(x["top"] < tau for x in pos), "test_false_alarms": sum(x["top"] < tau for x in neg),
                        "test_auc": auc, "test_routed": len(kept), "test_routed_correct": sum(x["passed"] for x in kept),
                        "test_asked_by_kind": {k: {"asked": sum(x["top"] < tau for x in test if x["kind"] == k),
                                                   "total": sum(1 for x in test if x["kind"] == k)} for k in KINDS}}
    if explicit is not None:
        asks = {key for key, r in explicit.items() if r["predicted"] == "hitl"}
        either = lambda key, x: key in asks or x["top"] < tau
        test_keys = [(k, x) for k, x in items.items() if x["split"] == "test"]
        out["combined_with_explicit"] = {
            "test_detected": sum(either(k, x) for k, x in test_keys if x["needs_human"]),
            "test_false_alarms": sum(either(k, x) for k, x in test_keys if not x["needs_human"]),
            "test_detected_by_kind": {k: sum(either(key, x) for key, x in test_keys if x["kind"] == k) for k in ("hitl_choose", "hitl_confirm")}}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=sorted(PACKS), required=True)
    parser.add_argument("--run", action="append", default=[])
    parser.add_argument("--gpu-run", action="append", default=[])
    parser.add_argument("--uzu-run", action="append", default=[])
    parser.add_argument("--backend", default="metal", choices=("metal", "cuda", "rocm", "vulkan"))
    parser.add_argument("--router")
    parser.add_argument("--router-revision")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        require(not args.output.exists(), "refusing to overwrite the output")
        packs = {pack: tracked(pack) for pack in PACKS[args.mode]}
        candidates = []
        specs = [("cpu", s) for s in args.run] + [("gpu", s) for s in args.gpu_run] + [("uzu", s) for s in args.uzu_run]
        require(specs, "at least one candidate run is required")
        for kind_, spec in specs:
            parts = spec.split("=")
            label, archives, reference = parts[0], [Path(p) for p in parts[1:-1]], parts[-1]
            require(len(archives) == len(packs), "one archive per pack is required")
            loaded = []
            for archive, (pack, (digest, cases)) in zip(archives, packs.items()):
                loaded.append(cpu_candidate(archive, reference, cases, digest) if kind_ == "cpu"
                              else uzu_candidate(archive, reference, cases, digest) if kind_ == "uzu"
                              else gpu_candidate(archive, reference, cases, digest, args.backend))
            entry = {"label": label, "identities": [identity for _, identity in loaded]}
            if args.mode == "relevance":
                entry["counts"] = relevance_counts(loaded[0][0], packs["passage-relevance-v2"][1])
            else:
                nine = hitl_items(loaded[0][0], packs["facade-routing-hitl-v1"][1])
                eight = hitl_items(loaded[1][0], packs["facade-routing-hitl-8opt-v1"][1])
                entry["explicit_option"] = explicit_counts(nine)
                entry["own_confidence"] = threshold_counts(eight, nine)
                entry["median_call_ms"] = latency(loaded[1][0])
            candidates.append(entry)
        out = {"schema_version": SCHEMA, "mode": args.mode,
               "packs": {pack: digest for pack, (digest, _) in packs.items()}, "candidates": candidates,
               "qualification": "exploratory; agent-authored references pending human review"}
        if args.mode == "hitl":
            require(args.router and args.router_revision and re.fullmatch(r"[0-9a-f]{40}", args.router_revision),
                    "router replay and full revision required")
            r9, r8 = (Path(p) for p in args.router.split("="))
            rows9, id9 = router_candidate(r9, packs["facade-routing-hitl-v1"][1], packs["facade-routing-hitl-v1"][0])
            rows8, id8 = router_candidate(r8, packs["facade-routing-hitl-8opt-v1"][1], packs["facade-routing-hitl-8opt-v1"][0])
            out["router"] = {"label": "FacadeRouterReplay", "router_source_revision": args.router_revision, "identities": [id9, id8],
                             "explicit_option": explicit_counts(hitl_items(rows9, packs["facade-routing-hitl-v1"][1])),
                             "own_confidence": threshold_counts(hitl_items(rows8, packs["facade-routing-hitl-8opt-v1"][1]))}
        text = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        for forbidden in ("/Users/", "/private/", "/tmp/", "/home/"):
            require(forbidden not in text, "local path in public aggregate")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(json.dumps({"status": "aggregate_written", "mode": args.mode, "candidates": [c["label"] for c in candidates]}))
    except (ValueError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
