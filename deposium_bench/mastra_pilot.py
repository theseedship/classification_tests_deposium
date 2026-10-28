"""Review-only tool choices and native wrapper contract checks.

No model, dependency installation or network is started on import. This module
is shared by the CLI and notebooks; its archives are distinct from campaigns.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

from .adapters import _environment, _json, _read
from .cases import _no_annotations, typed_equal
from .choice_protocol import validate_choice_input
from .registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datasets/mastra-read-pilot-v0/cases.jsonl"
BRIDGE = ROOT / "bridges/mastra-read-pilot.mjs"
CONTROLS = ROOT / "deposium_bench/data/mastra-read-contracts.json"
PLANNER_BRIDGE = ROOT / "bridges/mastra-planner-capture.mjs"
PLANNER_CONTROLS = ROOT / "deposium_bench/data/mastra-planner-contracts.json"
SNAPSHOT_HELPER = ROOT / "bridges/snapshot-identity.mjs"
GRAPH_HELPER = "src/agents/deposium-graph-tool.ts"
SOURCES = (
    "src/agents/deposium-agent.ts", "src/agents/use-mastra-transport.ts",
    "src/services/explicit-no-info-answer.ts", "src/utils/mcp-logger.ts",
    "src/utils/trace-context.ts", "package.json", "package-lock.json",
)
ACTIONS = {"search", "stats", "fallback"}
PROJECTION_VERSION = "mastra-read-choice/v1"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dump(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()


def _exact(value: object, keys: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"mastra pilot: invalid {label} fields")


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def candidate_request(case: dict) -> dict:
    """The only projection exposed to choice adapters; reference never copied."""
    visible = case["candidate_input"]
    value = {"context": "Demande utilisateur / User request:\n" + visible["message"]
                        + "\n\nPérimètre / Scope:\n" + visible["context"],
             "question": "Quelle action choisir pour cette demande ? / Which action fits this request?",
             "options": [{"id": option["id"], "description": option["label"]}
                         for option in visible["options"]]}
    validate_choice_input(value)
    _no_annotations(value)
    return {"case_id": case["case_id"], "contract_id": "bench.context-choice", "input": value}


def load_review_dataset(path: str | Path = DATASET) -> tuple[list[dict], str]:
    data = _read(Path(path))
    manifest_path = Path(path).with_name("manifest.json")
    if manifest_path.exists():
        manifest = _json(_read(manifest_path))
        if (manifest.get("cases_file") != Path(path).name
                or manifest.get("cases_sha256") != _sha(data)):
            raise ValueError("mastra pilot: dataset manifest mismatch")
    rows = [_json(line) for line in data.splitlines() if line.strip()]
    if not rows:
        raise ValueError("mastra pilot: empty corpus")
    identities, groups = set(), {}
    for case in rows:
        _exact(case, {"schema_version", "case_id", "scenario_id", "translation_family", "split",
                      "language", "candidate_input", "reference", "execution"}, "case")
        if case["schema_version"] != "deposium.mastra-read-review/v0":
            raise ValueError("mastra pilot: unknown case version")
        for field in ("case_id", "scenario_id", "translation_family"):
            if not _text(case[field]):
                raise ValueError("mastra pilot: invalid case identity")
        if case["case_id"] in identities:
            raise ValueError("mastra pilot: duplicate case")
        identities.add(case["case_id"])
        if case["split"] not in ("calibration", "test") or case["language"] not in ("fr", "en"):
            raise ValueError("mastra pilot: invalid split/language")
        for key in ("scenario_id", "translation_family"):
            group = key, case[key]
            if group in groups and groups[group] != case["split"]:
                raise ValueError("mastra pilot: cross-split family leakage")
            groups[group] = case["split"]
        visible = case["candidate_input"]
        _exact(visible, {"message", "context", "options"}, "candidate input")
        if not _text(visible["message"]) or not _text(visible["context"]):
            raise ValueError("mastra pilot: missing question/context")
        options = visible["options"]
        if not isinstance(options, list) or len(options) != 3:
            raise ValueError("mastra pilot: expected three choices")
        actions = []
        for option in options:
            _exact(option, {"id", "label", "action"}, "option")
            if not all(_text(option[key]) for key in option):
                raise ValueError("mastra pilot: empty option")
            actions.append(option["action"])
        if set(actions) != ACTIONS:
            raise ValueError("mastra pilot: unexpected action pool")
        candidate_request(case)
        reference = case["reference"]
        _exact(reference, {"acceptable_choices", "review", "rationale"}, "reference")
        choices = reference["acceptable_choices"]
        if (reference["review"] != "pending_human" or not _text(reference["rationale"])
                or not isinstance(choices, list) or not choices
                or any(not isinstance(choice, str) for choice in choices)
                or len(set(choices)) != len(choices)
                or not set(choices) <= {option["id"] for option in options}):
            raise ValueError("mastra pilot: invalid proposed reference")
        _exact(case["execution"], {"fixture_id"}, "execution")
        if case["execution"]["fixture_id"] != "synthetic-corpus-a":
            raise ValueError("mastra pilot: unknown fixture")
    return rows, _sha(data)


def _review_summary(rows: list[dict], digest: str) -> dict:
    return {"status": "valid_review_corpus", "sha256": digest, "cases": len(rows),
            "families": len({row["translation_family"] for row in rows}),
            "by_language": dict(Counter(row["language"] for row in rows)),
            "by_split": dict(Counter(row["split"] for row in rows)),
            "human_approved": 0, "cases_scored": 0, "evaluation_status": "not_run"}


def review_summary(path: str | Path = DATASET) -> dict:
    return _review_summary(*load_review_dataset(path))


def resolve_choice(case: dict, response: dict) -> dict:
    """Validate adapter output without consulting reference or inferring a gold."""
    _exact(response, {"choice_id"}, "choice response")
    selected = next((item for item in case["candidate_input"]["options"]
                     if item["id"] == response["choice_id"]), None)
    if selected is None:
        raise ValueError("mastra pilot: choice outside presented pool")
    return {"action": selected["action"], "choice_id": selected["id"],
            "semantic_score": None, "review": "pending_human"}


def _new_archive(output: Path, forbidden_root: Path | None = None) -> None:
    if forbidden_root and output.resolve().is_relative_to(forbidden_root.resolve()):
        raise ValueError("mastra pilot: output inside application forbidden")
    output.mkdir(parents=True, exist_ok=False)


def prepare_review(path: str | Path, output: str | Path) -> dict:
    rows, digest = load_review_dataset(path)
    requests = [candidate_request(row) for row in rows]
    target = Path(output)
    _new_archive(target)
    raw = b"".join(json.dumps(row, ensure_ascii=False, allow_nan=False).encode() + b"\n"
                   for row in requests)
    (target / "requests.jsonl").write_bytes(raw)
    # Separate annotations: adapters receive requests.jsonl only.
    (target / "review-cases.json").write_bytes(_dump(rows))
    summary = {**_review_summary(rows, digest), "schema_version": "deposium.mastra-read-preparation/v0",
               "qualification": "review_only", "dataset_sha256": digest,
               "requests_sha256": _sha(raw), "projector_sha256": _sha(Path(__file__).read_bytes()),
               "projection_version": PROJECTION_VERSION, "model_calls": 0,
               "note": "bench.context-choice requests only; not a case/v2 campaign corpus"}
    (target / "manifest.json").write_bytes(_dump(summary))
    return summary


def _git(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(["git", "-C", str(root), *args], check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=20, env=_environment())
    except (OSError, subprocess.SubprocessError):
        raise ValueError("mastra pilot: unable to read pinned Git source") from None
    return result.stdout


def _snapshot(root: Path, revision: str, destination: Path, *, extra_sources: tuple[str, ...] = ()) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("mastra pilot: complete revision required")
    _git(root, "cat-file", "-e", revision + "^{commit}")
    modules = root / "node_modules"
    if not modules.is_dir():
        raise ValueError("mastra pilot: preinstalled MCPs dependencies required")
    # Read the pinned importer first: old qualifications retain their exact
    # closure; the new static import must never silently fall back to the WIP.
    agent = _git(root, "show", f"{revision}:{SOURCES[0]}")
    names = list(SOURCES)
    if b"./deposium-graph-tool.js" in agent or b"./deposium-graph-tool.ts" in agent:
        names.append(GRAPH_HELPER)
    for name in extra_sources:
        if (not isinstance(name, str) or not name.startswith("src/")
                or ".." in Path(name).parts or Path(name).as_posix() != name):
            raise ValueError("mastra pilot: invalid snapshot source")
        if name not in names:
            names.append(name)
    files = {}
    for name in names:
        data = agent if name == SOURCES[0] else _git(root, "show", f"{revision}:{name}")
        if len(data) > 16 * 1024 * 1024:
            raise ValueError("mastra pilot: source size limit")
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files[name] = _sha(data)
    (destination / "node_modules").symlink_to(modules.resolve(), target_is_directory=True)
    installed_lock = modules / ".package-lock.json"
    provenance = {"revision": revision, "source_kind": "committed_file_snapshot",
                  "files_sha256": files,
                  "installed_package_lock_sha256": _sha(_read(installed_lock)) if installed_lock.is_file() else None,
                  "installed_dependencies": "shared_read_only_not_a_frozen_closure",
                  "application_worktree_executed": False}
    (destination / ".deposium-snapshot.json").write_bytes(_dump({
        "schema_version": "deposium.mcps-snapshot/v1", **provenance}))
    return provenance


def check_control(control: dict, response: dict) -> dict:
    """Exact structural oracle for fixtures; no semantic selection score."""
    expected = control["expected"]
    if not isinstance(expected, dict) or not expected:
        raise ValueError("mastra pilot: empty contract oracle")
    checks = {key: key in response and typed_equal(response[key], value)
              for key, value in expected.items()}
    return {"passed": bool(checks) and all(checks.values()), "checks": checks}


def _native(request: dict, snapshot: Path, bridge: Path = BRIDGE) -> dict:
    try:
        result = subprocess.run(["node", "--max-old-space-size=256", str(bridge), str(snapshot)],
                                input=_dump(request), cwd=ROOT, env=_environment(),
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=30, check=True)
        if len(result.stdout) > 1024 * 1024:
            raise ValueError("large output")
        value = _json(result.stdout)
        if not isinstance(value, dict) or value.get("status") not in {"ok", "error"}:
            raise ValueError("invalid bridge response")
        if value["status"] == "ok" and value.get("case_id") != request.get("case_id"):
            raise ValueError("bridge response identity mismatch")
        return value
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": "native_contract_timeout"}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"status": "error", "error": "native_contract_transport_failed"}


def run_native_controls(mcps_root: str | Path, revision: str, output: str | Path, *, planner: bool = False) -> dict:
    root, target = Path(mcps_root).resolve(), Path(output)
    control_path, bridge = (PLANNER_CONTROLS, PLANNER_BRIDGE) if planner else (CONTROLS, BRIDGE)
    controls_data = _read(control_path)
    fixture = _json(controls_data)
    controls = fixture["controls"]
    if not isinstance(controls, list) or not controls:
        raise ValueError("mastra pilot: no native controls")
    ids = [control["case_id"] for control in controls]
    if len(set(ids)) != len(ids):
        raise ValueError("mastra pilot: duplicate native control")
    if target.exists():
        raise FileExistsError(target)
    if target.resolve().is_relative_to(root):
        raise ValueError("mastra pilot: output inside application forbidden")
    registry, registry_sha = load_registry()
    bench_files = {path: path.read_bytes() for path in (Path(__file__).resolve(), bridge, SNAPSHOT_HELPER)}
    bench_hashes = {str(path.relative_to(ROOT)): _sha(data) for path, data in bench_files.items()}
    results = []
    runtime_identity = None
    with tempfile.TemporaryDirectory(prefix="deposium-mastra-") as directory:
        provenance = _snapshot(root, revision, Path(directory))
        frozen_bridge = Path(directory) / "bench-mastra-read-pilot.mjs"
        frozen_bridge.write_bytes(bench_files[bridge])
        (Path(directory) / SNAPSHOT_HELPER.name).write_bytes(bench_files[SNAPSHOT_HELPER])
        _new_archive(target, root)
        (target / "controls.json").write_bytes(controls_data)
        (target / "stack-registry.json").write_bytes(_dump(registry))
        with (target / "results.jsonl").open("x", encoding="utf-8") as stream:
            for control in controls:
                request = {"case_id": control["case_id"], **deepcopy(control["request"])}
                if control.get("use_fixture", True):
                    request["fixture"] = deepcopy(fixture["backend_fixture"])
                start = time.monotonic()
                response = _native(request, Path(directory), frozen_bridge)
                if response.get("status") == "ok":
                    identity = {key: response.get(key) for key in ("runtime", "catalog_sha256", "source_files_sha256")}
                    if (identity["source_files_sha256"] != provenance["files_sha256"]
                            or not isinstance(identity["runtime"], dict)
                            or not isinstance(identity["catalog_sha256"], str)
                            or (runtime_identity is not None and identity != runtime_identity)):
                        response = {"status": "error", "error": "native_provenance_changed",
                                    "raw_response": response}
                    else:
                        runtime_identity = identity
                row = {"case_id": control["case_id"], "request": request, "response": response,
                       "contract_check": check_control(control, response),
                       "cold_process_wall_ms": (time.monotonic() - start) * 1000,
                       "selection_scored": False}
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                results.append(row)
        if any(path.read_bytes() != data for path, data in bench_files.items()):
            raise ValueError("mastra pilot: bench source changed; partial archive retained")
        hashes = {name: _sha((target / name).read_bytes()) for name in
                  ("controls.json", "results.jsonl", "stack-registry.json")}
        summary = {
            "schema_version": "deposium.mastra-native-contract-check/v0",
            "qualification": "real_planner_scripted_provider_mock_backends" if planner else "real_wrappers_mock_backends_no_planner",
            "comparable_to_three_label_candidate": False,
            "controls": len(results), "controls_passed": sum(row["contract_check"]["passed"] for row in results),
            "contract_status": "matched" if all(row["contract_check"]["passed"] for row in results) else "failed",
            "cases_scored": 0, "model_calls": 0, "semantic_evaluation_status": "not_run",
            "service_status": "not_observed", "source": provenance,
            "files_sha256": hashes, "stack_registry_sha256": registry_sha,
            "bench_files_sha256": bench_hashes,
            "components": [{"id": component["id"],
                            "qualification": "mock_backends" if component["id"] == "deposium_MCPs" else "not_exercised"}
                           for component in registry["components"]],
            "limits": ["Planner provider responses are scripted, with the full six-tool pool; no model comparison." if planner
                       else "No model selection or planner generation was performed.",
                       "searchHub and getCorpusStats are simulated, including returned counts and passages.",
                       "Caller scope is synthetic; no authentication, database isolation or live service is qualified.",
                       "Cold process duration is not decision latency or a speed-up measurement."],
        }
        (target / "summary.json").write_bytes(_dump(summary))
    return summary
