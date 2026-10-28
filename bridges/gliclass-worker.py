"""Bounded, offline GLiClass worker; importing this file never imports a model."""
from __future__ import annotations

import importlib.metadata
import importlib.util
import os
from pathlib import Path
import socket
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deposium_bench.worker_transport import MAX_LINE, decode, wire


class WorkerError(ValueError):
    pass


def _read():
    data = sys.stdin.buffer.readline(MAX_LINE + 1)
    if not data:
        return None
    if len(data) > MAX_LINE or not data.endswith(b"\n"):
        raise WorkerError("gliclass_protocol_limit")
    return decode(data)


def _block_network():
    def blocked(*_args, **_kwargs):
        raise OSError("gliclass_network_disabled")
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.socket.sendto = blocked
    socket.create_connection = blocked
    socket.getaddrinfo = blocked


def _versions(pins):
    if (not isinstance(pins, dict) or not pins
            or any(not isinstance(k, str) or not k or not isinstance(v, str) or not v
                   for k, v in pins.items())):
        raise WorkerError("gliclass_runtime_pins_invalid")
    try:
        actual = {name: importlib.metadata.version(name) for name in pins if name != "python"}
    except importlib.metadata.PackageNotFoundError as exc:
        raise WorkerError("gliclass_runtime_missing") from exc
    actual["python"] = sys.version.split()[0]
    if any(actual.get(name) != version for name, version in pins.items()):
        raise WorkerError("gliclass_runtime_lock_mismatch")
    return actual


def _config(value):
    required = {"source_dir", "local_dir", "max_length", "threads", "pins",
                "device", "dtype", "backend"}
    if (not isinstance(value, dict) or set(value) != required
            or value["device"] != "mps" or value["dtype"] != "bfloat16"
            or value["backend"] != "eager" or type(value["max_length"]) is not int
            or value["max_length"] != 4096 or type(value["threads"]) is not int
            or not 1 <= value["threads"] <= 2):
        raise WorkerError("gliclass_initialization_invalid")
    for name in ("source_dir", "local_dir"):
        path = value[name]
        if (not isinstance(path, str) or not Path(path).is_absolute()
                or Path(path).is_symlink() or not Path(path).is_dir()):
            raise WorkerError("gliclass_assets_missing")
    if os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK", "0") != "0":
        raise WorkerError("gliclass_cpu_fallback_forbidden")
    return value


def _backend():
    path = Path(__file__).with_name("gliclass-backend.py")
    spec = importlib.util.spec_from_file_location("pinned_gliclass_backend", path)
    if spec is None or spec.loader is None:
        raise WorkerError("gliclass_backend_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    protocol = os.dup(sys.stdout.fileno())
    sink = os.open(os.devnull, os.O_WRONLY)
    os.dup2(sink, sys.stdout.fileno())
    os.close(sink)

    def emit(value):
        data = wire(value)
        if len(data) > MAX_LINE:
            raise WorkerError("gliclass_protocol_limit")
        while data:
            data = data[os.write(protocol, data):]

    try:
        request = _read()
        if not isinstance(request, dict) or set(request) != {"op", "config"} or request["op"] != "initialize":
            raise WorkerError("gliclass_initialization_invalid")
        config = _config(request["config"])
        versions = _versions(config["pins"])
        for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY",
                     "HF_HUB_DISABLE_IMPLICIT_TOKEN", "HF_HUB_DISABLE_PROGRESS_BARS"):
            os.environ[name] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        _block_network()
        engine = _backend().initialize(config)
        ready = engine.ready()
        if not isinstance(ready, dict) or set(ready) != {
                "runtime", "load_ms", "rss_mb", "max_length", "dtype", "device", "backend",
                "gpu_allocated_mb"}:
            raise WorkerError("gliclass_ready_invalid")
        ready["runtime"] = versions
        emit({"status": "ready", **ready})
    except Exception as exc:
        # stderr belongs to the caller's private archive, never the JSON protocol.
        traceback.print_exc(file=sys.stderr)
        emit({"status": "error", "error": str(exc) if isinstance(exc, WorkerError)
              else "gliclass_initialization_failed"})
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
                raise WorkerError("gliclass_protocol_invalid")
            try:
                result = engine.predict(request["input"])
                if not isinstance(result, dict) or set(result) != {"status", "output", "raw_output", "error"}:
                    raise WorkerError("gliclass_result_invalid")
            except Exception:
                traceback.print_exc(file=sys.stderr)
                result = {"status": "error", "output": None, "raw_output": None,
                          "error": "gliclass_inference_failed"}
            emit({"sequence": request["sequence"], **result})
    except Exception as exc:
        emit({"status": "error", "error": str(exc) if isinstance(exc, WorkerError)
              else "gliclass_protocol_invalid"})
    finally:
        os.close(protocol)


if __name__ == "__main__":
    main()
