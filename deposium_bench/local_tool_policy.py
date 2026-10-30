"""Generated JSON proposals through one explicitly supervised local model.

Imports do no model, file, network or service work. The model proposes actions;
the existing argument/episode runtime owns tool guards, execution and scoring.
Schema grammar is a syntax aid, never evidence of a correct proposal.
"""
from __future__ import annotations

from copy import deepcopy
import base64
import hashlib
from http.client import HTTPException
import math
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit

from .cases import CaseError, typed_equal
from .synthetic_tools import canonical
from .systemone_local import AUTH_ENV, digest, http_request

ADAPTER = "llama_cpp_json"
CONTRACTS = ("bench.tool-discovery", "bench.tool-arguments", "bench.tool-episode")
TRACE_VERSION = "deposium.local-tool-model-trace/v1"
CALL_VERSION = "deposium.local-json-call/v1"
SESSION_VERSION = "deposium.local-json-model-session/v1"
PROMPT_VERSION = "deposium.local-tool-policy-prompt/v2"
MODEL_FIELDS = {"endpoint", "model_id", "repo_id", "session_manifest", "session_sha256",
                "max_length", "max_rss_mb", "credential_env", "max_output_tokens", "seed", "prompt_version"}
SETTINGS_FIELDS = {"model_id", "max_length", "max_output_tokens", "seed", "prompt_version"}
STATUSES = {"ok", "unsupported", "missing", "error", "timeout", "abstain"}
PIN = "efe3626b119ff81033e309c3ba07a770bef2c546"
# Every prompt version ever used by an archived session stays here verbatim so a
# pure rescore can rebuild and compare the exact request bytes. v1 described the
# contracts incompletely: nothing told the candidate that a discovery shortlist
# must contain the selected tools, or that an episode finishes once an actual
# observation justifies an outcome. v2 states those public contract rules and
# names no case, catalogue entry, table or expected answer.
PROMPTS = {
    "deposium.local-tool-policy-prompt/v1": (
        "Return exactly one JSON value matching the response schema, with no commentary or markdown. "
        "Use only the supplied request, tool interfaces, permissions and actual observations. "
        "Never invent an execution receipt. Propose an action or decision; the runtime independently "
        "enforces permissions, bindings and budgets. A success finish requires an actual successful "
        "sum observation. A controlled lookup error can be retried within the remaining budget. "
        "For an incomplete artifact request clarification; for empty complete data stop without "
        "claiming a numeric result; for missing required input request clarification."),
    "deposium.local-tool-policy-prompt/v2": (
        "Return exactly one JSON value matching the response schema, with no commentary or markdown. "
        "Use only the supplied request, tool interfaces, permissions and actual observations. "
        "Never invent an execution receipt. Propose an action or decision; the runtime independently "
        "enforces permissions, bindings and budgets. "
        "Discovery: the shortlist lists every tool identifier you select, holds at most shortlist_limit "
        "entries and names only tool identifiers from the catalogue; select only eligible and available "
        "tools and the smallest set that completes the request. If a required input is missing, answer "
        "clarify with no tools. If no eligible available tool can perform the task, answer no_suitable "
        "with no tools and the matching reason. "
        "Arguments: copy the observed artifact identifier and scope exactly. "
        "Episode: after each actual observation choose one next action; when an observation already "
        "justifies an outcome, finish instead of calling another tool. A success finish requires an "
        "actual successful sum observation and repeats its value and unit. A controlled lookup error "
        "can be retried within the remaining budget. For an incomplete artifact request clarification; "
        "for empty complete data stop without claiming a numeric result; if a required tool is no longer "
        "available stop; for missing required input request clarification without guessing an identifier."),
}
SYSTEM = PROMPTS[PROMPT_VERSION]


def _sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _object(value, fields, message):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise CaseError(message)


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def credential_in_response(data, key):
    """Recognize literal and JSON-escaped credentials before archiving bytes."""
    text = data.decode("utf-8", errors="replace")
    escapes = re.compile(r'\\(?:u([0-9a-fA-F]{4})|(["\\/bfnrt]))')
    replacements = {'"': '"', '\\': '\\', '/': '/', 'b': '\b', 'f': '\f',
                    'n': '\n', 'r': '\r', 't': '\t'}
    for _ in range(32):
        if key in text:
            return True
        decoded = escapes.sub(lambda match: chr(int(match[1], 16)) if match[1]
                              else replacements[match[2]], text)
        if decoded == text:
            return False
        text = decoded
    # An excessively nested escape representation is unqualified, not safe to
    # retain merely because the finite inspection bound was exhausted.
    return True


