#!/usr/bin/env python3
"""Export reviewed public aggregates for Mirai's 4-bit D3 Flash pack on Uzu; no inference.

Each `--phase PACK=PILOT_ARCHIVE` names a sealed archive written by
`scripts/run-uzu-pilot.py` on a frozen choice pack (context, capability,
physics). The pilot seal, the inner campaign seal, the tracked pack bytes, the
tracked asset manifest and the pinned Uzu release are verified, then the phase
is scored through the same derived rescore and analysis as the GGUF exports.
Uzu does not report its compute backend: Metal is recorded as requested, not
observed. Only counts, latency, sampled RSS and identity hashes are written.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCHEMA = "deposium.uzu-campaign-public/v1"
PROTOCOL = "docs/UZU_D3_FLASH_M_PROTOCOL_20261101.md"
ASSETS = "profiles/d3-flash-m-uzu-assets.json"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--hardware", required=True, help="public hardware class")
    parser.add_argument("--phase", action="append", required=True, help="PACK=PILOT_ARCHIVE")
    parser.add_argument("--private-analysis", required=True, type=Path, help="new ignored directory for derived rescores")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    gguf = module("gguf_export", "scripts/export-gguf-gpu-campaign.py")
    deployment = module("deployment_export", "scripts/export-deployment-variants.py")
    require = gguf.require
    try:
        require(not args.output.exists(), "refusing to overwrite the output")
        private = args.private_analysis.absolute()
        require(private.resolve().is_relative_to((ROOT / "results").resolve()) and not private.exists(),
                "private analysis must be a new directory under results/")
        private.mkdir(parents=True)
        assets_path = ROOT / ASSETS
        assets = gguf.load(assets_path)
        phases, runtime = {}, None
        for spec in args.phase:
            pack, pilot = spec.split("=")
            pilot = Path(pilot)
            require(pack in gguf.CHOICE_PACKS and pack not in phases, f"unknown or duplicate pack {pack}")
            identity = deployment.verify_uzu(pilot, assets_path)
            require(identity["runtime"] == (runtime or identity["runtime"]), "phases ran on different runtimes")
            runtime = identity["runtime"]
            result = gguf.load(pilot / "pilot.json")
            # The GGUF scorer path reads these fields; Uzu reports no backend, so none is claimed.
            shaped = {"dataset": {"sha256": result["dataset_sha256"], "validated_cases": result["eligible_cases"]},
                      "actual_backend": {"kind": "uzu", "requested": "metal", "observed": None},
                      "resources": result["resources"]}
            body = gguf.export_choice(pack, pilot, None, shaped, private)
            body.update(attempt=pilot.name.rsplit("-", 1)[-1], rss_peak_mib=result["resources"]["rss_peak_mib"],
                        pilot_seal_sha256=sha((pilot / "pilot-seal.json").read_bytes()),
                        campaign_seal_sha256=sha((pilot / "campaign" / "seal.json").read_bytes()))
            body["resources"]["rss_scope"] = ("Sampled owned process-group peak over fresh Uzu server startup and this pack; "
                                              "unified memory, not GPU allocation")
            phases[pack] = body
        out = {"schema_version": SCHEMA, "label": args.label, "hardware": args.hardware, "protocol": PROTOCOL,
               "model": {"repo_id": assets["repo_id"], "revision": assets["revision"], "assets_manifest": ASSETS,
                         "assets_sha256": sha(assets_path.read_bytes()),
                         "weights_sha256": assets["files"][0]["sha256"]},
               "runtime": {**runtime, "backend": "uzu", "backend_requested": "metal", "backend_observed": None,
                           "egress_isolated": False},
               "phases": phases, "qualification": "exploratory; agent-authored references pending human review"}
        text = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        for forbidden in ("/Users/", "/private/", "/tmp/", "/home/"):
            require(forbidden not in text, "local path in public aggregate")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(json.dumps({"status": "aggregate_written", "label": args.label,
                          **{p: v["counts"]["passed_cases"] for p, v in phases.items()}}))
    except (ValueError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
