"""Verify pinned local HF snapshots and copy only the small Python source files.

No network, model import, weight copy or inference occurs. The caller supplies
Hugging Face model metadata fetched with ``?blobs=true`` at the pinned revision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


MODELS = {
    "omni": ("LiquidAI/d1-omni-600M", "414f8d6438174f5b2133a9c21a478fc42625e308",
             ("prompt.py", "modeling_d1.py", "encoder.py", "vision.py", "audio.py"), "omni"),
    "muose": ("muose/Muose-50M-Decision", "5afb8eeff127621fea2d66fc63f56798ada12eda",
              ("model.py", "decision_model.py"), "muose"),
    "kai": ("vllm-sr/Decision-2.0-Kai-0.6B", "cd49ea3813fd8ba0928a9a23ef6c9a0f2f0cd764",
            (), "decision2-kai"),
    "modernjev": ("MaziyarPanahi/ModernJEV-Decide-Preview",
                  "d5b398ed03de073a00bc4e53acf53afda409445e", ("predict.py",), "modernjev"),
}
IGNORED_DIRS = {".git", ".cache", "__pycache__"}
SOURCE_LIMIT = 2 * 1024 * 1024


def _safe_name(name):
    if not isinstance(name, str) or not name or "\x00" in name or "\\" in name:
        raise ValueError("unsafe Hub path")
    relative = Path(name)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in name.split("/")) or relative.as_posix() != name:
        raise ValueError("unsafe Hub path")
    return relative


def _inventory(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError("snapshot must be a real directory")
    names = set()
    for folder, directories, files in os.walk(root, followlinks=False):
        here = Path(folder)
        for name in directories + files:
            if (here / name).is_symlink():
                raise ValueError("snapshot symlinks refused")
        directories[:] = [name for name in directories if name not in IGNORED_DIRS]
        for name in files:
            if name in IGNORED_DIRS:
                continue
            path = here / name
            if not path.is_file():
                raise ValueError("snapshot contains a non-file")
            relative = path.relative_to(root).as_posix()
            _safe_name(relative)
            names.add(relative)
    if not names:
        raise ValueError("empty snapshot")
    return names


def _digests(path, *, git_blob):
    before = path.stat()
    sha256 = hashlib.sha256()
    sha1 = hashlib.sha1() if git_blob else None
    if sha1 is not None:
        sha1.update(b"blob " + str(before.st_size).encode() + b"\0")
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            sha256.update(block)
            if sha1 is not None:
                sha1.update(block)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("snapshot changed during verification")
    return sha256.hexdigest(), sha1.hexdigest() if sha1 is not None else None


def _publisher_files(metadata, repo, revision):
    if (not isinstance(metadata, dict) or metadata.get("id") != repo or metadata.get("sha") != revision
            or not isinstance(metadata.get("siblings"), list) or not metadata["siblings"]):
        raise ValueError("Hub metadata does not match pinned model")
    indexed = {}
    for item in metadata["siblings"]:
        if not isinstance(item, dict):
            raise ValueError("invalid Hub metadata")
        name = item.get("rfilename")
        _safe_name(name)
        if name in indexed or type(item.get("size")) is not int or item["size"] < 0:
            raise ValueError("incomplete or duplicate Hub metadata; use ?blobs=true")
        if "lfs" in item:
            lfs = item["lfs"]
            checksum = lfs.get("sha256") if isinstance(lfs, dict) else None
            if (not isinstance(checksum, str) or len(checksum) != 64
                    or any(char not in "0123456789abcdef" for char in checksum)
                    or lfs.get("size") != item["size"]):
                raise ValueError("invalid Hub LFS metadata")
        else:
            blob = item.get("blobId")
            if (not isinstance(blob, str) or len(blob) != 40
                    or any(char not in "0123456789abcdef" for char in blob)):
                raise ValueError("missing Hub Git blob identity")
        indexed[name] = item
    return indexed


def prepare(mode, model_dir, hub_metadata, source_dir, output_dir):
    repo, revision, sources, stem = MODELS[mode]
    model_dir = Path(model_dir)
    hub_metadata = Path(hub_metadata)
    output_dir = Path(output_dir)
    source_dir = Path(source_dir) if source_dir is not None else None
    if bool(sources) != (source_dir is not None):
        raise ValueError("source directory required exactly for modes with Python source")
    if output_dir.exists() or (source_dir is not None and source_dir.exists()):
        raise FileExistsError("source and manifest destinations must be new")
    model_root = model_dir.resolve(strict=True)
    targets = [output_dir] + ([source_dir] if source_dir is not None else [])
    if any(target.resolve().is_relative_to(model_root) or model_root.is_relative_to(target.resolve())
           for target in targets):
        raise ValueError("output destinations must be separate from the snapshot")
    if source_dir is not None and (source_dir.resolve().is_relative_to(output_dir.resolve())
                                   or output_dir.resolve().is_relative_to(source_dir.resolve())):
        raise ValueError("source and manifest destinations must be separate")
    metadata = json.loads(hub_metadata.read_text())
    published = _publisher_files(metadata, repo, revision)
    actual = _inventory(model_dir)
    if actual != set(published):
        raise ValueError("snapshot inventory differs from pinned Hub metadata")
    if not set(sources) <= actual:
        raise ValueError("required publisher source is missing")
    files = []
    for name in sorted(actual):
        path = model_dir / name
        item = published[name]
        if path.stat().st_size != item["size"]:
            raise ValueError("publisher size mismatch: " + name)
        digest, blob = _digests(path, git_blob="lfs" not in item)
        if "lfs" in item:
            if digest != item["lfs"]["sha256"]:
                raise ValueError("publisher LFS SHA-256 mismatch: " + name)
        elif blob != item["blobId"]:
            raise ValueError("publisher Git blob mismatch: " + name)
        files.append({"path": name, "size": item["size"], "sha256": digest})
    model_manifest = {"schema_version": "deposium.model-assets/v1", "repo_id": repo,
                      "revision": revision, "files": files}
    source_manifest = None
    if sources:
        source_files = [item for item in files if item["path"] in sources]
        if any(item["size"] > SOURCE_LIMIT for item in source_files):
            raise ValueError("publisher Python source exceeds copy limit")
        source_manifest = {"schema_version": "deposium.model-assets/v1", "repo_id": repo,
                           "revision": revision, "files": source_files}
        source_dir.mkdir(parents=True)
        for item in source_files:
            origin = model_dir / item["path"]
            target = source_dir / item["path"]
            with origin.open("rb") as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
            if target.stat().st_size != item["size"] or _digests(target, git_blob=False)[0] != item["sha256"]:
                raise ValueError("copied publisher source changed")
    output_dir.mkdir(parents=True)
    manifests = {stem + "-assets.json": model_manifest}
    if source_manifest is not None:
        manifests[stem + "-source-assets.json"] = source_manifest
    for name, value in manifests.items():
        with (output_dir / name).open("x") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    return {"mode": mode, "model_files": len(files), "source_files": len(sources), "inference": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODELS, required=True)
    parser.add_argument("--model-dir", type=Path, required=True, help="Existing pinned HF snapshot")
    parser.add_argument("--hub-metadata", type=Path, required=True, help="Pinned HF API response with blobs")
    parser.add_argument("--source-dir", type=Path, help="Fresh destination for verified small Python sources")
    parser.add_argument("--output-dir", type=Path, required=True, help="Fresh manifest destination")
    args = parser.parse_args()
    print(json.dumps(prepare(args.mode, args.model_dir, args.hub_metadata,
                             args.source_dir, args.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
