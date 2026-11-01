#!/usr/bin/env python3
"""Vocabulary-only native preparation of one pack for one D3/Clef GGUF; no weights, no inference.

Builds the exact native request bytes of every selected input through the
shared projection used by the upstream launcher, runs the pinned helper built
by `scripts/build-systemone-preflight.py` under RSS, host-reserve and wall-time
guards, and writes the audit that `run-upstream-native-pilot.py --preparation`
consumes. A synthetic oversized input is prepared separately and must be
refused. Everything is written to a new ignored `results/` directory: token
IDs, request bytes and paths stay local; only counts may be reported.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.native_resources import memory_snapshot  # noqa: E402
from deposium_bench.systemone_local import digest, native_request  # noqa: E402

_SPEC = importlib.util.spec_from_file_location("upstream_native_pilot", ROOT / "scripts/run-upstream-native-pilot.py")
upstream = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(upstream)
shared = upstream.shared
NEGATIVE_ID = "synthetic-native-overflow"


def require(value, reason):
    if not value:
        raise ValueError(reason)


def input_lines(cases, model_id, context):
    """One helper line per selected input, plus the separate overflow control."""
    lines = []
    for case in cases:
        wire = native_request(case["input"], model_id)[2]
        lines.append(json.dumps({"case_id": case["case_id"], "native_request_json": wire.decode()}, ensure_ascii=False))
    negative = native_request(upstream.overflow_input(context), model_id)[2]
    overflow = json.dumps({"case_id": NEGATIVE_ID, "native_request_json": negative.decode()}, ensure_ascii=False)
    return ("\n".join(lines) + "\n").encode(), (overflow + "\n").encode()


def run_helper(args, name, payload, output):
    """Run the helper once under the shared owned-process resource watcher."""
    (output / f"{name}-inputs.jsonl").write_bytes(payload)
    directory = output / name
    directory.mkdir()
    guard = {"stop_reason": None, "rss_peak_mib": 0, "min_available_mib": memory_snapshot()["MemAvailable_mib"]}
    stop, process, watcher = threading.Event(), None, None
    command = [str(args.helper), "--model", str(args.model), "--model-id", args.model_id,
               "--max-tokens", str(args.context), "--decision-type", args.decision_type]
    try:
        with (output / f"{name}-inputs.jsonl").open("rb") as stdin, \
                (directory / "prepared.jsonl").open("xb") as stdout, (directory / "stderr.log").open("xb") as stderr:
            process = subprocess.Popen(command, stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True)
            watcher = threading.Thread(target=shared.watch_resources, args=(process, stop, guard, directory, args), daemon=True)
            watcher.start()
            process.wait()
    finally:
        shared.finish_owned(process, watcher, stop)
    guard["exit_code"] = process.returncode if process is not None else None
    return (directory / "prepared.jsonl").read_bytes(), guard


def prepare(args):
    output = args.output.absolute()
    allowed = ROOT / "results"
    require(not allowed.is_symlink() and output.resolve().is_relative_to(allowed.resolve())
            and not output.exists() and not output.is_symlink(), "preparation_new_local_output_required")
    require(args.context == 4096, "preparation_context_must_match_launcher")
    model, helper = args.model.absolute(), args.helper.absolute()
    require(not model.is_symlink() and helper.is_file() and not helper.is_symlink(), "preparation_inputs_missing")
    assets = json.loads(args.assets_manifest.read_bytes())
    shared.validate_assets(assets, model)
    _, dataset, cases, _, warmup = upstream.selected_inputs(args)
    # The launcher's technical warm-up is a calibration input for passages; prepare it too.
    if warmup["case_id"] not in {case["case_id"] for case in cases}:
        cases = [*cases, warmup]
    main_payload, negative_payload = input_lines(cases, args.model_id, args.context)
    require(memory_snapshot()["MemAvailable_mib"] >= args.max_rss_mb + args.min_free_mb, "preparation_insufficient_memory")
    require(model.stat().st_size == assets["files"][0]["size"] and digest(model) == assets["files"][0]["sha256"],
            "native_model_hash_mismatch")
    output.mkdir(parents=True)
    prepared, main_guard = run_helper(args, "inputs", main_payload, output)
    require(main_guard["exit_code"] == 0 and main_guard["stop_reason"] is None, "native_preparation_failed")
    negative, negative_guard = run_helper(args, "overflow", negative_payload, output)
    require(negative_guard["exit_code"] == 2 and negative_guard["stop_reason"] is None, "native_overflow_not_refused")
    audit = output / "native-preparation.jsonl"
    audit.write_bytes(prepared + negative)
    # The launcher's own validator: exact inventory, wire hashes, option keys, limits and the refused overflow.
    mapping = upstream.preparation_map(audit, cases, args.model_id, args.context, args.decision_type, exact_cases=True)
    counts = sorted(mapping["request_tokens"].values())
    summary = {"schema_version": "deposium.native-preparation-summary/v2", "native_revision": upstream.PIN,
               "dataset_sha256": dataset["sha256"], "task": getattr(args, "task", "choices"),
               "prepared_inputs": len(cases), "distinct_request_bodies": len(counts),
               "min_tokens": counts[0], "max_tokens": counts[-1], "context": args.context,
               "model_repo_id": assets["repo_id"], "model_revision": assets["revision"],
               "model_sha256": assets["files"][0]["sha256"], "model_id": args.model_id,
               "helper_binary_sha256": digest(helper), "audit_sha256": mapping["audit_sha256"],
               "negative_control": "native_prepare_overflow_refused",
               "resources": {"inputs": main_guard, "overflow": negative_guard},
               "weights_loaded": False, "forward_executed": False,
               "scope": "local_only_contains_token_ids_do_not_publish"}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("helper", "model", "assets-manifest", "dataset", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--model-id", required=True)
    p.add_argument("--decision-type", choices=("d3", "clef"), default="d3")
    p.add_argument("--task", choices=("choices", "passages"), default="choices")
    p.add_argument("--passage-split", choices=("calibration", "test"), default="test")
    p.add_argument("--context", type=int, default=4096)
    p.add_argument("--max-rss-mb", type=int, default=2048)
    p.add_argument("--min-free-mb", type=int, default=8192)
    p.add_argument("--max-seconds", type=int, default=600)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    args.technical_only = False
    try:
        summary = prepare(args)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"Preparation stopped: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({k: summary[k] for k in ("prepared_inputs", "distinct_request_bodies", "min_tokens", "max_tokens")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
