"""Pinned graph contract comparison, using real MCPs services on isolated fixtures.

No graph algorithm, endpoint resolver, service launch or model lives here.
Documentary qualification and product answers require separate evidence.
"""
from __future__ import annotations

from copy import deepcopy
from collections import Counter
import json
from pathlib import Path
import tempfile
import time

from .adapters import _json, _read
from .cases import typed_equal
from .mastra_pilot import (ROOT, SNAPSHOT_HELPER, _dump, _native, _new_archive,
                           _sha, _snapshot)
from .registry import load_registry

BEFORE = "982f49d2b7ab85a6b52a91a4dac797559ebbc9df"
AFTER = "eed8934ed597da12a8c79f14f872042e0658f253"
BRIDGE = ROOT / "bridges/graph-service-compare.mjs"
DOCUMENT_LOADER = ROOT / "bridges/graph-document-loader.mjs"
CONTROLS = ROOT / "deposium_bench/data/graph-service-controls.json"
GRAPH_SOURCES = (
    "src/services/duckdb-graph-advanced.ts", "src/services/duckdb-schema.ts",
    "src/services/duckdb-column-default.ts", "src/services/duckdb-reingest-guard.ts",
    "src/services/graph-query-optimizer.ts", "src/config/graph-config.ts",
    "src/utils/sql-validators.ts", "src/contracts/temporal-relations.ts",
    "src/services/graph-table-contract.ts",
    "src/utils/source-pages.ts",
)
REQUEST_FIELDS = ("case_id", "entrypoint", "input", "context", "service")
FIXTURE_FIELDS = {"grants", "folders", "entities", "relations", "faults", "entities_add", "relations_add"}


def _result_class(response: dict) -> str:
    """Keep a successful zero-edge result distinct from non-results."""
    status = response.get("status", "missing")
    if status != "ok":
        return status
    outcome = response.get("outcome", "missing")
    if outcome != "ok":
        return outcome
    output = response.get("output")
    if not isinstance(output, dict):
        return "ok_edge_count_unknown"
    counts = []
    if type(output.get("edge_count")) is int and output["edge_count"] >= 0:
        counts.append(output["edge_count"])
    for owner in (output, output.get("path")):
        if isinstance(owner, dict) and isinstance(owner.get("edges"), list):
            counts.append(len(owner["edges"]))
    if isinstance(output.get("connections"), list):
        counts.append(len(output["connections"]))
    if not counts:
        return "ok_edge_count_unknown"
    if 0 in counts and any(count > 0 for count in counts):
        return "ok_edge_count_conflict"
    return "ok_with_edges" if any(count > 0 for count in counts) else "ok_zero_edges"


def contract_check(expected: list[dict], response: dict) -> dict:
    """Exact typed assertions on native JSON; missing, empty or wrong fails."""
    if not isinstance(expected, list) or not expected:
        raise ValueError("graph comparison: empty oracle")
    checks = []
    for assertion in expected:
        if (not isinstance(assertion, dict) or set(assertion) != {"path", "equals"}
                or not isinstance(assertion["path"], list) or not assertion["path"]
                or any(type(key) not in (str, int) or key == "" or (type(key) is int and key < 0)
                       for key in assertion["path"])):
            raise ValueError("graph comparison: invalid assertion")
        value = response
        found = True
        for key in assertion["path"]:
            if isinstance(value, dict) and type(key) is str and key in value:
                value = value[key]
            elif isinstance(value, list) and type(key) is int and key < len(value):
                value = value[key]
            else:
                found = False
                break
        checks.append({"path": assertion["path"], "passed": found and typed_equal(value, assertion["equals"])})
    return {"passed": response.get("status") == "ok" and all(row["passed"] for row in checks),
            "checks": checks}


