"""Transport tests use fake modules; real component replay is explicitly opt-in.

Run the optional local checks with DEPOSIUM_MCP_STACK_ROOT=/path/to/stack.
Nothing installs dependencies, downloads weights or starts a service.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import adapters


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridges" / "mcps-decisions.mjs"
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node is optional for offline bridge transport tests")
class BridgeTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        version = subprocess.run([NODE, "--version"], capture_output=True, text=True, check=True).stdout
        major, minor = map(int, version.strip().lstrip("v").split(".")[:2])
        if (major, minor) < (18, 19):
            raise unittest.SkipTest("Fake loader requires Node 18.19+")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.checkout = Path(self.temporary.name)
        self.write("package.json", json.dumps({"type": "module"}))
        self.package("tsx", {"dependencies": {"esbuild": "1.0.0"},
                              "exports": {"./esm/api": "./api.mjs", "./package.json": "./package.json"}})
        self.write("node_modules/tsx/api.mjs", "import { register as hook } from 'node:module'; "
                   "export function register() { hook(new URL('./loader.mjs', import.meta.url)); return () => {}; }")
        self.write("node_modules/tsx/loader.mjs", "import {readFile} from 'node:fs/promises'; "
                   "export async function load(url, ctx, next) { if(url.endsWith('.ts')) "
                   "return {format:'module',source:await readFile(new URL(url),'utf8'),shortCircuit:true}; "
                   "return next(url,ctx); }")
        platform = subprocess.run([NODE, "-p", "process.platform+'-'+process.arch"],
                                  capture_output=True, text=True, check=True).stdout.strip()
        self.platform_package = f"@esbuild/{platform}"
        self.package("esbuild", {"optionalDependencies": {self.platform_package: "1.0.0"}})
        self.package(self.platform_package)
        self.write(f"node_modules/{self.platform_package}/bin/esbuild", "offline fake binary")
        self.package("zod")
        for contract, (module, export) in adapters.CONTRACTS.items():
            self.write(module, f"export function {export}(input) {{ console.log('SECRET_DEBUG'); "
                       "if(input.fail) throw Error('SECRET_EXCEPTION'); "
                       "if(input.empty) return null; if(input.nonfinite) return {score:Infinity}; "
                       "if(input.huge) return {text:'x'.repeat(1024*1024)}; "
                       f"return {{called:{json.dumps(contract)},received:input}}; }}")

    def write(self, relative, content):
        target = self.checkout / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def package(self, name, extra=None):
        self.write(f"node_modules/{name}/package.json",
                   json.dumps({"name": name, "version": "1.0.0", **(extra or {})}))

    def invoke(self, request=None, *, raw=None, probe=False, resolve_runtime=False, expected_runtime=None):
        flags = ["--probe"] if probe else ["--resolve-runtime"] if resolve_runtime else []
        if expected_runtime is not None:
            flags = ["--expected-runtime", json.dumps(expected_runtime)]
        process = subprocess.run([NODE, str(BRIDGE), str(self.checkout), *flags],
                                 input=raw if raw is not None else json.dumps(request), text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 timeout=15, check=False, env=adapters._environment())
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertNotIn("SECRET", process.stdout + process.stderr)
        return json.loads(process.stdout)

    def request(self, contract="mcps.document-plan", input=None):
        return {"case_id": "transport-case", "contract_id": contract, "input": input or {"query": "sentinel"}}

    def test_all_contracts_call_checkout_exports_with_input_only(self):
        for contract in adapters.CONTRACTS:
            with self.subTest(contract=contract):
                request = self.request(contract, {"query": "sentinel", "context": {"active": [1, 2]}})
                response = self.invoke(request)
                self.assertEqual(response, {"status": "ok", "output": {"called": contract, "received": request["input"]},
                                            "raw_output": {"called": contract, "received": request["input"]}, "error": None})

    def test_unknown_and_inherited_contracts_are_unsupported(self):
        for contract in ("mcps.search", "__proto__", "constructor", "toString"):
            with self.subTest(contract=contract):
                self.assertEqual(self.invoke(self.request(contract))["status"], "unsupported")

    def test_annotations_at_any_input_depth_are_rejected(self):
        for key in ("gold", "annotations", "annotation", "reference_output", "expected", "expected_output",
                    "reference", "assertions", "rationale", "Gold", "EXPECTED", "Reference_Output"):
            with self.subTest(key=key):
                response = self.invoke(self.request(input={"context": [{key: {"target": "SECRET_REFERENCE"}}]}))
                self.assertEqual(response["status"], "error")
                self.assertIsNone(response["raw_output"])

    def test_full_case_and_blank_identity_are_rejected(self):
        full = {**self.request(), "gold": {"task": "catalog"}}
        blank = {**self.request(), "case_id": "  "}
        for request in (full, blank):
            self.assertEqual(self.invoke(request)["status"], "error")

    def test_nonfinite_json_input_and_output_are_rejected(self):
        raw = '{"case_id":"c","contract_id":"mcps.document-plan","input":{"value":1e400}}'
        self.assertEqual(self.invoke(raw=raw)["status"], "error")
        self.assertEqual(self.invoke(self.request(input={"nonfinite": True}))["status"], "error")

    def test_abstention_and_application_error_are_distinct(self):
        self.assertEqual(self.invoke(self.request(input={"empty": True})),
                         {"status": "abstain", "output": None, "raw_output": None, "error": None})
        self.assertEqual(self.invoke(self.request(input={"fail": True})),
                         {"status": "error", "output": None, "raw_output": None, "error": "bridge_execution_failed"})

    def test_malformed_and_oversized_requests_have_redacted_errors(self):
        for raw in ("{SECRET_INPUT", json.dumps(self.request(input={"query": "x" * (1024 * 1024)}))):
            self.assertEqual(self.invoke(raw=raw)["error"], "bridge_execution_failed")

    def test_oversized_response_is_a_redacted_error(self):
        self.assertEqual(self.invoke(self.request(input={"huge": True})),
                         {"status": "error", "output": None, "raw_output": None, "error": "bridge_execution_failed"})

    def test_probe_hashes_installed_runtime_files_and_excludes_unrelated_modules(self):
        self.write("node_modules/unrelated/secret.json", "private")
        result = self.invoke(probe=True)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["capabilities"], list(adapters.CONTRACTS))
        artifacts = result["runtime_artifacts"]
        self.assertEqual(artifacts["schema_version"], "deposium.runtime-artifacts/v1")
        self.assertEqual(set(artifacts["packages"]), {"tsx", "zod", "esbuild", self.platform_package})
        self.assertEqual(result["runtime_roots"]["packages"],
                         {name: metadata["root"] for name, metadata in artifacts["packages"].items()})
        self.assertEqual(artifacts["total_bytes"], sum(item["size"] for item in artifacts["files"]))
        self.assertGreater(len(artifacts["files"]), 4)
        for item in artifacts["files"]:
            self.assertNotIn("unrelated", item["path"])
            with Path(item["path"]).open("rb") as stream:
                self.assertEqual(item["sha256"], hashlib.file_digest(stream, "sha256").hexdigest())
            stat = Path(item["path"]).stat()
            self.assertEqual(item["mtime_ns"], str(stat.st_mtime_ns))
            self.assertEqual(item["ctime_ns"], str(stat.st_ctime_ns))

    def test_builtin_runtime_resolution_does_not_import_loader(self):
        self.write("node_modules/tsx/api.mjs", "throw new Error('SECRET_LOADER_MUST_NOT_RUN')")
        roots = self.invoke(resolve_runtime=True)
        self.assertEqual(roots["node"], str(Path(NODE).resolve()))
        self.assertEqual(set(roots["packages"]), {"tsx", "zod", "esbuild", self.platform_package})

    def test_retargeted_runtime_package_symlinks_are_rejected_before_import(self):
        for index, name in enumerate(("tsx", "zod", "esbuild", self.platform_package)):
            with self.subTest(package=name):
                link = self.checkout / "node_modules" / name
                original = self.checkout / "runtime-packages" / f"original-{index}"
                replacement = self.checkout / "runtime-packages" / f"replacement-{index}"
                original.parent.mkdir(exist_ok=True)
                link.rename(original)
                link.symlink_to(original, target_is_directory=True)
                expected = self.invoke(resolve_runtime=True)
                self.assertEqual(self.invoke(self.request(), expected_runtime=expected)["status"], "ok")
                shutil.copytree(original, replacement)
                marker = self.checkout / "unexpected-loader-import"
                if name == "tsx":
                    (replacement / "api.mjs").write_text("import { writeFileSync } from 'node:fs'; "
                        f"writeFileSync({json.dumps(str(marker))}, 'imported'); export function register() {{ return () => {{}}; }}")
                link.unlink()
                link.symlink_to(replacement, target_is_directory=True)
                self.assertEqual(self.invoke(self.request(), expected_runtime=expected)["status"], "error")
                self.assertFalse(marker.exists())
                # Restore a safe loader for the next dependency variant.
                link.unlink()
                link.symlink_to(original, target_is_directory=True)


class AdapterBoundaryTests(unittest.TestCase):
    def test_profile_declares_component_replay_without_search_or_model(self):
        profile, _ = adapters.load_profile(ROOT / "profiles" / "mcps-current.json")
        self.assertEqual(profile["qualification"], "component_replay")
        self.assertEqual(profile["capabilities"], list(adapters.CONTRACTS))
        self.assertIsNone(profile["model"])

    def test_missing_stack_and_unsupported_remain_distinct(self):
        profile, _ = adapters.load_profile(ROOT / "profiles" / "mcps-current.json")
        adapter = adapters.create_adapter(profile, ROOT / "profiles" / "mcps-current.json")
        request = {"case_id": "case", "input": {}, "contract_id": "mcps.document-plan"}
        self.assertEqual(adapter.predict(request)["status"], "missing")
        self.assertEqual(adapter.predict({**request, "contract_id": "mcps.search"})["status"], "unsupported")

    def test_environment_does_not_inherit_credentials_or_loader_configuration(self):
        with patch.dict(os.environ, {"API_KEY": "SECRET", "NODE_OPTIONS": "--import SECRET", "HOME": "/SECRET"}):
            environment = adapters._environment()
        self.assertTrue({"API_KEY", "NODE_OPTIONS", "HOME"}.isdisjoint(environment))
        self.assertEqual(environment["TSX_DISABLE_CACHE"], "1")

    def prepared_transport(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        checkout = Path(temporary.name)
        for relative, imports in adapters._IMPORTS.items():
            target = checkout / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("\n".join(f"import {{ unused }} from '{module}'" for module in sorted(imports)))
        runtime = checkout / "runtime.bin"
        runtime.write_bytes(b"initial runtime")
        stat = runtime.stat()
        profile, _ = adapters.load_profile(ROOT / "profiles" / "mcps-current.json")
        adapter = adapters.create_adapter(profile, ROOT / "profiles" / "mcps-current.json")
        adapter._failure = None
        adapter._command = ["offline-command"]
        adapter.provenance.update(component={"root": str(checkout)}, sources=adapters._source_hashes(checkout),
                                  lockfiles={}, bridge_sha256=hashlib.sha256(BRIDGE.read_bytes()).hexdigest(),
                                  runtime_artifacts={"files": [{"path": str(runtime), "size": stat.st_size,
                                      "mtime_ns": str(stat.st_mtime_ns), "ctime_ns": str(stat.st_ctime_ns),
                                      "device": str(stat.st_dev), "inode": str(stat.st_ino)}]})
        return adapter, checkout / next(iter(adapters._IMPORTS)), runtime

    def test_changed_sources_and_runtime_are_rejected_before_execution(self):
        for changed in ("source", "runtime"):
            with self.subTest(changed=changed):
                adapter, source, runtime = self.prepared_transport()
                if changed == "source":
                    source.write_text(source.read_text() + "\n// concurrent edit")
                else:
                    runtime.write_bytes(b"changed bytes")
                with patch.object(adapters, "_run") as run:
                    response = adapter.predict({"case_id": "c", "contract_id": "mcps.document-plan", "input": {}})
                run.assert_not_called()
                self.assertEqual(response["error"], "mcps_runtime_changed")

    def test_source_change_during_execution_discards_result(self):
        adapter, source, _ = self.prepared_transport()
        def execute(*args):
            source.write_text(source.read_text() + "\n// concurrent edit")
            return subprocess.CompletedProcess([], 0, json.dumps({"status": "ok", "output": {}, "raw_output": {}, "error": None}))
        with patch.object(adapters, "_run", side_effect=execute):
            response = adapter.predict({"case_id": "c", "contract_id": "mcps.document-plan", "input": {}})
        self.assertEqual(response["error"], "mcps_runtime_changed")
        self.assertIsNone(response["raw_output"])

    def test_transport_timeout_has_distinct_status(self):
        adapter, _, _ = self.prepared_transport()
        with patch.object(adapters, "_run", side_effect=subprocess.TimeoutExpired(["offline-command"], 1)):
            response = adapter.predict({"case_id": "c", "contract_id": "mcps.document-plan", "input": {}})
        self.assertEqual(response["status"], "timeout")
        self.assertEqual(response["error"], "bridge_timeout")


@unittest.skipUnless(os.environ.get("DEPOSIUM_MCP_STACK_ROOT"), "Real MCPs replay requires explicit opt-in stack root")
class RealMcpsReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile, _ = adapters.load_profile(ROOT / "profiles" / "mcps-current.json")
        cls.adapter = adapters.create_adapter(profile, ROOT / "profiles" / "mcps-current.json",
                                              os.environ["DEPOSIUM_MCP_STACK_ROOT"])
        if not cls.adapter.provenance["available"]:
            raise AssertionError(f"Explicit real replay unavailable: {cls.adapter.provenance['availability_error']}")

    def predict(self, contract, input):
        response = self.adapter.predict({"case_id": "local-probe", "contract_id": contract, "input": input})
        self.assertEqual(response["status"], "ok", response)
        return response["raw_output"]

    def test_document_plan_calls_real_normalizer(self):
        result = self.predict("mcps.document-plan", {"message": "Liste les documents", "has_documents": True})
        self.assertEqual(result["task"], "catalog")
        self.assertEqual(result["schema_version"], "chat-document-request/v1")

    def test_followup_requires_same_chat_and_complete_selection(self):
        selection = {"schema_version": "chat-document-selection/v1", "task": "stored_summaries",
                     "origin": "space_catalog", "chat_id": "chat-a", "assistant_message_id": "message-a",
                     "run_id": "run-a", "space_ids": ["space-a"], "file_ids": [1, 2], "complete": True}
        input = {"eligible": True, "context": selection, "chatId": "chat-a", "spaceIds": ["space-a"]}
        self.assertEqual(self.predict("mcps.document-followup", input)["status"], "resolved")
        self.assertEqual(self.predict("mcps.document-followup", {**input, "chatId": "other"})["status"], "clarify")

    def test_scope_dispatch_calls_real_document_source_decision(self):
        result = self.predict("mcps.scope-dispatch", {"query": "Dans mes documents", "language": "fr",
                                                     "hasDocuments": True, "activeConnectors": []})
        self.assertEqual(result["schemaVersion"], "scope-dispatch/v1")
        self.assertEqual(result["selected"], "documents")

    def test_semantic_source_respects_explicit_documents_and_unavailable_geo(self):
        input = {"query": "Analyse cette zone", "intent": "geo_analysis", "confidence": 0.9,
                 "activeConnectors": [], "hasDocuments": True}
        self.assertEqual(self.predict("mcps.semantic-source-route", {**input, "selectedValue": "documents"}),
                         {"kind": "documents", "reason": "explicit_choice"})
        self.assertEqual(self.predict("mcps.semantic-source-route", input),
                         {"kind": "none", "reason": "geo_connector_unavailable"})


if __name__ == "__main__":
    unittest.main()
