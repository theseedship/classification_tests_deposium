"""Offline, resident Laya choice worker. Imports no model before initialization."""
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


class LayaWorkerError(ValueError):
    pass


def _unique(items):
    value = {}
    for key, item in items:
        if key in value:
            raise LayaWorkerError("laya_duplicate_json_key")
        value[key] = item
    return value


def _read():
    data = sys.stdin.buffer.readline(MAX_LINE + 1)
    if not data:
        return None
    if len(data) > MAX_LINE or not data.endswith(b"\n"):
        raise LayaWorkerError("laya_protocol_limit")
    return json.loads(data, object_pairs_hook=_unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(LayaWorkerError("laya_nonfinite_json")))


def _rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _block_network():
    def blocked(*_args, **_kwargs):
        raise OSError("laya_network_disabled")
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.socket.sendto = blocked
    socket.create_connection = blocked


def _versions(pins):
    if (not isinstance(pins, dict) or not pins or
            any(not isinstance(k, str) or not k or not isinstance(v, str) or not v
                for k, v in pins.items())):
        raise LayaWorkerError("laya_runtime_pins_invalid")
    try:
        actual = {name: importlib.metadata.version(name) for name in pins if name != "python"}
    except importlib.metadata.PackageNotFoundError as exc:
        raise LayaWorkerError("laya_runtime_missing") from exc
    actual["python"] = sys.version.split()[0]
    if any(actual.get(name) != version for name, version in pins.items()):
        raise LayaWorkerError("laya_runtime_lock_mismatch")
    return actual


