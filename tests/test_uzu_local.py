"""Synthetic Uzu contract checks: no Uzu import, weights, socket or service."""
from contextlib import contextmanager
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

from deposium_bench.adapters import create_adapter, parse_profile
from deposium_bench.campaigns import _prepare_profile
from deposium_bench.native_supervision import native_supervision
from deposium_bench import systemone_local as local, uzu_local as uzu


class UzuFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pack = self.root / "fixture-pack"
        self.pack.mkdir()
        config = {"type": "DecisionModelConfig", "decision": {"codes": [f"code{i}" for i in range(255)],
            "temperature": 1.0}, "token_codec_config": {"prompt_template": "synthetic-not-a-real-renderer"}}
        for name in uzu.REQUIRED_FILES:
            (self.pack / name).write_text("synthetic-never-executed")
        (self.pack / "config.json").write_text(json.dumps(config))
        (self.pack / "chat_template.jinja").write_text(config["token_codec_config"]["prompt_template"])
        self.assets_path = self.root / "assets.json"
        self.refresh_assets()
        self.binary = self.root / "fixture-runtime"
        self.binary.write_bytes(b"synthetic-not-an-executable")
        self.supervisor = self.root / "fixture-supervisor.py"
        self.supervisor.write_text("# synthetic, not executed\n")
        self.value = {"context": "À Paris", "question": "Quel choix ?", "options": [
            {"id": "semantic-first", "description": "Premier choix"},
            {"id": "semantic-second", "description": "Deuxième choix"}]}
        self.body = local.native_request(self.value, "local/fixture-pack")[2]
        self.prep = {"schema_version": "deposium.uzu-input-preparation/v1", "uzu_revision": uzu.UZU_REVISION,
            "model_id": "local/fixture-pack", "assets_sha256": local.digest(self.assets_path),
            "max_tokens": 4096, "renderer": "hanashi::decision::DecisionEncoding",
            "weights_loaded": False, "forward_executed": False,
            "request_tokens": {hashlib.sha256(self.body).hexdigest(): {
                "input_tokens": 23, "token_ids_sha256": "a" * 64}},
            "overflow_control": {"request_body_sha256": "b" * 64, "input_tokens": 4097,
                                 "token_ids_sha256": "c" * 64}}
        self.prep_path = self.root / "preparation.json"
        self.prep_path.write_text(json.dumps(self.prep))
        self.session_path = self.root / "session.json"
        self.path = self.root / "profile.json"
        self.session = {"schema_version": "deposium.uzu-model-session/v1",
            "model": {"repo_id": uzu.PACK_REPO, "revision": uzu.PACK_REVISION,
                "alias": "local/fixture-pack", "path": str(self.pack),
                "assets_manifest": str(self.assets_path), "assets_sha256": local.digest(self.assets_path)},
            "runtime": {"repository": uzu.REPOSITORY, "revision": uzu.UZU_REVISION,
                        "binary": str(self.binary), "sha256": local.digest(self.binary)},
            "preparation": {"path": str(self.prep_path), "sha256": local.digest(self.prep_path)},
            "endpoint": "http://127.0.0.1:11439/v1/systemone", "max_rss_mb": 14336,
            "settings": {"client_max_tokens": 4096, "concurrency": 1, "questions_per_call": 1,
                         "implicit_acquisition": False},
            "pid": 987654, "supervisor": {"pid": os.getpid(), "path": str(self.supervisor),
                                         "sha256": local.digest(self.supervisor)}}
        self.profile = {"schema_version": "deposium.candidate/v1", "profile_id": "synthetic-uzu",
            "adapter": "uzu_systemone_local", "qualification": "model_isolated", "recordings": None,
            "capabilities": ["bench.context-choice"], "revision": uzu.PACK_REVISION, "timeout_seconds": 1,
            "model": {"endpoint": self.session["endpoint"], "model_id": "local/fixture-pack",
                "repo_id": uzu.PACK_REPO, "session_manifest": str(self.session_path),
                "session_sha256": "0" * 64, "credential_env": None, "max_length": 4096, "max_rss_mb": 14336}}
        self.save_session()
        self.request = {"case_id": "descriptive-case-hidden-from-model", "contract_id": "bench.context-choice",
                        "input": self.value}
        self.response = {"model": "local/fixture-pack", "answers": {"answer": {
            "type": "choice", "choice": "c1", "probabilities": {"c0": .2, "c1": .8}, "confidence": .27}},
            "usage": {"input_tokens": 23, "output_tokens": 0}}
        self.process = Mock(pid=987654)
        self.process.poll.return_value = None
        self.watcher = Mock()
        self.watcher.is_alive.return_value = True
        self.stop = threading.Event()
        self.guard = {"stop_reason": None, "rss_peak_mib": 12.0, "min_available_mib": 9000,
                      "last_observed_monotonic": time.monotonic()}

    def refresh_assets(self):
        self.assets = {"schema_version": "deposium.model-assets/v1", "repo_id": uzu.PACK_REPO,
            "revision": uzu.PACK_REVISION, "files": [{"path": name, "size": (self.pack / name).stat().st_size,
                "sha256": local.digest(self.pack / name)} for name in sorted(uzu.REQUIRED_FILES)]}
        self.assets_path.write_text(json.dumps(self.assets))

    def save_session(self):
        self.session_path.write_text(json.dumps(self.session))
        self.profile["model"]["session_sha256"] = local.digest(self.session_path)
        self.path.write_text(json.dumps(self.profile))

    @contextmanager
    def scope(self):
        self.guard["last_observed_monotonic"] = time.monotonic()
        with patch("deposium_bench.native_supervision.os.getpgid", return_value=self.process.pid), \
                native_supervision(self.path, process=self.process, watcher=self.watcher, stop=self.stop,
                                   guard=self.guard, max_rss_mb=14336, min_free_mb=8192) as scope:
            yield scope

    def adapter(self):
        result = create_adapter(self.profile, self.path)
        self.addCleanup(result.close)
        return result

    def http(self, value=None):
        return 200, json.dumps(self.response if value is None else value).encode()


