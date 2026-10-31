#!/usr/bin/env python3
"""Freeze tool-episodes-choice-v1 from the three public episode sources.

Deterministic: every case keeps its identity, language, split, request, fixture
and eight-assertion reference. Only the input schema version and the elapsed
budget change, to the v3 ten-minute envelope that admits CPU classifier wall
time under the closed-choice step policy. Run from the repository root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.cases import load_cases  # noqa: E402
from deposium_bench.tool_episodes import CONTRACT, INPUT_VERSION_V3  # noqa: E402

SOURCES = ("tool-episodes-v1", "tool-policy-canary-v1", "tool-policy-heldout-v1")
ELAPSED_MS = 600000
OUTPUT = ROOT / "datasets/tool-episodes-choice-v1"


def _encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def build():
    cases, sources = [], []
    for name in SOURCES:
        source, digest = load_cases(ROOT / "datasets" / name / "cases.jsonl")
        selected = [c for c in source if c["contract_id"] == CONTRACT]
        for case in selected:
            case = json.loads(_encode(case))
            case["input"]["schema_version"] = INPUT_VERSION_V3
            case["input"]["budgets"]["max_elapsed_ms"] = ELAPSED_MS
            cases.append(case)
        sources.append({"dataset_id": name, "cases_sha256": digest, "episode_case_ids": [c["case_id"] for c in selected]})
    payload = "".join(_encode(c) + "\n" for c in cases).encode("utf-8")
    manifest = {
        "schema_version": "deposium.tool-episodes-choice-manifest/v1",
        "dataset_id": "tool-episodes-choice-v1", "contract_id": CONTRACT,
        "frozen_date": "2026-10-31", "status": "frozen_before_first_candidate_prediction",
        "policy_mode": "closed_choice_step_menu_v1",
        "input_schema_version": INPUT_VERSION_V3,
        "budgets": {"max_steps": 5, "max_tool_calls": 3, "max_lookup_attempts": 2, "max_elapsed_ms": ELAPSED_MS},
        "cases_file": "cases.jsonl", "cases_sha256": hashlib.sha256(payload).hexdigest(),
        "case_count": len(cases), "family_count": len({c["translation_family"] for c in cases}),
        "counts_by_language": dict(sorted(Counter(c["language"] for c in cases).items())),
        "counts_by_split": {s: sum(c["split"] == s for c in cases) for s in ("train", "calibration", "test")},
        "sources": sources,
        "derivation": "Input schema v3 and max_elapsed_ms only; identities, requests, fixtures, faults and references unchanged.",
        "reference_review": "agent_only_pending_human",
        "exposure_note": "The held-out source cases were exposed once to the generative Qwen3-4B policy (prompt v2); no closed-choice candidate has seen any case.",
    }
    return payload, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the frozen files instead of writing them")
    args = parser.parse_args()
    payload, manifest = build()
    cases_path, manifest_path = OUTPUT / "cases.jsonl", OUTPUT / "manifest.json"
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        same = cases_path.read_bytes() == payload and manifest_path.read_text() == rendered
        print(json.dumps({"status": "frozen" if same else "drift", "case_count": manifest["case_count"],
                          "cases_sha256": manifest["cases_sha256"]}))
        return 0 if same else 1
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cases_path.write_bytes(payload)
    manifest_path.write_text(rendered)
    load_cases(cases_path)
    print(json.dumps({"status": "written", "case_count": manifest["case_count"], "cases_sha256": manifest["cases_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