def load_controls(path: str | Path = CONTROLS) -> tuple[dict, bytes]:
    data = _read(Path(path))
    fixture = _json(data)
    controls = fixture.get("controls") if isinstance(fixture, dict) else None
    if not isinstance(controls, list) or not 1 <= len(controls) <= 64 or not isinstance(fixture.get("fixture"), dict):
        raise ValueError("graph comparison: missing or oversized fixture")
    if set(fixture["fixture"]) - FIXTURE_FIELDS:
        raise ValueError("graph comparison: unknown fixture field")
    ids = set()
    for control in controls:
        if (not isinstance(control, dict) or not set(REQUEST_FIELDS) <= set(control)
                or not isinstance(control["case_id"], str) or not control["case_id"].strip()
                or control["case_id"] in ids
                or control["entrypoint"] not in {"helper", "legacy_service", "strict_service"}
                or not isinstance(control.get("fixture_overrides", {}), dict)
                or set(control.get("fixture_overrides", {})) - FIXTURE_FIELDS):
            raise ValueError("graph comparison: invalid or duplicate control")
        ids.add(control["case_id"])
        for arm in ("before", "after"):
            contract_check(control.get("expected_" + arm), {})
    return fixture, data


def control_request(control: dict, fixture: dict) -> dict:
    if set(fixture) - FIXTURE_FIELDS or set(control.get("fixture_overrides", {})) - FIXTURE_FIELDS:
        raise ValueError("graph comparison: unknown fixture field")
    request = {field: deepcopy(control[field]) for field in REQUEST_FIELDS}
    request["fixture"] = deepcopy(fixture)
    request["fixture"].update(deepcopy(control.get("fixture_overrides", {})))
    return request


