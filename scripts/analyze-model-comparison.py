"""Compare sealed context-choice campaigns and optional Mastra observations offline.

Only aggregate counts, timings and selected provenance are published. No model is
loaded; the Mastra references remain pending human review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from collections import Counter
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from deposium_bench import campaigns
from deposium_bench.cases import candidate_request as base_request
from deposium_bench.context_analysis import _stats
from deposium_bench.mastra_observation import observation_summary
from deposium_bench.mastra_pilot import (DATASET as MASTRA_DATASET, PROJECTION_VERSION,
    candidate_request as mastra_request, load_review_dataset, resolve_choice)
from deposium_bench.scoring import STATUSES, summarize

SCHEMA = "deposium.model-comparison-analysis/v1"
BASE_DATASET = ROOT / "datasets/context-choice-v1/cases.jsonl"
PRODUCER_FILES = ("scripts/analyze-model-comparison.py", "deposium_bench/campaigns.py",
                  "deposium_bench/scoring.py", "deposium_bench/context_analysis.py",
                  "deposium_bench/mastra_observation.py", "deposium_bench/mastra_pilot.py")


class AnalysisError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lines(data: bytes) -> list[dict]:
    if not data or not data.endswith(b"\n") or any(not line for line in data.split(b"\n")[:-1]):
        raise AnalysisError("invalid_lf_jsonl")
    return [campaigns._decode(line) for line in data.split(b"\n")[:-1]]


def _sealed_files(path: Path, required: set[str]) -> tuple[dict[str, bytes], dict]:
    if path.is_symlink() or not path.is_dir():
        raise AnalysisError("archive_missing")
    entries = list(path.iterdir())
    if any(p.is_symlink() or not p.is_file() for p in entries):
        raise AnalysisError("archive_inventory_invalid")
    payload = {p.name: p.read_bytes() for p in entries}
    if "seal.json" not in payload:
        raise AnalysisError("archive_unsealed")
    seal = campaigns._decode(payload["seal.json"])
    files = seal.get("files")
    if (set(seal) != {"schema_version", "files", "sha256"}
        or seal["schema_version"] != "deposium.archive-seal/v1"
        or not isinstance(files, dict) or not required <= set(files)
        or set(payload) != set(files) | {"seal.json"}
        or seal["sha256"] != _sha(campaigns._encode(files))
        or any(not isinstance(name, str) or Path(name).name != name or name in {".", ".."}
               or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
               or _sha(payload[name]) != digest for name, digest in files.items())):
        raise AnalysisError("archive_seal_invalid")
    return payload, seal


def _identity(profile: dict, provenance: dict) -> dict:
    if not isinstance(profile, dict) or not isinstance(provenance, dict):
        raise AnalysisError("provenance_invalid")
    adapter = profile.get("adapter")
    if not adapter or provenance.get("adapter") != adapter:
        raise AnalysisError("provenance_invalid")
    if adapter == "systemone_local":
        # Native sessions fingerprint model, executable and launcher separately.
        # Normalize these fields for the existing offline report, without
        # rewriting the original campaign provenance or making a service call.
        try:
            identity = provenance["identity"]
            native_model = identity["model"]
            native_runtime = identity["runtime"]
            filename = Path(native_model["path"]).name
            quantization = "Q4_K_M" if filename.endswith("-Q4_K_M.gguf") else (
                "Q8_0" if filename.endswith("-Q8_0.gguf") else "unknown")
            provenance = {**provenance,
                "model_revision": native_model["revision"], "model_repo_id": native_model["repo_id"],
                "model_assets_sha256": native_model["sha256"],
                "source_revision": native_runtime["revision"],
                "binary_sha256": native_runtime["sha256"],
                "adapter_sha256": identity["adapter_sha256"],
                "runtime_lock_sha256": identity["runtime_pin"]["sha256"],
                "runtime": {"llama_cpp_revision": native_runtime["revision"]},
                "settings": {"backend": "llama.cpp", "device": native_runtime["backend_requested"],
                    "dtype": quantization, "max_length": identity["settings"]["context"],
                    "max_rss_mb": identity["max_rss_mb"], "proxy": False, "redirects": False,
                    "retry_policy": "none", "strict_encoding": True}}
        except (KeyError, TypeError):
            raise AnalysisError("native_session_identity_invalid") from None
    revision = profile.get("revision")
    if revision and provenance.get("model_revision") != revision:
        raise AnalysisError("model_revision_mismatch")
    model = profile.get("model") or {}
    repo = model.get("repo_id")
    model_id = model.get("model_id")
    if not isinstance(model_id, str) or not re.fullmatch(r"[A-Za-z0-9_.+-]{1,100}", model_id):
        model_id = None
    if repo and provenance.get("model_repo_id", repo) != repo:
        raise AnalysisError("model_repo_mismatch")
    runtime = provenance.get("runtime")
    runtime_versions = ({key: value for key, value in runtime.items()
                         if isinstance(key, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.+-]*", key)
                         and not any(word in key.lower() for word in ("secret", "token", "key", "url", "path"))
                         and isinstance(value, str) and len(value) <= 100
                         and re.fullmatch(r"[A-Za-z0-9 ._+:-]+", value)}
                        if isinstance(runtime, dict) else None)
    settings = provenance.get("settings") if isinstance(provenance.get("settings"), dict) else {}
    allowed_settings = {"backend", "backbone_dtype", "batch_size", "cache_policy", "device", "dtype", "encoding_preflight",
                        "facts", "fork", "head_length", "loading_mode", "marker_only_head", "max_input_tokens",
                        "max_length", "max_request_bytes", "max_requests", "max_rss_mb",
                        "min_interval_seconds", "mode", "multi_label", "proxy", "redirects",
                        "permutation_average", "readout_dtype", "reserved_input_tokens_per_request", "retry_policy", "shared_context",
                        "strict_encoding", "threads", "tls_verify", "trained"}
    safe_settings = {key: value for key, value in settings.items() if key in allowed_settings
                     and (type(value) in (int, float, bool) and (type(value) is bool or math.isfinite(value))
                          or isinstance(value, str) and len(value) <= 60
                          and re.fullmatch(r"[A-Za-z0-9_.+-]+", value))}
    hashes = {key: value for key, value in provenance.items()
              if key in {"adapter_sha256", "model_assets_sha256", "prompt_sha256", "runtime_lock_sha256",
                         "source_manifest_sha256", "source_assets_sha256", "binary_sha256", "worker_sha256"}
              and isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)}
    revisions = {key: value for key, value in provenance.items()
                 if key in {"source_revision", "model_revision"} and isinstance(value, str)
                 and re.fullmatch(r"[0-9a-f]{7,64}", value)}
    return {"adapter": adapter, "profile_id": profile.get("profile_id"), "model_id": model_id,
            "model_repo_id": repo, "model_revision": revision,
            "source_revision": revisions.get("source_revision"),
            "identity_sha256": provenance.get("identity_sha256"),
            "model_assets_sha256": provenance.get("model_assets_sha256"),
            "runtime": runtime_versions, "settings": safe_settings,
            "hashes": hashes, "revisions": revisions,
            "device": safe_settings.get("device"),
            "timeout_seconds": _number(profile.get("timeout_seconds")),
            "initialization_rss_mib": _number(provenance.get("load_rss_mb"))}


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def _raw(record: dict, mastra: bool = False) -> dict:
    value = (record["response"] if mastra else record).get("raw_output")
    return value if isinstance(value, dict) else {}


def _native_sequence_counts(info: dict, components: dict) -> tuple[int | None, int | None]:
    """Count complete native sequences, including requests refused before forward."""
    vector = info.get("tokens_per_option", info.get("tokens_per_pair"))
    if isinstance(vector, list) and vector and all(type(value) is int and value >= 0 for value in vector):
        return max(vector), sum(vector)
    maximum = _number(info.get("max_sequence_tokens"))
    total = _number(info.get("sum_sequence_tokens"))
    if maximum is not None and total is not None:
        return maximum, total
    maximum = _number(components.get("max_sequence_tokens"))
    total = _number(components.get("total_tokens"))
    if maximum is not None and total is not None:
        return maximum, total
    single = _number(info.get("full_input_tokens"))
    if single is None:
        single = _number(info.get("encoded_tokens", info.get("tokens")))
    return single, single


def _measurements(records: list[dict], *, mastra: bool = False) -> dict:
    total = len(records)
    raws = [_raw(record, mastra) for record in records]
    statuses = [(record["response"]["status"] if mastra else record["status"]) for record in records]
    fields = {"adapter_ms": [record["adapter_wall_ms" if mastra else "duration_ms"] for record in records]}
    for name in ("inference_ms", "decision_ms", "http_ms"):
        fields[name] = [raw.get(name) for raw in raws]
    timing = {name: {**_stats(values), "unreported_calls": total - _stats(values)["count"]}
              for name, values in fields.items()}
    successful = sum(status == "ok" for status in statuses)
    timing_ok = {name: {**_stats(ok := [value for value, status in zip(values, statuses) if status == "ok"]),
                        "unreported_calls": successful - _stats(ok)["count"]}
                 for name, values in fields.items()}
    timing_by_status = {status: {name: _stats([value for value, state in zip(values, statuses) if state == status])
                                 for name, values in fields.items()}
                        for status in STATUSES if status in statuses}
    encoding = [raw.get("encoding_info") if isinstance(raw.get("encoding_info"), dict) else {} for raw in raws]
    tokens = [info.get("encoded_tokens", info.get("tokens")) for info in encoding]
    components = [raw.get("token_components") if isinstance(raw.get("token_components"), dict) else {} for raw in raws]
    sequence_counts = [_native_sequence_counts(info, component)
                       for info, component in zip(encoding, components)]
    usage = [raw.get("usage") if isinstance(raw.get("usage"), dict) else {} for raw in raws]
    def field_stats(values):
        values = [_number(value) for value in values]
        stats = _stats(values)
        return {**stats, "unreported_calls": total - stats["count"]}
    native = {"encoded_tokens": field_stats(tokens),
              "padded_tokens": field_stats([item.get("padded", item.get("padded_tokens")) for item in components]),
              "indecis_max_sequence_tokens": field_stats([item.get("max_sequence_tokens") for item in components]),
              "indecis_sum_tokens": field_stats([item.get("total_tokens") if _number(item.get("max_sequence_tokens")) is not None
                                                  else None for item in components]),
              "full_input_tokens": field_stats([info.get("full_input_tokens") for info in encoding]),
              "max_sequence_tokens": field_stats([value[0] for value in sequence_counts]),
              "sum_sequence_tokens": field_stats([value[1] for value in sequence_counts]),
              "padded_batch_tokens": field_stats([
                  info.get("padded_batch_tokens", component.get("padded", component.get("padded_tokens")))
                  for info, component in zip(encoding, components)])}
    provider = {name: {**field_stats([item.get(name) for item in usage]),
                       "sum": sum(value for item in usage if (value := _number(item.get(name))) is not None)}
                for name in ("input_tokens", "output_tokens")}
    flags = {}
    for name, key in (("state", "stateTruncated"), ("options", "optionsTruncated"),
                      ("noma_prefix", "prefix_truncated")):
        values = [info.get(key) for info in encoding]
        flags[name] = {"true": sum(value is True for value in values),
                       "false": sum(value is False for value in values),
                       "unknown": sum(type(value) is not bool for value in values)}
    values = [(raw.get("native_result") or {}).get("usage", {}).get("truncated")
              if isinstance(raw.get("native_result"), dict) and isinstance(raw["native_result"].get("usage"), dict)
              else None for raw in raws]
    flags["native_usage"] = {"true": sum(value is True for value in values),
                             "false": sum(value is False for value in values),
                             "unknown": sum(type(value) is not bool for value in values)}
    dropped = [info.get("state_tokens_dropped") for info in encoding]
    flags["laya_state_tokens_dropped"] = {"positive": sum(_number(value) is not None and value > 0 for value in dropped),
                                           "zero": sum(_number(value) == 0 for value in dropped),
                                           "unknown": sum(_number(value) is None for value in dropped)}
    forward = [raw.get("forward_executed") for raw in raws]
    rss = field_stats([raw.get("rss_mb") for raw in raws])
    return {"timing": timing, "timing_ok": timing_ok, "timing_by_status": timing_by_status,
            "native_tokens": native, "provider_declared_tokens": provider,
            "truncation": flags, "worker_rss_mib": rss,
            "forward_execution_flags": {"true": sum(value is True for value in forward),
                                        "false": sum(value is False for value in forward),
                                        "unknown": sum(type(value) is not bool for value in forward)},
            "http_attempted": sum(raw.get("http_attempted") is True for raw in raws)}


def _visible_length(cases: list[dict], *, mastra: bool) -> dict:
    chars, words = [], []
    for case in cases:
        request = mastra_request(case) if mastra else base_request(case)
        value = request["input"]
        parts = [value.get("context", ""), value.get("question", "")]
        parts += [option.get("description", "") for option in value.get("options", [])]
        if not all(isinstance(part, str) for part in parts):
            raise AnalysisError("candidate_visible_text_invalid")
        chars.append(sum(len(part) for part in parts))
        words.append(sum(len(re.findall(r"\S+", part)) for part in parts))
    return {"definition": "sum of Unicode characters or whitespace-delimited words in candidate-visible context, question and option descriptions; excludes IDs and serialization",
            "characters": _stats(chars), "words": _stats(words)}


def _counts(rows: list[dict]) -> dict:
    total = len(rows)
    scored = sum(row["scored"] for row in rows)
    correct = sum(row["passed"] for row in rows)
    return {"total": total, "scored": scored, "correct": correct,
            "coverage": scored / total if total else None,
            "correct_over_all": correct / total if total else None,
            "correct_over_scored": correct / scored if scored else None,
            "statuses": {status: sum(row["status"] == status for row in rows) for status in STATUSES},
            "translation_families": len({row["family"] for row in rows})}


def _base_routing(cases: list[dict], records: list[dict], scores: list[dict]) -> dict:
    rows = []
    for case, record, score in zip(cases, records, scores):
        choices = (case.get("evaluation") or {}).get("oracle", {}).get("choices", {})
        if case.get("evaluation", {}).get("domain") != "documentary" or not all(isinstance(value, str) for value in choices.values()):
            continue
        expected_id = case["reference"]["assertions"][0]["value"]
        predicted_id = (record.get("output") or {}).get("choice_id") if isinstance(record.get("output"), dict) else None
        expected = choices.get(expected_id, expected_id)
        predicted = choices.get(predicted_id, predicted_id) if predicted_id is not None else record["status"]
        rows.append({"family": case["translation_family"], "language": case["language"],
                     "domain": case["evaluation"]["domain"], "expected": expected,
                     "predicted": predicted, "scored": score["scored"], "passed": score["passed"]})
    actions = sorted({row["expected"] for row in rows})
    def matrix(subset):
        return {action: dict(sorted(Counter(row["predicted"] for row in subset
                                            if row["expected"] == action).items())) for action in actions}
    by_action = {action: {"total": sum(row["expected"] == action for row in rows),
                          "scored": sum(row["expected"] == action and row["scored"] for row in rows),
                          "correct": sum(row["expected"] == action and row["passed"] for row in rows)}
                 for action in actions}
    families = [[row for row in rows if row["family"] == family]
                for family in sorted({row["family"] for row in rows})]
    complete = [pair for pair in families if len(pair) == 2 and all(row["scored"] for row in pair)]
    return {"scope": "documentary_only_semantic_action_labels", "by_reference_action": by_action, "confusion": matrix(rows),
            "confusion_by_language": {language: matrix([row for row in rows if row["language"] == language])
                                      for language in sorted({row["language"] for row in rows})},
            "translation_pairs": {"total": len(families), "complete_scored": len(complete),
                                  "same_predicted_action": sum(pair[0]["predicted"] == pair[1]["predicted"]
                                                               for pair in complete),
                                  "both_correct": sum(all(row["passed"] for row in pair) for pair in complete)}}


def _group_measurements(cases: list[dict], records: list[dict], *, mastra: bool,
                        metric: str = "native_tokens") -> dict:
    result = {}
    for key in ("domain", "language", "domain_language") if not mastra else ("language",):
        groups = {}
        for index, case in enumerate(cases):
            domain = (case.get("evaluation") or {}).get("domain", "unannotated")
            value = domain if key == "domain" else f'{domain} / {case["language"]}' if key == "domain_language" else case["language"]
            groups.setdefault(value, []).append(records[index])
        result[key] = {name: _measurements(subset, mastra=mastra)[metric]
                       for name, subset in sorted(groups.items())}
    return result


def _mastra_action_language(rows: list[dict]) -> dict:
    result = {}
    for action in ("search", "stats", "fallback"):
        result[action] = {}
        for language in sorted({row["language"] for row in rows}):
            subset = [row for row in rows if action in row["proposed_actions"] and row["language"] == language]
            valid = sum(row["valid"] for row in subset)
            agreement = sum(row["agrees_with_proposal"] for row in subset)
            result[action][language] = {"total": len(subset), "valid_decisions": valid,
                                        "agreement_count": agreement}
    return result


def _mastra_language_matrix(rows: list[dict]) -> dict:
    result = {}
    for language in sorted({row["language"] for row in rows}):
        subset = [row for row in rows if row["language"] == language]
        result[language] = {action: dict(sorted(Counter(row["predicted_action"] or row["status"]
                                                      for row in subset if action in row["proposed_actions"]).items()))
                            for action in ("search", "stats", "fallback")}
    return result


def _base(path: Path) -> dict:
    payload, seal = _sealed_files(path, {"manifest.json", "cases.jsonl", "profile.json", "raw.jsonl", "summary.json", "report.md"})
    # The common reader verifies case and raw identities, profile, hashes and framing.
    _, manifest, cases, records, parent, _ = campaigns._archive(path)
    if (_lines(payload["cases.jsonl"]) != cases or
        (payload["raw.jsonl"] and _lines(payload["raw.jsonl"]) != records) or
        len(cases) != 132 or payload["cases.jsonl"] != BASE_DATASET.read_bytes() or
        manifest.get("mode") != "run" or manifest.get("input_protocol") != "context_choice" or
        manifest.get("scorer") != campaigns._scorer_fingerprint()):
        raise AnalysisError("base_protocol_or_corpus_mismatch")
    summary = campaigns._decode(payload["summary.json"])
    metrics = summarize(cases, records)
    if (len(records) != len(cases) or metrics["scored_cases"] == 0 or
        summary.get("schema_version") != "deposium.campaign-summary/v1" or
        summary.get("completion_status") != "complete" or
        summary.get("metrics") != metrics or
        summary.get("raw_sha256") != _sha(payload["raw.jsonl"]) or
        summary.get("scorer") != manifest["scorer"]):
        raise AnalysisError("base_summary_or_coverage_invalid")
    profile = campaigns._decode(payload["profile.json"])
    identity = _identity(profile, manifest.get("adapter_provenance"))
    if profile.get("qualification") != "model_isolated" or manifest.get("qualification") != "model_isolated":
        raise AnalysisError("base_qualification_invalid")
    rows = []
    for case, score in zip(cases, metrics["rows"]):
        meta = case.get("evaluation", {})
        rows.append({"status": score["status"], "scored": score["scored"],
                     "passed": score["passed"], "family": case["translation_family"],
                     "domain": meta.get("domain", "unannotated"), "language": case["language"],
                     "difficulty": meta.get("difficulty", "unannotated"), "split": case["split"],
                     "task_type": meta.get("task_type", "unannotated"),
                     "documentary_task": meta.get("task_type", "unannotated") if meta.get("domain") == "documentary" else None})
    groups = {}
    for dimension in ("domain", "language", "domain_language", "domain_split", "difficulty", "split", "task_type", "documentary_task"):
        keys = sorted({(row["domain"], row["language"]) if dimension == "domain_language" else
                       (row["domain"], row["split"]) if dimension == "domain_split" else row[dimension]
                       for row in rows if dimension != "documentary_task" or row[dimension] is not None})
        groups[dimension] = {" / ".join(key) if isinstance(key, tuple) else key:
            _counts([row for row in rows if ((row["domain"], row["language"]) if dimension == "domain_language" else
                                         (row["domain"], row["split"]) if dimension == "domain_split" else row[dimension]) == key])
            for key in keys}
    ok = [record for record in records if record["status"] == "ok"]
    first = records[0] if records else None
    rss = [(record.get("raw_output") or {}).get("rss_mb") for record in records
           if isinstance(record.get("raw_output"), dict)]
    rss_stats = _stats(rss)
    measurements = _measurements(records)
    return {"source": {"manifest_sha256": parent["manifest_sha256"], "raw_sha256": parent["raw_sha256"],
                       "seal_sha256": _sha(payload["seal.json"]), "seal_fingerprint": seal["sha256"],
                       "dataset_sha256": manifest["dataset_sha256"], "scorer_sha256": manifest["scorer"]["sha256"],
                       "run_id": manifest.get("run_id")},
            "identity": identity, "qualification": manifest["qualification"],
            "counts": _counts(rows), "groups": groups,
            "routing": _base_routing(cases, records, metrics["rows"]),
            "measurements": measurements, "token_groups": _group_measurements(cases, records, mastra=False),
            "provider_token_groups": _group_measurements(cases, records, mastra=False,
                                                          metric="provider_declared_tokens"),
            "candidate_visible_length": _visible_length(cases, mastra=False),
            "timing": {"successful_adapter_ms": _stats([r["duration_ms"] for r in ok]),
                       "first_call": {"status": first["status"], "adapter_ms": first["duration_ms"]},
                       "successful_after_first_ms": _stats([r["duration_ms"] for r in records[1:] if r["status"] == "ok"]),
                       "initialization_ms": manifest["adapter_provenance"].get("init_wall_ms")},
            "worker_rss_mib": {**rss_stats, "unreported_calls": len(records) - rss_stats["count"]},
            "initialization_rss_mib": identity["initialization_rss_mib"]}


def _mastra(path: Path) -> dict:
    required = {"manifest.json", "cases.jsonl", "requests.jsonl", "profile.json", "raw.jsonl", "summary.json", "adapter-initial.json"}
    payload, seal = _sealed_files(path, required)
    expected_cases, digest = load_review_dataset(MASTRA_DATASET)
    cases, requests, records = (_lines(payload[name]) for name in ("cases.jsonl", "requests.jsonl", "raw.jsonl"))
    expected_requests = [mastra_request(case) for case in expected_cases]
    manifest = campaigns._decode(payload["manifest.json"])
    summary = campaigns._decode(payload["summary.json"])
    profile = campaigns._decode(payload["profile.json"])
    initial = campaigns._decode(payload["adapter-initial.json"])
    identity = _identity(profile, initial)
    if (len(expected_cases) != 24 or cases != expected_cases or payload["cases.jsonl"] != MASTRA_DATASET.read_bytes()
        or requests != expected_requests or len(records) != 24
        or manifest.get("schema_version") != "deposium.mastra-read-observation/v1"
        or manifest.get("dataset_sha256") != digest
        or manifest.get("projection_version") != PROJECTION_VERSION
        or manifest.get("requests_sha256") != _sha(payload["requests.jsonl"])
        or manifest.get("case_ids") != [case["case_id"] for case in cases]
        or manifest.get("qualification") != "isolated_model_observation"
        or manifest.get("mode") not in {"local_single_pass", "remote_single_pass"}
        or manifest.get("budget", {}).get("max_calls") != 24
        or summary.get("schema_version") != "deposium.mastra-read-observation-summary/v1"
        or summary.get("completion_status") != "complete" or summary.get("stop_reason") is not None
        or summary.get("adapter_initial") != initial
        or profile.get("qualification") != "model_isolated"):
        raise AnalysisError("mastra_protocol_or_corpus_mismatch")
    final = summary.get("adapter_final")
    if _identity(profile, final) != identity:
        raise AnalysisError("mastra_final_identity_mismatch")
    for index, (case, request, record) in enumerate(zip(cases, requests, records)):
        response = record.get("response")
        if (set(record) != {"case_id", "request_sha256", "response", "decision", "adapter_wall_ms", "selection_scored", "first_call"}
            or record["case_id"] != case["case_id"]
            or record["request_sha256"] != _sha(campaigns._encode(request))
            or record["selection_scored"] is not False or record["first_call"] is not (index == 0)
            or not isinstance(response, dict) or set(response) != {"status", "output", "raw_output", "error"}
            or response["status"] not in STATUSES
            or type(record["adapter_wall_ms"]) not in (int, float)
            or not math.isfinite(record["adapter_wall_ms"]) or record["adapter_wall_ms"] < 0):
            raise AnalysisError("mastra_raw_invalid")
        if response["status"] == "ok":
            try:
                decision = resolve_choice(case, response["output"])
            except (ValueError, TypeError, KeyError) as exc:
                raise AnalysisError("mastra_choice_invalid") from exc
            if record["decision"] != decision:
                raise AnalysisError("mastra_choice_invalid")
        elif record["decision"] is not None:
            raise AnalysisError("mastra_choice_invalid")
    metrics = observation_summary(cases, records)
    archived_metrics = summary.get("metrics")
    def agrees_archived(old, current, location=""):
        # Early archives predate HTTP/status timing fields. Their old
        # forward_executed=0 meant "no reported forwards", now "unknown".
        if location == "/forward_executed" and old == 0 and current is None:
            return True
        if isinstance(old, dict) and isinstance(current, dict):
            return all(key in current and agrees_archived(value, current[key], location + "/" + key)
                       for key, value in old.items())
        return old == current
    if (not isinstance(archived_metrics, dict)
        or not {"coverage", "by_language", "by_split", "rows"} <= set(archived_metrics)
        or not agrees_archived(archived_metrics, metrics) or metrics["coverage"]["total"] != 24):
        raise AnalysisError("mastra_summary_mismatch")
    ok = [r for r in records if r["response"]["status"] == "ok"]
    rss = [(r["response"].get("raw_output") or {}).get("rss_mb") for r in records
           if isinstance(r["response"].get("raw_output"), dict)]
    rss_stats = _stats(rss)
    measurements = _measurements(records, mastra=True)
    return {"source": {"manifest_sha256": _sha(payload["manifest.json"]),
                       "raw_sha256": _sha(payload["raw.jsonl"]), "seal_sha256": _sha(payload["seal.json"]),
                       "seal_fingerprint": seal["sha256"], "dataset_sha256": digest,
                       "requests_sha256": manifest["requests_sha256"], "projection_version": PROJECTION_VERSION},
            "identity": identity, "qualification": "provisional_agreement_pending_human_review",
            "cases_scored": 0, "reference_review": "pending_human",
            "coverage": {k: v for k, v in metrics["coverage"].items() if k != "statuses"},
            "statuses": {status: metrics["coverage"]["statuses"].get(status, 0) for status in STATUSES},
            "by_language": metrics["by_language"], "by_split": metrics["by_split"],
            "by_proposed_action": metrics["by_proposed_action"],
            "by_proposed_action_language": _mastra_action_language(metrics["rows"]),
            "action_matrix": metrics["action_matrix"],
            "action_matrix_by_language": _mastra_language_matrix(metrics["rows"]),
            "paired_languages": metrics["paired_languages"],
            "measurements": measurements, "token_groups": _group_measurements(cases, records, mastra=True),
            "provider_token_groups": _group_measurements(cases, records, mastra=True,
                                                          metric="provider_declared_tokens"),
            "candidate_visible_length": _visible_length(cases, mastra=True),
            "timing": {"successful_adapter_ms": _stats([r["adapter_wall_ms"] for r in ok]),
                       "first_call": {"status": records[0]["response"]["status"], "adapter_ms": records[0]["adapter_wall_ms"]},
                       "successful_after_first_ms": _stats([r["adapter_wall_ms"] for r in records[1:] if r["response"]["status"] == "ok"]),
                       "initialization_ms": initial.get("init_wall_ms")},
            "worker_rss_mib": {**rss_stats, "unreported_calls": len(records) - rss_stats["count"]},
            "initialization_rss_mib": identity["initialization_rss_mib"],
            "budget": {key: value for key, value in manifest["budget"].items()
                       if key in {"max_calls", "max_seconds", "rss_guard_mib", "concurrency"}
                       and (_number(value) is not None or value is None)}}


def _label_path(value: str) -> tuple[str, Path]:
    label, sep, path = value.partition("=")
    if not sep or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", label) or not path:
        raise argparse.ArgumentTypeError("expected LABEL=ARCHIVE with a simple unique label")
    return label, Path(path)


def _table_section(name: str, models: dict, group: str) -> list[str]:
    lines = [f"## {name}", "", "| Groupe | " + " | ".join(models) + " |",
             "|---|" + "---|" * len(models)]
    keys = sorted({key for item in models.values() for key in item["groups"][group]})
    for key in keys:
        parts = []
        for item in models.values():
            count = item["groups"][group].get(key)
            parts.append(f'{count["correct"]}/{count["scored"]}/{count["total"]}' if count else "—")
        lines.append("| " + key.replace("|", "\\|") + " | " + " | ".join(parts) + " |")
    return lines + [""]


def _metric_cell(stats: dict) -> str:
    if not stats["count"]:
        return "— (0)"
    return f'{stats["min"]:.1f} / {stats["median"]:.1f} / {stats["p95"]:.1f} / {stats["max"]:.1f} ({stats["count"]})'


def _measurement_table(title: str, models: dict, path: tuple[str, ...], *, exclude=()) -> list[str]:
    names = sorted({name for item in models.values() for name in item["measurements"][path[0]]} - set(exclude))
    lines = [f"## {title}", "", "Min / médiane / p95 / max (n observé) ; — indique aucune mesure.", "",
             "| Mesure | " + " | ".join(models) + " |", "|---|" + "---:|" * len(models)]
    for name in names:
        lines.append("| " + name + " | " + " | ".join(
            _metric_cell(item["measurements"][path[0]][name]) for item in models.values()) + " |")
    return lines + [""]


def _matrix_table(title: str, models: dict, key: str) -> list[str]:
    rows = sorted({(expected, predicted) for item in models.values()
                   for expected, predictions in item[key].items() for predicted in predictions})
    lines = [f"## {title}", "", "| Attendu → prédit | " + " | ".join(models) + " |",
             "|---|" + "---:|" * len(models)]
    for expected, predicted in rows:
        lines.append(f"| {expected} → {predicted} | " + " | ".join(
            str(item[key].get(expected, {}).get(predicted, 0)) for item in models.values()) + " |")
    return lines + [""]


def _status_timing_table(title: str, models: dict, *, only_ok=False) -> list[str]:
    note = "Médiane / p95 (n) ; réponses ok uniquement." if only_ok else "Médiane / p95 (n) ; temps adaptateur inclut les échecs enregistrés."
    lines = [f"## {title}", "", note, "",
             "| Statut / mesure | " + " | ".join(models) + " |", "|---|" + "---:|" * len(models)]
    for status in ("ok",) if only_ok else STATUSES:
        for metric in ("adapter_ms", "inference_ms", "decision_ms", "http_ms"):
            if not any(status in item["measurements"]["timing_by_status"] for item in models.values()):
                continue
            cells = []
            for item in models.values():
                stats = item["measurements"]["timing_by_status"].get(status, {}).get(metric)
                cells.append(f'{stats["median"]:.1f} / {stats["p95"]:.1f} ({stats["count"]})'
                             if stats and stats["count"] else "— (0)")
            lines.append(f"| {status} / {metric} | " + " | ".join(cells) + " |")
    return lines + [""]


def _token_group_table(title: str, models: dict, dimension: str, *, metric="encoded_tokens") -> list[str]:
    groups = sorted({key for item in models.values() for key in item["token_groups"][dimension]})
    label = "plus longue séquence native" if metric == "max_sequence_tokens" else "encodés"
    lines = [f"## {title}", "", f"Tokens natifs {label} : médiane / p95 (n mesuré).", "",
             "| Groupe | " + " | ".join(models) + " |", "|---|" + "---:|" * len(models)]
    for group in groups:
        cells = []
        for item in models.values():
            stats = item["token_groups"][dimension].get(group, {}).get(metric)
            cells.append(f'{stats["median"]:.1f} / {stats["p95"]:.1f} ({stats["count"]})'
                         if stats and stats["count"] else "— (0)")
        lines.append(f"| {group} | " + " | ".join(cells) + " |")
    return lines + [""]


def _provider_token_group_table(title: str, models: dict, dimension: str) -> list[str]:
    groups = sorted({key for item in models.values() for key in item["provider_token_groups"][dimension]})
    lines = [f"## {title}", "", "Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.", "",
             "| Groupe / mesure | " + " | ".join(models) + " |", "|---|" + "---:|" * len(models)]
    for group in groups:
        for metric in ("input_tokens", "output_tokens"):
            lines.append(f"| {group} / {metric} | " + " | ".join(
                _metric_cell(item["provider_token_groups"][dimension][group][metric])
                if group in item["provider_token_groups"][dimension] else "— (0)"
                for item in models.values()) + " |")
    return lines + [""]


def _visible_table(title: str, models: dict) -> list[str]:
    lines = [f"## {title}", "", "Somme des caractères Unicode ou mots séparés par espace dans le contexte, la question et les descriptions d'options visibles par tous ; exclut les identifiants et la sérialisation.", "",
             "| Mesure | " + " | ".join(models) + " |", "|---|" + "---:|" * len(models)]
    for metric in ("characters", "words"):
        lines.append("| " + metric + " | " + " | ".join(
            _metric_cell(item["candidate_visible_length"][metric]) for item in models.values()) + " |")
    return lines + [""]


def _provenance_table(title: str, models: dict) -> list[str]:
    lines = [f"## {title}", "", "Champs explicitement autorisés depuis les profils et les archives ; empreintes complètes dans analysis.json.", "",
             "| Modèle | Adaptateur / modèle | Révision modèle / source | Device / dtype / threads | Limite entrée / RSS / timeout | Runtimes sélectionnés |",
             "|---|---|---|---|---|---|"]
    for label, item in models.items():
        identity = item["identity"]
        settings = identity["settings"]
        versions = identity["runtime"] or {}
        runtime = ", ".join(f"{key}={versions[key]}" for key in ("python", "parent_python", "go", "torch", "transformers", "tokenizers", "laya", "gliner2", "noma-source") if key in versions)
        revision = identity.get("model_revision") or "—"
        source = identity.get("source_revision") or "—"
        limits = "/".join(str(settings.get(key, "—")) for key in ("max_length", "max_rss_mb")) + "/" + str(identity.get("timeout_seconds") or "—")
        dtype = settings.get("dtype", settings.get("backbone_dtype", "—"))
        if "readout_dtype" in settings:
            dtype = f'{dtype}+{settings["readout_dtype"]}(readout)'
        dev = "/".join(str(value) for value in (settings.get("device", "—"), dtype, settings.get("threads", "—")))
        lines.append(f'| {label} | {identity["adapter"]} / {identity.get("model_repo_id") or identity.get("model_id") or "—"} | {revision} / {source} | {dev} | {limits} | {runtime or "—"} |')
    return lines + [""]


def _phase_table(title: str, models: dict) -> list[str]:
    lines = [f"## {title}", "", "Initialisation, premier appel, puis médiane / p95 des appels ok suivants ; mémoire RSS observée dans le worker et couverture sur tous les appels.", "",
             "| Modèle | Init ms | Premier appel ms (statut) | Après premier ok ms (n) | RSS worker max MiB (n/total) | RSS chargement MiB |",
             "|---|---:|---|---:|---:|---:|"]
    for label, item in models.items():
        timing = item["timing"]
        after = timing["successful_after_first_ms"]
        rss = item["worker_rss_mib"]
        total = item["coverage"]["total"] if "coverage" in item else item["counts"]["total"]
        init = timing["initialization_ms"]
        first = timing["first_call"]
        lines.append(f'| {label} | {init:.1f} ' if _number(init) is not None else f'| {label} | — ')
        lines[-1] += f'| {first["adapter_ms"]:.1f} ({first["status"]}) | '
        lines[-1] += f'{after["median"]:.1f} / {after["p95"]:.1f} ({after["count"]}) | ' if after["count"] else '— (0) | '
        lines[-1] += f'{rss["max"]:.1f} ({rss["count"]}/{total}) | ' if rss["count"] else f'— (0/{total}) | '
        load = item["initialization_rss_mib"]
        lines[-1] += f'{load:.1f} |' if _number(load) is not None else '— |'
    return lines + [""]


def _truncation_table(title: str, models: dict) -> list[str]:
    lines = [f"## {title}", "", "Vrai / faux / inconnu sur tous les appels ; le compteur Laya indique état tronqué positif / zéro / inconnu.", "",
             "| Modèle | État | Options | Préfixe Noma | Usage natif | État Laya réduit |",
             "|---|---:|---:|---:|---:|---:|"]
    for label, item in models.items():
        flags = item["measurements"]["truncation"]
        fmt = lambda obj, keys: "/".join(str(obj[k]) for k in keys)
        cells = [fmt(flags[name], ("true", "false", "unknown")) for name in ("state", "options", "noma_prefix", "native_usage")]
        cells.append(fmt(flags["laya_state_tokens_dropped"], ("positive", "zero", "unknown")))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return lines + [""]


def _markdown(result: dict) -> str:
    bases = {label: result["base"][label] for label in result["base_ranking"]}
    observations = {label: result["mastra"][label] for label in result["base_ranking"]
                    if label in result["mastra"]}
    observations.update({label: result["mastra"][label] for label in sorted(result["mastra"])
                         if label not in observations})
    small_base = any(item["identity"]["adapter"] == "small_model" for item in bases.values())
    small_mastra = any(item["identity"]["adapter"] == "small_model" for item in observations.values())
    generic_keys = {"full_input_tokens", "max_sequence_tokens", "sum_sequence_tokens", "padded_batch_tokens"}
    legacy_keys = {"indecis_max_sequence_tokens", "indecis_sum_tokens"}
    lines = ["# Comparaison des modèles de choix de contexte", "",
             "Cas corrects / scorés / total ; les erreurs et absences restent dans le total.",
             "Références agent à revoir humainement ; mesures exploratoires sur modèles isolés, pas parcours produit.", "",
             "## Classement des bases", "",
             "| Modèle | Corrects / scorés / total | Statuts (ok, unsupported, missing, error, timeout, abstain) | Médiane / p95 adaptateur ok (ms) | Premier appel (ms) | RSS max observé (MiB) |",
             "|---|---:|---|---:|---:|---:|"]
    def number(value):
        return "non observé" if value is None else f"{value:.1f}"
    for label, item in bases.items():
        c, t, rss = item["counts"], item["timing"], item["worker_rss_mib"]
        status = "/".join(str(c["statuses"][s]) for s in STATUSES)
        lines.append(f'| {label} | {c["correct"]}/{c["scored"]}/{c["total"]} | {status} | '
                     f'{number(t["successful_adapter_ms"]["median"])} / {number(t["successful_adapter_ms"]["p95"])} '
                     f'({t["successful_adapter_ms"]["count"]}) | {number(t["first_call"]["adapter_ms"])} | '
                     f'{number(rss["max"])} ({rss["count"]}/{c["total"]} rapportés) |')
    lines += ["", "Le temps adaptateur exclut l'initialisation ; premier appel distingué. P95 descriptif par rang le plus proche.", ""]
    for title, group in (("Domaines", "domain"), ("Langues", "language"), ("Domaines × langues", "domain_language"),
                         ("Domaines × split", "domain_split"), ("Difficulté", "difficulty"),
                         ("Split", "split"), ("Types de tâche, tous domaines", "task_type"),
                         ("Tâches documentaires", "documentary_task")):
        lines += _table_section(title, bases, group)
    lines += _measurement_table("Temps base ok (ms)" if small_base else "Temps base (ms)",
                                bases, ("timing_ok",) if small_base else ("timing",))
    lines += _phase_table("Phases et ressources base", bases)
    lines += _status_timing_table("Temps base par statut (ms)", bases, only_ok=small_base)
    lines += _measurement_table("Tokens natifs base", bases, ("native_tokens",),
                                exclude=legacy_keys if small_base else generic_keys)
    lines += _measurement_table("Tokens déclarés par le fournisseur, base", bases, ("provider_declared_tokens",))
    group_metric = "max_sequence_tokens" if small_base else "encoded_tokens"
    lines += _token_group_table("Tokens natifs base par domaine", bases, "domain", metric=group_metric)
    lines += _token_group_table("Tokens natifs base par langue", bases, "language", metric=group_metric)
    lines += _token_group_table("Tokens natifs base par domaine × langue", bases, "domain_language", metric=group_metric)
    lines += _provider_token_group_table("Tokens fournisseur base par domaine", bases, "domain")
    lines += _provider_token_group_table("Tokens fournisseur base par langue", bases, "language")
    lines += _provider_token_group_table("Tokens fournisseur base par domaine × langue", bases, "domain_language")
    lines += _visible_table("Longueur commune des entrées base", bases)
    lines += [("Tokens natifs : `max_sequence_tokens` est la plus longue séquence par décision, "
               "`sum_sequence_tokens` additionne ses séquences et `padded_batch_tokens` relève séparément "
               "les positions allouées. Les refus pré-forward restent comptés quand le tokenizer natif a mesuré "
               "l'entrée complète. Les temps agrégés ci-dessus concernent uniquement les réponses ok. "
               "Tokens fournisseur : comptabilité postérieure à la requête, non comparable au tokenizer local. "
               "RSS : pics rapportés par worker, sans RAM serveur distant.") if small_base else
              "Tokens natifs : encodage propre à chaque adaptateur ; `indecis_max_sequence_tokens` mesure la plus longue séquence, `indecis_sum_tokens` la somme des séquences. Tokens fournisseur : comptabilité postérieure à la requête, non comparable au tokenizer local. RSS : pics rapportés par worker, sans RAM serveur distant.", ""]
    lines += _matrix_table("Confusion des actions documentaires sur la base", {label: item["routing"] for label, item in bases.items()}, "confusion")
    for language in ("fr", "en"):
        scoped = {label: {"confusion": item["routing"]["confusion_by_language"].get(language, {})}
                  for label, item in bases.items()}
        lines += _matrix_table(f"Confusion documentaire base {language.upper()}", scoped, "confusion")
    lines += ["## Cohérence des traductions documentaires FR/EN", "", "| Modèle | Paires scorées / total | Même action | Deux correctes |",
              "|---|---:|---:|---:|"]
    for label, item in bases.items():
        pair = item["routing"]["translation_pairs"]
        lines.append(f'| {label} | {pair["complete_scored"]}/{pair["total"]} | {pair["same_predicted_action"]}/{pair["complete_scored"]} | {pair["both_correct"]}/{pair["complete_scored"]} |')
    lines.append("")
    lines += _provenance_table("Provenance et limites des bases", bases)
    lines += _truncation_table("Troncature observée, base", bases)
    if result["mastra"]:
        lines += ["## Observation Mastra", "", "Accord avec propositions d'agent ; références pending_human, aucun score sémantique final.", "",
                  "| Modèle | Accord / valides / total | Statuts | Médiane / p95 adaptateur ok (ms) | RSS max observé (MiB) |", "|---|---:|---|---:|---:|"]
        for label, item in observations.items():
            c, t, rss = item["coverage"], item["timing"], item["worker_rss_mib"]
            lines.append(f'| {label} | {c["agreement_count"]}/{c["valid_decisions"]}/{c["total"]} | '
                         f'{"/".join(str(item["statuses"][s]) for s in STATUSES)} | '
                         f'{number(t["successful_adapter_ms"]["median"])} / {number(t["successful_adapter_ms"]["p95"])} | '
                         f'{number(rss["max"])} ({rss["count"]}/{c["total"]} rapportés) |')
        lines.append("")
        lines += ["## Mastra par action proposée", "", "Accords / décisions valides / total. Une proposition en attente de revue humaine ne vaut pas une référence validée.", "",
                  "| Action | " + " | ".join(observations) + " |", "|---|" + "---:|" * len(observations)]
        for action in ("search", "stats", "fallback"):
            lines.append("| " + action + " | " + " | ".join(
                f'{item["by_proposed_action"][action]["agreement_count"]}/{item["by_proposed_action"][action]["valid_decisions"]}/{item["by_proposed_action"][action]["total"]}'
                for item in observations.values()) + " |")
        lines.append("")
        lines += ["## Mastra par action proposée et langue", "", "Accords / décisions valides / total.", "",
                  "| Action / langue | " + " | ".join(observations) + " |", "|---|" + "---:|" * len(observations)]
        for action in ("search", "stats", "fallback"):
            for language in ("fr", "en"):
                lines.append(f"| {action} / {language} | " + " | ".join(
                    f'{item["by_proposed_action_language"][action][language]["agreement_count"]}/{item["by_proposed_action_language"][action][language]["valid_decisions"]}/{item["by_proposed_action_language"][action][language]["total"]}'
                    for item in observations.values()) + " |")
        lines.append("")
        lines += _matrix_table("Mastra : action proposée → action prédite", observations, "action_matrix")
        for language in ("fr", "en"):
            scoped = {label: {"action_matrix": item["action_matrix_by_language"].get(language, {})}
                      for label, item in observations.items()}
            lines += _matrix_table(f"Mastra : action proposée → prédite {language.upper()}", scoped, "action_matrix")
        lines += ["## Mastra par langue et split", "", "Accords / décisions valides / total.", "",
                  "| Groupe | " + " | ".join(observations) + " |", "|---|" + "---:|" * len(observations)]
        for key in ("by_language", "by_split"):
            for group in sorted({name for item in observations.values() for name in item[key]}):
                lines.append(f"| {key} / {group} | " + " | ".join(
                    f'{item[key][group]["agreement_count"]}/{item[key][group]["valid_decisions"]}/{item[key][group]["total"]}'
                    if group in item[key] else "—" for item in observations.values()) + " |")
        lines.append("")
        lines += _measurement_table("Temps Mastra ok (ms)" if small_mastra else "Temps Mastra (ms)",
                                    observations, ("timing_ok",) if small_mastra else ("timing",))
        lines += _phase_table("Phases et ressources Mastra", observations)
        lines += _status_timing_table("Temps Mastra par statut (ms)", observations, only_ok=small_mastra)
        lines += _measurement_table("Tokens natifs Mastra", observations, ("native_tokens",),
                                    exclude=legacy_keys if small_mastra else generic_keys)
        lines += _measurement_table("Tokens déclarés par le fournisseur, Mastra", observations, ("provider_declared_tokens",))
        lines += _token_group_table("Tokens natifs Mastra par langue", observations, "language",
                                    metric="max_sequence_tokens" if small_mastra else "encoded_tokens")
        lines += _provider_token_group_table("Tokens fournisseur Mastra par langue", observations, "language")
        lines += _visible_table("Longueur commune des entrées Mastra", observations)
        lines += _truncation_table("Troncature observée, Mastra", observations)
        lines += ["## Cohérence Mastra FR/EN", "", "| Modèle | Paires valides / total | Même action |",
                  "|---|---:|---:|"]
        for label, item in observations.items():
            pair = item["paired_languages"]
            lines.append(f'| {label} | {pair["complete_pairs"]}/12 | {pair["same_action"]}/{pair["complete_pairs"]} |')
        lines.append("")
        lines += _provenance_table("Provenance et limites Mastra", observations)
    lines += ["Sources, révisions et empreintes : voir analysis.json. Aucune sortie de cas ni contexte privé publié.", ""]
    return "\n".join(lines)


def analyze(base: list[tuple[str, Path]], output_dir: str | Path,
            mastra: list[tuple[str, Path]] | None = None) -> dict:
    mastra = mastra or []
    if not base or len({label for label, _ in base}) != len(base) or len({label for label, _ in mastra}) != len(mastra):
        raise AnalysisError("labels_invalid")
    base_paths = {label: Path(path).resolve() for label, path in base}
    mastra_paths = {label: Path(path).resolve() for label, path in mastra}
    target = Path(output_dir).absolute()
    if (target.exists() or target.is_symlink() or
        any(target.resolve().is_relative_to(path) for path in (*base_paths.values(), *mastra_paths.values()))):
        raise AnalysisError("output_not_exclusive")
    source_hashes = {name: _sha((ROOT / name).read_bytes()) for name in PRODUCER_FILES}
    bases = {label: _base(path) for label, path in base_paths.items()}
    observations = {label: _mastra(path) for label, path in mastra_paths.items()}
    bases = dict(sorted(bases.items(), key=lambda pair: (-pair[1]["counts"]["correct"], pair[0])))
    result = {"schema_version": SCHEMA, "scope": "isolated_model_observations",
              "base_reference_review": "agent_only_pending_human",
              "base_rank_order": "correct_over_all_132_descending",
              "base_ranking": list(bases),
              "producer_files_sha256": source_hashes, "base": bases, "mastra": observations}
    if (any(_sha((ROOT / name).read_bytes()) != digest for name, digest in source_hashes.items()) or
        any(_sha((path / "seal.json").read_bytes()) != bases[label]["source"]["seal_sha256"] for label, path in base_paths.items()) or
        any(_sha((path / "seal.json").read_bytes()) != observations[label]["source"]["seal_sha256"] for label, path in mastra_paths.items())):
        raise AnalysisError("source_changed_during_analysis")
    target.mkdir(parents=True, exist_ok=False)
    with (target / "analysis.json").open("xb") as stream:
        stream.write(campaigns._encode(result))
    with (target / "report.md").open("xb") as stream:
        stream.write(_markdown(result).encode("utf-8"))
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=_label_path, action="append", required=True)
    parser.add_argument("--mastra", type=_label_path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    analyze(args.base, args.output_dir, args.mastra)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