def validate_settings(settings):
    _object(settings, SETTINGS_FIELDS, "local_json_settings_invalid")
    if (not isinstance(settings["model_id"], str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", settings["model_id"]) is None
            or settings["max_length"] != 4096
            or not _integer(settings["max_output_tokens"], 32, 512)
            or not _integer(settings["seed"], 0, 2**31 - 1)
            or settings["prompt_version"] not in PROMPTS):
        raise CaseError("local_json_settings_invalid")


def settings_for(model):
    value = {key: model[key] for key in SETTINGS_FIELDS}
    validate_settings(value)
    return value


def validate_model_profile(profile):
    model = profile.get("model")
    if (profile.get("adapter") != ADAPTER or profile.get("qualification") != "model_isolated"
            or profile.get("recordings") is not None
            or not isinstance(profile.get("revision"), str)
            or re.fullmatch(r"[0-9a-f]{40}", profile["revision"]) is None
            or not isinstance(profile.get("capabilities"), list) or not profile["capabilities"]
            or any(c not in CONTRACTS for c in profile["capabilities"])
            or len(set(profile["capabilities"])) != len(profile["capabilities"])
            or not isinstance(model, dict) or set(model) != MODEL_FIELDS):
        raise CaseError("local_json_profile_invalid")
    settings_for(model)
    try:
        endpoint = urlsplit(model["endpoint"])
        valid = (endpoint.scheme == "http" and endpoint.hostname == "127.0.0.1"
                 and endpoint.path == "/v1/chat/completions" and endpoint.port is not None
                 and 1024 <= endpoint.port <= 65535 and not endpoint.username and not endpoint.password
                 and not endpoint.query and not endpoint.fragment)
    except (TypeError, ValueError):
        valid = False
    if (not valid or model["credential_env"] != AUTH_ENV
            or not _integer(model["max_rss_mb"], 256, 8192)
            or not isinstance(model["repo_id"], str)
            or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", model["repo_id"]) is None
            or not isinstance(model["session_manifest"], str) or not model["session_manifest"]
            or "\x00" in model["session_manifest"]
            or not isinstance(model["session_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", model["session_sha256"]) is None
            or type(profile.get("timeout_seconds")) not in (int, float)
            or not math.isfinite(profile["timeout_seconds"]) or not 0 < profile["timeout_seconds"] <= 30):
        raise CaseError("local_json_profile_invalid")


def output_schema(contract):
    """Only the public output syntax; no gold sets or state-specific answers."""
    text = {"type": "string", "minLength": 1, "maxLength": 128}
    ids = {"type": "array", "items": text, "maxItems": 8}
    def obj(properties):
        return {"type": "object", "properties": properties, "required": list(properties),
                "additionalProperties": False}
    if contract == "bench.tool-discovery":
        return obj({"schema_version": {"type": "string", "const": "deposium.tool-discovery-output/v1"},
                    "shortlist": ids,
                    "selection": obj({"decision": {"type": "string", "enum": ["select", "clarify", "no_suitable"]},
                                      "tool_ids": ids, "reason": {"type": "string", "enum": [
                                          "ready", "missing_information", "no_capability", "unavailable"]}})})
    arguments = obj({name: deepcopy(text) for name in ("artifact_id", "column", "unit", "scope_id")})
    if contract == "bench.tool-arguments":
        return obj({"tool_id": text, "arguments": arguments})
    if contract == "bench.tool-episode":
        return {"oneOf": [obj({"action": {"type": "string", "const": "call"}, "tool_id": text,
                               "arguments": {"oneOf": [arguments, obj({"dataset_id": text, "scope_id": text})]}}),
                          obj({"action": {"type": "string", "const": "finish"},
                               "decision": {"type": "string", "enum": ["success", "stop", "clarify"]},
                               "reason": {"type": "string", "enum": ["complete", "persistent_error", "no_data",
                                                                       "unavailable", "partial_data", "missing_information"]},
                               "value": {"type": ["integer", "null"]}, "unit": {"type": ["string", "null"], "maxLength": 128}})]}
    raise CaseError("local_json_unsupported_contract")


def request_body(contract, projection, settings):
    validate_settings(settings)
    # The caller must pass its task-specific projection, never the case envelope.
    return {"model": settings["model_id"], "messages": [
                {"role": "system", "content": PROMPTS[settings["prompt_version"]]},
                {"role": "user", "content": canonical(projection).decode("ascii")}],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "proposal", "strict": True, "schema": output_schema(contract)}},
            "temperature": 0, "top_p": 1, "top_k": 0, "repeat_penalty": 1,
            "seed": settings["seed"], "max_tokens": settings["max_output_tokens"],
            "stream": False, "n": 1, "cache_prompt": False}


