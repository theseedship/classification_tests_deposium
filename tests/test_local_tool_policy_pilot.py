"""Fake-process launcher controls; these tests never load or execute a model."""
from copy import deepcopy
import argparse
import base64
from contextlib import contextmanager, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from deposium_bench import local_tool_policy as local

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run-local-tool-policy-pilot.py"
SPEC = importlib.util.spec_from_file_location("local_policy_pilot", SCRIPT)
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class LocalToolPolicyPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)
        self.model = self.tmp / pilot.ASSETS["files"][0]["path"]
        self.model.write_bytes(b"synthetic unit fixture; never model weights")
        self.assets = deepcopy(pilot.ASSETS)
        self.assets["files"][0].update(size=self.model.stat().st_size, sha256=pilot.digest(self.model))
        self.manifest = self.tmp / "assets.json"
        self.manifest.write_bytes(json.dumps(self.assets).encode())
        self.binary = self.tmp / "llama-server"
        self.binary.write_bytes(b"synthetic inert native executable")
        self.runtime = {"repository": pilot.upstream.REPOSITORY, "revision": pilot.upstream.PIN,
                        "binary_sha256": pilot.digest(self.binary)}
        for relative in ("native/systemone-preflight.cpp", "docs/LOCAL_TOOL_POLICY_NATIVE_PROTOCOL_20261030.md",
                         pilot.HELDOUT_PROTOCOL, "docs/LOCAL_TOOL_POLICY_V1.md", "datasets/tool-policy-canary-v1/manifest.json",
                         "datasets/tool-policy-heldout-v1/manifest.json", "profiles/qwen3-4b-instruct-q8-assets.json"):
            path = self.tmp / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / relative).read_bytes())
        self.args = argparse.Namespace(source_root=self.tmp, binary=self.binary,
            runtime_manifest=self.tmp / "runtime.json", model=self.model, assets_manifest=self.manifest,
            dataset=ROOT / "datasets/tool-policy-canary-v1/cases.jsonl",
            dataset_manifest=self.tmp / "datasets/tool-policy-canary-v1/manifest.json",
            output=self.tmp / "results/session", port=11446)
        self.process = Mock(pid=424242, returncode=None)
        self.process.poll.return_value = None
        self.watcher = Mock()
        self.watcher.is_alive.return_value = True
        self.generated_key = None
        self.commands, self.controls, self.events = [], [], []
        self.original_popen = pilot.subprocess.Popen
        self.log = b"ggml_metal_init: synthetic GPU\nload_tensors: offloaded 33/33 layers to GPU\n"
        self.available = 50000
        self.props = {"model_alias": pilot.MODEL_ID, "model_ftype": "Q8_0", "total_slots": 1,
            "default_generation_settings": {"n_ctx": 4096}, "chat_template": "{{ 'synthetic template' }}\n\u00e9"}
        self.auth_status = 401
        self.overflow_status = 400
        self.overflow = {"error": {"type": "exceed_context_size_error", "n_prompt_tokens": 9000, "n_ctx": 4096}}
        self.unknown_response_model = pilot.MODEL_ID
        self.echo_props_credential = False
        self.close_writer = True

    def native(self, value, model=None):
        return {"model": model or pilot.MODEL_ID, "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(value)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}

    def fake_launch(self, command, **kwargs):
        if command[0] != str(self.binary):
            self.assertEqual(Path(command[0]).name, "git", "unexpected non-native process in unit fixture")
            return self.original_popen(command, **kwargs)
        self.commands.append(command)
        self.generated_key = kwargs["env"]["LLAMA_API_KEY"]
        self.assertTrue(kwargs["start_new_session"])
        self.assertNotIn(self.generated_key, json.dumps(command))
        for forbidden in ("LLAMA_INHERITED", "GATEWAY_INHERITED", "AWS_SECRET_ACCESS_KEY"):
            self.assertNotIn(forbidden, kwargs["env"])
        kwargs["stdout"].write(self.log)
        kwargs["stdout"].flush()
        return self.process

    def fake_thread(self, *args, **kwargs):
        process, stop, guard, output, envelope = kwargs["args"]
        self.assertEqual((envelope.max_rss_mb, envelope.min_free_mb, envelope.max_seconds), (8192, 8192, 600))
        guard.update(last_observed_monotonic=time.monotonic(), rss_peak_mib=100, min_available_mib=self.available)
        (output / "resources.jsonl").write_text('{"synthetic_resource_sample":true}\n')
        return self.watcher

    def fake_finish(self, process, watcher, stop):
        self.events.append("cleanup")
        stop.set()
        if process is not None:
            process.poll.return_value = 0
            process.returncode = 0
        if watcher is not None and self.close_writer:
            watcher.is_alive.return_value = False
            with (self.args.output / "resources.jsonl").open("a") as stream:
                stream.write('{"synthetic_writer_closed":true}\n')

    def http(self, port, method, path, body, key, timeout):
        self.controls.append((method, path))
        if path == "/health":
            return 200, b"{}"
        if path == "/props":
            props = deepcopy(self.props)
            if self.echo_props_credential:
                escaped = "".join("\\u%04x" % ord(c) for c in self.generated_key)
                return 200, ('{"chat_template":"' + escaped + '"}').encode()
            return 200, json.dumps(props).encode()
        request = json.loads(body)
        if not key:
            return self.auth_status, b"{}"
        if len(request["messages"][1]["content"]) > 70000:
            return self.overflow_status, json.dumps(self.overflow).encode()
        if request["model"] == "unknown-local-policy-model":
            return 200, json.dumps(self.native({"ready": True}, self.unknown_response_model)).encode()
        return 200, json.dumps(self.native({"ready": True})).encode()

    @contextmanager
    def mocked(self):
        def empty_archive(path, dataset):
            with tarfile.open(path, "w"):
                pass
        with patch.object(pilot, "ROOT", self.tmp), patch.object(pilot, "ASSETS", self.assets), \
                patch.object(pilot.upstream, "validated_runtime", return_value=self.runtime), \
                patch.object(pilot, "memory_snapshot", side_effect=lambda: {"MemAvailable_mib": self.available}), \
                patch.object(pilot.socket, "socket"), patch.object(pilot.os, "getpgid", return_value=self.process.pid), \
                patch.object(pilot.subprocess, "Popen", side_effect=self.fake_launch), \
                patch.object(pilot.threading, "Thread", side_effect=self.fake_thread), \
                patch.object(pilot, "http_request", side_effect=self.http), \
                patch.object(local, "http_request", return_value=(200, json.dumps(self.native({"invalid_synthetic_proposal": True})).encode())), \
                patch.object(pilot.shared, "archive_bench_source", side_effect=empty_archive), \
                patch.object(pilot.shared, "finish_owned", side_effect=self.fake_finish), \
                patch.dict(os.environ, {"LLAMA_INHERITED": "fixture", "GATEWAY_INHERITED": "fixture",
                                        "AWS_SECRET_ACCESS_KEY": "synthetic-test-value"}):
            yield

    def assert_sealed_after_cleanup(self):
        self.assertIn("cleanup", self.events)
        seal = json.loads((self.args.output / "pilot-seal.json").read_bytes())
        for relative, checksum in seal["files"].items():
            self.assertEqual(pilot.digest(self.args.output / relative), checksum)
        if (self.args.output / "resources.jsonl").exists():
            self.assertIn("synthetic_writer_closed", (self.args.output / "resources.jsonl").read_text())
        if self.generated_key:
            for path in self.args.output.rglob("*"):
                if path.is_file():
                    self.assertNotIn(self.generated_key.encode(), path.read_bytes())

    def test_public_pin_and_canary_bytes_are_exact_without_loading_any_assets(self):
        manifest = json.loads((ROOT / "profiles/qwen3-4b-instruct-q8-assets.json").read_bytes())
        self.assertEqual(pilot.ASSETS, manifest)
        for name in ("canary", "heldout"):
            manifest = json.loads((ROOT / f"datasets/tool-policy-{name}-v1/manifest.json").read_bytes())
            self.assertEqual(hashlib.sha256((ROOT / f"datasets/tool-policy-{name}-v1/cases.jsonl").read_bytes()).hexdigest(),
                             manifest["cases_sha256"])
        self.assertEqual(pilot.ENVELOPE["admission_available_mib"], 16384)
        self.assertEqual(pilot.local.PROMPT_VERSION, "deposium.local-tool-policy-prompt/v2")

    def test_frozen_manifest_binds_canary_and_heldout_and_refuses_other_inventories(self):
        with patch.object(pilot, "ROOT", self.tmp):
            payload, cases, info = pilot.frozen_dataset(self.args.dataset_manifest, self.args.dataset)
            self.assertEqual((info["cases"], info["families"], info["counts_by_split"]["train"], info["dataset_id"]),
                             (10, 5, 10, "tool-policy-canary-v1"))
            held = self.tmp / "datasets/tool-policy-heldout-v1/manifest.json"
            payload, cases, info = pilot.frozen_dataset(held, ROOT / "datasets/tool-policy-heldout-v1/cases.jsonl")
            self.assertEqual((info["cases"], info["families"], info["counts_by_split"], info["manifest"]),
                             (24, 12, {"train": 0, "calibration": 0, "test": 24}, "datasets/tool-policy-heldout-v1/manifest.json"))
            self.assertEqual(info["counts_by_contract"], {"bench.tool-discovery": 8, "bench.tool-arguments": 4, "bench.tool-episode": 12})
            with self.assertRaisesRegex(ValueError, "frozen_dataset_mismatch"):
                pilot.frozen_dataset(held, self.args.dataset)
            manifest = json.loads(held.read_bytes())
            for relative, pinned in pilot.FROZEN_MANIFESTS.items():
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), pinned)
            # A self-consistent but unpinned manifest (edited reference plus matching
            # hash, or any modified inventory) is not frozen, even under datasets/.
            edited = ROOT / "datasets/tool-policy-heldout-v1/cases.jsonl"
            tampered = edited.read_bytes().replace(b'"value": 75', b'"value": 76')
            self.assertNotEqual(tampered, edited.read_bytes())
            (self.tmp / "tampered.jsonl").write_bytes(tampered)
            for change in ({"cases_sha256": hashlib.sha256(tampered).hexdigest()}, {"status": "draft"},
                           {"case_count": 23}, {"counts_by_split": {"train": 24, "calibration": 0, "test": 0}}, {}):
                unpinned = self.tmp / "datasets/tool-policy-heldout-v1/unpinned.json"
                unpinned.write_text(json.dumps({**manifest, **change}))
                with self.subTest(change=change), self.assertRaisesRegex(ValueError, "manifest_not_frozen"):
                    pilot.frozen_dataset(unpinned, self.tmp / "tampered.jsonl")
            with self.assertRaisesRegex(ValueError, "frozen_dataset_mismatch"):
                pilot.frozen_dataset(held, self.tmp / "tampered.jsonl")
            with self.assertRaisesRegex(ValueError, "outside_checkout"):
                pilot.frozen_dataset(Path(__file__).resolve(), edited)

    def test_actual_source_snapshot_imports_and_displays_help_without_original_checkout(self):
        actual_capture = pilot.shared.archive_bench_source
        self.available = 16000  # Capture source only; no weight hash or process.
        with self.mocked(), patch.object(pilot.shared, "archive_bench_source", side_effect=actual_capture):
            result = pilot.pilot(self.args)
        self.assertEqual(result["status"], "not_run")
        self.assertEqual(self.commands, [])
        extracted = self.tmp / "isolated-source"
        extracted.mkdir()
        with tarfile.open(self.args.output / "bench-source.tar") as snapshot:
            for relative, source in (("scripts/run-local-tool-policy-pilot.py", SCRIPT),
                                     ("scripts/run-upstream-native-pilot.py", Path(pilot.upstream.__file__)),
                                     ("scripts/run-native-pilot.py", Path(pilot.shared.__file__))):
                self.assertEqual(snapshot.extractfile(relative).read(), source.read_bytes())
            snapshot.extractall(extracted, filter="data")
        bootstrap = r'''
import importlib.util
from pathlib import Path
import sys

captured = Path(sys.argv[1]).resolve()
forbidden = Path(sys.argv[2]).resolve()
snapshot_root = captured.parents[1]
sys.path[:] = [entry for entry in sys.path if entry and not Path(entry).resolve().is_relative_to(forbidden)]
assert all(not Path(entry).resolve().is_relative_to(forbidden) for entry in sys.path)

def deny_original_source(event, args):
    if event in {"open", "os.listdir", "os.scandir"} and args and isinstance(args[0], (str, bytes)):
        path = Path(args[0].decode() if isinstance(args[0], bytes) else args[0]).resolve()
        if path.is_relative_to(forbidden):
            raise RuntimeError("original checkout is unavailable to this process")

sys.addaudithook(deny_original_source)
spec = importlib.util.spec_from_file_location("captured_policy_launcher", captured)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.ROOT == snapshot_root
assert Path(module.upstream.__file__) == snapshot_root / "scripts/run-upstream-native-pilot.py"
assert Path(module.shared.__file__) == snapshot_root / "scripts/run-native-pilot.py"
import deposium_bench
assert Path(deposium_bench.__file__).is_relative_to(snapshot_root)
module.main(["--help"])
'''
        child = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", bootstrap,
            str(extracted / "scripts/run-local-tool-policy-pilot.py"), str(ROOT)], cwd=extracted,
            env={"PATH": os.defpath, "LANG": "C.UTF-8"}, text=True, capture_output=True, timeout=20, check=False)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertIn("--runtime-manifest", child.stdout)
        self.assertIn("--assets-manifest", child.stdout)
        self.assertNotIn(str(ROOT), child.stdout)

    def test_shared_campaign_keeps_semantic_failures_and_ignores_unknown_native_request_alias(self):
        previous = os.environ.get(pilot.AUTH_ENV)
        with self.mocked():
            result = pilot.pilot(self.args)
        self.assertTrue(result["collection_complete"])
        self.assertEqual(result["scored_cases"], 10)
        self.assertEqual(result["quality_verdict"], "fail")
        self.assertEqual(result["native_request_alias_enforcement"], False)
        self.assertTrue(result["outer_sealed"])
        self.assertEqual(os.environ.get(pilot.AUTH_ENV), previous)
        self.assertEqual((self.args.output / "chat-template.jinja").read_bytes(), self.props["chat_template"].encode())
        session = json.loads((self.args.output / "session.json").read_bytes())
        self.assertEqual(set(session), {"schema_version", "endpoint", "model", "runtime", "harness", "runtime_pin", "template",
                                       "settings", "max_rss_mb", "pid", "supervisor"})
        self.assertEqual(session["model"]["quantization"], "Q8_0")
        self.assertEqual(session["settings"]["seed"], 42)
        self.assertEqual(session["template"]["sha256"], pilot.digest(self.args.output / "chat-template.jinja"))
        command = self.commands[0]
        for flag in ("--jinja", "--no-context-shift", "--no-warmup", "--no-webui"):
            self.assertIn(flag, command)
        for flag, value in (("--fit", "off"), ("--parallel", "1"), ("--ctx-size", "4096"), ("--ubatch-size", "4096")):
            self.assertEqual(command[command.index(flag) + 1], value)
        self.assert_sealed_after_cleanup()

    def test_memory_refusal_retains_not_run_receipt_before_any_weight_hash_or_process(self):
        self.available = 16000
        original_digest = pilot.digest
        observed = []
        def no_weight_hash(path):
            observed.append(Path(path))
            self.assertNotEqual(Path(path), self.model)
            return original_digest(path)
        with self.mocked(), patch.object(pilot, "digest", side_effect=no_weight_hash):
            result = pilot.pilot(self.args)
        self.assertEqual(result["status"], "not_run")
        self.assertEqual(result["stop_reason"], "insufficient_available_memory")
        self.assertEqual(result["scored_cases"], 0)
        self.assertEqual(self.commands, [])
        self.assertNotIn(self.model, observed)
        preflight = json.loads((self.args.output / "preflight.json").read_bytes())
        self.assertFalse(preflight["admitted"])
        self.assertFalse(preflight["weight_hash_performed"])
        self.assertFalse((self.args.output / "campaign").exists())
        self.assert_sealed_after_cleanup()

    def test_inert_file_read_may_change_atime_without_invalidating_model_identity(self):
        os.utime(self.model, (1, time.time()))
        original_digest = pilot.digest
        observed = []
        def actual_inert_read(path):
            if Path(path) != self.model:
                return original_digest(path)
            before = self.model.stat()
            value = original_digest(path)  # Read only the tiny synthetic fixture.
            after = self.model.stat()
            observed.append((before, after))
            return value
        with self.mocked(), patch.object(pilot, "digest", side_effect=actual_inert_read):
            result = pilot.pilot(self.args)
        self.assertTrue(result["collection_complete"])
        self.assertEqual(result["weight_verification"], "verified")
        self.assertEqual(len(observed), 1)
        before, after = observed[0]
        stable = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        self.assertEqual(stable(before), stable(after))
        if before.st_atime_ns == after.st_atime_ns:
            self.skipTest("This filesystem does not update access time on reads")
        self.assertNotEqual(before, after)

    def test_inert_file_mutation_during_hash_still_refuses_before_launch(self):
        original_digest = pilot.digest
        def changed_after_read(path):
            value = original_digest(path)
            if Path(path) == self.model:
                data = self.model.read_bytes()
                self.model.write_bytes(b"X" + data[1:])
            return value
        with self.mocked(), patch.object(pilot, "digest", side_effect=changed_after_read):
            result = pilot.pilot(self.args)
        self.assertEqual(result["failure_code"], "local_policy_model_changed_during_hash")
        self.assertEqual(self.commands, [])
        self.assertFalse((self.args.output / "campaign").exists())
        self.assert_sealed_after_cleanup()

    def test_occupied_port_refuses_before_weight_hash_and_keeps_existing_service_untouched(self):
        original_digest = pilot.digest
        def no_model_hash(path):
            self.assertNotEqual(Path(path), self.model)
            return original_digest(path)
        sock = Mock()
        sock.__enter__ = Mock(return_value=sock)
        sock.__exit__ = Mock(return_value=False)
        sock.bind.side_effect = OSError("synthetic occupied port")
        with self.mocked(), patch.object(pilot.socket, "socket", return_value=sock), \
                patch.object(pilot, "digest", side_effect=no_model_hash):
            result = pilot.pilot(self.args)
        self.assertEqual(result["failure_code"], "local_policy_port_unavailable")
        self.assertEqual(self.commands, [])
        self.assertEqual(result["scored_cases"], 0)
        self.assert_sealed_after_cleanup()

    def test_wrong_dataset_asset_or_runtime_refuses_before_model_read_or_output(self):
        for variant in ("dataset", "assets", "runtime"):
            if variant == "dataset":
                bad = self.tmp / "bad-cases.jsonl"
                bad.write_bytes(self.args.dataset.read_bytes() + b"\n")
                self.args.dataset = bad
            elif variant == "assets":
                self.args.dataset = ROOT / "datasets/tool-policy-canary-v1/cases.jsonl"
                self.manifest.write_text(json.dumps({**self.assets, "revision": "f" * 40}))
            else:
                self.manifest.write_text(json.dumps(self.assets))
            with self.subTest(variant=variant), self.mocked(), \
                    patch.object(pilot, "digest", side_effect=AssertionError("invalid preflight hashed files")):
                if variant == "runtime":
                    with patch.object(pilot.upstream, "validated_runtime", side_effect=ValueError("wrong_runtime")), \
                            self.assertRaisesRegex(ValueError, "wrong_runtime"):
                        pilot.pilot(self.args)
                else:
                    with self.assertRaisesRegex(ValueError, "frozen_dataset|exact_qwen"):
                        pilot.pilot(self.args)
            self.assertEqual(self.commands, [])
            self.assertFalse(self.args.output.exists())

    def test_partial_metal_offload_fails_before_template_and_quality_calls(self):
        self.log = b"ggml_metal_init: synthetic GPU\nload_tensors: offloaded 32/33 layers to GPU\n"
        with self.mocked():
            result = pilot.pilot(self.args)
        self.assertEqual(result["failure_code"], "local_policy_full_metal_offload_required")
        self.assertFalse((self.args.output / "session.json").exists())
        self.assertFalse((self.args.output / "campaign").exists())
        self.assert_sealed_after_cleanup()

    def test_required_auth_overflow_and_returned_alias_failures_prevent_quality(self):
        for variant in ("auth", "overflow", "returned_model"):
            # Each attempt is isolated and retains its own controls.
            self.args.output = self.tmp / "results" / variant
            self.process.poll.return_value, self.process.returncode = None, None
            self.watcher.is_alive.return_value = True
            self.auth_status = 200 if variant == "auth" else 401
            self.overflow_status = 200 if variant == "overflow" else 400
            self.unknown_response_model = "foreign-model" if variant == "returned_model" else pilot.MODEL_ID
            with self.subTest(variant=variant), self.mocked():
                result = pilot.pilot(self.args)
            self.assertEqual(result["status"], "technical_failure")
            self.assertEqual(result["scored_cases"], 0)
            self.assertFalse((self.args.output / "campaign").exists())
            self.assert_sealed_after_cleanup()

    def test_escaped_credential_in_props_is_hashed_redacted_and_not_written(self):
        self.echo_props_credential = True
        with self.mocked():
            result = pilot.pilot(self.args)
        self.assertEqual(result["failure_code"], "local_policy_response_credential_redacted")
        self.assertTrue(result["technical_controls"][0]["response_redacted"])
        self.assertIsNone(result["technical_controls"][0]["response_base64"])
        self.assertFalse((self.args.output / "native-props.json").exists())
        self.assertFalse((self.args.output / "campaign").exists())
        self.assert_sealed_after_cleanup()

    def test_interrupt_releases_owned_process_and_writer_then_seals_partial_attempt(self):
        with self.mocked(), patch.object(pilot, "run_campaign", side_effect=KeyboardInterrupt()), self.assertRaises(KeyboardInterrupt):
            pilot.pilot(self.args)
        result = json.loads((self.args.output / "pilot.json").read_bytes())
        self.assertEqual(result["status"], "interrupted")
        self.assertTrue(result["owned_process_terminated"])
        self.assertTrue(result["resource_writer_closed"])
        self.assert_sealed_after_cleanup()

    def test_unclosed_writer_is_not_outer_sealed_or_reported_as_complete(self):
        self.close_writer = False
        with self.mocked():
            result = pilot.pilot(self.args)
        self.assertFalse(result["resource_writer_closed"])
        self.assertFalse(result["outer_sealed"])
        self.assertFalse(result["collection_complete"])
        self.assertFalse((self.args.output / "pilot-seal.json").exists())

    def test_actual_synthetic_campaign_and_profile_validate_existing_public_schemas(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is optional")
        with self.mocked():
            pilot.pilot(self.args)
        root = self.args.output
        for name, path in (("candidate", root / "profile.json"), ("campaign", root / "campaign/manifest.json"),
                           ("campaign-summary", root / "campaign/summary.json")):
            schema = json.loads((ROOT / "schemas" / (name + "-v1.schema.json")).read_bytes())
            jsonschema.validate(json.loads(path.read_bytes()), schema)
        schema = json.loads((ROOT / "schemas/result-v1.schema.json").read_bytes())
        for line in (root / "campaign/raw.jsonl").read_bytes().splitlines():
            jsonschema.validate(json.loads(line), schema)

    def test_unowned_group_never_receives_group_signal_only_new_child_is_terminated(self):
        def terminate():
            self.process.poll.return_value = -15
            self.process.returncode = -15
        self.process.terminate.side_effect = terminate
        with self.mocked(), patch.object(pilot.os, "getpgid", return_value=123), \
                patch.object(pilot.os, "killpg", side_effect=AssertionError("unowned group signalled")):
            result = pilot.pilot(self.args)
        self.process.terminate.assert_called_once()
        self.assertEqual(result["failure_code"], "local_policy_process_group_not_owned")
        self.assertTrue(result["owned_process_terminated"])

    def test_help_and_import_are_inert_and_cli_has_no_resource_override(self):
        output = io.StringIO()
        with patch.object(pilot.subprocess, "Popen", side_effect=AssertionError("help launched")), \
                patch.object(pilot, "memory_snapshot", side_effect=AssertionError("help probed resources")), \
                redirect_stdout(output), self.assertRaises(SystemExit) as stopped:
            pilot.main(["--help"])
        self.assertEqual(stopped.exception.code, 0)
        self.assertNotIn("--max-rss", output.getvalue())
        self.assertNotIn("--max-seconds", output.getvalue())
        spec = importlib.util.spec_from_file_location("inert_local_pilot_import", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        with patch.object(pilot.subprocess, "Popen", side_effect=AssertionError("import launched")), \
                patch.object(local, "http_request", side_effect=AssertionError("import HTTP")):
            spec.loader.exec_module(module)


if __name__ == "__main__":
    unittest.main()
