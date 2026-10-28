#!/usr/bin/env python3
"""Explicit, offline inspection of the real Mastra factory; no tool execution."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

BENCH = Path(__file__).resolve().parents[1]
BRIDGE = BENCH / "bridges/mastra-tool-surface.mjs"
SOURCES = (
    "src/agents/deposium-agent.ts",
    "src/agents/use-mastra-transport.ts",
    "src/utils/mcp-logger.ts",
    "src/utils/trace-context.ts",
    "src/services/explicit-no-info-answer.ts",
    "package.json",
    "package-lock.json",
)
TOOLS = {"abstain_decision", "deposium_analyze", "deposium_answer",
         "deposium_graph", "deposium_search", "escalate_decision"}


def validate_probe(probe: object) -> None:
    if (not isinstance(probe, dict) or probe.get("status") != "ok"
            or probe.get("transport") != "in-process" or probe.get("probe_only") is not True):
        raise ValueError("native_surface_probe_failed")
    for key in ("cases_scored", "tool_executions", "model_calls", "network_attempts"):
        if type(probe.get(key)) is not int or probe[key] != 0:
            raise ValueError("native_surface_activity_unexpected")
    tools = probe.get("tools")
    if not isinstance(tools, list) or len(tools) != len(TOOLS):
        raise ValueError("native_surface_catalog_missing")
    names = []
    for tool in tools:
        if (not isinstance(tool, dict) or not isinstance(tool.get("name"), str)
                or not isinstance(tool.get("description"), str) or not tool["description"].strip()
                or not isinstance(tool.get("inputSchema"), dict)
                or tool["inputSchema"].get("type") != "object"
                or not isinstance(tool["inputSchema"].get("properties"), dict)):
            raise ValueError("native_surface_schema_invalid")
        names.append(tool["name"])
    if set(names) != TOOLS:
        raise ValueError("native_surface_catalog_unexpected")


def environment() -> dict[str, str]:
    # In particular, no credentials, HOME, dotenv, NODE_OPTIONS or loader hooks.
    return {"PATH": os.environ.get("PATH", os.defpath), "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8", "TZ": "UTC", "TSX_DISABLE_CACHE": "1",
            "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def run(command: list[str], root: Path, timeout: int = 10) -> str:
    result = subprocess.run(command, cwd=root, env=environment(), timeout=timeout,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            check=True)
    if len(result.stdout) > 1024 * 1024:
        raise ValueError("probe_output_limit")
    return result.stdout.decode("utf-8")


def source_state(root: Path, revision: str) -> dict:
    if run(["git", "rev-parse", "HEAD"], root).strip() != revision:
        raise ValueError("source_revision_mismatch")
    if run(["git", "status", "--porcelain=v1", "--untracked-files=no"], root).strip():
        raise ValueError("source_tracked_dirty")
    hashes = {}
    for name in SOURCES:
        data = (root / name).read_bytes()
        hashes[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    return {"head": revision, "tracked_dirty": False, "files": hashes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcps-root", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_revision):
        parser.error("--expected-revision must be a complete Git SHA")
    if args.output.exists():
        parser.error("output already exists; choose a fresh archive path")
    try:
        root = args.mcps_root.resolve(strict=True)
        if args.output.resolve().is_relative_to(root):
            raise ValueError("output_inside_application_forbidden")
        before = source_state(root, args.expected_revision)
        output = run(["node", "--max-old-space-size=256", str(BRIDGE), str(root)],
                     BENCH, timeout=30)
        probe = json.loads(output)
        validate_probe(probe)
        if source_state(root, args.expected_revision) != before:
            raise ValueError("source_changed_during_probe")
        report = {
            "schema_version": "deposium.mastra-surface-probe/v1",
            "qualification": "native_catalog_probe_only",
            "evaluation_status": "not_run",
            "cases_scored": 0,
            "tool_executions": 0,
            "model_calls": 0,
            "service_status": "not_observed",
            "source_checkout": before,
            "bench_files_sha256": {
                str(path.relative_to(BENCH)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (Path(__file__).resolve(), BRIDGE)
            },
            "probe": probe,
            "limits": [
                "Factory and tool declarations only; handlers and model were not executed.",
                "Selected source hashes and installed package versions are not a sealed runtime closure.",
                "No claim about a deployed MCP instance, authorization or latency.",
            ],
        }
        encoded = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
        print(json.dumps({"status": "probe_recorded", "evaluation_status": "not_run",
                          "cases_scored": 0, "output": str(args.output)}))
        return 0
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError):
        # Never print child logs, exceptions or ambient configuration.
        print(json.dumps({"status": "error", "error": "surface_probe_failed",
                          "evaluation_status": "not_run", "cases_scored": 0}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
