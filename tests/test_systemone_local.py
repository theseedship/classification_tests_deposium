"""Offline contracts of the native gateway adapter; no weights or service."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from deposium_bench.adapters import create_adapter, parse_profile
from deposium_bench.campaigns import _prepare_profile, _validate_output_scope, CampaignError
from deposium_bench import systemone_local as local
from deposium_bench.native_resources import parse_vm_stat, process_group_rss_mib

KEY = "synthetic-local-fixture-key"


class LocalSystemOneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "profile.json"
        records = {}
        for name in ("model", "runtime", "gateway", "harness", "runtime_pin"):
            path = self.root / name
            path.write_bytes((name + "-synthetic-fixture").encode())
            records[name] = {"sha256": local.digest(path),
                "binary" if name in {"runtime", "gateway"} else "path": str(path)}
        records["model"].update(repo_id="fixture/model", revision="a" * 40, alias="fixture-model")
        self.session = {"schema_version": "deposium.local-model-session/v1", **records,
            "endpoint": "http://127.0.0.1:11438/v1/systemone", "max_rss_mb": 20480,
            "settings": {"context": 4096, "parallel": 1, "concurrency": 1,
                "questions_per_call": 1, "truncation": "reject_in_pinned_native_engine"}}
        self.session_path = self.root / "session.json"
        self.session_path.write_text(json.dumps(self.session))
        self.profile = {"schema_version": "deposium.candidate/v1", "profile_id": "fixture",
            "adapter": "systemone_local", "qualification": "model_isolated",
            "capabilities": ["bench.context-choice"], "revision": "a" * 40, "recordings": None,
            "timeout_seconds": 1, "model": {"endpoint": self.session["endpoint"], "model_id": "fixture-model",
                "repo_id": "fixture/model", "session_manifest": "session.json",
                "session_sha256": local.digest(self.session_path), "max_length": 4096,
                "max_rss_mb": 20480, "credential_env": local.AUTH_ENV}}
        self.path.write_text(json.dumps(self.profile))
        self.request = {"case_id": "semantic-case-must-stay-out", "contract_id": "bench.context-choice",
            "input": {"context": "A synthetic context", "question": "Choose the action", "options": [
                {"id": "semantic-first", "description": "First option"},
                {"id": "semantic-second", "description": "Second option"}]}}
        self.native = {"model": self.session["model"]["path"], "answers": {"answer": {
            "type": "choice", "choice": "c1", "probabilities": {"c0": .2, "c1": .8}, "confidence": .3}},
            "usage": {"input_tokens": 23, "output_tokens": 0}}
        self.env = patch.dict(os.environ, {local.AUTH_ENV: KEY})
        self.env.start()
        self.addCleanup(self.env.stop)

    def adapter(self):
        result = create_adapter(self.profile, self.path)
        self.addCleanup(result.close)
        return result

    def response(self, native=None):
        return 200, json.dumps(self.native if native is None else native).encode()

    def test_no_request_during_construction_and_mapping_uses_no_annotations(self):
        with patch.object(local, "http_request", return_value=self.response()) as call:
            adapter = self.adapter()
            call.assert_not_called()
            result = adapter.predict(self.request)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"], {"choice_id": "semantic-second"})
        payload = json.loads(call.call_args.args[3])
        self.assertEqual(payload["questions"]["answer"]["criteria"], {"c0": "First option", "c1": "Second option"})
        self.assertNotIn("semantic", call.call_args.args[3].decode())
        self.assertNotIn(KEY, json.dumps(result) + json.dumps(adapter.provenance))
        self.assertIsNone(result["raw_output"]["forward_executed"])
        self.assertEqual(result["raw_output"]["native_result"], self.native)

    def test_profile_rejects_remote_proxy_credentials_and_bad_limits(self):
        for change in ({"endpoint": "http://localhost:11438/v1/systemone"},
                       {"endpoint": "https://example.com:443/v1/systemone"},
                       {"endpoint": "http://user:pass@127.0.0.1:11438/v1/systemone"},
                       {"endpoint": "http://127.0.0.1:11438/v1/systemone?forward=remote"},
                       {"max_length": True}, {"session_sha256": "bad"},
                       {"credential_env": "TYPESAFE_API_KEY"}):
            profile = deepcopy(self.profile)
            profile["model"].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                parse_profile(json.dumps(profile).encode())

    def test_missing_or_mutated_assets_and_receipt_never_make_requests(self):
        with patch.object(local, "http_request") as call:
            adapter = self.adapter()
            (self.root / "model").write_bytes(b"changed")
            self.assertEqual(adapter.predict(self.request)["status"], "error")
            call.assert_not_called()
            self.session_path.unlink()
            self.assertEqual(self.adapter().predict(self.request)["status"], "missing")
            call.assert_not_called()

    def test_wrong_models_empty_wrong_and_nonfinite_probabilities_are_rejected(self):
        changes = [lambda n: n.update(model="different-model"),
                   lambda n: n.update(answers={}),
                   lambda n: n["answers"]["answer"].update(probabilities={}),
                   lambda n: n["answers"]["answer"].update(choice="c0"),
                   lambda n: n["answers"]["answer"]["probabilities"].update(c1=float("nan")),
                   lambda n: n["answers"]["answer"]["probabilities"].update(c1=.3),
                   lambda n: n["usage"].update(input_tokens=4097),
                   lambda n: n["usage"].update(output_tokens=1)]
        for change in changes:
            native = deepcopy(self.native)
            change(native)
            with self.subTest(change=change), patch.object(local, "http_request", return_value=self.response(native)):
                result = self.adapter().predict(self.request)
                self.assertEqual(result["status"], "error")
                self.assertIsNone(result["output"])

    def test_error_timeout_and_unsupported_remain_distinct_without_retry(self):
        for side_effect, status in ((TimeoutError(), "timeout"), (OSError(), "error")):
            with self.subTest(status=status), patch.object(local, "http_request", side_effect=side_effect) as call:
                adapter = self.adapter()
                self.assertEqual(adapter.predict(self.request)["status"], status)
                self.assertEqual(adapter.predict(self.request)["status"], status)
                self.assertEqual(call.call_count, 1)
        self.assertEqual(self.adapter().predict({"contract_id": "other"})["status"], "unsupported")

    def test_explicit_native_overflow_is_unsupported_and_other_500_stays_error(self):
        error = {"error": {"code": 500, "type": "server_error", "message":
            "input (4701 tokens) is too large to process. increase the physical batch size (current batch size: 4096)"}}
        with patch.object(local, "http_request", side_effect=[(500, json.dumps(error).encode()), self.response()]):
            adapter = self.adapter()
            refused = adapter.predict(self.request)
            self.assertEqual(refused["status"], "unsupported")
            self.assertIsNone(refused["output"])
            self.assertFalse(refused["raw_output"]["forward_executed"])
            self.assertEqual(adapter.predict(self.request)["status"], "ok")
        context_error = {"error": {"code": 400, "type": "exceed_context_size_error",
                                  "n_prompt_tokens": 4682, "n_ctx": 4096}}
        with patch.object(local, "http_request", return_value=(400, json.dumps(context_error).encode())):
            self.assertEqual(self.adapter().predict(self.request)["status"], "unsupported")
        error["error"]["message"] = "unexpected engine failure"
        with patch.object(local, "http_request", return_value=(500, json.dumps(error).encode())):
            self.assertEqual(self.adapter().predict(self.request)["status"], "error")

    def test_unauthorized_and_secret_echo_are_rejected_without_leaking(self):
        native = deepcopy(self.native)
        native["unexpected"] = KEY
        for response in ((401, b""), self.response(native)):
            with patch.object(local, "http_request", return_value=response):
                result = self.adapter().predict(self.request)
                self.assertEqual(result["status"], "error")
                self.assertNotIn(KEY, json.dumps(result))

    def test_profile_rebasing_and_schema(self):
        profile, _, _ = _prepare_profile(self.path)
        self.assertEqual(profile["model"]["session_manifest"], str(self.session_path))
        try:
            import jsonschema
        except ImportError:
            self.skipTest("optional JSON Schema validator unavailable")
        schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/candidate-v1.schema.json").read_text())
        jsonschema.Draft202012Validator(schema).validate(self.profile)
        wrong = deepcopy(self.profile)
        wrong["model"]["max_length"] = True
        self.assertTrue(list(jsonschema.Draft202012Validator(schema).iter_errors(wrong)))

    def test_resource_memory_parser_and_group_scope(self):
        text = ("Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
                "Pages free: 10.\nPages inactive: 20.\nPages speculative: 3.\nPages purgeable: 7.\n")
        self.assertEqual(parse_vm_stat(text), 33 * 16384 / 2**20)
        with self.assertRaises(ValueError):
            parse_vm_stat("incomplete")
        with self.assertRaises(ValueError):
            process_group_rss_mib(os.getpgrp())
        with patch("deposium_bench.native_resources._capture", return_value="123 1024\n456 4096\n123 2048\n"):
            self.assertEqual(process_group_rss_mib(123), 3)

    def test_mastra_does_not_reserve_the_already_resident_model_twice(self):
        from deposium_bench import mastra_observation as observation
        from deposium_bench.native_supervision import native_supervision
        class FixtureAdapter:
            provenance = {"available": True, "identity_sha256": "fixture-only"}
            def predict(self, request):
                return {"status": "ok", "output": {"choice_id": request["input"]["options"][0]["id"]},
                        "raw_output": None, "error": None}
            def close(self):
                pass
        process = Mock(pid=424242)
        process.poll.return_value = None
        watcher = Mock()
        watcher.is_alive.return_value = True
        guard = {"stop_reason": None, "rss_peak_mib": 18000, "min_available_mib": 8192,
                 "last_observed_monotonic": time.monotonic()}
        self.session.update(pid=process.pid, supervisor={"pid": os.getpid()})
        self.session_path.write_text(json.dumps(self.session))
        self.profile["model"]["session_sha256"] = local.digest(self.session_path)
        self.path.write_text(json.dumps(self.profile))
        with patch("deposium_bench.native_resources.memory_snapshot", return_value={"MemAvailable_mib": 8192}), \
                patch("deposium_bench.native_supervision.os.getpgid", return_value=process.pid), \
                native_supervision(self.path, process=process, watcher=watcher, stop=threading.Event(),
                    guard=guard, max_rss_mb=20480, min_free_mb=8192), \
                patch.object(observation, "create_adapter", return_value=FixtureAdapter()):
            summary = observation.observe_local(observation.DATASET, self.path, self.root / "mastra")
        self.assertEqual(summary["metrics"]["coverage"]["valid_decisions"], 24)
        self.assertEqual(summary["metrics"]["cases_scored"], 0)


if __name__ == "__main__":
    unittest.main()
