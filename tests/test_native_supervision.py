"""Resident native admission requires an effective matching live supervisor."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from deposium_bench import mastra_observation as observation
from deposium_bench import native_supervision as supervision
from deposium_bench.mastra_pilot import DATASET


class FakeAdapter:
    def __init__(self, after_call=lambda: None):
        self.provenance = {"available": True, "identity_sha256": "synthetic-native-test"}
        self.calls = 0
        self.closed = False
        self.after_call = after_call

    def predict(self, request):
        self.calls += 1
        self.after_call()
        return {"status": "ok", "output": {"choice_id": "a"}, "error": None,
                "raw_output": {"forward_executed": None}}

    def close(self):
        self.closed = True


class NativeSupervisionTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name).resolve()
        self.path = self.root / "profile.json"
        self.session_path = self.root / "session.json"
        self.process = Mock(pid=424242)
        self.process.poll.return_value = None
        self.watcher = Mock()
        self.watcher.is_alive.return_value = True
        self.stop = threading.Event()
        self.guard = {"stop_reason": None, "rss_peak_mib": 18000,
                      "min_available_mib": 9000, "last_observed_monotonic": time.monotonic()}
        self.session = {"schema_version": "deposium.local-model-session/v1", "pid": self.process.pid,
                        "supervisor": {"pid": os.getpid()}, "max_rss_mb": 20480}
        self.session_path.write_text(json.dumps(self.session))
        self.profile = {"schema_version": "deposium.candidate/v1", "profile_id": "synthetic-native",
            "adapter": "systemone_local", "qualification": "model_isolated", "revision": "a" * 40,
            "capabilities": ["bench.context-choice"], "recordings": None, "timeout_seconds": 1,
            "model": {"endpoint": "http://127.0.0.1:11438/v1/systemone", "model_id": "fixture",
                      "repo_id": "synthetic/model", "session_manifest": "session.json",
                      "session_sha256": hashlib.sha256(self.session_path.read_bytes()).hexdigest(),
                      "max_length": 4096, "max_rss_mb": 20480,
                      "credential_env": "DEPOSIUM_BENCH_LOCAL_KEY"}}
        self.path.write_text(json.dumps(self.profile))
        group = patch.object(supervision.os, "getpgid", return_value=self.process.pid)
        group.start()
        self.addCleanup(group.stop)

    def scope(self, **changes):
        arguments = dict(process=self.process, watcher=self.watcher, stop=self.stop,
                         guard=self.guard, max_rss_mb=20480, min_free_mb=8192)
        arguments.update(changes)
        return supervision.native_supervision(self.path, **arguments)

    def assert_not_admitted(self, expected):
        output = self.root / "not-admitted"
        with patch.object(observation, "create_adapter") as factory, \
                patch.object(observation, "_stack_context") as stack, \
                patch("deposium_bench.native_resources.memory_snapshot") as memory:
            with self.assertRaisesRegex(ValueError, expected):
                observation.observe_local(DATASET, self.path, output)
        factory.assert_not_called()
        stack.assert_not_called()
        memory.assert_not_called()
        self.assertFalse(output.exists())

    def test_direct_saved_profile_requires_scope_before_ram_archive_or_factory(self):
        self.assert_not_admitted("native_supervision_required")

    def test_effective_scope_is_bound_to_profile_and_cleared_on_exit(self):
        with self.scope() as scope:
            self.assertIs(supervision.require_native_supervision(self.profile, self.path), scope)
            other = deepcopy(self.profile)
            other["model"]["model_id"] = "another-model"
            with self.assertRaisesRegex(ValueError, "binding_changed"):
                supervision.require_native_supervision(other, self.path)
            self.assertEqual(scope.provenance()["min_available_mib"], 8192)
        self.assert_not_admitted("native_supervision_required")
        with self.assertRaisesRegex(ValueError, "not_live"):
            scope.check(self.profile, self.path)

    def test_dead_watcher_exited_process_stop_and_guard_failure_reject_admission(self):
        mutations = [lambda: setattr(self.watcher.is_alive, "return_value", False),
                     lambda: setattr(self.process.poll, "return_value", 0),
                     self.stop.set,
                     lambda: self.guard.update(stop_reason="host_memory_guard")]
        for mutation in mutations:
            self.watcher.is_alive.return_value = True
            self.process.poll.return_value = None
            self.stop.clear()
            self.guard["stop_reason"] = None
            with self.scope(), self.subTest(mutation=mutation):
                mutation()
                self.assert_not_admitted("native_supervision_not_live")

    def test_missing_stale_future_or_violated_samples_fail_closed(self):
        changes = [{"last_observed_monotonic": None},
                   {"last_observed_monotonic": time.monotonic() - 11},
                   {"last_observed_monotonic": time.monotonic() + 60},
                   {"rss_peak_mib": 20481}, {"min_available_mib": 8191},
                   {"rss_peak_mib": float("nan")}]
        for change in changes:
            guard = {**self.guard, **change}
            with self.subTest(change=change), self.assertRaises(supervision.NativeSupervisionError):
                with self.scope(guard=guard):
                    self.fail("invalid guard admitted")

    def test_other_group_supervisor_and_budget_are_rejected(self):
        with patch.object(supervision.os, "getpgid", return_value=self.process.pid + 1):
            with self.assertRaisesRegex(ValueError, "process_mismatch"):
                with self.scope():
                    self.fail("unowned group admitted")
        with self.assertRaisesRegex(ValueError, "budget_mismatch"):
            with self.scope(max_rss_mb=20481):
                self.fail("different budget admitted")
        self.session["supervisor"]["pid"] += 1
        self.session_path.write_text(json.dumps(self.session))
        self.profile["model"]["session_sha256"] = hashlib.sha256(self.session_path.read_bytes()).hexdigest()
        self.path.write_text(json.dumps(self.profile))
        with self.assertRaisesRegex(ValueError, "process_mismatch"):
            with self.scope():
                self.fail("other supervisor admitted")

    def test_replaced_profile_or_session_invalidates_live_scope(self):
        for target in (self.path, self.session_path):
            original = target.read_bytes()
            with self.scope(), self.subTest(path=target.name):
                target.write_bytes(original + b"\n")
                self.assert_not_admitted("binding_changed")
            target.write_bytes(original)

    def test_supervised_resident_model_uses_existing_budget_and_seals_complete_pass(self):
        adapter = FakeAdapter()
        with self.scope(), \
                patch("deposium_bench.native_resources.memory_snapshot", return_value={"MemAvailable_mib": 9000}), \
                patch.object(observation, "create_adapter", return_value=adapter), \
                patch.object(observation, "_stack_context", return_value=({}, None)):
            summary = observation.observe_local(DATASET, self.path, self.root / "complete")
        self.assertEqual(adapter.calls, 24)
        self.assertTrue(adapter.closed)
        self.assertEqual(summary["completion_status"], "complete")
        self.assertEqual(summary["metrics"]["coverage"]["valid_decisions"], 24)
        self.assertEqual(summary["metrics"]["cases_scored"], 0)
        self.assertTrue((self.root / "complete/seal.json").is_file())
        manifest = json.loads((self.root / "complete/manifest.json").read_text())
        self.assertEqual(manifest["native_supervision"]["rss_guard_mib"], 20480)

    def test_loss_during_inflight_call_preserves_record_then_stops_without_next_call(self):
        for failure in (lambda: setattr(self.watcher.is_alive, "return_value", False),
                        lambda: self.guard.update(stop_reason="rss_guard"),
                        self.stop.set):
            self.watcher.is_alive.return_value = True
            self.guard["stop_reason"] = None
            self.stop.clear()
            adapter = FakeAdapter(after_call=failure)
            output = self.root / ("lost-" + str(id(failure)))
            with self.scope(), self.subTest(failure=failure), \
                    patch("deposium_bench.native_resources.memory_snapshot", return_value={"MemAvailable_mib": 9000}), \
                    patch.object(observation, "create_adapter", return_value=adapter), \
                    patch.object(observation, "_stack_context", return_value=({}, None)):
                summary = observation.observe_local(DATASET, self.path, output)
            self.assertEqual(adapter.calls, 1)
            self.assertTrue(adapter.closed)
            self.assertEqual(summary["completion_status"], "incomplete")
            self.assertEqual(summary["stop_reason"], "native_supervision_lost")
            self.assertEqual(summary["metrics"]["coverage"]["statuses"], {"ok": 1, "missing": 23})
            self.assertTrue((output / "seal.json").is_file())

    def test_loss_before_first_call_prevents_any_prediction_and_seals_missing_cases(self):
        adapter = FakeAdapter()
        snapshots = 0
        def snapshot():
            nonlocal snapshots
            snapshots += 1
            if snapshots == 2:  # Admission succeeded; the first call is next.
                self.watcher.is_alive.return_value = False
            return {"MemAvailable_mib": 9000}
        output = self.root / "lost-before-call"
        with self.scope(), \
                patch("deposium_bench.native_resources.memory_snapshot", side_effect=snapshot), \
                patch.object(observation, "create_adapter", return_value=adapter), \
                patch.object(observation, "_stack_context", return_value=({}, None)):
            summary = observation.observe_local(DATASET, self.path, output)
        self.assertEqual(adapter.calls, 0)
        self.assertTrue(adapter.closed)
        self.assertEqual(summary["completion_status"], "incomplete")
        self.assertEqual(summary["stop_reason"], "native_supervision_lost")
        self.assertEqual(summary["metrics"]["coverage"]["statuses"], {"missing": 24})
        self.assertTrue((output / "seal.json").is_file())


if __name__ == "__main__":
    unittest.main()
