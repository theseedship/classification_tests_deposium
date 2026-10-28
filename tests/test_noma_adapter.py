"""Noma parent contract tests without weights, child processes or model imports."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from deposium_bench.choice_protocol import CONTEXT_CHOICE_CONTRACT
from deposium_bench.worker_transport import wire
from deposium_bench import noma_adapter as module


INPUT = {
    "context": "Visible text.",
    "question": "Which action?",
    "options": [{"id": "opaque-first", "description": "Search"},
                {"id": "opaque-second", "description": "Count"}],
}


def response(value=INPUT):
    info = {"tokens": 4, "prefix_tokens": 2, "block_tokens": 2,
            "prefix_truncated": False, "prefix_uncapped_equal": True,
            "forward_count": 1, "forward_ids_equal": True,
            "facts_version": "facts-0.2", "reference_time": module.REFERENCE_TIME,
            "fact_lines": ["F1: fixture"]}
    raw = {"native_result": {"probabilities": {"c0": 0.25, "c1": 0.75},
                             "abstain": 0.99, "uncertainty": 0.05},
           "native_tokens": 4, "input_sha256": hashlib.sha256(wire(value)).hexdigest(),
           "ordered_ids": [o["id"] for o in value["options"]],
           "encoding_info": info, "forward_executed": True,
           "decision_ms": 5.0, "inference_ms": 4.0, "rss_mb": 12.0}
    return {"sequence": 1, "status": "ok", "output": {"choice_id": "opaque-second"},
            "raw_output": raw, "error": None}


def uninitialized_adapter():
    adapter = object.__new__(module.NomaAdapter)
    adapter._model = {"max_length": 1024, "max_rss_mb": 8192}
    adapter._sequence = 1
    return adapter


class NomaAdapterContractTests(unittest.TestCase):
    def test_parent_accepts_exact_worker_payload_and_opaque_choice(self):
        adapter = uninitialized_adapter()
        adapter._audit(response(), INPUT)
        self.assertEqual(response()["output"], {"choice_id": "opaque-second"})

    def test_parent_rejects_sequence_tokens_facts_clock_choice_and_forward(self):
        mutations = (
            lambda r: r.update(sequence=2),
            lambda r: r["raw_output"].update(native_tokens=3),
            lambda r: r["raw_output"]["encoding_info"].update(tokens=3),
            lambda r: r["raw_output"]["encoding_info"].update(reference_time="2026-10-04T00:00:00Z"),
            lambda r: r["raw_output"]["encoding_info"].update(facts_version="wrong"),
            lambda r: r.update(output={"choice_id": "opaque-first"}),
            lambda r: r["raw_output"].update(forward_executed=False),
            lambda r: r["raw_output"]["encoding_info"].update(forward_ids_equal=False),
            lambda r: r["raw_output"]["native_result"]["probabilities"].update(c1=1.1),
            lambda r: r["raw_output"]["native_result"].update(abstain=-0.1),
        )
        for change in mutations:
            case = response()
            change(case)
            with self.subTest(change=change), self.assertRaises(ValueError):
                uninitialized_adapter()._audit(case, INPUT)

    def test_preflight_overflow_uses_full_prefix_tokens_without_forward(self):
        case = response()
        raw = case["raw_output"]
        case.update(status="unsupported", output=None, error="noma_context_overflow")
        raw.update(native_result=None, native_tokens=0, forward_executed=False, inference_ms=None)
        raw["encoding_info"].update(tokens=5, prefix_tokens=3, block_tokens=2,
                                    prefix_truncated=True, prefix_uncapped_equal=False,
                                    forward_count=0, forward_ids_equal=False)
        uninitialized_adapter()._audit(case, INPUT)
        bad = deepcopy(case)
        bad["raw_output"]["forward_executed"] = True
        with self.assertRaises(ValueError):
            uninitialized_adapter()._audit(bad, INPUT)

    def test_protocol_failure_closes_and_caches_without_new_exchange(self):
        adapter = uninitialized_adapter()
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
        self.assertEqual(first["status"], "error")
        self.assertEqual(first["error"], "noma_worker_protocol_invalid")
        self.assertEqual(second["raw_output"], {"forward_executed": False, "cached_failure": True})
        self.assertEqual(exchange.call_count, 1)
        self.assertTrue(closed)
        self.assertFalse(adapter.provenance["available"])

    def test_missing_assets_never_spawn_child(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = {"schema_version": "deposium.candidate/v1",
                       "profile_id": "test-noma", "adapter": "noma",
                       "qualification": "model_isolated", "capabilities": [CONTEXT_CHOICE_CONTRACT],
                       "recordings": None, "revision": module.REVISION,
                       "timeout_seconds": 2, "model": {
                           "repo_id": module.REPO_ID, "source_revision": module.SOURCE_REVISION,
                           "local_dir": "model", "source_dir": "source",
                           "runtime_python": "python", "assets_manifest": "model.json",
                           "source_manifest": "source.json", "prompt_path": "prompt.json",
                           "runtime_lock": "runtime.lock", "max_length": 1024,
                           "threads": 2, "max_rss_mb": 8192}}
            with patch.object(module.NomaAdapter, "_prepare", side_effect=FileNotFoundError), \
                    patch.object(module.subprocess, "Popen", side_effect=AssertionError("child spawned")):
                adapter = module.NomaAdapter(profile, Path(temp) / "profile.json")
            self.assertFalse(adapter.provenance["available"])
            self.assertEqual(adapter.provenance["availability_error"], "noma_assets_or_runtime_missing")


if __name__ == "__main__":
    unittest.main()
