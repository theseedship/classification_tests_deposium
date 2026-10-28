#!/usr/bin/env python3
"""Explicit, supervised one-model pilot through the real inference gateway.

No weights are downloaded. CLI and notebook use the same campaign functions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import tarfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from deposium_bench.campaigns import run_campaign
from deposium_bench.mastra_observation import observe_local
from deposium_bench.native_resources import memory_snapshot, process_group_rss_mib
from deposium_bench.native_supervision import native_supervision
from deposium_bench.systemone_local import AUTH_ENV, LocalSystemOneAdapter, digest, http_request, native_overflow


def write_new(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def stop_owned(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGINT)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)


def finish_owned(process, watcher, stop):
    """Close the resource writer before callers fingerprint any archive file."""
    stop.set()
    try:
        if watcher is not None:
            # Captures and process waits have their own timeouts. A bounded join
            # could leave this writer running after pilot-seal.json is written.
            watcher.join()
    finally:
        if process is not None:
            stop_owned(process)


def validate_assets(assets, model):
    """Reject malformed provenance before reading weights or loading a model."""
    if (not isinstance(assets, dict)
            or assets.get("schema_version") != "deposium.model-assets/v1"
            or not isinstance(assets.get("repo_id"), str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", assets["repo_id"])
            or not isinstance(assets.get("revision"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", assets["revision"])
            or not isinstance(assets.get("files"), list) or len(assets["files"]) != 1):
        raise ValueError("native_pilot_model_identity_invalid")
    entry = assets["files"][0]
    if (not isinstance(entry, dict) or entry.get("path") != model.name
            or type(entry.get("size")) is not int or entry["size"] <= 0
            or not isinstance(entry.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])):
        raise ValueError("native_pilot_model_identity_invalid")


def watch_resources(process, stop, guard, output, args):
    started = time.monotonic()
    with (output / "resources.jsonl").open("x") as samples:
        while not stop.is_set() and process.poll() is None:
            try:
                memory = memory_snapshot()
                rss = process_group_rss_mib(process.pid)
                guard["rss_peak_mib"] = max(guard["rss_peak_mib"], rss)
                guard["min_available_mib"] = min(guard["min_available_mib"], memory["MemAvailable_mib"])
                samples.write(json.dumps({"elapsed_seconds": time.monotonic() - started,
                    "process_group_rss_mib": rss, "memory": memory}) + "\n")
                samples.flush()
                reason = ("rss_guard" if rss > args.max_rss_mb else
                          "host_memory_guard" if memory["MemAvailable_mib"] < args.min_free_mb else
                          "wall_budget" if time.monotonic() - started > args.max_seconds else None)
                if reason:
                    guard["stop_reason"] = reason
                    stop_owned(process)
                    return
                guard["last_observed_monotonic"] = time.monotonic()
            except (OSError, ValueError, subprocess.SubprocessError):
                guard["stop_reason"] = "resource_observation_failed"
                if process.poll() is None:
                    stop_owned(process)
                return
            stop.wait(.25)


def pilot(args):
    # Complete validation before creating an archive or starting a service.
    service = args.service_root.expanduser().resolve(strict=True)
    stack = args.stack_root.expanduser().resolve(strict=True)
    output = args.output.expanduser().resolve()
    if any(output.is_relative_to(root) for root in (service, stack)):
        raise ValueError("native_pilot_output_must_be_outside_application_stack")
    model = args.model.expanduser().resolve(strict=True)
    assets = json.loads(args.assets_manifest.read_text())
    validate_assets(assets, model)
    # Check admission before hashing weights warms the filesystem cache. Pages
    # read here belong to the forthcoming model budget, not a second model.
    before = memory_snapshot()
    if before["MemAvailable_mib"] < args.max_rss_mb + args.min_free_mb:
        raise ValueError("native_pilot_insufficient_available_memory_before_start")
    if (model.is_symlink()
            or model.stat().st_size != assets["files"][0]["size"]
            or digest(model) != assets["files"][0]["sha256"]):
        raise ValueError("native_pilot_model_identity_invalid")
    if memory_snapshot()["MemAvailable_mib"] < args.min_free_mb:
        raise ValueError("native_pilot_insufficient_reserve_after_asset_verification")
    if args.port == args.subprocess_port:
        raise ValueError("native_pilot_ports_must_differ")
    helper = service / "scripts/local-inference.py"
    spec = importlib.util.spec_from_file_location("deposium_native_launcher", helper)
    local = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(local)
    pin = local.read_pin(args.runtime)
    runtime = local.verified_runtime(local.runtime_dir(service / ".local/llama", pin, args.backend),
                                     pin, args.backend)
    gateway = service / "target/debug/deposium-inference"
    if not gateway.is_file() or not os.access(gateway, os.X_OK):
        raise FileNotFoundError("native_pilot_gateway_missing")
    output.mkdir(parents=True, exist_ok=False)
    with tarfile.open(output / "bench-source.tar", "x") as archive:
        for path in sorted((ROOT / "deposium_bench").rglob("*.py")):
            archive.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
        for path in sorted((ROOT / "schemas").glob("*.json")):
            archive.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
        archive.add(__file__, arcname="scripts/run-native-pilot.py", recursive=False)
    with tarfile.open(output / "service-source.tar", "x") as archive:
        selected = list((service / "src").rglob("*.rs")) + [helper, service / "Cargo.toml",
            service / "Cargo.lock", service / "rust-toolchain.toml",
            service / "config" / ("llama-" + args.runtime + ".lock.json")]
        for path in sorted(selected):
            archive.add(path, arcname=str(path.relative_to(service)), recursive=False)
    text = local.catalog_text(model, args.model_id, runtime["binary"], args.backend, args.context,
                              "decision", runtime=args.runtime)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("extra_args = "):
            extra = json.loads(line[len("extra_args = "):])
            extra += ["--log-verbosity", "4", "--log-file", str(output / "engine.log")]
            lines[i] = "extra_args = " + json.dumps(extra)
    config = output / "models.toml"
    config.write_text("\n".join(lines) + "\n")
    key = secrets.token_hex(32)
    child_env = local.local_environment(config, model.parent, args.port, args.subprocess_port,
                                        {**os.environ, "GATEWAY_API_KEY": key})
    # Scoped to this process; never written to arguments, profiles or archives.
    previous_key = os.environ.get(AUTH_ENV)
    os.environ[AUTH_ENV] = key
    guard_stop = threading.Event()
    guard = {"stop_reason": None, "rss_peak_mib": 0, "min_available_mib": before["MemAvailable_mib"]}
    process = None
    watcher = None
    result = {"schema_version": "deposium.native-pilot/v1", "created_at": datetime.now(timezone.utc).isoformat(),
              "model_assets": assets, "runtime": runtime, "memory_before": before,
              "completed": False, "smoke_cases_scored": 0, "campaigns": {},
              "budget": {"rss_guard_mib": args.max_rss_mb, "min_available_mib": args.min_free_mb,
                         "max_seconds": args.max_seconds, "sample_interval_seconds": .25},
              "limitations": ["Model-only tests; no tool or product path.",
                "Host available memory on macOS is a reclaimable-page estimate.",
                "Process-group RSS is not a measurement of all unified GPU allocations.",
                "One slot, one question per call, sequential; concurrent D3 batching unqualified.",
                "Campaigns follow an archived synthetic warm-up; latency is not a cold-start measure."]}
    try:
        with (output / "gateway.log").open("x") as log:
            process = subprocess.Popen([str(gateway)], cwd=service, env=child_env,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            if os.getpgid(process.pid) != process.pid:
                raise ValueError("native_pilot_process_group_not_owned")

            watcher = threading.Thread(target=watch_resources,
                args=(process, guard_stop, guard, output, args), daemon=True)
            watcher.start()
            deadline = time.monotonic() + 180
            while True:
                if process.poll() is not None or guard["stop_reason"]:
                    raise RuntimeError("native_pilot_gateway_exited_before_readiness")
                try:
                    status, _ = http_request(args.port, "GET", "/health", None, key, 1)
                    if status == 200:
                        break
                except (OSError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError("native_pilot_startup_timeout")
                time.sleep(.1)
            session = {"schema_version": "deposium.local-model-session/v1",
                "endpoint": "http://127.0.0.1:%d/v1/systemone" % args.port,
                "model": {"repo_id": assets["repo_id"], "revision": assets["revision"],
                          "path": str(model), "sha256": assets["files"][0]["sha256"], "alias": args.model_id},
                "runtime": {"repository": pin["repository"], "revision": pin["revision"],
                            "binary": runtime["binary"], "sha256": runtime["binary_sha256"],
                            "backend_requested": args.backend},
                "gateway": {"binary": str(gateway), "sha256": digest(gateway)},
                "harness": {"path": str(helper), "sha256": digest(helper)},
                "runtime_pin": {"path": str(service / "config" / ("llama-" + args.runtime + ".lock.json")),
                    "sha256": digest(service / "config" / ("llama-" + args.runtime + ".lock.json"))},
                "settings": {"context": args.context, "parallel": 1, "concurrency": 1,
                             "questions_per_call": 1, "truncation": "reject_in_pinned_native_engine"},
                "max_rss_mb": args.max_rss_mb, "pid": process.pid,
                "supervisor": {"pid": os.getpid(), "path": str(Path(__file__).resolve()),
                               "sha256": digest(__file__)}}
            session_path = output / "session.json"
            write_new(session_path, session)
            profile = {"schema_version": "deposium.candidate/v1", "profile_id": args.model_id + "-native-v1",
                "adapter": "systemone_local", "qualification": "model_isolated", "capabilities": ["bench.context-choice"],
                "revision": assets["revision"], "recordings": None, "timeout_seconds": 30,
                "model": {"endpoint": session["endpoint"], "model_id": args.model_id,
                    "repo_id": assets["repo_id"], "session_manifest": str(session_path),
                    "session_sha256": digest(session_path), "max_length": args.context,
                    "max_rss_mb": args.max_rss_mb, "credential_env": AUTH_ENV}}
            profile_path = output / "profile.json"
            write_new(profile_path, profile)
            adapter = LocalSystemOneAdapter(profile, profile_path)
            try:
                smoke = adapter.predict({"contract_id": "bench.context-choice", "input": {
                    "context": "A customer says that the same order was charged twice.",
                    "question": "Which team should review the request?", "options": [
                        {"id": "synthetic-billing", "description": "Payments, charges and refunds"},
                        {"id": "synthetic-shipping", "description": "Shipment location and delivery dates"}]}})
                write_new(output / "smoke.json", smoke)
                if smoke["status"] != "ok":
                    raise RuntimeError("native_pilot_model_smoke_failed")
                # Exercise empty-body auth rejection and wrong-kind/unknown-model guards.
                checks = []
                for path, body, auth, expected in (
                    ("/v1/systemone", {"model": args.model_id}, "", 401),
                    ("/v1/chat/completions", {"model": args.model_id, "messages": []}, key, 400),
                    ("/v1/systemone", {"model": "unknown-native-pilot-model"}, key, 404)):
                    status, _ = http_request(args.port, "POST", path, json.dumps(body).encode(), auth, 5)
                    checks.append({"path": path, "status": status, "expected": expected})
                    if status != expected:
                        raise RuntimeError("native_pilot_guard_smoke_failed")
                write_new(output / "guard-smoke.json", checks)
                oversized = {"model": args.model_id, "state": "sentinel " * (args.context + 512),
                    "questions": {"answer": {"type": "choice", "instructions": "Choose an option.",
                        "criteria": {"c0": "First option", "c1": "Second option"}}}}
                status, raw_overflow = http_request(args.port, "POST", "/v1/systemone",
                    json.dumps(oversized).encode(), key, 10)
                write_new(output / "overflow-smoke.json", {"status": status,
                    "state_words": args.context + 512, "context": args.context,
                    "response": raw_overflow.decode("utf-8", errors="replace")})
                if status not in {400, 413, 422} and not (status == 500 and native_overflow(raw_overflow, args.context)):
                    raise RuntimeError("native_pilot_native_overflow_not_rejected")
            finally:
                adapter.close()
            if not args.smoke_only:
                base = run_campaign(ROOT / "datasets/context-choice-v1/cases.jsonl", profile_path,
                                    output / "bases", stack_root=args.stack_root)
                result["campaigns"]["bases"] = base
                if (base["completion_status"] != "complete" or base["metrics"]["total_cases"] != 132
                        or base["metrics"]["counts_by_status"]["ok"] != 132
                        or base["metrics"]["scored_cases"] != 132):
                    raise RuntimeError("native_pilot_base_coverage_incomplete")
                if guard["stop_reason"]:
                    raise RuntimeError("native_pilot_resource_guard")
                with native_supervision(profile_path, process=process, watcher=watcher,
                        stop=guard_stop, guard=guard, max_rss_mb=args.max_rss_mb,
                        min_free_mb=args.min_free_mb):
                    mastra = observe_local(ROOT / "datasets/mastra-read-pilot-v0/cases.jsonl", profile_path,
                                           output / "mastra", stack_root=args.stack_root)
                result["campaigns"]["mastra"] = mastra
                if (mastra["completion_status"] != "complete"
                        or mastra["metrics"]["coverage"]["valid_decisions"] != 24):
                    raise RuntimeError("native_pilot_mastra_coverage_incomplete")
            result["completed"] = not guard["stop_reason"]
    finally:
        try:
            finish_owned(process, watcher, guard_stop)
        finally:
            if previous_key is None:
                os.environ.pop(AUTH_ENV, None)
            else:
                os.environ[AUTH_ENV] = previous_key
        if process is not None:
            result["gateway_exit_code"] = process.returncode
        result["resources"] = guard
        result["memory_after"] = memory_snapshot()
        write_new(output / "pilot.json", result)
        files = {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}
        write_new(output / "pilot-seal.json", {"schema_version": "deposium.native-pilot-seal/v1", "files": files})
    print(json.dumps({"output": str(output), "completed": result["completed"], "resources": guard}, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service-root", type=Path, required=True)
    parser.add_argument("--stack-root", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--assets-manifest", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", choices=("decision2", "d3"), default="d3")
    parser.add_argument("--backend", choices=("metal", "cpu", "cuda"), required=True)
    parser.add_argument("--context", type=int, default=4096)
    parser.add_argument("--port", type=int, default=11438)
    parser.add_argument("--subprocess-port", type=int, default=18480)
    parser.add_argument("--max-rss-mb", type=int, default=20480)
    parser.add_argument("--min-free-mb", type=int, default=8192)
    parser.add_argument("--max-seconds", type=int, default=1200)
    parser.add_argument("--smoke-only", action="store_true")
    args = parser.parse_args(argv)
    if (not 128 <= args.context <= 32768 or not 1024 <= args.port <= 65535
            or not 1024 <= args.subprocess_port <= 65535 or not 256 <= args.max_rss_mb <= 49152
            or not 2048 <= args.min_free_mb <= 16384 or not 1 <= args.max_seconds <= 1800):
        parser.error("invalid explicit resource limits")
    pilot(args)


if __name__ == "__main__":
    main()
