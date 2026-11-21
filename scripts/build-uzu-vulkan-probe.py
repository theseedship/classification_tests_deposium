#!/usr/bin/env python3
"""Prepare, without building or running, a source-pinned weight-free Vulkan probe."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]
REVISION = "95e8f2282daf0fb78938b620f835b8fd3d716c73"
REPOSITORY = "https://github.com/trymirai/uzu.git"
HELPER = ROOT / "native/uzu-vulkan-probe/main.rs"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def captured(command, cwd):
    return subprocess.check_output(command, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def require(value, code):
    if not value:
        raise ValueError(code)


def toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{k} = {toml_value(v)}" for k, v in value.items()) + " }"
    raise ValueError("unsupported_dependency_specification")


def prepare(source, output):
    source, output = Path(source).resolve(strict=True), Path(output).absolute()
    require(output.resolve().is_relative_to((ROOT / "results").resolve())
            and not output.exists() and not output.is_symlink(), "new_results_directory_required")
    require(captured(["git", "rev-parse", "HEAD"], source) == REVISION, "source_revision_mismatch")
    require(captured(["git", "remote", "get-url", "origin"], source) == REPOSITORY, "source_repository_mismatch")
    require(not captured(["git", "status", "--porcelain", "--untracked-files=all"], source), "source_not_clean")
    workspace = tomllib.loads((source / "Cargo.toml").read_text())["workspace"]
    dependencies = {"uzu-engine": {"path": str(source / "crates/uzu-engine"),
                                   "default-features": False, "features": ["vulkan"]}}
    for name in ("ash", "tokio", "serde_json"):
        spec = workspace["dependencies"][name]
        dependencies[name] = dict(spec) if isinstance(spec, dict) else {"version": spec}
    dependencies["tokio"]["features"] = sorted(set(dependencies["tokio"].get("features", [])) | {"rt", "macros"})
    output.mkdir(parents=True)
    (output / "src").mkdir()
    shutil.copyfile(HELPER, output / "src/main.rs")
    shutil.copyfile(source / "Cargo.lock", output / "Cargo.lock")
    manifest = "\n".join(["[package]", 'name = "uzu-vulkan-probe"', 'version = "0.1.0"',
        f'edition = "{workspace["package"]["edition"]}"', "publish = false", "", "[workspace]", "",
        "[dependencies]", *(f"{name} = {toml_value(spec)}" for name, spec in dependencies.items()), ""])
    (output / "Cargo.toml").write_text(manifest)
    record = {"schema_version": "deposium.uzu-vulkan-probe-preparation/v1",
        "scope": "private_local_paths_do_not_publish_verbatim", "uzu_repository": REPOSITORY,
        "uzu_revision": REVISION, "uzu_source": str(source), "helper_source_sha256": digest(HELPER),
        "builder_sha256": digest(__file__), "lockfile_sha256": digest(output / "Cargo.lock"),
        "manifest_sha256": digest(output / "Cargo.toml"), "status": "prepared_not_built",
        "model_loaded": False, "inference_run": False, "native_context_created": False}
    require(not captured(["git", "status", "--porcelain", "--untracked-files=all"], source), "source_changed")
    (output / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    return {"status": record["status"], "uzu_revision": REVISION, "inference_run": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uzu-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(prepare(args.uzu_source, args.output)))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        print(json.dumps({"status": "error", "error_code": "probe_preparation_failed"}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
