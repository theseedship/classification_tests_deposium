"""Regenerate aggregate-only Noma pilot evidence from two sealed local archives.

No adapter, model, service, private context, per-case row or proposed reference
is exported. An archive with different code/scorer semantics must be reviewed
and rescored explicitly, rather than silently treated as the same pilot.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from deposium_bench import campaigns
from deposium_bench.context_analysis import _stats
from deposium_bench.cases import candidate_request as base_request
from deposium_bench.mastra_observation import observation_summary
from deposium_bench.mastra_pilot import (DATASET as MASTRA_DATASET, PROJECTION_VERSION,
                                         candidate_request as mastra_request,
                                         load_review_dataset, resolve_choice)
from deposium_bench.noma_adapter import REPO_ID, REVISION, SOURCE_REVISION
from deposium_bench.scoring import summarize

BASE_DATASET = ROOT / "datasets/context-choice-v1/cases.jsonl"
SCHEMA = "deposium.noma-pilot-analysis/v1"
NOMA_CODE = (ROOT / "bridges/noma-worker.py", ROOT / "deposium_bench/noma_adapter.py")
STATUSES = ("ok", "unsupported", "missing", "error", "timeout", "abstain")


class AnalysisError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_lines(data: bytes) -> list[dict]:
    """Require LF framing; Python's str.splitlines also splits private text chars."""
    if not data.endswith(b"\n"):
        raise AnalysisError("archive_jsonl_missing_lf")
    lines = data.split(b"\n")
    if lines[-1] != b"" or any(not line for line in lines[:-1]):
        raise AnalysisError("archive_jsonl_blank_record")
    return [campaigns._decode(line) for line in lines[:-1]]


def _files(root: Path) -> tuple[dict[str, bytes], dict]:
    if root.is_symlink() or not root.is_dir():
        raise AnalysisError("archive_missing")
    entries = list(root.iterdir())
    if any(entry.is_symlink() or not entry.is_file() for entry in entries):
        raise AnalysisError("archive_inventory_invalid")
    payload = {entry.name: entry.read_bytes() for entry in entries}
    if "seal.json" not in payload:
        raise AnalysisError("archive_unsealed")
    seal = campaigns._decode(payload["seal.json"])
    if (set(seal) != {"schema_version", "files", "sha256"}
            or seal["schema_version"] != "deposium.archive-seal/v1"
            or not isinstance(seal["files"], dict)
            or set(payload) != set(seal["files"]) | {"seal.json"}
            or not {"manifest.json", "cases.jsonl", "requests.jsonl", "profile.json",
                    "raw.jsonl", "summary.json", "adapter-initial.json"} <= set(seal["files"])
            or any(not isinstance(name, str) or Path(name).name != name or name in {".", ".."}
                   or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                   or _sha(payload[name]) != digest for name, digest in seal["files"].items())
            or seal["sha256"] != _sha(campaigns._encode(seal["files"]))):
        raise AnalysisError("archive_seal_invalid")
    return payload, seal


def _identity(profile: dict) -> None:
    model = profile.get("model") if isinstance(profile, dict) else None
    if (profile.get("adapter") != "noma" or profile.get("revision") != REVISION
            or profile.get("qualification") != "model_isolated"
            or profile.get("capabilities") != ["bench.context-choice"]
            or not isinstance(model, dict) or model.get("repo_id") != REPO_ID
            or model.get("source_revision") != SOURCE_REVISION):
        raise AnalysisError("archive_not_pinned_noma")


def _provenance(value: dict) -> bool:
    return (isinstance(value, dict) and value.get("adapter") == "noma"
            and value.get("model_repo_id") == REPO_ID
            and value.get("model_revision") == REVISION
            and value.get("source_revision") == SOURCE_REVISION)


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def _samples(records: list[dict], *, mastra: bool) -> dict:
    """Timings use successful calls only; first call is never mixed into steady calls."""
    rows = []
    for index, record in enumerate(records):
        status = record["response"]["status"] if mastra else record["status"]
        raw = record["response"].get("raw_output") if mastra else record.get("raw_output")
        raw = raw if isinstance(raw, dict) else {}
        first = record["first_call"] if mastra else index == 0
        rows.append((status, raw, record.get("adapter_wall_ms") if mastra else record.get("duration_ms"), first))
    ok = [row for row in rows if row[0] == "ok"]
    def timings(subset):
        return {name: _stats([value for _, raw, wall, _ in subset
                              if (value := _number(wall if name == "adapter_wall_ms"
                                                   else raw.get(name))) is not None])
                for name in ("adapter_wall_ms", "decision_ms", "inference_ms")}
    native = [_number(raw.get("native_tokens")) for _, raw, _, _ in rows
              if raw.get("forward_executed") is True]
    rss = [_number(raw.get("rss_mb")) for _, raw, _, _ in rows]
    return {
        "status_counts": {status: sum(row[0] == status for row in rows) for status in STATUSES},
        "recorded_calls": len(rows),
        "native_tokens_forwarded": _stats(native),
        "worker_rss_mib": _stats(rss),
        "native_abstain_signal": _stats([_number(raw.get("native_result", {}).get("abstain"))
                                           for _, raw, _, _ in ok if isinstance(raw.get("native_result"), dict)]),
        "native_uncertainty": _stats([_number(raw.get("native_result", {}).get("uncertainty"))
                                      for _, raw, _, _ in ok if isinstance(raw.get("native_result"), dict)]),
        "timing_ok_only": {
            "all": timings(ok), "first_call": timings([row for row in ok if row[3]]),
            "after_first_call": timings([row for row in ok if not row[3]])},
        "first_call_status": next((row[0] for row in rows if row[3]), None),
    }


