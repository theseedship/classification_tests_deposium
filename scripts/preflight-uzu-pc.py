#!/usr/bin/env python3
"""Offline source gate for pinned Uzu WebGPU; never builds or runs Uzu."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.uzu_local import REPOSITORY, UZU_REVISION

ENGINE = "crates/uzu-engine/"
KERNEL = ENGINE + "src/backends/webgpu/kernel.rs"
MATMUL = ENGINE + "src/encodable_block/linear/matmul.rs"
ATTENTION = ENGINE + "src/encodable_block/mixer/attention/mod.rs"
# Raw-byte hashes of the reviewed release source, including its line endings.
EXPECTED_HASHES = {
    "Cargo.toml": "adba4205908fe30ca8cae69cd02ff9f0881c7c8bf3cecb473b98ddd4c67bc598",
    ENGINE + "Cargo.toml": "d0db07175184bd5a2a27cd49374f9c0e69a5029621e055126f245bcf49d2e57d",
    KERNEL: "c169ca0e64dc1bcf429615d820246922963d51a369596381df68dcaeff36306a",
    MATMUL: "3873ff960711c239330ba2b1b18d0279c3abaf28363ea60107ac5885fb6121c6",
    ATTENTION: "14213b906894615c2ae2d7c1ea8e66c89b98d07f4b3263ee812682e37dd3b94a",
}


def git(source, *args):
    try:
        return subprocess.run(["git", "--no-optional-locks", "-C", str(source), *args],
                              check=True, capture_output=True, text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("source_git_unavailable") from exc


def inspect_source(source):
    """Read only reviewed source; errors are fixed codes without local values."""
    if not source.is_dir():
        raise ValueError("source_missing")
    if Path(git(source, "rev-parse", "--show-toplevel")).resolve() != source:
        raise ValueError("source_not_repository_root")
    if git(source, "remote", "get-url", "origin") != REPOSITORY:
        raise ValueError("source_origin_mismatch")
    if git(source, "rev-parse", "HEAD") != UZU_REVISION:
        raise ValueError("source_revision_mismatch")
    # Include ignored files: an ignored generated include can change a build.
    if git(source, "status", "--porcelain=v1", "--untracked-files=all", "--ignored"):
        raise ValueError("source_dirty")
    data = {}
    for name in EXPECTED_HASHES:
        path = source / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(source):
            raise ValueError("source_evidence_missing")
        data[name] = path.read_bytes()
    hashes = {name: hashlib.sha256(value).hexdigest() for name, value in data.items()}
    if hashes != EXPECTED_HASHES:
        return {"execution_gate": "unknown", "reason": "source_evidence_changed", "source_sha256": hashes}
    manifests = {name: tomllib.loads(data[name].decode()) for name in ("Cargo.toml", ENGINE + "Cargo.toml")}
    features = manifests[ENGINE + "Cargo.toml"].get("features", {})
    text = data[KERNEL].decode()
    unsupported = {}
    for name in ("AttentionKernel", "MatmulKernel"):
        declaration = bool(re.search(r"type\s+" + name + r"\s*=\s*Unsupported<WebGPU>\s*;", text))
        constructor = bool(re.search(r"impl " + name + r" for Unsupported<WebGPU>\s*\{.*?fn new\(.*?\)\s*->[^\{]+\{\s*Err\(WebGPUError::NotSupported\)\s*\}", text, re.S))
        unsupported[name] = {"associated_type_unsupported": declaration, "constructor_not_supported": constructor}
    callsites = {name: "::" + kernel + "::new(" in data[name].decode()
                 for name, kernel in ((MATMUL, "MatmulKernel"), (ATTENTION, "AttentionKernel"))}
    known = (features.get("default") == ["metal", "cpu"] and "webgpu" in features
             and all(all(item.values()) for item in unsupported.values()) and all(callsites.values()))
    return {"execution_gate": "unsupported" if known else "unknown",
            "reason": "pinned_webgpu_required_kernels_not_supported" if known else "source_evidence_unknown",
            "source_sha256": hashes, "engine_features": features,
            "workspace_version": manifests["Cargo.toml"].get("workspace", {}).get("package", {}).get("version"),
            "webgpu_kernels": unsupported, "model_constructor_callsites": callsites}


def preflight(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    results = (ROOT / "results").resolve()
    if output == results or not output.is_relative_to(results):
        raise ValueError("output_must_be_new_directory_under_results")
    if output.exists():
        raise ValueError("output_already_exists")
    if git(ROOT, "check-ignore", "--no-index", str(output / "preflight.json")) == "":
        raise ValueError("output_not_ignored")
    report = {"schema_version": "deposium.uzu-pc-preflight/v1", "campaign": "not_run",
              "cases_scored": 0, "actual_backend": "not_observed", "models": "not_loaded",
              "requested_backend": "webgpu", "uzu_revision": UZU_REVISION,
              "uzu_repository": REPOSITORY,
              "private_local_metadata": {"source_path": str(source)},
              "scope": "Pinned source inspection only; no inference, device qualification, or claim about newer revisions."}
    try:
        report.update(inspect_source(source))
    except (ValueError, OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        report.update(execution_gate="error", reason=str(exc) if isinstance(exc, ValueError) and str(exc).startswith("source_") else "source_inspection_error")
    output.mkdir(parents=True, exist_ok=False)
    (output / "preflight.json").write_text(json.dumps(report, indent=2) + "\n")
    return {key: report[key] for key in ("execution_gate", "reason", "campaign", "cases_scored", "actual_backend", "models")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uzu-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = preflight(args.uzu_source, args.output)
    except (ValueError, OSError) as exc:
        result = {"execution_gate": "error", "reason": str(exc) if isinstance(exc, ValueError) else "output_write_error"}
    print(json.dumps(result))
    return 2 if result["execution_gate"] == "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
