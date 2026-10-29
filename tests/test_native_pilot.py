"""Supervisor failure paths without launching processes or loading weights."""
import argparse
from contextlib import ExitStack, nullcontext, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import signal
import tarfile
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
            assets_manifest=assets, output=root / "archive", max_rss_mb=20480, min_free_mb=8192,
            dataset=None, context=4096, port=11438, subprocess_port=18480, runtime="d3",
            backend="metal", model_id="synthetic-fixture", max_seconds=1200, smoke_only=False)
        return args, manifest

    def campaign_summary(self, total, counts=None, completion="complete"):
        statuses = {name: 0 for name in ("ok", "unsupported", "missing", "error", "timeout", "abstain")}
        statuses.update(counts or {"ok": total})
        scored = statuses["ok"] + statuses["abstain"]
        return {"completion_status": completion, "metrics": {"total_cases": total,
            "counts_by_status": statuses, "scored_cases": scored,
            "verdict": "fail" if scored else "invalid", "passed_cases": 0}}

    def simulated_service(self, args, run_summary, *, mutate_source=False, late_guard_reason=None,
                          lost_supervision=False, prior_guard_reason=None):
        """Exercise real supervisor dispatch/archives, with no process or HTTP."""
        service = args.service_root
        for name in ("scripts/local-inference.py", "src/lib.rs", "Cargo.toml", "Cargo.lock",
                     "rust-toolchain.toml", "config/llama-d3.lock.json", "fixture-runtime"):
            path = service / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic-offline-fixture")
        gateway = service / "target/debug/deposium-inference"
        gateway.parent.mkdir(parents=True)
        gateway.write_bytes(b"synthetic-gateway-not-executed")
        gateway.chmod(0o700)
        runtime = service / "fixture-runtime"
        local = Mock()
        local.read_pin.return_value = {"repository": "https://example.invalid/synthetic-runtime",
                                       "revision": "a" * 40}
        local.verified_runtime.return_value = {"binary": str(runtime), "binary_sha256": pilot.digest(runtime)}
        local.catalog_text.return_value = 'extra_args = []\n'
        local.local_environment.return_value = {}
        process = Mock(pid=424242, returncode=0)
        process.poll.return_value = None
        adapter = Mock()
        adapter.predict.return_value = {"status": "ok"}
        active_scope = Mock()

        def start(*_, **__):
            if mutate_source:
                args.dataset.write_bytes(b"changed after validation")
            return process

        def execute(*_, **kwargs):
            callback = kwargs.get("stop_requested")
            if callback is not None:
                self.assertEqual(callback(), lost_supervision)
            return run_summary

        with ExitStack() as patches:
            patches.enter_context(patch.object(pilot, "memory_snapshot", return_value={"MemAvailable_mib": 50000}))
            patches.enter_context(patch.object(pilot.importlib.util, "spec_from_file_location", return_value=Mock()))
            patches.enter_context(patch.object(pilot.importlib.util, "module_from_spec", return_value=local))
            patches.enter_context(patch.object(pilot.subprocess, "Popen", side_effect=start))
            patches.enter_context(patch.object(pilot.os, "getpgid", return_value=process.pid))
            watcher = patches.enter_context(patch.object(pilot.threading, "Thread"))
            if lost_supervision:
                def scope_lost(*_):
                    guard = watcher.call_args.kwargs["args"][2]
                    guard["stop_reason"] = prior_guard_reason
                    raise pilot.NativeSupervisionError("synthetic watcher stopped")
                active_scope.check.side_effect = scope_lost
            if late_guard_reason:
                def final_sample():
                    guard = watcher.call_args.kwargs["args"][2]
                    self.assertIsNone(guard["stop_reason"])
                    guard["stop_reason"] = late_guard_reason
                watcher.return_value.join.side_effect = final_sample
                patches.enter_context(patch.object(pilot, "stop_owned"))
            finish = patches.enter_context(patch.object(pilot, "finish_owned",
                wraps=pilot.finish_owned if late_guard_reason else None))
            patches.enter_context(patch.object(pilot, "LocalSystemOneAdapter", return_value=adapter))
            http = patches.enter_context(patch.object(pilot, "http_request", side_effect=[
                (200, b""), (401, b""), (400, b""), (404, b""), (400, b"{}")]))
            run = patches.enter_context(patch.object(pilot, "run_campaign", side_effect=execute))
            observe = patches.enter_context(patch.object(pilot, "observe_local", return_value={
                "completion_status": "complete", "metrics": {"coverage": {"valid_decisions": 24}}}))
            scope = patches.enter_context(patch.object(pilot, "native_supervision", return_value=nullcontext(active_scope)))
            scope.active_scope = active_scope
            patches.enter_context(redirect_stdout(io.StringIO()))
            result = pilot.pilot(args)
        self.assertEqual(http.call_count, 5)
        finish.assert_called_once_with(process, watcher.return_value, unittest.mock.ANY)
        adapter.close.assert_called_once()
        return result, run, observe, scope

    def test_cli_preserves_historical_defaults_and_allows_explicit_dataset_smoke(self):
        required = ["--service-root", "synthetic-inference", "--stack-root", "synthetic-stack",
                    "--model", "synthetic.gguf", "--assets-manifest", "synthetic-assets.json",
                    "--model-id", "synthetic", "--backend", "metal", "--output", "synthetic-output"]
        for extra in ([], ["--dataset", "synthetic-cases.jsonl", "--smoke-only"]):
            with patch.object(pilot, "pilot") as launch:
                pilot.main(required + extra)
            args = launch.call_args.args[0]
            self.assertEqual(args.dataset, Path("synthetic-cases.jsonl") if extra else None)
            self.assertEqual(args.smoke_only, bool(extra))
            self.assertEqual((args.context, args.max_seconds, args.min_free_mb), (4096, 1200, 8192))

    def test_invalid_dataset_is_rejected_before_resources_weight_hash_or_start(self):
        canonical = json.loads(pilot.DEFAULT_DATASET.read_text().splitlines()[0])
        changed = json.loads(json.dumps(canonical))
        changed["input"]["context"] += " Changed synthetic facts."
        invalid = [b"", b"not-json\n", b"{}\n", (json.dumps(changed) + "\n").encode(),
                   (json.dumps(canonical) + "\n" + json.dumps(canonical) + "\n").encode()]
        for index, payload in enumerate(invalid):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as scratch:
                args, _ = self.fixture(Path(scratch))
                args.dataset = Path(scratch) / "invalid.jsonl"
                args.dataset.write_bytes(payload)
                with patch.object(pilot, "memory_snapshot") as memory, \
                        patch.object(pilot, "digest") as weight_hash, \
                        patch.object(pilot.subprocess, "Popen") as start:
                    with self.assertRaises(ValueError):
                        pilot.pilot(args)
                memory.assert_not_called()
                weight_hash.assert_not_called()
                start.assert_not_called()
                self.assertFalse(args.output.exists())

    def test_typed_v1_dataset_is_rejected_before_resources_or_start(self):
        with tempfile.TemporaryDirectory() as scratch:
            args, _ = self.fixture(Path(scratch))
            args.dataset = pilot.ROOT / "datasets/decisions-v1/cases.jsonl"
            with patch.object(pilot, "memory_snapshot") as memory, patch.object(pilot.subprocess, "Popen") as start:
                with self.assertRaisesRegex(ValueError, "context_choice_v2"):
                    pilot.pilot(args)
            memory.assert_not_called()
            start.assert_not_called()

    def test_explicit_dataset_has_dynamic_coverage_and_never_requires_accuracy_pass(self):
        cases = (pilot.ROOT / "datasets/capability-choice-v1/cases.jsonl").read_bytes().splitlines(keepends=True)[:12]
        for counts, completion, expected_completed, expected_technical in (
                ({"ok": 12}, "complete", True, True),
                ({"ok": 2, "unsupported": 2, "missing": 2, "error": 2, "timeout": 2, "abstain": 2},
                 "complete", True, False),
                ({"unsupported": 12}, "complete", False, False),
                ({"ok": 1, "missing": 11}, "incomplete", False, False),
                ({"ok": 1, "missing": 11}, "interrupted", False, False)):
            with self.subTest(counts=counts, completion=completion), tempfile.TemporaryDirectory() as scratch:
                args, _ = self.fixture(Path(scratch))
                args.dataset = Path(scratch) / "selected.jsonl"
                payload = b"".join(cases)
                args.dataset.write_bytes(payload)
                summary = self.campaign_summary(12, counts, completion)
                result, run, observe, scope = self.simulated_service(args, summary, mutate_source=True)
                run.assert_called_once_with(args.output.resolve() / "dataset.jsonl", args.output.resolve() / "profile.json",
                                            args.output.resolve() / "campaign", stack_root=args.stack_root,
                                            stop_requested=unittest.mock.ANY)
                observe.assert_not_called()
                scope.assert_called_once()
                scope.active_scope.check.assert_called_once()
                self.assertEqual((args.output / "dataset.jsonl").read_bytes(), payload)
                self.assertEqual(result["dataset"]["sha256"], pilot.digest(args.output / "dataset.jsonl"))
                self.assertEqual(result["dataset"]["validated_cases"], 12)
                self.assertEqual(result["completed"], expected_completed)
                self.assertEqual(result["campaign_coverage"]["technical_full_coverage"], expected_technical)
                self.assertEqual(result["campaign_coverage"]["counts_by_status"], summary["metrics"]["counts_by_status"])
                self.assertEqual(result["campaign_coverage"]["quality_verdict"], summary["metrics"]["verdict"])
                self.assertTrue((args.output / "pilot-seal.json").is_file())

    def test_explicit_phase_stop_hook_uses_live_scope_and_preserves_existing_guard_reason(self):
        for prior_reason in (None, "host_memory_guard"):
            with self.subTest(prior_reason=prior_reason), tempfile.TemporaryDirectory() as scratch:
                args, _ = self.fixture(Path(scratch))
                args.dataset = pilot.DEFAULT_DATASET
                result, run, observe, scope = self.simulated_service(
                    args, self.campaign_summary(132, {"missing": 132}, "incomplete"),
                    lost_supervision=True, prior_guard_reason=prior_reason)
                self.assertTrue(callable(run.call_args.kwargs["stop_requested"]))
                scope.assert_called_once()
                scope.active_scope.check.assert_called_once()
                observe.assert_not_called()
                self.assertFalse(result["completed"])
                self.assertFalse(result["campaign_coverage"]["collection_complete"])
                self.assertEqual(result["campaign_coverage"]["counts_by_status"]["missing"], 132)
                self.assertEqual(result["campaign_coverage"]["quality_verdict"], "invalid")
                self.assertEqual(result["resources"]["stop_reason"], prior_reason or "native_supervision_lost")

    def test_default_sequence_and_smoke_only_retain_their_previous_campaign_volumes(self):
        for smoke_only in (False, True):
            with self.subTest(smoke_only=smoke_only), tempfile.TemporaryDirectory() as scratch:
                args, _ = self.fixture(Path(scratch))
                args.smoke_only = smoke_only
                result, run, observe, scope = self.simulated_service(args, self.campaign_summary(132))
                self.assertTrue(result["completed"])
                self.assertEqual(result["dataset"]["validated_cases"], 132)
                self.assertEqual(result["smoke_cases_scored"], 0)
                if smoke_only:
                    run.assert_not_called()
                    observe.assert_not_called()
                    scope.assert_not_called()
                    self.assertEqual(result["campaigns"], {})
                else:
                    run.assert_called_once()
                    self.assertEqual(run.call_args.args[2], args.output.resolve() / "bases")
                    observe.assert_called_once()
                    self.assertEqual(observe.call_args.args[2], args.output.resolve() / "mastra")
                    scope.assert_called_once()
                    self.assertEqual(set(result["campaigns"]), {"bases", "mastra"})

    def test_guard_tripped_by_final_join_sample_clears_completion_before_sealing(self):
        for mode in ("default", "explicit", "smoke"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as scratch:
                args, _ = self.fixture(Path(scratch))
                args.dataset = pilot.DEFAULT_DATASET if mode == "explicit" else None
                args.smoke_only = mode == "smoke"
                result, _, _, _ = self.simulated_service(args, self.campaign_summary(132),
                                                         late_guard_reason="rss_guard")
                self.assertFalse(result["completed"])
                stored = json.loads((args.output / "pilot.json").read_text())
                self.assertFalse(stored["completed"])
                self.assertEqual(stored["resources"]["stop_reason"], "rss_guard")
                seal = json.loads((args.output / "pilot-seal.json").read_text())
                self.assertEqual(seal["files"]["pilot.json"], pilot.digest(args.output / "pilot.json"))

    def test_source_archive_retains_json_oracles_and_exact_selected_snapshot(self):
        payload = pilot.DEFAULT_DATASET.read_bytes()
        with tempfile.TemporaryDirectory() as scratch:
            target = Path(scratch) / "bench-source.tar"
            pilot.archive_bench_source(target, payload)
            with tarfile.open(target) as source:
                for relative in ("deposium_bench/data/stack-registry.json", "deposium_bench/data/context-distractors.json",
                                 "deposium_bench/research_corpus.py", "deposium_bench/capability_corpus.py",
                                 *("datasets/capability-choice-v1/" + name for name in pilot.SOURCE_FILES)):
                    self.assertEqual(source.extractfile(relative).read(), (pilot.ROOT / relative).read_bytes())
                self.assertEqual(source.extractfile("datasets/native-pilot-selected/cases.jsonl").read(), payload)

    def test_campaign_denominator_mismatch_is_not_reported_as_completed(self):
        summary = self.campaign_summary(12)
        summary["metrics"]["counts_by_status"]["ok"] = 11
        with self.assertRaisesRegex(ValueError, "denominator_mismatch"):
            pilot.dataset_coverage(summary, 12)

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
