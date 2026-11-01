"""Bounded choice observation and offline passage ranking composition.

Importing this module does not load a model. Candidate transport receives only
an opaque call ID, the declared contract, and the whitelisted choice input.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import time

from .adapters import _normalize_envelope, create_adapter, load_profile
from .campaigns import (_close_adapter, _decode, _destination, _encode, _hash,
                        _prepare_profile, _source_fingerprint, _stack_context, _write_new)
from .d3_adapter import minimum_available_mib
from .vela2_adapter import minimum_available_mib as vela2_minimum_available_mib
from .mastra_observation import memory_snapshot
from .native_supervision import NativeSupervisionError, require_native_supervision
from .passage_dataset import (CHOICE_LABELS, DEFAULT_DATASET, candidate_row,
                              export_requests, load_dataset, score_choices,
                              score_rankings, select_cases)

AXES = ("relevance", "support", "answerability")
MAX_UNIQUE_CALLS = 1200
FLOOR_MIB = 4096
# Local CPU classifiers admitted for passage choices: the pinned historical D3-lite
# profile and the macOS CPU runtime identities of the small capability rows.
LOCAL_CHOICE_MODELS = {"d3": {"vllm-sr/d3-lite", "vllm-sr/d3-nano", "vllm-sr/d3-mini"},
                       "vela2": {"vllm-sr/Vela-2.0-0.3B"}}
# One sealed pass may outlast an hour on CPU for 728 physical calls; remote and
# native sessions keep the original one-hour bound.
LOCAL_MAX_SECONDS = 6 * 3600
MACOS_RUNTIME_LOCK = "d3-macos/runtime.lock"
REMOTE_DATASET_SHA256 = "35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476"


class PassageObservationError(ValueError):
    """Pilot selection, source, archive, or prediction is untrustworthy."""


def select_pilot(cases: list[dict], split: str = "test") -> list[dict]:
    """One fixed order, all eight directions and both views; test by default."""
    selected = select_cases(cases, split=split)
    selected = [case for case in selected if case["provenance"].get("position_rotation") == 0]
    if len(selected) != 128 or len({case["family_id"] for case in selected}) != 8:
        raise PassageObservationError("Expected exactly 128 rotation-zero cases and eight families")
    if Counter((case["question_language"], case["passage_language"], case["view"])
               for case in selected) != Counter({(q, p, view): 8 for q, p in
                    (("fr", "fr"), ("en", "en"), ("de", "de"), ("es", "es"),
                     ("it", "it"), ("pt", "pt"), ("fr", "en"), ("en", "fr"))
                    for view in ("full", "head_384")}):
        raise PassageObservationError("Pilot directions or views changed")
    return selected


def choice_plan(cases: list[dict]) -> tuple[list[dict], list[dict]]:
    """Deduplicate by exact candidate-visible contract and input, never gold."""
    logical = [request for axis in AXES for request in export_requests(cases, axis)]
    physical, seen = [], {}
    for request in logical:
        candidate_row(request)  # the shared choice protocol validates each input
        digest = _hash(_encode({"contract_id": request["contract_id"], "input": request["input"]}))
        request["call_id"] = "call-" + digest
        if digest not in seen:
            seen[digest] = len(physical)
            physical.append({"case_id": request["call_id"], "contract_id": request["contract_id"],
                             "input": request["input"]})
    if len(physical) > MAX_UNIQUE_CALLS:
        raise PassageObservationError("Physical call cap exceeded")
    return logical, physical


def _seal(destination: Path) -> None:
    files = {path.name: _hash(path.read_bytes()) for path in sorted(destination.iterdir()) if path.is_file()}
    _write_new(destination / "seal.json", _encode({"schema_version": "deposium.archive-seal/v1",
                                                  "files": files, "sha256": _hash(_encode(files))}))


def _verified_files(directory: str | Path, required: set[str]) -> dict[str, bytes]:
    root = Path(directory)
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise PassageObservationError("Archive root must be a directory, not a symlink")
    # Archives are flat and self-contained. Check every entry before reading any
    # payload, including the seal; is_file() would follow links and ignore FIFOs.
    entries = list(root.iterdir())
    if any(not stat.S_ISREG(path.lstat().st_mode) for path in entries):
        raise PassageObservationError("Archive entries must be regular files, not symlinks")
    seal = _decode((root / "seal.json").read_bytes())
    files = seal.get("files")
    if (seal.get("schema_version") != "deposium.archive-seal/v1" or not isinstance(files, dict)
            or not required <= files.keys() or seal.get("sha256") != _hash(_encode(files))):
        raise PassageObservationError("Archive seal is invalid or incomplete")
    if {path.name for path in entries} != set(files) | {"seal.json"}:
        raise PassageObservationError("Unsealed or missing archive file")
    result = {}
    for name, digest in files.items():
        if name in ("", ".", "..") or Path(name).name != name or not isinstance(digest, str):
            raise PassageObservationError("Unsafe sealed path")
        payload = (root / name).read_bytes()
        if _hash(payload) != digest:
            raise PassageObservationError("Archive file hash mismatch: " + name)
        result[name] = payload
    if set(path.name for path in root.iterdir()) != set(files) | {"seal.json"}:
        raise PassageObservationError("Unsealed archive file")
    return result


def _jsonl(payload: bytes) -> list[dict]:
    if not payload:
        return []
    if not payload.endswith(b"\n"):
        raise PassageObservationError("Incomplete JSONL tail")
    return [_decode(line) for line in payload.splitlines()]


def _logical_predictions(logical: list[dict], records: list[dict]) -> list[dict]:
    indexed = {}
    for record in records:
        call_id = record["call_id"]
        if call_id in indexed:
            raise PassageObservationError("Duplicate physical response")
        indexed[call_id] = record
    rows = []
    for request in logical:
        response = indexed.get(request["call_id"], {}).get("response")
        row = {key: request[key] for key in ("case_id", "axis")}
        for key in ("passage_id", "claim_id"):
            if key in request:
                row[key] = request[key]
        row["call_id"] = request["call_id"]
        row["status"] = response["status"] if response is not None else "missing"
        if response is not None and row["status"] == "ok":
            row["choice_id"] = response["output"]["choice_id"]
        rows.append(row)
    return rows


def _scores(cases: list[dict], logical_rows: list[dict]) -> dict:
    return {axis: score_choices(cases, [{k: v for k, v in row.items() if k != "call_id"}
                                        for row in logical_rows if row["axis"] == axis and row["status"] != "missing"], axis)
            for axis in AXES}


def _resume_parent(archive: str | Path, *, split: str, cases: list[dict],
                   logical: list[dict], physical: list[dict], dataset_hash: str,
                   dataset_manifest: bytes, archived_profile: dict, source_hash: str) -> tuple[Path, str, list[dict]]:
    """Verify the sealed Jev-001 prefix before creating a new archive or adapter."""
    parent = Path(archive).expanduser().absolute()
    files = _verified_files(parent, {"cases.jsonl", "dataset-manifest.json", "manifest.json",
                                     "logical-requests.jsonl", "physical-requests.jsonl",
                                     "profile.json", "raw.jsonl", "logical-predictions.jsonl",
                                     "summary.json", "adapter-initial.json"})
    parent = parent.resolve()
    seal_hash = _hash((parent / "seal.json").read_bytes())
    manifest, summary = _decode(files["manifest.json"]), _decode(files["summary.json"])
    if (manifest.get("schema_version") != "deposium.passage-choice-observation/v1"
            or manifest.get("execution_scope") != "remote_http_model_isolated"
            or manifest.get("split") != split or manifest.get("dataset_sha256") != dataset_hash
            or manifest.get("source_profile_sha256") != source_hash
            or manifest.get("case_ids") != [case["case_id"] for case in cases]
            or manifest.get("physical_requests_sha256") != _hash(files["physical-requests.jsonl"])
            or manifest.get("logical_requests_sha256") != _hash(files["logical-requests.jsonl"])
            or files["cases.jsonl"] != b"".join(_encode(case) for case in cases)
            or files["dataset-manifest.json"] != dataset_manifest
            or files["logical-requests.jsonl"] != b"".join(_encode(request) for request in logical)
            or files["physical-requests.jsonl"] != b"".join(_encode(request) for request in physical)
            or files["profile.json"] != _encode(archived_profile)
            or manifest.get("budget", {}).get("planned_unique_calls") != len(physical)):
        raise PassageObservationError("Jev resume parent does not match the fixed plan and profile")
    rows = _jsonl(files["raw.jsonl"])
    if (summary.get("schema_version") != "deposium.passage-choice-summary/v1"
            or summary.get("completion_status") != "incomplete"
            or summary.get("stop_reason") != "adapter_unavailable"
            or summary.get("physical_attempted") != 104
            or summary.get("physical_planned") != len(physical)
            or summary.get("physical_statuses") != {"ok": 103, "error": 1}
            or len(rows) != 104
            or _logical_predictions(logical, rows) != _jsonl(files["logical-predictions.jsonl"])):
        raise PassageObservationError("Jev resume parent is not the expected incomplete prefix")
    attempts = set()
    for index, (record, request) in enumerate(zip(rows, physical)):
        response = record.get("response")
        raw = response.get("raw_output") if isinstance(response, dict) else None
        if (record.get("call_id") != request["case_id"]
                or record.get("request_sha256") != _hash(_encode(request))
                or not isinstance(record.get("adapter_wall_ms"), (int, float))
                or not isinstance(raw, dict) or raw.get("http_attempted") is not True
                or raw.get("cached_failure") is not False or raw.get("http_status") != 200
                or not isinstance(raw.get("native_result"), dict)
                or raw.get("requested_model") != archived_profile["model"]["model_id"]
                or not isinstance(raw.get("attempt_id"), str) or not raw["attempt_id"]
                or raw["attempt_id"] in attempts
                or (index < 103 and (response.get("status") != "ok" or response.get("error") is not None
                                     or raw.get("observed_model") != archived_profile["model"]["model_id"]
                                     or raw.get("usage") != raw["native_result"].get("usage")))
                or (index == 103 and (response.get("status") != "error"
                                      or response.get("error") != "jev_response_invalid"))):
            raise PassageObservationError("Jev resume parent has an invalid HTTP attempt prefix")
        attempts.add(raw["attempt_id"])
    return parent, seal_hash, rows


def _revalidate_inherited(adapter, request: dict, record: dict, parent_seal_hash: str) -> dict:
    """Reparse the saved native JSON with the current Jev adapter; never reserve or call HTTP."""
    prior = record["response"]
    old_raw = prior["raw_output"]
    native = old_raw["native_result"]
    validation_raw = deepcopy(old_raw)
    native_result, choice = adapter._response(json.dumps(native, ensure_ascii=False, allow_nan=False).encode(),
                                              deepcopy(request["input"]), validation_raw)
    if native_result != native or choice["choice_id"] not in {option["id"] for option in request["input"]["options"]}:
        raise PassageObservationError("Jev inherited native response failed offline validation")
    if prior["status"] == "ok":
        if (prior["output"] != choice or old_raw["observed_model"] != native_result["model"]
                or old_raw["usage"] != native_result["usage"]):
            raise PassageObservationError("Jev inherited successful choice changed on revalidation")
        response = deepcopy(prior)
    else:
        validation_raw.update(observed_model=native_result["model"], usage=native_result["usage"])
        response = {"status": "ok", "output": choice, "raw_output": validation_raw, "error": None}
    inherited = deepcopy(record)
    inherited["response"] = _normalize_envelope(response)
    inherited["revalidated_from"] = {"parent_seal_sha256": parent_seal_hash,
                                     "prior_status": prior["status"], "prior_error": prior["error"]}
    return inherited


def observe_choice(profile_path: str | Path, output: str | Path, *, split: str = "test",
                   max_seconds: int = 2400, dataset_path: str | Path = DEFAULT_DATASET,
                   stack_root: str | Path | None = None, adapter_factory=create_adapter,
                   memory_reader=None, allow_remote: bool = False,
                   resume_archive: str | Path | None = None) -> dict:
    """One sealed, no-retry pass; every physical response is fsynced."""
    if type(max_seconds) is not int or not 1 <= max_seconds <= LOCAL_MAX_SECONDS:
        raise PassageObservationError(f"Wall budget must be 1..{LOCAL_MAX_SECONDS} seconds")
    if split not in ("train", "calibration", "test"):
        raise PassageObservationError("Unknown split")
    path = Path(profile_path).resolve()
    profile, source_hash = load_profile(path)
    remote = profile["adapter"] == "jev_http"
    native = profile["adapter"] == "systemone_local"
    supervision = None
    if resume_archive is not None and not (remote and allow_remote):
        raise PassageObservationError("Jev resume requires --allow-remote and a Jev HTTP profile")
    if remote:
        if not allow_remote:
            raise PassageObservationError("Jev HTTP requires explicit --allow-remote")
    elif native:
        supervision = require_native_supervision(profile, path)
    elif (profile["adapter"] not in LOCAL_CHOICE_MODELS
          or profile["model"]["repo_id"] not in LOCAL_CHOICE_MODELS[profile["adapter"]]
          or profile["capabilities"] != ["bench.context-choice"] or profile["recordings"] is not None
          or (profile["model"]["repo_id"] != "vllm-sr/d3-lite"
              and Path(profile["model"]["runtime_lock"]).as_posix().rsplit("runtimes/", 1)[-1] != MACOS_RUNTIME_LOCK)):
        raise PassageObservationError("Only the pinned D3-lite profile or a macOS CPU D3/Vela 2.0 choice profile is admitted")
    if (remote or native) and max_seconds > 3600:
        raise PassageObservationError("Remote and native passage sessions keep the one-hour wall budget")
    archived_profile, normalized_hash, recordings = _prepare_profile(path)
    if normalized_hash != source_hash or recordings is not None:
        raise PassageObservationError("Profile changed during preparation")
    cases, dataset_hash = load_dataset(dataset_path)
    if remote and dataset_hash != REMOTE_DATASET_SHA256:
        raise PassageObservationError("Jev HTTP requires the pinned passage corpus")
    selected = select_pilot(cases, split)
    logical, physical = choice_plan(selected)
    if len(logical) != 1408 or len(physical) != 728:
        raise PassageObservationError("Unexpected request plan size")
    dataset_manifest = Path(dataset_path).parent.joinpath("manifest.json").read_bytes()
    parent, parent_seal_hash, inherited = (None, None, [])
    if resume_archive is not None:
        parent, parent_seal_hash, inherited = _resume_parent(
            resume_archive, split=split, cases=selected, logical=logical, physical=physical,
            dataset_hash=dataset_hash, dataset_manifest=dataset_manifest,
            archived_profile=archived_profile, source_hash=source_hash)
    if memory_reader is None:
        if native:
            from .native_resources import memory_snapshot as memory_reader
        else:
            memory_reader = memory_snapshot
    # The live matching supervisor already admits and guards this resident
    # model. Require its full host reserve, without reserving its RSS twice.
    floor = supervision.min_free_mb if native else FLOOR_MIB
    minimum = (floor if remote or native else
               max((vela2_minimum_available_mib if profile["adapter"] == "vela2" else minimum_available_mib)(profile["model"]["repo_id"]),
                   profile["model"]["max_rss_mb"] + 1024))
    before = memory_reader()
    if before.get("MemAvailable_mib", 0) < minimum:
        raise PassageObservationError("Insufficient available host RAM before observation" if remote else
                                      "Insufficient available RAM before model initialization")
    stack, preflight = _stack_context(physical, profile, stack_root)
    if stack_root is not None and (stack["inventory_status"] != "observed" or preflight is None):
        raise PassageObservationError("Configured application stack preflight unavailable")
    source = _source_fingerprint()
    destination = _destination(output, stack_root, parent_archive=parent)
    _write_new(destination / "cases.jsonl", b"".join(_encode(case) for case in selected))
    _write_new(destination / "dataset-manifest.json", dataset_manifest)
    _write_new(destination / "logical-requests.jsonl", b"".join(_encode(request) for request in logical))
    _write_new(destination / "physical-requests.jsonl", b"".join(_encode(request) for request in physical))
    _write_new(destination / "profile.json", _encode(archived_profile))
    if preflight is not None:
        _write_new(destination / "stack-preflight.json", preflight)
    manifest = {"schema_version": "deposium.passage-choice-observation/v1",
                "created_at": datetime.now(timezone.utc).isoformat(), "split": split,
                "dataset_sha256": dataset_hash, "source_profile_sha256": source_hash,
                "case_ids": [case["case_id"] for case in selected],
                "logical_requests_sha256": _hash((destination / "logical-requests.jsonl").read_bytes()),
                "physical_requests_sha256": _hash((destination / "physical-requests.jsonl").read_bytes()),
                "bench": source, "stack_context": stack, "memory_before": before,
                "budget": {"max_seconds": max_seconds, "max_unique_calls": MAX_UNIQUE_CALLS,
                           "planned_unique_calls": len(physical), "minimum_available_mib": minimum,
                           "ongoing_available_floor_mib": floor, "concurrency": 1},
                "qualification": "isolated_model_observation_agent_only_references",
                "limitations": ["One in-flight call may finish after the wall deadline.",
                                "Four passages are authored, not retrieved by the application.",
                                "No service, product answer, or human-reviewed gold is observed."]}
    if remote:
        manifest["execution_scope"] = "remote_http_model_isolated"
        manifest["resource_observation"] = {"memory_snapshots": "client_host_only",
                                            "remote_model_ram": "not_observed"}
        manifest["limitations"].append(
            "HTTP duration includes network and server time; remote model RAM and inference time are not observed.")
    if native:
        manifest["execution_scope"] = "supervised_native_model_isolated"
        manifest["native_supervision"] = supervision.provenance()
    if parent is not None:
        manifest["resume_parent"] = {"path": str(parent), "seal_sha256": parent_seal_hash,
                                     "physical_inherited": len(inherited)}
    _write_new(destination / "manifest.json", _encode(manifest))
    adapter, records, stop_reason, fatal = None, [], None, None
    initial, final = None, None
    started = time.monotonic()
    try:
        with (destination / "raw.jsonl").open("xb") as stream:
            adapter = adapter_factory(profile, path)
            initial = deepcopy(adapter.provenance)
            _write_new(destination / "adapter-initial.json", _encode(initial))
            if not initial.get("available", False):
                stop_reason = "adapter_initialization_failed"
            for request, prior in zip(physical, inherited) if stop_reason is None else ():
                record = _revalidate_inherited(adapter, request, prior, parent_seal_hash)
                stream.write(_encode(record)); stream.flush(); os.fsync(stream.fileno())
                records.append(record)
            if parent is not None and stop_reason is None:
                _verified_files(parent, {"raw.jsonl"})
                if _hash((parent / "seal.json").read_bytes()) != parent_seal_hash:
                    raise PassageObservationError("Jev resume parent changed during revalidation")
            for request in physical[len(inherited):] if stop_reason is None else ():
                if supervision is not None:
                    try:
                        supervision.check(profile, path)
                    except NativeSupervisionError:
                        stop_reason = "native_supervision_lost"
                        break
                if time.monotonic() - started >= max_seconds:
                    stop_reason = "wall_budget"
                    break
                if memory_reader().get("MemAvailable_mib", 0) < floor:
                    stop_reason = "host_memory_pressure"
                    break
                begun = time.perf_counter()
                try:
                    response = _normalize_envelope(adapter.predict(deepcopy(request)))
                    if response["status"] == "ok":
                        choice = response["output"]
                        if (not isinstance(choice, dict) or set(choice) != {"choice_id"}
                                or choice["choice_id"] not in {o["id"] for o in request["input"]["options"]}):
                            response = {"status": "error", "output": None, "raw_output": response["raw_output"],
                                        "error": "choice_outside_contract"}
                except Exception:
                    response = {"status": "error", "output": None, "raw_output": None,
                                "error": "candidate_adapter_failed"}
                record = {"call_id": request["case_id"], "request_sha256": _hash(_encode(request)),
                          "response": response, "adapter_wall_ms": (time.perf_counter() - begun) * 1000}
                stream.write(_encode(record)); stream.flush(); os.fsync(stream.fileno())
                records.append(record)
                if not adapter.provenance.get("available", True):
                    stop_reason = "adapter_unavailable"
                    break
    except KeyboardInterrupt:
        stop_reason = "interrupted"
    except Exception as exc:
        stop_reason = "observation_failed"
        fatal = type(exc).__name__
    finally:
        if adapter is not None:
            final = deepcopy(adapter.provenance)
            try:
                _close_adapter(adapter)
            except Exception:
                stop_reason = stop_reason or "adapter_close_failed"
        if supervision is not None:
            try:
                supervision.check(profile, path)
            except NativeSupervisionError:
                stop_reason = stop_reason or "native_supervision_lost"
        if _source_fingerprint()["files"] != source["files"]:
            stop_reason = "bench_source_changed"
        logical_rows = _logical_predictions(logical, records)
        scores = _scores(selected, logical_rows)
        _write_new(destination / "logical-predictions.jsonl", b"".join(_encode(row) for row in logical_rows))
        _write_new(destination / "scores.json", _encode(scores))
        summary = {"schema_version": "deposium.passage-choice-summary/v1",
                   "completion_status": "complete" if stop_reason is None and len(records) == len(physical) else "incomplete",
                   "stop_reason": stop_reason, "fatal_type": fatal,
                   "selected_cases": len(selected), "logical_decisions": len(logical),
                   "physical_planned": len(physical), "physical_attempted": len(records),
                   "physical_statuses": dict(Counter(row["response"]["status"] for row in records)),
                   "logical_statuses": {axis: scores[axis]["counts_by_status"] for axis in AXES},
                   "adapter_initial": initial, "adapter_final": final,
                   "memory_after": memory_reader(), "model_phase_wall_ms": (time.monotonic() - started) * 1000,
                   "scores": {axis: {"coverage": scores[axis]["coverage"],
                                     "accuracy_over_all": scores[axis]["accuracy_over_all"]} for axis in AXES}}
        if parent is not None:
            summary.update(physical_inherited=min(len(records), len(inherited)),
                           physical_new=max(0, len(records) - len(inherited)),
                           resume_parent_seal_sha256=parent_seal_hash)
        _write_new(destination / "summary.json", _encode(summary))
        _seal(destination)
    return summary


def compose_rankings(cases: list[dict], logical_rows: list[dict], baseline: list[dict]) -> dict:
    """Replacement and additive rankings; no inference and no hidden gold in ordering."""
    # Reuse scorer validation before reading baseline orders. Omitted rows remain
    # missing in every denominator; unknown or duplicate IDs are rejected.
    baseline_report = score_rankings(cases, baseline)
    baseline_by_id = {row["case_id"]: row for row in baseline}
    relevance = {(row["case_id"], row["passage_id"]): row for row in logical_rows
                 if row["axis"] == "relevance"}
    answerability = {row["case_id"]: row for row in logical_rows if row["axis"] == "answerability"}
    replacement, complement, gates = [], [], []
    for case in cases:
        cid = case["case_id"]
        original = [passage["id"] for passage in case["passages"]]
        grades = [relevance.get((cid, pid)) for pid in original]
        valid = all(row is not None and row["status"] == "ok" for row in grades)
        if valid:
            predicted = {pid: CHOICE_LABELS["relevance"][row["choice_id"]] for pid, row in zip(original, grades)}
            replacement.append({"case_id": cid, "status": "ok",
                                "ranking": sorted(original, key=lambda pid: -predicted[pid])})
        else:
            failures = [row["status"] if row is not None else "missing" for row in grades]
            status = next((name for name in ("error", "timeout", "unsupported", "abstain", "missing")
                           if name in failures), "missing")
            replacement.append({"case_id": cid, "status": status})
        base = baseline_by_id.get(cid, {"status": "missing"})
        if valid and base["status"] == "ok":
            complement.append({"case_id": cid, "status": "ok",
                               "ranking": sorted(base["ranking"], key=lambda pid: -predicted[pid])})
        else:
            complement.append({"case_id": cid, "status": base["status"] if base["status"] != "ok" else replacement[-1]["status"]})
        gate = answerability.get(cid)
        gates.append({"case_id": cid, "status": gate["status"] if gate else "missing",
                      "decision": CHOICE_LABELS["answerability"][gate["choice_id"]]
                      if gate and gate["status"] == "ok" else None})
    return {"baseline": baseline_report, "replacement": score_rankings(cases, [r for r in replacement if r["status"] != "missing"]),
            "complement": score_rankings(cases, [r for r in complement if r["status"] != "missing"]),
            "replacement_predictions": replacement, "complement_predictions": complement,
            "full_pool_answerability_gate": gates}


def analyze(choice_archive: str | Path, baseline_predictions: str | Path, output: str | Path) -> dict:
    """Read two sealed inputs and write a new sealed derived archive."""
    source = Path(choice_archive).expanduser().absolute()
    choice_files = _verified_files(source, {"cases.jsonl", "dataset-manifest.json", "manifest.json",
                                             "logical-requests.jsonl", "physical-requests.jsonl",
                                             "raw.jsonl", "logical-predictions.jsonl", "scores.json", "summary.json"})
    baseline_path = Path(baseline_predictions).expanduser().absolute()
    baseline_files = _verified_files(baseline_path.parent, {baseline_path.name})
    source = source.resolve()
    baseline_path = baseline_path.resolve()
    destination_path = Path(output).expanduser().resolve()
    if any(destination_path.is_relative_to(parent) for parent in (source, baseline_path.parent)):
        raise PassageObservationError("A derived archive must be outside both source archives")
    cases = _jsonl(choice_files["cases.jsonl"])
    manifest = _decode(choice_files["manifest.json"])
    if [case["case_id"] for case in cases] != manifest.get("case_ids"):
        raise PassageObservationError("Choice archive case identities changed")
    logical = _jsonl(choice_files["logical-predictions.jsonl"])
    expected = [row for row in _jsonl(choice_files["logical-requests.jsonl"])]
    if (len(logical) != len(expected) or any(tuple(row.get(k) for k in ("case_id", "axis", "passage_id", "claim_id", "call_id")) !=
                                               tuple(req.get(k) for k in ("case_id", "axis", "passage_id", "claim_id", "call_id"))
                                               for row, req in zip(logical, expected))):
        raise PassageObservationError("Choice logical predictions do not match requests")
    # Check that logical predictions actually derive from sealed physical responses.
    physical = _jsonl(choice_files["physical-requests.jsonl"])
    raw = _jsonl(choice_files["raw.jsonl"])
    if (len(raw) > len(physical) or any(row.get("call_id") != request["case_id"] or
                                        row.get("request_sha256") != _hash(_encode(request))
                                        for row, request in zip(raw, physical))):
        raise PassageObservationError("Physical trace does not match request plan")
    reconstructed = _logical_predictions(expected, raw)
    if reconstructed != logical:
        raise PassageObservationError("Choice predictions differ from physical trace")
    baseline = _jsonl(baseline_files[baseline_path.name])
    report = compose_rankings(cases, logical, baseline)
    destination = _destination(output, None, parent_archive=source)
    _write_new(destination / "analysis.json", _encode(report))
    _write_new(destination / "parents.json", _encode({"choice_archive": str(source),
                    "choice_seal_sha256": _hash((source / "seal.json").read_bytes()),
                    "baseline_predictions": str(baseline_path),
                    "baseline_seal_sha256": _hash((baseline_path.parent / "seal.json").read_bytes())}))
    _seal(destination)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    choice = commands.add_parser("choice")
    choice.add_argument("--profile", required=True)
    choice.add_argument("--output", required=True)
    choice.add_argument("--split", default="test", choices=("train", "calibration", "test"))
    choice.add_argument("--max-seconds", type=int, default=2400)
    choice.add_argument("--allow-remote", action="store_true")
    choice.add_argument("--resume-archive")
    choice.add_argument("--stack-root", default=os.environ.get("DEPOSIUM_STACK_ROOT"))
    derived = commands.add_parser("analyze")
    derived.add_argument("--choice-archive", required=True)
    derived.add_argument("--baseline-predictions", required=True)
    derived.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "choice":
        result = observe_choice(args.profile, args.output, split=args.split, max_seconds=args.max_seconds,
                                stack_root=args.stack_root, allow_remote=args.allow_remote,
                                resume_archive=args.resume_archive)
    else:
        result = analyze(args.choice_archive, args.baseline_predictions, args.output)
    print(json.dumps(result if args.command == "choice" else
                     {"baseline": result["baseline"]["scoring_status"],
                      "replacement": result["replacement"]["scoring_status"],
                      "complement": result["complement"]["scoring_status"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
