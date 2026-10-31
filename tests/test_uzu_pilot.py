"""Owned Uzu controller fixtures. Every native process and HTTP call is mocked."""
import argparse
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from unittest.mock import Mock, patch

from test_uzu_local import UzuFixture
from deposium_bench.physics_corpus import build_cases
from deposium_bench import systemone_local as local
from deposium_bench import uzu_local as uzu

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run-uzu-pilot.py"
SPEC = importlib.util.spec_from_file_location("uzu_pilot_fixture", SCRIPT)
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class UzuPilotTests(UzuFixture):
    def setUp(self):
        super().setUp()
        self.case = build_cases()[0]
        self.dataset = self.root / "cases.jsonl"
        self.dataset.write_text(json.dumps(self.case) + "\n")
        body = local.native_request(self.case["input"], "local/fixture-pack")[2]
        self.prep["request_tokens"] = {hashlib.sha256(body).hexdigest(): {
            "input_tokens": 23, "token_ids_sha256": "a" * 64}}
        self.prep_path.write_text(json.dumps(self.prep))
        self.runtime_manifest = self.root / "runtime.json"
        self.runtime_manifest.write_text(json.dumps({"repository": uzu.REPOSITORY,
            "revision": uzu.UZU_REVISION, "binary_sha256": local.digest(self.binary)}))
        self.args = argparse.Namespace(execute=True, pack=self.pack, binary=self.binary,
            assets_manifest=self.assets_path, runtime_manifest=self.runtime_manifest,
            preparation=self.prep_path, dataset=self.dataset, output=self.root / "new-output",
            model_id="local/fixture-pack", port=11439, max_rss_mb=14336, min_free_mb=8192, max_seconds=1200)
        self.process.poll.return_value = None
        self.decision = {"model": "local/fixture-pack", "answers": {"answer": {
            "type": "choice", "choice": "c3", "probabilities": {"c0": .1, "c1": .2, "c2": .3, "c3": .4},
            "confidence": .03}}, "usage": {"input_tokens": 23, "output_tokens": 0}}
        self.ready = (200, json.dumps({"data": [{"id": "local/fixture-pack"}]}).encode())

    def mocked_execution(self):
        stack = ExitStack()
        stack.enter_context(patch.object(pilot.platform, "system", return_value="Darwin"))
        stack.enter_context(patch.object(pilot.platform, "machine", return_value="arm64"))
        stack.enter_context(patch.object(pilot, "memory_snapshot", return_value={"MemAvailable_mib": 30000}))
        self.port_check = stack.enter_context(patch.object(pilot, "ensure_port_available"))
        stack.enter_context(patch.object(pilot.os, "getpgid", return_value=self.process.pid))
        self.spawn = stack.enter_context(patch.object(pilot, "Popen", return_value=self.process))
        self.http = stack.enter_context(patch.object(pilot, "http_request", return_value=self.ready))
        self.native_http = stack.enter_context(patch.object(local, "http_request",
            return_value=(200, json.dumps(self.decision).encode())))
        self.absent = stack.enter_context(patch.object(pilot, "group_absent", return_value=True))

        def thread_factory(*, target, args, daemon):
            watcher = Mock()
            watcher.is_alive.return_value = True
            def start():
                args[2].update(last_observed_monotonic=pilot.time.monotonic())
            watcher.start.side_effect = start
            return watcher
        stack.enter_context(patch.object(pilot.threading, "Thread", side_effect=thread_factory))

        def finish(process, watcher, stop):
            stop.set()
            if process is not None:
                process.poll.return_value = 0
        self.finish = stack.enter_context(patch.object(pilot.shared, "finish_owned", side_effect=finish))
        return stack

    def test_full_controller_uses_shared_scorer_and_preserves_original_dataset(self):
        before = self.dataset.read_bytes()
        with self.mocked_execution():
            result = pilot.pilot(self.args)
        self.assertTrue(result["completed"])
        self.assertEqual(result["cleanup"], "verified_group_absent")
        self.assertEqual(result["coverage"]["eligible_cases"], 1)
        self.assertIsNone(result["backend_observed"])
        self.assertTrue((self.args.output / "campaign/seal.json").is_file())
        self.assertEqual((self.args.output / "assets-manifest.json").read_bytes(), self.assets_path.read_bytes())
        self.assertEqual((self.args.output / "input-preparation.json").read_bytes(), self.prep_path.read_bytes())
        seal = json.loads((self.args.output / "pilot-seal.json").read_text())
        self.assertEqual(seal["files"]["session.json"], local.digest(self.args.output / "session.json"))
        self.assertIn("campaign/raw.jsonl", seal["files"])
        self.assertFalse(any("private-cache" in name for name in seal["files"]))
        self.assertEqual(self.dataset.read_bytes(), before)
        command = self.spawn.call_args.args[0]
        self.assertEqual(command[:3], [str(self.binary), "server", "--model"])
        self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
        self.assertIs(result["egress_isolated"], False)
        self.assertEqual(command[command.index("--model") + 1], str(self.pack))
        self.assertIn("--no-prefix-cache", command)
        self.assertIs(self.spawn.call_args.kwargs["start_new_session"], True)
        self.assertEqual(self.spawn.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertNotIn(local.AUTH_ENV, self.spawn.call_args.kwargs["env"])
        self.assertNotIn("HF_TOKEN", self.spawn.call_args.kwargs["env"])
        self.assertEqual(self.native_http.call_count, 1)

    def test_cleanup_unknown_never_reports_success_even_if_campaign_completed(self):
        with self.mocked_execution():
            self.absent.return_value = False
            result = pilot.pilot(self.args)
        self.assertEqual(result["cleanup"], "unknown")
        self.assertFalse(result["completed"])

    def test_timeout_case_is_retained_and_cleanup_still_runs(self):
        with self.mocked_execution():
            self.native_http.side_effect = TimeoutError()
            result = pilot.pilot(self.args)
        self.assertFalse(result["completed"])
        self.assertEqual(result["coverage"]["counts_by_status"]["timeout"], 1)
        self.assertEqual(result["cleanup"], "verified_group_absent")
        self.finish.assert_called_once()

    def test_low_memory_stops_before_hashing_pack_or_spawn(self):
        with self.mocked_execution(), patch.object(pilot, "memory_snapshot",
                return_value={"MemAvailable_mib": 100}), patch.object(pilot, "verify_pack") as verify:
            with self.assertRaisesRegex(ValueError, "admission"):
                pilot.pilot(self.args)
            verify.assert_not_called()
            self.spawn.assert_not_called()
        self.assertFalse(self.args.output.exists())

    def test_missing_or_changed_preparation_does_not_launch_or_create_archive(self):
        for mutation in (lambda p: p.update(request_tokens={}),
                         lambda p: p.update(uzu_revision="a" * 40),
                         lambda p: p["request_tokens"].update({"d" * 64: {"input_tokens": 2,
                                                                                     "token_ids_sha256": "e" * 64}})):
            prep = deepcopy(self.prep)
            mutation(prep)
            self.prep_path.write_text(json.dumps(prep))
            with self.mocked_execution(), self.subTest(mutation=mutation), self.assertRaises(ValueError):
                pilot.pilot(self.args)
            self.spawn.assert_not_called()
            self.assertFalse(self.args.output.exists())

    def test_occupied_port_cannot_reuse_an_existing_service(self):
        with self.mocked_execution(), patch.object(pilot, "verify_pack") as verify:
            self.port_check.side_effect = OSError("synthetic address already in use")
            with self.assertRaises(OSError):
                pilot.pilot(self.args)
            self.spawn.assert_not_called()
            verify.assert_not_called()

    def test_wrong_readiness_model_never_reaches_prediction(self):
        def wrong(*args):
            self.process.poll.return_value = 1
            return 200, json.dumps({"data": [{"id": "different-model"}]}).encode()
        with self.mocked_execution(), patch.object(pilot.time, "sleep"):
            self.http.side_effect = wrong
            with self.assertRaisesRegex(ValueError, "startup_stopped"):
                pilot.pilot(self.args)
        self.native_http.assert_not_called()
        self.finish.assert_called_once()

    def test_asset_change_during_preparation_prevents_launch(self):
        count = [0]
        def memory():
            count[0] += 1
            if count[0] == 2:
                (self.pack / "model.safetensors").write_text("changed after verification")
            return {"MemAvailable_mib": 30000}
        with self.mocked_execution(), patch.object(pilot, "memory_snapshot", side_effect=memory):
            with self.assertRaisesRegex(ValueError, "prelaunch_file_changed"):
                pilot.pilot(self.args)
            self.spawn.assert_not_called()

    def test_no_execute_or_wrong_platform_cannot_spawn(self):
        with self.mocked_execution():
            self.args.execute = False
            with self.assertRaisesRegex(ValueError, "explicit_execution"):
                pilot.pilot(self.args)
            self.args.execute = True
            with patch.object(pilot.platform, "system", return_value="Linux"), \
                    self.assertRaisesRegex(ValueError, "mac_arm64"):
                pilot.pilot(self.args)
            self.spawn.assert_not_called()

    def test_budgets_and_port_are_not_silently_increased(self):
        for key, value in (("max_rss_mb", 32768), ("min_free_mb", 0), ("max_seconds", 1201), ("port", True)):
            args = deepcopy(self.args)
            setattr(args, key, value)
            with self.mocked_execution(), self.subTest(key=key), self.assertRaises(ValueError):
                pilot.pilot(args)
            self.spawn.assert_not_called()

    def test_existing_output_and_output_inside_pack_are_refused(self):
        for output in (self.pack, self.pack / "subdir", self.root):
            self.args.output = output
            with self.mocked_execution(), self.subTest(output=output), self.assertRaises(ValueError):
                pilot.pilot(self.args)
            self.spawn.assert_not_called()

    def test_unverified_process_group_is_not_signalled_as_a_group(self):
        with self.mocked_execution(), patch.object(pilot.os, "getpgid", return_value=1):
            with self.assertRaisesRegex(ValueError, "group_not_owned"):
                pilot.pilot(self.args)
        self.finish.assert_not_called()
        self.process.terminate.assert_called_once()
        result = json.loads((self.args.output / "pilot.json").read_text())
        self.assertEqual(result["cleanup"], "unknown")
        self.assertFalse(result["completed"])

    def test_spawn_error_is_preserved_and_does_not_claim_cleanup(self):
        with self.mocked_execution():
            self.spawn.side_effect = OSError("synthetic startup failure")
            with self.assertRaises(OSError):
                pilot.pilot(self.args)
        result = json.loads((self.args.output / "pilot.json").read_text())
        self.assertEqual(result["error"], "OSError")
        self.assertEqual(result["cleanup"], "not_started")
        self.assertFalse(result["completed"])

    def test_cleanup_failure_keeps_primary_error_in_receipt(self):
        with self.mocked_execution():
            self.http.side_effect = RuntimeError("synthetic readiness failure")
            self.finish.side_effect = TimeoutError("synthetic cleanup failure")
            with self.assertRaises(TimeoutError):
                pilot.pilot(self.args)
        result = json.loads((self.args.output / "pilot.json").read_text())
        self.assertEqual(result["error"], "RuntimeError")
        self.assertEqual(result["cleanup_error"], "TimeoutError")
        self.assertEqual(result["cleanup"], "unknown")
        self.assertFalse(result["completed"])

    def test_late_cleanup_keeps_completed_campaign_but_refuses_global_success(self):
        clock = [10.0]
        with self.mocked_execution(), patch.object(pilot.time, "monotonic", side_effect=lambda: clock[0]):
            finish = self.finish.side_effect
            def late(*args):
                finish(*args)
                clock[0] += 2
            self.finish.side_effect = late
            self.args.max_seconds = 1
            result = pilot.pilot(self.args)
        self.assertTrue(result["coverage"]["technical_full_coverage"])
        self.assertFalse(result["completed"])
        self.assertEqual(result["cleanup"], "verified_group_absent")

    def test_group_absence_requires_process_lookup_error(self):
        with patch.object(pilot.os, "killpg", side_effect=ProcessLookupError):
            self.assertTrue(pilot.group_absent(987654))
        with patch.object(pilot.os, "killpg", return_value=None):
            self.assertFalse(pilot.group_absent(987654))
        with patch.object(pilot.os, "killpg", side_effect=PermissionError), self.assertRaises(PermissionError):
            pilot.group_absent(987654)
