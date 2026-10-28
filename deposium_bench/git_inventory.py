"""Read-only Git inventory; its fingerprint describes metadata, not source bytes.

No source files, diffs, remote URLs, models or services are read. Only the
working .gitmodules file is hashed. Dirty counts cannot reproduce local edits.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess
from typing import Any


class InventoryError(ValueError):
    """The requested root cannot be inventoried safely."""


_TIMEOUT = 15
_MAX_DEPTH = 32
_MAX_COMPONENTS = 4096
_MAX_GITMODULES_BYTES = 1024 * 1024
_CONFLICTS = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}


class _GitError(Exception):
    def __init__(self, code: str):
        self.code = code


def _git(repo: Path, *args: str, allow_missing: bool = False) -> bytes:
    # Ambient Git selectors must not redirect inspection to a different repo.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(repo), *args],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env,
            timeout=_TIMEOUT, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise _GitError("git_timeout") from exc
    except OSError as exc:
        raise _GitError("git_unavailable") from exc
    if result.returncode != 0:
        if allow_missing and result.returncode == 1:
            return b""
        raise _GitError("git_command_failed")
    return result.stdout


def _issue(code: str, message: str, severity: str = "warning") -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _true_root(path: Path) -> bool:
    if not path.is_dir() or not (path / ".git").exists():
        return False
    if _git(path, "rev-parse", "--is-bare-repository").strip() != b"false":
        return False
    raw_top = _git(path, "rev-parse", "--show-toplevel")
    top = os.fsdecode(raw_top[:-1] if raw_top.endswith(b"\n") else raw_top)
    return Path(top).resolve() == path


def _status(repo: Path) -> tuple[dict[str, int], dict[str, set[str]]]:
    # Never let Git itself descend into potentially unsafe submodule paths.
    records = _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all",
                   "--ignore-submodules=all").split(b"\0")
    counts = dict(staged=0, unstaged=0, untracked=0, conflicted=0)
    counted: dict[str, set[str]] = {key: set() for key in counts}
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 3 or record[2:3] != b" ":
            raise _GitError("invalid_git_status")
        xy = record[:2].decode("ascii")
        path = os.fsdecode(record[3:])
        if xy == "??":
            counts["untracked"] += 1
            counted["untracked"].add(path)
        elif xy != "!!":
            for key, present in (("staged", xy[0] != " "), ("unstaged", xy[1] != " "),
                                 ("conflicted", xy in _CONFLICTS or "U" in xy)):
                if present:
                    counts[key] += 1
                    counted[key].add(path)
        if "R" in xy or "C" in xy:
            # With -z the destination comes first and the source is a second token.
            index += 1
    return counts, counted


def _safe_child(repo: Path, path: str) -> Path | None:
    posix = PurePosixPath(path)
    windows = PureWindowsPath(path)
    if (not path or "\0" in path or posix.is_absolute() or windows.is_absolute()
            or windows.drive or ".." in posix.parts or not posix.parts
            or any(part.lower() == ".git" for part in posix.parts)):
        return None
    child = repo.joinpath(*posix.parts)
    try:
        resolved = child.resolve()
        if resolved == repo or not resolved.is_relative_to(repo):
            return None
    except (OSError, RuntimeError, ValueError):
        return None
    return child


def _modules(repo: Path, issues: list[dict[str, str]]) -> tuple[str | None, dict[str, str]]:
    file = repo / ".gitmodules"
    if file.is_symlink():
        issues.append(_issue("unsafe_gitmodules", ".gitmodules is a symlink; not read.", "error"))
        return None, {}
    if not file.exists():
        return None, {}
    try:
        if not file.is_file() or file.stat().st_size > _MAX_GITMODULES_BYTES:
            issues.append(_issue("invalid_gitmodules", ".gitmodules is not a bounded regular file.", "error"))
            return None, {}
        contents = file.read_bytes()
    except OSError:
        issues.append(_issue("gitmodules_unreadable", ".gitmodules could not be read.", "error"))
        return None, {}
    digest = hashlib.sha256(contents).hexdigest()
    try:
        # Explicitly disable includes: this command reads no referenced config files.
        raw = _git(repo, "config", "--no-includes", "-z", "--file", str(file),
                   "--get-regexp", r"^submodule\..*\.path$", allow_missing=True)
    except _GitError as exc:
        issues.append(_issue(exc.code, ".gitmodules paths could not be parsed.", "error"))
        return digest, {}
    paths: dict[str, str] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        key, separator, value = record.partition(b"\n")
        if not separator:
            issues.append(_issue("invalid_gitmodules", "A path declaration could not be parsed.", "error"))
            continue
        path = os.fsdecode(value)
        normalized = PurePosixPath(path)
        if path and not normalized.is_absolute() and ".." not in normalized.parts:
            path = normalized.as_posix()
        name = os.fsdecode(key)[len("submodule."):-len(".path")]
        if path in paths:
            issues.append(_issue("duplicate_submodule_path", "Multiple declarations have the same path.", "error"))
        else:
            paths[path] = name
    return digest, paths


def _snapshot(repo: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    # --verify rejects malformed/incomplete revisions, without exposing stderr.
    try:
        head = _git(repo, "rev-parse", "--verify", "HEAD^{commit}").strip().decode("ascii")
    except _GitError as exc:
        if exc.code != "git_command_failed":
            raise
        # Unborn HEAD is valid; a dangling/corrupt existing HEAD is not.
        reference = _git(repo, "symbolic-ref", "-q", "HEAD", allow_missing=True).strip()
        if not reference or _git(repo, "show-ref", "--hash", os.fsdecode(reference),
                                 allow_missing=True):
            raise _GitError("invalid_head")
        head = None
        issues.append(_issue("unborn_head", "Repository has no committed HEAD."))
    counts, counted = _status(repo)
    digest, declared = _modules(repo, issues)
    links_head: dict[str, str] = {}
    if head:
        for record in _git(repo, "ls-tree", "-r", "-z", "HEAD").split(b"\0"):
            if not record:
                continue
            meta, _, path = record.partition(b"\t")
            mode, _, sha = meta.split(b" ")
            if mode == b"160000":
                links_head[os.fsdecode(path)] = sha.decode("ascii")
    links_index: dict[str, str] = {}
    stages: dict[str, dict[str, str]] = {}
    conflicted: set[str] = set()
    for record in _git(repo, "ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        meta, _, path_bytes = record.partition(b"\t")
        mode, sha, stage = meta.split(b" ")
        path = os.fsdecode(path_bytes)
        if stage != b"0":
            conflicted.add(path)
        if mode == b"160000":
            if stage == b"0":
                links_index[path] = sha.decode("ascii")
            else:
                stages.setdefault(path, {})[stage.decode("ascii")] = sha.decode("ascii")
    for path in set(links_head) | set(links_index) | set(stages):
        if links_head.get(path) != links_index.get(path) or path in conflicted:
            if path not in counted["staged"]:
                counts["staged"] += 1
                counted["staged"].add(path)
        if path in conflicted:
            for key in ("unstaged", "conflicted"):
                if path not in counted[key]:
                    counts[key] += 1
                    counted[key].add(path)
    return dict(head=head, dirty=any(counts.values()), status_counts=counts,
                gitmodules_sha256=digest, issues=issues, declared=declared,
                links_head=links_head, links_index=links_index, stages=stages,
                conflicted=conflicted, counted=counted)


def inspect_stack(root: str | Path) -> dict[str, Any]:
    """Inventory a Git root and the union of declared, HEAD and index gitlinks.

    Git operations have a 15-second timeout. Inspection stops at 32 levels and
    4096 components. Missing or unsafe children remain visible, with unknown
    descendant coverage. The fingerprint includes the canonical root path and
    JSON metadata only; changing dirty file bytes alone need not change it.
    """
    try:
        canonical = Path(root).expanduser().resolve(strict=True)
        if not _true_root(canonical):
            raise InventoryError("Stack root must be the root of a non-bare Git working tree.")
        initial = _snapshot(canonical)
    except InventoryError:
        raise
    except (_GitError, OSError, RuntimeError, ValueError, TypeError) as exc:
        raise InventoryError("Stack root could not be inspected as a Git working tree.") from None

    public_fields = ("head", "dirty", "status_counts", "gitmodules_sha256")
    result: dict[str, Any] = {
        "root": str(canonical),
        "parent": {key: initial[key] for key in public_fields},
        "components": [], "issues": list(initial["issues"]),
        "fingerprint_scope": "metadata_only",
    }
    visited = {canonical}

    def discover(repo: Path, parent_path: str, snapshot: dict[str, Any], depth: int) -> None:
        paths = sorted(set(snapshot["declared"]) | set(snapshot["links_head"])
                       | set(snapshot["links_index"]) | set(snapshot["stages"]))
        for local_path in paths:
            if len(result["components"]) >= _MAX_COMPONENTS:
                result["issues"].append(_issue("component_limit", "Component limit reached; inventory is incomplete.", "error"))
                return
            relative = PurePosixPath(local_path)
            path = local_path if parent_path == "." else f"{parent_path}/{local_path}"
            component: dict[str, Any] = dict(
                path=path, parent_path=parent_path, name=snapshot["declared"].get(local_path),
                declared=local_path in snapshot["declared"],
                gitlink_head=snapshot["links_head"].get(local_path),
                gitlink_index=snapshot["links_index"].get(local_path), head=None,
                state="uninitialized", dirty=None, status_counts=None,
                head_matches_gitlink=None, gitmodules_sha256=None, issues=[],
            )
            if relative.is_absolute() or PureWindowsPath(local_path).drive:
                component["declared_path"] = local_path
                token = hashlib.sha256(os.fsencode(local_path)).hexdigest()[:16]
                component["path"] = f"__invalid__/{token}" if parent_path == "." else f"{parent_path}/__invalid__/{token}"
            component_issues = component["issues"]
            result["components"].append(component)
            conflict = local_path in snapshot["conflicted"]
            if snapshot["stages"].get(local_path):
                component["gitlink_index_stages"] = snapshot["stages"][local_path]
            if conflict:
                component["state"] = "conflict"
                component_issues.append(_issue("gitlink_conflict", "Parent index has an unresolved conflict at this path.", "error"))
            if not component["declared"]:
                component_issues.append(_issue("undeclared_gitlink", "Gitlink has no working .gitmodules declaration."))
            elif not component["gitlink_head"] and not component["gitlink_index"] and not conflict:
                component_issues.append(_issue("declared_without_gitlink", "Declaration has no HEAD or index gitlink."))
            if component["gitlink_head"] != component["gitlink_index"] and not conflict:
                component_issues.append(_issue("gitlink_index_differs", "HEAD and index gitlinks differ (addition, removal or change)."))
            child = _safe_child(repo, local_path)
            if child is None:
                component["state"] = "invalid"
                component_issues.append(_issue("unsafe_path", "Submodule path is unsafe; target was not inspected.", "error"))
                component_issues.append(_issue("descendants_unknown", "Descendant inventory is unknown."))
                continue
            try:
                resolved = child.resolve()
                if resolved in visited:
                    component["state"] = "invalid"
                    component_issues.append(_issue("repository_cycle", "Repository was already visited.", "error"))
                    component_issues.append(_issue("descendants_unknown", "Descendant inventory is unknown."))
                    continue
                if child.exists() and not child.is_dir():
                    component["state"] = "invalid"
                    component_issues.append(_issue("invalid_child_repository", "Submodule path is not a directory.", "error"))
                    component_issues.append(_issue("descendants_unknown", "Descendant inventory is unknown."))
                    continue
                if not child.exists() or not (child / ".git").exists():
                    component_issues.append(_issue("uninitialized_submodule", "No child Git working tree is available."))
                    component_issues.append(_issue("descendants_unknown", "Descendant inventory is unknown."))
                    continue
                if not _true_root(resolved):
                    component["state"] = "invalid"
                    component_issues.append(_issue("invalid_child_repository", "Path is not a child Git working-tree root.", "error"))
                    component_issues.append(_issue("descendants_unknown", "Descendant inventory is unknown."))
                    continue
                child_snapshot = _snapshot(resolved)
            except (_GitError, OSError, RuntimeError, ValueError) as exc:
                component["state"] = "invalid"
                code = exc.code if isinstance(exc, _GitError) else "child_unreadable"
                component_issues.append(_issue(code, "Child Git metadata could not be inspected.", "error"))
                component_issues.append(_issue("descendants_unknown", "Descendant inventory is unknown."))
                continue
            visited.add(resolved)
            component.update({key: child_snapshot[key] for key in public_fields})
            component["state"] = "conflict" if conflict else "initialized"
            component_issues.extend(child_snapshot["issues"])
            if component["head"] is not None and component["gitlink_head"] is not None:
                component["head_matches_gitlink"] = component["head"] == component["gitlink_head"]
                if not component["head_matches_gitlink"]:
                    component_issues.append(_issue("head_mismatch", "Child HEAD differs from the parent HEAD gitlink."))
            if depth >= _MAX_DEPTH:
                component_issues.append(_issue("depth_limit", "Recursion limit reached; descendants are unknown.", "error"))
            else:
                discover(resolved, component["path"], child_snapshot, depth + 1)
            component["dirty"] = child_snapshot["dirty"]
            if component["gitlink_index"] and (
                component["dirty"] or component["head"] != component["gitlink_index"]
            ):
                if local_path not in snapshot["counted"]["unstaged"]:
                    snapshot["status_counts"]["unstaged"] += 1
                    snapshot["counted"]["unstaged"].add(local_path)
                    snapshot["dirty"] = True
        snapshot["dirty"] = any(snapshot["status_counts"].values())

    discover(canonical, ".", initial, 1)
    result["parent"]["dirty"] = initial["dirty"]
    result["components"].sort(key=lambda item: (item["path"], item["parent_path"]))
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    result["fingerprint_sha256"] = hashlib.sha256(encoded).hexdigest()
    return result
