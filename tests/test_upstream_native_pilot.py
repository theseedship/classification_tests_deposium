"""Direct upstream supervision and encoding controls without a native process."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from deposium_bench.physics_corpus import build_cases
from deposium_bench import systemone_local

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run-upstream-native-pilot.py"
SPEC = importlib.util.spec_from_file_location("upstream_pilot", SCRIPT)
upstream = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upstream)


def encoded(case, model_id="fixture-model", negative=False):
    body = upstream.native_request(case["input"], model_id)[2]
    tokens = [1] * (4097 if negative else 2)
    return {"schema_version": "deposium.native-systemone-encoding/v1", "source_revision": upstream.PIN,
        "case_id": "synthetic-native-overflow" if negative else case["case_id"],
        "max_tokens": 4096, "vocab_only": True, "weights_loaded": False,
        "inference_context_created": False, "forward_executed": False, "native_input_prepared": True,
        "variant_count": 1, "status": "unsupported" if negative else "within_limit",
        "request_body_sha256": hashlib.sha256(body).hexdigest(), "request_body_bytes": len(body),
        "variants": [{"token_ids": tokens, "token_count": len(tokens),
            "token_ids_sha256": hashlib.sha256(json.dumps(tokens, separators=(",", ":")).encode()).hexdigest(),
            "option_keys": ["c0", "c1", "c2", "c3"], "within_limit": not negative}]}


def upstream_args(**changes):
    from types import SimpleNamespace
    values = dict(context=4096, min_free_mb=8192, max_seconds=600, port=11438, max_rss_mb=24576,
                  execution_envelope=upstream.DEFAULT_ENVELOPE, phase="canary", decision_type="d3",
                  task="choices", technical_only=False, model_id=upstream.D327_ALIAS, backend="metal",
                  preparation_receipt=None, calibration_receipt=None, dataset=None)
    values.update(changes)
    return SimpleNamespace(**values)


class UpstreamPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = build_cases()[0]
        self.audit = self.root / "audit.jsonl"
        self.rows = [encoded(self.case), encoded(self.case, negative=True)]
        self.write_audit(self.rows)

    def write_audit(self, rows):
        self.audit.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_native_preparation_binds_wire_hash_tokens_and_negative_control(self):
        result = upstream.preparation_map(self.audit, [self.case], "fixture-model", 4096)
        self.assertEqual(result["request_tokens"], {self.rows[0]["request_body_sha256"]: 2})
        self.assertEqual(result["audit_sha256"], upstream.digest(self.audit))
        for mutate in (
                lambda rows: rows.pop(),
                lambda rows: rows.append(deepcopy(rows[0])),
                lambda rows: rows[0].update(forward_executed=True),
                lambda rows: rows[0].update(source_revision="b" * 40),
                lambda rows: rows[0].update(request_body_sha256="c" * 64),
                lambda rows: rows[0]["variants"][0].update(token_ids=[9, 9]),
                lambda rows: rows[1].update(status="within_limit")):
            with self.subTest(mutate=mutate):
                changed = deepcopy(self.rows)
                mutate(changed)
                self.write_audit(changed)
                with self.assertRaises(ValueError):
                    upstream.preparation_map(self.audit, [self.case], "fixture-model", 4096)

    def test_preparation_accepts_two_to_sixteen_contiguous_option_keys(self):
        from deposium_bench.facade_corpus import build_cases as facade_cases
        case = facade_cases()[0]
        self.assertEqual(len(case["input"]["options"]), 8)
        rows = [encoded(case), encoded(case, negative=True)]
        rows[0]["variants"][0]["option_keys"] = ["c" + str(i) for i in range(8)]
        self.write_audit(rows)
        upstream.preparation_map(self.audit, [case], "fixture-model", 4096)
        for keys in (["c" + str(i) for i in range(17)], ["c0"], ["c0", "c2"], ["c1", "c0"]):
            with self.subTest(keys=keys):
                changed = deepcopy(rows)
                changed[0]["variants"][0]["option_keys"] = keys
                self.write_audit(changed)
                with self.assertRaises(ValueError):
                    upstream.preparation_map(self.audit, [case], "fixture-model", 4096)

    def test_declared_backends_have_a_distinct_offload_marker_and_27b_stays_metal(self):
        self.assertEqual(set(upstream.BACKEND_BUFFERS), {"metal", "cuda", "rocm", "vulkan"})
        import re
        logs = {"cuda": "load_tensors:        CUDA0 model buffer size =  4914.39 MiB",
                "rocm": "load_tensors:        ROCm0 model buffer size =  4914.39 MiB",
                "vulkan": "load_tensors:      Vulkan0 model buffer size =  4914.39 MiB"}
        for backend, line in logs.items():
            self.assertRegex(line, upstream.BACKEND_BUFFERS[backend])
            for other in set(logs) - {backend}:
                self.assertIsNone(re.search(upstream.BACKEND_BUFFERS[other], line))
        self.assertIsNone(re.search(upstream.BACKEND_BUFFERS["cuda"], "load_tensors: CPU_Mapped model buffer size = 1 MiB"))
        args = upstream_args(execution_envelope=upstream.D327_ENVELOPE, backend="cuda")
        with self.assertRaisesRegex(ValueError, "d327_exact_candidate_required"):
            upstream.execution_envelope(args, upstream.D327_ASSETS, Path(upstream.D327_ASSETS["files"][0]["path"]), [])

    def test_small_envelope_admits_only_small_models_at_eight_gib(self):
        small = {"repo_id": "ggml-org/vllm-d3-mini-GGUF", "files": [{"path": "m.gguf", "size": 5 * 1024 ** 3, "sha256": "a" * 64}]}
        args = upstream_args(execution_envelope=upstream.SMALL_ENVELOPE, max_rss_mb=8192, phase=None)
        self.assertEqual(upstream.execution_envelope(args, small, Path("m.gguf"), [])[0], {"name": upstream.SMALL_ENVELOPE})
        large = {**small, "files": [{**small["files"][0], "size": 7 * 1024 ** 3}]}
        with self.assertRaisesRegex(ValueError, "small_envelope_requires_a_small_model"):
            upstream.execution_envelope(args, large, Path("m.gguf"), [])
        with self.assertRaisesRegex(ValueError, "fixed_envelope_required"):
            upstream.execution_envelope(upstream_args(execution_envelope=upstream.SMALL_ENVELOPE, max_rss_mb=18432, phase=None),
                                        small, Path("m.gguf"), [])

    def test_flash_q4_envelope_is_bound_to_the_pinned_file(self):
        flash = upstream.FLASH_Q4_ASSETS
        name = Path(flash["files"][0]["path"])
        args = upstream_args(execution_envelope=upstream.FLASH_Q4_ENVELOPE, max_rss_mb=12288, phase=None)
        self.assertEqual(upstream.execution_envelope(args, flash, name, [])[0], {"name": upstream.FLASH_Q4_ENVELOPE})
        other = {**flash, "files": [{**flash["files"][0], "sha256": "0" * 64}]}
        with self.assertRaisesRegex(ValueError, "requires_the_pinned_d3_flash_q4"):
            upstream.execution_envelope(args, other, name, [])
        with self.assertRaisesRegex(ValueError, "fixed_envelope_required"):
            upstream.execution_envelope(upstream_args(execution_envelope=upstream.FLASH_Q4_ENVELOPE, max_rss_mb=18432, phase=None),
                                        flash, name, [])

    def test_runtime_refuses_wrong_source_and_binary_hash(self):
        binary = self.root / "llama-server"
        binary.write_bytes(b"synthetic-never-executed")
        manifest = self.root / "runtime.json"
        record = {"repository": upstream.REPOSITORY, "revision": upstream.PIN,
                  "binary_sha256": upstream.digest(binary)}
        manifest.write_text(json.dumps(record))
        with patch.object(upstream, "capture", side_effect=[upstream.PIN, upstream.REPOSITORY, ""]):
            self.assertEqual(upstream.validated_runtime(self.root, binary, manifest), record)
        with patch.object(upstream, "capture", return_value="wrong"):
            with self.assertRaisesRegex(ValueError, "source_identity"):
                upstream.validated_runtime(self.root, binary, manifest)
        binary.write_bytes(b"changed")
        with patch.object(upstream, "capture", side_effect=[upstream.PIN, upstream.REPOSITORY, ""]):
            with self.assertRaisesRegex(ValueError, "binary_hash"):
                upstream.validated_runtime(self.root, binary, manifest)

    def test_passage_selection_uses_existing_projection_and_calibration_only_canary(self):
        import argparse
        from deposium_bench.passage_dataset import DEFAULT_DATASET
        from deposium_bench.passage_observation import choice_plan, select_pilot
        from deposium_bench.passage_dataset import load_dataset
        source, _ = load_dataset()
        logical, _ = choice_plan(select_pilot(source, "calibration"))
        expected = []
        for axis in ("relevance", "support", "answerability"):
            expected.extend(sorted({r["call_id"] for r in logical if r["axis"] == axis})[:4])
        args = argparse.Namespace(task="passages", dataset=DEFAULT_DATASET, passage_split="calibration",
                                  technical_only=True)
        payload, metadata, calls, manifest, warmup = upstream.selected_inputs(args)
        self.assertEqual([r["case_id"] for r in calls], expected)
        self.assertEqual(len(calls), 12)
        self.assertEqual(metadata["selected_pools"], 128)
        self.assertEqual(payload, DEFAULT_DATASET.read_bytes())
        self.assertEqual(manifest, DEFAULT_DATASET.parent.joinpath("manifest.json").read_bytes())
        self.assertEqual(warmup, calls[0])
        self.assertEqual({len(r["input"]["options"]) for r in calls}, {3, 4})
        args.technical_only = False
        args.passage_split = "test"
        _, metadata, calls, _, same_warmup = upstream.selected_inputs(args)
        self.assertEqual(len(calls), 728)
        self.assertEqual(same_warmup, warmup)
        args.technical_only = True
        with self.assertRaisesRegex(ValueError, "calibration"):
            upstream.selected_inputs(args)

    def test_clef_joint_order_and_three_choice_receipts_are_bound_without_d3_fallback(self):
        rows = deepcopy(self.rows)
        for row in rows:
            row.update(decision_type="clef", joint=True)
            variant = row["variants"][0]
            variant["option_keys"] = ["c0", "c1", "c2"]
            variant["n_scores"] = 3
            variant["decision_order"] = [1] * len(variant["token_ids"])
            variant["decision_order_sha256"] = hashlib.sha256(
                json.dumps(variant["decision_order"], separators=(",", ":")).encode()).hexdigest()
        case = deepcopy(self.case)
        case["input"]["options"].pop()
        body = upstream.native_request(case["input"], "fixture-model")[2]
        rows[0].update(request_body_sha256=hashlib.sha256(body).hexdigest(), request_body_bytes=len(body))
        self.write_audit(rows)
        prepared = upstream.preparation_map(self.audit, [case], "fixture-model", 4096, "clef")
        self.assertEqual(prepared["decision_type"], "clef")
        with self.assertRaisesRegex(ValueError, "preparation_invalid"):
            upstream.preparation_map(self.audit, [case], "fixture-model", 4096, "d3")
        rows[0]["variants"][0]["decision_order"][0] = 9
        self.write_audit(rows)
        with self.assertRaisesRegex(ValueError, "joint_order_hash"):
            upstream.preparation_map(self.audit, [case], "fixture-model", 4096, "clef")

    def test_owned_direct_session_keeps_wrong_answers_and_seals_after_cleanup(self):
        import argparse
        assets_model = self.root / "fixture.gguf"
        assets_model.write_bytes(b"synthetic-not-weights")
        assets = self.root / "assets.json"
        assets.write_text(json.dumps({"schema_version": "deposium.model-assets/v1",
            "repo_id": "fixture/model", "revision": "a" * 40, "files": [{"path": assets_model.name,
                "size": assets_model.stat().st_size, "sha256": upstream.digest(assets_model)}]}))
        dataset = self.root / "cases.jsonl"
        dataset.write_text(json.dumps(self.case) + "\n")
        binary = self.root / "llama-server"
        binary.write_bytes(b"synthetic-native-server")
        runtime = {"repository": upstream.REPOSITORY, "revision": upstream.PIN,
                   "binary_sha256": upstream.digest(binary)}
        output = self.root / "results/session"
        args = argparse.Namespace(dataset=dataset, output=output, model=assets_model, assets_manifest=assets,
            source_root=self.root, binary=binary, runtime_manifest=self.root / "runtime.json",
            preparation=self.audit, model_id="fixture-model", port=11438, context=4096,
            max_rss_mb=18432, min_free_mb=8192, max_seconds=600)
        process = Mock(pid=424242, returncode=0)
        process.poll.return_value = None
        watcher = Mock()
        watcher.is_alive.return_value = True
        observed_key = []
        original_start = upstream.subprocess.Popen

        def launch(command, **kwargs):
            if command[0] != str(binary):
                return original_start(command, **kwargs)
            observed_key.append(kwargs["env"]["LLAMA_API_KEY"])
            self.assertNotIn(observed_key[-1], json.dumps(command))
            self.assertEqual(command[command.index("--log-verbosity") + 1], "4")
            kwargs["stdout"].write(b"ggml_metal_init: found device: synthetic GPU\nload_tensors: offloaded 33/33 layers to GPU\ndecision model type: vllm-d3\n")
            kwargs["stdout"].flush()
            return process

        def thread(*_, **kwargs):
            kwargs["args"][2]["last_observed_monotonic"] = time.monotonic()
            return watcher

        def request(port, method, path, body, key, timeout):
            if method == "GET":
                return 200, b"{}"
            if not key:
                return 401, b"{}"
            return 500, json.dumps({"error": {"code": 500, "type": "server_error",
                "message": "input (5000 tokens) is too large to process. increase the physical batch size (current batch size: 4096)"}}).encode()

        native = {"model": "fixture-model", "answers": {"answer": {"type": "choice", "choice": "c1",
            "probabilities": {"c0": .1, "c1": .7, "c2": .1, "c3": .1}, "confidence": .7}},
            "usage": {"input_tokens": 2, "output_tokens": 0}}
        previous_key = os.environ.get(upstream.AUTH_ENV)
        with patch.object(upstream, "ROOT", self.root), \
                patch.object(upstream.socket, "socket"), \
                patch.object(upstream, "validated_runtime", return_value=runtime), \
                patch.object(upstream, "memory_snapshot", return_value={"MemAvailable_mib": 50000}), \
                patch.object(upstream.subprocess, "Popen", side_effect=launch), \
                patch.object(upstream.os, "getpgid", return_value=process.pid), \
                patch.object(upstream.threading, "Thread", side_effect=thread), \
                patch.object(upstream, "http_request", side_effect=request), \
                patch.object(systemone_local, "http_request", return_value=(200, json.dumps(native).encode())), \
                patch.object(upstream.shared, "finish_owned") as finish:
            result = upstream.pilot(args)
        self.assertTrue(result["completed"])
        self.assertEqual(result["campaign_coverage"]["quality_verdict"], "fail")
        self.assertEqual(result["campaign_coverage"]["scored_cases"], 1)
        self.assertEqual(result["actual_backend"]["offloaded_layers"], 33)
        finish.assert_called_once()
        self.assertEqual(os.environ.get(upstream.AUTH_ENV), previous_key)
        seal = json.loads((output / "pilot-seal.json").read_text())
        for name, sha in seal["files"].items():
            self.assertEqual(upstream.digest(output / name), sha)
        for path in output.rglob("*.json"):
            self.assertNotIn(observed_key[0], path.read_text())


if __name__ == "__main__":
    unittest.main()
