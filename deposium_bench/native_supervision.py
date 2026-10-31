"""In-process proof of a live supervisor for an already resident native model.

This scope never starts, signals or discovers a service. A saved session or a
live PID alone does not grant the resident-model memory admission exception.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import math
import os
from pathlib import Path
import time

from .adapters import load_profile
from .worker_transport import decode

_ACTIVE = ContextVar("deposium_native_supervision", default=None)
_MAX_FILE_BYTES = 1024 * 1024
_MAX_SAMPLE_AGE_SECONDS = 10


class NativeSupervisionError(ValueError):
    """The resident service has no matching, currently effective supervisor."""


def _read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_FILE_BYTES:
        raise NativeSupervisionError("native_supervision_binding_invalid")
    data = path.read_bytes()
    if len(data) > _MAX_FILE_BYTES:
        raise NativeSupervisionError("native_supervision_binding_invalid")
    return data


def _identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


class _NativeSupervision:
    def __init__(self, profile_path, *, process, watcher, stop, guard,
                 max_rss_mb, min_free_mb):
        self.profile_path = Path(profile_path).resolve()
        profile, self.profile_sha256 = load_profile(self.profile_path)
        if (profile["adapter"] not in {"systemone_local", "uzu_systemone_local", "llama_cpp_json"}
                or type(max_rss_mb) is not int or max_rss_mb != profile["model"]["max_rss_mb"]
                or type(min_free_mb) is not int or not 2048 <= min_free_mb <= 16384):
            raise NativeSupervisionError("native_supervision_budget_mismatch")
        self.profile_identity = _identity(profile)
        self.session_path = self.profile_path.parent / profile["model"]["session_manifest"]
        self.session_sha256 = profile["model"]["session_sha256"]
        session_data = _read(self.session_path)
        if hashlib.sha256(session_data).hexdigest() != self.session_sha256:
            raise NativeSupervisionError("native_supervision_binding_invalid")
        session = decode(session_data)
        self.process = process
        self.watcher = watcher
        self.stop = stop
        self.guard = guard
        self.max_rss_mb = max_rss_mb
        self.min_free_mb = min_free_mb
        self.owner_pid = os.getpid()
        self.active = True
        if (not isinstance(session, dict) or not isinstance(session.get("supervisor"), dict)
                or type(process.pid) is not int or process.pid <= 1
                or type(session.get("pid")) is not int
                or type(session["supervisor"].get("pid")) is not int
                or session.get("pid") != process.pid
                or session.get("supervisor", {}).get("pid") != self.owner_pid
                or session.get("max_rss_mb") != max_rss_mb):
            raise NativeSupervisionError("native_supervision_process_mismatch")
        self.check(profile, self.profile_path)

    def check(self, profile, profile_path):
        """Fail closed on changed identity, exited guard/service or stale probes."""
        try:
            if not self.active:
                raise NativeSupervisionError("native_supervision_not_live")
            if (os.getpid() != self.owner_pid
                    or Path(profile_path).resolve() != self.profile_path
                    or _identity(profile) != self.profile_identity
                    or hashlib.sha256(_read(self.profile_path)).hexdigest() != self.profile_sha256
                    or hashlib.sha256(_read(self.session_path)).hexdigest() != self.session_sha256):
                raise NativeSupervisionError("native_supervision_binding_changed")
            if (self.process.poll() is not None or not self.watcher.is_alive()
                    or self.stop.is_set() or self.guard.get("stop_reason") is not None):
                raise NativeSupervisionError("native_supervision_not_live")
            pgid = os.getpgid(self.process.pid)
            if pgid != self.process.pid or pgid == os.getpgrp():
                raise NativeSupervisionError("native_supervision_process_mismatch")
            observed = self.guard.get("last_observed_monotonic")
            rss = self.guard.get("rss_peak_mib")
            available = self.guard.get("min_available_mib")
            if any(type(value) not in (int, float) or not math.isfinite(value)
                   for value in (observed, rss, available)):
                raise NativeSupervisionError("native_supervision_observation_missing")
            if (not 0 <= time.monotonic() - observed <= _MAX_SAMPLE_AGE_SECONDS
                    or not 0 <= rss <= self.max_rss_mb or available < self.min_free_mb):
                raise NativeSupervisionError("native_supervision_guard_not_effective")
        except (OSError, KeyError, TypeError, AttributeError):
            raise NativeSupervisionError("native_supervision_not_live") from None

    def provenance(self):
        return {"kind": "live_in_process_native_supervision", "process_group": self.process.pid,
                "supervisor_pid": self.owner_pid, "session_sha256": self.session_sha256,
                "profile_sha256": self.profile_sha256, "rss_guard_mib": self.max_rss_mb,
                "min_available_mib": self.min_free_mb,
                "max_observation_age_seconds": _MAX_SAMPLE_AGE_SECONDS}


@contextmanager
def native_supervision(profile_path, *, process, watcher, stop, guard,
                       max_rss_mb, min_free_mb):
    """Bind one live owned service and watcher to its exact local profile."""
    if _ACTIVE.get() is not None:
        raise NativeSupervisionError("native_supervision_scope_already_active")
    scope = _NativeSupervision(profile_path, process=process, watcher=watcher,
                              stop=stop, guard=guard, max_rss_mb=max_rss_mb,
                              min_free_mb=min_free_mb)
    token = _ACTIVE.set(scope)
    try:
        yield scope
    finally:
        scope.active = False
        _ACTIVE.reset(token)


def require_native_supervision(profile, profile_path):
    """Require the matching active scope, checking effective liveness now."""
    scope = _ACTIVE.get()
    if scope is None:
        raise NativeSupervisionError("native_supervision_required")
    scope.check(profile, profile_path)
    return scope
