#!/usr/bin/env python3
"""Explicit Uzu decision pilot using the shared campaign engine.

CPU fixtures qualify this controller only. No Uzu build, preparation producer,
model, native sandbox, Metal backend or performance is qualified by those tests.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
from subprocess import Popen
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.campaigns import run_campaign
from deposium_bench.cases import parse_cases
from deposium_bench.native_resources import memory_snapshot
from deposium_bench.native_supervision import native_supervision, NativeSupervisionError
from deposium_bench.systemone_local import digest, http_request, native_request
from deposium_bench.worker_transport import decode
from deposium_bench.uzu_local import (PACK_REPO, PACK_REVISION, REPOSITORY, UZU_REVISION,
    MAX_METADATA, closed, preparation_map, read_metadata, require, sha, verify_pack)

SPEC = importlib.util.spec_from_file_location("uzu_shared_supervision", ROOT / "scripts/run-native-pilot.py")
shared = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shared)

# Stock CLI contains a downloader. Restrict remote egress even for accidentally
# incomplete local packs. This OS policy needs its own real Mac qualification.
NETWORK_POLICY = '(version 1)(allow default)(deny network-outbound)(allow network-outbound (remote ip "127.0.0.1:*"))'


def launch_command(binary, pack, port):
    require(type(port) is int and 1024 <= port <= 65535, "uzu_port_invalid")
    return ["/usr/bin/sandbox-exec", "-p", NETWORK_POLICY, str(binary), "server",
            "--model", str(pack), "--host", "127.0.0.1", "--port", str(port), "--no-prefix-cache"]


def group_absent(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False


def ensure_port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", port))


def pilot(args):
    require(args.execute is True, "uzu_explicit_execution_required")
    require(platform.system() == "Darwin" and platform.machine() == "arm64", "uzu_mac_arm64_only")
    require(type(args.max_rss_mb) is int and args.max_rss_mb == 14336
            and type(args.min_free_mb) is int and args.min_free_mb == 8192
            and type(args.max_seconds) is int and 1 <= args.max_seconds <= 1200,
            "uzu_proposed_envelope_invalid")
    launch_command(args.binary, args.pack, args.port)
    require(isinstance(args.model_id, str) and args.model_id.strip()
            and len(args.model_id) <= 256 and "\x00" not in args.model_id, "uzu_served_id_required")
    ensure_port_available(args.port)
    started = time.monotonic()
    deadline = started + args.max_seconds
    pack, binary = Path(args.pack).absolute(), Path(args.binary).absolute()
    assets_path, prep_path = Path(args.assets_manifest).absolute(), Path(args.preparation).absolute()
    output = Path(args.output).absolute()
    require(not output.exists() and not output.is_symlink()
            and not output.resolve().is_relative_to(pack.resolve())
            and (not output.resolve().is_relative_to(ROOT)
                 or output.resolve().is_relative_to(ROOT / "results")),
            "uzu_output_must_be_new_private_and_outside_pack")
    dataset = Path(args.dataset).read_bytes()
    cases, dataset_sha = parse_cases(dataset)
    require(cases and all(c["contract_id"] == "bench.context-choice" for c in cases), "uzu_choice_dataset_required")
    before = memory_snapshot()
    require(before["MemAvailable_mib"] >= args.max_rss_mb + args.min_free_mb, "uzu_memory_admission_refused")
    states = {}

    def remember(path, expected):
        path = Path(path)
        require(not path.is_symlink() and path.is_file(), "uzu_file_missing_or_symlink")
        state = (path.stat().st_dev, path.stat().st_ino, path.stat().st_size, path.stat().st_mtime_ns,
                 path.stat().st_ctime_ns)
        require(time.monotonic() < deadline and digest(path) == expected, "uzu_file_hash_or_deadline")
        require(state == (path.stat().st_dev, path.stat().st_ino, path.stat().st_size,
                          path.stat().st_mtime_ns, path.stat().st_ctime_ns), "uzu_file_changed")
        states[path] = state

    assets = verify_pack(pack, assets_path, remember)
    runtime = read_metadata(args.runtime_manifest)
    closed(runtime, {"repository", "revision", "binary_sha256"}, "uzu_runtime_manifest_invalid")
    require(runtime["repository"] == REPOSITORY and runtime["revision"] == UZU_REVISION
            and sha(runtime["binary_sha256"]), "uzu_runtime_identity_invalid")
    remember(binary, runtime["binary_sha256"])
    assets_sha = digest(assets_path)
    prep = read_metadata(prep_path)
    prepared = preparation_map(prep, model_id=args.model_id,
                               assets_sha256=assets_sha, max_tokens=4096)
    expected = {hashlib.sha256(native_request(c["input"], args.model_id)[2]).hexdigest()
                for c in cases}
    require(set(prepared) == expected, "uzu_preparation_exact_dataset_required")
    remember(prep_path, digest(prep_path))
    require(time.monotonic() < deadline and memory_snapshot()["MemAvailable_mib"] >= args.min_free_mb,
            "uzu_prelaunch_deadline_or_reserve")
    from deposium_bench.systemone_local import _state
    require(all(_state(path) == state for path, state in states.items()), "uzu_prelaunch_file_changed")
    output.mkdir(parents=True)
    (output / "dataset.jsonl").write_bytes(dataset)
    # Keep exact metadata originals with the campaign instead of depending on
    # mutable external preparation/manifests after the run. Never copy weights.
    for source, name, expected_sha, expected_value in (
            (assets_path, "assets-manifest.json", assets_sha, assets),
            (prep_path, "input-preparation.json", digest(prep_path), prep),
            (Path(args.runtime_manifest), "runtime-manifest.json", digest(args.runtime_manifest), runtime)):
        with source.open("rb") as stream:
            data = stream.read(MAX_METADATA + 1)
        require(len(data) <= MAX_METADATA and hashlib.sha256(data).hexdigest() == expected_sha,
                "uzu_metadata_changed_before_capture")
        require(decode(data) == expected_value, "uzu_metadata_value_changed_before_capture")
        with (output / name).open("xb") as stream:
            stream.write(data)
    assets_path, prep_path = output / "assets-manifest.json", output / "input-preparation.json"
    cache = output / "private-cache"
    cache.mkdir()
    # No credentials, proxies, provider endpoints or remote model names inherited.
    environment = {"PATH": os.defpath, "LANG": "C.UTF-8", "TZ": "UTC",
                   "XDG_CACHE_HOME": str(cache), "TMPDIR": str(cache)}
    command = launch_command(binary, pack, args.port)
    shared.write_new(output / "launch.json", {"command": command, "network": "loopback_only_requested"})
    stop = threading.Event()
    guard = {"stop_reason": None, "rss_peak_mib": 0, "min_available_mib": before["MemAvailable_mib"]}
    process = watcher = None
    owned = False
    result = {"schema_version": "deposium.uzu-pilot/v1", "created_at": datetime.now(timezone.utc).isoformat(),
              "dataset_sha256": dataset_sha, "eligible_cases": len(cases), "completed": False,
              "cleanup": "not_started", "backend_requested": "metal", "backend_observed": None}
    try:
        with (output / "engine.log").open("xb") as log:
            process = Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
            require(os.getpgid(process.pid) == process.pid and process.pid != os.getpgrp(), "uzu_group_not_owned")
            owned = True
            resource_args = argparse.Namespace(max_rss_mb=args.max_rss_mb, min_free_mb=args.min_free_mb,
                max_seconds=max(0, deadline - time.monotonic()))
            watcher = threading.Thread(target=shared.watch_resources,
                args=(process, stop, guard, output, resource_args), daemon=True)
            watcher.start()
            startup_deadline = min(deadline, time.monotonic() + 180)
            while True:
                require(process.poll() is None and guard["stop_reason"] is None
                        and time.monotonic() < startup_deadline, "uzu_startup_stopped")
                try:
                    status, data = http_request(args.port, "GET", "/v1/models", None, None, 1)
                    models = decode(data)
                    if (status == 200 and isinstance(models, dict) and isinstance(models.get("data"), list)
                            and len(models["data"]) == 1 and models["data"][0].get("id") == args.model_id
                            and guard.get("last_observed_monotonic") is not None):
                        break
                except (OSError, TimeoutError, ValueError):
                    pass
                time.sleep(.1)
            session = {"schema_version": "deposium.uzu-model-session/v1",
                "model": {"repo_id": PACK_REPO, "revision": PACK_REVISION, "alias": args.model_id,
                    "path": str(pack), "assets_manifest": str(assets_path), "assets_sha256": assets_sha},
                "runtime": {"repository": REPOSITORY, "revision": UZU_REVISION, "binary": str(binary),
                    "sha256": runtime["binary_sha256"]},
                "preparation": {"path": str(prep_path), "sha256": digest(prep_path)},
                "endpoint": f"http://127.0.0.1:{args.port}/v1/systemone",
                "settings": {"client_max_tokens": 4096, "concurrency": 1, "questions_per_call": 1,
                             "implicit_acquisition": False},
                "max_rss_mb": args.max_rss_mb, "pid": process.pid,
                "supervisor": {"pid": os.getpid(), "path": str(Path(__file__)), "sha256": digest(__file__)}}
            shared.write_new(output / "session.json", session)
            profile = {"schema_version": "deposium.candidate/v1", "profile_id": "uzu-d3-flash-m",
                "adapter": "uzu_systemone_local", "qualification": "model_isolated",
                "capabilities": ["bench.context-choice"], "revision": PACK_REVISION, "recordings": None,
                "timeout_seconds": 30, "model": {"endpoint": session["endpoint"], "model_id": args.model_id,
                    "repo_id": PACK_REPO, "session_manifest": str(output / "session.json"),
                    "session_sha256": digest(output / "session.json"), "max_length": 4096,
                    "max_rss_mb": args.max_rss_mb, "credential_env": None}}
            profile_path = output / "profile.json"
            shared.write_new(profile_path, profile)
            with native_supervision(profile_path, process=process, watcher=watcher, stop=stop,
                    guard=guard, max_rss_mb=args.max_rss_mb, min_free_mb=args.min_free_mb) as scope:
                def stopped():
                    try:
                        scope.check(profile, profile_path)
                    except NativeSupervisionError:
                        guard["stop_reason"] = guard["stop_reason"] or "native_supervision_lost"
                    return guard["stop_reason"] is not None
                summary = run_campaign(output / "dataset.jsonl", profile_path, output / "campaign",
                                       stop_requested=stopped)
                result["coverage"] = shared.dataset_coverage(summary, len(cases))
                result["completed"] = result["coverage"]["technical_full_coverage"] and not stopped()
    except BaseException as exc:
        result["error"] = type(exc).__name__
        raise
    finally:
        try:
            if process is not None and not owned:
                # Never signal an unverified group. Only the exact Popen child
                # can be terminated; descendant cleanup remains unknown.
                stop.set()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            else:
                shared.finish_owned(process, watcher, stop)
            result["cleanup"] = ("not_started" if process is None else
                "verified_group_absent" if owned and process.poll() is not None
                and group_absent(process.pid) else "unknown")
        except BaseException as exc:
            result["cleanup"] = "unknown"
            result["cleanup_error"] = type(exc).__name__
            raise
        finally:
            files = {str(path.relative_to(output)): digest(path) for path in sorted(output.rglob("*"))
                     if "private-cache" not in path.relative_to(output).parts
                     and not path.is_symlink() and path.is_file()}
            result.update(resources=guard, elapsed_seconds=time.monotonic() - started,
                          elapsed_scope="through_cleanup_and_evidence_hashing_before_final_receipt")
            result["completed"] = bool(result["completed"] and result["cleanup"] == "verified_group_absent"
                                       and result["elapsed_seconds"] <= args.max_seconds)
            shared.write_new(output / "pilot.json", result)
            files["pilot.json"] = digest(output / "pilot.json")
            shared.write_new(output / "pilot-seal.json", {"schema_version": "deposium.uzu-pilot-seal/v1",
                "files": files, "sha256": hashlib.sha256(
                    json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pack", "assets-manifest", "binary", "runtime-manifest", "preparation", "dataset", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--model-id", required=True, help="Exact id served from the pinned local pack")
    parser.add_argument("--port", type=int, default=11439)
    parser.add_argument("--max-rss-mb", type=int, default=14336)
    parser.add_argument("--min-free-mb", type=int, default=8192)
    parser.add_argument("--max-seconds", type=int, default=1200)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("--execute is required; this CPU contribution does not authorize a native run")
    return 0 if pilot(args)["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
