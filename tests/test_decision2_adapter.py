"""Offline protocol tests: no candidate imports, weights, network or inference."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from deposium_bench.choice_protocol import CONTEXT_CHOICE_PROMPT
from deposium_bench import decision2_adapter as module


FAKE_WORKER = r'''import hashlib, json, math, resource, sys, time
mode = MODE
def send(value):
    print(json.dumps(value, allow_nan=False), flush=True)
request = json.loads(sys.stdin.readline())
model_name = request['config']['repo_id'].split('/')[-1]
native_limit = 8192 if model_name == 'Decision-2.0-Kai-0.6B' else 16384
send({'status':'ready','runtime':{**request['config']['pins'],'python':sys.version.split()[0]},
      'load_ms':1.0,'rss_mb':7000.0 if mode == 'high_rss' else 10.0,'native_max_input_tokens':native_limit,
      'dtype':'float32','device':'cpu'})
for line in sys.stdin:
    request = json.loads(line)
    if mode == 'sleep': time.sleep(1)
    value = request['input']
    blob = (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    ids = [option['id'] for option in value['options']]
    probs = {'c0':0.25,'c1':0.75} if mode != 'bad_probability' else {'c0':1.25,'c1':-0.25}
    confidence = 1 + sum(p * math.log(p) for p in (0.25, 0.75)) / math.log(2)
    native = {'model':model_name,'answers':{'decision':
              {'type':'choice','choice':'c0' if mode == 'bad_choice' else 'c1',
               'probabilities':probs,'confidence':confidence}},
              'usage':{'input_tokens':40,'output_tokens':0}}
    raw = {'native_result':native,'native_tokens':40,
           'input_sha256':hashlib.sha256(blob).hexdigest(),'ordered_ids':ids,
           'encoding_info':{'tokens':40,'stateTruncated':False,'optionsTruncated':False},
           'forward_executed':True,'decision_ms':4.0,'inference_ms':3.0,'rss_mb':10.0}
    send({'sequence':request['sequence'],'status':'ok','output':{'choice_id':ids[1]},
          'raw_output':raw,'error':None})
'''


class Decision2AdapterTests(unittest.TestCase):
    def setUp(self):
        # Admission control reads /proc/meminfo: keep ordinary tests independent of the host's free RAM.
        memory = patch.object(module.Decision2Adapter, "_host_available_mb", return_value=100000)
        memory.start()
        self.addCleanup(memory.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.model = self.root / "model"
        self.model.mkdir()
        (self.model / "config.json").write_text('{}\n')
        self.prompt = self.root / "prompt.json"
        self.prompt.write_text(json.dumps(CONTEXT_CHOICE_PROMPT))
        self.lock = self.root / "runtime.lock"
        self.lock.write_text('torch==1.2.3\ntransformers==5.17.0\ntokenizers==0.23.2\nsafetensors==0.8.0\n')
        self.manifest = self.root / "assets.json"
        payload = (self.model / "config.json").read_bytes()
        self.manifest.write_text(json.dumps({
            "schema_version": "deposium.model-assets/v1", "repo_id": module.REPO_ID,
            "revision": "3594047d69f476f1d01cf84c593e213fc3a4dfe0",
            "files": [{"path": "config.json", "size": len(payload),
                       "sha256": hashlib.sha256(payload).hexdigest()}]}))
        self.worker = self.root / "worker.py"
        self.worker.write_text(FAKE_WORKER.replace("MODE", repr("ok")))
        self.profile = {"schema_version": "deposium.candidate/v1", "profile_id": "offline-decision2",
                        "adapter": "decision2", "qualification": "model_isolated",
                        "capabilities": ["bench.context-choice"], "recordings": None,
                        "revision": "3594047d69f476f1d01cf84c593e213fc3a4dfe0",
                        "timeout_seconds": 3,
                        "model": {"repo_id": module.REPO_ID, "local_dir": "model",
                                  "runtime_python": sys.executable, "assets_manifest": "assets.json",
                                  "prompt_path": "prompt.json", "runtime_lock": "runtime.lock",
                                  "max_length": 4096, "threads": 2, "max_rss_mb": 6144}}
        self.input = {"context": "Une demande en français.", "question": "Quelle action ?",
                      "options": [{"id": "private-db-id", "description": "Rechercher"},
                                  {"id": "opaque-other-id", "description": "Compter"}]}

    def adapter(self):
        with patch.object(module, "WORKER", self.worker):
            adapter = module.Decision2Adapter(self.profile, self.root / "profile.json")
        self.addCleanup(adapter.close)
        return adapter

    def test_exact_pins_and_profile_limits(self):
        self.assertEqual(module._lock_pins(self.lock.read_text())["transformers"], "5.17.0")
        for text in ('torch>=2\n', 'torch==1\ntorch==2\n', 'transformers==5.17.0\n'):
            with self.assertRaises(ValueError):
                module._lock_pins(text)
        self.profile["model"]["max_length"] = 4097
        with self.assertRaises(module.Decision2ProfileError):
            module.validate_model_profile(self.profile)

    def test_nox4_pinned_profile_and_bounded_guards(self):
        repo = module.NOX_REPO_ID
        revision, name, native_limit = module.MODELS[repo]
        self.assertEqual((revision, name, native_limit),
                         ("ae269ecf34a0b3a89026bc1afd9c995279212fad", "Decision-2.0-Nox-4B", 16384))
        self.assertEqual(module.minimum_available_mib(repo), 24576)
        self.assertEqual(module.memory_floor_mib(repo), 4096)
        profile = json.loads(json.dumps(self.profile))
        profile["model"].update(repo_id=repo, max_rss_mb=22528)
        profile.update(revision=revision, timeout_seconds=60)
        module.validate_model_profile(profile)
        for key, value in (("max_rss_mb", 22529), ("max_length", 4097), ("threads", 3)):
            changed = json.loads(json.dumps(profile))
            changed["model"][key] = value
            with self.subTest(key=key), self.assertRaises(module.Decision2ProfileError):
                module.validate_model_profile(changed)
        for key, value in (("revision", "0" * 40), ("timeout_seconds", 61)):
            changed = json.loads(json.dumps(profile))
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(module.Decision2ProfileError):
                module.validate_model_profile(changed)
        self.manifest.write_text(json.dumps({**json.loads(self.manifest.read_text()),
                                             "repo_id": repo, "revision": revision}))
        self.profile = profile
        with patch.object(module.Decision2Adapter, "_host_available_mb", return_value=24575), \
                patch.object(module.subprocess, "Popen", side_effect=AssertionError("worker spawned")):
            blocked = self.adapter()
        self.assertEqual(blocked.provenance["availability_error"], "decision2_host_memory_low")
        with patch.object(module.Decision2Adapter, "_host_available_mb", return_value=24576):
            allowed = self.adapter()
        self.assertTrue(allowed.provenance["available"])
        self.assertEqual(allowed.provenance["native_max_input_tokens"], 16384)

    def test_no_missing_weights_download_and_no_candidate_import(self):
        (self.model / "config.json").unlink()
        adapter = self.adapter()
        self.assertFalse(adapter.provenance["available"])
        self.assertEqual(adapter.predict({"contract_id": "bench.context-choice", "input": self.input})["status"], "missing")

    def test_fake_worker_opaque_choice_and_provenance(self):
        adapter = self.adapter()
        self.assertTrue(adapter.provenance["available"])
        response = adapter.predict({"contract_id": "bench.context-choice", "input": self.input})
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["output"], {"choice_id": "opaque-other-id"})
        self.assertEqual(response["raw_output"]["native_result"]["answers"]["decision"]["choice"], "c1")
        self.assertEqual(adapter.provenance["effective_max_input_tokens"], 4096)
        self.assertEqual(adapter.provenance["native_max_input_tokens"], 16384)
        self.assertEqual(adapter.provenance["transport_sha256"],
                         hashlib.sha256((Path(module.__file__).with_name("worker_transport.py")).read_bytes()).hexdigest())

    def test_close_refuses_new_prediction_and_cleans_owned_pycache(self):
        adapter = self.adapter()
        owned = adapter._pycache
        self.assertTrue(owned.is_dir())
        self.assertIn("-B", adapter._process.args)
        self.assertIn(f"pycache_prefix={owned}", adapter._process.args)
        adapter.close()
        self.assertFalse(owned.exists())
        response = adapter.predict({"contract_id": "bench.context-choice", "input": self.input})
        self.assertEqual((response["status"], response["error"]), ("error", "decision2_adapter_closed"))

    def test_original_failure_takes_priority_after_close(self):
        self.worker.write_text(FAKE_WORKER.replace("MODE", repr("bad_probability")))
        adapter = self.adapter()
        request = {"contract_id": "bench.context-choice", "input": self.input}
        first = adapter.predict(request)
        adapter.close()
        again = adapter.predict(request)
        self.assertEqual(again["error"], first["error"])
        self.assertTrue(again["raw_output"]["cached_failure"])

    def test_bad_native_probability_fails_closed(self):
        self.worker.write_text(FAKE_WORKER.replace("MODE", repr("bad_probability")))
        adapter = self.adapter()
        response = adapter.predict({"contract_id": "bench.context-choice", "input": self.input})
        self.assertEqual((response["status"], response["error"]),
                         ("error", "decision2_runtime_or_protocol_changed"))
        self.assertFalse(adapter.provenance["available"])

    def test_choice_must_agree_with_probability_argmax(self):
        self.worker.write_text(FAKE_WORKER.replace("MODE", repr("bad_choice")))
        adapter = self.adapter()
        response = adapter.predict({"contract_id": "bench.context-choice", "input": self.input})
        self.assertEqual(response["status"], "error")

    def test_worker_timeout_and_reported_rss_close_process(self):
        for mode, expected in (("sleep", "decision2_inference_timeout"),
                               ("high_rss", "decision2_rss_limit")):
            self.worker.write_text(FAKE_WORKER.replace("MODE", repr(mode)))
            self.profile["timeout_seconds"] = 0.08
            adapter = self.adapter()
            if mode == "sleep":
                response = adapter.predict({"contract_id": "bench.context-choice", "input": self.input})
                self.assertEqual(response["error"], expected)
            else:
                self.assertEqual(adapter.provenance["availability_error"], expected)
            self.assertFalse(adapter.provenance["available"])

    def test_host_memory_gate_runs_before_worker_spawn(self):
        with patch.object(module, "WORKER", self.worker), \
                patch.object(module.Decision2Adapter, "_host_available_mb", return_value=7167), \
                patch.object(module.subprocess, "Popen", side_effect=AssertionError("worker spawned")):
            adapter = module.Decision2Adapter(self.profile, self.root / "profile.json")
        self.addCleanup(adapter.close)
        self.assertFalse(adapter.provenance["available"])
        self.assertEqual(adapter.provenance["availability_error"], "decision2_host_memory_low")
        with patch.object(module, "WORKER", self.worker), \
                patch.object(module.Decision2Adapter, "_host_available_mb", return_value=7168):
            allowed = module.Decision2Adapter(self.profile, self.root / "profile.json")
        self.addCleanup(allowed.close)
        self.assertTrue(allowed.provenance["available"])

    def test_loaded_worker_memory_is_not_counted_twice(self):
        # After load the worker is already out of MemAvailable: only the 1 GiB floor applies.
        available = [8000]
        with patch.object(module, "WORKER", self.worker), patch.object(
                module.Decision2Adapter, "_host_available_mb", side_effect=lambda: available[0]):
            adapter = module.Decision2Adapter(self.profile, self.root / "profile.json")
            self.addCleanup(adapter.close)
            self.assertTrue(adapter.provenance["available"])
            adapter._peak_rss_mb = 3525  # real archive: the model is resident, yet 1500 MiB stay available
            available[0] = 1500
            response = adapter.predict({"contract_id": "bench.context-choice", "input": self.input})
            self.assertEqual(response["status"], "ok")
            available[0] = 1023
            response = adapter.predict({"contract_id": "bench.context-choice", "input": self.input})
        self.assertEqual((response["status"], response["error"]), ("error", "decision2_host_memory_low"))

    def test_cached_failure_is_marked_and_first_failure_is_not(self):
        self.worker.write_text(FAKE_WORKER.replace("MODE", repr("bad_probability")))
        adapter = self.adapter()
        request = {"contract_id": "bench.context-choice", "input": self.input}
        first, second = adapter.predict(request), adapter.predict(request)
        self.assertEqual(first["error"], second["error"])
        self.assertIsNone(first["raw_output"])
        self.assertEqual(second["raw_output"], {"forward_executed": False, "cached_failure": True})

    def test_oversized_request_is_refused_for_that_case_only(self):
        adapter = self.adapter()
        huge = {**self.input, "context": "x" * (module.MAX_LINE + 1)}
        refused = adapter.predict({"contract_id": "bench.context-choice", "input": huge})
        self.assertEqual((refused["status"], refused["error"]), ("unsupported", "decision2_request_too_large"))
        self.assertFalse(refused["raw_output"]["forward_executed"])
        self.assertTrue(adapter.provenance["available"])
        later = adapter.predict({"contract_id": "bench.context-choice", "input": self.input})
        self.assertEqual(later["status"], "ok")

    def test_official_encode_preflight_overflow_never_forwards(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("decision2_worker_test", root / "bridges/decision2-worker.py")
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        infer = types.ModuleType("decision2._vendor.dev2model.infer")
        infer.question_to_row = lambda *_: {"id": "request/decision"}
        dm = types.ModuleType("decision2._vendor.dev2model.decision_model")
        dm.encode = lambda *_: {"ids": list(range(4097))}
        dm.collate = lambda *_: self.fail("collate must not run after overflow")
        class NoForward:
            max_input_tokens = 16384
            backend = types.SimpleNamespace(tokenizer=object())
            def system_one(self, **_kwargs):
                raise AssertionError("forward must not run")
        fake = {"decision2": types.ModuleType("decision2"),
                "decision2._vendor": types.ModuleType("decision2._vendor"),
                "decision2._vendor.dev2model": types.ModuleType("decision2._vendor.dev2model"),
                infer.__name__: infer, dm.__name__: dm}
        with patch.dict(sys.modules, fake), patch.object(worker, "_host_available_mb", return_value=100000), \
                patch.object(worker, "_rss", return_value=10):
            result = worker._predict(NoForward(), self.input, 4096)
        self.assertEqual((result["status"], result["error"]), ("unsupported", "decision2_context_overflow"))
        self.assertFalse(result["raw_output"]["forward_executed"])

    def test_asset_mutation_fails_closed(self):
        adapter = self.adapter()
        (self.model / "config.json").write_text('{"changed":true}\n')
        response = adapter.predict({"contract_id": "bench.context-choice", "input": self.input})
        self.assertEqual(response["status"], "error")
        self.assertFalse(adapter.provenance["available"])

    def test_new_asset_and_symlink_fail_closed(self):
        for kind in ("new_file", "symlink"):
            adapter = self.adapter()
            extra = self.model / "extra.py"
            if kind == "new_file":
                extra.write_text("x = 1\n")
            else:
                extra.symlink_to(self.model / "config.json")
            response = adapter.predict({"contract_id": "bench.context-choice", "input": self.input})
            self.assertEqual(response["status"], "error")
            self.assertFalse(adapter.provenance["available"])
            extra.unlink()


if __name__ == "__main__":
    unittest.main()