def decode_response(data, settings):
    """Return parsed JSON without repair; preserve schema-wrong JSON for scoring."""
    from .adapters import _json
    try:
        native = _json(data)
    except (ValueError, RecursionError):
        raise CaseError("local_json_native_response_invalid") from None
    if (not isinstance(native, dict) or native.get("model") != settings["model_id"]
            or not isinstance(native.get("choices"), list) or len(native["choices"]) != 1):
        raise CaseError("local_json_native_response_invalid")
    choice = native["choices"][0]
    if (not isinstance(choice, dict) or type(choice.get("index")) is not int or choice["index"] != 0
            or choice.get("finish_reason") != "stop" or not isinstance(choice.get("message"), dict)
            or choice["message"].get("role") != "assistant"
            or choice["message"].get("tool_calls") or choice["message"].get("refusal")
            or not isinstance(choice["message"].get("content"), str)):
        raise CaseError("local_json_generation_incomplete_or_invalid")
    content = choice["message"]["content"]
    if not content.strip() or len(content.encode("utf-8")) > 8192:
        raise CaseError("local_json_generation_empty_or_oversized")
    usage = native.get("usage")
    if (not isinstance(usage, dict)
            or not _integer(usage.get("prompt_tokens"), 1, settings["max_length"])
            or not _integer(usage.get("completion_tokens"), 1, settings["max_output_tokens"])
            or usage.get("total_tokens") != usage["prompt_tokens"] + usage["completion_tokens"]
            or usage["total_tokens"] > settings["max_length"]):
        raise CaseError("local_json_usage_missing_or_overflow")
    for container in (native, usage):
        if "truncated" in container and (type(container["truncated"]) is not bool or container["truncated"]):
            raise CaseError("local_json_explicit_truncation_or_invalid_flag")
    try:
        return _json(content.encode("utf-8"))
    except (ValueError, RecursionError):
        raise CaseError("local_json_generation_json_invalid") from None


def http_failure(status, data, settings):
    """Only the pinned engine's explicit context refusal is unsupported."""
    from .adapters import _json
    try:
        error = _json(data)["error"]
        if (status in {400, 413, 422} and error.get("type") == "exceed_context_size_error"
                and type(error.get("n_prompt_tokens")) is int
                and error["n_prompt_tokens"] >= settings["max_length"]
                and error.get("n_ctx") == settings["max_length"]):
            return "unsupported", "local_json_context_overflow"
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        pass
    return "error", "local_json_http_status"


