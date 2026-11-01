#!/usr/bin/env python3
"""Build the vocabulary-only Uzu decision preparation helper against a clean pinned Uzu checkout.

The helper (`native/uzu-preparation/main.rs`) calls the pinned
`hanashi::decision::DecisionEncoding`; it loads a pack's codec configuration and
tokenizer, never its weights. The crate is generated in a new ignored
`results/` directory with path dependencies on the checkout and the workspace's
own dependency specifications and lockfile. Paths stay in the local build record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.uzu_local import UZU_REVISION  # noqa: E402

REPOSITORY = "https://github.com/trymirai/uzu.git"
HELPER = ROOT / "native/uzu-preparation/main.rs"
CRATES = {"hanashi": "crates/legacy/hanashi", "shoji": "crates/legacy/shoji"}
SHARED = ("tokenizers", "indexmap", "serde", "serde_json")


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def captured(command, cwd=None):
    return subprocess.check_output(command, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{k} = {toml_value(v)}" for k, v in value.items()) + " }"
    raise ValueError(f"unsupported TOML value {value!r}")


def build(source, output, toolchain):
    source, output = Path(source).resolve(strict=True), Path(output).absolute()
    require(output.resolve().is_relative_to((ROOT / "results").resolve()) and not output.exists(),
            "output must be a new directory under results/")
    require(captured(["git", "rev-parse", "HEAD"], source) == UZU_REVISION, "Uzu source revision mismatch")
    require(captured(["git", "remote", "get-url", "origin"], source) == REPOSITORY, "Uzu source repository mismatch")
    require(not captured(["git", "status", "--porcelain", "--untracked-files=all"], source), "Uzu source must remain clean")
    workspace = tomllib.loads((source / "Cargo.toml").read_text())
    shared = workspace["workspace"]["dependencies"]
    edition = workspace["workspace"]["package"]["edition"]
    dependencies = {name: {"path": str(source / path)} for name, path in CRATES.items()}
    for name in SHARED:
        spec = shared[name]
        dependencies[name] = spec if isinstance(spec, dict) else {"version": spec}
    dependencies["serde"] = {**dependencies["serde"], "features": sorted(set(dependencies["serde"].get("features", [])) | {"derive"})}
    output.mkdir(parents=True)
    (output / "src").mkdir()
    shutil.copyfile(HELPER, output / "src/main.rs")
    shutil.copyfile(source / "Cargo.lock", output / "Cargo.lock")
    manifest = "\n".join(["[package]", 'name = "uzu-preparation"', 'version = "0.1.0"', f'edition = "{edition}"',
                          "publish = false", "", "[workspace]", "", "[dependencies]",
                          *(f"{name} = {toml_value(spec)}" for name, spec in dependencies.items()), ""])
    (output / "Cargo.toml").write_text(manifest)
    environment = {**os.environ, "CARGO_TARGET_DIR": str(output / "target")}
    with (output / "build.log").open("x") as log:
        subprocess.run(["rustup", "run", toolchain, "cargo", "build", "--release", "--quiet"], cwd=output,
                       env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
    binary = output / "target/release/uzu-preparation"
    help_text = captured([str(binary), "--help"])
    require(captured(["git", "status", "--porcelain", "--untracked-files=all"], source) == "", "Uzu source changed while building")
    record = {"schema_version": "deposium.uzu-preparation-build/v1",
              "scope": "local_private_build_provenance_contains_paths_do_not_publish_verbatim",
              "uzu_repository": REPOSITORY, "uzu_revision": UZU_REVISION, "uzu_source": str(source),
              "helper_source_sha256": digest(HELPER), "builder_sha256": digest(__file__),
              "lockfile_sha256": digest(output / "Cargo.lock"), "manifest_sha256": digest(output / "Cargo.toml"),
              "rustc_version": captured(["rustup", "run", toolchain, "rustc", "--version"]),
              "helper_binary_sha256": digest(binary), "help_output": help_text,
              "weights_loaded": False, "inference_run": False}
    (output / "build.json").write_text(json.dumps(record, indent=2) + "\n")
    return {"status": "built", "uzu_revision": UZU_REVISION, "helper_binary_sha256": record["helper_binary_sha256"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uzu-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--toolchain", default="nightly")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args.uzu_source, args.output, args.toolchain)))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"Uzu preparation build failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
