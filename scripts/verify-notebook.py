#!/usr/bin/env python3
"""Opt-in fresh-kernel fixture parity; requires the locked notebook extra.

This command deliberately executes campaigns. Ordinary stdlib tests do not.
Only the shipped recorded-control profile is used; no stack or model is loaded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "notebooks" / "decision_bench.ipynb"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def same_json(left, right) -> bool:
    """Compare JSON types exactly, including bool/int and int/float distinctions."""
    options = {"sort_keys": True, "ensure_ascii": False, "allow_nan": False}
    return json.dumps(left, **options) == json.dumps(right, **options)


def fingerprint(directory: Path) -> dict[str, str]:
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.rglob("*")) if path.is_file()}


def stable_records(directory: Path) -> dict[str, dict]:
    records = {}
    for line in (directory / "raw.jsonl").read_text(encoding="utf-8").split("\n"):
        if not line:
            continue
        record = json.loads(line)
        identity = record["case_id"]
        if identity in records:
            raise AssertionError(f"Duplicate case_id in {directory}: {identity}")
        # Preserve identity and every result field; only execution metadata varies.
        records[identity] = {key: value for key, value in record.items()
                             if key not in {"duration_ms", "run_id"}}
    return records


def execute_cli(mode: str, destination: Path, *, source: Path | None = None,
                max_new_cases: int | None = None) -> dict:
    command = [sys.executable, "-m", "deposium_bench", mode,
               "--output", str(destination), "--format", "json"]
    if mode == "run":
        command += ["--dataset", "datasets/decisions-v1/cases.jsonl",
                    "--profile", "profiles/fixture-control.json"]
    else:
        command += ["--archive", str(source)]
    if max_new_cases is not None:
        command += ["--max-new-cases", str(max_new_cases)]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
    if not (destination / "summary.json").is_file():
        raise RuntimeError(f"CLI {mode} did not produce a summary: {completed.stderr.strip()}")
    summary = read_json(destination / "summary.json")
    verdict = summary["metrics"]["verdict"]
    expected_exit = (130 if summary["completion_status"] == "interrupted" else
                     2 if verdict == "invalid" else
                     0 if verdict == "pass" and summary["completion_status"] == "complete" else 1)
    if completed.returncode != expected_exit:
        raise AssertionError(f"CLI {mode} exit {completed.returncode}; expected {expected_exit}")
    if not same_json(json.loads(completed.stdout), summary):
        raise AssertionError(f"CLI {mode} printed a different summary")
    return summary


def execute_notebook(mode: str, destination: Path, cwd: Path, executed_path: Path, *,
                     source: Path | None = None, max_new_cases: int | None = None) -> dict:
    # Optional imports stay out of the ordinary stdlib validation/import path.
    import nbformat
    from nbclient import NotebookClient
    from jupyter_client import KernelManager

    notebook = nbformat.read(SOURCE, as_version=4)
    parameter_cells = [index for index, cell in enumerate(notebook.cells)
                       if "parameters" in cell.metadata.get("tags", [])]
    if len(parameter_cells) != 1:
        raise AssertionError("Expected exactly one notebook parameters cell")
    parameters = {"dataset_path": "datasets/decisions-v1/cases.jsonl",
                  "profile_path": "profiles/fixture-control.json",
                  "output_dir": str(destination), "stack_root": None,
                  "run_mode": mode, "source_archive": str(source) if source else None,
                  "max_new_cases": max_new_cases}
    injection = nbformat.v4.new_code_cell(
        "\n".join(f"{key} = {value!r}" for key, value in parameters.items()),
        metadata={"tags": ["injected-parameters"]},
    )
    notebook.cells.insert(parameter_cells[0] + 1, injection)
    manager = KernelManager(kernel_name="python3")
    # Launch this exact environment without registering or installing a kernel.
    manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
    try:
        NotebookClient(notebook, km=manager, timeout=120, allow_errors=False,
                       resources={"metadata": {"path": str(cwd)}}).execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
        manager.cleanup_resources()
    nbformat.write(notebook, executed_path)
    return read_json(destination / "summary.json")


def compare(cli: Path, notebook: Path) -> dict:
    left, right = read_json(cli / "summary.json"), read_json(notebook / "summary.json")
    for field in ("metrics", "completion_status", "mode", "qualification", "stack_coverage"):
        if not same_json(left[field], right[field]):
            raise AssertionError(f"CLI/notebook disagree on {field}: {cli.name}")
    if not same_json(stable_records(cli), stable_records(notebook)):
        raise AssertionError(f"CLI/notebook disagree on per-case raw/normalized records: {cli.name}")
    metrics = left["metrics"]
    return {"mode": left["mode"], "completion_status": left["completion_status"],
            "total_cases": metrics["total_cases"], "scored_cases": metrics["scored_cases"],
            "passed_cases": metrics["passed_cases"], "failed_cases": metrics["failed_cases"],
            "verdict": metrics["verdict"], "recorded_cases": len(stable_records(cli))}


def verify_cwd(directory: Path, cwd: Path) -> list[dict]:
    results = []
    archives = {}
    initial_snapshots = {}
    for name, mode, source_name, limit in (
        ("full", "run", None, None), ("partial", "run", None, 4),
        ("resume", "resume", "partial", None), ("rescore", "rescore", "resume", None),
    ):
        pair = {}
        for interface in ("cli", "notebook"):
            destination = directory / f"{interface}-{name}"
            source = archives.get((interface, source_name))
            if interface == "cli":
                execute_cli(mode, destination, source=source, max_new_cases=limit)
            else:
                execute_notebook(mode, destination, cwd, directory / f"executed-{name}.ipynb",
                                 source=source, max_new_cases=limit)
            pair[interface] = destination
            archives[interface, name] = destination
            initial_snapshots[interface, name] = fingerprint(destination)
        result = compare(pair["cli"], pair["notebook"])
        result.update(stage=name, kernel_cwd=str(cwd))
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    for (interface, name), archive in archives.items():
        if fingerprint(archive) != initial_snapshots[interface, name]:
            raise AssertionError(f"Original archive changed: {archive}")
    for interface in ("cli", "notebook"):
        full = archives[interface, "full"]
        for stage in ("resume", "rescore"):
            derived = archives[interface, stage]
            if (not same_json(read_json(full / "summary.json")["metrics"],
                              read_json(derived / "summary.json")["metrics"])
                    or not same_json(stable_records(full), stable_records(derived))):
                raise AssertionError(f"{interface} {stage} differs from full fixture execution")
        resumed_raw = (archives[interface, "resume"] / "raw.jsonl").read_bytes()
        if resumed_raw != (archives[interface, "rescore"] / "raw.jsonl").read_bytes():
            raise AssertionError(f"{interface} rescore altered the raw trace")
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-cwd", choices=("root", "notebooks", "both"), default="both")
    parser.add_argument("--output-dir", type=Path,
                        help="New archive directory; default: results/notebook-parity-<uuid>")
    args = parser.parse_args(argv)
    destination = (args.output_dir.expanduser().resolve() if args.output_dir else
                   ROOT / "results" / f"notebook-parity-{uuid4().hex}")
    original_source = SOURCE.read_bytes()
    # Fail on missing extras before creating output; never install dependencies.
    try:
        import nbformat
        import nbclient
        import ipykernel
    except ImportError as exc:
        parser.error(f"Missing notebook extra ({exc.name}); use the locked notebook environment.")
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    try:
        for selected in (("root", "notebooks") if args.kernel_cwd == "both" else (args.kernel_cwd,)):
            directory = destination / selected
            directory.mkdir()
            cwd = ROOT if selected == "root" else ROOT / "notebooks"
            rows.extend(verify_cwd(directory, cwd))
    finally:
        if SOURCE.read_bytes() != original_source:
            raise AssertionError("Source notebook changed during verification")
    report = {"status": "pass", "qualification": "fixture_notebook_cli_parity",
              "archive_dir": str(destination), "python": sys.executable,
              "source_notebook_sha256": hashlib.sha256(original_source).hexdigest(),
              "fresh_kernels": len(rows), "source_notebook_unchanged": True,
              "original_archives_unchanged": True, "comparisons": rows}
    (destination / "verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
