"""Verify one explicitly downloaded Vela3-fast decision backbone; never download or load it."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.vela3_fast_adapter import OFFICIAL_HELPERS, OFFICIAL_METADATA, REPO_ID, REVISION, WEIGHT_SHA256, WEIGHT_SIZE

REQUIRED = set(OFFICIAL_HELPERS) | {"config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors"}
OPTIONAL = {"README.md", "LICENSE", "requirements.txt", "vela3_config.json"}
TENSOR_ELEMENTS = 380436226  # Includes the scalar log_tau (one element).


def prepare(model_dir, metadata, output):
    source = Path(model_dir).resolve(strict=True)
    destination = Path(output).absolute()
    if destination.resolve().is_relative_to(source) or destination.exists() or destination.is_symlink():
        raise ValueError("manifest must be new and outside its snapshot")
    spec = importlib.util.spec_from_file_location("bench_asset_verifier", ROOT / "scripts/prepare-small-decision-assets.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    published = helper._publisher_files(json.loads(Path(metadata).read_text()), REPO_ID, REVISION)
    names = helper._inventory(source)
    if not REQUIRED <= names or names - REQUIRED - OPTIONAL:
        raise ValueError("snapshot must contain only the decision backbone and selected official metadata")
    weight = published["model.safetensors"]
    if weight["size"] != WEIGHT_SIZE or weight.get("lfs", {}).get("sha256") != WEIGHT_SHA256:
        raise ValueError("publisher weight identity differs from the fixed decision backbone")
    files = []
    for name in sorted(names):
        item, path = published[name], source / name
        if path.stat().st_size != item["size"]:
            raise ValueError("publisher asset size mismatch: " + name)
        digest, blob = helper._digests(path, git_blob="lfs" not in item)
        if (("lfs" in item and digest != item["lfs"]["sha256"])
                or ("lfs" not in item and blob != item["blobId"])):
            raise ValueError("publisher hash mismatch: " + name)
        audited = {**OFFICIAL_HELPERS, **OFFICIAL_METADATA}
        if name in audited and digest != audited[name]:
            raise ValueError("official helper differs from audited source: " + name)
        files.append({"path": name, "size": item["size"], "sha256": digest})
    spec = importlib.util.spec_from_file_location("bench_tensor_verifier", ROOT / "scripts/prepare-d3-assets.py")
    tensors = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tensors)
    if tensors.tensor_counts(source / "model.safetensors") != {"F32": TENSOR_ELEMENTS}:
        raise ValueError("decision backbone tensor count/dtype differs from the reviewed checkpoint")
    manifest = {"schema_version": "deposium.model-assets/v1", "repo_id": REPO_ID,
                "revision": REVISION, "files": files}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x") as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare(args.model_dir, args.metadata, args.output)
    print(json.dumps({"repo_id": REPO_ID, "revision": REVISION, "files_verified": len(manifest["files"])}))


if __name__ == "__main__":
    main()
