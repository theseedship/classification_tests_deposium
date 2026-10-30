#!/usr/bin/env python3
"""Explicit, bounded local JSON-policy canary; no work or services on import."""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from http.client import HTTPException
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
from deposium_bench import local_tool_policy as local
from deposium_bench.campaigns import _decode, run_campaign
from deposium_bench.cases import parse_cases, typed_equal
from deposium_bench.native_resources import memory_snapshot
from deposium_bench.native_supervision import native_supervision, NativeSupervisionError
from deposium_bench.synthetic_tools import canonical
from deposium_bench.systemone_local import AUTH_ENV, digest, http_request

SPEC = importlib.util.spec_from_file_location("tool_policy_upstream", ROOT / "scripts/run-upstream-native-pilot.py")
upstream = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upstream)
shared = upstream.shared

MODEL_ID = "qwen3-4b-instruct-q8-tool-policy-v1"
# A frozen public dataset manifest binds the exact case bytes, counts, splits and
# contracts before any prediction. The launcher pins each admitted manifest's
# own bytes here, so an edited or untracked manifest (even a self-consistent
# one) is refused; freezing another pack is a reviewed launcher change.
MANIFEST_VERSIONS = {"deposium.tool-policy-canary-manifest/v1", "deposium.tool-policy-heldout-manifest/v1"}
FROZEN_MANIFESTS = {
    "datasets/tool-policy-canary-v1/manifest.json": "86dc93ddca375b89cb74c186dae6e3bd6d990110d3d641817e3c5f9006e5e4bc",
    "datasets/tool-policy-heldout-v1/manifest.json": "c57545613997e21a804a5587bda7a20819d3b436ea9b3d15e2d40b686ec639ed",
}
HELDOUT_PROTOCOL = "docs/LOCAL_TOOL_POLICY_HELDOUT_PROTOCOL_20261030.md"
CACHE_AMENDMENT = "docs/LOCAL_TOOL_POLICY_PROMPT_CACHE_AMENDMENT_20261030.md"
ASSETS = {"schema_version": "deposium.model-assets/v1", "repo_id": "unsloth/Qwen3-4B-Instruct-2507-GGUF",
    "revision": "a06e946bb6b655725eafa393f4a9745d460374c9", "files": [{
        "path": "Qwen3-4B-Instruct-2507-Q8_0.gguf", "size": 4280405600,
        "sha256": "391c1e410fd9f4cf2de2b510273b56a84c19ce18f4fa3bfb3774031dac4ef068"}]}
SETTINGS = {"model_id": MODEL_ID, "max_length": 4096, "max_output_tokens": 256,
            "seed": 42, "prompt_version": local.PROMPT_VERSION}
ENVELOPE = {"context": 4096, "batch": 4096, "microbatch": 4096, "parallel": 1,
    "request_concurrency": 1, "rss_limit_mib": 8192, "reserve_mib": 8192,
    "admission_available_mib": 16384, "max_session_seconds": 600, "per_call_seconds": 20,
    "automatic_http_retries": 0, "backend_fallback": False,
    # The pinned server keeps a host prompt cache of 8,192 MiB by default and
    # grows toward it on every task; requests never reuse it (cache_prompt is
    # false), so it is disabled. Attempts before the dated amendment ran with
    # the default and are recorded as such in their archives.
    "host_prompt_cache_mib": 0}


def require(value, code):
    if not value:
        raise ValueError(code)


def regular(path, maximum):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum,
            "local_policy_input_missing_or_unbounded")


