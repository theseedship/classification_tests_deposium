"""Resident MCPs function replay with bounded JSONL and shared provenance guards."""
from __future__ import annotations

import copy
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

from . import adapters

BRIDGE = Path(__file__).resolve().parents[1] / "bridges/mcps-resident.mjs"
MAX_LINE = 1024 * 1024


class ResidentMCPAdapter:
    """Keep actual MCPs exports loaded; preserve legacy preflight and drift checks."""

    def __init__(self, profile: dict, profile_path: str | Path, stack_root: str | Path | None):
        started = time.perf_counter()
        self._process = None
        self._buffer = bytearray()
        self._sequence = 0
        self._failure = None
        self._timeout = float(profile["timeout_seconds"])
        self.capabilities = list(profile["capabilities"])
        self._delegate = None
        original = copy.deepcopy(profile)
        legacy = {**original, "adapter": "mcps"}
        self.provenance = {"adapter": "mcps_resident", "qualification": profile["qualification"],
                           "capabilities": self.capabilities, "model": None, "available": False,
                           "profile_sha256": adapters._identity(original),
                           "adapter_sha256": adapters._sha(adapters._read(Path(__file__))),
                           "resident_bridge_sha256": adapters._sha(adapters._read(BRIDGE)),
                           "transport": "resident_process_jsonl"}
        try:
            self._delegate = adapters.McpsAdapter(legacy, Path(profile_path).resolve(),
                                                   Path(stack_root) if stack_root is not None else None)
            self.provenance.update({key: value for key, value in self._delegate.provenance.items()
                                    if key not in {"adapter", "profile_sha256", "adapter_sha256", "identity_sha256", "transport"}})
            if self._delegate._failure is not None:
                self._failure = copy.deepcopy(self._delegate._failure)
            else:
                metadata = self._delegate.provenance
                roots = {"node": self._delegate._command[0], "packages": {
                    name: package["root"] for name, package in metadata["runtime_artifacts"]["packages"].items()}}
                command = [self._delegate._command[0], str(BRIDGE), metadata["component"]["root"],
                           adapters.json.dumps(roots, sort_keys=True)]
                self._process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                 stderr=subprocess.DEVNULL, env=adapters._environment(),
                                                 cwd=BRIDGE.parent, start_new_session=True)
                os.set_blocking(self._process.stdin.fileno(), False)
                os.set_blocking(self._process.stdout.fileno(), False)
                ready = self._exchange(None, self._timeout)
                if (not isinstance(ready, dict) or set(ready) != {"status", "worker_load_ms", "capabilities"}
                        or ready["status"] != "ready" or ready["capabilities"] != list(adapters.CONTRACTS)
                        or not self._finite(ready["worker_load_ms"])):
                    raise adapters.AdapterError("resident_ready_invalid")
                self._guard()
                self.provenance.update(available=True, worker_load_ms=ready["worker_load_ms"])
        except TimeoutError:
            self._fail("timeout", "mcps_resident_initialization_timeout")
        except (FileNotFoundError, OSError):
            self._fail("missing", "mcps_resident_runtime_missing")
        except (adapters.AdapterError, ValueError, KeyError, TypeError):
            self._fail("error", "mcps_resident_initialization_invalid")
        except BaseException:
            self.close()
            raise
        self.provenance["init_wall_ms"] = (time.perf_counter() - started) * 1000
        identity = {key: value for key, value in self.provenance.items()
                    if key not in {"init_wall_ms", "worker_load_ms"}}
        self.provenance["identity_sha256"] = adapters._identity(identity)

    @staticmethod
    def _finite(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    def _guard(self):
        if (not self._delegate._unchanged()
                or adapters._sha(adapters._read(Path(__file__))) != self.provenance["adapter_sha256"]
                or adapters._sha(adapters._read(BRIDGE)) != self.provenance["resident_bridge_sha256"]):
            raise adapters.AdapterError("mcps_resident_runtime_changed")

    def _exchange(self, message: dict | None, timeout: float):
        if self._process is None or self._process.poll() is not None:
            raise OSError("resident_exited")
        payload = b"" if message is None else (adapters.json.dumps(message, ensure_ascii=False,
                                             allow_nan=False) + "\n").encode()
        if len(payload) > MAX_LINE:
            raise adapters.AdapterError("resident_request_too_large")
        deadline = time.monotonic() + timeout
        sent = 0
        with selectors.DefaultSelector() as selector:
            if payload:
                selector.register(self._process.stdin, selectors.EVENT_WRITE)
            selector.register(self._process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("resident_timeout")
                for key, event in selector.select(remaining):
                    if event & selectors.EVENT_WRITE:
                        sent += os.write(key.fd, payload[sent:sent + 65536])
                        if sent == len(payload):
                            selector.unregister(self._process.stdin)
                    elif event & selectors.EVENT_READ:
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            raise OSError("resident_exited")
                        self._buffer.extend(chunk)
                        if len(self._buffer) > MAX_LINE:
                            raise adapters.AdapterError("resident_response_too_large")
                        if b"\n" in self._buffer:
                            line, _, rest = self._buffer.partition(b"\n")
                            if rest or sent != len(payload):
                                raise adapters.AdapterError("resident_protocol_invalid")
                            self._buffer.clear()
                            return adapters._json(line)

    def _fail(self, status: str, code: str):
        self._failure = adapters._envelope(status, error=code)
        self.provenance.update(available=False, availability_error=code)
        self.close()

    def predict(self, request: dict) -> dict:
        request = adapters._request(request)
        if request["contract_id"] not in self.capabilities:
            return adapters._envelope("unsupported", error="unsupported_contract")
        if self._failure is not None:
            return copy.deepcopy(self._failure)
        self._sequence += 1
        try:
            self._guard()
            result = self._exchange({"op": "predict", "sequence": self._sequence,
                                     "contract_id": request["contract_id"], "input": request["input"]}, self._timeout)
            self._guard()
            if (not isinstance(result, dict) or set(result) != {"sequence", "status", "output", "raw_output", "error"}
                    or type(result["sequence"]) is not int or result["sequence"] != self._sequence):
                raise adapters.AdapterError("resident_sequence_invalid")
            response = adapters._normalize_envelope({key: value for key, value in result.items() if key != "sequence"})
            if response["status"] in {"ok", "abstain"}:
                raw = response["raw_output"]
                if (not isinstance(raw, dict) or set(raw) != {"decision", "timings"}
                        or not isinstance(raw["timings"], dict) or set(raw["timings"]) != {"decision_ms"}
                        or not self._finite(raw["timings"]["decision_ms"])
                        or raw["decision"] != response["output"]):
                    raise adapters.AdapterError("resident_timings_invalid")
            return response
        except TimeoutError:
            self._fail("timeout", "mcps_resident_timeout")
        except (OSError, ValueError, TypeError, KeyError):
            self._fail("error", "mcps_resident_protocol_or_runtime_changed")
        except BaseException:
            self.close()
            raise
        return copy.deepcopy(self._failure)

    def close(self):
        process = self._process
        if process is None:
            return
        self._process = None
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=1)
        finally:
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()
