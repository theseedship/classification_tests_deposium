"""Offline Vela3-fast transport guards; no weights, third-party imports or GPU."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from deposium_bench import vela3_fast_adapter as module
from deposium_bench.adapters import parse_profile
from deposium_bench.campaigns import _prepare_profile
from deposium_bench.choice_protocol import CONTEXT_CHOICE_CONTRACT
from deposium_bench.worker_transport import wire

INPUT = {"context": "Visible text.", "question": "Which action?",
         "options": [{"id": "opaque-b", "description": "Search"},
                     {"id": "opaque-a", "description": "Count"}]}


def profile():
    return {"schema_version": "deposium.candidate/v1", "profile_id": "test-vela3_fast",
            "adapter": "vela3_fast", "qualification": "model_isolated",
            "capabilities": [CONTEXT_CHOICE_CONTRACT], "recordings": None,
            "revision": module.REVISION, "timeout_seconds": 30,
            "model": {"repo_id": module.REPO_ID,
                      "local_dir": "model", "runtime_python": "python",
                      "assets_manifest": "model.json",
                      "prompt_path": "prompt.json", "runtime_lock": "runtime.lock",
                      "max_length": 4096, "threads": 2, "max_rss_mb": 8192,
                      "min_free_mb": 8192, "device": "cpu", "dtype": "float32", "backend": "sdpa"}}


def response(value=INPUT):
    probabilities = {"Count": 0.75, "Search": 0.25}  # JSON object order is not option order.
    digest = "a" * 64
    info = {"tokens": 14, "full_input_tokens": 14, "encoded_tokens": 14,
            "context_tokens": 10, "label_tokens": 4, "truncated": False,
            "reserved_marker": False, "context_complete": True,
            "forward_count": 1, "forward_ids_equal": True, "forward_masks_equal": True,
            "expected_sha256": digest, "actual_sha256": digest}
    native = [{"decision": {"type": "choice", "choice": "Count", "probabilities": probabilities}}, 14]
    raw = {"native_result": native, "probabilities": probabilities,
           "input_sha256": hashlib.sha256(wire(value)).hexdigest(),
           "ordered_ids": [o["id"] for o in value["options"]],
           "ordered_descriptions": [o["description"] for o in value["options"]],
           "encoding_info": info, "forward_executed": True, "decision_ms": 6.0,
           "inference_ms": 5.0, "rss_mb": 1000.0, "gpu_allocated_mb": 0.0}
    return {"sequence": 1, "status": "ok", "output": {"choice_id": "opaque-a"},
            "raw_output": raw, "error": None}


def uninitialized():
    adapter = object.__new__(module.Vela3FastAdapter)
    adapter._model = profile()["model"]
    adapter._sequence = 1
    adapter._peak_rss_mb = 0.0
    adapter._peak_gpu_allocated_mb = 0.0
    adapter.provenance = {}
    return adapter


class Vela3FastAdapterTests(unittest.TestCase):
    def test_profile_enforces_pins_budgets_and_shared_parser(self):
        value = profile()
        module.validate_model_profile(value)
        parsed, _ = parse_profile(wire(value))
        self.assertEqual(parsed, value)
        for key, bad in (("max_length", 8192), ("max_rss_mb", 10000), ("min_free_mb", 0),
                         ("threads", True), ("device", "auto"), ("dtype", "bfloat16"),
                         ("backend", "eager"), ("repo_id", "unknown/model")):
            value = profile()
            value["model"][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.validate_model_profile(value)
        value = profile()
        value["revision"] = "0" * 40
        with self.assertRaises(ValueError):
            module.validate_model_profile(value)
        value = profile()
        value["timeout_seconds"] = 31
        with self.assertRaises(ValueError):
            module.validate_model_profile(value)

    def test_profile_paths_are_archived_absolute_without_resolving_venv_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "python").symlink_to("base-python")
            path = root / "candidate.json"
            path.write_bytes(wire(profile()))
            prepared, _, _ = _prepare_profile(path)
            for field in module.PATH_FIELDS:
                self.assertEqual(prepared["model"][field], str(root / profile()["model"][field]))
            self.assertTrue(prepared["model"]["runtime_python"].endswith("/python"))

    def test_native_audit_accepts_opaque_mapping_and_unordered_probability_object(self):
        adapter = uninitialized()
        adapter._audit(response(), INPUT)
        self.assertEqual(adapter.provenance["peak_gpu_allocated_mb"], 0)
        self.assertEqual(adapter.provenance["peak_rss_mb"], 1000)

    def test_native_audit_rejects_empty_forged_truncated_and_wrong_choice(self):
        mutations = (
            lambda r: r.update(sequence=2),
            lambda r: r["raw_output"].update(input_sha256="f" * 64),
            lambda r: r["raw_output"].update(ordered_ids=["opaque-a", "opaque-b"]),
            lambda r: r["raw_output"].update(forward_executed=False),
            lambda r: r["raw_output"]["encoding_info"].update(truncated=True),
            lambda r: r["raw_output"]["encoding_info"].update(context_complete=False),
            lambda r: r["raw_output"]["encoding_info"].update(forward_ids_equal=False),
            lambda r: r["raw_output"]["encoding_info"].update(actual_sha256="b" * 64),
            lambda r: r["raw_output"]["encoding_info"].update(full_input_tokens=15),
            lambda r: r["raw_output"].update(probabilities={}),
            lambda r: r["raw_output"].update(native_result=[]),
            lambda r: r["raw_output"]["probabilities"].update(Count=0.40),
            lambda r: r["raw_output"]["probabilities"].update(Count=float("nan")),
            lambda r: r.update(output={"choice_id": "opaque-b"}),
        )
        for mutate in mutations:
            value = response()
            mutate(value)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                uninitialized()._audit(value, INPUT)

    def test_overflow_requires_explained_loss_and_zero_forward(self):
        value = response()
        value.update(status="unsupported", output=None, error="vela3_fast_context_overflow")
        value["raw_output"].update(native_result=None, probabilities=None,
                                  forward_executed=False, inference_ms=None)
        value["raw_output"]["encoding_info"].update(full_input_tokens=5000, truncated=True,
            context_complete=False, forward_count=0, actual_sha256=None,
            forward_ids_equal=False, forward_masks_equal=False)
        uninitialized()._audit(value, INPUT)
        for mutate in (lambda r: r["raw_output"].update(forward_executed=True),
                       lambda r: r["raw_output"]["encoding_info"].update(forward_count=1),
                       lambda r: r["raw_output"].update(native_result=[{}])):
            forged = deepcopy(value)
            mutate(forged)
            with self.assertRaises(ValueError):
                uninitialized()._audit(forged, INPUT)
        value["raw_output"]["encoding_info"].update(full_input_tokens=14, truncated=False,
                                                     context_complete=True)
        with self.assertRaises(ValueError):
            uninitialized()._audit(value, INPUT)

    def test_pre_encoding_error_is_distinct_from_unsupported(self):
        value = response()
        value.update(status="error", output=None, error="vela3_fast_encoding_failed")
        value["raw_output"].update(native_result=None, probabilities=None, encoding_info=None,
                                  forward_executed=False, inference_ms=None)
        uninitialized()._audit(value, INPUT)
        value["status"] = "unsupported"
        with self.assertRaises(ValueError):
            uninitialized()._audit(value, INPUT)

    def test_admission_precedes_weight_reads_and_worker_start(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(module.Vela3FastAdapter, "_remember", return_value="a" * 64), \
                    patch.object(module.Vela3FastAdapter, "_available", return_value=16383), \
                    patch.object(module.Vela3FastAdapter, "_prepare", side_effect=AssertionError("weights read")) as prepare, \
                    patch.object(module.subprocess, "Popen") as start:
                adapter = module.Vela3FastAdapter(profile(), Path(root) / "profile.json")
            self.assertEqual(adapter.provenance["availability_error"], "vela3_fast_host_memory_low_before_hash")
            prepare.assert_not_called()
            start.assert_not_called()
        with tempfile.TemporaryDirectory() as root:
            with patch.object(module.Vela3FastAdapter, "_remember", return_value="a" * 64), \
                    patch.object(module.Vela3FastAdapter, "_available", side_effect=[50000, 8191]), \
                    patch.object(module.Vela3FastAdapter, "_prepare"), \
                    patch.object(module.subprocess, "Popen") as start:
                adapter = module.Vela3FastAdapter(profile(), Path(root) / "profile.json")
            self.assertEqual(adapter.provenance["availability_error"], "vela3_fast_host_memory_low_after_hash")
            start.assert_not_called()

    def test_monitor_tracks_only_owned_group_rss_and_host_reserve(self):
        adapter = uninitialized()
        adapter._process = types.SimpleNamespace(pid=23456)
        adapter._last_monitor = 0
        adapter._stderr_path = None
        with patch.object(module, "process_group_rss_mib", return_value=8193) as rss, \
                patch.object(module.time, "monotonic", return_value=1.0), \
                patch.object(adapter, "_available", return_value=50000):
            with self.assertRaisesRegex(MemoryError, "rss_limit"):
                adapter._monitor()
            rss.assert_called_once_with(23456)
        adapter._last_monitor = 0
        adapter._peak_rss_mb = 0
        with patch.object(module, "process_group_rss_mib", return_value=100), \
                patch.object(module.time, "monotonic", return_value=2.0), \
                patch.object(adapter, "_available", return_value=8191):
            with self.assertRaisesRegex(MemoryError, "host_memory_low"):
                adapter._monitor()
        with self.assertRaisesRegex(ValueError, "cpu_gpu_allocation_invalid"):
            adapter._check_reported_resources({"rss_mb": 10, "gpu_allocated_mb": 1})
        with self.assertRaisesRegex(MemoryError, "rss_limit"):
            adapter._check_reported_resources({"rss_mb": 8193, "gpu_allocated_mb": 0})

    def test_asset_mutation_and_added_files_fail_guard_without_forward(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            asset = root / "weight"
            asset.write_bytes(b"original")
            adapter = uninitialized()
            adapter._states = {}
            adapter._inventories = {root: {"weight"}}
            adapter._remember(asset)
            adapter._monitor = lambda: None
            adapter._guard()
            asset.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "assets_changed"):
                adapter._guard()
            adapter._states = {}
            (root / "unexpected").write_bytes(b"new")
            with self.assertRaisesRegex(ValueError, "inventory_changed"):
                adapter._guard()

    def test_protocol_failure_closes_worker_and_caches_failure(self):
        adapter = uninitialized()
        adapter._sequence = 0
        adapter._profile = {"timeout_seconds": 1}
        adapter._failure = None
        adapter._closed = False
        adapter._process = types.SimpleNamespace()
        adapter._guard = lambda: None
        adapter.close = Mock()
        wrong = response()
        wrong["sequence"] = 99
        request = {"contract_id": CONTEXT_CHOICE_CONTRACT, "input": INPUT}
        with patch.object(module, "exchange", return_value=wrong) as exchange:
            first = adapter.predict(request)
            second = adapter.predict(request)
        self.assertEqual(first["error"], "vela3_fast_worker_protocol_invalid")
        self.assertEqual(second["raw_output"], {"forward_executed": False, "cached_failure": True})
        self.assertEqual(exchange.call_count, 1)
        adapter.close.assert_called_once()

    def test_close_reaps_owned_process_after_forced_kill(self):
        adapter = uninitialized()
        worker = Mock(pid=23456, stdin=Mock(), stdout=Mock())
        worker.wait.side_effect = [subprocess.TimeoutExpired("worker", 10), 0]
        adapter._process = worker
        adapter._cache = Mock()
        cache = adapter._cache
        with patch.object(module.os, "killpg") as kill:
            adapter.close()
        self.assertEqual([call.args[0] for call in kill.call_args_list], [23456, 23456])
        self.assertEqual(worker.wait.call_count, 2)
        worker.stdin.close.assert_called_once()
        worker.stdout.close.assert_called_once()
        cache.cleanup.assert_called_once()
        self.assertIsNone(adapter._process)

    def test_bundle_rejects_digest_mismatch_traversal_and_unlisted_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / "assets"
            assets.mkdir()
            (assets / "weight").write_bytes(b"weights")
            manifest = {"schema_version": "deposium.model-assets/v1", "repo_id": module.REPO_ID,
                        "revision": module.REVISION, "files": [{"path": "weight", "size": 7,
                        "sha256": hashlib.sha256(b"weights").hexdigest()}]}
            manifest_path = root / "manifest.json"
            adapter = uninitialized()
            adapter._paths = {"local_dir": assets, "assets_manifest": manifest_path}
            for change, expected in ((lambda m: m["files"][0].update(sha256="f" * 64), "hash_mismatch"),
                                     (lambda m: m["files"][0].update(path="../weight"), "path_invalid")):
                altered = deepcopy(manifest)
                change(altered)
                manifest_path.write_bytes(wire(altered))
                adapter._states, adapter._inventories = {}, {}
                with self.assertRaisesRegex(ValueError, expected):
                    adapter._bundle("local_dir", "assets_manifest", module.REPO_ID, module.REVISION,
                                    module.time.monotonic() + 5)
            manifest_path.write_bytes(wire(manifest))
            (assets / "unlisted").write_bytes(b"extra")
            with self.assertRaisesRegex(ValueError, "inventory_changed"):
                adapter._bundle("local_dir", "assets_manifest", module.REPO_ID, module.REVISION,
                                module.time.monotonic() + 5)

    def test_only_pinned_official_helpers_and_single_backbone_weights_are_admitted(self):
        files = [{"path": name, "size": 1, "sha256": digest}
                 for name, digest in module.OFFICIAL_HELPERS.items()]
        files += [{"path": name, "size": 1, "sha256": digest}
                  for name, digest in module.OFFICIAL_METADATA.items()]
        files += [{"path": "model.safetensors", "size": module.WEIGHT_SIZE, "sha256": module.WEIGHT_SHA256}]
        manifest = {"schema_version": "deposium.model-assets/v1", "repo_id": module.REPO_ID,
                    "revision": module.REVISION, "files": files}
        module.Vela3FastAdapter._asset_identity(manifest)
        changes = (
            lambda m: m["files"][-1].update(sha256="b" * 64),
            lambda m: m["files"][-1].update(size=1),
            lambda m: m["files"][0].update(sha256="b" * 64),
            lambda m: next(item for item in m["files"] if item["path"] == "config.json").update(sha256="b" * 64),
            lambda m: next(item for item in m["files"] if item["path"] == "tokenizer.json").update(sha256="b" * 64),
            lambda m: next(item for item in m["files"] if item["path"] == "tokenizer_config.json").update(sha256="b" * 64),
            lambda m: m["files"].append({"path": "span_head.safetensors", "size": 1, "sha256": "b" * 64}),
            lambda m: m["files"].append({"path": "torch.py", "size": 1, "sha256": "b" * 64}),
            lambda m: m["files"].append({"path": "pytorch_model.bin", "size": 1, "sha256": "b" * 64}),
        )
        for change in changes:
            altered = deepcopy(manifest)
            change(altered)
            adapter = uninitialized()
            adapter._paths = {"assets_manifest": Path("not-read-by-test")}
            with self.subTest(change=change), \
                    patch.object(adapter, "_read", return_value=(wire(altered), "a" * 64)), \
                    patch.object(adapter, "_bundle", side_effect=AssertionError("weights must not be hashed")) as bundle:
                with self.assertRaises(ValueError):
                    adapter._prepare(module.time.monotonic() + 5)
                bundle.assert_not_called()

    def test_mastra_fresh_worker_admission_uses_native_snapshot_and_full_reserve(self):
        from deposium_bench import mastra_observation as observation
        from deposium_bench import native_resources
        for available in (16383, 16384):
            with self.subTest(available=available), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path = root / "profile.json"
                path.write_bytes(wire(profile()))
                output = root / "campaign"
                with patch.object(native_resources, "memory_snapshot", return_value={"MemAvailable_mib": available}) as native, \
                        patch.object(observation, "memory_snapshot", side_effect=AssertionError("Linux-only snapshot")), \
                        patch.object(observation, "create_adapter") as factory, \
                        patch.object(observation, "_stack_context", side_effect=RuntimeError("past admission")) as stack:
                    error = ValueError if available < 16384 else RuntimeError
                    message = "available RAM" if available < 16384 else "past admission"
                    with self.assertRaisesRegex(error, message):
                        observation.observe_local(observation.DATASET, path, output)
                native.assert_called_once()
                self.assertEqual(stack.call_count, int(available == 16384))
                factory.assert_not_called()
                self.assertFalse(output.exists())

    def _generated_campaign_manifest(self, initialization="ready"):
        """Exercise the real adapter, asset checks and campaign writer with fake IPC."""
        from deposium_bench import campaigns
        from deposium_bench.cases import load_cases
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            value = profile()
            data = b"synthetic asset, never imported or executed"
            digest = hashlib.sha256(data).hexdigest()
            model_paths = {"config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors", *module.OFFICIAL_HELPERS}
            inventory = []
            for name in sorted(model_paths):
                asset = root / "model" / name
                asset.parent.mkdir(parents=True, exist_ok=True)
                asset.write_bytes(data)
                inventory.append({"path": name, "size": len(data), "sha256": digest})
            (root / "model.json").write_bytes(wire({"schema_version": "deposium.model-assets/v1",
                "repo_id": module.REPO_ID, "revision": module.REVISION, "files": inventory}))
            if initialization == "missing_assets":
                (root / "model/model.safetensors").unlink()
            (root / "python").write_bytes(b"synthetic interpreter, never executed")
            (root / "prompt.json").write_bytes(wire(module.CONTEXT_CHOICE_PROMPT))
            pins = {"python": "3.12.12", "numpy": "2.4.5", "torch": "2.14.0", "transformers": "5.17.0",
                    "tokenizers": "0.23.3", "safetensors": "0.8.0"}
            (root / "runtime.lock").write_text("".join(f"{name}=={version}\n" for name, version in pins.items()))
            profile_path = root / "profile.json"
            profile_path.write_bytes(wire(value))
            case = deepcopy(load_cases(module.ROOT / "datasets/context-choice-v1/cases.jsonl")[0][0])
            dataset = root / "cases.jsonl"
            dataset.write_bytes(wire(case))
            worker = Mock(pid=23456, stdin=Mock(), stdout=Mock())
            worker.wait.return_value = 0

            def fake_exchange(_process, message, **_kwargs):
                if message["op"] == "initialize":
                    if initialization == "backend_failure":
                        return {"status": "error", "error": "vela3_fast_backend_unavailable"}
                    return {"status": "ready", "runtime": {**pins, "python": "3.12.12"},
                            "load_ms": 1.0, "rss_mb": 100.0, "gpu_allocated_mb": 0.0,
                            "max_length": 4096, "dtype": "float32", "device": "cpu", "backend": "sdpa"}
                result = response(message["input"])
                probabilities = {option["description"]: float(index == 0)
                                 for index, option in enumerate(message["input"]["options"])}
                result["raw_output"].update(native_result=[{"decision": {
                    "type": "choice", "choice": message["input"]["options"][0]["description"],
                    "probabilities": probabilities}}, 14], probabilities=probabilities)
                result["output"] = {"choice_id": message["input"]["options"][0]["id"]}
                result["sequence"] = message["sequence"]
                return result

            source_fingerprint = campaigns._source_fingerprint()
            with patch.object(module, "WEIGHT_SIZE", len(data)), \
                    patch.object(module, "WEIGHT_SHA256", digest), \
                    patch.object(module, "OFFICIAL_HELPERS", {name: digest for name in module.OFFICIAL_HELPERS}), \
                    patch.object(module, "OFFICIAL_METADATA", {name: digest for name in module.OFFICIAL_METADATA}), \
                    patch.object(campaigns, "_source_fingerprint", return_value=source_fingerprint), \
                    patch.object(module.Vela3FastAdapter, "_available", return_value=50000), \
                    patch.object(module, "process_group_rss_mib", return_value=100.0), \
                    patch.object(module.subprocess, "Popen", return_value=worker) as start, \
                    patch.object(module.os, "set_blocking"), patch.object(module.os, "killpg"), \
                    patch.object(module, "exchange", side_effect=fake_exchange):
                summary = campaigns.run_campaign(dataset, profile_path, root / "campaign")
            self.assertEqual(summary["completion_status"], "complete")
            self.assertEqual(start.call_count, int(initialization != "missing_assets"))
            manifest = json.loads((root / "campaign/manifest.json").read_bytes())
            provenance = manifest["adapter_provenance"]
            self.assertEqual(provenance["available"], initialization == "ready")
            return manifest

    def _campaign_schema_validator(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("optional schema validator not installed")
        schema = json.loads((module.ROOT / "schemas/campaign-v1.schema.json").read_bytes())
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema), schema

    def test_campaign_schema_accepts_actual_adapter_ready_manifest_with_cpu_resources(self):
        validator, schema = self._campaign_schema_validator()
        manifest = self._generated_campaign_manifest()
        validator.validate(manifest)
        provenance = manifest["adapter_provenance"]
        self.assertEqual((provenance["device"], provenance["dtype"], provenance["backend"]),
                         ("cpu", "float32", "sdpa"))
        self.assertEqual(provenance["load_gpu_allocated_mb"], 0)
        self.assertGreaterEqual(provenance["min_observed_available_mb"], 8192)
        # The frozen transport checks this separate GPU counter against the
        # same numeric ceiling; this does not turn RSS into total unified RAM.
        large_gpu_observation = deepcopy(manifest)
        large_gpu_observation["adapter_provenance"].update(
            load_gpu_allocated_mb=10000, peak_gpu_allocated_mb=10000)
        self.assertTrue(list(validator.iter_errors(large_gpu_observation)))
        candidate = json.loads((module.ROOT / "schemas/candidate-v1.schema.json").read_bytes())
        self.assertEqual(schema["$defs"]["vela3_fast_model_config"],
                         candidate["$defs"]["vela3_fast_model_config"])

    def test_campaign_schema_accepts_real_adapter_backend_and_asset_initialization_failures(self):
        validator, _ = self._campaign_schema_validator()
        for reason, code in (("backend_failure", "vela3_fast_backend_unavailable"),
                             ("missing_assets", "vela3_fast_assets_or_runtime_missing")):
            with self.subTest(reason=reason):
                manifest = self._generated_campaign_manifest(reason)
                validator.validate(manifest)
                provenance = manifest["adapter_provenance"]
                self.assertFalse(provenance["available"])
                self.assertEqual(provenance["availability_error"], code)
                missing_error = deepcopy(manifest)
                missing_error["adapter_provenance"].pop("availability_error")
                self.assertTrue(list(validator.iter_errors(missing_error)))
                false_success = deepcopy(manifest)
                false_success["adapter_provenance"].update(available=True)
                false_success["adapter_provenance"].pop("availability_error")
                self.assertTrue(list(validator.iter_errors(false_success)))

    def test_campaign_schema_rejects_wrong_model_pins_cpu_modes_and_unknown_fields(self):
        validator, _ = self._campaign_schema_validator()
        original = self._generated_campaign_manifest()
        changes = (
            lambda p: p.update(model_revision="0" * 40),
            lambda p: p.update(model_repo_id="unknown/model"),
            lambda p: p["model"].update(repo_id="unknown/model"),
            lambda p: p["model_assets"].update(revision="0" * 40),
            lambda p: p.update(device="mps"),
            lambda p: p.update(dtype="bfloat16"),
            lambda p: p["settings"].update(backend="eager"),
            lambda p: p["model"].update(min_free_mb=0),
            lambda p: p.update(unknown_field=True),
            lambda p: p["model"].update(unknown_field=True),
            lambda p: p["settings"].update(unknown_field=True),
            lambda p: p["model_assets"]["files"][0].update(unknown_field=True),
            lambda p: p["runtime_pins"].pop("numpy"),
            lambda p: p["runtime_pins"].update(transformers="5.19.0"),
            lambda p: p["runtime"].update(torch="0.0"),
            lambda p: p["runtime"].pop("python"),
            lambda p: p.pop("load_gpu_allocated_mb"),
            lambda p: p.update(peak_rss_mb=8193),
            lambda p: p.update(peak_gpu_allocated_mb=True),
            lambda p: p.update(min_observed_available_mb=8191),
            lambda p: p.update(availability_error="vela3_fast_fake_error"),
        )
        for change in changes:
            value = deepcopy(original)
            change(value["adapter_provenance"])
            with self.subTest(change=change):
                self.assertTrue(list(validator.iter_errors(value)))
        # A failed resource guard must remain archivable, including its offending
        # observation; it is not converted into an available/successful runtime.
        resource_failure = deepcopy(original)
        resource_failure["adapter_provenance"].update(available=False,
            availability_error="vela3_fast_host_memory_low", min_observed_available_mb=8191)
        validator.validate(resource_failure)

    def test_profile_schema_matches_parser_when_jsonschema_is_available(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("optional schema validator not installed")
        schema = json.loads((module.ROOT / "schemas/candidate-v1.schema.json").read_text())
        validator = Draft202012Validator(schema)
        self.assertEqual(list(validator.iter_errors(profile())), [])
        invalid = profile()
        invalid["model"]["min_free_mb"] = 8191
        self.assertTrue(list(validator.iter_errors(invalid)))


if __name__ == "__main__":
    unittest.main()