def _mastra(path: Path) -> dict:
    payload, seal = _files(path)
    manifest = campaigns._decode(payload["manifest.json"])
    summary = campaigns._decode(payload["summary.json"])
    profile = campaigns._decode(payload["profile.json"])
    initial = campaigns._decode(payload["adapter-initial.json"])
    _identity(profile)
    expected_cases, expected_digest = load_review_dataset(MASTRA_DATASET)
    archived_cases = _load_lines(payload["cases.jsonl"])
    requests = _load_lines(payload["requests.jsonl"])
    records = _load_lines(payload["raw.jsonl"])
    expected_requests = [mastra_request(case) for case in expected_cases]
    if (len(expected_cases) != 24 or archived_cases != expected_cases
            or _sha(payload["cases.jsonl"]) != expected_digest
            or requests != expected_requests
            or _sha(payload["requests.jsonl"]) != manifest.get("requests_sha256")
            or manifest.get("schema_version") != "deposium.mastra-read-observation/v1"
            or manifest.get("mode") != "local_single_pass"
            or manifest.get("allow_remote") is not False
            or manifest.get("qualification") != "isolated_model_observation"
            or manifest.get("projection_version") != PROJECTION_VERSION
            or manifest.get("dataset_sha256") != expected_digest
            or manifest.get("case_ids") != [case["case_id"] for case in expected_cases]
            or manifest.get("budget", {}).get("max_calls") != 24
            or not _provenance(initial)
            or summary.get("schema_version") != "deposium.mastra-read-observation-summary/v1"
            or summary.get("completion_status") != "complete"
            or summary.get("stop_reason") is not None
            or summary.get("adapter_initial") != initial
            or not _provenance(summary.get("adapter_final"))
            or len(records) != 24):
        raise AnalysisError("mastra_archive_identity_invalid")
    for index, (case, request, record) in enumerate(zip(expected_cases, expected_requests, records)):
        if (set(record) != {"case_id", "request_sha256", "response", "decision",
                            "adapter_wall_ms", "selection_scored", "first_call"}
                or record["case_id"] != case["case_id"]
                or record["request_sha256"] != _sha(campaigns._encode(request))
                or record["selection_scored"] is not False
                or record["first_call"] is not (index == 0)
                or record["response"].get("status") not in STATUSES
                or _number(record["adapter_wall_ms"]) is None):
            raise AnalysisError("mastra_raw_projection_invalid")
        response = record["response"]
        if not isinstance(response, dict) or set(response) != {"status", "output", "raw_output", "error"}:
            raise AnalysisError("mastra_response_invalid")
        if response["status"] == "ok":
            try:
                expected_decision = resolve_choice(case, response["output"])
            except (ValueError, TypeError, KeyError) as exc:
                raise AnalysisError("mastra_decision_invalid") from exc
            if record["decision"] != expected_decision:
                raise AnalysisError("mastra_decision_invalid")
        elif record["decision"] is not None:
            raise AnalysisError("mastra_decision_invalid")
    metrics = observation_summary(expected_cases, records)
    if summary.get("metrics") != metrics:
        raise AnalysisError("mastra_summary_mismatch")
    return {
        "source": {"manifest_sha256": _sha(payload["manifest.json"]),
                   "seal_sha256": _sha(payload["seal.json"]),
                   "seal_fingerprint": seal["sha256"],
                   "files_sha256": seal["files"],
                   "dataset_sha256": expected_digest,
                   "model_revision": REVISION, "source_revision": SOURCE_REVISION},
        "completion_status": summary["completion_status"],
        "initialization": {key: initial.get(key) for key in ("runtime", "init_wall_ms", "load_ms", "load_rss_mb", "device", "dtype")},
        "qualification": metrics["qualification"],
        "cases_scored": metrics["cases_scored"],
        "human_approved_references": metrics["human_approved_references"],
        "semantic_verdict": metrics["semantic_verdict"],
        "coverage": metrics["coverage"],
        "by_language": metrics["by_language"],
        "by_split": metrics["by_split"],
        "paired_languages": metrics["paired_languages"],
        "observations": _samples(records, mastra=True),
    }


def _base_counts(rows: list[dict]) -> dict:
    total = len(rows)
    scored = sum(row["scored"] for row in rows)
    passed = sum(row["passed"] for row in rows)
    return {"total": total, "scored": scored, "passed": passed,
            "coverage": scored / total if total else None,
            "accuracy_over_all": passed / total if total else None,
            "accuracy_scored": passed / scored if scored else None,
            "statuses": {status: sum(row["status"] == status for row in rows) for status in STATUSES},
            "independent_families": len({row["family"] for row in rows})}