def compare_graph_contracts(mcps_root: str | Path, output: str | Path, *,
                            before: str = BEFORE, after: str = AFTER,
                            repetitions: int = 1, max_seconds: int = 300) -> dict:
    """Explicit local invocation; immutable archives, alternate arms, no live DB."""
    if type(repetitions) is not int or not 1 <= repetitions <= 4:
        raise ValueError("graph comparison: repetitions must be 1..4")
    if type(max_seconds) is not int or not 1 <= max_seconds <= 600:
        raise ValueError("graph comparison: wall budget must be 1..600 seconds")
    if before == after:
        raise ValueError("graph comparison: two distinct revisions required")
    root, target = Path(mcps_root).resolve(), Path(output)
    if target.exists():
        raise FileExistsError(target)
    if target.resolve().is_relative_to(root):
        raise ValueError("graph comparison: output inside application forbidden")
    fixture, fixture_bytes = load_controls()
    registry, registry_sha = load_registry()
    bench_paths = (Path(__file__).resolve(), ROOT / "deposium_bench/mastra_pilot.py", BRIDGE, SNAPSHOT_HELPER, DOCUMENT_LOADER)
    bench_bytes = {path: path.read_bytes() for path in bench_paths}
    bench_hashes = {str(path.relative_to(ROOT)): _sha(data) for path, data in bench_bytes.items()}
    rows, runtime, snapshots, provenance = [], {}, {}, {}
    started, stop = time.monotonic(), None
    with tempfile.TemporaryDirectory(prefix="deposium-graph-compare-") as temporary:
        for arm, revision in (("before", before), ("after", after)):
            snapshot = Path(temporary) / arm
            snapshot.mkdir()
            provenance[arm] = _snapshot(root, revision, snapshot, extra_sources=GRAPH_SOURCES)
            for path in (BRIDGE, SNAPSHOT_HELPER, DOCUMENT_LOADER):
                (snapshot / path.name).write_bytes(bench_bytes[path])
            snapshots[arm] = snapshot
        _new_archive(target, root)
        (target / "controls.json").write_bytes(fixture_bytes)
        (target / "stack-registry.json").write_bytes(_dump(registry))
        comparison_kind = "before_after_805" if (before, after) == (BEFORE, AFTER) else "pinned_revision_comparison"
        revisions = {"before": before, "after": after}
        manifest = {"schema_version": "deposium.graph-contract-comparison/v1",
                    "qualification": "real_mcps_services_on_synthetic_duckdb",
                    "data_kind": "synthetic", "sources": provenance,
                    "comparison_kind": comparison_kind, "revisions": revisions,
                    "controls_sha256": _sha(fixture_bytes), "bench_files_sha256": bench_hashes,
                    "stack_registry_sha256": registry_sha,
                    "repetitions": repetitions, "max_seconds": max_seconds,
                    "order": "alternate_before_after_by_control_and_repetition",
                    "scope_services": "authorization_grants_and_folder_mapping_are_synthetic",
                    "duckpgq": "declared_unavailable_at_capability_seam_for_isolated_cte",
                    "process_mode": "new_process_and_new_memory_database_per_invocation",
                    "components": [{"id": item["id"], "qualification":
                                    "isolated_real_services" if item["id"] == "deposium_MCPs" else "not_exercised"}
                                   for item in registry["components"]]}
        (target / "manifest.json").write_bytes(_dump(manifest))
        with (target / "raw.jsonl").open("x", encoding="utf-8") as stream:
            for repetition in range(repetitions):
                for index, control in enumerate(fixture["controls"]):
                    request = control_request(control, fixture["fixture"])
                    arms = ("before", "after") if (index + repetition) % 2 == 0 else ("after", "before")
                    for arm in arms:
                        if time.monotonic() - started >= max_seconds:
                            stop = "wall_budget"
                            break
                        began = time.monotonic()
                        response = _native(request, snapshots[arm], snapshots[arm] / BRIDGE.name)
                        if response.get("status") == "ok":
                            identity = response.get("runtime")
                            if (response.get("source_files_sha256") != provenance[arm]["files_sha256"]
                                    or not isinstance(identity, dict) or response.get("network_attempts") != 0
                                    or (arm in runtime and identity != runtime[arm])):
                                # Keep the rejected bridge output for audit, as the Mastra pilot does.
                                response = {"status": "error", "error": "graph_provenance_changed",
                                            "raw_response": response}
                                stop = "provenance_mismatch"
                            else:
                                runtime[arm] = identity
                        row = {"case_id": control["case_id"], "arm": arm, "repetition": repetition,
                               "entrypoint": control["entrypoint"], "request": request, "response": response,
                               "cold_process_wall_ms": (time.monotonic() - began) * 1000,
                               "contract_check": contract_check(control["expected_" + arm], response),
                               "documentary_scored": False, "response_quality_scored": False}
                        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                        stream.flush()
                        rows.append(row)
                        if stop:
                            break
                    if stop:
                        break
                if stop:
                    break
        if any(path.read_bytes() != data for path, data in bench_bytes.items()) or CONTROLS.read_bytes() != fixture_bytes:
            stop = stop or "bench_source_changed"
        summary = {"schema_version": "deposium.graph-contract-summary/v1",
                   "qualification": manifest["qualification"], "completion_status": "incomplete" if stop else "complete",
                   "comparison_kind": comparison_kind, "revisions": revisions,
                   "stop_reason": stop, "controls": len(fixture["controls"]),
                   "expected_executions": len(fixture["controls"]) * repetitions * 2,
                   "observed_executions": len(rows), "arms": {},
                   "documentary_cases_scored": 0, "model_calls": 0,
                   "product_candidate_status": "not_implemented", "live_service_status": "not_observed",
                   "limits": ["Synthetic contract assertions do not qualify private documents or final answers.",
                              "Real graph services use a fresh in-memory fixture; authorization/storage mappings are simulated.",
                              "DuckPGQ capability is explicitly overridden; no native extension parity claim.",
                              "Every process/database is cold; timings do not estimate production or warm-cache latency."]}
        for arm in ("before", "after"):
            selected = [row for row in rows if row["arm"] == arm]
            summary["arms"][arm] = {"executed": len(selected), "expected": len(fixture["controls"]) * repetitions,
                                    "contract_checks_passed": sum(row["contract_check"]["passed"] for row in selected),
                                    "missing": len(fixture["controls"]) * repetitions - len(selected),
                                    "result_classes": dict(Counter(_result_class(row["response"]) for row in selected)),
                                    "outcomes": dict(Counter(row["response"].get("outcome", row["response"].get("status", "missing"))
                                                             for row in selected))}
        (target / "summary.json").write_bytes(_dump(summary))
        hashes = {path.name: _sha(path.read_bytes()) for path in sorted(target.iterdir()) if path.is_file()}
        (target / "seal.json").write_bytes(_dump({"schema_version": "deposium.graph-contract-seal/v1", "files": hashes}))
    return summary
