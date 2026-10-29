"""Candidate transports, with no business routing or reference annotations.

Importing this module performs no I/O. Real MCPs replay is an explicit profile
operation, in a separate process for each request, with a restricted environment.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from .cases import CaseError, _json as validate_json, _no_annotations


class AdapterError(ValueError):
    """A candidate profile, recording, or request is invalid."""


CONTRACTS = {
    "mcps.document-plan": ("src/services/chat-document-request-plan.ts", "normalizeChatDocumentRequest"),
    "mcps.document-followup": ("src/services/chat-document-selection.ts", "resolveDocumentFollowUp"),
    "mcps.scope-dispatch": ("src/services/scope-dispatcher.ts", "buildScopeDispatchDecision"),
    "mcps.semantic-source-route": ("src/services/source-route-resolver.ts", "resolveSemanticSourceRoute"),
}
STATUSES = {"ok", "unsupported", "missing", "error", "timeout", "abstain"}
_FIELDS = {"schema_version", "profile_id", "adapter", "qualification", "capabilities", "model",
           "timeout_seconds", "revision", "recordings"}
_BRIDGE = Path(__file__).resolve().parents[1] / "bridges" / "mcps-decisions.mjs"
# Reviewed runtime closure. Type-only imports disappear in the TS loader.
# Refuse an expanded runtime graph; it requires a new safety review.
_IMPORTS = {
    "src/services/chat-document-request-plan.ts": {"./canonical-chat-file-answer-policy.js"},
    "src/services/canonical-chat-file-answer-policy.ts": {"node:crypto", "./citation-document-ids.js"},
    "src/services/citation-document-ids.ts": set(),
    "src/services/chat-document-selection.ts": {"zod"},
    "src/services/scope-dispatcher.ts": {"./chat-artifact-context.js"},
    "src/services/chat-artifact-context.ts": set(),
    "src/services/source-route-resolver.ts": {"../config/connectors.js", "./connector-picker.js"},
    "src/services/connector-picker.ts": {"../config/connectors.js"},
    "src/config/connectors.ts": {"../types/chat-stream.js"},
    "src/types/chat-stream.ts": {"zod"},
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identity(value: Any) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False).encode())


def _read(path: Path, limit: int = 16 * 1024 * 1024) -> bytes:
    try:
        if not path.is_file() or path.stat().st_size > limit:
            raise AdapterError("Candidate file is missing or exceeds the size limit.")
        return path.read_bytes()
    except OSError:
        raise AdapterError("Candidate file could not be read.") from None


def _json(data: bytes | str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise AdapterError("Duplicate JSON key.")
            result[key] = value
        return result
    try:
        value = json.loads(data, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(AdapterError("Non-finite JSON number.")))
        validate_json(value)
        return value
    except (ValueError, UnicodeError):
        raise AdapterError("Invalid candidate JSON.") from None


def _validate_profile(profile: dict) -> None:
    if not isinstance(profile, dict) or set(profile) != _FIELDS:
        raise AdapterError("Candidate profile fields do not match deposium.candidate/v1.")
    if profile["schema_version"] != "deposium.candidate/v1" or not isinstance(profile["profile_id"], str) or not profile["profile_id"].strip():
        raise AdapterError("Invalid candidate profile identity.")
    adapter = profile["adapter"]
    if not isinstance(adapter, str) or adapter not in {"mcps", "mcps_resident", "recorded", "julia", "gliner", "jev_http", "decision3_http", "indecis", "decision2", "vela2", "d3", "noma", "laya", "small_model", "systemone_local", "gliclass", "vela3_fast"}:
        raise AdapterError("Unknown candidate adapter.")
    capabilities = profile["capabilities"]
    allowed = set(CONTRACTS) | ({"mcps.search"} if adapter == "recorded" else set())
    if adapter in {"julia", "gliner", "jev_http", "decision3_http", "indecis", "decision2", "vela2", "d3", "noma", "laya", "small_model", "systemone_local", "gliclass", "vela3_fast", "recorded"}:
        allowed.add("bench.context-choice")
    if (not isinstance(capabilities, list) or not capabilities
            or any(not isinstance(item, str) or item not in allowed for item in capabilities)
            or len(set(capabilities)) != len(capabilities)):
        raise AdapterError("Invalid or duplicate candidate capabilities.")
    timeout = profile["timeout_seconds"]
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise AdapterError("Candidate timeout must be finite and positive.")
    if adapter == "julia":
        from .julia_adapter import validate_model_profile
        validate_model_profile(profile)
        return
    if adapter == "gliner":
        from .gliner_adapter import validate_model_profile
        validate_model_profile(profile)
        return
    if adapter == "indecis":
        from .indecis_adapter import validate_model_profile
        validate_model_profile(profile)
        return
    if adapter == "decision3_http":
        from .decision3_http_adapter import validate_model_profile
        validate_model_profile(profile)
        return
    if adapter == "jev_http":
        from .jev_http_adapter import validate_model_profile
        validate_model_profile(profile)
        return
    if adapter == "systemone_local":
        from .systemone_local import validate_model_profile
        validate_model_profile(profile)
        return
    if adapter == "decision2":
        from .decision2_adapter import validate_model_profile
        validate_model_profile(profile)
        return
    if adapter == "vela2":
        from .vela2_adapter import validate_model_profile
        validate_model_profile(profile)
        return
    if adapter == "d3":
        from .d3_adapter import validate_model_profile
        validate_model_profile(profile)
        return
    if adapter == "small_model":
        from .small_model_adapter import validate_model_profile
        validate_model_profile(profile)
        return
    if adapter == "noma":
        from .noma_adapter import validate_model_profile
        validate_model_profile(profile)
        return
    if adapter == "vela3_fast":
        from .vela3_fast_adapter import validate_model_profile
        validate_model_profile(profile)
        return
    if adapter == "gliclass":
        from .gliclass_adapter import validate_model_profile
        validate_model_profile(profile)
        return
    if adapter == "laya":
        from .laya_adapter import validate_model_profile
        validate_model_profile(profile)
        return
    if profile["model"] is not None:
        raise AdapterError("These replay adapters do not load a model.")
    if adapter in {"mcps", "mcps_resident"}:
        if (profile["qualification"] != "component_replay" or profile["recordings"] is not None
                or not isinstance(profile["revision"], str) or not re.fullmatch(r"[0-9a-f]{40}", profile["revision"])):
            raise AdapterError("MCPs replay requires a pinned revision and component_replay qualification.")
    elif (profile["qualification"] != "harness_control" or profile["revision"] is not None
          or not isinstance(profile["recordings"], str) or not profile["recordings"].strip()):
        raise AdapterError("Recorded controls require a recordings file and harness_control qualification.")


def parse_profile(data: bytes) -> tuple[dict, str]:
    profile = _json(data)
    _validate_profile(profile)
    return profile, _sha(data)


def load_profile(path: str | Path) -> tuple[dict, str]:
    return parse_profile(_read(Path(path), 1024 * 1024))


def _envelope(status: str, output: Any = None, raw_output: Any = None, error: str | None = None) -> dict:
    return dict(status=status, output=output, raw_output=raw_output, error=error)


def _normalize_envelope(value: Any) -> dict:
    if not isinstance(value, dict) or set(value) != {"status", "output", "raw_output", "error"}:
        raise AdapterError("Invalid adapter response envelope.")
    if not isinstance(value["status"], str) or value["status"] not in STATUSES:
        raise AdapterError("Unknown adapter response status.")
    if value["error"] is not None and not isinstance(value["error"], str):
        raise AdapterError("Invalid adapter error type.")
    result = copy.deepcopy(value)
    # Error text is an identifier, never a subprocess exception or provider log.
    if result["error"] is not None and not re.fullmatch(r"[a-z][a-z0-9_]{0,95}", result["error"]):
        result["error"] = "redacted_adapter_error"
    try:
        validate_json(result)
    except CaseError:
        raise AdapterError("Adapter output must be finite JSON.") from None
    return result


def _request(request: dict) -> dict:
    if (not isinstance(request, dict) or not isinstance(request.get("case_id"), str)
            or not request["case_id"] or not isinstance(request.get("contract_id"), str)
            or not isinstance(request.get("input"), dict)):
        raise AdapterError("Candidate request requires case_id, contract_id and input.")
    # Whitelist the transport fields; a full annotated case cannot leak its gold.
    clean = {key: copy.deepcopy(request[key]) for key in ("case_id", "contract_id", "input")}
    try:
        validate_json(clean)
        _no_annotations(clean["input"])
        encoded = json.dumps(clean, allow_nan=False)
    except (ValueError, TypeError):
        raise AdapterError("Candidate input must be finite JSON.") from None
    if len(encoded.encode()) > 1024 * 1024:
        raise AdapterError("Candidate request exceeds the size limit.")
    return clean


def _environment() -> dict[str, str]:
    # Do not inherit HOME, credentials, NODE_OPTIONS, Git selectors or dotenv flags.
    return {"PATH": os.environ.get("PATH", os.defpath), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            "TZ": "UTC", "TSX_DISABLE_CACHE": "1", "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _run(command: list[str], timeout: float, input_text: str | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, input=input_text, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          text=True, check=False, timeout=timeout, env=_environment(), cwd=cwd)


def _base_provenance(profile: dict, profile_path: Path) -> tuple[dict, dict]:
    # Fingerprint the parsed profile actually supplied, never reread a mutable
    # source path. The campaign separately retains the source file byte hash.
    profile_sha = _identity(profile)
    normalized = {key: value for key, value in profile.items() if key != "recordings"}
    adapter_sha = _sha(_read(Path(__file__)))
    provenance = dict(profile_sha256=profile_sha, adapter_sha256=adapter_sha,
                      qualification=profile["qualification"], adapter=profile["adapter"],
                      model=None, capabilities=list(profile["capabilities"]))
    return provenance, dict(profile=normalized, adapter_sha256=adapter_sha)


class RecordedAdapter:
    def __init__(self, profile: dict, profile_path: Path, recordings_data: bytes | None = None):
        self.capabilities = list(profile["capabilities"])
        self.provenance, identity = _base_provenance(profile, profile_path)
        data = (_read((profile_path.parent / profile["recordings"]).resolve())
                if recordings_data is None else recordings_data)
        if len(data) > 16 * 1024 * 1024:
            raise AdapterError("Recording file exceeds the size limit.")
        self._entries: dict[str, dict] = {}
        for line in data.splitlines():
            if not line.strip():
                raise AdapterError("Blank recording record.")
            item = _json(line)
            if not isinstance(item, dict) or set(item) != {"case_id", "status", "output", "raw_output", "error"}:
                raise AdapterError("Unknown or missing recording fields.")
            case_id = item.pop("case_id")
            if not isinstance(case_id, str) or not case_id or case_id in self._entries:
                raise AdapterError("Invalid or duplicate recording case_id.")
            self._entries[case_id] = _normalize_envelope(item)
        if not self._entries:
            raise AdapterError("Recording file contains zero responses.")
        digest = _sha(data)
        self.provenance.update(recordings_sha256=digest, available=True, recordings_count=len(self._entries),
                               identity_sha256=_identity({**identity, "recordings_sha256": digest}))

    def predict(self, request: dict) -> dict:
        request = _request(request)
        if request["contract_id"] not in self.capabilities:
            return _envelope("unsupported", error="unsupported_contract")
        return copy.deepcopy(self._entries.get(request["case_id"], _envelope("missing", error="recording_missing")))


def _source_hashes(root: Path) -> dict[str, str]:
    hashes = {}
    for relative, expected in _IMPORTS.items():
        path = root / relative
        if not path.resolve().is_relative_to(root):
            raise AdapterError("unsafe_source_path")
        data = _read(path)
        source = data.decode("utf-8")
        matches = re.findall(r"^import\s+(type\s+)?(?:[^;]*?)\s+from\s+['\"]([^'\"]+)['\"]", source, re.MULTILINE)
        actual = {module for type_only, module in matches if not type_only}
        if actual != expected or re.search(r"\b(?:import|require)\s*\(", source) or re.search(r"^import\s*['\"]|^export\b[^\n]*\bfrom\b", source, re.MULTILINE):
            raise AdapterError("runtime_import_closure_changed")
        hashes[relative] = _sha(data)
    return hashes


def _lock_hashes(root: Path) -> dict[str, str]:
    return {name: _sha(_read(root / name)) for name in
            ("package.json", "pnpm-lock.yaml", "package-lock.json", "bun.lock", "bun.lockb", "yarn.lock")
            if (root / name).is_file()}


def _runtime_unchanged(artifacts: dict) -> bool:
    """Check observed file identities, without hashing the runtime for every case."""
    for file in artifacts["files"]:
        stat = Path(file["path"]).stat()
        current = {"size": stat.st_size, "mtime_ns": str(stat.st_mtime_ns),
                   "ctime_ns": str(stat.st_ctime_ns), "device": str(stat.st_dev), "inode": str(stat.st_ino)}
        if any(current[key] != file[key] for key in current):
            return False
    return True


def _prepare_mcps(root: Path, profile: dict) -> tuple[list[str], dict]:
    if not root.is_dir() or not (root / ".git").exists():
        raise FileNotFoundError("mcps_checkout_missing")
    git = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(root)]
    head = _run(git + ["rev-parse", "--verify", "HEAD^{commit}"], 15)
    if head.returncode:
        raise AdapterError("mcps_git_unavailable")
    head_sha = head.stdout.strip()
    if head_sha != profile["revision"]:
        raise AdapterError("mcps_revision_mismatch")
    status = _run(git + ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=all"], 15)
    if status.returncode:
        raise AdapterError("mcps_status_unavailable")
    sources = _source_hashes(root)
    locks = _lock_hashes(root)
    if len(locks) < 2:
        raise AdapterError("mcps_lockfile_missing")
    node = shutil.which("node", path=_environment()["PATH"])
    if node is None:
        raise FileNotFoundError("node_unavailable")
    # Pin the observed executable, not a mutable PATH or symlink alias.
    node = str(Path(node).resolve())
    command = [node, str(_BRIDGE), str(root)]
    probe = _run(command + ["--probe"], profile["timeout_seconds"], cwd=_BRIDGE.parent)
    if probe.returncode:
        raise AdapterError("bridge_probe_failed")
    metadata = _json(probe.stdout)
    if (not isinstance(metadata, dict) or metadata.get("status") != "ok"
            or metadata.get("capabilities") != list(CONTRACTS)
            or not isinstance(metadata.get("runtime"), dict)
            or set(metadata["runtime"]) != {"node", "tsx", "zod"}
            or any(not isinstance(value, str) or not value for value in metadata["runtime"].values())
            or not isinstance(metadata.get("runtime_artifacts"), dict)
            or not isinstance(metadata["runtime_artifacts"].get("files"), list)
            or not metadata["runtime_artifacts"]["files"]):
        raise AdapterError("bridge_probe_failed")
    if (sources != _source_hashes(root) or locks != _lock_hashes(root)
            or not _runtime_unchanged(metadata["runtime_artifacts"])):
        raise AdapterError("runtime_changed_during_probe")
    expected_roots = {"node": node, "packages": {
        name: package["root"] for name, package in metadata["runtime_artifacts"]["packages"].items()}}
    node_files = [file for file in metadata["runtime_artifacts"]["files"] if file["owner"] == "node"]
    if (metadata.get("runtime_roots") != expected_roots or len(node_files) != 1
            or node_files[0]["path"] != node):
        raise AdapterError("runtime_resolution_changed")
    # The bridge checks fresh package resolution before imports and after calls;
    # old files remaining intact must not hide a retargeted package symlink.
    command += ["--expected-runtime", json.dumps(expected_roots, sort_keys=True)]
    return command, dict(component={"root": str(root), "head": head_sha, "dirty": bool(status.stdout),
                                    "canonical": not bool(status.stdout)}, sources=sources, lockfiles=locks,
                         runtime=metadata["runtime"], runtime_artifacts=metadata["runtime_artifacts"],
                         bridge_sha256=_sha(_read(_BRIDGE)),
                         entrypoints={key: dict(module=entry[0], export=entry[1]) for key, entry in CONTRACTS.items()},
                         transport="one_process_per_request_json_stdin", available=True,
                         guards="isolated_function_only; no authorization, HTTP, retrieval or product guards")


class McpsAdapter:
    def __init__(self, profile: dict, profile_path: Path, stack_root: Path | None):
        self.capabilities = list(profile["capabilities"])
        self._timeout = profile["timeout_seconds"]
        self.provenance, identity = _base_provenance(profile, profile_path)
        self._failure: dict | None = None
        self._command: list[str] = []
        if stack_root is None:
            self._failure = _envelope("missing", error="stack_root_required")
        else:
            root = stack_root.expanduser().resolve() / "deposium_MCPs"
            try:
                self._command, metadata = _prepare_mcps(root, profile)
                self.provenance.update(metadata)
                identity.update({key: metadata[key] for key in
                                 ("sources", "lockfiles", "runtime", "runtime_artifacts", "bridge_sha256", "entrypoints")})
            except (FileNotFoundError, OSError):
                self._failure = _envelope("missing", error="mcps_runtime_missing")
            except subprocess.TimeoutExpired:
                self._failure = _envelope("timeout", error="bridge_probe_timeout")
            except (AdapterError, UnicodeError):
                self._failure = _envelope("error", error="mcps_checkout_or_runtime_incompatible")
        if self._failure is not None:
            self.provenance.update(available=False, availability_error=self._failure["error"])
            identity["availability_error"] = self._failure["error"]
        self.provenance["identity_sha256"] = _identity(identity)

    def _unchanged(self) -> bool:
        root = Path(self.provenance["component"]["root"])
        return (_source_hashes(root) == self.provenance["sources"]
                and _lock_hashes(root) == self.provenance["lockfiles"]
                and _sha(_read(_BRIDGE)) == self.provenance["bridge_sha256"]
                and _runtime_unchanged(self.provenance["runtime_artifacts"]))

    def predict(self, request: dict) -> dict:
        request = _request(request)
        if request["contract_id"] not in self.capabilities:
            return _envelope("unsupported", error="unsupported_contract")
        if self._failure is not None:
            return copy.deepcopy(self._failure)
        try:
            if not self._unchanged():
                return _envelope("error", error="mcps_runtime_changed")
            process = _run(self._command, self._timeout, json.dumps(request, allow_nan=False), _BRIDGE.parent)
            if not self._unchanged():
                return _envelope("error", error="mcps_runtime_changed")
            if process.returncode:
                return _envelope("error", error="bridge_process_failed")
            if not process.stdout.strip():
                return _envelope("missing", error="bridge_no_output")
            return _normalize_envelope(_json(process.stdout))
        except subprocess.TimeoutExpired:
            return _envelope("timeout", error="bridge_timeout")
        except OSError:
            return _envelope("missing", error="bridge_runtime_missing")
        except AdapterError:
            return _envelope("error", error="bridge_invalid_output")


def create_adapter(profile: dict, profile_path: str | Path, stack_root: str | Path | None = None,
                   *, recordings_data: bytes | None = None):
    _validate_profile(profile)
    profile = copy.deepcopy(profile)
    path = Path(profile_path).resolve()
    if profile["adapter"] == "recorded":
        return RecordedAdapter(profile, path, recordings_data)
    if profile["adapter"] == "julia":
        from .julia_adapter import JuliaAdapter
        return JuliaAdapter(profile, path)
    if profile["adapter"] == "gliner":
        from .gliner_adapter import GLiNERAdapter
        return GLiNERAdapter(profile, path)
    if profile["adapter"] == "indecis":
        from .indecis_adapter import IndecisAdapter
        return IndecisAdapter(profile, path)
    if profile["adapter"] == "decision3_http":
        from .decision3_http_adapter import Decision3HTTPAdapter
        return Decision3HTTPAdapter(profile, path)
    if profile["adapter"] == "jev_http":
        from .jev_http_adapter import JevHTTPAdapter
        return JevHTTPAdapter(profile, path)
    if profile["adapter"] == "systemone_local":
        from .systemone_local import LocalSystemOneAdapter
        return LocalSystemOneAdapter(profile, path)
    if profile["adapter"] == "decision2":
        from .decision2_adapter import Decision2Adapter
        return Decision2Adapter(profile, path)
    if profile["adapter"] == "vela2":
        from .vela2_adapter import Vela2Adapter
        return Vela2Adapter(profile, path)
    if profile["adapter"] == "d3":
        from .d3_adapter import D3Adapter
        return D3Adapter(profile, path)
    if profile["adapter"] == "small_model":
        from .small_model_adapter import SmallModelAdapter
        return SmallModelAdapter(profile, path)
    if profile["adapter"] == "noma":
        from .noma_adapter import NomaAdapter
        return NomaAdapter(profile, path)
    if profile["adapter"] == "vela3_fast":
        from .vela3_fast_adapter import Vela3FastAdapter
        return Vela3FastAdapter(profile, path)
    if profile["adapter"] == "gliclass":
        from .gliclass_adapter import GLiClassAdapter
        return GLiClassAdapter(profile, path)
    if profile["adapter"] == "laya":
        from .laya_adapter import LayaAdapter
        return LayaAdapter(profile, path)
    if profile["adapter"] == "mcps_resident":
        from .mcps_resident import ResidentMCPAdapter
        return ResidentMCPAdapter(profile, path, Path(stack_root) if stack_root is not None else None)
    return McpsAdapter(profile, path, Path(stack_root) if stack_root is not None else None)
