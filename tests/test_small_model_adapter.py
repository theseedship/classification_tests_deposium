"""Model-free parent checks for isolated small decision workers."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import small_model_adapter as module
from deposium_bench.choice_protocol import CONTEXT_CHOICE_CONTRACT, CONTEXT_CHOICE_PROMPT
from deposium_bench.worker_transport import wire

WORKER_FILE = Path(__file__).resolve().parents[1] / "bridges/small-decision-worker.py"
worker_spec = importlib.util.spec_from_file_location("small_model_worker_under_test", WORKER_FILE)
worker = importlib.util.module_from_spec(worker_spec)
worker_spec.loader.exec_module(worker)

VALUE = {"context": "state", "question": "choose", "options": [
    {"id": "opaque-b", "description": "Search"},
    {"id": "opaque-a", "description": "Count"}]}


def profile(mode="omni"):
    repo, revision, max_length = module.REPOS[mode]
    model = {"mode": mode, "repo_id": repo, "local_dir": "model", "source_dir": "source",
             "runtime_python": "python", "assets_manifest": "model.json",
             "source_manifest": "source.json", "runtime_lock": "runtime.lock",
             "max_length": max_length, "threads": 2, "max_rss_mb": module.rss_limit_mib(mode)}
    model["prompt_path" if mode in {"omni", "liquid3"} else "template_path"] = "prompt.json"
    return {"schema_version": "deposium.candidate/v1", "profile_id": "test-" + mode,
            "adapter": "small_model", "qualification": "model_isolated",
            "capabilities": [CONTEXT_CHOICE_CONTRACT], "recordings": None,
            "revision": revision, "timeout_seconds": 60 if mode == "liquid3" else 30,
            "model": model}


def prepared_fixture(root, mode="muose", missing=None):
    """Tiny local inventories exercise _prepare without model weights or runtime."""
    item = profile(mode)
    repo, revision, _ = module.REPOS[mode]
    model_names = ({"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
                    "prompt.py", "modeling_d1.py", "encoder.py", "vision.py", "audio.py"} if mode == "omni" else
                   {"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
                    "api.py", "hybrid.py", "lfm2_vl.py", "modeling_d1.py", "prompt.py", "runner.py"}
                   if mode == "liquid3" else
                   {"config.json", "model.safetensors", "vocab.json", "merges.txt"})
    source_names = ({"prompt.py", "modeling_d1.py", "encoder.py", "vision.py", "audio.py"}
                    if mode == "omni" else
                    {"api.py", "hybrid.py", "lfm2_vl.py", "modeling_d1.py", "prompt.py", "runner.py"}
                    if mode == "liquid3" else {"model.py", "decision_model.py"})
    for directory, names, manifest in (("model", model_names, "model.json"),
                                       ("source", source_names, "source.json")):
        if missing == directory:
            continue
        folder = root / directory
        folder.mkdir()
        entries = []
        for name in sorted(names):
            data = ("fixture:" + name).encode()
            (folder / name).write_bytes(data)
            entries.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
        if missing != manifest:
            (root / manifest).write_bytes(wire({"schema_version": "deposium.model-assets/v1",
                                                 "repo_id": repo, "revision": revision, "files": entries}))
    if missing != "prompt.json":
        (root / "prompt.json").write_bytes(wire(
            CONTEXT_CHOICE_PROMPT if mode in {"omni", "liquid3"} else {}))
    return item


def uninitialized(mode="omni"):
    adapter = object.__new__(module.SmallModelAdapter)
    adapter._mode = mode
    adapter._model = {"max_rss_mb": module.rss_limit_mib(mode),
                      "max_length": module.REPOS[mode][2]}
    adapter._sequence = 1
    return adapter


def omni_result():
    digest = "a" * 64
    info = {"full_input_equal": True, "markers_equal": True,
            "full_input_tokens": 65, "encoded_tokens": 65,
            "forward_count": 1, "forward_ids_equal": True,
            "forward_markers_equal": True, "actual_sha256": digest,
            "expected_sha256": digest}
    native = {"answers": {"answer": {"type": "choice", "choice": "option_001",
                                     "probabilities": {"option_000": .25, "option_001": .75}}},
              "usage": {"input_tokens": 65, "output_tokens": 0}}
    raw = {"native_result": native, "input_sha256": hashlib.sha256(wire(VALUE)).hexdigest(),
           "ordered_ids": ["opaque-b", "opaque-a"],
           "ordered_descriptions": ["Search", "Count"], "encoding_info": info,
           "forward_executed": True, "decision_ms": 6.0, "inference_ms": 5.0,
           "rss_mb": 1000.0}
    return {"sequence": 1, "status": "ok", "output": {"choice_id": "opaque-a"},
            "raw_output": raw, "error": None}


def liquid3_result():
    result = omni_result()
    digest = "a" * 64
    result["raw_output"]["encoding_info"] = {
        "full_input_tokens": 65, "expected_sha256": digest, "native_sha256": digest,
        "full_input_equal": True, "forward_count": 1,
        "model_forward_count": 1, "model_forward_ids_equal": True,
        "model_forward_sha256": digest, "altered_segment": None}
    return result


class SmallModelAdapterTests(unittest.TestCase):
    def test_worker_rejects_wrong_mode_budget_and_unexpected_paths(self):
        config = {"mode": "omni", "source_dir": "/tmp/source", "local_dir": "/tmp/model",
                  "max_length": 16384, "threads": 2, "pins": {"python": "3.12.3"}}
        worker._config(config)
        for change in ({"max_length": 512}, {"threads": 3},
                       {"source_dir": "relative"}, {"template_path": "/tmp/template"}):
            with self.subTest(change=change), self.assertRaises(worker.WorkerError):
                worker._config({**config, **change})
        modern = {**config, "mode": "modernjev", "max_length": 4096,
                  "template_path": "/tmp/template"}
        worker._config(modern)
        liquid = {**config, "mode": "liquid3", "max_length": 4096}
        worker._config(liquid)
        for change in ({"max_length": 32768}, {"template_path": "/tmp/template"}):
            with self.subTest(change=change), self.assertRaises(worker.WorkerError):
                worker._config({**liquid, **change})

    def test_all_profiles_pin_identity_and_limits(self):
        for mode in module.REPOS:
            with self.subTest(mode=mode):
                module.validate_model_profile(profile(mode))
                for key, bad in (("max_rss_mb", module.rss_limit_mib(mode) + 1), ("threads", 3),
                                 ("max_length", 1024)):
                    item = profile(mode)
                    item["model"][key] = bad
                    with self.assertRaises(ValueError):
                        module.validate_model_profile(item)
                item = profile(mode)
                item["timeout_seconds"] += 1
                with self.assertRaises(ValueError):
                    module.validate_model_profile(item)

    def test_parent_rejects_forged_native_mapping_or_forward(self):
        uninitialized()._audit(omni_result(), VALUE)
        mutations = (
            lambda r: r.update(sequence=2),
            lambda r: r["raw_output"]["encoding_info"].update(full_input_equal=False),
            lambda r: r["raw_output"]["encoding_info"].update(actual_sha256="b" * 64),
            lambda r: r["raw_output"].update(forward_executed=False),
            lambda r: r.update(output={"choice_id": "opaque-b"}),
            lambda r: r["raw_output"]["native_result"]["usage"].update(input_tokens=64),
        )
        for mutate in mutations:
            item = omni_result()
            mutate(item)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                uninitialized()._audit(item, VALUE)

    def test_liquid3_parent_checks_both_native_and_model_forward(self):
        uninitialized("liquid3")._audit(liquid3_result(), VALUE)
        mutations = (
            lambda r: r["raw_output"]["encoding_info"].update(forward_count=0),
            lambda r: r["raw_output"]["encoding_info"].update(native_sha256="b" * 64),
            lambda r: r["raw_output"]["encoding_info"].update(model_forward_count=0),
            lambda r: r["raw_output"]["encoding_info"].update(model_forward_count=2),
            lambda r: r["raw_output"]["encoding_info"].update(model_forward_ids_equal=False),
            lambda r: r["raw_output"]["encoding_info"].update(model_forward_sha256="b" * 64),
            lambda r: r["raw_output"]["native_result"]["usage"].update(input_tokens=64),
            lambda r: r.update(output={"choice_id": "opaque-b"}),
        )
        for mutate in mutations:
            result = liquid3_result()
            mutate(result)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                uninitialized("liquid3")._audit(result, VALUE)

    def test_muose_native_scores_map_only_to_supplied_ids(self):
        result = omni_result()
        result["raw_output"]["encoding_info"] = {
            "truncated": False, "max_length": 512, "tokens_per_option": [20, 21]}
        result["raw_output"]["native_result"] = {
            "scores": [-1.0, 1.0], "probabilities": [.12, .88], "selected_index": 1}
        uninitialized("muose")._audit(result, VALUE)
        bad = deepcopy(result)
        bad["raw_output"]["native_result"]["selected_index"] = 0
        with self.assertRaises(ValueError):
            uninitialized("muose")._audit(bad, VALUE)

    def test_modernjev_native_ranking_maps_description_to_opaque_id(self):
        result = omni_result()
        result["raw_output"]["encoding_info"] = {
            "truncated": False, "max_length": 4096, "candidate_batch_size": 1,
            "pair_input_ids_sha256": ["a" * 64, "b" * 64],
            "actual_input_ids_sha256": ["a" * 64, "b" * 64],
            "forward_count": 2, "forward_ids_equal": True, "forward_masks_equal": True}
        result["raw_output"]["native_result"] = {
            "predicted_label": "Count", "allowed_choices": ["Search", "Count"],
            "candidates": [{"label": "Count", "score": .8, "raw_score": 1.2, "rank": 1},
                           {"label": "Search", "score": .2, "raw_score": -.4, "rank": 2}],
            "truncated": False, "max_sequence_length": 4096, "note": "native"}
        uninitialized("modernjev")._audit(result, VALUE)
        bad = deepcopy(result)
        bad["raw_output"]["native_result"]["allowed_choices"].reverse()
        with self.assertRaises(ValueError):
            uninitialized("modernjev")._audit(bad, VALUE)
        bad = deepcopy(result)
        bad["raw_output"]["encoding_info"]["forward_masks_equal"] = False
        with self.assertRaises(ValueError):
            uninitialized("modernjev")._audit(bad, VALUE)

    def test_missing_assets_do_not_spawn_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(module.SmallModelAdapter, "_prepare", side_effect=FileNotFoundError), \
                    patch.object(module.subprocess, "Popen", side_effect=AssertionError("spawned")):
                adapter = module.SmallModelAdapter(profile(), Path(temp) / "profile.json")
            self.assertFalse(adapter.provenance["available"])
            self.assertEqual(adapter.provenance["availability_error"],
                             "small_model_assets_or_runtime_missing")

    def test_real_missing_preparation_inputs_are_missing_without_worker(self):
        for mode, missing in (("muose", "model"), ("muose", "model.json"),
                              ("muose", "source"), ("muose", "source.json"),
                              ("muose", "prompt.json"), ("omni", "prompt.json"),
                              ("liquid3", "prompt.json"), ("liquid3", "model"),
                              ("liquid3", "source.json"),
                              ("muose", "runtime.lock")):
            with self.subTest(mode=mode, missing=missing), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                item = prepared_fixture(root, mode, missing)
                with patch.object(module.subprocess, "Popen", side_effect=AssertionError("spawned")) as spawn:
                    adapter = module.SmallModelAdapter(item, root / "profile.json")
                spawn.assert_not_called()
                self.assertFalse(adapter.provenance["available"])
                self.assertEqual(adapter.provenance["availability_error"],
                                 "small_model_assets_or_runtime_missing")
                response = adapter.predict({"contract_id": CONTEXT_CHOICE_CONTRACT, "input": VALUE})
                self.assertEqual(response["status"], "missing")
                self.assertIsNone(response["output"])
                self.assertIs(response["raw_output"]["forward_executed"], False)

    def test_liquid3_requires_all_six_pinned_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            item = prepared_fixture(root, "liquid3")
            manifest = root / "source.json"
            value = json.loads(manifest.read_text())
            self.assertEqual({entry["path"] for entry in value["files"]},
                             {"api.py", "hybrid.py", "lfm2_vl.py", "modeling_d1.py",
                              "prompt.py", "runner.py"})
            (root / "source/runner.py").unlink()
            value["files"] = [entry for entry in value["files"] if entry["path"] != "runner.py"]
            manifest.write_bytes(wire(value))
            with patch.object(module.subprocess, "Popen", side_effect=AssertionError("spawned")) as spawn:
                adapter = module.SmallModelAdapter(item, root / "profile.json")
            spawn.assert_not_called()
            self.assertEqual(adapter.provenance["availability_error"],
                             "small_model_source_incomplete")

    def test_invalid_preparation_inputs_remain_errors_without_worker(self):
        for kind in ("malformed", "directory", "broken_symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                item = prepared_fixture(root, missing="model.json")
                target = root / "model.json"
                if kind == "malformed":
                    target.write_text("not json")
                elif kind == "directory":
                    target.mkdir()
                else:
                    target.symlink_to(root / "absent.json")
                with patch.object(module.subprocess, "Popen", side_effect=AssertionError("spawned")) as spawn:
                    adapter = module.SmallModelAdapter(item, root / "profile.json")
                spawn.assert_not_called()
                self.assertFalse(adapter.provenance["available"])
                self.assertEqual(adapter.provenance["availability_error"],
                                 "small_model_initialization_invalid")
                response = adapter.predict({"contract_id": CONTEXT_CHOICE_CONTRACT, "input": VALUE})
                self.assertEqual(response["status"], "error")
                self.assertIs(response["raw_output"]["forward_executed"], False)

    def test_memory_guard_before_spawn_and_during_exchange(self):
        for mode, available, floor in (("omni", 6143, 2047),
                                       ("liquid3", 22527, 4095)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                with patch.object(module.SmallModelAdapter, "_prepare"), \
                        patch.object(module.SmallModelAdapter, "_available", return_value=available), \
                        patch.object(module.subprocess, "Popen", side_effect=AssertionError("spawned")):
                    adapter = module.SmallModelAdapter(profile(mode), Path(temp) / "profile.json")
                self.assertEqual(adapter.provenance["availability_error"],
                                 "small_model_host_memory_low")
                resident = uninitialized(mode)
                resident._process = None
                resident._peak_rss_mb = 0.0
                with patch.object(module.SmallModelAdapter, "_available", return_value=floor):
                    with self.assertRaises(MemoryError):
                        resident._monitor()

    def test_liquid3_rss_guard_is_distinct_from_small_models(self):
        result = liquid3_result()
        result["raw_output"]["rss_mb"] = 18432.0
        uninitialized("liquid3")._audit(result, VALUE)
        result["raw_output"]["rss_mb"] = 18432.1
        with self.assertRaises(MemoryError):
            uninitialized("liquid3")._audit(result, VALUE)
        small = omni_result()
        small["raw_output"]["rss_mb"] = 4096.1
        with self.assertRaises(MemoryError):
            uninitialized("omni")._audit(small, VALUE)


if __name__ == "__main__":
    unittest.main()