def frozen_dataset(manifest_path, dataset_path):
    """Bind the dataset bytes to a tracked frozen manifest; refuse any other inventory."""
    regular(manifest_path, 1024 * 1024)
    require(not manifest_path.is_symlink() and manifest_path.resolve().is_relative_to(ROOT.resolve()),
            "local_policy_manifest_outside_checkout")
    relative = str(manifest_path.resolve().relative_to(ROOT.resolve()))
    manifest_bytes = manifest_path.read_bytes()
    require(FROZEN_MANIFESTS.get(relative) == hashlib.sha256(manifest_bytes).hexdigest(),
            "local_policy_manifest_not_frozen")
    manifest = _decode(manifest_bytes)
    fields = ("schema_version", "dataset_id", "cases_sha256", "case_count", "family_count",
              "counts_by_split", "counts_by_contract", "status")
    require(isinstance(manifest, dict) and all(k in manifest for k in fields)
            and manifest["schema_version"] in MANIFEST_VERSIONS
            and manifest["status"] == "frozen_before_first_candidate_prediction",
            "local_policy_dataset_manifest_invalid")
    regular(dataset_path, 2 * 1024 * 1024)
    payload = dataset_path.read_bytes()
    require(hashlib.sha256(payload).hexdigest() == manifest["cases_sha256"], "local_policy_frozen_dataset_mismatch")
    cases, _ = parse_cases(payload)
    splits = {s: sum(c["split"] == s for c in cases) for s in ("train", "calibration", "test")}
    contracts = {k: sum(c["contract_id"] == k for c in cases) for k in local.CONTRACTS}
    require(len(cases) == manifest["case_count"] > 0
            and len({c["translation_family"] for c in cases}) == manifest["family_count"]
            and typed_equal(splits, manifest["counts_by_split"])
            and typed_equal({k: v for k, v in contracts.items() if v}, manifest["counts_by_contract"])
            and all(c["contract_id"] in local.CONTRACTS for c in cases),
            "local_policy_dataset_inventory_mismatch")
    info = {"dataset_id": manifest["dataset_id"], "manifest": relative,
            "manifest_sha256": FROZEN_MANIFESTS[relative], "sha256": manifest["cases_sha256"], "cases": len(cases),
            "families": manifest["family_count"], "counts_by_split": splits, "counts_by_contract": contracts}
    return payload, cases, info


def selected_inputs(args):
    payload, cases, dataset = frozen_dataset(args.dataset_manifest, args.dataset)
    regular(args.assets_manifest, 1024 * 1024)
    assets = _decode(args.assets_manifest.read_bytes())
    require(typed_equal(assets, ASSETS), "local_policy_exact_qwen_assets_required")
    model = args.model.absolute()
    require(not model.is_symlink() and model.name == ASSETS["files"][0]["path"], "local_policy_model_path_invalid")
    return payload, cases, assets, model, dataset


def technical_body(model=MODEL_ID, oversized=False):
    # Separate synthetic protocol control; never a scored dataset input.
    prompt = "sentinel " * 8192 if oversized else "Return the object required by the response schema."
    return {"model": model, "messages": [{"role": "system", "content": "Return one JSON value."},
        {"role": "user", "content": prompt}], "response_format": {"type": "json_schema", "json_schema": {
            "name": "technical_control", "strict": True, "schema": {"type": "object",
                "properties": {"ready": {"type": "boolean", "const": True}}, "required": ["ready"],
                "additionalProperties": False}}}, "temperature": 0, "top_p": 1, "top_k": 0,
        "repeat_penalty": 1, "seed": 42, "max_tokens": 256, "stream": False, "n": 1, "cache_prompt": False}


def observed_json(data, key):
    require(not local.credential_in_response(data, key), "local_policy_response_credential_redacted")
    return _decode(data)


