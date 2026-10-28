"""Offline Vela3-fast IPC tests; no model, Torch or network dependency."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from deposium_bench.worker_transport import MAX_LINE, wire

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "bridges/vela3-fast-worker.py"
spec = importlib.util.spec_from_file_location("test_vela3_fast_worker", WORKER)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
PINS = {"python": "3.12.12", "torch": "2.14.0", "transformers": "5.17.0",
        "tokenizers": "0.23.3", "safetensors": "0.8.0", "numpy": "2.4.5"}


def config(root):
    return {"source_dir": str(root), "local_dir": str(root), "max_length": 4096,
            "threads": 2, "pins": PINS.copy(), "device": "cpu", "dtype": "float32", "backend": "sdpa"}


class Vela3FastWorkerTests(unittest.TestCase):
    def test_import_is_inert_and_does_not_import_third_party_runtime(self):
        code = ("import importlib.util,sys; "
                f"s=importlib.util.spec_from_file_location('worker',{str(WORKER)!r}); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "assert not any(n in sys.modules for n in ('torch','transformers','numpy'))")
        result = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, b"")

    def test_config_requires_cpu_f32_sdpa_pins_limits_and_same_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            value = config(root)
            with patch.dict(os.environ, {"PYTORCH_ENABLE_MPS_FALLBACK": "0"}):
                self.assertEqual(worker._config(value), value)
                mutations = (lambda c: c.update(device="mps"), lambda c: c.update(device="auto"),
                    lambda c: c.update(dtype="bfloat16"), lambda c: c.update(backend="eager"),
                    lambda c: c.update(max_length=8192), lambda c: c.update(threads=True),
                    lambda c: c.update(threads=3), lambda c: c.update(local_dir="relative"),
                    lambda c: c.update(source_dir=str(root.parent)), lambda c: c.update(extra=True),
                    lambda c: c["pins"].update(torch="0.0"), lambda c: c["pins"].pop("numpy"))
                for mutate in mutations:
                    invalid = deepcopy(value)
                    mutate(invalid)
                    with self.subTest(mutate=mutate), self.assertRaises(worker.WorkerError):
                        worker._config(invalid)
                symlink = root / "link"
                symlink.symlink_to(root, target_is_directory=True)
                invalid = {**value, "source_dir": str(symlink), "local_dir": str(symlink)}
                with self.assertRaisesRegex(worker.WorkerError, "assets_missing"):
                    worker._config(invalid)
            with patch.dict(os.environ, {"PYTORCH_ENABLE_MPS_FALLBACK": "1"}):
                with self.assertRaisesRegex(worker.WorkerError, "fallback_forbidden"):
                    worker._config(value)

    def test_versions_checks_every_pin_and_rejects_missing_runtime(self):
        pins = {**PINS, "python": sys.version.split()[0]}
        with patch.object(worker.importlib.metadata, "version", side_effect=lambda name: pins[name]) as version:
            self.assertEqual(worker._versions(pins), pins)
            self.assertEqual({call.args[0] for call in version.call_args_list}, set(pins)-{"python"})
        with patch.object(worker.importlib.metadata, "version", return_value="wrong"):
            with self.assertRaisesRegex(worker.WorkerError, "lock_mismatch"):
                worker._versions(pins)
        with patch.object(worker.importlib.metadata, "version", side_effect=worker.importlib.metadata.PackageNotFoundError):
            with self.assertRaisesRegex(worker.WorkerError, "runtime_missing"):
                worker._versions(pins)
        for value in ({}, {"python": ""}, {1: "value"}):
            with self.subTest(value=value), self.assertRaisesRegex(worker.WorkerError, "pins_invalid"):
                worker._versions(value)

    def test_bounded_input_rejects_missing_newline_oversize_and_duplicate_keys(self):
        for data in (b"{}", b" " * MAX_LINE + b"\n", b'{"op":1,"op":2}\n'):
            with self.subTest(data=data[:30]), patch.object(worker.sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO(data))):
                with self.assertRaises(ValueError):
                    worker._read()
        with patch.object(worker.sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO(b""))):
            self.assertIsNone(worker._read())

    def _session(self, messages, mode="ok"):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            # A stdlib-only backend substitutes IPC endpoints, not model behavior.
            code = f'''
import importlib.util,types,os,socket
s=importlib.util.spec_from_file_location("worker",{str(WORKER)!r})
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
m._versions=lambda pins:pins
class Engine:
 def ready(self):
  print("backend noisy stdout must be private",flush=True)
  os.write(1,b"native noise\\n")
  if {mode!r}=="bad_ready": return {{}}
  return {{"runtime":{{}},"load_ms":1,"rss_mb":10,"max_length":4096,"dtype":"float32","device":"cpu","backend":"sdpa","gpu_allocated_mb":0}}
 def predict(self,value):
  if {mode!r}=="predict_error": raise RuntimeError("private-sensitive-runtime-exception")
  return {{"status":"ok","output":{{"choice_id":"opaque"}},"raw_output":{{"observed_input":value}},"error":None}}
def initialize(config):
 try: socket.getaddrinfo("network-must-never-be-contacted.invalid",443)
 except OSError as exc:
  assert str(exc)=="vela3_fast_network_disabled"
 else: raise AssertionError("network was not blocked")
 return Engine()
m._backend=lambda:types.SimpleNamespace(initialize=initialize)
m.main()
'''
            initialize = {"op": "initialize", "config": config(root)}
            data = b"".join(wire(message) for message in [initialize, *messages])
            result = subprocess.run([sys.executable, "-I", "-B", "-c", code], input=data,
                                    capture_output=True, timeout=15,
                                    env={**os.environ, "PYTORCH_ENABLE_MPS_FALLBACK": "0"})
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            return [json.loads(line) for line in result.stdout.splitlines()], result.stderr

    def test_protocol_keeps_stdout_private_blocks_network_and_preserves_sequence(self):
        request = {"op": "predict", "sequence": 1, "input": {"context": "visible"}}
        replies, _ = self._session([request])
        self.assertEqual(len(replies), 2)
        self.assertEqual(replies[0]["status"], "ready")
        self.assertEqual(replies[0]["runtime"], PINS)
        self.assertEqual(replies[1], {"sequence": 1, "status": "ok", "output": {"choice_id": "opaque"},
                                    "raw_output": {"observed_input": request["input"]}, "error": None})
        for sequence in (1, 3, True):
            with self.subTest(sequence=sequence):
                replies, _ = self._session([request, {**request, "sequence": sequence}])
                self.assertEqual(replies[-1], {"status": "error", "error": "vela3_fast_protocol_invalid"})

    def test_initialization_and_prediction_failures_remain_distinct_and_private(self):
        replies, _ = self._session([], "bad_ready")
        self.assertEqual(replies, [{"status": "error", "error": "vela3_fast_ready_invalid"}])
        replies, stderr = self._session([{"op": "predict", "sequence": 1, "input": {}}], "predict_error")
        self.assertEqual(replies[1], {"sequence": 1, "status": "error", "output": None,
                                     "raw_output": None, "error": "vela3_fast_inference_failed"})
        self.assertIn(b"private-sensitive-runtime-exception", stderr)
        self.assertNotIn("private-sensitive", json.dumps(replies))


if __name__ == "__main__":
    unittest.main()
