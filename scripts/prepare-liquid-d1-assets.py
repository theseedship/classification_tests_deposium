"""Verify the pinned Liquid d1-3B snapshot and copy its small native source files.

This is an offline inventory/hash operation. It never loads or downloads a model.
The metadata must be the Hub API response with blobs=true at the pinned revision.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

REPO = "LiquidAI/d1-3B"
REVISION = "051bcc464b01b9f92942b364d9586b0ef5912432"
SOURCES = ("api.py", "hybrid.py", "lfm2_vl.py", "modeling_d1.py", "prompt.py", "runner.py")


def _shared():
    path = Path(__file__).with_name("prepare-small-decision-assets.py")
    spec = importlib.util.spec_from_file_location("prepare_small_decision_assets", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("shared asset verifier missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(model_dir, hub_metadata, source_dir, output_dir):
    shared = _shared()
    shared.MODELS["liquid3"] = (REPO, REVISION, SOURCES, "liquid3")
    return shared.prepare("liquid3", model_dir, hub_metadata, source_dir, output_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--hub-metadata", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.model_dir, args.hub_metadata, args.source_dir,
                             args.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
