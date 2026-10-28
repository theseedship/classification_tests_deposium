"""Kai identity and transport checks without weights, candidate imports or inference."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import decision2_adapter
from deposium_bench.choice_protocol import CONTEXT_CHOICE_PROMPT
from tests.test_decision2_adapter import FAKE_WORKER


ROOT = Path(__file__).resolve().parents[1]
KAI_REPO = "vllm-sr/Decision-2.0-Kai-0.6B"
KAI_REVISION = "cd49ea3813fd8ba0928a9a23ef6c9a0f2f0cd764"


class Decision2KaiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.model = self.root / "model"
        self.model.mkdir()
        payload = b"{}\n"
        (self.model / "config.json").write_bytes(payload)
        (self.root / "prompt.json").write_text(json.dumps(CONTEXT_CHOICE_PROMPT))
        (self.root / "runtime.lock").write_text(
            "torch==1.2.3\ntransformers==5.17.0\ntokenizers==0.23.2\nsafetensors==0.8.0\n")
        (self.root / "assets.json").write_text(json.dumps({
            "schema_version": "deposium.model-assets/v1", "repo_id": KAI_REPO,
            "revision": KAI_REVISION,
            "files": [{"path": "config.json", "size": len(payload),
                       "sha256": hashlib.sha256(payload).hexdigest()}]}))
        self.worker = self.root / "worker.py"
        self.worker.write_text(FAKE_WORKER.replace("MODE", repr("ok")))
        self.profile = json.loads((ROOT / "profiles/decision2-kai-cpu-context.json").read_text())
        self.profile["model"].update(local_dir="model", runtime_python=sys.executable,
                                     assets_manifest="assets.json", prompt_path="prompt.json",
                                     runtime_lock="runtime.lock")
        self.value = {"context": "Une demande en français.", "question": "Quelle action ?",
                      "options": [{"id": "private-db-id", "description": "Rechercher"},
                                  {"id": "opaque-other-id", "description": "Compter"}]}

    def test_profile_pin_and_native_limit(self):
        decision2_adapter.validate_model_profile(self.profile)
        for field, value in (("revision", "3594047d69f476f1d01cf84c593e213fc3a4dfe0"),
                             ("revision", "0" * 40)):
            changed = json.loads(json.dumps(self.profile))
            changed[field] = value
            with self.assertRaises(decision2_adapter.Decision2ProfileError):
                decision2_adapter.validate_model_profile(changed)

    def test_offline_worker_audits_kai_output_and_provenance(self):
        with patch.object(decision2_adapter, "WORKER", self.worker), patch.object(
                decision2_adapter.Decision2Adapter, "_host_available_mb", return_value=100000):
            adapter = decision2_adapter.Decision2Adapter(self.profile, self.root / "profile.json")
        self.addCleanup(adapter.close)
        self.assertTrue(adapter.provenance["available"])
        self.assertEqual(adapter.provenance["model_repo_id"], KAI_REPO)
        self.assertEqual(adapter.provenance["native_max_input_tokens"], 8192)
        response = adapter.predict({"contract_id": "bench.context-choice", "input": self.value})
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["output"], {"choice_id": "opaque-other-id"})
        self.assertEqual(response["raw_output"]["native_result"]["model"], "Decision-2.0-Kai-0.6B")

    def test_cross_model_manifest_rejected_before_worker(self):
        manifest = self.root / "assets.json"
        value = json.loads(manifest.read_text())
        value["repo_id"] = decision2_adapter.REPO_ID
        manifest.write_text(json.dumps(value))
        with patch.object(decision2_adapter, "WORKER", self.worker), patch.object(
                decision2_adapter.Decision2Adapter, "_host_available_mb", return_value=100000), patch.object(
                decision2_adapter.subprocess, "Popen", side_effect=AssertionError("worker spawned")):
            adapter = decision2_adapter.Decision2Adapter(self.profile, self.root / "profile.json")
        self.addCleanup(adapter.close)
        self.assertFalse(adapter.provenance["available"])

    def test_publisher_manifest_requires_matching_kai_identity(self):
        spec = importlib.util.spec_from_file_location("decision2_worker_kai_test", ROOT / "bridges/decision2-worker.py")
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        payload = (self.model / "config.json").read_bytes()
        bundle = {"schema": "dev2-package-manifest/1", "repo_id": KAI_REPO,
                  "model_name": "Decision-2.0-Kai-0.6B", "profile": "qwen-full",
                  "max_input_tokens": 8192,
                  "files_sha256": {"config.json": hashlib.sha256(payload).hexdigest()}}
        (self.model / "MODEL_MANIFEST.json").write_text(json.dumps(bundle))
        self.assertEqual(worker._verify_bundle(self.model, KAI_REPO, KAI_REVISION), bundle)
        for field, value in (("repo_id", decision2_adapter.REPO_ID),
                             ("model_name", "Decision-2.0-Eos-0.8B"),
                             ("max_input_tokens", 16384)):
            altered = dict(bundle)
            altered[field] = value
            (self.model / "MODEL_MANIFEST.json").write_text(json.dumps(altered))
            with self.subTest(field=field), self.assertRaises(ValueError):
                worker._verify_bundle(self.model, KAI_REPO, KAI_REVISION)
        with self.assertRaises(ValueError):
            worker._verify_bundle(self.model, KAI_REPO, "0" * 40)


if __name__ == "__main__":
    unittest.main()
