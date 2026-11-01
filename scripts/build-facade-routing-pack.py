#!/usr/bin/env python3
"""Freeze the facade-routing packs (easy, advanced, complex) from their authored specifications (issue #56); no inference.

Each request family becomes two closed-choice cases (FR, EN) asking which of
eight generic tool categories a document assistant should expose. Options are
rotated deterministically so the reference position is spread across the
eight slots. Splits per category: one train, one calibration, three test
families. Run from the repository root; --check verifies the frozen files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.cases import validate_cases  # noqa: E402
from deposium_bench.facade_corpus import PACKS, ROOT as CORPUS_ROOT, build, build_cases  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    status, drift = {}, False
    for dataset_id in PACKS:
        payload, manifest = build(dataset_id)
        validate_cases(build_cases(dataset_id))
        directory = CORPUS_ROOT / "datasets" / dataset_id
        cases_path, manifest_path = directory / "cases.jsonl", directory / "manifest.json"
        sha = json.loads(manifest)["cases_sha256"]
        if args.check:
            same = (cases_path.is_file() and cases_path.read_bytes() == payload
                    and manifest_path.read_text(encoding="utf-8") == manifest)
            drift |= not same
            status[dataset_id] = {"status": "frozen" if same else "drift", "cases_sha256": sha}
        else:
            cases_path.write_bytes(payload)
            manifest_path.write_text(manifest, encoding="utf-8")
            status[dataset_id] = {"status": "written", "cases_sha256": sha}
    print(json.dumps(status))
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
