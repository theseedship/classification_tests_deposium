"""Inventory pinned, already downloaded Noma assets. No inference or download."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deposium_bench.adapters import _environment
from deposium_bench.noma_adapter import NomaAdapter, REPO_ID, REVISION, SOURCE_REPO, SOURCE_REVISION

WEIGHTS_SHA256 = "74319701dde4fd0a2c9cfaea0cbeaf475ccf8059993b8b936434fbb432389671"


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b""):
            result.update(block)
    return result.hexdigest()


def inventory(root, repo, revision):
    files = [{"path": name, "size": (root/name).stat().st_size, "sha256": digest(root/name)}
             for name in sorted(NomaAdapter._inventory(root))]
    if not files:
        raise ValueError("empty asset inventory")
    return {"schema_version": "deposium.model-assets/v1", "repo_id": repo, "revision": revision, "files": files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="Manifest destination; existing files refused")
    args = parser.parse_args()
    git = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(args.source_dir)]
    def read_git(*parts):
        return subprocess.check_output(git+list(parts), env=_environment(), timeout=15)
    if read_git("rev-parse", "HEAD").decode().strip() != SOURCE_REVISION or read_git("status", "--porcelain"):
        raise ValueError("Noma source revision must be pinned and clean")
    source = inventory(args.source_dir, SOURCE_REPO, SOURCE_REVISION)
    # Match actual checkout bytes to the publisher commit, not just the HEAD label.
    for item in source["files"]:
        blob = read_git("show", SOURCE_REVISION+":"+item["path"])
        if hashlib.sha256(blob).hexdigest() != item["sha256"]:
            raise ValueError("Source bytes differ from pinned Git blob: "+item["path"])
    model = inventory(args.model_dir, REPO_ID, REVISION)
    expected = dict(line.split(None, 1)[::-1] for line in (args.model_dir/"SHA256SUMS").read_text().splitlines())
    if expected.get("model.safetensors") != WEIGHTS_SHA256:
        raise ValueError("Unexpected publisher weights checksum")
    for item in model["files"]:
        if item["path"] != "SHA256SUMS" and expected.get(item["path"]) != item["sha256"]:
            raise ValueError("Model bytes differ from publisher checksum: "+item["path"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {"noma-assets.json": model, "noma-source-assets.json": source}
    if any((args.output_dir/name).exists() for name in outputs):
        raise FileExistsError("Existing manifests are never replaced")
    for name, value in outputs.items():
        with (args.output_dir/name).open("x") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    print(json.dumps({"model_files": len(model["files"]), "source_files": len(source["files"]), "inference": False}))


if __name__ == "__main__":
    main()
