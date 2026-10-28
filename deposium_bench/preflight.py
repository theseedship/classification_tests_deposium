"""Read-only inventory and contract checks, shared by CLI and future notebooks.

This module never imports a target application, resolves a model or contacts a
service. A successful inspection is not a successful evaluation.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from . import __version__
from .git_inventory import InventoryError, inspect_stack
from .registry import RegistryError, load_registry, relative_path

MANIFEST_VERSION = "deposium.preflight/v1"
LOCKFILES = ("Cargo.lock", "uv.lock", "pnpm-lock.yaml", "package-lock.json",
             "bun.lock", "bun.lockb", "deno.lock", "poetry.lock")
MAX_FILE_BYTES = 16 * 1024 * 1024


def _issue(code: str, severity: str, message: str, component_id: str | None = None) -> dict:
    issue = {"code": code, "severity": severity, "message": message}
    if component_id is not None:
        issue["component_id"] = component_id
    return issue


def _file_record(root: Path, relative: str) -> dict:
    """Hash an explicitly selected source file, without persisting its content."""
    relative_path(relative)
    record = {"path": relative, "status": "missing", "sha256": None}
    base = root.resolve()
    target = base / relative
    try:
        resolved = target.resolve()
        if not resolved.is_relative_to(base):
            return {**record, "status": "unsafe_path"}
        # No secret files, opaque caches or symlinked source aliases are read.
        for part in Path(relative).parts:
            if (part.startswith(".env") or part in {"secrets", ".aws", ".git", "private"}
                    or part.endswith((".pem", ".key"))):
                return {**record, "status": "excluded"}
        current = base
        for part in Path(relative).parts:
            current = current / part
            if current.is_symlink():
                return {**record, "status": "unsafe_path"}
        if not target.is_file():
            return record
        before = target.stat()
        if before.st_size > MAX_FILE_BYTES:
            return {**record, "status": "too_large"}
        with target.open("rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
        after = target.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
                after.st_size, after.st_mtime_ns, after.st_ino):
            return {**record, "status": "changed_during_read"}
        if len(data) > MAX_FILE_BYTES:
            return {**record, "status": "too_large"}
        return {**record, "status": "present", "sha256": hashlib.sha256(data).hexdigest()}
    except (OSError, ValueError, RuntimeError):
        return {**record, "status": "unreadable"}


def _bench_provenance() -> dict:
    root = Path(__file__).resolve().parent.parent
    try:
        git = inspect_stack(root)["parent"]
    except InventoryError:
        git = None
    sources = [_file_record(root, str(path.relative_to(root)))
               for path in sorted((root / "deposium_bench").glob("*.py"))]
    return {"version": __version__, "git": git, "sources": sources,
            "source_archive": "not_captured"}


def build_preflight(stack_root: str | Path, *, registry_path: str | Path | None = None,
                    selected_components: list[str] | None = None) -> dict:
    """Inspect a local stack and record planned contracts without executing them.

    None selects all known and discovered components for inspection. An explicit
    selection must contain registered IDs; omitted components remain visible.
    """
    registry, registry_hash = load_registry(registry_path)
    known_ids = {component["id"] for component in registry["components"]}
    if selected_components is not None:
        if not selected_components or len(set(selected_components)) != len(selected_components):
            raise RegistryError("selection: expected non-empty unique component IDs")
        if set(selected_components) - known_ids:
            raise RegistryError("selection: unknown component ID")
    selected = known_ids if selected_components is None else set(selected_components)
    stack = inspect_stack(stack_root)
    root = Path(stack["root"])
    discovered = {component["path"]: component for component in stack["components"]}
    issues = list(stack["issues"])
    if stack["parent"]["dirty"]:
        issues.append(_issue("parent_dirty", "warning", "Parent checkout has uncommitted changes."))
    components = []
    for definition in registry["components"]:
        component_id = definition["id"]
        selected_here = component_id in selected
        source = discovered.pop(definition["path"], None)
        severity = "error" if selected_here else "warning"
        initialized = source is not None and source["state"] == "initialized"
        if source is None:
            issues.append(_issue("registered_component_missing", severity,
                                 "Registered component is absent from the discovered stack.", component_id))
        else:
            for issue in source["issues"]:
                issues.append({**issue, "component_id": component_id})
            if not initialized:
                issues.append(_issue("component_unavailable", severity,
                                     "Component cannot be inspected as an initialized checkout.", component_id))
            if source["dirty"]:
                issues.append(_issue("component_dirty", "warning",
                                     "Component checkout has uncommitted changes.", component_id))
        contracts = []
        for contract in definition["contracts"]:
            if initialized and selected_here:
                probe = _file_record(root / definition["path"], contract["entrypoint"]["path"])
                tests = [_file_record(root / definition["path"], path) for path in contract["tests"]]
                if probe["status"] != "present":
                    issues.append(_issue("entrypoint_unavailable", "error",
                                         f"Source for contract {contract['id']} cannot be fingerprinted.", component_id))
                if any(test["status"] != "present" for test in tests):
                    issues.append(_issue("test_reference_unavailable", "warning",
                                         f"Some test sources for contract {contract['id']} are unavailable.", component_id))
            else:
                status = "not_selected" if not selected_here else "unavailable"
                probe = {"path": contract["entrypoint"]["path"], "status": status, "sha256": None}
                tests = [{"path": path, "status": status, "sha256": None} for path in contract["tests"]]
            contracts.append({**contract, "entrypoint_file": probe, "test_files": tests,
                              "execution_status": "not_run", "case_ids": [],
                              "assertion_status": "planned"})
        lockfiles = []
        if initialized and selected_here:
            for name in LOCKFILES:
                probe = _file_record(root / definition["path"], name)
                if probe["status"] != "missing":
                    lockfiles.append(probe)
        components.append({"id": component_id, "path": definition["path"],
                           "owner": definition["owner"], "role": definition["role"],
                           "packs": definition["packs"], "notes": definition["notes"],
                           "registry_status": "registered" if source else "missing",
                           "selected": selected_here,
                           "omission_reason": None if selected_here else "not_selected",
                           "source_state": source["state"] if source else "missing",
                           "contracts": contracts, "root_lockfiles": lockfiles,
                           "runtime": {"status": "not_observed", "executed": False},
                           "source_archive": "not_captured"})
    for path, source in sorted(discovered.items()):
        issues.append(_issue("unregistered_component", "error",
                             "Discovered component has no registry contract.", path))
        issues.extend({**issue, "component_id": path} for issue in source["issues"])
        components.append({"id": None, "path": path, "owner": None, "role": None,
                           "packs": [], "notes": "Discovered without a registered contract.",
                           "registry_status": "unregistered", "selected": selected_components is None,
                           "omission_reason": None if selected_components is None else "not_selected",
                           "source_state": source["state"], "contracts": [], "root_lockfiles": [],
                           "runtime": {"status": "not_observed", "executed": False},
                           "source_archive": "not_captured"})
    if not stack["components"]:
        issues.append(_issue("empty_stack", "error", "No submodule was discovered."))
    counts = Counter(issue["severity"] for issue in issues)
    status = "invalid" if counts["error"] else "attention" if counts["warning"] else "ok"
    selected_contracts = [contract for component in components if component["selected"]
                          for contract in component["contracts"]]
    compose_files = []
    for path in ("deposium-local/docker-compose.yml", "deposium-local/docker-compose.override.yml"):
        probe = _file_record(root, path)
        if probe["status"] != "missing":
            compose_files.append(probe)
    return {
        "schema_version": MANIFEST_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "offline_stack_preflight",
        "status": status,
        "evaluation": {"status": "not_run", "cases_scored": 0, "campaign_ready": False},
        "bench": _bench_provenance(),
        "registry": {"schema_version": registry["schema_version"], "sha256": registry_hash},
        "stack": stack,
        "selection": {"mode": "all" if selected_components is None else "explicit",
                      "selected_ids": sorted(selected)},
        "components": components,
        "external_dependencies": [{**dependency, "status": "not_observed"}
                                  for dependency in registry["external_dependencies"]],
        "runtime_provenance": {"status": "not_observed", "compose_file_candidates": compose_files,
                               "effective_compose_files": None, "images": None,
                               "build_sources": None, "data_state": None},
        "coverage": {"registered_components": len(registry["components"]),
                     "discovered_components": len(stack["components"]),
                     "selected_components": sum(c["selected"] for c in components),
                     "selected_contracts": len(selected_contracts),
                     "source_files_present": sum(c["entrypoint_file"]["status"] == "present"
                                                 for c in selected_contracts),
                     "adapters": dict(sorted(Counter(c["adapter_status"] for c in selected_contracts).items())),
                     "cases_defined": 0, "cases_scored": 0},
        "issues": issues,
        "limitations": ["Inventory is a best-effort read, not an atomic stack snapshot.",
                        "Git fingerprint covers metadata, not the contents of all local changes.",
                        "Only registered entrypoint/test files and root lockfiles are fingerprinted.",
                        "Source presence does not validate a symbol, API schema or runtime behavior.",
                        "Compose candidates are hashed, not resolved or identified as active.",
                        "No code, service, adapter or model was executed; no corpus was scored."],
    }


def render_summary(manifest: dict) -> str:
    coverage = manifest["coverage"]
    lines = [f"Deposium — préflight : {manifest['status']}",
             f"Stack : {manifest['stack']['root']}",
             f"Composants : {coverage['discovered_components']} découverts / "
             f"{coverage['registered_components']} enregistrés; {coverage['selected_components']} sélectionnés.",
             f"Contrats : {coverage['source_files_present']} sources présentes / {coverage['selected_contracts']} sélectionnés.",
             "Évaluation : non exécutée, 0 cas scoré; campagne non prête.",
             "Runtime, images et données : non observés."]
    for component in manifest["components"]:
        selection = "sélectionné" if component["selected"] else "omis : not_selected"
        lines.append(f"- {component['path']}: {component['source_state']}, "
                     f"{component['registry_status']}, {selection}")
    for issue in manifest["issues"]:
        component = f" [{issue['component_id']}]" if "component_id" in issue else ""
        lines.append(f"{issue['severity']}: {issue['code']}{component} — {issue['message']}")
    return "\n".join(lines) + "\n"


def write_manifest(manifest: dict, destination: str | Path) -> Path:
    """Create a new archive; existing paths are never replaced."""
    path = Path(destination)
    stack_root = Path(manifest["stack"]["root"]).resolve()
    if path.resolve().is_relative_to(stack_root):
        raise ValueError("manifest output must be outside the application stack")
    payload = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    # O_EXCL via 'x' also rejects an existing symlink, preserving prior archives.
    with path.open("x", encoding="utf-8") as handle:
        handle.write(payload)
    return path
