"""Bounded JSON-line exchange with an already started, nonblocking worker.

The caller owns process lifetime, resource monitoring and the child environment.
No model or third-party package is imported here.
"""
from __future__ import annotations

import json
import math
import os
import selectors
import time

from .cases import _json as validate_json

MAX_LINE = 1024 * 1024


def wire(value):
    validate_json(value)
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def decode(data):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    value = json.loads(data, object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))
    validate_json(value)
    return value


def exchange(process, message, *, timeout_seconds, monitor, error_prefix="worker") -> dict:
    """Send one JSON line and receive exactly one JSON object, with no surplus bytes.

    ``process`` must expose nonblocking stdin/stdout pipes. ``monitor`` may raise to
    stop the exchange, and is called at most 50 ms apart while waiting.
    """
    payload = wire(message)
    if len(payload) > MAX_LINE:
        raise ValueError(f"{error_prefix}_request_too_large")
    if process is None or process.poll() is not None:
        raise OSError(f"{error_prefix}_worker_exited")
    if (not callable(monitor) or type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
        raise ValueError(f"{error_prefix}_worker_protocol_invalid")

    sent = 0
    buffer = bytearray()
    deadline = time.monotonic() + timeout_seconds
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdin, selectors.EVENT_WRITE)
        selector.register(process.stdout, selectors.EVENT_READ)
        while True:
            monitor()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"{error_prefix}_worker_timeout")
            for key, event in selector.select(min(remaining, 0.05)):
                if event & selectors.EVENT_WRITE:
                    count = os.write(key.fd, payload[sent:sent + 65536])
                    if count <= 0:
                        raise OSError(f"{error_prefix}_worker_exited")
                    sent += count
                    if sent == len(payload):
                        selector.unregister(process.stdin)
                if event & selectors.EVENT_READ:
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        raise OSError(f"{error_prefix}_worker_exited")
                    buffer.extend(chunk)
                    if len(buffer) > MAX_LINE:
                        raise ValueError(f"{error_prefix}_worker_output_too_large")
                    if b"\n" in buffer:
                        line, _, rest = buffer.partition(b"\n")
                        if rest or sent != len(payload):
                            raise ValueError(f"{error_prefix}_worker_protocol_invalid")
                        value = decode(line)
                        if not isinstance(value, dict):
                            raise ValueError(f"{error_prefix}_worker_protocol_invalid")
                        return value
