"""Laya parent contract checks without weights, runtime imports or child processes."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from deposium_bench import laya_adapter as module
from deposium_bench.choice_protocol import CONTEXT_CHOICE_CONTRACT
from deposium_bench.worker_transport import wire


INPUT = {"context": "Visible text.", "question": "Which action?",
         "options": [{"id": "opaque-b", "description": "Search"},
                     {"id": "opaque-a", "description": "Count"}]}


def profile():
    return {"schema_version": "deposium.candidate/v1", "profile_id": "test-laya",
            "adapter": "laya", "qualification": "model_isolated",
            "capabilities": [CONTEXT_CHOICE_CONTRACT], "recordings": None,
            "revision": module.REVISION, "timeout_seconds": 5,
            "model": {"repo_id": module.REPO_ID, "source_revision": module.SOURCE_REVISION,
                      "local_dir": "model", "source_dir": "source", "runtime_python": "python",
                      "assets_manifest": "model.json", "source_manifest": "source.json",
                      "prompt_path": "prompt.json", "runtime_lock": "runtime.lock",
                      "max_length": 1024, "head_length": 256, "threads": 2, "max_rss_mb": 3072}}


def response(value=INPUT):
    digest = "a" * 64
    native = {"model": "laya-rl-agent",
              "answers": {"answer": {"type": "choice", "choice": "Count",
                                     "probabilities": {"Search": 0.25, "Count": 0.75}}},
              "usage": {"truncated": False, "state_tokens_dropped": 0,
                        "truncated_questions": [], "input_tokens": 14, "output_tokens": 0}}
    info = {"tokens": 14, "state_tokens": 3, "state_tokens_dropped": 0,
            "head_complete": True, "options_distinct": True, "reserved_marker": False,
            "forward_count": 1, "forward_ids_equal": True, "forward_masks_equal": True,
            "expected_sha256": digest, "actual_sha256": digest}
    raw = {"native_result": native, "input_sha256": hashlib.sha256(wire(value)).hexdigest(),
           "ordered_ids": ["opaque-b", "opaque-a"],
           "ordered_descriptions": ["Search", "Count"], "encoding_info": info,
           "forward_executed": True, "decision_ms": 6.0, "inference_ms": 5.0,
           "rss_mb": 1000.0}
    return {"sequence": 1, "status": "ok", "output": {"choice_id": "opaque-a"},
            "raw_output": raw, "error": None}


def uninitialized():
    adapter = object.__new__(module.LayaAdapter)
    adapter._model = {"max_length": 1024, "max_rss_mb": 3072}
    adapter._sequence = 1
    return adapter


class LayaAdapterTests(unittest.TestCase):
    def test_profile_pins_checkpoint_source_and_budgets(self):
        module.validate_model_profile(profile())
        for key, bad in (("head_length", 255), ("max_length", 1023),
                         ("max_rss_mb", 3073), ("threads", 3)):
            item = profile()
            item["model"][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.validate_model_profile(item)
        item = profile()
        item["revision"] = "0" * 40
        with self.assertRaises(ValueError):
            module.validate_model_profile(item)

    def test_parent_accepts_native_choice_and_rejects_forged_forward_or_mapping(self):
        uninitialized()._audit(response(), INPUT)
        mutations = (
            lambda r: r.update(sequence=2),
            lambda r: r["raw_output"]["encoding_info"].update(forward_ids_equal=False),
            lambda r: r["raw_output"]["encoding_info"].update(actual_sha256="b" * 64),
            lambda r: r["raw_output"].update(forward_executed=False),
            lambda r: r["raw_output"]["native_result"]["usage"].update(truncated=True),
            lambda r: r["raw_output"]["native_result"]["answers"]["answer"]
                ["probabilities"].update(Count=0.4),
            lambda r: r.update(output={"choice_id": "opaque-b"}),
        )
        for mutate in mutations:
            item = response()
            mutate(item)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                uninitialized()._audit(item, INPUT)

    def test_overflow_requires_no_forward_and_explained_loss(self):
        item = response()
        item.update(status="unsupported", output=None, error="laya_context_overflow")
        raw = item["raw_output"]
        raw.update(native_result=None, forward_executed=False, inference_ms=None)
        raw["encoding_info"].update(state_tokens_dropped=2, forward_count=0,
                                    forward_ids_equal=False, forward_masks_equal=False,
                                    actual_sha256=None)
        uninitialized()._audit(item, INPUT)
        forged = deepcopy(item)
        forged["raw_output"]["forward_executed"] = True
        with self.assertRaises(ValueError):
            uninitialized()._audit(forged, INPUT)

    def test_native_encoding_error_preserves_worker_error_before_forward(self):
        item = response()
        item.update(status="error", output=None, error="laya_encoding_failed")
        item["raw_output"].update(native_result=None, encoding_info=None,
                                  forward_executed=False, inference_ms=None)
        uninitialized()._audit(item, INPUT)
        forged = deepcopy(item)
        forged["raw_output"]["forward_executed"] = True
        with self.assertRaises(ValueError):
            uninitialized()._audit(forged, INPUT)

    def test_reserved_marker_unsupported_requires_visible_marker_and_no_forward(self):
        value = {**INPUT, "context": "Visible <mask> text."}
        item = response(value)
        item.update(status="unsupported", output=None, error="laya_context_overflow")
        item["raw_output"].update(native_result=None, forward_executed=False,
                                  inference_ms=None)
        item["raw_output"]["encoding_info"].update(
            reserved_marker=True, forward_count=0, forward_ids_equal=False,
            forward_masks_equal=False, actual_sha256=None)
        uninitialized()._audit(item, value)
        forged = deepcopy(item)
        forged["raw_output"]["encoding_info"]["reserved_marker"] = False
        with self.assertRaises(ValueError):
            uninitialized()._audit(forged, value)

    def test_missing_assets_do_not_spawn_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(module.LayaAdapter, "_prepare", side_effect=FileNotFoundError), \
                    patch.object(module.subprocess, "Popen", side_effect=AssertionError("spawned")):
                adapter = module.LayaAdapter(profile(), Path(temp) / "profile.json")
            self.assertFalse(adapter.provenance["available"])
            self.assertEqual(adapter.provenance["availability_error"],
                             "laya_assets_or_runtime_missing")

    def test_memory_gates_before_spawn_and_during_exchange(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(module.LayaAdapter, "_prepare"), \
                    patch.object(module.LayaAdapter, "_available", return_value=6143), \
                    patch.object(module.subprocess, "Popen", side_effect=AssertionError("spawned")):
                adapter = module.LayaAdapter(profile(), Path(temp) / "profile.json")
            self.assertEqual(adapter.provenance["availability_error"], "laya_host_memory_low")
        resident = uninitialized()
        resident._process = None
        resident._peak_rss_mb = 0.0
        with patch.object(module.LayaAdapter, "_available", return_value=2047):
            with self.assertRaises(MemoryError):
                resident._monitor()

    def test_protocol_failure_closes_and_is_cached(self):
        adapter = uninitialized()
        adapter._sequence = 0
        adapter._profile = {"timeout_seconds": 1}
        adapter._failure = None
        adapter._closed = False
        adapter._process = types.SimpleNamespace()
        adapter.provenance = {"available": True}
        adapter._guard = lambda: None
        closed = []
        adapter.close = lambda: closed.append(True)
        wrong = response()
        wrong["sequence"] = 99
        request = {"contract_id": CONTEXT_CHOICE_CONTRACT, "input": INPUT}
        with patch.object(module, "exchange", return_value=wrong) as exchange:
            first = adapter.predict(request)
            second = adapter.predict(request)
        self.assertEqual(first["error"], "laya_worker_protocol_invalid")
        self.assertEqual(second["raw_output"], {"forward_executed": False, "cached_failure": True})
        self.assertEqual(exchange.call_count, 1)
        self.assertTrue(closed)
        self.assertFalse(adapter.provenance["available"])


if __name__ == "__main__":
    unittest.main()
