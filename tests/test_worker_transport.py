"""Transport regressions with a tiny Python child, no model or network."""
from __future__ import annotations

import os
import subprocess
import sys
import unittest

from deposium_bench import worker_transport as transport


CHILD = r'''import json, sys, time
mode = sys.argv[1]
for line in sys.stdin:
    if mode == 'closed': break
    if mode == 'timeout': time.sleep(1); continue
    if mode == 'midline': sys.stdout.write('{"ok":true'); sys.stdout.flush(); break
    if mode == 'oversize': sys.stdout.write('x' * (1024 * 1024 + 1)); sys.stdout.flush(); break
    if mode == 'duplicate': sys.stdout.write('{"x":1,"x":2}\n'); sys.stdout.flush(); continue
    if mode == 'nan': sys.stdout.write('{"x":NaN}\n'); sys.stdout.flush(); continue
    if mode == 'list': sys.stdout.write('[]\n'); sys.stdout.flush(); continue
    if mode == 'parasite': sys.stdout.write('{"ok":true}\nextra'); sys.stdout.flush(); continue
    request = json.loads(line)
    sys.stdout.write(json.dumps({'echo':request}, ensure_ascii=False) + '\n')
    sys.stdout.flush()
'''


class WorkerTransportTests(unittest.TestCase):
    def child(self, mode):
        process = subprocess.Popen([sys.executable, "-I", "-B", "-c", CHILD, mode],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stdout.fileno(), False)
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.wait(timeout=2)
            process.stdin.close()
            process.stdout.close()
        self.addCleanup(cleanup)
        return process

    def test_reused_worker_and_unicode_line(self):
        process = self.child("echo")
        for value in ({"text": "a\u2028b"}, {"number": 2}):
            reply = transport.exchange(process, value, timeout_seconds=1, monitor=lambda: None)
            self.assertEqual(reply, {"echo": value})
        self.assertIn("\u2028".encode(), transport.wire({"text": "a\u2028b"}))

    def test_closed_and_midline_workers(self):
        for mode in ("closed", "midline"):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(OSError, "test_worker_exited"):
                    transport.exchange(self.child(mode), {"op": "x"}, timeout_seconds=1,
                                       monitor=lambda: None, error_prefix="test")

    def test_timeout_monitors_and_oversize(self):
        calls = []
        with self.assertRaisesRegex(TimeoutError, "test_worker_timeout"):
            transport.exchange(self.child("timeout"), {"op": "x"}, timeout_seconds=0.16,
                               monitor=lambda: calls.append(1), error_prefix="test")
        self.assertGreaterEqual(len(calls), 2)
        with self.assertRaisesRegex(ValueError, "test_worker_output_too_large"):
            transport.exchange(self.child("oversize"), {"op": "x"}, timeout_seconds=1,
                               monitor=lambda: None, error_prefix="test")
        with self.assertRaisesRegex(ValueError, "test_request_too_large"):
            transport.exchange(None, {"text": "x" * transport.MAX_LINE}, timeout_seconds=1,
                               monitor=lambda: None, error_prefix="test")

    def test_duplicate_nonfinite_and_extra_output(self):
        for mode, code in (("duplicate", "duplicate_json_key"),
                           ("nan", "nonfinite_json"),
                           ("list", "test_worker_protocol_invalid"),
                           ("parasite", "test_worker_protocol_invalid")):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(ValueError, code):
                    transport.exchange(self.child(mode), {"op": "x"}, timeout_seconds=1,
                                       monitor=lambda: None, error_prefix="test")
        for data in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            with self.assertRaises(ValueError):
                transport.decode(data)
        with self.assertRaises(ValueError):
            transport.wire({"x": float("nan")})


if __name__ == "__main__":
    unittest.main()
