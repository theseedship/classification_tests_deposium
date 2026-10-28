#!/usr/bin/env python3
"""Materialize the declared 18-case calibration grid, tokenizer only, no inference."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from deposium_bench.cases import load_cases
from deposium_bench.lengths import build_lengths, encode, sha

FAMILIES = {
    "documentary": ("catalog-active-inventory", "retrieve_answer-content-not-summary",
                    "stored_summaries-language-followup"),
    "mathematics": ("square-expansion", "chain-derivative", "transpose-chain"),
    "chemistry": ("water-balance", "combustion-balance", "aliquot-and-mix"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError("Choose a new output directory.")
    source = ROOT / "datasets/context-choice-v1/cases.jsonl"
    cases, digest = load_cases(source)
    ids = [f"ctx-{domain}-{name}-{language}" for domain, names in FAMILIES.items()
           for name in names for language in ("fr", "en")]
    selected = [case for identity in ids for case in cases if case["case_id"] == identity]
    if len(selected) != 18 or any(case["split"] != "calibration" for case in selected):
        raise ValueError("The frozen calibration selection changed.")
    output.mkdir(parents=True)
    base = output / "base.jsonl"
    base.write_bytes(b"".join(encode(case) for case in selected))
    selection = {"schema_version": "deposium.context-selection/v1", "source_sha256": digest,
                 "selected_sha256": sha(base), "script_sha256": sha(__file__), "case_ids": ids,
                 "families": 9, "split": "calibration", "expected_variants": 378,
                 "selection": "fixed by domain and declared difficulty before model predictions"}
    (output / "selection.json").write_bytes(encode(selection))
    manifest = build_lengths(base, ROOT / "profiles/julia-1-cpu-context.json", output / "lengths",
                             positions=("start", "middle", "end"))
    print(json.dumps({"case_count": manifest["case_count"], "eligible_cases": manifest["eligible_cases"],
                      "families": manifest["families"], "dataset_sha256": manifest["dataset_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
