"""Verify pinned D3 Torch snapshots against Hub metadata, offline."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
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
    "edge": ("vllm-sr/d3-edge", "18d61df78684675463af9ae732872478845c5a79"),
    "lite": ("vllm-sr/d3-lite", "a8d25a91ef75552803f7009d25b7bd435991abd9"),
    "nano": ("vllm-sr/d3-nano", "3aeb1c22a5632aac72353c36b3d0111c40e7dbf4"),
    "mini": ("vllm-sr/d3-mini", "a475367de0d8133a3c1a2a0dc12303d89cfa2ab4"),
    "flash": ("vllm-sr/d3-flash", "521525effa79469d899a570726547dd7f00da3af"),
}
BACKBONE_ELEMENTS = {"edge": 594321600, "lite": 852985920, "nano": 2213241664,
                     "mini": 4539265536, "flash": 8392695024}
HIDDEN = {"edge": 1024, "lite": 1024, "nano": 2048, "mini": 2560, "flash": 4096}
WEIGHT_FILES = {
    "edge": ("model-00001-of-00001.safetensors",),
    "lite": ("model-00001-of-00001.safetensors",),
    "nano": ("model.safetensors",),
    "mini": tuple(f"model-{i:05d}-of-00002.safetensors" for i in range(1, 3)),
    "flash": tuple(f"model-{i:05d}-of-00004.safetensors" for i in range(1, 5)),
}


def tensor_counts(path):
    """Read bounded safetensors headers, including scalar tensor elements."""
    with Path(path).open("rb") as stream:
        prefix = stream.read(8)
        if len(prefix) != 8:
            raise ValueError("incomplete safetensors prefix")
        length = int.from_bytes(prefix, "little")
        size = Path(path).stat().st_size - 8 - length
        if not 1 <= length <= 16 * 1024 * 1024 or size < 0:
            raise ValueError("invalid safetensors header length")
        raw = stream.read(length)
        if len(raw) != length:
            raise ValueError("incomplete safetensors header")
    header = decode(raw)
    if not isinstance(header, dict):
        raise ValueError("invalid safetensors header")
    counts, intervals = {}, []
    widths = {"BF16": 2, "F16": 2, "F32": 4, "F64": 8, "I64": 8,
              "I32": 4, "I16": 2, "I8": 1, "U8": 1, "BOOL": 1}
    for name, tensor in header.items():
        if name == "__metadata__":
            continue
        if not isinstance(tensor, dict):
            raise ValueError("invalid safetensors tensor")
        shape, offsets, dtype = tensor.get("shape"), tensor.get("data_offsets"), tensor.get("dtype")
        if (not isinstance(dtype, str) or dtype not in widths or not isinstance(shape, list)
                or any(type(x) is not int or x < 0 for x in shape)
                or not isinstance(offsets, list) or len(offsets) != 2
                or any(type(x) is not int for x in offsets)):
            raise ValueError("invalid safetensors tensor metadata")
        count = math.prod(shape)
        lo, hi = offsets
        if not 0 <= lo <= hi <= size or hi - lo != count * widths[dtype]:
            raise ValueError("safetensors tensor byte range mismatch")
        if hi > lo:
            intervals.append((lo, hi))
        counts[dtype] = counts.get(dtype, 0) + count
    intervals.sort()
    if not counts or any(left[1] > right[0] for left, right in zip(intervals, intervals[1:])):
        raise ValueError("empty or overlapping safetensors tensors")
    return counts


def reviewed_tensor_counts(mode, model_dir, inventory):
    """Count every reviewed shard, rejecting extra weights and mixed dtypes."""
    weight_names = WEIGHT_FILES[mode]
    selected = set(weight_names) | {"readout.safetensors"}
    if {name for name in inventory if name.endswith(".safetensors")} != selected:
        raise ValueError("D3 weight inventory differs from reviewed checkpoint")
    tensors = {name: tensor_counts(Path(model_dir) / name) for name in (*weight_names, "readout.safetensors")}
    if (any(set(tensors[name]) != {"BF16"} for name in weight_names)
            or sum(tensors[name]["BF16"] for name in weight_names) != BACKBONE_ELEMENTS[mode]
            or tensors["readout.safetensors"] != {"F32": 255 * HIDDEN[mode]}):
        raise ValueError("D3 tensor counts or dtypes differ from reviewed checkpoint")
    return tensors


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
    excluded = set()
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
    tensors = reviewed_tensor_counts(mode, model_dir, expected)
    manifest = {"schema_version": "deposium.model-assets/v1", "repo_id": repo,
                "revision": revision, "files": files}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(manifest, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    return {"repo_id": repo, "revision": revision, "verified_files": len(files),
            "verified_bytes": sum(item["size"] for item in files),
            "excluded_files": sorted(excluded),
            "tensor_elements": tensors,
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
