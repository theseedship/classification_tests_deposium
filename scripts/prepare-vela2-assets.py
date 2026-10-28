"""Verify selected pinned Vela Torch snapshots against Hub metadata, offline."""
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

# Reuse the existing publisher blob/LFS verifier; no model code is imported.
HELPER = ROOT / "scripts/prepare-small-decision-assets.py"
spec = importlib.util.spec_from_file_location("small_asset_verifier", HELPER)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
MODELS = {
    "03": ("vllm-sr/Vela-2.0-0.3B", "d6f03aa9baca4f9017fa8f8e9c2764d3bed3f409"),
    "08": ("vllm-sr/Vela-2.0-0.8B", "326b01d81f61fff7fd4ae570e54b87a49119e490"),
    "4": ("vllm-sr/Vela-2.0-4B", "d692394127f6f87fc581d8634c9558fe4776efce"),
}


def prepare(mode, model_dir, metadata_path, output):
    repo, revision = MODELS[mode]
    model_dir, metadata_path, output = map(Path, (model_dir, metadata_path, output))
    if output.exists() or output.is_symlink():
        raise FileExistsError("manifest destination must be new")
    if output.resolve().is_relative_to(model_dir.resolve()):
        raise ValueError("manifest must be outside snapshot")
    metadata_bytes = metadata_path.read_bytes()
    metadata = decode(metadata_bytes)
    published = verifier._publisher_files(metadata, repo, revision)
    excluded = {name for name in published if mode == "03" and name.startswith("onnx/")}
    expected = set(published) - excluded
    actual = verifier._inventory(model_dir)
    if actual != expected:
        raise ValueError("snapshot inventory differs from selected pinned Hub files")
    files = []
    for name in sorted(expected):
        item, path = published[name], model_dir / name
        if path.stat().st_size != item["size"]:
            raise ValueError("publisher size mismatch: " + name)
        digest, blob = verifier._digests(path, git_blob="lfs" not in item)
        if (digest != item["lfs"]["sha256"] if "lfs" in item else blob != item["blobId"]):
            raise ValueError("publisher checksum mismatch: " + name)
        files.append({"path": name, "size": item["size"], "sha256": digest})
    manifest = {"schema_version": "deposium.model-assets/v1", "repo_id": repo,
                "revision": revision, "files": files}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(manifest, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    return {"repo_id": repo, "revision": revision, "verified_files": len(files),
            "verified_bytes": sum(item["size"] for item in files),
            "excluded_files": sorted(excluded),
            "hub_metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
            "verifier_sha256": hashlib.sha256(HELPER.read_bytes()).hexdigest(),
            "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "inference": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODELS, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--hub-metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.mode, args.model_dir, args.hub_metadata, args.output), sort_keys=True))