class UzuAdapterTests(UzuFixture):
    def test_saved_profile_cannot_hash_pack_or_contact_service_without_live_supervision(self):
        with patch.object(local, "digest", side_effect=AssertionError("no resident-pack read")), \
                patch.object(local, "http_request", side_effect=AssertionError("no HTTP")):
            adapter = self.adapter()
            self.assertFalse(adapter.provenance["available"])
            self.assertEqual(adapter.predict(self.request)["status"], "error")

    def test_constructor_does_not_import_uzu_or_contact_service_and_prediction_reuses_projection(self):
        with self.scope(), patch.object(local, "http_request", return_value=self.http()) as http, \
                patch.dict(os.environ, {local.AUTH_ENV: "synthetic-must-not-be-forwarded"}):
            adapter = self.adapter()
            self.assertTrue(adapter.provenance["available"])
            http.assert_not_called()
            result = adapter.predict(self.request)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"], {"choice_id": "semantic-second"})
        self.assertEqual(http.call_args.args[3], self.body)
        self.assertEqual(http.call_args.args[4], "")
        self.assertNotIn(b"descriptive-case", self.body)
        self.assertNotIn(b"semantic-", self.body)
        self.assertIsNone(result["raw_output"]["forward_executed"])
        self.assertIsNone(adapter.provenance["backend_observed"])
        self.assertIsNone(adapter.provenance["token_id_live_match"])
        self.assertEqual(adapter.provenance["authentication"], "not_provided_by_uzu")

    def test_profile_parser_rejects_other_pack_revision_remote_endpoint_credentials_and_bad_limits(self):
        for top, fields in (({"revision": "a" * 40}, {}), ({"recordings": "fixture.json"}, {}),
                ({"timeout_seconds": 31}, {}), ({}, {"credential_env": local.AUTH_ENV}),
                ({}, {"repo_id": "other/pack"}), ({}, {"endpoint": "http://example.com:1234/v1/systemone"}),
                ({}, {"max_length": True})):
            profile = deepcopy(self.profile)
            profile.update(top)
            profile["model"].update(fields)
            with self.subTest(top=top, fields=fields), self.assertRaises(ValueError):
                parse_profile(json.dumps(profile).encode())
        schema = json.loads((Path(__file__).parents[1] / "schemas/candidate-v1.schema.json").read_text())
        self.assertIn("uzu_systemone_local", schema["properties"]["adapter"]["enum"])
        self.assertEqual(schema["$defs"]["uzu_systemone_model_config"]["properties"]["credential_env"], {"type": "null"})

    def test_prepared_input_is_required_and_mismatched_token_count_cannot_be_scored(self):
        with self.scope(), patch.object(local, "http_request", return_value=self.http()) as http:
            adapter = self.adapter()
            other = deepcopy(self.request)
            other["input"]["context"] += " changed"
            self.assertEqual(adapter.predict(other)["status"], "error")
            http.assert_not_called()
        with self.scope():
            native = deepcopy(self.response)
            native["usage"]["input_tokens"] = 24
            with patch.object(local, "http_request", return_value=self.http(native)):
                result = self.adapter().predict(self.request)
        self.assertEqual(result["status"], "error")
        self.assertIn("count_mismatch", result["error"])

    def test_mutated_missing_or_extra_pack_files_are_rejected_before_http(self):
        for action in ("changed", "missing", "extra"):
            file = self.pack / "tokenizer_config.json"
            original = file.read_bytes()
            if action == "changed": file.write_bytes(b"changed")
            if action == "missing": file.unlink()
            if action == "extra": (self.pack / "encoding.json").write_text("{}")
            with self.scope(), self.subTest(action=action), patch.object(local, "http_request") as http:
                self.assertFalse(self.adapter().provenance["available"])
                http.assert_not_called()
            file.write_bytes(original)
            (self.pack / "encoding.json").unlink(missing_ok=True)

    def test_changes_between_calls_include_unlisted_runtime_files(self):
        with self.scope(), patch.object(local, "http_request", return_value=self.http()) as http:
            adapter = self.adapter()
            self.assertEqual(adapter.predict(self.request)["status"], "ok")
            (self.pack / "encoding.json").write_text("{}")
            self.assertEqual(adapter.predict(self.request)["status"], "error")
            self.assertEqual(http.call_count, 1)

    def test_invalid_native_responses_and_truncation_never_become_choices(self):
        for mutation in (lambda n: n.update(model="other"),
                lambda n: n["answers"]["answer"].update(choice="unknown"),
                lambda n: n["answers"]["answer"]["probabilities"].update(c0=float("nan")),
                lambda n: n["usage"].update(truncated=True),
                lambda n: n["usage"].update(input_tokens=0),
                lambda n: n["usage"].update(output_tokens=1)):
            native = deepcopy(self.response)
            mutation(native)
            with self.scope(), self.subTest(mutation=mutation), \
                    patch.object(local, "http_request", return_value=self.http(native)):
                self.assertEqual(self.adapter().predict(self.request)["status"], "error")

    def test_uzu_overflow_is_unsupported_and_unknown_server_error_remains_error(self):
        error = {"error": {"code": "backend_error", "type": "server_error",
                           "message": "Input larger than model context size"}}
        with self.scope(), patch.object(local, "http_request", return_value=(500, json.dumps(error).encode())):
            result = self.adapter().predict(self.request)
        self.assertEqual(result["status"], "unsupported")
        self.assertIs(result["raw_output"]["forward_executed"], False)
        error["error"]["message"] = "Unknown GPU error"
        with self.scope(), patch.object(local, "http_request", return_value=(500, json.dumps(error).encode())):
            self.assertEqual(self.adapter().predict(self.request)["status"], "error")

    def test_timeout_is_retained_without_retry_or_claim_that_native_compute_stopped(self):
        with self.scope(), patch.object(local, "http_request", side_effect=TimeoutError()) as http:
            adapter = self.adapter()
            self.assertEqual(adapter.predict(self.request)["status"], "timeout")
            self.assertEqual(adapter.predict(self.request)["status"], "timeout")
            self.assertEqual(http.call_count, 1)
            self.assertIsNone(adapter.provenance["physical_forward_count"])

    def test_supervision_loss_during_response_prevents_acceptance(self):
        def response(*_):
            self.stop.set()
            return self.http()
        with self.scope(), patch.object(local, "http_request", side_effect=response):
            result = self.adapter().predict(self.request)
        self.assertEqual(result["status"], "error")

    def test_metadata_preparation_keeps_unknowns_and_other_sources_out(self):
        mutations = [lambda p: p.update(uzu_revision="a" * 40), lambda p: p.update(max_tokens=True),
            lambda p: p.update(weights_loaded=True), lambda p: p.update(forward_executed=True),
            lambda p: p.update(request_tokens={}), lambda p: p.update(renderer="Python imitation"),
            lambda p: p["overflow_control"].update(input_tokens=4096),
            lambda p: next(iter(p["request_tokens"].values())).update(input_tokens=None),
            lambda p: next(iter(p["request_tokens"].values())).update(token_ids_sha256=None)]
        for mutate in mutations:
            value = deepcopy(self.prep)
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                uzu.preparation_map(value, model_id="local/fixture-pack",
                    assets_sha256=local.digest(self.assets_path), max_tokens=4096)

    def test_pack_path_escape_duplicate_and_symlink_are_refused(self):
        for name in ("../model.safetensors", "config.json"):
            assets = deepcopy(self.assets)
            assets["files"][0]["path"] = name
            self.assets_path.write_text(json.dumps(assets))
            with self.subTest(name=name), self.assertRaises(ValueError):
                uzu.verify_pack(self.pack, self.assets_path, Mock())
        self.assets_path.write_text(json.dumps(self.assets))
        file = self.pack / "model.safetensors"
        file.unlink()
        file.symlink_to(self.binary)
        with self.assertRaises(ValueError):
            uzu.verify_pack(self.pack, self.assets_path, Mock())

    def test_legacy_profiles_are_not_accepted_as_uzu_and_rebasing_is_shared(self):
        old = deepcopy(self.profile)
        old["adapter"] = "systemone_local"
        with self.assertRaises(ValueError):
            uzu.validate_model_profile(old)
        relative = deepcopy(self.profile)
        relative["model"]["session_manifest"] = "session.json"
        path = self.root / "relative.json"
        path.write_text(json.dumps(relative))
        profile, _, _ = _prepare_profile(path)
        self.assertEqual(profile["model"]["session_manifest"], str(self.session_path))

    def test_relative_session_survives_campaign_rebasing_under_the_same_live_scope(self):
        relative = deepcopy(self.profile)
        relative["model"]["session_manifest"] = "session.json"
        self.path.write_text(json.dumps(relative))
        prepared, _, _ = _prepare_profile(self.path)
        with self.scope(), patch.object(local, "http_request", return_value=self.http()):
            adapter = create_adapter(prepared, self.path)
            self.addCleanup(adapter.close)
            self.assertTrue(adapter.provenance["available"])
            self.assertEqual(adapter.predict(self.request)["status"], "ok")

    def test_no_uzu_or_model_dependency_is_imported(self):
        import sys
        self.assertFalse(any(k == "uzu" or k.startswith("uzu.") for k in sys.modules))

    def test_pack_metadata_types_and_size_limits_fail_closed(self):
        for value in ([1], {"type": "ChatModelConfig"},
                {"type": "DecisionModelConfig", "decision": {"codes": ["same"] * 255, "temperature": True}},
                {"type": "DecisionModelConfig", "decision": {"codes": [f"c{i}" for i in range(255)],
                 "temperature": 1}, "token_codec_config": None}):
            (self.pack / "config.json").write_text(json.dumps(value))
            self.refresh_assets()
            with self.subTest(value=value), self.assertRaises(ValueError):
                uzu.verify_pack(self.pack, self.assets_path, Mock())
        self.assets["files"][0]["size"] = 1024 * 1024 + 1
        self.assets_path.write_text(json.dumps(self.assets))
        with self.assertRaisesRegex(ValueError, "asset_size_limit"):
            uzu.verify_pack(self.pack, self.assets_path, Mock())