def pilot(args):
    payload, cases, assets, model, dataset = selected_inputs(args)
    require(type(args.port) is int and 1024 <= args.port <= 65535, "local_policy_port_invalid")
    output = args.output.absolute()
    allowed = ROOT / "results"
    require(not allowed.is_symlink() and output.resolve().is_relative_to(allowed.resolve())
            and not output.exists() and not output.is_symlink(), "local_policy_new_ignored_output_required")
    source, binary = args.source_root.resolve(strict=True), args.binary.absolute()
    runtime = upstream.validated_runtime(source, binary, args.runtime_manifest)
    output.mkdir(parents=True, exist_ok=False)
    (output / "dataset.jsonl").write_bytes(payload)
    shared.archive_bench_source(output / "bench-source.tar", payload)
    with tarfile.open(output / "bench-source.tar", "a") as archive:
        archive.add(Path(__file__), arcname="scripts/run-local-tool-policy-pilot.py", recursive=False)
        archive.add(Path(upstream.__file__), arcname="scripts/run-upstream-native-pilot.py", recursive=False)
        for relative in ("native/systemone-preflight.cpp", "docs/LOCAL_TOOL_POLICY_NATIVE_PROTOCOL_20261030.md",
                         HELDOUT_PROTOCOL, CACHE_AMENDMENT, "docs/LOCAL_TOOL_POLICY_V1.md", dataset["manifest"],
                         "profiles/qwen3-4b-instruct-q8-assets.json"):
            archive.add(ROOT / relative, arcname=relative, recursive=False)
    shared.write_new(output / "runtime-pin.json", runtime)
    result = {"schema_version": "deposium.local-tool-policy-pilot/v1",
        "created_at": datetime.now(timezone.utc).isoformat(), "execution_scope": "isolated_upstream_generated_tool_proposals",
        "status": "not_run", "collection_complete": False, "scored_cases": 0, "total_cases": dataset["cases"],
        "quality_verdict": "not_run", "model_assets": assets, "runtime": runtime, "envelope": ENVELOPE,
        "dataset": dataset, "prompt_version": local.PROMPT_VERSION,
        "technical_controls_in_quality_denominator": False, "technical_controls": [],
        "weight_verification": "not_run", "memory_before": None, "memory_after": None}
    process = watcher = None
    owned_group = False
    stop = threading.Event()
    guard = {"stop_reason": None, "rss_peak_mib": 0, "min_available_mib": None}
    previous = os.environ.get(AUTH_ENV)
    key = None
    try:
        before = memory_snapshot()
        require(isinstance(before, dict) and type(before.get("MemAvailable_mib")) in (int, float)
                and math.isfinite(before["MemAvailable_mib"]) and before["MemAvailable_mib"] >= 0,
                "local_policy_memory_observation_invalid")
        result["memory_before"] = before
        guard["min_available_mib"] = before["MemAvailable_mib"]
        admitted = before["MemAvailable_mib"] >= 16384
        shared.write_new(output / "preflight.json", {"schema_version": "deposium.local-tool-policy-preflight/v1",
            "model_id": MODEL_ID, "dataset_sha256": dataset["sha256"], "envelope": ENVELOPE,
            "available_mib": before["MemAvailable_mib"], "admitted": admitted,
            "weight_hash_performed": False, "model_loaded": False, "campaign_cases_scored": 0})
        if not admitted:
            result["stop_reason"] = "insufficient_available_memory"
            return result
        # Probe before model I/O. Never attach to a pre-existing service.
        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", args.port))
        except OSError:
            raise ValueError("local_policy_port_unavailable") from None
        require(model.is_file() and model.stat().st_size == assets["files"][0]["size"], "local_policy_model_size_mismatch")
        before_stat = model.stat()
        before_state = (before_stat.st_dev, before_stat.st_ino, before_stat.st_size,
                        before_stat.st_mtime_ns, before_stat.st_ctime_ns)
        result["weight_verification"] = "hash_started"
        require(digest(model) == assets["files"][0]["sha256"], "local_policy_model_hash_mismatch")
        after_stat = model.stat()
        require(not model.is_symlink()
                and (after_stat.st_dev, after_stat.st_ino, after_stat.st_size,
                     after_stat.st_mtime_ns, after_stat.st_ctime_ns) == before_state,
                "local_policy_model_changed_during_hash")
        result["weight_verification"] = "verified"
        require(memory_snapshot()["MemAvailable_mib"] >= 8192, "local_policy_reserve_after_hash")
        key = secrets.token_hex(32)
        environment = {name: os.environ[name] for name in ("PATH", "LANG", "LC_ALL", "TZ", "TMPDIR") if name in os.environ}
        environment["LLAMA_API_KEY"] = key
        os.environ[AUTH_ENV] = key
        command = [str(binary), "--model", str(model), "--alias", MODEL_ID, "--host", "127.0.0.1",
            "--port", str(args.port), "--ctx-size", "4096", "--batch-size", "4096", "--ubatch-size", "4096",
            "--parallel", "1", "--n-gpu-layers", "99", "--jinja", "--fit", "off", "--no-context-shift",
            "--no-warmup", "--no-webui", "--cache-ram", str(ENVELOPE["host_prompt_cache_mib"]), "--log-verbosity", "4"]
        shared.write_new(output / "launch.json", {"command": command, "credential_transport": "ephemeral_environment_only"})
        envelope_args = argparse.Namespace(max_rss_mb=8192, min_free_mb=8192, max_seconds=600)
        with (output / "engine.log").open("xb") as log:
            process = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            result["status"] = "technical_preparation"
            require(os.getpgid(process.pid) == process.pid and process.pid != os.getpgrp(), "local_policy_process_group_not_owned")
            owned_group = True
            watcher = threading.Thread(target=shared.watch_resources, args=(process, stop, guard, output, envelope_args), daemon=True)
            watcher.start()
            deadline = time.monotonic() + 180
            result["startup_health_attempts"] = 0
            while True:
                require(process.poll() is None and guard["stop_reason"] is None, "local_policy_startup_stopped")
                result["startup_health_attempts"] += 1
                try:
                    if http_request(args.port, "GET", "/health", None, key, 1)[0] == 200 and guard.get("last_observed_monotonic") is not None:
                        break
                except (OSError, HTTPException, TimeoutError):
                    pass
                require(time.monotonic() < deadline, "local_policy_startup_timeout")
                time.sleep(.1)
            native_log = (output / "engine.log").read_text(errors="replace")
            offload = re.search(r"offloaded (\d+)/(\d+) layers to GPU", native_log)
            require(offload is not None and int(offload[1]) == int(offload[2]) > 0
                    and re.search(r"metal", native_log, re.I), "local_policy_full_metal_offload_required")
            result["actual_backend"] = {"kind": "metal", "offloaded_layers": int(offload[1]), "total_layers": int(offload[2])}
            # Verify the effect in the owned log, as for Metal: the flag alone is not evidence.
            require(re.search(r"prompt cache is disabled", native_log) is not None
                    and re.search(r"prompt cache is enabled", native_log) is None, "local_policy_host_prompt_cache_not_disabled")
            result["host_prompt_cache"] = "disabled_observed_in_native_log"

            def control(name, method, path, body, credential, scope=None):
                if scope is not None:
                    scope.check(profile, profile_path)
                receipt = {"name": name, "method": method, "path": path, "http_attempted": True,
                    "http_status": None, "request_sha256": hashlib.sha256(body).hexdigest() if body is not None else None,
                    "response_sha256": None, "response_base64": None, "response_redacted": False}
                try:
                    status, data = http_request(args.port, method, path, body, credential, 20)
                    receipt.update(http_status=status, response_sha256=hashlib.sha256(data).hexdigest())
                    receipt["response_redacted"] = local.credential_in_response(data, key)
                    if not receipt["response_redacted"]:
                        receipt["response_base64"] = base64.b64encode(data).decode("ascii")
                except (OSError, HTTPException, TimeoutError, ValueError) as exc:
                    receipt["error_kind"] = type(exc).__name__
                    raise ValueError("local_policy_control_transport_failed") from None
                finally:
                    result["technical_controls"].append(receipt)
                require(not receipt["response_redacted"], "local_policy_response_credential_redacted")
                if scope is not None:
                    scope.check(profile, profile_path)
                return status, data

            status, data = control("authenticated_props", "GET", "/props", None, key)
            require(status == 200, "local_policy_props_failed")
            props = observed_json(data, key)
            template = props.get("chat_template")
            require(props.get("model_alias") == MODEL_ID and props.get("total_slots") == 1
                    and props.get("default_generation_settings", {}).get("n_ctx") == 4096
                    and isinstance(props.get("model_ftype"), str) and re.fullmatch(r"Q8_0(?:\s.*)?", props["model_ftype"]) is not None
                    and isinstance(template, str) and 0 < len(template.encode("utf-8")) <= 128 * 1024,
                    "local_policy_native_metadata_invalid")
            (output / "chat-template.jinja").write_bytes(template.encode("utf-8"))
            (output / "native-props.json").write_bytes(data)
            session = {"schema_version": local.SESSION_VERSION, "endpoint": f"http://127.0.0.1:{args.port}/v1/chat/completions",
                "model": {"repo_id": assets["repo_id"], "revision": assets["revision"], "path": str(model),
                    "sha256": assets["files"][0]["sha256"], "alias": MODEL_ID, "size": assets["files"][0]["size"], "quantization": "Q8_0"},
                "runtime": {"repository": upstream.REPOSITORY, "revision": upstream.PIN, "binary": str(binary),
                    "sha256": runtime["binary_sha256"], "backend_requested": "metal"},
                "harness": {"path": str(Path(__file__)), "sha256": digest(__file__)},
                "runtime_pin": {"path": str(output / "runtime-pin.json"), "sha256": digest(output / "runtime-pin.json")},
                "template": {"path": str(output / "chat-template.jinja"), "sha256": digest(output / "chat-template.jinja")},
                "settings": {**SETTINGS, "parallel": 1, "concurrency": 1, "truncation": "reject_in_pinned_native_engine"},
                "max_rss_mb": 8192, "pid": process.pid,
                "supervisor": {"pid": os.getpid(), "path": str(Path(__file__)), "sha256": digest(__file__)}}
            shared.write_new(output / "session.json", session)
            profile = {"schema_version": "deposium.candidate/v1", "profile_id": MODEL_ID,
                "adapter": local.ADAPTER, "qualification": "model_isolated", "capabilities": list(local.CONTRACTS),
                "revision": assets["revision"], "recordings": None, "timeout_seconds": 20,
                "model": {"endpoint": session["endpoint"], **SETTINGS, "repo_id": assets["repo_id"],
                    "session_manifest": str(output / "session.json"), "session_sha256": digest(output / "session.json"),
                    "max_rss_mb": 8192, "credential_env": AUTH_ENV}}
            profile_path = output / "profile.json"
            shared.write_new(profile_path, profile)
            with native_supervision(profile_path, process=process, watcher=watcher, stop=stop,
                    guard=guard, max_rss_mb=8192, min_free_mb=8192) as scope:
                body = canonical(technical_body())
                status, _ = control("unauthenticated_chat", "POST", "/v1/chat/completions", body, "", scope)
                require(status == 401, "local_policy_auth_not_enforced")
                status, data = control("chat_json_warmup", "POST", "/v1/chat/completions", body, key, scope)
                native = observed_json(data, key)
                require(status == 200 and typed_equal(local.decode_response(data, SETTINGS), {"ready": True}),
                        "local_policy_real_json_control_failed")
                truncated = native["usage"].get("truncated")
                require(truncated is None or truncated is False, "local_policy_native_truncation_invalid")
                result["warmup_observation"] = {"usage": native["usage"], "native_usage_truncated": truncated,
                    "scope": "observed_json_schema_conformance_not_general_grammar_attestation"}
                status, data = control("unknown_request_model_diagnostic", "POST", "/v1/chat/completions",
                    canonical(technical_body("unknown-local-policy-model")), key, scope)
                require(status in (200, 400, 404), "local_policy_model_diagnostic_failed")
                if status == 200:
                    local.decode_response(data, SETTINGS)  # The loaded alias, never the unknown request, must be returned.
                    result["native_request_alias_enforcement"] = False
                else:
                    result["native_request_alias_enforcement"] = None
                result["fixed_client_alias_guard"] = "candidate_cannot_supply_model_or_endpoint"
                status, data = control("oversized_chat_context", "POST", "/v1/chat/completions",
                    canonical(technical_body(oversized=True)), key, scope)
                require(local.http_failure(status, data, SETTINGS)[0] == "unsupported", "local_policy_explicit_overflow_refusal_required")

                def stopped():
                    try:
                        scope.check(profile, profile_path)
                    except NativeSupervisionError:
                        guard["stop_reason"] = guard["stop_reason"] or "native_supervision_lost"
                        return True
                    return False
                scope.check(profile, profile_path)
                summary = run_campaign(output / "dataset.jsonl", profile_path, output / "campaign", stop_requested=stopped)
                coverage = shared.dataset_coverage(summary, dataset["cases"])
                result.update(status="collected" if coverage["collection_complete"] else "partial",
                    collection_complete=coverage["collection_complete"], scored_cases=coverage["scored_cases"],
                    quality_verdict=coverage["quality_verdict"], campaign_coverage=coverage)
    except BaseException as exc:
        result["failure_code"] = str(exc) if re.fullmatch(r"[a-z0-9_]{1,150}", str(exc)) else "local_policy_pilot_exception"
        result["failure_kind"] = type(exc).__name__
        if process is not None:
            result["status"] = "partial" if (output / "campaign").exists() else "technical_failure"
        if not isinstance(exc, (OSError, ValueError, KeyError, TypeError, HTTPException, subprocess.SubprocessError)):
            result["status"] = "interrupted"
            raise
        return result
    finally:
        try:
            if process is not None and not owned_group:
                # A failed session-creation check grants no right to signal a
                # process group. Terminate only the child we just created.
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                shared.finish_owned(None, watcher, stop)
            else:
                shared.finish_owned(process, watcher, stop)
        except (OSError, subprocess.SubprocessError):
            result["cleanup_error"] = "local_policy_owned_cleanup_failed"
        if key is not None:
            if previous is None:
                os.environ.pop(AUTH_ENV, None)
            else:
                os.environ[AUTH_ENV] = previous
        result["owned_process_terminated"] = process is None or process.poll() is not None
        result["resource_writer_closed"] = watcher is None or not watcher.is_alive()
        result["resources"] = deepcopy(guard)
        if guard["stop_reason"] is not None:
            # A resource or supervision stop is the attempt's stop reason; surface
            # it beside the collection flags instead of only inside the guard copy.
            result["collection_complete"] = False
            result["stop_reason"] = result.get("stop_reason") or guard["stop_reason"]
        try:
            result["memory_after"] = memory_snapshot()
        except (OSError, ValueError, subprocess.SubprocessError):
            result["memory_after_error"] = "not_observed"
        result["outer_sealed"] = result["owned_process_terminated"] and result["resource_writer_closed"]
        if not result["outer_sealed"]:
            result["collection_complete"] = False
        shared.write_new(output / "pilot.json", result)
        if result["outer_sealed"]:
            shared.write_new(output / "pilot-seal.json", {"schema_version": "deposium.native-pilot-seal/v1",
                "files": {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-root", "binary", "runtime-manifest", "model", "assets-manifest", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=ROOT / "datasets/tool-policy-canary-v1/cases.jsonl")
    parser.add_argument("--dataset-manifest", type=Path, default=ROOT / "datasets/tool-policy-canary-v1/manifest.json")
    parser.add_argument("--port", type=int, default=11446)
    args = parser.parse_args(argv)
    try:
        result = pilot(args)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print("Local policy prerequisites refused; no model result established.", file=sys.stderr)
        return 2
    print(json.dumps({k: result.get(k) for k in ("status", "collection_complete", "scored_cases", "total_cases",
        "quality_verdict", "stop_reason", "failure_code", "outer_sealed")}))
    return 0 if result["collection_complete"] and result["scored_cases"] > 0 and result["outer_sealed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
