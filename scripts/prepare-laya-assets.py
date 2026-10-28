"""Prepare pinned Laya metadata with the official helper; no download or inference."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.adapters import _environment

REPO = "convaiinnovations/laya-multilingual"
REV = "1720e3e3357cfe1e281542e223f8273b0890ca34"
SOURCE = "NandhaKishorM/laya"
SOURCE_REV = "2e4d9c87e8b1621deb344eac7de5c7258f32f849"
FILES = ("model.safetensors", "rl_agent_config.json", "encoder/config.json",
         "tokenizer/tokenizer.json", "tokenizer/tokenizer_config.json")
PUBLISHED_SHA256 = {
    "model.safetensors": "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204",
    "tokenizer/tokenizer.json": "609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f",
}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inventory(root, names, repo, revision):
    return {"schema_version": "deposium.model-assets/v1", "repo_id": repo,
            "revision": revision,
            "files": [{"path": name, "size": (root / name).stat().st_size,
                       "sha256": digest(root / name)} for name in sorted(names)]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir", type=Path, required=True)
    p.add_argument("--model-dir", type=Path, required=True, help="Original HF snapshot")
    p.add_argument("--prepared-dir", type=Path, required=True, help="Fresh derived bundle")
    p.add_argument("--hub-metadata", type=Path, required=True, help="Pinned HF API metadata with blobs")
    p.add_argument("--runtime-python", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    if args.prepared_dir.exists() or args.output_dir.exists():
        raise FileExistsError("Prepared assets and manifest output must be fresh")
    metadata = json.loads(args.hub_metadata.read_text())
    if metadata.get("id") != REPO or metadata.get("sha") != REV:
        raise ValueError("Hub metadata is not the pinned checkpoint")
    indexed = {item["rfilename"]: item for item in metadata["siblings"]}
    original = inventory(args.model_dir, FILES, REPO, REV)
    for item in original["files"]:
        path = args.model_dir / item["path"]
        if path.is_symlink():
            raise ValueError("Model symlinks refused")
        published = indexed[item["path"]]
        if item["path"] in PUBLISHED_SHA256 and item["sha256"] != PUBLISHED_SHA256[item["path"]]:
            raise ValueError("Pinned publisher SHA-256 mismatch")
        if item["size"] != published["size"]:
            raise ValueError("Publisher size mismatch")
        if "lfs" in published:
            if item["sha256"] != published["lfs"]["sha256"]:
                raise ValueError("Publisher SHA-256 mismatch")
        else:
            blob = b"blob " + str(item["size"]).encode() + b"\0" + path.read_bytes()
            if hashlib.sha1(blob).hexdigest() != published["blobId"]:
                raise ValueError("Publisher Git blob mismatch")
    git = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(args.source_dir)]
    def read_git(*parts):
        return subprocess.check_output(git + list(parts), env=_environment(), timeout=15)
    if read_git("rev-parse", "HEAD").decode().strip() != SOURCE_REV or read_git("status", "--porcelain"):
        raise ValueError("Source must be pinned and clean")
    names = [n.decode() for n in read_git("ls-files", "-z").split(b"\0") if n]
    source = inventory(args.source_dir, names, SOURCE, SOURCE_REV)
    for item in source["files"]:
        path = args.source_dir / item["path"]
        if path.is_symlink() or hashlib.sha256(read_git("show", SOURCE_REV + ":" + item["path"])).hexdigest() != item["sha256"]:
            raise ValueError("Source differs from pinned Git blob")
    args.prepared_dir.mkdir(parents=True)
    for name in FILES:
        target = args.prepared_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.model_dir / name, target)
    # The publisher's extra_special_tokens list needs the SDK's own compatibility
    # conversion. Preserve original bytes and fingerprint the derived bundle.
    with tempfile.TemporaryDirectory(prefix="laya-prepare-") as cache:
        env = {**_environment(), "USE_TF": "0", "HF_HUB_OFFLINE": "1",
               "TRANSFORMERS_OFFLINE": "1", "HF_HOME": cache, "XDG_CACHE_HOME": cache,
               "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"}
        code = ("import sys; sys.path.insert(0,sys.argv[1]); "
                "from laya.agent import _fix_tokenizer_config; _fix_tokenizer_config(sys.argv[2])")
        subprocess.run([str(args.runtime_python), "-I", "-B", "-X", "pycache_prefix=" + cache + "/pycache",
                        "-c", code, str(args.source_dir.resolve()), str(args.prepared_dir.resolve())],
                       env=env, check=True, timeout=60, stdout=subprocess.DEVNULL)
    prepared = inventory(args.prepared_dir, FILES, REPO, REV)
    changed = [a["path"] for a, b in zip(original["files"], prepared["files"]) if a != b]
    if changed != ["tokenizer/tokenizer_config.json"]:
        raise ValueError("Unexpected official preparation changes")
    preparation = {"schema_version": "deposium.laya-asset-preparation/v1",
                   "model_revision": REV, "source_revision": SOURCE_REV,
                   "official_helper": "laya.agent._fix_tokenizer_config",
                   "original": original, "prepared": prepared,
                   "changed_files": changed, "inference": False}
    args.output_dir.mkdir(parents=True)
    for name, value in (("laya-multilingual-assets.json", prepared),
                        ("laya-source-assets.json", source), ("laya-preparation.json", preparation)):
        with (args.output_dir / name).open("x") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    print(json.dumps({"model_files": len(FILES), "source_files": len(names), "changed": changed, "inference": False}))


if __name__ == "__main__":
    main()
