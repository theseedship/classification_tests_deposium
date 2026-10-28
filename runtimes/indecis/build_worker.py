#!/usr/bin/env python3
"""Offline build and bounded source provenance. Never opens model weights."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

REVISION = "339e191405ac9be90f6857f810f478b3312b7f35"
FLAGS = ["-p", "2", "-trimpath", "-buildvcs=false"]
SOURCE_LIMIT = 10 * 1024 * 1024


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def run(args, *, cwd, env=None):
    return subprocess.run(args, cwd=cwd, env=env, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=180).stdout


def source_manifest(source):
    if run(["git", "rev-parse", "HEAD"], cwd=source).decode().strip() != REVISION:
        raise ValueError("indecis_source_revision_mismatch")
    if run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=source):
        raise ValueError("indecis_source_dirty")
    tracked = run(["git", "ls-files", "-z"], cwd=source).decode().split("\0")
    files = []
    total = 0
    for name in sorted(name for name in tracked if name):
        relative = Path(name)
        if relative.suffix not in {".go", ".s", ".h"} and relative.name not in {"go.mod", "go.sum", "LICENSE"}:
            continue
        path = source / relative
        if relative.is_absolute() or ".." in relative.parts or path.is_symlink() or not path.is_file():
            raise ValueError("indecis_source_path_invalid")
        total += path.stat().st_size
        if len(files) >= 1000 or total > SOURCE_LIMIT:
            raise ValueError("indecis_source_limit")
        files.append({"path": name, "sha256": digest(path), "size": path.stat().st_size})
    return {"schema_version": "deposium.indecis-source/v1", "repo_id": "github.com/bornholm/indecis",
            "revision": REVISION, "files": files, "total_bytes": total}


def worker_hash(bridge):
    return hashlib.sha256(encode({name: digest(bridge / name)
                                 for name in ("main.go", "main_test.go", "go.mod")})).hexdigest()


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--go", type=Path, default=root / ".cache/go1.27.1/go/bin/go")
    parser.add_argument("--test", action="store_true", help="Run bridge fake-engine tests, without weights.")
    args = parser.parse_args()
    source = root / ".cache/indecis-source"
    bridge = root / "bridges/indecis-worker"
    directory = root / "runtimes/indecis"
    binary = root / ".cache/indecis-runtime/indecis-worker"
    source_before = source_manifest(source)
    worker_before = worker_hash(bridge)
    env = os.environ.copy()
    env.update(GOTOOLCHAIN="local", GOPROXY="off", GOSUMDB="off", GOMAXPROCS="2",
               GOFLAGS="", GOWORK="off", GOENV="off",
               CGO_ENABLED="0", GOEXPERIMENT="simd", GOOS="linux", GOARCH="amd64",
               GOPATH=str(root / ".cache/indecis-go-path"),
               GOMODCACHE=str(root / ".cache/indecis-go-mod"),
               GOCACHE=str(root / ".cache/indecis-go-build"))
    go = str(args.go.resolve())
    version = run([go, "version"], cwd=bridge, env=env).decode().split()[2]
    if version != "go1.27.1":
        raise ValueError("indecis_go_version_mismatch")
    if args.test:
        print(run([go, "test", "-p", "2", "-count=1", "-v", "./..."], cwd=bridge, env=env).decode(), end="")
    binary.parent.mkdir(parents=True, exist_ok=True)
    run([go, "build", *FLAGS, "-o", str(binary), "."], cwd=bridge, env=env)
    # Inspect the built artifact, rather than merely recording requested flags.
    artifact = run([go, "version", "-m", str(binary)], cwd=bridge, env=env).decode()
    settings = {}
    for line in artifact.splitlines()[1:]:
        parts = line.strip().split("\t")
        if len(parts) == 2 and parts[0] == "build" and "=" in parts[1]:
            name, value = parts[1].split("=", 1)
            settings[name] = value
    for name in ("CGO_ENABLED", "GOOS", "GOARCH", "GOEXPERIMENT"):
        if settings.get(name) != env[name]:
            raise ValueError("indecis_build_setting_mismatch:" + name)
    artifact_version = artifact.splitlines()[0].rsplit(": ", 1)[-1]
    if artifact_version != version + "-X:simd":
        raise ValueError("indecis_binary_go_version_mismatch")
    if source_manifest(source) != source_before or worker_hash(bridge) != worker_before:
        raise ValueError("indecis_source_changed_during_build")
    source_bytes = encode(source_before)
    build = {"schema_version": "deposium.indecis-build/v1", "source_revision": REVISION,
             "source_manifest_sha256": hashlib.sha256(source_bytes).hexdigest(),
             "worker_source_sha256": worker_before, "binary_sha256": digest(binary),
             "go_version": artifact_version, "build_flags": FLAGS,
             "go_env": {name: env[name] for name in
                        ("GOOS", "GOARCH", "CGO_ENABLED", "GOTOOLCHAIN", "GOEXPERIMENT", "GOPROXY", "GOSUMDB")}}
    (directory / "indecis-source-manifest.json").write_bytes(source_bytes)
    (directory / "indecis-build-manifest.json").write_bytes(encode(build))
    print(json.dumps({"binary": str(binary), "binary_sha256": build["binary_sha256"],
                      "source_files": len(source_before["files"]), "source_bytes": source_before["total_bytes"],
                      "go_version": artifact_version, "build_settings_verified": settings,
                      "inference_executed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
