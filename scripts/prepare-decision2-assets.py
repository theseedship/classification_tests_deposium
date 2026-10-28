"""Verify the pinned Nox4 snapshot against complete Hub blob metadata, offline.

Only a new manifest is written. Model code, weights and a runtime are never
imported or downloaded by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.worker_transport import decode

HELPER = ROOT / "scripts/prepare-small-decision-assets.py"
spec = importlib.util.spec_from_file_location("small_asset_verifier", HELPER)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)

REPO_ID = "vllm-sr/Decision-2.0-Nox-4B"
REVISION = "ae269ecf34a0b3a89026bc1afd9c995279212fad"


def prepare(model_dir, metadata_path, output):
    model_dir, metadata_path, output = map(Path, (model_dir, metadata_path, output))
    if output.exists() or output.is_symlink():
        raise FileExistsError("manifest destination must be new")
    if output.resolve().is_relative_to(model_dir.resolve()):
        raise ValueError("manifest must be outside snapshot")
    metadata_bytes = metadata_path.read_bytes()
    metadata = decode(metadata_bytes)
    published = verifier._publisher_files(metadata, REPO_ID, REVISION)
    expected = set(published)
    if verifier._inventory(model_dir) != expected:
        raise ValueError("snapshot inventory differs from pinned Hub files")
    files = []
    for name in sorted(expected):
        item, path = published[name], model_dir / name
        if path.stat().st_size != item["size"]:
            raise ValueError("publisher size mismatch: " + name)
        digest, blob = verifier._digests(path, git_blob="lfs" not in item)
        if (digest != item["lfs"]["sha256"] if "lfs" in item else blob != item["blobId"]):
            raise ValueError("publisher checksum mismatch: " + name)
        files.append({"path": name, "size": item["size"], "sha256": digest})
    manifest = {"schema_version": "deposium.model-assets/v1", "repo_id": REPO_ID,
                "revision": REVISION, "files": files}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(manifest, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    return {"repo_id": REPO_ID, "revision": REVISION, "verified_files": len(files),
            "verified_bytes": sum(item["size"] for item in files),
            "hub_metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
            "verifier_sha256": hashlib.sha256(HELPER.read_bytes()).hexdigest(),
            "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "inference": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--hub-metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.model_dir, args.hub_metadata, args.output), sort_keys=True))