def validate_call(call, contract, projection, settings):
    _object(call, {"schema_version", "projection", "projection_sha256", "request", "request_sha256",
                   "http_attempted", "http_status", "response_base64", "response_sha256", "guard_error",
                   "response_redacted", "status", "output", "error", "duration_ms"},
            "local_json_retained_call_invalid")
    expected = request_body(contract, projection, settings)
    if (call["schema_version"] != CALL_VERSION or not typed_equal(call["projection"], projection)
            or call["projection_sha256"] != _sha(projection) or not typed_equal(call["request"], expected)
            or call["request_sha256"] != _sha(expected) or call["status"] not in STATUSES
            or type(call["duration_ms"]) not in (int, float) or not math.isfinite(call["duration_ms"])
            or call["duration_ms"] < 0 or type(call["http_attempted"]) is not bool
            or type(call["response_redacted"]) is not bool
            or call["guard_error"] not in (None, "local_json_supervision_lost")):
        raise CaseError("local_json_call_projection_or_status_mismatch")
    encoded = call["response_base64"]
    if call["guard_error"] is not None and (call["status"] != "error" or call["output"] is not None
                                           or call["error"] != "local_json_supervision_lost"):
        raise CaseError("local_json_guard_failure_mismatch")
    if call["response_redacted"]:
        if (encoded is not None or not call["http_attempted"] or not _integer(call["http_status"], 100, 599)
                or not isinstance(call["response_sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", call["response_sha256"]) is None
                or call["status"] != "error" or call["output"] is not None
                or call["error"] != (call["guard_error"] or "local_json_response_credential_redacted")):
            raise CaseError("local_json_redacted_response_mismatch")
        return
    if encoded is None:
        if (call["response_sha256"] is not None or call["http_status"] is not None
                or call["output"] is not None or call["status"] not in {"error", "timeout"}
                or call["error"] not in {"local_json_http_timeout", "local_json_transport_error", "local_json_supervision_lost"}
                or not call["http_attempted"] and call["guard_error"] is None
                and not (call["status"] == "timeout" and contract == "bench.tool-episode"
                         and projection["remaining_budget"]["elapsed_ms"] == 0)):
            raise CaseError("local_json_absent_response_mismatch")
        return
    try:
        if not isinstance(encoded, str) or len(encoded) > 1400000:
            raise ValueError()
        data = base64.b64decode(encoded, validate=True)
    except ValueError:
        raise CaseError("local_json_retained_response_encoding_invalid") from None
    if (len(data) > 1024 * 1024 or hashlib.sha256(data).hexdigest() != call["response_sha256"]
            or not _integer(call["http_status"], 100, 599) or not call["http_attempted"]):
        raise CaseError("local_json_retained_response_mismatch")
    if call["guard_error"] is not None:
        return
    if call["http_status"] != 200:
        status, error = http_failure(call["http_status"], data, settings)
        if call["status"] != status or call["output"] is not None or call["error"] != error:
            raise CaseError("local_json_http_failure_mismatch")
        return
    try:
        parsed = decode_response(data, settings)
    except ValueError:
        if call["status"] != "error" or call["output"] is not None or call["error"] != "local_json_response_invalid":
            raise CaseError("local_json_parse_failure_mismatch")
    else:
        if call["status"] != "ok" or call["error"] is not None or not typed_equal(call["output"], parsed):
            raise CaseError("local_json_actual_generation_mismatch")


def validate_trace(case, result, settings=None):
    """Pure verification of each model generation and its proposal binding."""
    from . import tool_arguments as arguments, tool_episodes as episodes
    raw = result.get("raw_output")
    _object(raw, {"schema_version", "settings", "calls", "argument_diagnostic", "episode"},
            "local_json_trace_required")
    if raw["schema_version"] != TRACE_VERSION:
        raise CaseError("local_json_trace_version_invalid")
    validate_settings(raw["settings"])
    if settings is not None and not typed_equal(raw["settings"], settings):
        raise CaseError("local_json_trace_profile_settings_mismatch")
    calls = raw["calls"]
    if not isinstance(calls, list) or len(calls) > 5:
        raise CaseError("local_json_call_count_invalid")
    output, status, contract = result.get("output"), result.get("status"), case["contract_id"]
    if not calls:
        if contract == episodes.CONTRACT and status == "ok" and output is not None:
            episodes.validate_receipt(case["input"], output)
            if (output["steps"] or output["termination"] != "time_limit"
                    or output["checks"]["task_success"] or raw["episode"] is not None
                    or raw["argument_diagnostic"] is not None or result.get("error") is not None):
                raise CaseError("local_json_unobserved_episode_mismatch")
            if "duration_ms" in result and output["elapsed_ms"] > result["duration_ms"] + 0.001:
                raise CaseError("local_json_episode_duration_exceeds_case_interval")
            return
        if status not in {"missing", "error"} or output is not None or raw["episode"] is not None or raw["argument_diagnostic"] is not None:
            raise CaseError("local_json_unobserved_call_mismatch")
        return
    if contract == "bench.tool-discovery":
        if len(calls) != 1 or raw["argument_diagnostic"] is not None or raw["episode"] is not None:
            raise CaseError("local_json_discovery_trace_invalid")
        projections = [case["input"]]
        expected_output = calls[0]["output"] if status == "ok" else None
    elif contract == arguments.CONTRACT:
        if len(calls) != 1 or raw["episode"] is not None:
            raise CaseError("local_json_arguments_trace_invalid")
        if status == "ok":
            arguments.validate_receipt(case["input"], output)
            if raw["argument_diagnostic"] is not None or not typed_equal(output["proposal"], calls[0]["output"]):
                raise CaseError("local_json_argument_proposal_mismatch")
            projections, expected_output = [output["candidate_input"]], output
        else:
            arguments.validate_diagnostic(case["input"], raw["argument_diagnostic"])
            projections, expected_output = [raw["argument_diagnostic"]["candidate_input"]], None
    elif contract == episodes.CONTRACT:
        episode = output if status == "ok" else raw["episode"]
        episodes.validate_receipt(case["input"], episode)
        if "duration_ms" in result and episode["elapsed_ms"] > result["duration_ms"] + 0.001:
            raise CaseError("local_json_episode_duration_exceeds_case_interval")
        if (len(calls) != len(episode["steps"]) or raw["argument_diagnostic"] is not None
                or status == "ok" and raw["episode"] is not None):
            raise CaseError("local_json_episode_trace_invalid")
        projections, expected_output = [], output if status == "ok" else None
        for step, call in zip(episode["steps"], calls):
            if (step["policy_status"] != call["status"] or not typed_equal(step["proposal"], call["output"])):
                raise CaseError("local_json_episode_proposal_mismatch")
            if (type(call.get("duration_ms")) not in (int, float)
                    or call["duration_ms"] > step["elapsed_after_policy_ms"] - step["elapsed_before_ms"] + 0.001):
                raise CaseError("local_json_model_duration_exceeds_policy_interval")
            projections.append(step["candidate_input"])
    else:
        raise CaseError("local_json_unsupported_contract")
    for call, projection in zip(calls, projections):
        validate_call(call, contract, projection, raw["settings"])
    if (status != calls[-1]["status"] or result.get("error") != calls[-1]["error"]
            or not typed_equal(output, expected_output)):
        raise CaseError("local_json_final_status_or_output_mismatch")
    if "duration_ms" in result and sum(call["duration_ms"] for call in calls) > result["duration_ms"] + 0.001:
        raise CaseError("local_json_model_duration_exceeds_case_interval")


class _ModelPolicy:
    def __init__(self, adapter, contract):
        self.adapter, self.contract, self.calls = adapter, contract, []

    def predict(self, projection):
        from .adapters import _envelope
        timeout = self.adapter.profile["timeout_seconds"]
        if self.contract == "bench.tool-episode":
            timeout = min(timeout, projection["remaining_budget"]["elapsed_ms"] / 1000)
        body = request_body(self.contract, projection, self.adapter.settings)
        call = {"schema_version": CALL_VERSION, "projection": deepcopy(projection), "projection_sha256": _sha(projection),
                "request": body, "request_sha256": _sha(body), "http_attempted": False, "http_status": None, "response_base64": None,
                "guard_error": None,
                "response_redacted": False,
                "response_sha256": None, "status": "error", "output": None, "error": "local_json_transport_error",
                "duration_ms": 0.0}
        started = time.monotonic()
        try:
            try:
                self.adapter.guard()
            except (OSError, ValueError):
                call["guard_error"] = "local_json_supervision_lost"
                raise
            if timeout <= 0:
                raise TimeoutError()
            call["http_attempted"] = True
            status, data = http_request(self.adapter.port, "POST", "/v1/chat/completions", canonical(body), self.adapter.key, timeout)
            # Base64 also preserves a malformed/non-UTF-8 native response.
            call.update(http_status=status, response_sha256=hashlib.sha256(data).hexdigest())
            if credential_in_response(data, self.adapter.key):
                call.update(response_redacted=True, error="local_json_response_credential_redacted")
            else:
                call["response_base64"] = base64.b64encode(data).decode("ascii")
            if call["response_redacted"]:
                pass  # Native bytes containing the credential are never retained.
            elif status != 200:
                call["status"], call["error"] = http_failure(status, data, self.adapter.settings)
            else:
                try:
                    call["output"] = decode_response(data, self.adapter.settings)
                except ValueError:
                    call["error"] = "local_json_response_invalid"
                else:
                    call.update(status="ok", error=None)
            try:
                self.adapter.guard()
            except (OSError, ValueError):
                call["guard_error"] = "local_json_supervision_lost"
                raise
        except TimeoutError:
            call.update(status="timeout", output=None, error="local_json_http_timeout")
        except (OSError, ValueError, HTTPException):
            call.update(status="error", output=None, error=call["guard_error"] or "local_json_transport_error")
        call["duration_ms"] = (time.monotonic() - started) * 1000
        self.calls.append(call)
        return _envelope(call["status"], output=deepcopy(call["output"]), error=call["error"])


class LocalToolPolicyAdapter:
    """No service is discovered/started; a live owned supervisor is required."""
    def __init__(self, profile, profile_path):
        validate_model_profile(profile)
        self.profile, self.path = deepcopy(profile), Path(profile_path).absolute()
        self.settings = settings_for(profile["model"])
        self.capabilities = list(profile["capabilities"])
        self.port = urlsplit(profile["model"]["endpoint"]).port
        self.key = os.environ.get(AUTH_ENV, "")
        self.states, self.lock, self.closed, self.failure = {}, threading.Lock(), False, None
        self.provenance = {"adapter": ADAPTER, "qualification": "model_isolated", "capabilities": self.capabilities,
                           "available": False, "transport": "loopback_http_no_proxy_no_redirect_no_retry",
                           "input_protocol": "generated_tool_proposals_v1", "model_execution": "not_observed"}
        try:
            from .native_supervision import require_native_supervision
            scope = require_native_supervision(self.profile, self.path)
            if scope.min_free_mb < 8192:
                raise CaseError("local_json_host_reserve_too_small")
            if not self.key or not self.key.isascii() or any(ord(c) <= 32 or ord(c) >= 127 for c in self.key):
                raise CaseError("local_json_key_invalid")
            model = profile["model"]
            session_path = self.path.parent / model["session_manifest"]
            self.remember(session_path, model["session_sha256"], maximum=1024 * 1024)
            from .adapters import _json
            self.session = _json(session_path.read_bytes())
            session = self.session
            _object(session, {"schema_version", "endpoint", "model", "runtime", "harness", "runtime_pin",
                              "template", "settings", "max_rss_mb", "pid", "supervisor"}, "local_json_session_fields_invalid")
            _object(session["model"], {"repo_id", "revision", "path", "sha256", "alias", "size", "quantization"},
                    "local_json_model_identity_invalid")
            _object(session["runtime"], {"repository", "revision", "binary", "sha256", "backend_requested"},
                    "local_json_runtime_identity_invalid")
            for field in ("harness", "runtime_pin", "template"):
                _object(session[field], {"path", "sha256"}, "local_json_source_binding_invalid")
            _object(session["supervisor"], {"pid", "path", "sha256"}, "local_json_supervisor_binding_invalid")
            if (session.get("schema_version") != SESSION_VERSION or session.get("endpoint") != model["endpoint"]
                    or session["model"]["repo_id"] != model["repo_id"] or session["model"]["revision"] != profile["revision"]
                    or session["model"]["alias"] != model["model_id"]
                    or type(session["max_rss_mb"]) is not int or session["max_rss_mb"] != model["max_rss_mb"]
                    or not typed_equal(session["settings"], {**self.settings, "parallel": 1, "concurrency": 1,
                                                           "truncation": "reject_in_pinned_native_engine"})
                    or session["runtime"]["repository"] != "https://github.com/ggml-org/llama.cpp.git"
                    or session["runtime"]["revision"] != PIN or session["runtime"]["backend_requested"] != "metal"):
                raise CaseError("local_json_session_identity_invalid")
            if (not _integer(session["model"]["size"], 1, model["max_rss_mb"] * 1024 * 1024)
                    or not isinstance(session["model"]["quantization"], str)
                    or re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", session["model"]["quantization"]) is None
                    or Path(session["model"]["path"]).stat().st_size != session["model"]["size"]
                    or session["supervisor"]["path"] != session["harness"]["path"]
                    or session["supervisor"]["sha256"] != session["harness"]["sha256"]):
                raise CaseError("local_json_model_or_supervisor_identity_invalid")
            for field, path_field in (("model", "path"), ("runtime", "binary"), ("harness", "path"),
                                      ("runtime_pin", "path"), ("template", "path")):
                self.remember(Path(session[field][path_field]), session[field]["sha256"])
            sources = {name: digest(Path(__file__).with_name(name)) for name in (
                "adapters.py", "local_tool_policy.py", "native_supervision.py", "systemone_local.py", "cases.py",
                "tool_arguments.py", "tool_episodes.py", "synthetic_tools.py", "tool_discovery.py")}
            for name, checksum in sources.items():
                self.remember(Path(__file__).with_name(name), checksum)
            identity = {key: session[key] for key in ("model", "runtime", "harness", "runtime_pin", "template", "settings", "max_rss_mb")}
            identity["adapter_sources"] = sources
            self.provenance.update(available=True, identity=identity, identity_sha256=_sha(identity),
                                   adapter_sha256=_sha(sources), session_sha256=model["session_sha256"])
        except FileNotFoundError:
            self.failure = ("missing", "local_json_asset_missing")
        except (OSError, ValueError, KeyError, TypeError):
            self.failure = ("error", "local_json_session_or_supervision_invalid")
        if self.failure:
            self.provenance["availability_error"] = self.failure[1]

    def remember(self, path, checksum, maximum=None):
        if (path.is_symlink() or not path.is_file() or not isinstance(checksum, str)
                or re.fullmatch(r"[0-9a-f]{64}", checksum) is None or maximum is not None and path.stat().st_size > maximum):
            raise CaseError("local_json_asset_invalid")
        before = path.stat()
        state = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        if digest(path) != checksum:
            raise CaseError("local_json_asset_hash_mismatch")
        after = path.stat()
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != state:
            raise CaseError("local_json_asset_hash_mismatch")
        self.states[path] = state

    def guard(self):
        from .native_supervision import require_native_supervision
        if self.closed:
            raise CaseError("local_json_adapter_closed")
        scope = require_native_supervision(self.profile, self.path)
        if scope.min_free_mb < 8192:
            raise CaseError("local_json_host_reserve_too_small")
        for path, expected in self.states.items():
            stat = path.stat()
            if path.is_symlink() or (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) != expected:
                raise CaseError("local_json_asset_changed")

    def predict(self, request):
        from .adapters import _envelope, _request
        from . import tool_arguments as arguments, tool_episodes as episodes, tool_discovery as discovery
        request = _request(request)
        contract = request["contract_id"]
        if contract not in self.capabilities:
            return _envelope("unsupported", error="unsupported_contract")
        raw = {"schema_version": TRACE_VERSION, "settings": deepcopy(self.settings), "calls": [],
               "argument_diagnostic": None, "episode": None}
        if self.failure:
            return _envelope(self.failure[0], raw_output=raw, error=self.failure[1])
        if not self.lock.acquire(blocking=False):
            return _envelope("error", raw_output=raw, error="local_json_concurrency_forbidden")
        try:
            self.guard()
            policy = _ModelPolicy(self, contract)
            if contract == discovery.CONTRACT:
                discovery.validate_input(request["input"])
                response = policy.predict(deepcopy(request["input"]))
            elif contract == arguments.CONTRACT:
                response = arguments.run_arguments(request["input"], policy.predict)
                if response["status"] != "ok":
                    raw["argument_diagnostic"] = response["raw_output"]
            else:
                status, error, output = episodes.run_episode(request["input"], policy)
                response = _envelope(status, output=output if status == "ok" else None, error=error)
                if status != "ok":
                    raw["episode"] = output
            raw["calls"] = policy.calls
            if any(call["http_status"] is not None for call in policy.calls):
                self.provenance["native_response"] = "observed_not_physical_forward_attestation"
            return _envelope(response["status"], output=response["output"], raw_output=raw, error=response["error"])
        except (OSError, ValueError, KeyError, TypeError):
            return _envelope("error", raw_output=raw, error="local_json_execution_or_guard_invalid")
        finally:
            self.lock.release()

    def close(self):
        self.closed = True
