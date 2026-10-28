"""Persistent offline Noma choice worker; model imports occur only after initialize."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import resource
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deposium_bench.choice_protocol import ordered_choice_ids, validate_choice_input

MAX_LINE = 1024 * 1024
REFERENCE_TIME = "2026-10-03T00:00:00Z"
NATIVE_MAX_PREFIX_TOKENS = 4096
HIGH_PREFIX_CAP = 100000


class NomaWorkerError(ValueError):
    """An expected protocol, encoding or native-result failure."""


def _unique(items):
    value = {}
    for key, item in items:
        if key in value:
            raise NomaWorkerError("noma_duplicate_json_key")
        value[key] = item
    return value


def _read():
    data = sys.stdin.buffer.readline(MAX_LINE + 1)
    if not data:
        return None
    if len(data) > MAX_LINE or not data.endswith(b"\n"):
        raise NomaWorkerError("noma_protocol_limit")
    return json.loads(data, object_pairs_hook=_unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          NomaWorkerError("noma_nonfinite_json")))


def _rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _block_network():
    def blocked(*_args, **_kwargs):
        raise OSError("noma_network_disabled")
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.socket.sendto = blocked
    socket.create_connection = blocked


def _versions(pins):
    if (not isinstance(pins, dict) or not pins or
            any(not isinstance(k, str) or not k or not isinstance(v, str) or not v
                for k, v in pins.items())):
        raise NomaWorkerError("noma_runtime_pins_invalid")
    try:
        actual = {name: importlib.metadata.version(name) for name in pins if name != "python"}
    except importlib.metadata.PackageNotFoundError as exc:
        raise NomaWorkerError("noma_runtime_missing") from exc
    actual["python"] = sys.version.split()[0]
    if any(actual.get(name) != version for name, version in pins.items()):
        raise NomaWorkerError("noma_runtime_lock_mismatch")
    return actual


def _input_hash(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _blank_raw(value, ids):
    return {"native_result": None, "native_tokens": 0, "input_sha256": _input_hash(value),
            "ordered_ids": ids, "encoding_info": None, "forward_executed": False,
            "decision_ms": None, "inference_ms": None, "rss_mb": None}


def _finish(raw, started):
    raw["decision_ms"] = (time.perf_counter() - started) * 1000
    raw["rss_mb"] = _rss()


def _result(status, raw, error=None, output=None):
    return {"status": status, "output": output, "raw_output": raw, "error": error}


def _predict(model, value, cap, *, serializer_cls=None, fact_channel=None):
    """Project a choice onto one native question and audit its real flat forward."""
    started = time.perf_counter()
    validate_choice_input(value)
    ids = ordered_choice_ids(value)
    raw = _blank_raw(value, ids)
    if serializer_cls is None:
        from noma.model.serialize import Serializer as serializer_cls
    if fact_channel is None:
        from noma.model import facts as fact_channel
    criteria = {f"c{i}": option["description"] for i, option in enumerate(value["options"])}
    question = {"type": "choice", "instructions": value["question"], "criteria": criteria}
    questions = {"answer": question}
    state = value["context"]
    if model.bucket is not None or model._graphs is not None or model.cfg.use_facts is not True:
        return _result("error", None, "noma_model_mode_changed")
    try:
        prefix = model.ser.prefix(state, [question], REFERENCE_TIME)
        uncapped = serializer_cls(model.tok, max_prefix_tokens=HIGH_PREFIX_CAP,
                                  use_facts=True).prefix(state, [question], REFERENCE_TIME)
        block = model.ser.block(question)
        fact_questions = [question["instructions"] + " " + " ".join(criteria.values())]
        fact_lines = fact_channel.facts(state, fact_questions, REFERENCE_TIME)
    except Exception:
        # Token counts do not exist if serialization failed; do not invent them.
        return _result("error", None, "noma_encoding_failed")
    expected_ids = prefix.ids + block.ids
    full_tokens = len(uncapped.ids) + len(block.ids)
    prefix_equal = prefix.ids == uncapped.ids
    raw["encoding_info"] = {
        # Count the complete high-cap sequence even when the native prefix truncates.
        # This keeps tokens == prefix_tokens + block_tokens on unsupported rows.
        "tokens": full_tokens, "prefix_tokens": len(uncapped.ids),
        "block_tokens": len(block.ids), "prefix_truncated": bool(prefix.truncated or uncapped.truncated),
        "prefix_uncapped_equal": prefix_equal, "forward_count": 0,
        "forward_ids_equal": False, "facts_version": model.cfg.facts_version,
        "reference_time": REFERENCE_TIME, "fact_lines": fact_lines,
    }
    if (prefix.truncated or uncapped.truncated or not prefix_equal or
            full_tokens > cap or len(expected_ids) > cap):
        _finish(raw, started)
        return _result("unsupported", raw, "noma_context_overflow")

    observed = {"count": 0, "equal": True}
    native_hidden = model.hidden

    def traced_hidden(input_ids, **kwargs):
        observed["count"] += 1
        actual = input_ids.detach().cpu().tolist()
        observed["equal"] = observed["equal"] and (
            list(input_ids.shape) == [1, len(expected_ids)] and actual == [expected_ids])
        raw["encoding_info"]["forward_count"] = observed["count"]
        raw["encoding_info"]["forward_ids_equal"] = observed["equal"]
        if not observed["equal"]:
            raise NomaWorkerError("noma_forward_ids_mismatch")
        raw["forward_executed"] = True
        return native_hidden(input_ids, **kwargs)

    model.hidden = traced_hidden
    inference_started = time.perf_counter()
    try:
        answers, native_tokens = model.decide(state, questions, reference_time=REFERENCE_TIME,
                                              fork=False)
        raw["inference_ms"] = (time.perf_counter() - inference_started) * 1000
    except NomaWorkerError as exc:
        raw["inference_ms"] = ((time.perf_counter() - inference_started) * 1000
                               if raw["forward_executed"] else None)
        _finish(raw, started)
        return _result("error", raw, str(exc))
    except Exception:
        raw["inference_ms"] = ((time.perf_counter() - inference_started) * 1000
                               if raw["forward_executed"] else None)
        _finish(raw, started)
        return _result("error", raw, "noma_inference_failed")
    finally:
        model.hidden = native_hidden
    if observed["count"] != 1 or not observed["equal"]:
        _finish(raw, started)
        return _result("error", raw, "noma_forward_count_mismatch")
    if type(native_tokens) is not int or native_tokens != len(expected_ids):
        _finish(raw, started)
        return _result("error", raw, "noma_native_tokens_mismatch")
    raw["native_tokens"] = native_tokens
    try:
        if not isinstance(answers, dict) or set(answers) != {"answer"}:
            raise NomaWorkerError("noma_distribution_invalid")
        probabilities, abstain, uncertainty = answers["answer"]
        if (not isinstance(probabilities, dict) or list(probabilities) != list(criteria)
                or any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
                       for p in probabilities.values())
                or abs(sum(probabilities.values()) - 1) > 1e-5
                or type(abstain) not in (int, float) or not math.isfinite(abstain)
                or not 0 <= abstain <= 1
                or type(uncertainty) not in (int, float) or not math.isfinite(uncertainty)
                or uncertainty < 0):
            raise NomaWorkerError("noma_distribution_invalid")
        native = {"probabilities": probabilities, "abstain": abstain, "uncertainty": uncertainty}
        raw["native_result"] = native
        # First maximum in supplied order is the deterministic tie policy.
        first = max(probabilities, key=probabilities.get)
        choice_id = ids[list(criteria).index(first)]
    except (TypeError, ValueError, KeyError, NomaWorkerError):
        _finish(raw, started)
        return _result("error", raw, "noma_distribution_invalid")
    _finish(raw, started)
    return _result("ok", raw, output={"choice_id": choice_id})


def main():
    # Keep model/library printouts off the JSONL protocol channel.
    protocol = os.dup(sys.stdout.fileno())
    sink = os.open(os.devnull, os.O_WRONLY)
    os.dup2(sink, sys.stdout.fileno())
    os.close(sink)

    def emit(value):
        data = (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        if len(data) > MAX_LINE:
            raise NomaWorkerError("noma_protocol_limit")
        while data:
            data = data[os.write(protocol, data):]

    try:
        request = _read()
        if (not isinstance(request, dict) or set(request) != {"op", "config"}
                or request["op"] != "initialize"):
            raise NomaWorkerError("noma_initialization_invalid")
        config = request["config"]
        if (not isinstance(config, dict) or
                set(config) != {"source_dir", "local_dir", "max_length", "threads", "pins"} or
                any(not isinstance(config[k], str) or not Path(config[k]).is_absolute()
                    for k in ("source_dir", "local_dir")) or
                type(config["max_length"]) is not int or not 1 <= config["max_length"] <= 1024 or
                type(config["threads"]) is not int or not 1 <= config["threads"] <= 2):
            raise NomaWorkerError("noma_initialization_invalid")
        source = Path(config["source_dir"])
        local = Path(config["local_dir"])
        if (source.is_symlink() or not source.is_dir() or
                local.is_symlink() or not local.is_dir()):
            raise NomaWorkerError("noma_assets_missing")
        versions = _versions(config["pins"])
        _block_network()
        started = time.perf_counter()
        import torch
        torch.set_num_threads(config["threads"])
        torch.set_num_interop_threads(1)
        sys.path.insert(0, str(source))
        import noma
        from noma import Noma
        model = Noma.from_pretrained(str(local), device="cpu", dtype=torch.bfloat16)
        body_dtype = next(model.body.parameters()).dtype
        if (model.cfg.use_facts is not True or
                model.ser.max_prefix != NATIVE_MAX_PREFIX_TOKENS or
                model.bucket is not None or model._graphs is not None or
                next(model.parameters()).device.type != "cpu" or
                body_dtype != torch.bfloat16):
            raise NomaWorkerError("noma_model_identity_invalid")
        emit({"status": "ready", "runtime": {**versions, "noma-source": noma.__version__},
              "load_ms": (time.perf_counter() - started) * 1000, "rss_mb": _rss(),
              "native_max_prefix_tokens": model.ser.max_prefix,
              "dtype": "bfloat16", "device": "cpu",
              "facts_version": model.cfg.facts_version})
    except Exception as exc:
        code = str(exc) if isinstance(exc, NomaWorkerError) else "noma_initialization_failed"
        emit({"status": "error", "error": code})
        os.close(protocol)
        return
    try:
        while True:
            request = _read()
            if request is None:
                return
            if (not isinstance(request, dict) or
                    set(request) != {"op", "sequence", "input"} or
                    request["op"] != "predict" or
                    type(request["sequence"]) is not int or request["sequence"] < 0):
                raise NomaWorkerError("noma_protocol_invalid")
            try:
                result = _predict(model, request["input"], config["max_length"])
            except Exception:
                result = {"status": "error", "output": None, "raw_output": None,
                          "error": "noma_inference_failed"}
            emit({"sequence": request["sequence"], **result})
    except Exception as exc:
        code = str(exc) if isinstance(exc, NomaWorkerError) else "noma_protocol_invalid"
        emit({"status": "error", "error": code})
    finally:
        os.close(protocol)


if __name__ == "__main__":
    main()
