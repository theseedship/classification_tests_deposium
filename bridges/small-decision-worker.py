"""Resident offline CPU worker for the two independently pinned small models."""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deposium_bench.worker_transport import MAX_LINE, decode, wire


class WorkerError(ValueError):
    pass


def _read():
    data = sys.stdin.buffer.readline(MAX_LINE + 1)
    if not data:
        return None
    if len(data) > MAX_LINE or not data.endswith(b"\n"):
        raise WorkerError("small_model_protocol_limit")
    return decode(data)


def _block_network():
    def blocked(*_args, **_kwargs):
        raise OSError("small_model_network_disabled")
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.socket.sendto = blocked
    socket.create_connection = blocked


def _versions(pins):
    if (not isinstance(pins, dict) or not pins or
            any(not isinstance(k, str) or not k or not isinstance(v, str) or not v
                for k, v in pins.items())):
        raise WorkerError("small_model_runtime_pins_invalid")
    try:
        actual = {name: importlib.metadata.version(name) for name in pins if name != "python"}
    except importlib.metadata.PackageNotFoundError as exc:
        raise WorkerError("small_model_runtime_missing") from exc
    actual["python"] = sys.version.split()[0]
    if any(actual.get(name) != version for name, version in pins.items()):
        raise WorkerError("small_model_runtime_lock_mismatch")
    return actual


def _backend(mode):
    names = {"omni": "liquid-omni-backend.py", "muose": "muose-backend.py",
             "modernjev": "modernjev-backend.py", "liquid3": "liquid-d1-backend.py"}
    if mode not in names:
        raise WorkerError("small_model_mode_invalid")
    spec = importlib.util.spec_from_file_location("small_model_" + mode,
                                                  Path(__file__).with_name(names[mode]))
    if spec is None or spec.loader is None:
        raise WorkerError("small_model_backend_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(value):
    if not isinstance(value, dict) or value.get("mode") not in {"omni", "muose", "modernjev", "liquid3"}:
        raise WorkerError("small_model_initialization_invalid")
    required = {"mode", "source_dir", "local_dir", "max_length", "threads", "pins"}
    if value["mode"] in {"muose", "modernjev"}:
        required.add("template_path")
    if (set(value) != required or type(value["threads"]) is not int
            or not 1 <= value["threads"] <= 2
            or type(value["max_length"]) is not int
            or value["max_length"] != {"omni": 16384, "muose": 512,
                                        "modernjev": 4096, "liquid3": 4096}[value["mode"]]):
        raise WorkerError("small_model_initialization_invalid")
    for name in required & {"source_dir", "local_dir", "template_path"}:
        path = value[name]
        if not isinstance(path, str) or not Path(path).is_absolute() or Path(path).is_symlink():
            raise WorkerError("small_model_initialization_invalid")
    return value


def main():
    protocol = os.dup(sys.stdout.fileno())
    sink = os.open(os.devnull, os.O_WRONLY)
    os.dup2(sink, sys.stdout.fileno())
    os.close(sink)

    def emit(value):
        data = wire(value)
        if len(data) > MAX_LINE:
            raise WorkerError("small_model_protocol_limit")
        while data:
            data = data[os.write(protocol, data):]

    try:
        request = _read()
        if not isinstance(request, dict) or set(request) != {"op", "config"} or request["op"] != "initialize":
            raise WorkerError("small_model_initialization_invalid")
        config = _config(request["config"])
        versions = _versions(config["pins"])
        _block_network()
        engine = _backend(config["mode"]).initialize(config)
        ready = engine.ready()
        expected_ready = {"runtime", "load_ms", "rss_mb", "max_length", "dtype", "device", "backend"}
        if config["mode"] in {"muose", "modernjev"}:
            expected_ready.add("template_sha256")
        if not isinstance(ready, dict) or set(ready) != expected_ready:
            raise WorkerError("small_model_ready_invalid")
        ready["runtime"] = versions
        emit({"status": "ready", **ready})
    except Exception as exc:
        emit({"status": "error", "error": str(exc) if isinstance(exc, WorkerError)
              else "small_model_initialization_failed"})
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
                raise WorkerError("small_model_protocol_invalid")
            try:
                result = engine.predict(request["input"])
                if not isinstance(result, dict) or set(result) != {"status", "output", "raw_output", "error"}:
                    raise WorkerError("small_model_result_invalid")
            except Exception:
                result = {"status": "error", "output": None, "raw_output": None,
                          "error": "small_model_inference_failed"}
            emit({"sequence": request["sequence"], **result})
    except Exception as exc:
        emit({"status": "error", "error": str(exc) if isinstance(exc, WorkerError)
              else "small_model_protocol_invalid"})
    finally:
        os.close(protocol)


if __name__ == "__main__":
    main()
