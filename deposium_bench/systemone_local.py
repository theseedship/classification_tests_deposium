"""Bounded loopback transport to an explicitly started, fingerprinted gateway.

Construction verifies files only. It never starts a service or downloads a model.
The native pilot supervisor owns service lifetime and memory enforcement.
"""
from __future__ import annotations

import copy
import hashlib
from http.client import HTTPConnection, HTTPException
import json
import math
import os
from pathlib import Path
import re
import socket
import threading
import time
from urllib.parse import urlsplit

from .choice_protocol import CONTEXT_CHOICE_CONTRACT, validate_choice_input
from .worker_transport import decode

MAX_BYTES = 1024 * 1024
FIELDS = {"endpoint", "model_id", "repo_id", "session_manifest", "session_sha256",
          "max_length", "max_rss_mb", "credential_env"}
PATH_FIELDS = {"session_manifest"}
AUTH_ENV = "DEPOSIUM_BENCH_LOCAL_KEY"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _wire(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def native_request(value, model_id):
    """Pure shared HTTP projection; no native tokenization or forward audit."""
    validate_choice_input(value)
    mapping = {"c" + str(i): option["id"] for i, option in enumerate(value["options"])}
    payload = {"model": model_id, "state": value["context"],
        "questions": {"answer": {"type": "choice", "instructions": value["question"],
            "criteria": {"c" + str(i): option["description"]
                         for i, option in enumerate(value["options"])}}}}
    return payload, mapping, _wire(payload)


def _finite(value):
    return type(value) in (float, int) and math.isfinite(value) and 0 <= value <= 1


class NativeChoiceError(ValueError):
    """A native usage refusal, retaining diagnostics without executing anything."""
    def __init__(self, code, diagnostic):
        super().__init__(code)
        self.diagnostic = diagnostic


def native_choice_response(native, model_id, model_path, mapping, max_length, expected_input_tokens=None):
    """Pure response validation shared by live transport and retained audits."""
    if not isinstance(native, dict) or native.get("model") not in {model_id, model_path}:
        raise ValueError("systemone_response_model_mismatch")
    if not isinstance(native.get("answers"), dict) or set(native["answers"]) != {"answer"}:
        raise ValueError("systemone_response_invalid")
    answer = native["answers"]["answer"]
    probabilities = answer.get("probabilities") if isinstance(answer, dict) else None
    if (not isinstance(answer, dict) or answer.get("type") != "choice"
            or not isinstance(probabilities, dict) or set(probabilities) != set(mapping)
            or any(not _finite(p) for p in probabilities.values())
            or abs(sum(probabilities.values()) - 1) > 1e-5 or answer.get("choice") not in mapping
            or probabilities[answer["choice"]] != max(probabilities.values()) or not _finite(answer.get("confidence"))):
        raise ValueError("systemone_response_invalid")
    usage = native.get("usage")
    if (not isinstance(usage, dict) or type(usage.get("input_tokens")) is not int
            or not 0 < usage["input_tokens"] <= max_length
            or type(usage.get("output_tokens")) is not int or usage["output_tokens"] != 0):
        raise NativeChoiceError("systemone_usage_invalid", {})
    diagnostic = {"observed_model": native["model"], "usage": copy.deepcopy(usage)}
    if expected_input_tokens is not None:
        diagnostic.update(prepared_input_tokens=expected_input_tokens,
                          native_preparation_count_match=usage["input_tokens"] == expected_input_tokens)
        if not diagnostic["native_preparation_count_match"]:
            raise NativeChoiceError("systemone_native_preparation_count_mismatch", diagnostic)
    if "truncated" in usage:
        if type(usage["truncated"]) is not bool:
            raise NativeChoiceError("systemone_usage_invalid", diagnostic)
        diagnostic["native_usage_truncated"] = usage["truncated"]
        if usage["truncated"]:
            raise NativeChoiceError("systemone_native_input_truncated", diagnostic)
    return {"choice_id": mapping[answer["choice"]]}, diagnostic


def _state(path):
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def native_overflow(data, max_length):
    """Recognize only the pinned engines' explicit context/batch refusals.

    This engine reports that input refusal as HTTP 500. Other server errors
    remain errors; they are never treated as a supported decision or scored.
    """
    try:
        value = decode(data)
        error = value["error"]
        if (error.get("code") == 400 and error.get("type") == "exceed_context_size_error"
                and type(error.get("n_prompt_tokens")) is int
                and type(error.get("n_ctx")) is int
                and error["n_prompt_tokens"] > max_length and error["n_ctx"] == max_length):
            return value
        match = re.fullmatch(r"input \((\d+) tokens\) is too large to process\. increase the physical batch size \(current batch size: (\d+)\)",
                             error.get("message", ""))
        if (error["code"] == 500 and error["type"] == "server_error" and match
                and int(match[1]) > max_length and int(match[2]) == max_length):
            return value
    except (ValueError, TypeError, KeyError):
        pass
    return None


def validate_model_profile(profile):
    model = profile.get("model")
    if (not isinstance(model, dict) or set(model) != FIELDS
            or profile.get("adapter") != "systemone_local"
            or profile.get("qualification") != "model_isolated"
            or profile.get("capabilities") != [CONTEXT_CHOICE_CONTRACT]
            or not re.fullmatch(r"[0-9a-f]{40}", profile.get("revision") or "")
            or profile.get("recordings") is not None):
        raise ValueError("systemone_profile_invalid")
    if not isinstance(model["endpoint"], str):
        raise ValueError("systemone_loopback_endpoint_required")
    endpoint = urlsplit(model["endpoint"])
    if (endpoint.scheme != "http" or endpoint.hostname != "127.0.0.1"
            or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment
            or endpoint.path != "/v1/systemone" or endpoint.port is None
            or not 1024 <= endpoint.port <= 65535 or model["credential_env"] != AUTH_ENV):
        raise ValueError("systemone_loopback_endpoint_required")
    for key in ("model_id", "repo_id", "session_manifest"):
        if not isinstance(model[key], str) or not model[key].strip() or "\x00" in model[key]:
            raise ValueError("systemone_identity_invalid")
    if not isinstance(model["session_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", model["session_sha256"]):
        raise ValueError("systemone_session_hash_invalid")
    for key, low, high in (("max_length", 128, 32768), ("max_rss_mb", 256, 49152)):
        if type(model[key]) is not int or not low <= model[key] <= high:
            raise ValueError("systemone_budget_invalid")
    timeout = profile.get("timeout_seconds")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise ValueError("systemone_timeout_invalid")


def http_request(port, method, path, body, key, timeout):
    """Direct IPv4 loopback: no DNS, proxy, redirect or automatic retry."""
    connection = HTTPConnection("127.0.0.1", port=port, timeout=timeout)
    sockets = []
    expired = threading.Event()
    def expire():
        expired.set()
        for sock in sockets:
            try: sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
        connection.close()
    timer = threading.Timer(timeout, expire)
    timer.daemon = True
    timer.start()
    response = None
    started = time.monotonic()
    try:
        connection.connect()
        sockets.append(connection.sock)
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if key:
            headers["Authorization"] = "Bearer " + key
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        length = response.getheader("content-length")
        if length is not None and (not re.fullmatch(r"[0-9]+", length) or int(length) > MAX_BYTES):
            raise ValueError("systemone_response_too_large")
        chunks, size = [], 0
        while True:
            piece = response.read1(min(65536, MAX_BYTES + 1 - size))
            if not piece:
                break
            chunks.append(piece)
            size += len(piece)
            if size > MAX_BYTES:
                raise ValueError("systemone_response_too_large")
        if expired.is_set() or time.monotonic() - started >= timeout:
            raise TimeoutError("systemone_http_timeout")
        return response.status, b"".join(chunks)
    except (OSError, HTTPException):
        if expired.is_set():
            raise TimeoutError("systemone_http_timeout") from None
        raise
    finally:
        timer.cancel()
        timer.join()
        if response is not None:
            response.close()
        connection.close()


class LocalSystemOneAdapter:
    capabilities = (CONTEXT_CHOICE_CONTRACT,)
    profile_validator = staticmethod(validate_model_profile)
    adapter_name = "systemone_local"
    requires_auth = True

    def __init__(self, profile, profile_path):
        self.profile_validator(profile)
        self._profile = copy.deepcopy(profile)
        self._model = self._profile["model"]
        self._key = os.environ.get(AUTH_ENV, "") if self.requires_auth else ""
        self._port = urlsplit(self._model["endpoint"]).port
        self._lock = threading.Lock()
        self._states = {}
        self._prepared_tokens = None
        self._failure = None
        self._closed = False
        self.provenance = {"adapter": self.adapter_name, "qualification": "model_isolated",
                           "capabilities": list(self.capabilities), "available": False,
                           "transport": "loopback_http_no_proxy_no_redirect_no_retry",
                           "model_execution": "not_observed", "input_protocol": "context_choice"}
        try:
            if self.requires_auth and (not self._key or not self._key.isascii()
                    or any(ord(c) <= 32 or ord(c) >= 127 for c in self._key)):
                raise ValueError("systemone_local_key_missing_or_invalid")
            self._bind_session(profile_path)
        except FileNotFoundError:
            self._fail("missing", "systemone_asset_missing")
        except (OSError, ValueError, KeyError, TypeError):
            self._fail("error", "systemone_identity_invalid")

    def _bind_session(self, profile_path):
        profile = self._profile
        path = Path(profile_path).absolute().parent / self._model["session_manifest"]
        self._remember(path, self._model["session_sha256"])
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("systemone_session_too_large")
        self._session = decode(path.read_bytes())
        session = self._session
        if (session["schema_version"] != "deposium.local-model-session/v1"
                or session["model"]["revision"] != profile["revision"]
                or session["model"]["repo_id"] != self._model["repo_id"]
                or session["model"]["alias"] != self._model["model_id"]
                or session["endpoint"] != self._model["endpoint"]
                or session["settings"] != {"context": self._model["max_length"],
                    "parallel": 1, "concurrency": 1, "questions_per_call": 1,
                    "truncation": "reject_in_pinned_native_engine"}
                or session["max_rss_mb"] != self._model["max_rss_mb"]):
            raise ValueError("systemone_session_identity_mismatch")
        for record, name in ((session["model"], "path"), (session["runtime"], "binary"),
                             (session["gateway"], "binary"), (session["harness"], "path"),
                             (session["runtime_pin"], "path")):
            self._remember(Path(record[name]), record["sha256"])
        if "native_preparation" in session:
            binding = session["native_preparation"]
            preparation_path = Path(binding["path"])
            self._remember(preparation_path, binding["sha256"])
            if preparation_path.stat().st_size > MAX_BYTES:
                raise ValueError("systemone_preparation_invalid")
            preparation = decode(preparation_path.read_bytes())
            entries = preparation.get("request_tokens")
            if (preparation.get("schema_version") != "deposium.native-preparation-map/v1"
                    or preparation.get("model_id") != self._model["model_id"]
                    or preparation.get("source_revision") != session["runtime"]["revision"]
                    or preparation.get("max_tokens") != self._model["max_length"]
                    or not isinstance(entries, dict) or not entries
                    or any(not re.fullmatch(r"[0-9a-f]{64}", key)
                           or type(count) is not int or not 0 < count <= self._model["max_length"]
                           for key, count in entries.items())):
                raise ValueError("systemone_preparation_invalid")
            self._prepared_tokens = entries
        self._remember(Path(__file__), digest(__file__))
        self._remember(Path(__file__).with_name("choice_protocol.py"),
                       digest(Path(__file__).with_name("choice_protocol.py")))
        identity = {key: session[key] for key in
                    ("model", "runtime", "gateway", "harness", "runtime_pin", "settings", "max_rss_mb")}
        identity["adapter_sha256"] = digest(__file__)
        identity["choice_protocol_sha256"] = digest(Path(__file__).with_name("choice_protocol.py"))
        if self._prepared_tokens is not None:
            identity["native_preparation"] = session["native_preparation"]
        self.provenance.update(available=True, identity=identity,
            identity_sha256=hashlib.sha256(_wire(identity)).hexdigest(), session_sha256=self._model["session_sha256"])

    def _overflow_response(self, data):
        return native_overflow(data, self._model["max_length"])

    def _remember(self, path, expected):
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError("systemone_asset_missing")
        before = _state(path)
        if digest(path) != expected or before != _state(path):
            raise ValueError("systemone_asset_changed")
        self._states[path] = before

    def _guard(self):
        if any(path.is_symlink() or _state(path) != state for path, state in self._states.items()):
            raise ValueError("systemone_asset_changed")

    def _fail(self, status, error, raw=None):
        if raw is not None and self._key and self._key in json.dumps(raw):
            raw = None
        self._failure = {"status": status, "output": None, "raw_output": raw, "error": error}
        self.provenance.update(available=False, availability_error=error)
        return copy.deepcopy(self._failure)

    def close(self):
        self._closed = True

    def predict(self, request):
        if not isinstance(request, dict) or request.get("contract_id") != CONTEXT_CHOICE_CONTRACT:
            return {"status": "unsupported", "output": None, "raw_output": None, "error": "unsupported_contract"}
        with self._lock:
            if self._failure:
                result = copy.deepcopy(self._failure)
                result["raw_output"] = {"http_attempted": False, "cached_failure": True,
                                        "native_usage_truncated": None}
                return result
            if self._closed:
                return self._fail("error", "systemone_adapter_closed")
            raw = {"http_attempted": False, "cached_failure": False, "native_result": None,
                   "requested_model": self._model["model_id"], "forward_executed": None,
                   "native_usage_truncated": None}
            try:
                value = request.get("input")
                payload, mapping, body = native_request(value, self._model["model_id"])
                if self._key and self._key in body.decode():
                    raise ValueError("systemone_input_secret_rejected")
                if len(body) > 131072:
                    return {"status": "unsupported", "output": None, "raw_output": raw,
                            "error": "systemone_request_body_too_large"}
                self._guard()
                body_sha256 = hashlib.sha256(body).hexdigest()
                if self._prepared_tokens is not None and body_sha256 not in self._prepared_tokens:
                    return self._fail("error", "systemone_native_request_not_prepared", raw)
                raw.update(http_attempted=True, native_request=payload, option_mapping=mapping,
                           request_body_sha256=body_sha256)
                started = time.perf_counter()
                status, data = http_request(self._port, "POST", "/v1/systemone", body, self._key,
                                            self._profile["timeout_seconds"])
                raw.update(http_status=status, http_ms=(time.perf_counter() - started) * 1000,
                           response_sha256=hashlib.sha256(data).hexdigest())
                self._guard()
                if status != 200:
                    overflow = self._overflow_response(data) if status in {400, 500} else None
                    if overflow is not None:
                        raw.update(native_error=overflow, forward_executed=False)
                        return {"status": "unsupported", "output": None, "raw_output": raw,
                                "error": "systemone_native_context_overflow"}
                    return self._fail("error", "systemone_http_status_" + str(status), raw)
                native = decode(data)
                if self._key and self._key in json.dumps(native):
                    raise ValueError("systemone_response_secret_rejected")
                raw["native_result"] = native
                try:
                    output, diagnostic = native_choice_response(native, self._model["model_id"], self._session["model"]["path"],
                        mapping, self._model["max_length"], self._prepared_tokens[body_sha256] if self._prepared_tokens is not None else None)
                except NativeChoiceError as exc:
                    raw.update(exc.diagnostic)
                    return self._fail("error", str(exc), raw)
                raw.update(diagnostic)
                self.provenance["model_response"] = "observed"
                return {"status": "ok", "output": output,
                        "raw_output": raw, "error": None}
            except TimeoutError:
                return self._fail("timeout", "systemone_http_timeout", raw)
            except (OSError, HTTPException):
                return self._fail("error", "systemone_transport_or_asset_error", raw)
            except (ValueError, KeyError, TypeError, AttributeError):
                return self._fail("error", "systemone_input_or_response_invalid", raw)
