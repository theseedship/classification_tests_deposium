#!/usr/bin/env python3
"""Download the file pinned by a tracked GGUF asset manifest and verify its size and SHA-256.

`--assets profiles/<name>-assets.json` names a Hugging Face repository, an exact
revision and one file with its size and SHA-256. The file is streamed to
`<output-dir>/<file>.part`, verified, then renamed; an existing verified file
is kept. The output directory must be under this checkout's ignored
`results/`. Nothing else is read or written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CHUNK = 8 * 1024 * 1024


def verify(path: Path, size: int, digest: str) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest() == digest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", required=True, type=Path, help="tracked profiles/*-assets.json")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    assets_path = (ROOT / args.assets).resolve() if not args.assets.is_absolute() else args.assets.resolve()
    output = args.output_dir.absolute()
    try:
        if not assets_path.is_relative_to(ROOT / "profiles"):
            raise ValueError("asset manifest must be tracked under profiles/")
        if not output.resolve().is_relative_to((ROOT / "results").resolve()):
            raise ValueError("output directory must be under results/")
        assets = json.loads(assets_path.read_text(encoding="utf-8"))
        if assets.get("schema_version") != "deposium.model-assets/v1" or len(assets["files"]) != 1:
            raise ValueError("expected a single-file deposium.model-assets/v1 manifest")
        entry = assets["files"][0]
        target = output / entry["path"]
        output.mkdir(parents=True, exist_ok=True)
        if verify(target, entry["size"], entry["sha256"]):
            print(json.dumps({"status": "present_verified", "file": entry["path"]}))
            return 0
        url = f"https://huggingface.co/{assets['repo_id']}/resolve/{assets['revision']}/{entry['path']}"
        partial = target.with_name(target.name + ".part")
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as handle:
            for block in iter(lambda: response.read(CHUNK), b""):
                handle.write(block)
        if not verify(partial, entry["size"], entry["sha256"]):
            partial.unlink(missing_ok=True)
            raise ValueError("downloaded file does not match the pinned size and SHA-256")
        partial.replace(target)
        print(json.dumps({"status": "downloaded_verified", "file": entry["path"], "bytes": entry["size"]}))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"fetch stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
