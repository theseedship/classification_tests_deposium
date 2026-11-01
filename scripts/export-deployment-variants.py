#!/usr/bin/env python3
"""Export public aggregates comparing deployment variants of the D3 decision models; no inference.

Variants: D3 mini Q8 and Q4 GGUF on llama.cpp Metal (`run-upstream-native-pilot.py`
archives) and Mirai's 4-bit D3 Flash pack on Uzu (`run-uzu-pilot.py` archives).
Each `--phase VARIANT:PACK=ARCHIVE` is verified (outer and campaign seals, the
tracked pack bytes, the tracked asset manifest, the native or Uzu revision and
binary) and paired case by case with the D3 mini Q8 archive of the same pack.
Only counts, agreement, median call time and sampled RSS are written.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.uzu_local import UZU_REVISION  # noqa: E402

SCHEMA = "deposium.deployment-variants-public/v1"
PACKS = ("facade-routing-v1", "facade-routing-advanced-v1", "facade-routing-complex-v1", "context-choice-v1",
         "capability-choice-v1", "physics-choice-v1", "passage-relevance-v2", "facade-routing-hitl-v1",
         "facade-routing-hitl-8opt-v1")
VARIANTS = {"D3miniQ8Metal": ("gguf", "profiles/d3-mini-q8-assets.json"),
            "D3miniQ4Metal": ("gguf", "profiles/d3-mini-q4-assets.json"),
            "D3FlashMUzu": ("uzu", "profiles/d3-flash-m-uzu-assets.json")}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


spec = importlib.util.spec_from_file_location("gguf_export", ROOT / "scripts/export-gguf-gpu-campaign.py")
gguf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gguf)


def verify_uzu(pilot: Path, assets_path: Path):
    seal = load(pilot / "pilot-seal.json")
    require(seal.get("schema_version") == "deposium.uzu-pilot-seal/v1", "invalid Uzu pilot seal")
    for name, digest in seal["files"].items():
        require(sha((pilot / name).read_bytes()) == digest, f"Uzu pilot file changed: {name}")
    gguf.verify_seal(pilot / "campaign")
    result, session = load(pilot / "pilot.json"), load(pilot / "session.json")
    runtime = load(pilot / "runtime-manifest.json")
    require(result["completed"] is True and session["runtime"]["revision"] == UZU_REVISION == runtime["revision"]
            and session["runtime"]["sha256"] == runtime["binary_sha256"], "incomplete Uzu pilot or other runtime")
    require(session["model"]["assets_sha256"] == sha(assets_path.read_bytes()), "Uzu pack differs from the tracked manifest")
    return {"rss_peak_mib": result["resources"]["rss_peak_mib"], "backend_requested": result["backend_requested"],
            "backend_observed": result["backend_observed"], "egress_isolated": result["egress_isolated"],
            "runtime": {"uzu_revision": UZU_REVISION, "binary_sha256": runtime["binary_sha256"]},
            "dataset_sha256": result["dataset_sha256"]}


def verify_gguf(pilot: Path, assets_path: Path):
    result = gguf.verify_pilot(pilot, load(assets_path), "metal")
    return {"rss_peak_mib": result["resources"]["rss_peak_mib"], "backend_requested": "metal",
            "backend_observed": result["actual_backend"]["kind"], "egress_isolated": None,
            "runtime": {"native_revision": result["runtime"]["revision"], "binary_sha256": result["runtime"]["binary_sha256"]},
            "dataset_sha256": result["dataset"]["sha256"]}


def rows(pilot: Path, cases: dict, digest: str):
    campaign = pilot / "campaign"
    manifest, summary = load(campaign / "manifest.json"), load(campaign / "summary.json")
    require(manifest["dataset_sha256"] == digest and summary["completion_status"] == "complete", "incomplete campaign or other pack")
    passed = {r["case_id"]: r["passed"] for r in summary["metrics"]["rows"]}
    raw = {r["case_id"]: r for r in map(json.loads, (campaign / "raw.jsonl").read_text(encoding="utf-8").splitlines())}
    require(set(passed) == set(raw) == set(cases), "case set differs")
    return passed, raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", action="append", required=True, help="VARIANT:PACK=ARCHIVE")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        require(not args.output.exists(), "refusing to overwrite the output")
        archives = {}
        for item in args.phase:
            key, archive = item.split("=", 1)
            variant, pack = key.split(":")
            require(variant in VARIANTS and pack in PACKS and (variant, pack) not in archives, f"invalid phase {item}")
            archives[(variant, pack)] = Path(archive)
        out = {"schema_version": SCHEMA, "variants": {}, "packs": {},
               "qualification": "exploratory; deployment comparison (weights format, quantization and engine together)"}
        for pack in PACKS:
            payload = (ROOT / "datasets" / pack / "cases.jsonl").read_bytes()
            digest = sha(payload)
            cases = {c["case_id"]: c for c in map(json.loads, payload.decode("utf-8").splitlines())}
            baseline = None
            entry = {"dataset_sha256": digest, "cases": len(cases), "variants": {}}
            for variant in VARIANTS:
                pilot = archives.get((variant, pack))
                require(pilot is not None, f"missing {variant} on {pack}")
                kind, assets = VARIANTS[variant]
                identity = (verify_uzu if kind == "uzu" else verify_gguf)(pilot, ROOT / assets)
                require(identity.pop("dataset_sha256") == digest, f"{variant} archive is not on {pack}")
                passed, raw = rows(pilot, cases, digest)
                test = [c for c in cases if cases[c]["split"] == "test"]
                answers = {c: (raw[c].get("output") or {}).get("choice_id") for c in cases}
                body = {"correct": sum(passed.values()), "total": len(cases),
                        "test_correct": sum(passed[c] for c in test), "test_total": len(test),
                        "statuses": dict(sorted(Counter(r["status"] for r in raw.values()).items())),
                        "median_call_ms": statistics.median(r["duration_ms"] for r in raw.values() if r["status"] == "ok"),
                        "rss_peak_mib": identity["rss_peak_mib"],
                        "seal_sha256": sha((pilot / "pilot-seal.json").read_bytes())}
                if baseline is None:
                    baseline = (passed, answers)
                else:
                    body["paired_with_d3_mini_q8"] = {
                        "identical_answers": sum(answers[c] == baseline[1][c] for c in cases),
                        "both": sum(passed[c] and baseline[0][c] for c in cases),
                        "variant_only": sum(passed[c] and not baseline[0][c] for c in cases),
                        "q8_only": sum(baseline[0][c] and not passed[c] for c in cases)}
                entry["variants"][variant] = body
                out["variants"].setdefault(variant, {"assets_manifest": assets, "kind": kind,
                    **{k: identity[k] for k in ("backend_requested", "backend_observed", "egress_isolated", "runtime")}})
                require(out["variants"][variant]["runtime"] == identity["runtime"], f"{variant} ran on different runtimes")
            out["packs"][pack] = entry
        text = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        for forbidden in ("/Users/", "/private/", "/tmp/", "/home/"):
            require(forbidden not in text, "local path in public aggregate")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(json.dumps({"status": "aggregate_written", "packs": len(out["packs"])}))
    except (ValueError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
