"""Supervisor failure paths without launching processes or loading weights."""
import argparse
import importlib.util
import json
from pathlib import Path
import signal
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run-native-pilot.py"
SPEC = importlib.util.spec_from_file_location("native_pilot", SCRIPT)
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class NativePilotTests(unittest.TestCase):
    def fixture(self, root):
        service, stack = root / "inference", root / "stack"
        service.mkdir()
        stack.mkdir()
        model = root / "fixture.gguf"
        model.write_bytes(b"GGUF-not-real-weights")
        manifest = {"schema_version": "deposium.model-assets/v1", "repo_id": "fixture/model",
                    "revision": "a" * 40, "files": [{"path": model.name,
                    "size": model.stat().st_size, "sha256": pilot.digest(model)}]}
        assets = root / "assets.json"
        assets.write_text(json.dumps(manifest))
        args = argparse.Namespace(service_root=service, stack_root=stack, model=model,
            assets_manifest=assets, output=root / "archive", max_rss_mb=20480, min_free_mb=8192)
        return args, manifest

    def test_admission_precedes_hashing_and_reserve_is_checked_afterwards(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            args, _ = self.fixture(root)
            with patch.object(pilot, "memory_snapshot", return_value={"MemAvailable_mib": 1024}), \
                    patch.object(pilot, "digest", side_effect=AssertionError("no weight reads")), \
                    patch.object(pilot.subprocess, "Popen") as start:
                with self.assertRaisesRegex(ValueError, "before_start"):
                    pilot.pilot(args)
                start.assert_not_called()
            with patch.object(pilot, "memory_snapshot", side_effect=[
                    {"MemAvailable_mib": 50000}, {"MemAvailable_mib": 1024}]), \
                    patch.object(pilot.subprocess, "Popen") as start:
                with self.assertRaisesRegex(ValueError, "reserve_after_asset"):
                    pilot.pilot(args)
                start.assert_not_called()

    def test_malformed_model_provenance_is_rejected_before_weight_reads_or_start(self):
        with tempfile.TemporaryDirectory() as scratch:
            args, valid = self.fixture(Path(scratch))
            invalid = [{k: v for k, v in valid.items() if k != name}
                       for name in ("repo_id", "revision")]
            invalid += [{**valid, name: value} for name, value in (
                ("repo_id", None), ("repo_id", "https://example.invalid/model"),
                ("repo_id", "missing-owner"), ("revision", "main"),
                ("revision", "z" * 40), ("revision", None))]
            for manifest in invalid:
                with self.subTest(manifest=manifest):
                    args.assets_manifest.write_text(json.dumps(manifest))
                    with patch.object(pilot, "memory_snapshot") as memory, \
                            patch.object(pilot, "digest") as weight_read, \
                            patch.object(pilot.subprocess, "Popen") as start:
                        with self.assertRaisesRegex(ValueError, "model_identity_invalid"):
                            pilot.pilot(args)
                        memory.assert_not_called()
                        weight_read.assert_not_called()
                        start.assert_not_called()
                    self.assertFalse(args.output.exists())

    def test_application_destinations_and_symlink_alias_are_rejected_even_for_smoke(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            args, _ = self.fixture(root)
            alias = root / "stack-alias"
            alias.symlink_to(args.stack_root, target_is_directory=True)
            for output in (args.service_root, args.service_root / "pilot",
                           args.stack_root, args.stack_root / "pilot", alias / "pilot"):
                for smoke_only in (True, False):
                    with self.subTest(output=output, smoke_only=smoke_only):
                        args.output, args.smoke_only = output, smoke_only
                        with patch.object(pilot, "memory_snapshot") as memory, \
                                patch.object(pilot.subprocess, "Popen") as start:
                            with self.assertRaisesRegex(ValueError, "output_must_be_outside_application_stack"):
                                pilot.pilot(args)
                            memory.assert_not_called()
                            start.assert_not_called()
                        self.assertEqual(list(args.service_root.iterdir()), [])
                        self.assertEqual(list(args.stack_root.iterdir()), [])

    def test_cleanup_waits_for_resource_writer_before_sealing(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            stop, opened, release, closed, finished = (threading.Event() for _ in range(5))
            errors = []

            def write_delayed_sample():
                with (root / "resources.jsonl").open("x") as stream:
                    opened.set()
                    release.wait(3)
                    stream.write('{"last_sample":true}\n')
                closed.set()

            class SlowCapture(threading.Thread):
                def join(self, timeout=None):
                    if timeout is None:
                        super().join()
                    # Simulate an expired bounded join without a four-second wait.

            writer = SlowCapture(target=write_delayed_sample, daemon=True)
            writer.start()
            self.assertTrue(opened.wait(1))

            def cleanup_and_seal():
                try:
                    pilot.finish_owned(Mock(), writer, stop)
                    pilot.write_new(root / "seal.json", {"sha256": pilot.digest(root / "resources.jsonl")})
                except BaseException as error:
                    errors.append(error)
                finally:
                    finished.set()

            with patch.object(pilot, "stop_owned", side_effect=lambda _: self.assertTrue(closed.is_set())) as terminate:
                cleanup = threading.Thread(target=cleanup_and_seal, daemon=True)
                cleanup.start()
                try:
                    self.assertTrue(stop.wait(1))
                    self.assertFalse(finished.wait(.05))
                    self.assertFalse((root / "seal.json").exists())
                finally:
                    release.set()
                    cleanup.join(timeout=2)
                    writer.join()
                self.assertTrue(finished.is_set())
                self.assertEqual(errors, [])
                terminate.assert_called_once()
            self.assertEqual(json.loads((root / "seal.json").read_text())["sha256"],
                             pilot.digest(root / "resources.jsonl"))

    def test_guards_stop_only_the_owned_group_and_preserve_observations(self):
        for available, rss, expected in ((50000, 2049, "rss_guard"),
                                         (1024, 100, "host_memory_guard")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as scratch:
                process = Mock(pid=424242)
                process.poll.return_value = None
                guard = {"stop_reason": None, "rss_peak_mib": 0, "min_available_mib": 60000}
                args = argparse.Namespace(max_rss_mb=2048, min_free_mb=8192, max_seconds=100)
                with patch.object(pilot, "memory_snapshot", return_value={"MemAvailable_mib": available}), \
                        patch.object(pilot, "process_group_rss_mib", return_value=rss), \
                        patch.object(pilot.os, "killpg") as kill:
                    pilot.watch_resources(process, threading.Event(), guard, Path(scratch), args)
                kill.assert_called_once_with(424242, signal.SIGINT)
                self.assertEqual(guard["stop_reason"], expected)
                sample = json.loads((Path(scratch) / "resources.jsonl").read_text())
                self.assertEqual(sample["process_group_rss_mib"], rss)

    def test_missing_resource_observation_fails_closed(self):
        with tempfile.TemporaryDirectory() as scratch:
            process = Mock(pid=424242)
            process.poll.return_value = None
            guard = {"stop_reason": None, "rss_peak_mib": 0, "min_available_mib": 60000}
            args = argparse.Namespace(max_rss_mb=2048, min_free_mb=8192, max_seconds=100)
            with patch.object(pilot, "memory_snapshot", side_effect=OSError()), \
                    patch.object(pilot.os, "killpg") as kill:
                pilot.watch_resources(process, threading.Event(), guard, Path(scratch), args)
            self.assertEqual(guard["stop_reason"], "resource_observation_failed")
            kill.assert_called_once_with(424242, signal.SIGINT)

    def test_stopped_process_is_never_signalled(self):
        process = Mock(pid=424242)
        process.poll.return_value = 0
        with patch.object(pilot.os, "killpg") as kill:
            pilot.stop_owned(process)
        kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
