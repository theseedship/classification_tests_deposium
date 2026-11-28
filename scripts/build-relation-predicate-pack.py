#!/usr/bin/env python3
"""Build or verify the frozen synthetic relation-predicate pack."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deposium_bench.cases import parse_cases
from deposium_bench.relation_predicate_corpus import DATASET, frozen_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = frozen_files()
    cases, _ = parse_cases(files["cases.jsonl"])
    for filename, payload in files.items():
        path = DATASET / filename
        if args.check:
            if path.read_bytes() != payload:
                parser.error(f"{filename} differs from the frozen specification")
        else:
            path.write_bytes(payload)
    print(f"{len(cases)} synthetic relation-predicate cases")


if __name__ == "__main__":
    main()
