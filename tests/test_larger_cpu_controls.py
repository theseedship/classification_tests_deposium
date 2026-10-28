"""Model-free checks for the explicit larger CPU control and its sealed archive."""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench.decision2_adapter import minimum_available_mib as decision2_floor
from deposium_bench.small_model_adapter import minimum_available_mib as liquid_floor
from deposium_bench.vela2_adapter import minimum_available_mib as vela_floor


FILE = Path(__file__).resolve().parents[1] / "scripts/check-larger-cpu.py"
spec = importlib.util.spec_from_file_location("check_larger_cpu_under_test", FILE)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)

MODELS = (
    ("decision2", "vllm-sr/Decision-2.0-Nox-4B", "nox", decision2_floor),
    ("vela2", "vllm-sr/Vela-2.0-4B", "vela2-4", vela_floor),
    ("small_model", "LiquidAI/d1-3B", "liquid3", liquid_floor),
)


def profile(adapter, repo, mode):
    return {"adapter": adapter, "model": {"repo_id": repo, "mode": mode}}


class FakeAdapter:
    def __init__(self, short=None, overflow=None):
        self.responses = [short or {"status": "ok", "output": {"choice_id": "a"},
                                    "raw_output": {"forward_executed": True}},
                          overflow or {"status": "unsupported", "output": None,
                                       "raw_output": {"forward_executed": False}}]
        self.requests = []
        self.provenance = {"available": True, "qualification": "synthetic_only"}
        self._peak_rss_mb = 123.0
        self.closed = False

    def predict(self, request):
        self.requests.append(request)
        return self.responses[len(self.requests) - 1]

    def close(self):
        self.closed = True


class LargerCpuControlTests(unittest.TestCase):
    def run_control(self, candidate, output, available, adapter=None):
        fake = adapter or FakeAdapter()
        with patch.object(control, "load_profile", return_value=(candidate, "f" * 64)), \
                patch.object(control, "memory_snapshot",
                             return_value={"MemAvailable_mib": available}), \
                patch.object(control, "_source_fingerprint", return_value={"commit": "test"}), \
                patch.object(control, "create_adapter", return_value=fake) as factory, \
                redirect_stdout(io.StringIO()) as printed:
            status = control.check(Path("unused-profile.json"), output)
        return status, fake, factory, printed.getvalue()

    def test_allowlist_rejects_unknown_model_and_wrong_adapter_before_factory(self):
        wrong = (
            profile("small_model", "LiquidAI/d1-omni-600M", "omni"),
            profile("decision2", "LiquidAI/d1-3B", "liquid3"),
            profile("vela2", "vllm-sr/Decision-2.0-Nox-4B", "nox"),
        )
        for candidate in wrong:
            with self.subTest(candidate=candidate), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "archive"
                with patch.object(control, "load_profile", return_value=(candidate, "f" * 64)), \
                        patch.object(control, "memory_snapshot",
                                     side_effect=AssertionError("memory read")) as memory, \
                        patch.object(control, "create_adapter",
                                     side_effect=AssertionError("factory")) as factory:
                    with self.assertRaisesRegex(ValueError, "reviewed larger CPU profile"):
                        control.check(Path("unused-profile.json"), output)
                memory.assert_not_called()
                factory.assert_not_called()
                self.assertFalse(output.exists())

    def test_each_model_checks_ram_before_archive_or_factory(self):
        for name, repo, mode, floor_for in MODELS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "archive"
                candidate = profile(name, repo, mode)
                with patch.object(control, "load_profile", return_value=(candidate, "f" * 64)), \
                        patch.object(control, "memory_snapshot",
                                     return_value={"MemAvailable_mib": floor_for(mode if name == "small_model" else repo) - 1}), \
                        patch.object(control, "_source_fingerprint",
                                     side_effect=AssertionError("fingerprint")) as source, \
                        patch.object(control, "create_adapter",
                                     side_effect=AssertionError("factory")) as factory:
                    with self.assertRaisesRegex(ValueError, "insufficient RAM"):
                        control.check(Path("unused-profile.json"), output)
                source.assert_not_called()
                factory.assert_not_called()
                self.assertFalse(output.exists())

    def test_short_ok_and_overflow_unsupported_seal_zero_scored_cases(self):
        for name, repo, mode, floor_for in MODELS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "archive"
                floor = floor_for(mode if name == "small_model" else repo)
                status, adapter, factory, printed = self.run_control(
                    profile(name, repo, mode), output, floor)
                self.assertEqual(status, 0)
                self.assertTrue(adapter.closed)
                factory.assert_called_once()
                self.assertIn("synthetic_controls=pass; scored_cases=0", printed)
                self.assertEqual(len(adapter.requests), 2)
                self.assertTrue(all(request["contract_id"] == "bench.context-choice"
                                    for request in adapter.requests))
                self.assertEqual(adapter.requests[0]["input"]["context"],
                                 "Les documents sont stockés dans le dossier Atlas.")
                self.assertGreater(len(adapter.requests[1]["input"]["context"]), 4096)
                manifest = json.loads((output / "manifest.json").read_text())
                self.assertTrue(manifest["controls_passed"])
                self.assertEqual(manifest["scored_cases"], 0)
                self.assertEqual(manifest["scope"], "synthetic_contract_only")
                records = [json.loads(line) for line in (output / "raw.jsonl").read_text().splitlines()]
                self.assertEqual([record["control"] for record in records], ["short", "overflow"])
                self.assertEqual([record["result"]["status"] for record in records],
                                 ["ok", "unsupported"])
                self.assertEqual([record["result"]["raw_output"]["forward_executed"]
                                  for record in records], [True, False])
                seal = json.loads((output / "seal.json").read_text())
                files = {file: hashlib.sha256((output / file).read_bytes()).hexdigest()
                         for file in ("manifest.json", "raw.jsonl")}
                self.assertEqual(seal["files"], files)
                self.assertEqual(seal["sha256"], hashlib.sha256(control._encode(files)).hexdigest())

    def test_error_or_refusal_fails_control_and_preserves_sealed_evidence(self):
        name, repo, mode, floor_for = MODELS[2]
        failures = (
            ({"status": "error", "raw_output": {"forward_executed": False}}, None),
            ({"status": "unsupported", "raw_output": {"forward_executed": False}}, None),
            (None, {"status": "error", "raw_output": {"forward_executed": False}}),
            (None, {"status": "unsupported", "raw_output": {"forward_executed": True}}),
        )
        for short, overflow in failures:
            with self.subTest(short=short, overflow=overflow), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "archive"
                status, adapter, _, printed = self.run_control(
                    profile(name, repo, mode), output, floor_for(mode),
                    FakeAdapter(short=short, overflow=overflow))
                self.assertEqual(status, 1)
                self.assertTrue(adapter.closed)
                self.assertIn("synthetic_controls=fail; scored_cases=0", printed)
                manifest = json.loads((output / "manifest.json").read_text())
                self.assertFalse(manifest["controls_passed"])
                self.assertEqual(manifest["scored_cases"], 0)
                self.assertTrue((output / "seal.json").is_file())


if __name__ == "__main__":
    unittest.main()
