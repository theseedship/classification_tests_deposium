#!/usr/bin/env python3
"""Freeze facade-routing-v1 from its authored specification (issue #56); no inference.

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
from deposium_bench.facade_corpus import build_cases  # noqa: E402

from deposium_bench.facade_corpus import DIRECTORY, build  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload, manifest = build()
    validate_cases(build_cases())
    cases_path, manifest_path = DIRECTORY / "cases.jsonl", DIRECTORY / "manifest.json"
    if args.check:
        same = cases_path.read_bytes() == payload and manifest_path.read_text(encoding="utf-8") == manifest
        print(json.dumps({"status": "frozen" if same else "drift", "cases_sha256": json.loads(manifest)["cases_sha256"]}))
        return 0 if same else 1
    cases_path.write_bytes(payload)
    manifest_path.write_text(manifest, encoding="utf-8")
    print(json.dumps({"status": "written", "cases_sha256": json.loads(manifest)["cases_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
