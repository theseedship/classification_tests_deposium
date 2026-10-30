"""Offline passage-order planning and evidence retention from sealed observations.

This module never creates a candidate adapter or invokes inference. Projections,
physical-call identity, choice/ranking scoring and archive seals are shared with
the existing passage engine. No dataset or reference is regenerated.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import re
import stat

from .adapters import _identity, _normalize_envelope, parse_profile
from .campaigns import _decode, _destination, _encode, _hash, _write_new
from .passage_dataset import (DEFAULT_DATASET, PassageDatasetError, STATUSES,
                              _summarize, export_requests, load_dataset,
                              score_choices, score_rankings, select_cases, validate_cases)
from .passage_observation import (AXES, PassageObservationError, _jsonl, _logical_predictions,
                                  _seal, _verified_files, choice_plan, compose_rankings)

VERSION = "deposium.passage-order-retention/v1"
DATASET_SHA256 = "35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476"
ROTATIONS = (0, 1, 2, 3)
CUTOFFS = (1, 3, 4)
RULE = {
    "ranking": "shared_replacement_predicted_relevance_descending_input_order_ties",
    "cutoffs": list(CUTOFFS),
    "sufficient_set": "contains_at_least_one_frozen_minimal_evidence_set",
    "sufficient_set_eligible": "answerable_only",
    "conflict_pair": "supports_and_refutes_the_same_frozen_claim",
    "conflict_pair_eligible": "conflicting_visible_evidence_only",
    "missing_or_failed_eligible_ranking": "zero_over_eligible",
    "inapplicable_metric": "null",
    "answerability_gate": "not_applied",
    "selection": "fixed_before_any_new_candidate_predictions_no_test_tuning",
}


def _require(condition, message):
    if not condition:
        raise PassageObservationError(message)


def _pool_key(case):
    return tuple(case[key] for key in ("family_id", "question_language", "passage_language", "view"))


def _annotation_identity(annotations):
    # Frozen arrays follow passage order in v1. Compare their identities without
    # changing the dataset, the arrays supplied to scorers, or any reference.
    value = deepcopy(annotations)
    value["relevance"].sort(key=lambda row: row["passage_id"])
    value["claims"].sort(key=lambda row: row["id"])
    for claim in value["claims"]:
        claim["judgments"].sort(key=lambda row: row["passage_id"])
    value["minimal_evidence_sets"] = sorted(sorted(ids) for ids in value["minimal_evidence_sets"])
    return value


def validate_rotations(cases):
    """Require complete matched rotations of the same visible, annotated pool."""
    validate_cases(cases)
    groups = defaultdict(dict)
    for case in cases:
        rotation = case["provenance"].get("position_rotation")
        _require(type(rotation) is int and rotation in ROTATIONS, "Unknown passage rotation")
        group = groups[_pool_key(case)]
        _require(rotation not in group, "Duplicate matched pool rotation")
        group[rotation] = case
    for group in groups.values():
        _require(set(group) == set(ROTATIONS), "Every matched pool requires all four rotations")
        anchor = group[0]
        for rotation, case in group.items():
            expected = anchor["passages"][rotation:] + anchor["passages"][:rotation]
            _require(case["passages"] == expected and case["query"] == anchor["query"]
                     and case["split"] == anchor["split"]
                     and case["scenario_id"] == anchor["scenario_id"]
                     and _annotation_identity(case["annotations"]) == _annotation_identity(anchor["annotations"]),
                     "A rotation must preserve the pool, query, split and frozen references")
    return cases


def select_order_cases(cases, split="test"):
    """Select existing variants; never synthesize rotations or references."""
    _require(split in ("train", "calibration", "test"), "Unknown split")
    selected = select_cases(cases, split=split)
    validate_rotations(selected)
    counts = Counter((c["question_language"], c["passage_language"], c["view"],
                      c["provenance"]["position_rotation"]) for c in selected)
    directions = (("fr", "fr"), ("en", "en"), ("de", "de"), ("es", "es"),
                  ("it", "it"), ("pt", "pt"), ("fr", "en"), ("en", "fr"))
    expected = Counter({(q, p, view, rotation): 8 for q, p in directions
                        for view in ("full", "head_384") for rotation in ROTATIONS})
    _require(len(selected) == 512 and len({c["family_id"] for c in selected}) == 8
             and counts == expected, "Frozen passage-order selection changed")
    return selected


def build_plan(dataset_path=DEFAULT_DATASET, split="test"):
    cases, digest = load_dataset(dataset_path)
    _require(digest == DATASET_SHA256, "This plan requires the frozen passage-evidence-v1 corpus")
    selected = select_order_cases(cases, split)
    logical, physical = choice_plan(selected)
    by_axis = {}
    for axis in AXES:
        rows = [row for row in logical if row["axis"] == axis]
        by_axis[axis] = {"logical_decisions": len(rows),
                         "distinct_physical_calls": len({row["call_id"] for row in rows}),
                         "order_interpretation": ("order_visible_in_pool_input" if axis == "answerability"
                                                  else "single_passage_projection_invariant")}
    return {"schema_version": VERSION, "plan_id": "passage-order-retention-v1-20261030",
            "status": "offline_prepared_no_new_inference", "reference_review": "agent_only_pending_human",
            "dataset": {"path": "datasets/passage-evidence-v1/cases.jsonl", "sha256": digest,
                        "split": split, "pools": len(selected), "families": 8,
                        "directions": 8, "views": ["full", "head_384"], "rotations": list(ROTATIONS)},
            "logical_decisions": len(logical), "distinct_physical_calls": len(physical),
            "by_axis": by_axis,
            "logical_requests_sha256": _hash(b"".join(_encode(row) for row in logical)),
            "physical_requests_sha256": _hash(b"".join(_encode(row) for row in physical)),
            "retention_rule": deepcopy(RULE),
            "current_execution_budget": {"model_calls": 0, "network_calls": 0,
                                         "candidate_adapters_created": 0},
            "future_inference": {"status": "not_admitted_by_this_offline_plan",
                                 "required_before_first_call": ["pinned_candidate_and_runtime",
                                     "complete_native_input_preparation", "calibration_canary",
                                     "frozen_numeric_time_memory_and_request_budgets"],
                                 "maximum_distinct_test_calls_for_this_plan": len(physical),
                                 "automatic_retries": 0},
            "limitations": ["Variants share eight families; they are not independent facts.",
                            "Relevance/support rotation reuse is input invariance, not observed order robustness.",
                            "Retention is evaluated against frozen synthetic references, not generated answers.",
                            "No model, retrieval, answer-generation or product qualification follows."]}


def _compact(report):
    return {key: value for key, value in report.items() if key not in {"rows", "by"}}


def _groups(rows, metric_names):
    """Use the shared denominator/undefined-metric summarizer for every group."""
    dimensions = ("rotation", "view", "language_direction", "family_id")
    return {axis: {str(value): _compact(_summarize([r for r in rows if r[axis] == value], metric_names))
                   for value in sorted({r[axis] for r in rows})} for axis in dimensions}


def evidence_retention(cases, predictions):
    """Frozen sufficient-set/conflict-pair capture; not answer correctness."""
    ranks = score_rankings(cases, predictions)  # exact permutations, statuses, unknowns and duplicates
    indexed = {row["case_id"]: row for row in predictions}
    rows = []
    names = [f"{metric}@{k}" for metric in ("sufficient_set", "conflict_pair") for k in CUTOFFS]
    for case, rank in zip(cases, ranks["rows"]):
        row = deepcopy(rank)
        row["rotation"] = case["provenance"]["position_rotation"]
        row["metric_eligible"] = {}
        ranking = indexed.get(case["case_id"], {}).get("ranking") or []
        for k in CUTOFFS:
            top = set(ranking[:k])
            eligible_set = case["annotations"]["query_status"] == "answerable"
            eligible_conflict = case["annotations"]["query_status"] == "conflicting_visible_evidence"
            complete_set = any(set(evidence) <= top for evidence in case["annotations"]["minimal_evidence_sets"])
            conflict = any({"supports", "refutes"} <= {
                j["label"] for j in claim["judgments"] if j["passage_id"] in top}
                for claim in case["annotations"]["claims"])
            for metric, eligible, value in (("sufficient_set", eligible_set, complete_set),
                                             ("conflict_pair", eligible_conflict, conflict)):
                name = f"{metric}@{k}"
                row["metric_eligible"][name] = eligible
                row[name] = int(value) if eligible and row["status"] == "ok" else None
        rows.append(row)
    report = _summarize(rows, names)
    report["by_order_group"] = _groups(rows, names)
    report["rule"] = deepcopy(RULE)
    if not any(item["eligible_cases"] for item in report["metrics"].values()):
        report["scoring_status"] = "no_eligible_retention_cases"
    return {"ranking_scores": ranks, "evidence_retention": report}


def _order_summary(rows):
    complete = [row for row in rows if row["complete_valid"]]
    disagreements = sum(not row["labels_agree"] for row in complete)
    return {"matched_groups": len(rows), "complete_valid_groups": len(complete),
            "invariant_input_groups": sum(row["distinct_candidate_inputs"] == 1 for row in rows),
            "changed_input_groups": sum(row["distinct_candidate_inputs"] > 1 for row in rows),
            "status_changed_groups": sum(row["status_changed"] for row in rows),
            "label_disagreement_groups": disagreements,
            "label_disagreement_over_complete": disagreements / len(complete) if complete else None,
            "correctness_changed_groups": sum(row["correctness_changed"] for row in complete),
            "all_rotations_correct_groups": sum(row["all_correct"] for row in rows),
            "all_rotations_correct_over_all": sum(row["all_correct"] for row in rows) / len(rows) if rows else None}


def score_order(cases, logical_rows):
    """Score supplied choices and their matched rotations; no candidate calls."""
    validate_rotations(cases)
    allowed = {"case_id", "axis", "passage_id", "claim_id", "status", "choice_id", "error"}
    _require(all(isinstance(row, dict) and set(row) <= allowed | {"call_id"}
                 and row.get("axis") in AXES for row in logical_rows), "Unknown logical prediction fields or axis")
    clean = [{key: value for key, value in row.items() if key != "call_id"} for row in logical_rows]
    identity_fields = ("case_id", "axis", "passage_id", "claim_id")
    expected = {tuple(row.get(key) for key in identity_fields)
                for axis in AXES for row in export_requests(cases, axis)}
    seen = set()
    for row in clean:
        identity = tuple(row.get(key) for key in identity_fields)
        _require(identity in expected and identity not in seen and row.get("status") in STATUSES,
                 "Unknown, duplicate or invalid logical prediction")
        _require(row["status"] != "missing" or row.get("choice_id") is None,
                 "A missing prediction cannot supply a choice")
        seen.add(identity)
    by_case = {case["case_id"]: case for case in cases}
    reports = {}
    for axis in AXES:
        predictions = [row for row in clean if row["axis"] == axis and row["status"] != "missing"]
        report = score_choices(cases, predictions, axis)
        requests = export_requests(cases, axis)
        indexed = {tuple(row.get(key) for key in ("case_id", "passage_id", "claim_id")): row for row in predictions}
        matched = defaultdict(list)
        for request, scored in zip(requests, report["rows"]):
            case = by_case[request["case_id"]]
            scored["rotation"] = case["provenance"]["position_rotation"]
            key = _pool_key(case) + (request.get("passage_id"), request.get("claim_id"))
            prediction = indexed.get(tuple(request.get(k) for k in ("case_id", "passage_id", "claim_id")), {})
            matched[key].append((request, scored, prediction))
        groups = []
        for key, items in sorted(matched.items(), key=lambda pair: repr(pair[0])):
            statuses = [item[1]["status"] for item in items]
            complete = all(status == "ok" for status in statuses)
            labels = [item[2].get("choice_id") for item in items]
            correct = [item[1]["accuracy"] for item in items]
            groups.append({"family_id": key[0], "language_direction": f"{key[1]}->{key[2]}", "view": key[3],
                           "passage_id": key[4], "claim_id": key[5],
                           "distinct_candidate_inputs": len({_hash(_encode({"contract_id": r["contract_id"],
                                                                                            "input": r["input"]})) for r, _, _ in items}),
                           "counts_by_status": dict(Counter(statuses)), "complete_valid": complete,
                           "status_changed": len(set(statuses)) > 1,
                           "labels_agree": len(set(labels)) == 1 if complete else None,
                           "correctness_changed": len(set(correct)) > 1 if complete else None,
                           "all_correct": complete and all(value == 1 for value in correct)})
        report["by_order_group"] = _groups(report["rows"], ["accuracy"])
        report["order_sensitivity"] = {"overall": _order_summary(groups),
            "by": {field: {value: _order_summary([row for row in groups if row[field] == value])
                            for value in sorted({row[field] for row in groups})}
                   for field in ("family_id", "language_direction", "view")}, "rows": groups,
            "interpretation": "pool_order_visible" if axis == "answerability" else "single_passage_projection_invariant"}
        reports[axis] = report
    # Use only the existing replacement path. No external reranker or composed
    # answerability gate is silently introduced by this analysis.
    composition = compose_rankings(cases, clean, [])
    retention = evidence_retention(cases, [row for row in composition["replacement_predictions"]
                                         if row["status"] != "missing"])
    return {"schema_version": VERSION, "evaluation_status": "offline_scored_not_inference",
            "qualification": "derived_observations_pending_human_reference_review",
            "model_calls_by_this_command": 0, "source_pools": len(cases),
            "family_count": len({case["family_id"] for case in cases}),
            "choice_scores": reports, "replacement": retention,
            "replacement_predictions": composition["replacement_predictions"],
            "end_to_end_answer_quality": "not_evaluated"}


def _digest_text(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _source_identity(files, manifest, summary):
    """Validate retained identities without reopening assets or live runtimes."""
    profile, archived_profile_hash = parse_profile(files["profile.json"])
    bench = manifest.get("bench")
    _require(isinstance(bench, dict) and isinstance(bench.get("files"), dict)
             and isinstance(bench.get("version"), str) and bench["version"]
             and all(isinstance(name, str) and Path(name).name == name and name.endswith(".py")
                     and _digest_text(digest) for name, digest in bench["files"].items())
             and bench.get("sha256") == _hash(_encode(bench["files"]))
             and {"passage_dataset.py", "passage_observation.py", "choice_protocol.py", "scoring.py",
                  "campaigns.py", "adapters.py"} <= set(bench["files"])
             and _digest_text(manifest.get("source_profile_sha256")), "Source code/profile fingerprint is missing or inconsistent")
    _require(profile["capabilities"] == ["bench.context-choice"]
             and profile["adapter"] in {"recorded", "d3", "systemone_local", "jev_http"},
             "Source profile is outside the retained passage observer contract")
    initial = _decode(files["adapter-initial.json"])
    final = summary.get("adapter_final")
    _require(summary.get("adapter_initial") == initial and isinstance(final, dict),
             "Retained initial/final adapter provenance is missing or inconsistent")
    _require(not _jsonl(files["raw.jsonl"]) or initial.get("available") is True,
             "Physical observations cannot precede successful adapter admission")
    stable = {"adapter", "qualification", "capabilities", "model", "model_revision", "model_repo_id",
              "identity", "runtime", "device", "backbone_dtype", "readout_dtype", "settings", "runtime_pins"}
    stable |= {key for key in set(initial) | set(final) if key.endswith("_sha256")}
    _require(all(initial.get(key) == final.get(key) for key in stable)
             and initial.get("adapter") == profile["adapter"]
             and initial.get("qualification") == profile["qualification"]
             and initial.get("capabilities") == profile["capabilities"]
             and type(initial.get("available")) is bool and type(final.get("available")) is bool
             and _digest_text(initial.get("identity_sha256")), "Source adapter identity changed or differs from its profile")
    adapter = profile["adapter"]
    hashes = bench["files"]
    if adapter == "recorded":
        _require(profile["qualification"] == "harness_control" and profile["model"] is None
                 and profile["revision"] is None and profile["recordings"] == "recordings.jsonl"
                 and manifest.get("qualification") == "harness_control_not_model"
                 and initial.get("profile_sha256") == _identity(profile)
                 and initial.get("adapter_sha256") == hashes["adapters.py"]
                 and "recordings.jsonl" in files
                 and initial.get("recordings_sha256") == _hash(files["recordings.jsonl"]),
                 "Recorded source lacks explicit control provenance")
        normalized = {key: value for key, value in profile.items() if key != "recordings"}
        _require(initial["identity_sha256"] == _identity({"profile": normalized,
            "adapter_sha256": initial["adapter_sha256"], "recordings_sha256": initial["recordings_sha256"]}),
            "Recorded source identity fingerprint mismatch")
        recorded = {}
        expected_ids = {row["case_id"] for row in _jsonl(files["physical-requests.jsonl"])}
        for row in _jsonl(files["recordings.jsonl"]):
            _require(set(row) == {"case_id", "status", "output", "raw_output", "error"}
                     and row["case_id"] in expected_ids and row["case_id"] not in recorded,
                     "Invalid recorded control response identity")
            recorded[row["case_id"]] = _normalize_envelope({key: value for key, value in row.items() if key != "case_id"})
        _require(initial.get("recordings_count") == len(recorded) and recorded
                 and all(recorded.get(row["call_id"]) == row["response"] for row in _jsonl(files["raw.jsonl"])),
                 "Recorded control observations differ from their policy recordings")
    else:
        _require(profile["qualification"] == "model_isolated"
                 and manifest.get("qualification") == "isolated_model_observation_agent_only_references",
                 "Model source must retain its explicit isolated qualification")
        source_module = "systemone_local.py" if adapter == "systemone_local" else adapter + "_adapter.py"
        _require(_digest_text(hashes.get(source_module)), "Source adapter code fingerprint is missing")
        if adapter == "systemone_local":
            identity = initial.get("identity")
            _require(isinstance(identity, dict) and isinstance(identity.get("model"), dict)
                     and all(isinstance(identity.get(key), dict) and _digest_text(identity[key].get("sha256"))
                             for key in ("model", "runtime", "gateway", "harness", "runtime_pin"))
                     and identity["model"].get("repo_id") == profile["model"]["repo_id"]
                     and identity["model"].get("revision") == profile["revision"]
                     and identity["model"].get("alias") == profile["model"]["model_id"]
                     and initial.get("session_sha256") == profile["model"]["session_sha256"]
                     and identity.get("adapter_sha256") == hashes.get("systemone_local.py")
                     and identity.get("choice_protocol_sha256") == hashes["choice_protocol.py"]
                     and identity.get("max_rss_mb") == profile["model"]["max_rss_mb"]
                     and identity.get("settings") == {"context": profile["model"]["max_length"],
                         "parallel": 1, "concurrency": 1, "questions_per_call": 1,
                         "truncation": "reject_in_pinned_native_engine"}
                     and manifest.get("execution_scope") == "supervised_native_model_isolated",
                     "Native source model/session/code identity mismatch")
            supervision = manifest.get("native_supervision", {})
            _require(supervision.get("session_sha256") == profile["model"]["session_sha256"]
                     and supervision.get("profile_sha256") == manifest["source_profile_sha256"],
                     "Native source supervision is not bound to its source profile/session")
        else:
            path_fields = {"local_dir", "runtime_python", "assets_manifest", "prompt_path", "runtime_lock", "budget_ledger"}
            retained_model = initial.get("model")
            _require(isinstance(retained_model, dict)
                     and {k: v for k, v in retained_model.items() if k not in path_fields} ==
                         {k: v for k, v in profile["model"].items() if k not in path_fields}
                     and _digest_text(initial.get("profile_sha256"))
                     and initial.get("adapter_sha256") == hashes.get(adapter + "_adapter.py")
                     and initial.get("choice_protocol_sha256") == hashes["choice_protocol.py"],
                     "Source model settings or adapter/code identity mismatch")
            if adapter == "d3":
                from .d3_adapter import RUNTIME_NAMES
                _require(initial.get("model_revision") == profile["revision"]
                         and initial.get("model_repo_id") == profile["model"]["repo_id"]
                         and isinstance(initial.get("runtime"), dict) and initial["runtime"]
                         and isinstance(initial.get("runtime_pins"), dict) and initial["runtime_pins"]
                         and RUNTIME_NAMES <= initial["runtime_pins"].keys()
                         and all(isinstance(version, str) and len(version) <= 128
                                 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+!_-]*", version)
                                 and initial["runtime"].get(name) == version
                                 for name, version in initial["runtime_pins"].items())
                         and initial.get("device") == "cpu"
                         and initial.get("backbone_dtype") == "bfloat16" and initial.get("readout_dtype") == "float32"
                         and all(_digest_text(initial.get(key)) for key in ("worker_sha256", "model_assets_sha256",
                             "assets_manifest_sha256", "runtime_python_sha256", "runtime_lock_sha256", "prompt_sha256")),
                         "D3 source revision/runtime/assets identity is incomplete")
            else:
                _require(isinstance(initial.get("runtime"), dict) and initial["runtime"],
                         "Remote source client-runtime identity is missing")
                _require(manifest.get("execution_scope") == "remote_http_model_isolated",
                         "Remote source execution scope is missing")
    # Original profile byte hashes and normalized archived profile bytes differ
    # legitimately. Keep both; never claim that reserialization reproduces it.
    return {"profile_id": profile["profile_id"], "adapter": adapter,
            "qualification": profile["qualification"], "model_revision": profile["revision"],
            "model_repo_id": profile["model"].get("repo_id") if profile["model"] else None,
            "model_id": profile["model"].get("model_id") if profile["model"] else None,
            "source_profile_bytes_sha256": manifest["source_profile_sha256"],
            "archived_profile_bytes_sha256": archived_profile_hash,
            "adapter_identity_sha256": initial["identity_sha256"],
            "adapter_provenance_hashes": {key: value for key, value in initial.items()
                                          if key.endswith("_sha256") and _digest_text(value)},
            "adapter_identity_check": ("recorded_identity_rehashed" if adapter == "recorded" else
                                       "retained_adapter_hash_with_profile_code_and_stable_runtime_crosschecks"),
            "source_bench_version": bench["version"], "source_bench_sha256": bench["sha256"],
            "source_scorer_files_sha256": {name: hashes[name] for name in
                ("passage_dataset.py", "passage_observation.py", "choice_protocol.py", "scoring.py")},
            "retained_runtime_sha256": _hash(_encode({key: initial[key] for key in
                ("identity", "runtime", "settings", "device", "backbone_dtype", "readout_dtype", "runtime_pins") if key in initial})),
            "observed_runtime_fields_retained": sorted(key for key in ("identity", "runtime", "settings", "device") if key in initial),
            "declared_settings": {key: profile["model"][key] for key in
                ("max_length", "max_rss_mb", "device", "dtype", "backend") if profile["model"] and key in profile["model"]},
            "live_runtime_checked_by_this_command": False}


def analyze_archive(choice_archive, output, *, split="test", dataset_path=DEFAULT_DATASET):
    """Pure rescore/reuse of one sealed source; unseen wire inputs stay missing."""
    source = Path(choice_archive).expanduser().absolute()
    _require(stat.S_ISDIR(source.lstat().st_mode) and stat.S_ISREG((source / "seal.json").lstat().st_mode),
             "Source root/seal must be an ordinary directory/regular file, not a symlink or special entry")
    seal_bytes = (source / "seal.json").read_bytes()
    required = {"cases.jsonl", "dataset-manifest.json", "manifest.json", "profile.json", "adapter-initial.json",
        "logical-requests.jsonl", "physical-requests.jsonl", "raw.jsonl", "logical-predictions.jsonl",
        "scores.json", "summary.json"}
    files = _verified_files(source, required)
    _require((source / "seal.json").read_bytes() == seal_bytes, "Source seal changed during verification")
    cases, digest = load_dataset(dataset_path)
    _require(digest == DATASET_SHA256, "This analysis requires the frozen passage-evidence-v1 corpus")
    selected = select_order_cases(cases, split)
    source_cases = _jsonl(files["cases.jsonl"])
    canonical = {case["case_id"]: case for case in selected}
    _require(source_cases and all(canonical.get(case.get("case_id")) == case for case in source_cases),
             "Source archive cases differ from the frozen selected corpus")
    # Existing observation archives cover rotation zero; a future shared-runner
    # extension may retain all rotations in the same archive contract.
    allowed_selections = (selected, [case for case in selected if case["provenance"]["position_rotation"] == 0])
    _require(source_cases in allowed_selections, "Source must retain the full selected or rotation-zero case set")
    manifest = _decode(files["manifest.json"])
    source_manifest = _decode(files["dataset-manifest.json"])
    _require(manifest.get("schema_version") == "deposium.passage-choice-observation/v1"
             and manifest.get("dataset_sha256") == digest and source_manifest.get("cases_sha256") == digest
             and manifest.get("case_ids") == [case["case_id"] for case in source_cases], "Source corpus identity mismatch")
    _require(files["dataset-manifest.json"] == Path(dataset_path).parent.joinpath("manifest.json").read_bytes(),
             "Retained dataset manifest differs from the frozen release")
    source_logical, source_physical = choice_plan(source_cases)
    _require(files["logical-requests.jsonl"] == b"".join(_encode(row) for row in source_logical)
             and files["physical-requests.jsonl"] == b"".join(_encode(row) for row in source_physical)
             and manifest.get("logical_requests_sha256") == _hash(files["logical-requests.jsonl"])
             and manifest.get("physical_requests_sha256") == _hash(files["physical-requests.jsonl"]),
             "Source request plan differs from shared projections")
    raw = _jsonl(files["raw.jsonl"])
    _require(len(raw) <= len(source_physical), "Extra physical observations")
    for record, request in zip(raw, source_physical):
        _require(record.get("call_id") == request["case_id"]
                 and record.get("request_sha256") == _hash(_encode(request)), "Physical observation/request mismatch")
        response = _normalize_envelope(record["response"])
        _require(response == record["response"], "Noncanonical physical response")
        if response["status"] == "ok":
            _require(isinstance(response["output"], dict) and set(response["output"]) == {"choice_id"}
                     and response["output"]["choice_id"] in {option["id"] for option in request["input"]["options"]},
                     "Invalid observed choice output")
    _require(_logical_predictions(source_logical, raw) == _jsonl(files["logical-predictions.jsonl"]),
             "Logical predictions do not reconstruct from physical observations")
    summary = _decode(files["summary.json"])
    statuses = dict(Counter(row["response"]["status"] for row in raw))
    _require(summary.get("schema_version") == "deposium.passage-choice-summary/v1"
             and summary.get("selected_cases") == len(source_cases)
             and summary.get("logical_decisions") == len(source_logical)
             and summary.get("physical_planned") == len(source_physical)
             and summary.get("physical_attempted") == len(raw)
             and summary.get("physical_statuses") == statuses
             and summary.get("completion_status") in {"complete", "incomplete"}
             and (summary["completion_status"] != "complete" or len(raw) == len(source_physical)),
             "Source physical coverage summary differs from retained observations")
    source_identity = _source_identity(files, manifest, summary)
    logical, physical = choice_plan(selected)
    rows = _logical_predictions(logical, raw)
    report = score_order(selected, rows)
    observed = {row["call_id"] for row in raw}
    report["source_observations"] = {"source_seal_sha256": _hash(seal_bytes), "source_identity": source_identity,
        "source_declared_qualification": manifest.get("qualification", "not_declared"),
        "source_completion_status": summary["completion_status"],
        "source_physical_observations": len(raw), "source_physical_statuses": statuses,
        "target_physical_calls": len(physical),
        "target_physical_observed": sum(row["case_id"] in observed for row in physical),
        "target_physical_unobserved": sum(row["case_id"] not in observed for row in physical),
        "new_physical_calls": 0, "reuse_rule": "exact_contract_and_candidate_input_bytes_only"}
    report["plan"] = build_plan(dataset_path, split)
    report["analysis_sources_sha256"] = {"deposium_bench/" + name: _hash(Path(__file__).with_name(name).read_bytes())
        for name in ("passage_order_retention.py", "passage_dataset.py", "passage_observation.py",
                     "campaigns.py", "choice_protocol.py", "adapters.py")}
    _require(_verified_files(source, required) == files and (source / "seal.json").read_bytes() == seal_bytes,
             "Source archive changed during analysis")
    destination = _destination(output, None, parent_archive=source)
    _write_new(destination / "analysis.json", _encode(report))
    _write_new(destination / "parents.json", _encode({"choice_archive": str(source.resolve()),
        "source_seal_sha256": report["source_observations"]["source_seal_sha256"],
        "producer_sha256": _hash(Path(__file__).read_bytes()),
        "plan_sha256": _hash(_encode(report["plan"]))}))
    _seal(destination)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Print the deterministic offline plan; no model calls")
    analyze = commands.add_parser("analyze", help="Rescore one sealed observation into a new sealed archive")
    for sub in (plan, analyze):
        sub.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
        sub.add_argument("--split", choices=("train", "calibration", "test"), default="test")
    analyze.add_argument("--choice-archive", required=True)
    analyze.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        report = (build_plan(args.dataset, args.split) if args.command == "plan" else
                  analyze_archive(args.choice_archive, args.output, split=args.split, dataset_path=args.dataset))
    except (OSError, ValueError, KeyError, TypeError, PassageDatasetError):
        parser.exit(2, "Passage order/retention validation failed; no inference or qualification follows.\n")
    print(json.dumps(report if args.command == "plan" else report["source_observations"],
                     ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
