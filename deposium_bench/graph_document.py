"""Private, unscored level-A observations on a complete captured corpus.

The existing bridge calls pinned MCPs services. This module only validates,
isolates, budgets and archives their execution; it contains no graph algorithm.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from .adapters import _environment, _json as _strict_json
from .cases import _no_annotations
from .graph_comparison import AFTER, BEFORE, BRIDGE, GRAPH_SOURCES
from .graph_review import load_graph_templates, validate_private_packet
from .graph_snapshot import audit_snapshot, _sha as file_sha
from .mastra_pilot import ROOT, SNAPSHOT_HELPER, _dump, _sha, _snapshot
from .registry import load_registry

DOCUMENT_LOADER = ROOT / "bridges/graph-document-loader.mjs"
REQUEST_KEYS = {"case_id", "family_id", "endpoint_mode", "entrypoint", "input", "context", "service"}
INPUT_KEYS = {"operation", "entity", "entity_id", "end_entity", "end_entity_id", "max_hops", "max_depth", "limit", "folder_ids"}
SERVICE_KEYS = {"graph_name", "folder_ids", "owner_tenant_id", "entity_id", "source_id", "target_id",
                "max_hops", "max_depth", "max_edges", "limit"}


def _private(path: str | Path) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_relative_to((ROOT / "results").resolve()):
        raise ValueError("graph document: inputs and outputs must remain under ignored results/")
    return resolved


def _write(path: Path, raw: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)


def validate_plan(plan: dict, packet: dict, packet_sha: str, scope: dict) -> list[dict]:
    """Only explicit endpoint requests may reach the service, never references."""
    if (not isinstance(plan, dict)
            or set(plan) != {"schema_version", "snapshot_sha256", "packet_sha256", "requests"}
            or plan["schema_version"] != "deposium.graph-document-plan/v1"
            or plan["packet_sha256"] != packet_sha
            or plan["snapshot_sha256"] != packet["snapshot"]["sha256"]
            or not isinstance(plan["requests"], list) or not 1 <= len(plan["requests"]) <= 48):
        raise ValueError("graph document: invalid or unbound request plan")
    owner, space = scope["owner_tenant_id"], scope["space_id"]
    folders = {str(value) for value in scope["folder_ids"]}
    eligible = {f["family_id"] for f in packet["families"] if f["status"] == "resolved"}
    ids = set()
    for row in plan["requests"]:
        if (not isinstance(row, dict) or set(row) != REQUEST_KEYS
                or not isinstance(row["case_id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", row["case_id"])
                or row["case_id"] in ids or not isinstance(row["family_id"], str)
                or row["family_id"] not in eligible & {"G01", "G02", "G03", "G06"}
                or row["endpoint_mode"] not in ("name", "id")
                or row["entrypoint"] not in ("helper", "legacy_service", "strict_service")
                or row["context"] != {"tenant_id": owner, "space_ids": [space]}
                or not isinstance(row["input"], dict) or set(row["input"]) - INPUT_KEYS
                or row["input"].get("operation") not in ("search", "neighbors", "path")
                or not isinstance(row["service"], dict) or set(row["service"]) - SERVICE_KEYS):
            raise ValueError("graph document: invalid, duplicate or out-of-scope request")
        _no_annotations(row)
        ids.add(row["case_id"])
        for value in (row["input"], row["service"]):
            for key, limit in (("max_hops", 4), ("max_depth", 3), ("max_edges", 1000), ("limit", 100)):
                if key in value and (type(value[key]) is not int or not 1 <= value[key] <= limit):
                    raise ValueError("graph document: request exceeds fixed operation budget")
            for key in ("entity", "entity_id", "end_entity", "end_entity_id", "source_id", "target_id"):
                if key in value and (not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > 2048):
                    raise ValueError("graph document: invalid endpoint")
        args, inp = row["service"], row["input"]
        if "folder_ids" in inp:
            selected = inp["folder_ids"]
            if (row["entrypoint"] != "helper" or not isinstance(selected, list) or not selected
                    or any(not isinstance(f, str) for f in selected) or len(set(selected)) != len(selected)
                    or not set(selected) <= folders):
                raise ValueError("graph document: explicit helper folders must be captured and authorized")
        if row["entrypoint"] != "helper":
            selected = args.get("folder_ids")
            if (not isinstance(selected, list) or not selected or any(not isinstance(f, str) for f in selected)
                    or len(set(selected)) != len(selected) or not set(selected) <= folders
                    or args.get("owner_tenant_id", owner) != owner
                    or args.get("graph_name") != f"entity_graph_{owner.replace('-', '_')}_{selected[0]}"):
                raise ValueError("graph document: service scope not captured")
            if inp["operation"] in {"path", "neighbors"} and not args.get("source_id"):
                raise ValueError("graph document: explicit service source required")
            if inp["operation"] == "path" and not args.get("target_id"):
                raise ValueError("graph document: explicit service target required")
            if inp["operation"] == "neighbors" and args.get("owner_tenant_id") != owner:
                raise ValueError("graph document: explicit neighborhood owner required")
            for actual, described in (("source_id", "entity_id"), ("target_id", "end_entity_id"), ("entity_id", "entity_id")):
                if actual in args and args[actual] != inp.get(described):
                    raise ValueError("graph document: described and executed endpoints differ")
        elif args:
            raise ValueError("graph document: helper must resolve its own service arguments")
        if row["endpoint_mode"] == "name":
            if any(key in inp for key in ("entity_id", "end_entity_id")) or args.get("entity_id"):
                raise ValueError("graph document: name and ID routes must remain separate")
            if row["entrypoint"] != "helper" and inp["operation"] != "search":
                raise ValueError("graph document: direct service has no name resolver")
            if not inp.get("entity") or (inp["operation"] == "path" and not inp.get("end_entity")):
                raise ValueError("graph document: named endpoints required")
        elif row["entrypoint"] == "helper":
            if not inp.get("entity_id") or (inp["operation"] == "path" and not inp.get("end_entity_id")):
                raise ValueError("graph document: ID endpoints required")
        elif inp["operation"] == "search" and (not args.get("entity_id") or row["entrypoint"] == "legacy_service"):
            raise ValueError("graph document: ID search requires strict service")
    return deepcopy(plan["requests"])


def _available_mib() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024
    raise ValueError("graph document: memory availability unavailable")


def _require_candidate_descendant(root: Path, candidate: str) -> None:
    result = subprocess.run(["git", "merge-base", "--is-ancestor", AFTER, candidate],
                            cwd=root, env=_environment(), stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=10)
    if result.returncode != 0:
        raise ValueError("graph document: candidate must descend from the pinned #805 revision")


def _invoke(request: dict, snapshot: Path, seconds: float) -> dict:
    """One Node process; sampled RSS guard includes native DuckDB allocations."""
    peak, failure = 0.0, None
    with tempfile.TemporaryFile() as output:
        try:
            process = subprocess.Popen(["node", "--max-old-space-size=256", str(snapshot / BRIDGE.name), str(snapshot)],
                                       stdin=subprocess.PIPE, stdout=output, stderr=subprocess.DEVNULL,
                                       cwd=ROOT, env=_environment())
        except OSError:
            return {"status": "error", "error": "document_driver_unavailable", "sampled_peak_rss_mib": peak}
        began = time.monotonic()
        try:
            process.stdin.write(_dump(request))
            process.stdin.close()
            while process.poll() is None:
                try:
                    for line in Path(f"/proc/{process.pid}/status").read_text().splitlines():
                        if line.startswith("VmRSS:"):
                            peak = max(peak, int(line.split()[1]) / 1024)
                except FileNotFoundError:
                    pass
                if peak > 1536:
                    failure = "resource_limit"
                elif time.monotonic() - began >= seconds:
                    failure = "timeout"
                elif os.fstat(output.fileno()).st_size > 1024 * 1024:
                    failure = "output_limit"
                if failure:
                    process.kill()
                    break
                time.sleep(0.05)
            process.wait(timeout=5)
            if failure:
                return {"status": failure, "error": "document_driver_" + failure, "sampled_peak_rss_mib": peak}
            output.seek(0)
            raw = output.read(1024 * 1024 + 1)
            if process.returncode or len(raw) > 1024 * 1024:
                raise ValueError("transport failed")
            response = _strict_json(raw)
            if (not isinstance(response, dict) or response.get("status") not in {"ok", "error"}
                    or response.get("case_id") != request["case_id"]):
                raise ValueError("invalid response")
            response["sampled_peak_rss_mib"] = peak
            return response
        except (OSError, ValueError, subprocess.SubprocessError):
            return {"status": "error", "error": "document_driver_transport_failed", "sampled_peak_rss_mib": peak}
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


def observation_summary(requests: list[dict], rows: list[dict], repetitions: int, stop: str | None) -> dict:
    expected = len(requests) * repetitions
    if not requests:
        raise ValueError("graph document: empty observation plan")
    valid = sum(r.get("provenance_valid") is True and r["response"].get("status") == "ok" for r in rows)
    summary = {"schema_version": "deposium.graph-document-summary/v1",
               "qualification": "unscored_real_services_on_captured_private_data",
               "completion_status": "incomplete" if stop or valid != expected * 2 else "complete",
               "stop_reason": stop, "requests": len(requests), "repetitions": repetitions,
               "expected_executions": expected * 2, "observed_executions": len(rows),
               "valid_observations": valid,
               "families_total": 8, "families_observed": len({r["family_id"] for r in rows}),
               "unresolved_families": ["G04", "G05"], "non_graph_controls": ["T01", "T02"],
               "documentary_cases_scored": 0, "final_answers_scored": 0, "model_calls": 0,
               "level_B": "not_run", "level_C": "not_implemented", "arms": {},
               "limits": ["References are proposals, not human-reviewed truth; no documentary accuracy score.",
                          "Name/ID routes are not FR/EN model calls; languages remain unmeasured at level B.",
                          "Grants/folder mapping are captured fixtures, not live access-control qualification.",
                          "DuckPGQ is disabled at the capability seam; this observes CTE fallback only.",
                          "Every invocation has a fresh process and database; no warm or production latency claim."]}
    for arm in ("before", "after"):
        selected = [r for r in rows if r["arm"] == arm]
        by_entry = {}
        for entry in ("helper", "legacy_service", "strict_service"):
            subset = [r for r in selected if r["entrypoint"] == entry]
            by_entry[entry] = dict(Counter(r["response"].get("outcome", r["response"].get("status", "missing")) for r in subset))
        summary["arms"][arm] = {"executed": len(selected), "expected": expected, "missing": expected - len(selected),
                                "valid_observations": sum(r.get("provenance_valid") is True and r["response"].get("status") == "ok" for r in selected),
                                "transport_statuses": dict(Counter(r["response"].get("status", "missing") for r in selected)),
                                "outcomes_by_entrypoint": by_entry}
    rss = [r["response"]["sampled_peak_rss_mib"] for r in rows if "sampled_peak_rss_mib" in r["response"]]
    summary["sampled_peak_child_rss_mib"] = max(rss) if rss else None
    return summary


def observe_graph_documents(mcps_root: str | Path, archive: str | Path, plan_path: str | Path,
                            output: str | Path, *, repetitions: int = 1, max_seconds: int = 300,
                            candidate_revision: str | None = None) -> dict:
    if type(repetitions) is not int or not 1 <= repetitions <= 4 or type(max_seconds) is not int or not 1 <= max_seconds <= 600:
        raise ValueError("graph document: invalid repetition or wall budget")
    if candidate_revision is not None and (not re.fullmatch(r"[0-9a-f]{40}", candidate_revision)
                                           or candidate_revision == AFTER):
        raise ValueError("graph document: distinct complete candidate revision required")
    revisions = {"before": AFTER if candidate_revision else BEFORE, "after": candidate_revision or AFTER}
    root, source, plan_path, target = Path(mcps_root).resolve(), _private(archive), _private(plan_path), _private(output)
    if candidate_revision:
        _require_candidate_descendant(root, candidate_revision)
    if target.exists() or target.is_relative_to(source) or target.is_relative_to(root):
        raise ValueError("graph document: output must be a new separate private archive")
    for path in (source, plan_path, target):
        ignored = subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=ROOT, env=_environment(),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        if ignored.returncode != 0:
            raise ValueError("graph document: private path is not ignored by Git")
    tracked = subprocess.run(["git", "ls-files", "-z", "--", str(source), str(plan_path), str(target)],
                             cwd=ROOT, env=_environment(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
    if tracked.returncode or tracked.stdout:
        raise ValueError("graph document: private input is tracked by Git")
    if _available_mib() < 3072:
        raise ValueError("graph document: at least 3072 MiB available required")
    audit = audit_snapshot(source)
    if audit["status"] != "archive_consistent":
        raise ValueError("graph document: source archive integrity check failed")
    packet_raw, plan_raw = (source / "packet.json").read_bytes(), plan_path.read_bytes()
    if len(plan_raw) > 128 * 1024:
        raise ValueError("graph document: plan too large")
    packet, plan = _strict_json(packet_raw), _strict_json(plan_raw)
    templates, _ = load_graph_templates()
    review = validate_private_packet(packet, templates, source)
    if review["scope_evidence_consistency"] != "matched":
        raise ValueError("graph document: filtered scope evidence required")
    scope = _strict_json((source / "scope.private.json").read_bytes())
    requests = validate_plan(plan, packet, _sha(packet_raw), scope)
    capture = source / "snapshot.private.jsonl"
    if packet["snapshot"]["sha256"] != file_sha(capture):
        raise ValueError("graph document: packet and snapshot differ")
    schemas = list(source.glob("schema*.payload.private.json"))
    if len(schemas) != 1:
        raise ValueError("graph document: one captured schema required")
    descriptor = {"path": str(capture), "sha256": file_sha(capture),
                  "schema_path": str(schemas[0]), "schema_sha256": file_sha(schemas[0]),
                  "owner_tenant_id": scope["owner_tenant_id"], "folder_ids": [str(f) for f in scope["folder_ids"]],
                  "expected_counts": {k: audit["public_summary"]["snapshot_rows"].get(k, 0)
                                      for k in ("entities", "relations", "pages", "enriched")}}
    fixture = {"entities": [], "relations": [], "document_snapshot": descriptor,
               "grants": [{"spaceId": scope["space_id"], "ownerTenantId": scope["owner_tenant_id"], "accessMode": "member"}],
               "folders": {scope["space_id"]: scope["folder_ids"]}}
    bench_paths = (Path(__file__), ROOT / "deposium_bench/graph_comparison.py", ROOT / "deposium_bench/mastra_pilot.py",
                   ROOT / "deposium_bench/graph_review.py", ROOT / "deposium_bench/graph_snapshot.py", BRIDGE, DOCUMENT_LOADER, SNAPSHOT_HELPER)
    bench_bytes = {p: p.read_bytes() for p in bench_paths}
    registry, registry_sha = load_registry()
    rows, provenance, runtimes = [], {}, {}
    stop = None
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    _write(target / "plan.private.json", plan_raw)
    _write(target / "packet.private.json", packet_raw)
    _write(target / "integrity.private.json", _dump(audit))
    _write(target / "stack-registry.json", _dump(registry))
    with tempfile.TemporaryDirectory(prefix="deposium-graph-doc-") as temporary:
        snapshots = {}
        for arm, revision in revisions.items():
            snapshots[arm] = Path(temporary) / arm
            snapshots[arm].mkdir()
            provenance[arm] = _snapshot(root, revision, snapshots[arm], extra_sources=GRAPH_SOURCES)
            for p in (BRIDGE, DOCUMENT_LOADER, SNAPSHOT_HELPER):
                (snapshots[arm] / p.name).write_bytes(bench_bytes[p])
        manifest = {"schema_version": "deposium.graph-document-observation/v1", "sources": provenance,
                    "comparison_kind": "candidate_against_805" if candidate_revision else "before_after_805",
                    "reference_packet_revisions": {"before": BEFORE, "after": AFTER},
                    "snapshot": descriptor, "plan_sha256": _sha(plan_raw), "packet_sha256": _sha(packet_raw),
                    "reference_review": review, "stack_registry_sha256": registry_sha,
                    "bench_files_sha256": {str(p.relative_to(ROOT)): _sha(b) for p, b in bench_bytes.items()},
                    "budgets": {"concurrency": 1, "duckdb_threads": 2, "duckdb_memory_mb": 512,
                                "node_heap_mib": 256, "rss_guard_mib": 1536, "rss_poll_ms": 50,
                                "minimum_available_mib": 3072, "per_call_seconds": 30, "execution_wall_seconds": max_seconds},
                    "repetitions": repetitions, "order": "alternate_arms_by_request_and_repetition",
                    "process_mode": "fresh_process_and_memory_database_per_call",
                    "capture_source": "archive_paths_external_to_this_result_must_be_retained",
                    "scope_services": "captured_mapping_with_simulated_authorization",
                    "duckpgq": "declared_unavailable_for_cte", "models": [],
                    "components": [{"id": c["id"], "status": "isolated_services" if c["id"] == "deposium_MCPs" else "not_exercised"}
                                   for c in registry["components"]]}
        _write(target / "manifest.private.json", _dump(manifest))
        began = time.monotonic()
        fd = os.open(target / "raw.private.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            for repetition in range(repetitions):
                for index, planned in enumerate(requests):
                    request = {k: deepcopy(planned[k]) for k in ("case_id", "entrypoint", "input", "context", "service")}
                    request["fixture"] = fixture
                    arms = ("before", "after") if (index + repetition) % 2 == 0 else ("after", "before")
                    for arm in arms:
                        remaining = max_seconds - (time.monotonic() - began)
                        if remaining <= 0 or _available_mib() < 3072:
                            stop = "wall_budget" if remaining <= 0 else "memory_available_guard"
                            break
                        started = time.monotonic()
                        response = _invoke(request, snapshots[arm], min(30, remaining))
                        if response.get("status") == "ok":
                            meta = response.get("document_snapshot", {})
                            identity = response.get("runtime")
                            if (response.get("source_files_sha256") != provenance[arm]["files_sha256"]
                                    or not isinstance(identity, dict) or response.get("network_attempts") != 0
                                    or meta.get("snapshot_sha256") != descriptor["sha256"]
                                    or meta.get("schema_sha256") != descriptor["schema_sha256"]
                                    or meta.get("loaded_counts") != descriptor["expected_counts"]
                                    or (arm in runtimes and runtimes[arm] != identity)):
                                # Preserve even rejected raw outputs for audit.
                                stop = "provenance_mismatch"
                            else:
                                runtimes[arm] = identity
                        row = {"case_id": planned["case_id"], "family_id": planned["family_id"],
                               "endpoint_mode": planned["endpoint_mode"], "entrypoint": planned["entrypoint"],
                               "arm": arm, "repetition": repetition, "response": response,
                               "cold_process_wall_ms": (time.monotonic() - started) * 1000,
                               "provenance_valid": response.get("status") == "ok" and stop is None,
                               "documentary_scored": False, "response_quality_scored": False}
                        stream.write(_dump(row).replace(b"\n", b" ") + b"\n")
                        stream.flush()
                        rows.append(row)
                        if response.get("status") == "resource_limit":
                            stop = "child_rss_guard"
                        elif response.get("error") in {"graph_document_load_failed", "graph_input_failed",
                                                       "graph_database_failed", "graph_loader_failed", "document_driver_unavailable"}:
                            stop = "harness_setup_failed"
                        if stop:
                            break
                    if stop:
                        break
                if stop:
                    break
        if (any(p.read_bytes() != b for p, b in bench_bytes.items())
                or plan_path.read_bytes() != plan_raw or (source / "packet.json").read_bytes() != packet_raw
                or file_sha(capture) != descriptor["sha256"] or file_sha(schemas[0]) != descriptor["schema_sha256"]):
            stop = "input_or_bench_changed"
        summary = observation_summary(requests, rows, repetitions, stop)
        summary["comparison_kind"] = manifest["comparison_kind"]
        summary["revisions"] = revisions
        _write(target / "summary.json", _dump(summary))
        _write(target / "seal.json", _dump({"schema_version": "deposium.graph-document-seal/v1",
                                           "files": {p.name: file_sha(p) for p in sorted(target.iterdir()) if p.is_file()}}))
    return summary
