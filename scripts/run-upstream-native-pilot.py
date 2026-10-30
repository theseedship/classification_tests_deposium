#!/usr/bin/env python3
"""Explicit isolated decision campaign against the real pinned upstream llama-server.

No application gateway, installation, download or inference on import. The
shared engine, adapter, input projection, supervision and scorers are reused.
All output, source captures, logs and path-bearing receipts stay in results/.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tarfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.campaigns import run_campaign, _archive, _decode
from deposium_bench.cases import parse_cases, typed_equal
from deposium_bench.scoring import summarize
from deposium_bench import systemone_local
from deposium_bench.native_resources import memory_snapshot
from deposium_bench.native_supervision import native_supervision, NativeSupervisionError
from deposium_bench.systemone_local import (AUTH_ENV, LocalSystemOneAdapter, digest, native_choice_response,
                                           http_request, native_overflow, native_request)

SPEC = importlib.util.spec_from_file_location("shared_native_pilot", ROOT / "scripts/run-native-pilot.py")
shared = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shared)
PIN = "efe3626b119ff81033e309c3ba07a770bef2c546"
REPOSITORY = "https://github.com/ggml-org/llama.cpp.git"
DEFAULT_ENVELOPE = "flash-clef-18g-v1"
D327_ENVELOPE = "d3-27b-q4-24g-v1"
D327_ALIAS = "d3-27b-q4-v1"
D327_ASSETS = {"schema_version": "deposium.model-assets/v1",
    "repo_id": "ggml-org/vllm-d3-GGUF", "revision": "de9670136f5ddd83e677c89ce041d5b9bb3b0dcb",
    "files": [{"path": "vllm-d3-Q4_K_M.gguf", "size": 19403686112,
               "sha256": "a5a341e8611dc5d916c8f4c693dbef4a68e57eb17d37914fd56dcb5a9221eb2d"}]}
D327_PACKS = {
    "anchor": ("context-choice-v1", "767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616", 132),
    "capability": ("capability-choice-v1", "0b409a09bb5358b5c8d7574cbd330799511851a2acd90676e2f092f3d3c75eb0", 192)}
D327_CANARY_IDS = tuple(f"ccv1-{track}-02-{catalogue}-{language}"
    for track in ("selection", "arguments", "observations")
    for catalogue in ("compact", "expanded") for language in ("fr", "en"))
D327_PHASE_CAPS = {"canary": 600, "anchor": 1200, "capability": 1800}
D327_BUDGET_RULE = "ceil_180_plus_2n_times_max_canary_adapter_seconds/v1"


def require(value, message):
    if not value:
        raise ValueError(message)


def closed(value, keys, code):
    require(isinstance(value, dict) and set(value) == set(keys), code)


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def hash_value(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def receipt_bytes(path):
    require(path is not None and path.is_file() and not path.is_symlink()
            and path.stat().st_size <= 1024 * 1024, "d327_receipt_missing_or_unbounded")
    payload = path.read_bytes()
    return payload, _decode(payload)


def d327_inputs(phase, selected, selected_path):
    """Bind the phase and complete preparation set to unchanged public packs."""
    packs, payloads = {}, {}
    for name, (directory, expected, count) in D327_PACKS.items():
        payload = (ROOT / "datasets" / directory / "cases.jsonl").read_bytes()
        require(hashlib.sha256(payload).hexdigest() == expected, "d327_frozen_dataset_mismatch")
        cases, actual = parse_cases(payload)
        require(actual == expected and len(cases) == count, "d327_frozen_dataset_mismatch")
        packs[name], payloads[name] = cases, payload
    indexed = {case["case_id"]: case for case in packs["capability"]}
    canary = [indexed[case_id] for case_id in D327_CANARY_IDS]
    require(all(case["split"] == "calibration" for case in canary), "d327_canary_not_calibration")
    expected = canary if phase == "canary" else packs[phase]
    require(selected == expected, "d327_phase_dataset_mismatch")
    if phase != "canary":
        require(selected_path.read_bytes() == payloads[phase], "d327_full_phase_bytes_mismatch")
    return packs["anchor"] + packs["capability"], canary


def execution_envelope(args, assets, model, cases):
    """Choose an explicit model-bound envelope, before any model-byte read."""
    name = getattr(args, "execution_envelope", DEFAULT_ENVELOPE)
    phase = getattr(args, "phase", None)
    require(args.context == 4096 and args.min_free_mb == 8192
            and type(args.max_seconds) is int and 1024 <= args.port <= 65535,
            "upstream_pilot_fixed_envelope_required")
    if name == DEFAULT_ENVELOPE:
        require(args.max_rss_mb == 18432 and 0 < args.max_seconds <= 1200 and phase is None
                and getattr(args, "preparation_receipt", None) is None
                and getattr(args, "calibration_receipt", None) is None,
                "upstream_pilot_fixed_envelope_required")
        require(assets.get("repo_id") != D327_ASSETS["repo_id"]
                and model.name != D327_ASSETS["files"][0]["path"]
                and assets["files"][0]["sha256"] != D327_ASSETS["files"][0]["sha256"],
                "d327_explicit_envelope_required")
        return {"name": name}, cases, None
    require(name == D327_ENVELOPE and typed_equal(assets, D327_ASSETS) and model.name == D327_ASSETS["files"][0]["path"]
            and getattr(args, "decision_type", "d3") == "d3" and getattr(args, "task", "choices") == "choices"
            and not getattr(args, "technical_only", False) and args.model_id == D327_ALIAS,
            "d327_exact_candidate_required")
    require(args.max_rss_mb == 24576 and phase in D327_PHASE_CAPS
            and 0 < args.max_seconds <= D327_PHASE_CAPS[phase]
            and (phase != "canary" or args.max_seconds == 600), "d327_fixed_envelope_required")
    all_cases, canary = d327_inputs(phase, cases, args.dataset)
    return {"name": name, "phase": phase, "context": 4096, "rss_limit_mib": 24576,
            "reserve_mib": 8192, "admission_available_mib": 32768, "max_seconds": args.max_seconds,
            "full_phase_caps": D327_PHASE_CAPS, "budget_rule": D327_BUDGET_RULE}, all_cases, canary


def d327_preparation_receipt(path, audit, prepared):
    payload, receipt = receipt_bytes(path)
    closed(receipt, {"schema_version", "execution_envelope", "model_id", "model_assets", "native_revision",
                     "helper", "audit_sha256", "case_count", "overflow_controls", "resources"}, "d327_preparation_receipt_shape")
    require(receipt["schema_version"] == "deposium.d3-27b-native-preparation/v1"
            and receipt["execution_envelope"] == D327_ENVELOPE and receipt["model_id"] == D327_ALIAS
            and typed_equal(receipt["model_assets"], D327_ASSETS) and receipt["native_revision"] == PIN
            and receipt["audit_sha256"] == digest(audit) == prepared["audit_sha256"]
            and type(receipt["case_count"]) is int and receipt["case_count"] == 324
            and type(receipt["overflow_controls"]) is int and receipt["overflow_controls"] == 1,
            "d327_preparation_receipt_binding")
    helper = receipt["helper"]
    closed(helper, {"source_sha256", "binary_sha256", "build_manifest_sha256"}, "d327_preparation_helper_shape")
    require(helper["source_sha256"] == digest(ROOT / "native/systemone-preflight.cpp")
            and all(hash_value(v) for v in helper.values()), "d327_preparation_helper_binding")
    resource = receipt["resources"]
    closed(resource, {"rss_limit_mib", "reserve_mib", "max_seconds", "rss_peak_mib", "min_available_mib",
                      "elapsed_seconds", "stop_reason", "completed"}, "d327_preparation_resource_shape")
    require(type(resource["rss_limit_mib"]) is int and resource["rss_limit_mib"] == 2048
            and type(resource["reserve_mib"]) is int and resource["reserve_mib"] == 8192
            and type(resource["max_seconds"]) is int and resource["max_seconds"] == 600
            and all(finite_number(resource[k]) for k in ("rss_peak_mib", "min_available_mib", "elapsed_seconds"))
            and 0 < resource["rss_peak_mib"] <= 2048 and resource["min_available_mib"] >= 8192
            and 0 < resource["elapsed_seconds"] <= 600 and resource["stop_reason"] is None
            and resource["completed"] is True, "d327_preparation_resource_refused")
    return payload, receipt


def derive_phase_budgets(durations_ms):
    """Pure, fixed calibration rule; no test scores or future calls are used."""
    require(isinstance(durations_ms, list) and len(durations_ms) == 12
            and all(finite_number(v) and 0 < v <= 30000 for v in durations_ms), "d327_calibration_timings_invalid")
    slowest = max(durations_ms)
    budgets = {phase: math.ceil(180 + 2 * count * slowest / 1000)
               for phase, (_, _, count) in D327_PACKS.items()}
    require(all(budgets[phase] <= D327_PHASE_CAPS[phase] for phase in budgets), "d327_calibration_exceeds_declared_cap")
    return {"rule": D327_BUDGET_RULE, "max_canary_adapter_ms": slowest, "phase_max_seconds": budgets}


def verify_canary_seal(root, expected):
    """Read retained files only; never restore a saved service or load weights."""
    require(root.is_dir() and not root.is_symlink(), "d327_calibration_archive_missing")
    _, seal = receipt_bytes(root / "pilot-seal.json")
    require(seal.get("schema_version") == "deposium.native-pilot-seal/v1"
            and isinstance(seal.get("files"), dict) and 1 <= len(seal["files"]) <= 128
            and digest(root / "pilot-seal.json") == expected, "d327_calibration_seal_binding")
    entries = list(root.rglob("*"))
    require(not any(p.is_symlink() for p in entries)
            and {str(p.relative_to(root)) for p in entries if p.is_file()} == set(seal["files"]) | {"pilot-seal.json"},
            "d327_calibration_seal_inventory")
    require(sum(p.stat().st_size for p in entries if p.is_file()) <= 128 * 1024 * 1024,
            "d327_calibration_archive_unbounded")
    for relative, expected_hash in seal["files"].items():
        member = Path(relative)
        require(not member.is_absolute() and ".." not in member.parts and relative != "pilot-seal.json"
                and hash_value(expected_hash), "d327_calibration_unsafe_seal_member")
        require(digest(root / member) == expected_hash, "d327_calibration_sealed_file_changed")


def d327_calibration_receipt(path, phase, seconds, preparation_payload, prepared, canary, runtime):
    require(phase in D327_PACKS, "d327_calibration_phase_invalid")
    payload, receipt = receipt_bytes(path)
    closed(receipt, {"schema_version", "execution_envelope", "model_id", "model_sha256",
                     "preparation_receipt_sha256", "canary_archive", "canary_seal_sha256", "derivation"},
           "d327_calibration_receipt_shape")
    require(receipt["schema_version"] == "deposium.d3-27b-calibration/v1"
            and receipt["execution_envelope"] == D327_ENVELOPE and receipt["model_id"] == D327_ALIAS
            and receipt["model_sha256"] == D327_ASSETS["files"][0]["sha256"]
            and receipt["preparation_receipt_sha256"] == hashlib.sha256(preparation_payload).hexdigest()
            and isinstance(receipt["canary_archive"], str) and Path(receipt["canary_archive"]).is_absolute(),
            "d327_calibration_receipt_binding")
    root = Path(receipt["canary_archive"])
    verify_canary_seal(root, receipt["canary_seal_sha256"])
    _, manifest, cases, records, parent, retained = _archive(root / "campaign")
    _, pilot = receipt_bytes(root / "pilot.json")
    _, session = receipt_bytes(root / "session.json")
    require(all(isinstance(pilot.get(k), dict) for k in ("runtime", "resources", "execution_envelope", "actual_backend", "memory_before"))
            and all(isinstance(session.get(k), dict) for k in ("model", "runtime", "harness", "runtime_pin", "gateway", "native_preparation")),
            "d327_calibration_canary_shape")
    profile = json.loads(retained["profile.json"])
    backend = pilot["actual_backend"]
    require(parent["sealed"] and cases == canary and len(records) == 12
            and manifest["qualification"] == "model_isolated" and manifest["input_protocol"] == "context_choice"
            and pilot["completed"] is True and typed_equal(pilot["model_assets"], D327_ASSETS)
            and pilot["runtime"]["binary_sha256"] == runtime["binary_sha256"]
            and pilot["resources"]["stop_reason"] is None
            and finite_number(pilot["resources"].get("rss_peak_mib"))
            and 0 < pilot["resources"]["rss_peak_mib"] <= 24576
            and finite_number(pilot["resources"].get("min_available_mib"))
            and pilot["resources"]["min_available_mib"] >= 8192
            and finite_number(pilot["memory_before"].get("MemAvailable_mib"))
            and pilot["memory_before"]["MemAvailable_mib"] >= 32768
            and pilot["execution_envelope"]["name"] == D327_ENVELOPE
            and pilot["execution_envelope"]["phase"] == "canary"
            and pilot["execution_envelope"]["max_seconds"] == 600
            and backend["kind"] == "metal" and backend["decision_type"] == "vllm-d3"
            and type(backend["offloaded_layers"]) is int and backend["offloaded_layers"] > 0
            and backend["offloaded_layers"] == backend["total_layers"]
            and session["model"]["repo_id"] == D327_ASSETS["repo_id"]
            and session["model"]["revision"] == D327_ASSETS["revision"]
            and session["model"]["sha256"] == D327_ASSETS["files"][0]["sha256"]
            and session["model"]["alias"] == D327_ALIAS and session["runtime"]["revision"] == PIN
            and session["runtime"]["sha256"] == runtime["binary_sha256"]
            and session["settings"] == {"context": 4096, "parallel": 1, "concurrency": 1,
                "questions_per_call": 1, "truncation": "reject_in_pinned_native_engine"}
            and session["max_rss_mb"] == 24576 and session["harness"]["sha256"] == digest(__file__)
            and profile["adapter"] == "systemone_local" and profile["revision"] == D327_ASSETS["revision"]
            and profile["qualification"] == "model_isolated" and profile["capabilities"] == ["bench.context-choice"]
            and profile["timeout_seconds"] == 30 and profile["model"]["repo_id"] == D327_ASSETS["repo_id"]
            and profile["model"]["max_length"] == 4096 and profile["model"]["endpoint"] == session["endpoint"]
            and profile["model"]["model_id"] == D327_ALIAS and profile["model"]["max_rss_mb"] == 24576
            and profile["model"]["session_sha256"] == digest(root / "session.json")
            and session["native_preparation"]["sha256"] == digest(root / "native-preparation.json")
            and json.loads((root / "native-preparation.json").read_bytes()) == prepared
            and (root / "preparation-receipt.json").read_bytes() == preparation_payload,
            "d327_calibration_canary_binding")
    identity = {key: session[key] for key in ("model", "runtime", "gateway", "harness", "runtime_pin", "settings", "max_rss_mb")}
    identity["adapter_sha256"] = digest(systemone_local.__file__)
    identity["choice_protocol_sha256"] = digest(Path(systemone_local.__file__).with_name("choice_protocol.py"))
    identity["native_preparation"] = session["native_preparation"]
    provenance = manifest.get("adapter_provenance")
    require(isinstance(provenance, dict) and provenance.get("adapter") == "systemone_local"
            and provenance.get("qualification") == "model_isolated" and provenance.get("available") is True
            and provenance.get("capabilities") == ["bench.context-choice"]
            and provenance.get("session_sha256") == digest(root / "session.json")
            and typed_equal(provenance.get("identity"), identity)
            and provenance.get("identity_sha256") == hashlib.sha256(systemone_local._wire(identity)).hexdigest(),
            "d327_calibration_provenance_binding")
    _, summary = receipt_bytes(root / "campaign/summary.json")
    require(summary.get("schema_version") == "deposium.campaign-summary/v1"
            and summary.get("run_id") == manifest["run_id"] and summary.get("completion_status") == "complete"
            and summary.get("qualification") == "model_isolated"
            and summary.get("raw_sha256") == digest(root / "campaign/raw.jsonl")
            and typed_equal(summary.get("metrics"), summarize(cases, records)), "d327_calibration_summary_incomplete")
    by_id = {c["case_id"]: c for c in canary}
    for record in records:
        case = by_id[record["case_id"]]
        body, mapping, wire = native_request(case["input"], D327_ALIAS)
        body_hash = hashlib.sha256(wire).hexdigest()
        raw = record.get("raw_output")
        usage = raw.get("usage") if isinstance(raw, dict) else None
        require(record["status"] == "ok" and record["output"] in [{"choice_id": o["id"]} for o in case["input"]["options"]]
                and isinstance(raw, dict) and isinstance(usage, dict)
                and raw.get("http_attempted") is True and raw.get("http_status") == 200
                and raw.get("cached_failure") is False and raw.get("requested_model") == D327_ALIAS
                and raw.get("native_request") == body and raw.get("option_mapping") == mapping
                and raw.get("request_body_sha256") == body_hash
                and raw.get("native_preparation_count_match") is True
                and type(usage.get("input_tokens")) is int and usage["input_tokens"] == prepared["request_tokens"][body_hash]
                and type(usage.get("output_tokens")) is int and usage["output_tokens"] == 0
                and raw.get("observed_model") == D327_ALIAS,
                "d327_calibration_twelve_actual_calls_required")
        native_output, diagnostic = native_choice_response(raw.get("native_result"), D327_ALIAS,
            session["model"]["path"], mapping, 4096, prepared["request_tokens"][body_hash])
        require(typed_equal(native_output, record["output"])
                and all(typed_equal(raw.get(key), value) for key, value in diagnostic.items())
                and raw.get("native_usage_truncated") is (diagnostic.get("native_usage_truncated")),
                "d327_calibration_native_response_binding")
    derivation = derive_phase_budgets([r["duration_ms"] for r in records])
    require(receipt["derivation"] == derivation and type(seconds) is int
            and seconds == derivation["phase_max_seconds"][phase], "d327_calibration_budget_mismatch")
    return payload, receipt


def capture(command, cwd=None):
    return subprocess.check_output(command, cwd=cwd, text=True, stderr=subprocess.PIPE).strip()


def overflow_input(context):
    return {"context": "sentinel " * (context + 512), "question": "Choose one option.",
            "options": [{"id": str(i), "description": f"Option {i}"} for i in range(4)]}


def preparation_map(audit_path, cases, model_id, context, decision_type="d3", *, exact_cases=False):
    """Bind exact wire bytes to actual vocabulary-only native preparation."""
    require(audit_path.is_file() and not audit_path.is_symlink()
            and audit_path.stat().st_size <= 16 * 1024 * 1024, "native_preparation_missing")
    rows = [json.loads(line) for line in audit_path.read_bytes().splitlines()]
    by_id = {}
    request_tokens = {}
    negative = None
    for row in rows:
        require(row["case_id"] not in by_id, "native_preparation_duplicate")
        by_id[row["case_id"]] = row
        require(decision_type in {"d3", "clef"}
                and row.get("decision_type", "d3") == decision_type
                and row["schema_version"] == "deposium.native-systemone-encoding/v1"
                and row["source_revision"] == PIN and row["max_tokens"] == context
                and row["vocab_only"] is True and row["weights_loaded"] is False
                and row["inference_context_created"] is False and row["forward_executed"] is False
                and row["native_input_prepared"] is True and row["variant_count"] == 1
                and len(row["variants"]) == 1, "native_preparation_invalid")
        variant = row["variants"][0]
        tokens = variant["token_ids"]
        option_keys = variant["option_keys"]
        require(option_keys in (["c0", "c1", "c2"], ["c0", "c1", "c2", "c3"])
                and isinstance(tokens, list) and tokens and all(type(t) is int for t in tokens)
                and type(variant["token_count"]) is int and len(tokens) == variant["token_count"],
                "native_preparation_tokens_invalid")
        token_bytes = json.dumps(tokens, separators=(",", ":")).encode()
        require(hashlib.sha256(token_bytes).hexdigest() == variant["token_ids_sha256"],
                "native_preparation_token_hash_invalid")
        if decision_type == "clef":
            order = variant["decision_order"]
            require(row["joint"] is True and variant["n_scores"] == len(option_keys)
                    and isinstance(order, list) and len(order) == len(tokens)
                    and all(type(value) is int for value in order), "native_preparation_joint_head_invalid")
            order_bytes = json.dumps(order, separators=(",", ":")).encode()
            require(hashlib.sha256(order_bytes).hexdigest() == variant["decision_order_sha256"],
                    "native_preparation_joint_order_hash_invalid")
        if row["case_id"] == "synthetic-native-overflow":
            require(row["status"] == "unsupported" and variant["within_limit"] is False
                    and variant["token_count"] > context, "native_preparation_negative_control_failed")
            negative = row
        else:
            require(row["status"] == "within_limit" and variant["within_limit"] is True
                    and 0 < variant["token_count"] <= context, "native_preparation_overflow_or_error")
            body_hash = row["request_body_sha256"]
            require(re.fullmatch(r"[0-9a-f]{64}", body_hash), "native_preparation_body_hash_invalid")
            require(body_hash not in request_tokens or request_tokens[body_hash] == variant["token_count"],
                    "native_preparation_inconsistent")
            request_tokens[body_hash] = variant["token_count"]
    require(negative is not None, "native_preparation_negative_control_missing")
    if exact_cases:
        require(set(by_id) == {case["case_id"] for case in cases} | {"synthetic-native-overflow"},
                "native_preparation_exact_inventory_required")
        negative_wire = native_request(overflow_input(context), model_id)[2]
        require(negative["request_body_sha256"] == hashlib.sha256(negative_wire).hexdigest()
                and negative["request_body_bytes"] == len(negative_wire), "native_preparation_overflow_input_mismatch")
    for case in cases:
        _, _, body = native_request(case["input"], model_id)
        row = by_id.get(case["case_id"])
        require(row is not None and row["request_body_sha256"] == hashlib.sha256(body).hexdigest()
                and row["request_body_bytes"] == len(body)
                and row["variants"][0]["option_keys"] == ["c" + str(i) for i in range(len(case["input"]["options"]))],
                "native_preparation_input_mismatch")
    return {"schema_version": "deposium.native-preparation-map/v1", "source_revision": PIN,
            "decision_type": decision_type,
            "model_id": model_id, "max_tokens": context, "request_tokens": request_tokens,
            "audit_sha256": digest(audit_path), "audit_scope": "preparation_not_live_token_id_comparison"}


def validated_runtime(source, binary, manifest_path):
    require(not binary.is_symlink() and binary.is_file(), "native_binary_missing")
    manifest = json.loads(manifest_path.read_bytes())
    require(manifest["repository"] == REPOSITORY and manifest["revision"] == PIN
            and capture(["git", "rev-parse", "HEAD"], source) == PIN
            and capture(["git", "remote", "get-url", "origin"], source) == REPOSITORY
            and not capture(["git", "status", "--porcelain", "--untracked-files=all"], source),
            "native_source_identity_mismatch")
    require(digest(binary) == manifest["binary_sha256"], "native_binary_hash_mismatch")
    return manifest


def selected_inputs(args):
    """Use the existing task-specific validators/projections, never new golds."""
    if getattr(args, "task", "choices") == "choices":
        require(not getattr(args, "technical_only", False), "technical_only_requires_passage_calibration")
        payload, metadata = shared.selected_dataset(args)
        cases, _ = parse_cases(payload)
        return payload, metadata, cases, None, cases[0]
    from deposium_bench.passage_dataset import load_dataset
    from deposium_bench.passage_observation import AXES, choice_plan, select_pilot
    split = args.passage_split
    technical = args.technical_only
    require(not technical or split == "calibration", "technical_only_requires_passage_calibration")
    payload = args.dataset.read_bytes()
    manifest = args.dataset.parent.joinpath("manifest.json").read_bytes()
    all_cases, dataset_sha = load_dataset(args.dataset)
    require(hashlib.sha256(payload).hexdigest() == dataset_sha, "passage_source_changed")
    selected = select_pilot(all_cases, split)
    _, physical = choice_plan(selected)
    calibration = select_pilot(all_cases, "calibration")
    logical_calibration, physical_calibration = choice_plan(calibration)
    call_ids = []
    for axis in AXES:
        ids = sorted({row["call_id"] for row in logical_calibration if row["axis"] == axis})[:4]
        require(len(ids) == 4, "passage_canary_axis_missing")
        call_ids.extend(ids)
    canary = {row["case_id"]: row for row in physical_calibration if row["case_id"] in call_ids}
    require(len(canary) == 12, "passage_canary_call_collision")
    canary_inputs = [canary[call_id] for call_id in call_ids]
    inputs = canary_inputs if technical else physical
    metadata = {"sha256": dataset_sha, "schema_version": all_cases[0]["schema_version"],
                "snapshot": "dataset.jsonl", "selection": "explicit", "task": "passages",
                "split": split, "selected_pools": len(selected), "physical_calls": len(inputs),
                "technical_only": technical}
    return payload, metadata, inputs, manifest, canary_inputs[0]


def pilot(args):
    payload, dataset, cases, passage_manifest, warmup_request = selected_inputs(args)
    output = args.output.absolute()
    allowed = ROOT / "results"
    require(not allowed.is_symlink() and output.resolve().is_relative_to(allowed.resolve())
            and not output.exists() and not output.is_symlink(), "upstream_pilot_new_local_output_required")
    model, source, binary = args.model.absolute(), args.source_root.resolve(strict=True), args.binary.absolute()
    require(not model.is_symlink(), "native_model_symlink_rejected")
    assets = json.loads(args.assets_manifest.read_bytes())
    shared.validate_assets(assets, model)
    envelope, preparation_cases, canary = execution_envelope(args, assets, model, cases)
    runtime = validated_runtime(source, binary, args.runtime_manifest)
    decision_type = getattr(args, "decision_type", "d3")
    prepared = preparation_map(args.preparation, preparation_cases, args.model_id, args.context, decision_type,
                               exact_cases=canary is not None)
    preparation_payload = calibration_payload = None
    if canary is not None:
        preparation_payload, _ = d327_preparation_receipt(getattr(args, "preparation_receipt", None), args.preparation, prepared)
        if args.phase == "canary":
            require(getattr(args, "calibration_receipt", None) is None, "d327_canary_must_precede_calibration_receipt")
        else:
            calibration_payload, _ = d327_calibration_receipt(getattr(args, "calibration_receipt", None), args.phase,
                args.max_seconds, preparation_payload, prepared, canary, runtime)
    before = memory_snapshot()
    require(before["MemAvailable_mib"] >= args.max_rss_mb + args.min_free_mb,
            "native_pilot_insufficient_available_memory_before_start")
    require(model.is_file() and model.stat().st_size == assets["files"][0]["size"]
            and digest(model) == assets["files"][0]["sha256"], "native_model_hash_mismatch")
    require(memory_snapshot()["MemAvailable_mib"] >= args.min_free_mb, "native_model_reserve_after_hash")
    # Fail before launch if another service owns this port; never discover/reuse it.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.port))
    output.mkdir(parents=True, exist_ok=False)
    (output / "dataset.jsonl").write_bytes(payload)
    if passage_manifest is not None:
        (output / "manifest.json").write_bytes(passage_manifest)
    shared.archive_bench_source(output / "bench-source.tar", payload)
    with tarfile.open(output / "bench-source.tar", "a") as archive:
        archive.add(Path(__file__), arcname="scripts/run-upstream-native-pilot.py", recursive=False)
        if canary is not None:
            for relative in ("docs/D3_27B_CAPABILITY_PROTOCOL_20261030.md", "plans/d3-27b-capability-v1.json"):
                archive.add(ROOT / relative, arcname=relative, recursive=False)
    shared.write_new(output / "native-preparation.json", prepared)
    shared.write_new(output / "runtime-pin.json", runtime)
    if canary is not None:
        (output / "preparation-receipt.json").write_bytes(preparation_payload)
        if calibration_payload is not None:
            (output / "calibration-receipt.json").write_bytes(calibration_payload)
    key = secrets.token_hex(32)
    # Only explicit CLI settings and this ephemeral key reach the owned server.
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith(("LLAMA_", "GATEWAY_")) and k != AUTH_ENV}
    environment["LLAMA_API_KEY"] = key
    command = [str(binary), "--model", str(model), "--alias", args.model_id,
        "--host", "127.0.0.1", "--port", str(args.port), "--ctx-size", str(args.context),
        "--batch-size", str(args.context), "--ubatch-size", str(args.context), "--parallel", "1",
        "--n-gpu-layers", "99", "--fit", "off", "--no-context-shift", "--no-warmup",
        "--no-webui", "--log-verbosity", "4"]
    shared.write_new(output / "launch.json", {"command": command, "key_transport": "ephemeral_environment_only"})
    process = watcher = None
    stop = threading.Event()
    guard = {"stop_reason": None, "rss_peak_mib": 0, "min_available_mib": before["MemAvailable_mib"]}
    previous = os.environ.get(AUTH_ENV)
    os.environ[AUTH_ENV] = key
    result = {"schema_version": "deposium.upstream-native-pilot/v1", "created_at": datetime.now(timezone.utc).isoformat(),
              "execution_scope": "isolated_upstream_llama_cpp_no_application_gateway", "dataset": dataset,
              "completed": False, "model_assets": assets, "runtime": runtime, "memory_before": before,
              "synthetic_control_calls_in_quality_denominator": False}
    if canary is not None:
        result["execution_envelope"] = envelope
    try:
        with (output / "engine.log").open("xb") as log:
            process = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            require(os.getpgid(process.pid) == process.pid, "upstream_process_group_not_owned")
            watcher = threading.Thread(target=shared.watch_resources,
                args=(process, stop, guard, output, args), daemon=True)
            watcher.start()
            deadline = time.monotonic() + 180
            while True:
                require(process.poll() is None and not guard["stop_reason"], "upstream_startup_stopped")
                try:
                    if http_request(args.port, "GET", "/health", None, key, 1)[0] == 200:
                        break
                except (OSError, TimeoutError):
                    pass
                require(time.monotonic() < deadline, "upstream_startup_timeout")
                time.sleep(.1)
            native_log = (output / "engine.log").read_text(errors="replace")
            offload = re.search(r"offloaded (\d+)/(\d+) layers to GPU", native_log)
            require(offload is not None and int(offload[1]) == int(offload[2]) > 0
                    and re.search(r"metal", native_log, re.I), "upstream_metal_offload_not_observed")
            native_type = "clef" if decision_type == "clef" else "vllm-d3"
            require("decision model type: " + native_type in native_log, "upstream_decision_type_not_observed")
            result["actual_backend"] = {"kind": "metal", "offloaded_layers": int(offload[1]),
                                        "total_layers": int(offload[2]), "decision_type": native_type}
            session = {"schema_version": "deposium.local-model-session/v1",
                "endpoint": f"http://127.0.0.1:{args.port}/v1/systemone",
                "model": {"repo_id": assets["repo_id"], "revision": assets["revision"],
                          "path": str(model), "sha256": assets["files"][0]["sha256"], "alias": args.model_id},
                "runtime": {"repository": REPOSITORY, "revision": PIN, "binary": str(binary),
                            "sha256": runtime["binary_sha256"], "backend_requested": "metal",
                            "decision_type": decision_type},
                "gateway": {"kind": "upstream_native_http_listener_no_application_gateway",
                            "binary": str(binary), "sha256": runtime["binary_sha256"]},
                "harness": {"path": str(Path(__file__)), "sha256": digest(__file__)},
                "runtime_pin": {"path": str(output / "runtime-pin.json"), "sha256": digest(output / "runtime-pin.json")},
                "native_preparation": {"path": str(output / "native-preparation.json"),
                                       "sha256": digest(output / "native-preparation.json")},
                "settings": {"context": args.context, "parallel": 1, "concurrency": 1,
                             "questions_per_call": 1, "truncation": "reject_in_pinned_native_engine"},
                "max_rss_mb": args.max_rss_mb, "pid": process.pid,
                "supervisor": {"pid": os.getpid(), "path": str(Path(__file__)), "sha256": digest(__file__)}}
            shared.write_new(output / "session.json", session)
            profile = {"schema_version": "deposium.candidate/v1", "profile_id": args.model_id + "-upstream-v1",
                "adapter": "systemone_local", "qualification": "model_isolated", "capabilities": ["bench.context-choice"],
                "revision": assets["revision"], "recordings": None, "timeout_seconds": 30,
                "model": {"endpoint": session["endpoint"], "model_id": args.model_id,
                    "repo_id": assets["repo_id"], "session_manifest": str(output / "session.json"),
                    "session_sha256": digest(output / "session.json"), "max_length": args.context,
                    "max_rss_mb": args.max_rss_mb, "credential_env": AUTH_ENV}}
            profile_path = output / "profile.json"
            shared.write_new(profile_path, profile)
            # Native auth and overflow, without claiming application routing guards.
            auth_status, _ = http_request(args.port, "POST", "/v1/systemone", b"{}", "", 5)
            require(auth_status == 401, "upstream_auth_not_enforced")
            oversized = overflow_input(args.context)
            body = native_request(oversized, args.model_id)[2]
            overflow_status, overflow = http_request(args.port, "POST", "/v1/systemone", body, key, 10)
            require(overflow_status in {400, 413, 422} or
                    (overflow_status == 500 and native_overflow(overflow, args.context)),
                    "upstream_overflow_not_rejected")
            shared.write_new(output / "guard-controls.json", {"unauthenticated_status": auth_status,
                "overflow_status": overflow_status, "overflow_response": json.loads(overflow)})
            # Use a prepared calibration input as technical warm-up; not extra quality data.
            adapter = LocalSystemOneAdapter(profile, profile_path)
            try:
                smoke = adapter.predict({"contract_id": "bench.context-choice", "input": warmup_request["input"]})
                shared.write_new(output / "warmup.json", smoke)
                require(smoke["status"] == "ok", "upstream_prepared_warmup_failed")
            finally:
                adapter.close()
            with native_supervision(profile_path, process=process, watcher=watcher, stop=stop,
                    guard=guard, max_rss_mb=args.max_rss_mb, min_free_mb=args.min_free_mb) as scope:
                def stopped():
                    try:
                        scope.check(profile, profile_path)
                    except NativeSupervisionError:
                        guard["stop_reason"] = guard["stop_reason"] or "native_supervision_lost"
                        return True
                    return False
                if passage_manifest is None:
                    summary = run_campaign(output / "dataset.jsonl", profile_path, output / "campaign",
                                           stop_requested=stopped)
                    result["campaign_coverage"] = shared.dataset_coverage(summary, len(cases))
                    result["completed"] = (result["campaign_coverage"]["collection_complete"]
                                           and result["campaign_coverage"]["scored_cases"] > 0)
                elif dataset["technical_only"]:
                    adapter = LocalSystemOneAdapter(profile, profile_path)
                    observed = 0
                    try:
                        with (output / "technical-calls.jsonl").open("xb") as calls:
                            for request in cases:
                                require(not stopped(), "native_passage_canary_supervision_lost")
                                response = adapter.predict(request)
                                calls.write((json.dumps({"call_id": request["case_id"], "response": response},
                                    ensure_ascii=False, allow_nan=False) + "\n").encode())
                                calls.flush()
                                os.fsync(calls.fileno())
                                require(response["status"] == "ok", "native_passage_canary_invalid_output")
                                observed += 1
                    finally:
                        adapter.close()
                    result["technical_coverage"] = {"valid_calls": observed, "planned_calls": len(cases),
                                                    "quality_cases_scored": 0, "quality_gate": False}
                    result["completed"] = observed == len(cases) and not stopped()
                else:
                    from deposium_bench.passage_observation import observe_choice
                    summary = observe_choice(profile_path, output / "campaign", split=dataset["split"],
                                             max_seconds=args.max_seconds, dataset_path=output / "dataset.jsonl")
                    result["passage_coverage"] = {key: summary[key] for key in (
                        "completion_status", "stop_reason", "selected_cases", "logical_decisions",
                        "physical_planned", "physical_attempted", "physical_statuses", "logical_statuses", "scores")}
                    result["completed"] = (summary["completion_status"] == "complete"
                        and summary["physical_attempted"] == summary["physical_planned"] and not stopped())
            result["completed"] = result["completed"] and not guard["stop_reason"]
    except BaseException as exc:
        result["error_kind"] = type(exc).__name__
        message = str(exc)
        result["failure_code"] = message if re.fullmatch(r"[a-z0-9_]{1,150}", message) else "upstream_pilot_exception"
        raise
    finally:
        try:
            shared.finish_owned(process, watcher, stop)
        finally:
            if previous is None:
                os.environ.pop(AUTH_ENV, None)
            else:
                os.environ[AUTH_ENV] = previous
        result["resources"] = guard
        result["memory_after"] = memory_snapshot()
        result["completed"] = result["completed"] and guard["stop_reason"] is None
        if process is not None:
            result["native_exit_code"] = process.returncode
        shared.write_new(output / "pilot.json", result)
        shared.write_new(output / "pilot-seal.json", {"schema_version": "deposium.native-pilot-seal/v1",
            "files": {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-root", "binary", "runtime-manifest", "model", "assets-manifest", "preparation", "dataset", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--decision-type", choices=("d3", "clef"), default="d3")
    parser.add_argument("--execution-envelope", choices=(DEFAULT_ENVELOPE, D327_ENVELOPE), default=DEFAULT_ENVELOPE)
    parser.add_argument("--phase", choices=("canary", "anchor", "capability"))
    parser.add_argument("--preparation-receipt", type=Path)
    parser.add_argument("--calibration-receipt", type=Path)
    parser.add_argument("--task", choices=("choices", "passages"), default="choices")
    parser.add_argument("--passage-split", choices=("calibration", "test"), default="test")
    parser.add_argument("--technical-only", action="store_true")
    parser.add_argument("--port", type=int, default=11438)
    parser.add_argument("--context", type=int, default=4096)
    parser.add_argument("--max-rss-mb", type=int, default=18432)
    parser.add_argument("--min-free-mb", type=int, default=8192)
    parser.add_argument("--max-seconds", type=int, default=600)
    args = parser.parse_args(argv)
    try:
        result = pilot(args)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
        print("Upstream pilot stopped; inspect the new ignored archive if created.", file=sys.stderr)
        return 2
    print(json.dumps({"completed": result["completed"], "coverage": result.get("campaign_coverage")
                      or result.get("technical_coverage") or result.get("passage_coverage"),
                      "actual_backend": result["actual_backend"], "resources": result["resources"]}))
    return 0 if result["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
