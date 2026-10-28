"""Resident transport checks with a temporary fake app; no real stack or model."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from deposium_bench import adapters
from deposium_bench.mcps_resident import BRIDGE, ResidentMCPAdapter

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
try:
    NODE_FIXTURE_SUPPORTED = NODE and int(subprocess.check_output([NODE, "--version"], timeout=5).decode().split(".")[0][1:]) >= 24
except (OSError, ValueError, subprocess.SubprocessError):
    NODE_FIXTURE_SUPPORTED = False


@unittest.skipUnless(NODE_FIXTURE_SUPPORTED, "Node24 is optional; fake .ts fixtures require its native type stripping")
class ResidentMCPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = json.loads((ROOT / "profiles/mcps-current.json").read_bytes())
        self.profile["adapter"] = "mcps_resident"
        self.profile["timeout_seconds"] = 2
        self.profile_path = self.root / "profile.json"
        self.profile_path.write_text(json.dumps(self.profile))
        self.app = self.root / "app"
        self.app.mkdir()
        (self.app / "package.json").write_text('{"type":"module"}')
        packages = {}
        for name in ("tsx", "esbuild", "@esbuild/linux-x64", "zod"):
            folder = self.app / "node_modules" / name
            folder.mkdir(parents=True)
            metadata = {"name": name, "version": "0.0.0"}
            if name == "tsx":
                metadata.update(type="module", exports={"./esm/api": "./api.mjs", "./package.json": "./package.json"})
                (folder / "api.mjs").write_text("export function register(){ return () => {} }\n")
            (folder / "package.json").write_text(json.dumps(metadata))
            packages[name] = {"root": str(folder), "version": "0.0.0"}
        # No tsx compilation is needed: Node24 strips the plain-JS .ts fixtures.
        for module, name in adapters.CONTRACTS.values():
            path = self.app / module
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("globalThis.importCount=(globalThis.importCount??0)+1;\n"
                            f"export async function {name}(input) {{\n"
                            " console.log('private_fixture_secret');\n"
                            " if(input.throw) throw new Error('private_fixture_secret');\n"
                            " if(input.hang) await new Promise(resolve=>setTimeout(resolve,10000));\n"
                            " if(input.empty) return null;\n"
                            " if(input.oversize) return {text:'x'.repeat(1024*1024+1)};\n"
                            " globalThis.calls=(globalThis.calls??0)+1;\n"
                            " return {task:input.task, calls:globalThis.calls, imports:globalThis.importCount};\n"
                            "}\n")
        self.delegate = Mock()
        self.delegate._failure = None
        self.delegate._command = [str(Path(NODE).resolve())]
        self.delegate._unchanged.return_value = True
        self.delegate.provenance = {
            "adapter": "mcps", "adapter_sha256": "a" * 64, "profile_sha256": "b" * 64,
            "identity_sha256": "c" * 64, "component": {"root": str(self.app), "head": "0" * 40, "dirty": False},
            "runtime_artifacts": {"packages": packages, "files": []}, "available": True,
            "qualification": "component_replay", "model": None}

    def create(self):
        with patch.object(adapters, "McpsAdapter", return_value=self.delegate):
            adapter = ResidentMCPAdapter(self.profile, self.profile_path, self.root)
        self.addCleanup(adapter.close)
        self.assertTrue(adapter.provenance["available"], adapter.provenance)
        return adapter

    @staticmethod
    def request(**data):
        return {"case_id": "case-1", "contract_id": "mcps.document-plan", "input": {"task": "catalog", **data}}

    def test_real_bridge_calls_imported_exports_in_one_resident_process(self):
        adapter = self.create()
        pid = adapter._process.pid
        first = adapter.predict(self.request())
        second = adapter.predict(self.request(task="stored_summaries"))
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["output"], {"task": "catalog", "calls": 1, "imports": 4})
        self.assertEqual(second["output"], {"task": "stored_summaries", "calls": 2, "imports": 4})
        self.assertEqual(adapter._process.pid, pid)
        self.assertEqual(first["raw_output"]["decision"], first["output"])
        self.assertGreaterEqual(first["raw_output"]["timings"]["decision_ms"], 0)
        self.assertNotIn("private_fixture_secret", json.dumps(first))
        self.assertGreaterEqual(adapter.provenance["init_wall_ms"], adapter.provenance["worker_load_ms"])
        self.assertEqual(adapter.provenance["transport"], "resident_process_jsonl")
        self.assertEqual(len(adapter.provenance["identity_sha256"]), 64)

    def test_abstention_and_function_error_are_distinct_with_timing_only_for_decisions(self):
        adapter = self.create()
        empty = adapter.predict(self.request(empty=True))
        self.assertEqual(empty["status"], "abstain")
        self.assertIsNone(empty["output"])
        self.assertIn("decision_ms", empty["raw_output"]["timings"])
        error = adapter.predict(self.request(throw=True))
        self.assertEqual(error, {"status": "error", "output": None, "raw_output": None, "error": "bridge_execution_failed"})
        self.assertNotIn("private_fixture_secret", json.dumps(error))
        self.assertEqual(adapter.predict(self.request())["status"], "ok")

    def test_unsupported_does_not_consume_sequence_or_call_application(self):
        adapter = self.create()
        unsupported = adapter.predict({**self.request(), "contract_id": "unknown"})
        self.assertEqual(unsupported["status"], "unsupported")
        self.assertEqual(adapter._sequence, 0)
        self.assertEqual(adapter.predict(self.request())["output"]["calls"], 1)

    def test_annotations_rejected_before_transport(self):
        adapter = self.create()
        with self.assertRaises(adapters.AdapterError):
            adapter.predict(self.request(nested={"gold": "private"}))
        self.assertEqual(adapter._sequence, 0)

    def test_timeout_kills_process_and_returns_stable_failure(self):
        adapter = self.create()
        adapter._timeout = .05
        process = adapter._process
        result = adapter.predict(self.request(hang=True))
        self.assertEqual(result["status"], "timeout")
        self.assertIsNone(adapter._process)
        self.assertIsNotNone(process.poll())
        self.assertEqual(adapter.predict(self.request()), result)

    def test_drift_refuses_call_and_closes_process(self):
        adapter = self.create()
        process = adapter._process
        self.delegate._unchanged.return_value = False
        self.assertEqual(adapter.predict(self.request())["status"], "error")
        self.assertIsNotNone(process.poll())
        self.assertFalse(adapter.provenance["available"])

    def test_sequence_and_malformed_timing_do_not_become_valid_decisions(self):
        for update in ({"sequence": True}, {"sequence": 2},
                       {"raw_output": {"decision": {"task": "catalog"}, "timings": {"decision_ms": True}}}):
            with self.subTest(update=update):
                adapter = self.create()
                reply = {"sequence": 1, "status": "ok", "output": {"task": "catalog"},
                         "raw_output": {"decision": {"task": "catalog"}, "timings": {"decision_ms": 1}}, "error": None}
                with patch.object(adapter, "_exchange", return_value={**reply, **update}):
                    self.assertEqual(adapter.predict(self.request())["status"], "error")
                self.assertIsNone(adapter._process)

    def test_request_and_response_limits_close_instead_of_hanging(self):
        adapter = self.create()
        with self.assertRaises(adapters.AdapterError):
            adapter.predict(self.request(text="é" * (1024 * 1024)))
        self.assertEqual(adapter._sequence, 0)
        self.assertEqual(adapter.predict(self.request())["status"], "ok")
        adapter = self.create()
        response = adapter.predict(self.request(oversize=True))
        self.assertEqual(response["status"], "error")
        self.assertIsNone(adapter._process)

    def test_close_is_idempotent_and_waits_for_exit(self):
        adapter = self.create()
        process = adapter._process
        adapter.close()
        adapter.close()
        self.assertIsNotNone(process.poll())

    def test_identity_does_not_include_initialization_measurements(self):
        first = self.create()
        second = self.create()
        self.assertEqual(first.provenance["identity_sha256"], second.provenance["identity_sha256"])
        self.assertNotEqual(first._process.pid, second._process.pid)

    def test_initialization_failure_preserves_delegate_failure_without_spawning(self):
        self.delegate._failure = adapters._envelope("missing", error="mcps_runtime_missing")
        self.delegate.provenance["available"] = False
        with patch.object(adapters, "McpsAdapter", return_value=self.delegate), \
                patch("deposium_bench.mcps_resident.subprocess.Popen", side_effect=AssertionError("no process")):
            adapter = ResidentMCPAdapter(self.profile, self.profile_path, self.root)
        self.assertEqual(adapter.predict(self.request())["status"], "missing")
        self.assertGreaterEqual(adapter.provenance["init_wall_ms"], 0)


if __name__ == "__main__":
    unittest.main()
