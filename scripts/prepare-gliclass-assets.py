"""Verify an explicitly downloaded, pinned GLiClass snapshot; never download or load it."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "knowledgator/gliclass-v4-9b"
REVISION = "14d11a92b5e0bab4a166e1fce4cc0777cac27182"
REQUIRED = {"README.md", "config.json", "calibration_report.json", "chat_template.jinja",
            "model.safetensors", "processor_config.json", "tokenizer.json", "tokenizer_config.json"}


def prepare(model_dir, metadata, output):
    source = Path(model_dir).resolve(strict=True)
    destination = Path(output).absolute()
    if destination.resolve().is_relative_to(source) or destination.exists() or destination.is_symlink():
        raise ValueError("GLiClass manifest must be new and outside its snapshot")
    spec = importlib.util.spec_from_file_location("bench_asset_verifier", ROOT / "scripts/prepare-small-decision-assets.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    published = helper._publisher_files(json.loads(Path(metadata).read_text()), REPO, REVISION)
    if helper._inventory(source) != REQUIRED:
        raise ValueError("GLiClass snapshot inventory differs from the selected files")
    files = []
    for name in sorted(REQUIRED):
        item, path = published[name], source / name
        if path.stat().st_size != item["size"]:
            raise ValueError("GLiClass asset size mismatch: " + name)
        digest, blob = helper._digests(path, git_blob="lfs" not in item)
        if (("lfs" in item and digest != item["lfs"]["sha256"])
                or ("lfs" not in item and blob != item["blobId"])):
            raise ValueError("GLiClass publisher hash mismatch: " + name)
        files.append({"path": name, "size": item["size"], "sha256": digest})
    manifest = {"schema_version": "deposium.model-assets/v1", "repo_id": REPO,
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
    print(json.dumps({"repo_id": manifest["repo_id"], "revision": manifest["revision"],
                      "files_verified": len(manifest["files"])}))


if __name__ == "__main__":
    main()
