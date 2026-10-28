"""Explicit candidate observation on unapproved Mastra choice proposals.

Shares candidate adapters and archive primitives with the campaign engine.
It reports provisional agreement, never a human-validated semantic score.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import statistics
import time

from .adapters import create_adapter, load_profile, _normalize_envelope
from .campaigns import (_close_adapter, _destination, _encode, _hash, _prepare_profile,
                        _source_fingerprint, _stack_context, _write_new)
from .mastra_pilot import (DATASET, PROJECTION_VERSION, candidate_request,
                           load_review_dataset, resolve_choice)
from .native_supervision import NativeSupervisionError, require_native_supervision


def memory_snapshot() -> dict:
    values = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                values[key + "_mib"] = int(value.strip().split()[0]) / 1024
    except (OSError, ValueError, IndexError):
        pass
    return values


def _times(values: list[float]) -> dict:
    ordered = sorted(values)
    return {"count": len(values), "median_ms": statistics.median(values) if values else None,
            "p95_ms": ordered[math.ceil(len(ordered) * .95) - 1] if values else None,
            "p95_method": "nearest_rank_descriptive_single_pass"}


def observation_summary(cases: list[dict], records: list[dict]) -> dict:
    indexed = {row["case_id"]: row for row in records}
    if len(indexed) != len(records) or not set(indexed) <= {case["case_id"] for case in cases}:
        raise ValueError("mastra observation: duplicate or unknown result")
    rows = []
    for case in cases:
        record = indexed.get(case["case_id"])
        valid = bool(record and record["response"]["status"] == "ok" and record.get("decision"))
        proposed = case["reference"]["acceptable_choices"]
        actions = {item["id"]: item["action"] for item in case["candidate_input"]["options"]}
        rows.append({"case_id": case["case_id"], "language": case["language"], "split": case["split"],
                     "family": case["translation_family"], "status": record["response"]["status"] if record else "missing",
                     "valid": valid, "proposed_actions": sorted({actions[item] for item in proposed}),
                     "predicted_action": record["decision"]["action"] if valid else None,
                     "agrees_with_proposal": bool(valid and record["decision"]["choice_id"] in proposed)})
    def counts(subset):
        valid = sum(row["valid"] for row in subset)
        agrees = sum(row["agrees_with_proposal"] for row in subset)
        return {"total": len(subset), "valid_decisions": valid, "agreement_count": agrees,
                "agreement_over_all": agrees / len(subset) if subset else None,
                "agreement_over_valid": agrees / valid if valid else None,
                "statuses": dict(Counter(row["status"] for row in subset))}
    def timings(subset):
        result = {}
        for field in ("adapter_wall_ms", "decision_ms", "inference_ms", "http_ms"):
            values = []
            for record in subset:
                raw = record["response"].get("raw_output")
                value = record.get(field) if field == "adapter_wall_ms" else raw.get(field) if isinstance(raw, dict) else None
                if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                    values.append(value)
            result[field] = _times(values)
        return result
    timing = timings(records)
    timing_by_status = {status: timings([r for r in records if r["response"]["status"] == status])
                        for status in sorted({r["response"]["status"] for r in records})}
    pairs = []
    for family in sorted({row["family"] for row in rows}):
        pair = [row for row in rows if row["family"] == family]
        if len(pair) == 2 and all(row["valid"] for row in pair):
            pairs.append(pair[0]["predicted_action"] == pair[1]["predicted_action"])
    raw_outputs = [record["response"].get("raw_output") for record in records]
    rss = [raw["rss_mb"] for raw in raw_outputs if isinstance(raw, dict)
           and type(raw.get("rss_mb")) in (float, int) and math.isfinite(raw["rss_mb"])]
    forward_flags = {"true": 0, "false": 0, "unknown": 0}
    for raw in raw_outputs:
        flag = raw.get("forward_executed") if isinstance(raw, dict) else None
        forward_flags["true" if flag is True else "false" if flag is False else "unknown"] += 1
    usages = [raw["usage"] for raw in raw_outputs if isinstance(raw, dict)
              and raw.get("http_attempted") is True and isinstance(raw.get("usage"), dict)
              and set(raw["usage"]) == {"input_tokens", "output_tokens"}
              and all(type(value) is int and value >= 0 for value in raw["usage"].values())]
    http = {"attempted": sum(isinstance(raw, dict) and raw.get("http_attempted") is True for raw in raw_outputs),
            "cached_failure": sum(isinstance(raw, dict) and type(raw.get("http_attempted")) is bool
                                  and raw.get("cached_failure") is True for raw in raw_outputs),
            "usage_observations": len(usages),
            "input_tokens": sum(usage["input_tokens"] for usage in usages) if usages else None,
            "output_tokens": sum(usage["output_tokens"] for usage in usages) if usages else None,
            "observed_models": dict(Counter(raw["observed_model"] for raw in raw_outputs
                                             if isinstance(raw, dict) and isinstance(raw.get("observed_model"), str)))}
    return {"qualification": "provisional_agreement_agent_only_references", "cases_scored": 0,
            "human_approved_references": 0, "semantic_verdict": "not_qualified",
            "coverage": counts(rows),
            "by_language": {language: counts([row for row in rows if row["language"] == language])
                            for language in sorted({row["language"] for row in rows})},
            "by_split": {split: counts([row for row in rows if row["split"] == split])
                         for split in sorted({row["split"] for row in rows})},
            "by_proposed_action": {action: counts([row for row in rows if action in row["proposed_actions"]])
                                   for action in ("search", "stats", "fallback")},
            "action_matrix": {action: dict(Counter(row["predicted_action"] or row["status"] for row in rows
                                                    if action in row["proposed_actions"]))
                              for action in ("search", "stats", "fallback")},
            "paired_languages": {"complete_pairs": len(pairs), "same_action": sum(pairs)},
            "timing": timing, "timing_scope": "all_recorded_calls_including_failures",
            "timing_by_status": timing_by_status,
            "rss_peak_reported_mib": max(rss) if rss else None,
            "forward_executed": forward_flags["true"] if forward_flags["unknown"] == 0 else None,
            "forward_execution_flags": forward_flags, "http": http,
            "rows": rows}


def observe_local(dataset: str | Path, profile_path: str | Path, output: str | Path,
                  *, stack_root: str | Path | None = None, max_seconds: int = 300,
                  allow_remote: bool = False) -> dict:
    """One bounded pass; remote Jev requires explicit opt-in, without retries."""
    if type(allow_remote) is not bool:
        raise ValueError("mastra observation: allow_remote must be boolean")
    if type(max_seconds) is not int or not 1 <= max_seconds <= 600:
        raise ValueError("mastra observation: budget must be 1..600 seconds")
    cases, digest = load_review_dataset(dataset)
    if len(cases) > 64:
        raise ValueError("mastra observation: at most 64 cases per pilot")
    data = Path(dataset).read_bytes()
    if _hash(data) != digest:
        raise ValueError("mastra observation: dataset changed before execution")
    path = Path(profile_path).resolve()
    profile, source_hash = load_profile(path)
    larger_cpu = ((profile["adapter"] == "decision2" and profile["model"]["repo_id"] == "vllm-sr/Decision-2.0-Nox-4B")
                  or (profile["adapter"] == "vela2" and profile["model"]["repo_id"] == "vllm-sr/Vela-2.0-4B")
                  or (profile["adapter"] == "small_model" and profile["model"]["mode"] == "liquid3"))
    if profile["adapter"] != "d3" and not larger_cpu and max_seconds > 300:
        raise ValueError("mastra observation: budget must be 1..300 seconds for this adapter")
    remote = profile["adapter"] == "jev_http"
    allowed = {"indecis", "julia", "gliner", "decision2", "vela2", "d3", "noma", "laya", "small_model", "systemone_local", "gliclass", "vela3_fast"} | ({"jev_http"} if allow_remote else set())
    if profile["adapter"] not in allowed or "bench.context-choice" not in profile["capabilities"]:
        raise ValueError("mastra observation: only explicit local choice models are supported")
    if remote and (len(cases) > 24 or digest != _hash(Path(DATASET).read_bytes())):
        raise ValueError("mastra observation: remote pilot requires the frozen synthetic Mastra corpus (at most 24 cases)")
    archived_profile, normalized_hash, recordings = _prepare_profile(path)
    if normalized_hash != source_hash or recordings is not None:
        raise ValueError("mastra observation: profile changed")
    snapshot = memory_snapshot
    supervision = None
    if profile["adapter"] in {"systemone_local", "gliclass", "vela3_fast"}:
        from .native_resources import memory_snapshot as snapshot
    if profile["adapter"] == "systemone_local":
        supervision = require_native_supervision(profile, path)
    before_memory = snapshot()
    min_free_mib = float(profile["model"]["max_rss_mb"]) + 1024 if not remote else None
    if profile["adapter"] == "systemone_local":
        # The matching live in-process supervisor enforces the full RSS and
        # host reserve budgets for this already resident service continuously.
        # Reserving its entire RSS budget again would count the model twice.
        min_free_mib = 1024
    if profile["adapter"] in {"gliclass", "vela3_fast"}:
        # This adapter owns and initializes a fresh worker: reserve its full RSS
        # budget before model hashing/loading, plus the shared host reserve.
        min_free_mib = float(profile["model"]["max_rss_mb"] + profile["model"]["min_free_mb"])
    if profile["adapter"] == "small_model":
        from .small_model_adapter import minimum_available_mib
        min_free_mib = max(min_free_mib, minimum_available_mib(profile["model"]["mode"]))
    if profile["adapter"] == "vela2":
        from .vela2_adapter import minimum_available_mib
        min_free_mib = max(min_free_mib, minimum_available_mib(profile["model"]["repo_id"]))
    if profile["adapter"] == "decision2":
        from .decision2_adapter import minimum_available_mib
        min_free_mib = max(min_free_mib, minimum_available_mib(profile["model"]["repo_id"]))
    if profile["adapter"] == "d3":
        from .d3_adapter import minimum_available_mib
        min_free_mib = max(min_free_mib, minimum_available_mib(profile["model"]["repo_id"]))
    if not remote and before_memory.get("MemAvailable_mib", 0) < min_free_mib:
        raise ValueError("mastra observation: insufficient available RAM for guarded local pilot")
    requests = [candidate_request(case) for case in cases]
    stack, preflight = _stack_context(requests, profile, stack_root)
    source = _source_fingerprint()
    destination = _destination(output, stack_root)
    _write_new(destination / "cases.jsonl", data)
    _write_new(destination / "requests.jsonl", b"".join(_encode(request) for request in requests))
    _write_new(destination / "profile.json", _encode(archived_profile))
    if preflight is not None:
        _write_new(destination / "stack-preflight.json", preflight)
    manifest = {"schema_version": "deposium.mastra-read-observation/v1",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "mode": "remote_single_pass" if remote else "local_single_pass", "allow_remote": allow_remote,
                "qualification": "isolated_model_observation", "projection_version": PROJECTION_VERSION,
                "dataset_sha256": digest, "source_profile_sha256": source_hash,
                "requests_sha256": _hash((destination / "requests.jsonl").read_bytes()),
                "case_ids": [case["case_id"] for case in cases], "bench": source,
                "stack_context": stack, "memory_before": before_memory,
                "budget": {"max_calls": len(cases), "max_seconds": max_seconds,
                           "rss_guard_mib": None if remote else profile["model"]["max_rss_mb"], "concurrency": 1},
                "limitations": ["References are pending human review; agreement is not accuracy.",
                                "No MCP tool, planner or product path is executed.",
                                "Single pass without warm-up; timings are descriptive and include host pressure.",
                                "Budgets checked between calls; one in-flight adapter call may finish after the wall deadline."]}
    if remote:
        manifest["budget"]["http_policy"] = {key: profile["model"][key] for key in
                                                ("max_requests", "max_input_tokens", "reserved_input_tokens_per_request",
                                                 "max_request_bytes", "min_interval_seconds")}
        manifest["limitations"].extend([
            "Explicit remote reference on synthetic cases; user requests and option descriptions leave this host.",
            "http_ms is client round-trip latency including TLS, transfer and server wait; server compute and RAM are not observed.",
            "No native tokenizer or server truncation indicator is available; usage reports provider token accounting.",
            "The shared durable HTTP budget is retained; fatal errors stop further HTTP attempts without retries."])
    if supervision is not None:
        manifest["native_supervision"] = supervision.provenance()
    _write_new(destination / "manifest.json", _encode(manifest))
    adapter = None
    records = []
    stop_reason = None
    started = time.monotonic()
    initial_provenance = None
    final_provenance = None
    try:
        if supervision is not None:
            supervision.check(profile, path)
        adapter = create_adapter(profile, path)
        initial_provenance = deepcopy(adapter.provenance)
        _write_new(destination / "adapter-initial.json", _encode(initial_provenance))
        with (destination / "raw.jsonl").open("xb") as stream:
            for case, request in zip(cases, requests):
                if time.monotonic() - started >= max_seconds:
                    stop_reason = "wall_budget"
                    break
                if not remote and snapshot().get("MemAvailable_mib", 0) < (4096 if larger_cpu else 1024):
                    stop_reason = "host_memory_pressure"
                    break
                if supervision is not None:
                    try:
                        supervision.check(profile, path)
                    except NativeSupervisionError:
                        stop_reason = "native_supervision_lost"
                        break
                call_start = time.perf_counter()
                try:
                    response = _normalize_envelope(adapter.predict(deepcopy(request)))
                except Exception:
                    response = {"status": "error", "output": None, "raw_output": None,
                                "error": "candidate_adapter_failed"}
                elapsed = (time.perf_counter() - call_start) * 1000
                if supervision is not None:
                    try:
                        supervision.check(profile, path)
                    except NativeSupervisionError:
                        stop_reason = "native_supervision_lost"
                decision = None
                if response["status"] == "ok":
                    try:
                        decision = resolve_choice(case, response["output"])
                    except (ValueError, TypeError):
                        response = {**response, "status": "error", "error": "choice_outside_contract"}
                record = {"case_id": case["case_id"], "request_sha256": _hash(_encode(request)),
                          "response": response, "decision": decision, "adapter_wall_ms": elapsed,
                          "selection_scored": False, "first_call": not records}
                stream.write(_encode(record)); stream.flush(); os.fsync(stream.fileno())
                records.append(record)
                if stop_reason is not None:
                    break
        final_provenance = deepcopy(adapter.provenance)
    except NativeSupervisionError:
        stop_reason = "native_supervision_lost"
    except KeyboardInterrupt:
        stop_reason = "interrupted"
    finally:
        if adapter is not None:
            final_provenance = deepcopy(adapter.provenance)
            _close_adapter(adapter)
    if _source_fingerprint()["files"] != source["files"]:
        stop_reason = "bench_source_changed"
    metrics = observation_summary(cases, records)
    summary = {"schema_version": "deposium.mastra-read-observation-summary/v1",
               "completion_status": "complete" if stop_reason is None and len(records) == len(cases) else "incomplete",
               "stop_reason": stop_reason, "metrics": metrics,
               "adapter_initial": initial_provenance, "adapter_final": final_provenance,
               "memory_after": snapshot(), "model_phase_wall_ms": (time.monotonic() - started) * 1000}
    _write_new(destination / "summary.json", _encode(summary))
    files = {file.name: _hash(file.read_bytes()) for file in sorted(destination.iterdir()) if file.is_file()}
    _write_new(destination / "seal.json", _encode({"schema_version": "deposium.archive-seal/v1",
                                                  "files": files, "sha256": _hash(_encode(files))}))
    return summary
