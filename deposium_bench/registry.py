"""Validate the versioned registry without importing any application code."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = "deposium.stack-registry/v1"
DEFAULT_REGISTRY = Path(__file__).parent / "data" / "stack-registry.json"
PACKS = {"DOC", "FOLLOWUP", "PRESENTATION", "SOURCES", "EVIDENCE", "CLAIMS",
         "ROBUSTNESS", "CONTEXT", "EXTRACTION", "PRODUCT"}
KINDS = {"function", "http", "library", "bootstrap"}
LEVELS = {"A", "B", "C"}
ADAPTER_STATES = {"planned", "available", "incompatible"}


class RegistryError(ValueError):
    """A registry is malformed or cannot identify its components safely."""


def _object(value: Any, required: set[str], optional: set[str], where: str) -> None:
    if not isinstance(value, dict):
        raise RegistryError(f"{where}: expected an object")
    if required - value.keys() or value.keys() - required - optional:
        raise RegistryError(f"{where}: missing or unknown fields")


def _text(value: Any, where: str) -> None:
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise RegistryError(f"{where}: expected non-empty text without control characters")


def relative_path(value: Any, where: str = "path") -> str:
    _text(value, where)
    path = PurePosixPath(value)
    if (path.is_absolute() or path.as_posix() != value or
            any(part in {".", "..", ".git"} for part in path.parts) or
            not path.parts or "\\" in value or ":" in value):
        raise RegistryError(f"{where}: expected a normalized relative path")
    return value


def _texts(value: Any, where: str, choices: set[str] | None = None,
           *, empty: bool = False) -> None:
    if not isinstance(value, list) or (not value and not empty):
        raise RegistryError(f"{where}: expected {'a' if empty else 'a non-empty'} list")
    for item in value:
        _text(item, where)
        if choices is not None and item not in choices:
            raise RegistryError(f"{where}: unknown value")
    if len(value) != len(set(value)):
        raise RegistryError(f"{where}: duplicate values")


def validate_registry(value: Any) -> dict:
    """Enforce v1 structure and cross-record invariants; return the input."""
    _object(value, {"schema_version", "components", "external_dependencies"}, set(), "registry")
    if value["schema_version"] != SCHEMA_VERSION:
        raise RegistryError("registry: unsupported schema_version")
    if not isinstance(value["components"], list) or not value["components"]:
        raise RegistryError("registry: components must not be empty")
    ids: set[str] = set()
    paths: set[str] = set()
    contracts: set[str] = set()
    for component in value["components"]:
        _object(component, {"id", "path", "owner", "role", "packs", "contracts", "notes"},
                set(), "component")
        for key in ("id", "owner", "role", "notes"):
            _text(component[key], f"component.{key}")
        relative_path(component["path"], "component.path")
        if component["id"] in ids or component["path"] in paths:
            raise RegistryError("registry: duplicate component id or path")
        ids.add(component["id"])
        paths.add(component["path"])
        _texts(component["packs"], "component.packs", PACKS)
        if not isinstance(component["contracts"], list) or not component["contracts"]:
            raise RegistryError("component: contracts must not be empty")
        for contract in component["contracts"]:
            _object(contract, {"id", "entrypoint", "kind", "levels", "adapter_status",
                               "assertions", "tests"}, set(), "contract")
            _text(contract["id"], "contract.id")
            if contract["id"] in contracts:
                raise RegistryError("registry: duplicate contract id")
            contracts.add(contract["id"])
            for field, choices in (("kind", KINDS), ("adapter_status", ADAPTER_STATES)):
                if not isinstance(contract[field], str) or contract[field] not in choices:
                    raise RegistryError(f"contract.{field}: unknown value")
            _texts(contract["levels"], "contract.levels", LEVELS)
            _texts(contract["assertions"], "contract.assertions")
            _texts(contract["tests"], "contract.tests", empty=True)
            for path in contract["tests"]:
                relative_path(path, "contract.tests")
            _object(contract["entrypoint"], {"path"}, {"symbol"}, "contract.entrypoint")
            relative_path(contract["entrypoint"]["path"], "contract.entrypoint.path")
            if "symbol" in contract["entrypoint"]:
                _text(contract["entrypoint"]["symbol"], "contract.entrypoint.symbol")
    dependencies = value["external_dependencies"]
    if not isinstance(dependencies, list):
        raise RegistryError("registry: external_dependencies must be a list")
    dependency_ids: set[str] = set()
    for dependency in dependencies:
        _object(dependency, {"id", "kind", "description", "required_by"}, set(), "dependency")
        for key in ("id", "kind", "description"):
            _text(dependency[key], f"dependency.{key}")
        if dependency["id"] in dependency_ids:
            raise RegistryError("registry: duplicate dependency id")
        dependency_ids.add(dependency["id"])
        _texts(dependency["required_by"], "dependency.required_by", ids)
    return value


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise RegistryError("registry: duplicate JSON key")
        result[key] = value
    return result


def load_registry(path: str | Path | None = None) -> tuple[dict, str]:
    """Return validated registry plus SHA-256 of the original bytes."""
    try:
        payload = Path(path or DEFAULT_REGISTRY).read_bytes()
        value = json.loads(payload, object_pairs_hook=_unique_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryError("registry: cannot read valid UTF-8 JSON") from exc
    return validate_registry(value), hashlib.sha256(payload).hexdigest()