def _base(path: Path) -> dict:
    # Validate LF framing independently before invoking the existing campaign reader.
    if not path.is_dir() or path.is_symlink():
        raise AnalysisError("base_archive_missing")
    strict_cases = _load_lines((path / "cases.jsonl").read_bytes())
    raw_bytes = (path / "raw.jsonl").read_bytes()
    strict_raw = _load_lines(raw_bytes) if raw_bytes else []
    archive, manifest, cases, records, parent, payload = campaigns._archive(path)
    seal = campaigns._decode(payload["seal.json"]) if parent["sealed"] else {}
    if (set(archive.iterdir()) != {archive / name for name in set(seal.get("files", {})) | {"seal.json"}}
            or any(item.is_symlink() or not item.is_file() for item in archive.iterdir())
            or len(strict_cases) != len(cases) or len(strict_raw) != len(records)):
        raise AnalysisError("base_archive_inventory_invalid")
    if not parent["sealed"] or manifest.get("mode") != "run":
        raise AnalysisError("base_archive_not_original_sealed_run")
    profile = campaigns._decode(payload["profile.json"])
    _identity(profile)
    if (manifest.get("input_protocol") != "context_choice"
            or not _provenance(manifest.get("adapter_provenance"))
            or manifest.get("scorer") != campaigns._scorer_fingerprint()
            or len(cases) != 132
            or payload["cases.jsonl"] != BASE_DATASET.read_bytes()):
        raise AnalysisError("base_archive_identity_invalid")
    summary = campaigns._decode(payload["summary.json"])
    scores = summarize(cases, records)
    if (summary.get("schema_version") != "deposium.campaign-summary/v1"
            or summary.get("metrics") != scores
            or summary.get("raw_sha256") != _sha(payload["raw.jsonl"])):
        raise AnalysisError("base_summary_mismatch")
    rows = []
    for case, score in zip(cases, scores["rows"]):
        meta = case.get("evaluation", {})
        rows.append({"family": case["translation_family"], "status": score["status"],
                     "scored": score["scored"], "passed": score["passed"],
                     "domain": meta.get("domain", "unannotated"),
                     "language": case["language"], "difficulty": meta.get("difficulty", "unannotated"),
                     "split": case["split"]})
    groups = {field: {value: _base_counts([row for row in rows if row[field] == value])
                      for value in sorted({row[field] for row in rows})}
              for field in ("domain", "language", "difficulty", "split")}
    return {
        "source": {"manifest_sha256": parent["manifest_sha256"],
                   "seal_sha256": _sha(payload["seal.json"]),
                   "seal_fingerprint": campaigns._decode(payload["seal.json"])["sha256"],
                   "raw_sha256": parent["raw_sha256"],
                   "dataset_sha256": manifest["dataset_sha256"],
                   "model_revision": REVISION, "source_revision": SOURCE_REVISION,
                   "scorer_sha256": manifest["scorer"]["sha256"]},
        "completion_status": summary["completion_status"],
        "qualification": manifest["qualification"],
        "initialization": {key: manifest["adapter_provenance"].get(key)
                           for key in ("runtime", "init_wall_ms", "load_ms", "load_rss_mb", "device", "dtype")},
        "counts": _base_counts(rows),
        "groups": groups,
        "observations": _samples(records, mastra=False),
    }


def analyze(mastra: str | Path, base: str | Path, output: str | Path) -> dict:
    mastra_path, base_path, target = Path(mastra).resolve(), Path(base).resolve(), Path(output).absolute()
    if (target.exists() or target.is_symlink()
            or target.resolve().is_relative_to(mastra_path)
            or target.resolve().is_relative_to(base_path)):
        raise AnalysisError("output_not_exclusive")
    producer = Path(__file__).resolve()
    source_hashes = {str(path.relative_to(ROOT)): _sha(path.read_bytes())
                     for path in (producer, *NOMA_CODE, ROOT / "deposium_bench/campaigns.py",
                                  ROOT / "deposium_bench/scoring.py",
                                  ROOT / "deposium_bench/mastra_observation.py",
                                  ROOT / "deposium_bench/context_analysis.py")}
    result = {"schema_version": SCHEMA, "model": REPO_ID,
              "scope": "isolated local Noma; no planner, service or product path",
              "quality_limit": "Mastra agreement uses unapproved proposed references; not semantic accuracy",
              "producer_files_sha256": source_hashes,
              "mastra": _mastra(mastra_path), "base": _base(base_path)}
    if (any(_sha((ROOT / name).read_bytes()) != digest for name, digest in source_hashes.items())
            or _sha((mastra_path / "seal.json").read_bytes()) != result["mastra"]["source"]["seal_sha256"]
            or _sha((base_path / "seal.json").read_bytes()) != result["base"]["source"]["seal_sha256"]):
        raise AnalysisError("analysis_source_changed")
    with target.open("xb") as stream:
        stream.write(campaigns._encode(result))
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mastra", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    analyze(args.mastra, args.base, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