def _input_hash(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ids_hash(ids):
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()


def _result(status, raw, error=None, output=None):
    return {"status": status, "output": output, "raw_output": raw, "error": error}


def _predict(agent, value, max_length, head_length, *, common=None):
    """Use Laya's own encoder to prove a lossless row before its native forward."""
    started = time.perf_counter()
    validate_choice_input(value)
    ids = ordered_choice_ids(value)
    descriptions = [option["description"] for option in value["options"]]
    raw = {"native_result": None, "input_sha256": _input_hash(value), "ordered_ids": ids,
           "ordered_descriptions": descriptions, "encoding_info": None,
           "forward_executed": False, "decision_ms": None, "inference_ms": None, "rss_mb": None}

    def finish(status, error=None, output=None):
        raw["decision_ms"] = (time.perf_counter() - started) * 1000
        raw["rss_mb"] = _rss()
        return _result(status, raw, error, output)

    if common is None:
        from laya import common
    # Descriptions are unique by the bench contract. Native choice labels are rendered
    # into the question, so IDs must not be used as labels in the model-visible row.
    question = {"type": "choice", "instructions": value["question"],
                "criteria": {description: None for description in descriptions}}
    questions = {"answer": question}
    state = value["context"]
    try:
        agent._check_question("answer", question)
        internal = agent._to_internal(question)
        tokenized_options = [common.encode_text(agent.tok, " " + description,
                                                add_special_tokens=False)["input_ids"]
                             for description in descriptions]
        full_question = common.encode_text(agent.tok, "choice question: " + value["question"],
                                           add_special_tokens=False)["input_ids"]
        # The large head invokes the *same* native builder without its regular head cap.
        # A separate option-length check detects its unconditional 48-token option cap.
        full_head_limit = len(full_question) + sum(len(tokens) + 1 for tokens in tokenized_options) + 32
        full_head, full_markers, _ = common.build_head(agent.tok, internal, full_head_limit)
        head, markers, head_stats = common.build_head(agent.tok, internal, head_length)
        full_state_ids = common.encode_text(agent.tok, common.serialize_state(state),
                                            add_special_tokens=False)["input_ids"]
        complete_ids, complete_markers, _, complete_state = common.build_sequence(
            agent.tok, state, internal, max_len=len(full_state_ids) + len(head) + 1,
            head_max_len=head_length, state_ids=full_state_ids,
            return_stats=True, return_truncation_stats=True)
        encoded = agent._encode_state(state, ["answer"], {"answer": internal},
                                      max_len=max_length, head_max_len=head_length)[0]
    except Exception:
        return finish("error", "laya_encoding_failed")
    options_complete = (all(len(tokens) <= 48 for tokens in tokenized_options)
                        and head == full_head and markers == full_markers)
    distinct = head_stats["options_distinct"] == len(descriptions)
    state_dropped = encoded["state_stats"]["state_tokens_dropped"]
    expected_ids = encoded["ids"]
    expected_markers = encoded["markers"]
    reserved_marker = any(agent.tok.mask_token in text
                          for text in [state, value["question"], *descriptions])
    info = {"tokens": len(complete_ids), "state_tokens": len(full_state_ids),
            "state_tokens_dropped": state_dropped, "head_complete": options_complete,
            "options_distinct": distinct, "reserved_marker": reserved_marker,
            "forward_count": 0, "forward_ids_equal": False,
            "forward_masks_equal": False, "expected_sha256": _ids_hash(expected_ids),
            "actual_sha256": None}
    raw["encoding_info"] = info
    if (agent.cfg.get("max_len") != max_length or agent.cfg.get("head_max_len") != head_length
            or agent.device.type != "cpu" or agent.backend != "eager" or agent.amp_enabled):
        return finish("error", "laya_model_mode_changed")
    if (not options_complete or not distinct or reserved_marker or state_dropped != 0
            or encoded["state_stats"]["truncated"] or complete_state["truncated"]
            or len(complete_ids) > max_length or expected_ids != complete_ids
            or expected_markers != complete_markers or len(expected_markers) != len(descriptions)):
        return finish("unsupported", "laya_context_overflow")

    observed = {"count": 0}
    native_forward = agent._forward

    def audited_forward(batch):
        observed["count"] += 1
        info["forward_count"] = observed["count"]
        actual_ids = batch["input_ids"].detach().cpu().tolist()
        info["actual_sha256"] = _ids_hash(actual_ids[0]) if len(actual_ids) == 1 else None
        info["forward_ids_equal"] = actual_ids == [expected_ids]
        info["forward_masks_equal"] = (
            batch["attention_mask"].detach().cpu().tolist() == [[1] * len(expected_ids)]
            and batch["marker_pos"].detach().cpu().tolist() == [expected_markers]
            and batch["marker_mask"].detach().cpu().tolist() == [[True] * len(expected_markers)]
            and batch["qtype"].detach().cpu().tolist() == [0])
        if observed["count"] != 1 or not info["forward_ids_equal"] or not info["forward_masks_equal"]:
            raise LayaWorkerError("laya_forward_encoding_mismatch")
        raw["forward_executed"] = True
        return native_forward(batch)

    agent._forward = audited_forward
    inference_started = time.perf_counter()
    try:
        native = agent.predict(state, questions, max_len=max_length, head_max_len=head_length)
        raw["inference_ms"] = (time.perf_counter() - inference_started) * 1000
    except LayaWorkerError as exc:
        return finish("error", str(exc))
    except Exception:
        return finish("error", "laya_inference_failed")
    finally:
        agent._forward = native_forward
    if observed["count"] != 1:
        return finish("error", "laya_forward_count_mismatch")
    try:
        if not isinstance(native, dict) or set(native) != {"model", "answers", "usage"}:
            raise LayaWorkerError("laya_distribution_invalid")
        answer = native["answers"]["answer"]
        probs = answer["probabilities"]
        usage = native["usage"]
        if (answer["type"] != "choice" or list(probs) != descriptions
                or answer["choice"] not in descriptions
                or any(type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1
                       for p in probs.values())
                or abs(sum(probs.values()) - 1) > 0.002
                or probs[answer["choice"]] + 0.0001 < max(probs.values())
                or usage["truncated"] is not False or usage["state_tokens_dropped"] != 0
                or usage["truncated_questions"] != [] or "options" in usage
                or usage["input_tokens"] != len(expected_ids) or usage["output_tokens"] != 0):
            raise LayaWorkerError("laya_distribution_invalid")
        selected = ids[descriptions.index(answer["choice"])]
    except (KeyError, TypeError, ValueError, LayaWorkerError):
        return finish("error", "laya_distribution_invalid")
    raw["native_result"] = native
    return finish("ok", output={"choice_id": selected})


def main():
    protocol = os.dup(sys.stdout.fileno())
    sink = os.open(os.devnull, os.O_WRONLY)
    os.dup2(sink, sys.stdout.fileno())
    os.close(sink)

    def emit(value):
        data = (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode()
        if len(data) > MAX_LINE:
            raise LayaWorkerError("laya_protocol_limit")
        while data:
            data = data[os.write(protocol, data):]

    try:
        request = _read()
        if not isinstance(request, dict) or set(request) != {"op", "config"} or request["op"] != "initialize":
            raise LayaWorkerError("laya_initialization_invalid")
        config = request["config"]
        if (not isinstance(config, dict) or
                set(config) != {"source_dir", "local_dir", "max_length", "head_length", "threads", "pins"}
                or any(not isinstance(config[k], str) or not Path(config[k]).is_absolute()
                       for k in ("source_dir", "local_dir"))
                or config["max_length"] != 1024 or config["head_length"] != 256
                or type(config["threads"]) is not int or not 1 <= config["threads"] <= 2):
            raise LayaWorkerError("laya_initialization_invalid")
        source, local = Path(config["source_dir"]), Path(config["local_dir"])
        if source.is_symlink() or not source.is_dir() or local.is_symlink() or not local.is_dir():
            raise LayaWorkerError("laya_assets_missing")
        versions = _versions(config["pins"])
        _block_network()
        started = time.perf_counter()
        import torch
        torch.set_num_threads(config["threads"])
        torch.set_num_interop_threads(1)
        sys.path.insert(0, str(source))
        import laya
        agent = laya.load(str(local), device="cpu", backend="eager")
        if (laya.__version__ != "0.3.26" or agent.device.type != "cpu" or agent.backend != "eager"
                or agent.dtype != torch.float32 or agent.amp_enabled
                or agent.cfg.get("max_len") != 1024 or agent.cfg.get("head_max_len") != 256
                or agent.tok.mask_token != "<mask>"
                or next(agent.model.parameters()).device.type != "cpu"):
            raise LayaWorkerError("laya_model_identity_invalid")
        emit({"status": "ready", "runtime": {**versions, "laya": laya.__version__},
              "load_ms": (time.perf_counter() - started) * 1000, "rss_mb": _rss(),
              "max_length": agent.cfg["max_len"], "head_length": agent.cfg["head_max_len"],
              "dtype": "float32", "device": "cpu", "backend": "eager"})
    except Exception as exc:
        emit({"status": "error", "error": str(exc) if isinstance(exc, LayaWorkerError)
              else "laya_initialization_failed"})
        os.close(protocol)
        return
    try:
        while True:
            request = _read()
            if request is None:
                return
            if (not isinstance(request, dict) or set(request) != {"op", "sequence", "input"}
                    or request["op"] != "predict" or type(request["sequence"]) is not int
                    or request["sequence"] < 1):
                raise LayaWorkerError("laya_protocol_invalid")
            try:
                result = _predict(agent, request["input"], config["max_length"], config["head_length"])
            except Exception:
                result = _result("error", None, "laya_inference_failed")
            emit({"sequence": request["sequence"], **result})
    except Exception as exc:
        emit({"status": "error", "error": str(exc) if isinstance(exc, LayaWorkerError)
              else "laya_protocol_invalid"})
    finally:
        os.close(protocol)


if __name__ == "__main__":
    main()
