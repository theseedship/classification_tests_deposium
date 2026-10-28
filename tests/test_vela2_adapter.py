"""Offline Vela2 contract tests; no checkpoint or candidate import is needed."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from deposium_bench.adapters import parse_profile
from deposium_bench.campaigns import _prepare_profile
from deposium_bench.choice_protocol import CONTEXT_CHOICE_PROMPT
from deposium_bench import vela2_adapter as module
from deposium_bench import mastra_observation as observation
from deposium_bench.mastra_pilot import DATASET

ROOT = Path(__file__).resolve().parents[1]
REVISION = "d6f03aa9baca4f9017fa8f8e9c2764d3bed3f409"
INPUT = {"context": "Une demande en français.", "question": "Quelle action ?",
         "options": [{"id": "opaque-a", "description": "Rechercher"},
                     {"id": "opaque-b", "description": "Compter"}]}
FAKE_WORKER = '''import hashlib, json, sys
def send(value): print(json.dumps(value,allow_nan=False),flush=True)
config=json.loads(sys.stdin.readline())["config"]
send({"status":"ready","runtime":config["pins"],"load_ms":1.0,"rss_mb":10.0,
      "native_max_input_tokens":8192,"dtype":"float32","device":"cpu",
      "loading_mode":"hf-automodel-fp32"})
for line in sys.stdin:
    request=json.loads(line); value=request["input"]
    blob=(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)+"\\n").encode()
    ids=[o["id"] for o in value["options"]]
    native={"model":"vllm-sr/Vela-2.0-0.3B","answers":{"decision":{
        "type":"choice","choice":"c1","probabilities":{"c0":0.25,"c1":0.75},"confidence":0.5}},
        "usage":{"input_tokens":40,"output_tokens":0}}
    if MODE=="bad_usage": native["usage"]["input_tokens"]=39
    raw={"native_result":native,"native_tokens":native["usage"]["input_tokens"],
         "input_sha256":hashlib.sha256(blob).hexdigest(),"ordered_ids":ids,
         "encoding_info":{"tokens":40,"stateTruncated":False,"optionsTruncated":False},
         "forward_executed":True,"decision_ms":4.0,"inference_ms":3.0,"rss_mb":10.0}
    send({"sequence":request["sequence"],"status":"ok","output":{"choice_id":ids[1]},
          "raw_output":raw,"error":None})
'''


class Vela2AdapterTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.model = self.root / "model"
        self.model.mkdir()
        (self.model / "config.json").write_text("{}\n")
        (self.root / "prompt.json").write_text(json.dumps(CONTEXT_CHOICE_PROMPT))
        (self.root / "runtime.lock").write_text(
            "numpy==2.1.0\ntorch==2.14.0+cpu\ntransformers==5.17.0\ntokenizers==0.23.2\nsafetensors==0.8.0\n")
        data = (self.model / "config.json").read_bytes()
        (self.root / "assets.json").write_text(json.dumps({
            "schema_version": "deposium.model-assets/v1", "repo_id": module.REPO_ID,
            "revision": REVISION, "files": [{"path": "config.json", "size": len(data),
                                          "sha256": hashlib.sha256(data).hexdigest()}]}))
        self.worker = self.root / "worker.py"
        self.worker.write_text(FAKE_WORKER.replace("MODE", repr("ok")))
        self.profile = {"schema_version": "deposium.candidate/v1", "profile_id": "offline-vela2",
                        "adapter": "vela2", "qualification": "model_isolated",
                        "capabilities": ["bench.context-choice"], "recordings": None,
                        "revision": REVISION, "timeout_seconds": 3,
                        "model": {"repo_id": module.REPO_ID, "local_dir": "model",
                                  "runtime_python": sys.executable, "assets_manifest": "assets.json",
                                  "prompt_path": "prompt.json", "runtime_lock": "runtime.lock",
                                  "max_length": 4096, "threads": 2, "max_rss_mb": 4096}}

    def adapter(self):
        with patch.object(module, "WORKER", self.worker), patch.object(
                module.Vela2Adapter, "_host_available_mb", return_value=100000):
            adapter = module.Vela2Adapter(self.profile, self.root / "profile.json")
        self.addCleanup(adapter.close)
        return adapter

    def test_profile_pins_and_public_profile_parse_without_loading_model(self):
        parse_profile(json.dumps(self.profile).encode())
        for name in ("03", "08"):
            profile = json.loads((ROOT / f"profiles/vela2-{name}-cpu-context.json").read_text())
            parse_profile(json.dumps(profile).encode())
        self.assertEqual(module.minimum_available_mib(module.REPO_ID), 6144)
        self.assertEqual(module.minimum_available_mib("vllm-sr/Vela-2.0-0.8B"), 8192)
        for key, value in (("max_length", 4097), ("threads", 3), ("max_rss_mb", 4097)):
            changed = json.loads(json.dumps(self.profile))
            changed["model"][key] = value
            with self.subTest(key=key), self.assertRaises(module.Vela2ProfileError):
                module.validate_model_profile(changed)
        self.profile["model"]["repo_id"] = "vllm-sr/Vela-2.0-9B"
        with self.assertRaises(ValueError):
            parse_profile(json.dumps(self.profile).encode())

    def test_vela4_profile_has_separate_memory_and_time_limits(self):
        repo = module.VELA4_REPO_ID
        revision, name, native_limit = module.MODELS[repo]
        self.assertEqual((revision, name, native_limit),
                         ("d692394127f6f87fc581d8634c9558fe4776efce", repo, 16384))
        self.assertEqual(module.minimum_available_mib(repo), 24576)
        self.assertEqual(module.memory_floor_mib(repo), 4096)
        profile = json.loads(json.dumps(self.profile))
        profile["model"].update(repo_id=repo, max_rss_mb=22528)
        profile.update(revision=revision, timeout_seconds=60)
        module.validate_model_profile(profile)
        for key, value in (("max_rss_mb", 22529), ("max_length", 4097), ("threads", 3)):
            changed = json.loads(json.dumps(profile))
            changed["model"][key] = value
            with self.subTest(key=key), self.assertRaises(module.Vela2ProfileError):
                module.validate_model_profile(changed)
        for key, value in (("revision", "0" * 40), ("timeout_seconds", 61)):
            changed = json.loads(json.dumps(profile))
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(module.Vela2ProfileError):
                module.validate_model_profile(changed)

    def test_public_profiles_archive_absolute_paths_without_resolving_venv(self):
        for name in ("03", "08"):
            path = ROOT / f"profiles/vela2-{name}-cpu-context.json"
            source = json.loads(path.read_text())
            archived, _, recordings = _prepare_profile(path)
            self.assertIsNone(recordings)
            for key in module.PATH_FIELDS:
                self.assertEqual(archived["model"][key],
                                 os.path.abspath(path.parent / source["model"][key]))
            self.assertIn("decision2-runtime/bin/python", archived["model"]["runtime_python"])

    def test_missing_manifest_is_distinct_from_invalid_directory(self):
        (self.root / "assets.json").unlink()
        missing = self.adapter()
        self.assertEqual(missing.provenance["availability_error"], "vela2_assets_or_runtime_missing")
        (self.root / "assets.json").mkdir()
        invalid = self.adapter()
        self.assertEqual(invalid.provenance["availability_error"], "vela2_initialization_invalid")

    def test_each_variant_ram_floor_precedes_archive_and_model(self):
        for name, floor in (("03", 6144), ("08", 8192)):
            profile = ROOT / f"profiles/vela2-{name}-cpu-context.json"
            output = self.root / f"low-memory-{name}"
            with self.subTest(name=name), patch.object(
                    observation, "memory_snapshot", return_value={"MemAvailable_mib": floor - 1}), \
                    patch.object(observation, "_stack_context", side_effect=AssertionError("stack accessed")), \
                    patch.object(observation, "create_adapter", side_effect=AssertionError("model loaded")):
                with self.assertRaisesRegex(ValueError, "available RAM"):
                    observation.observe_local(DATASET, profile, output)
                self.assertFalse(output.exists())

    def test_missing_and_changed_assets_fail_before_inference(self):
        (self.model / "config.json").unlink()
        adapter = self.adapter()
        self.assertFalse(adapter.provenance["available"])
        self.assertEqual(adapter.predict({"contract_id": "bench.context-choice", "input": INPUT})["status"], "missing")
        (self.model / "config.json").write_text("{}\n")
        adapter = self.adapter()
        self.assertTrue(adapter.provenance["available"])
        (self.model / "config.json").write_text('{"changed":true}\n')
        response = adapter.predict({"contract_id": "bench.context-choice", "input": INPUT})
        self.assertEqual(response["status"], "error")
        self.assertFalse(adapter.provenance["available"])

    def test_opaque_choice_and_usage_proof(self):
        adapter = self.adapter()
        self.assertTrue(adapter.provenance["available"])
        response = adapter.predict({"contract_id": "bench.context-choice", "input": INPUT})
        self.assertEqual(response["output"], {"choice_id": "opaque-b"})
        self.assertEqual(response["raw_output"]["native_tokens"], 40)
        adapter.close()
        self.worker.write_text(FAKE_WORKER.replace("MODE", repr("bad_usage")))
        bad = self.adapter()
        response = bad.predict({"contract_id": "bench.context-choice", "input": INPUT})
        self.assertEqual((response["status"], response["error"]),
                         ("error", "vela2_runtime_or_protocol_changed"))

    def test_request_size_refusal_is_local_to_one_case(self):
        adapter = self.adapter()
        large = {**INPUT, "context": "x" * (module.MAX_LINE + 1)}
        refusal = adapter.predict({"contract_id": "bench.context-choice", "input": large})
        self.assertEqual((refusal["status"], refusal["error"]),
                         ("unsupported", "vela2_request_too_large"))
        self.assertFalse(refusal["raw_output"]["forward_executed"])
        self.assertEqual(adapter.predict({"contract_id": "bench.context-choice", "input": INPUT})["status"], "ok")


class Vela2NativeBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("vela2_worker_test", ROOT / "bridges/vela2-worker.py")
        cls.worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.worker)

    def test_loaded_named_parameters_are_checked_as_tensors_for_both_variants(self):
        torch = types.SimpleNamespace(float32="float32")
        for repo in (self.worker.REPO_ID, "vllm-sr/Vela-2.0-0.8B"):
            for invalid in (None, "dtype", "device", "count"):
                with self.subTest(repo=repo, invalid=invalid):
                    count = self.worker.MODELS[repo][1] + (1 if invalid == "count" else 0)
                    parameter = types.SimpleNamespace(numel=lambda: count,
                        dtype="float16" if invalid == "dtype" else "float32",
                        device=types.SimpleNamespace(type="cuda" if invalid == "device" else "cpu"))
                    parameters = [("backbone.weight", parameter)]
                    if repo != self.worker.REPO_ID:
                        broad = types.SimpleNamespace(numel=lambda: 1119745, dtype="float32",
                            device=types.SimpleNamespace(type="cpu"))
                        parameters.append(("span_broad.weight", broad))
                    model = types.SimpleNamespace(max_len=self.worker.MODELS[repo][2],
                        run=types.SimpleNamespace(model=types.SimpleNamespace(named_parameters=lambda: parameters)))
                    if invalid is None:
                        self.worker._check_model(model, repo, torch)
                    else:
                        with self.assertRaisesRegex(ValueError, "vela2_model_identity_invalid"):
                            self.worker._check_model(model, repo, torch)

    def test_vela4_local_headers_must_match_loaded_parameter_names_and_shapes(self):
        repo = self.worker.VELA4_REPO_ID
        # The pinned main shards include the scalar set_bias omitted by Hub's
        # aggregate metadata. Use small header-only files with the exact count;
        # no tensor payload or model import is needed.
        expected = 4211182082
        self.assertEqual(self.worker.MODELS[repo][1], expected)
        torch = types.SimpleNamespace(float32="float32")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            weight_map = {}
            shapes = {}
            for number, (key, shape) in enumerate((
                    ("set_bias", []), ("backbone.weight", [expected - 2]),
                    ("span2.o.bias", [1])), 1):
                filename = f"model-{number:05d}-of-00003.safetensors"
                header = json.dumps({key: {"dtype": "F32", "shape": shape,
                                           "data_offsets": [0, 4]}}).encode()
                (root / filename).write_bytes(struct.pack("<Q", len(header)) + header)
                weight_map[key] = filename
                shapes[key] = tuple(shape)
            broad_header = json.dumps({"span_broad.weight": {
                "dtype": "F32", "shape": [3], "data_offsets": [0, 12]}}).encode()
            (root / "broad_head.safetensors").write_bytes(
                struct.pack("<Q", len(broad_header)) + broad_header)
            (root / "model.safetensors.index.json").write_text(json.dumps({"weight_map": weight_map}))
            pinned_main, pinned_broad = self.worker._pinned_shapes(root)
            self.assertEqual(pinned_main, shapes)
            self.assertEqual(pinned_broad, {"span_broad.weight": (3,)})
            self.assertEqual(sum(math.prod(shape) for shape in pinned_main.values()), expected)

            def parameter(shape, dtype="float32"):
                return types.SimpleNamespace(shape=shape, numel=lambda: math.prod(shape),
                                             dtype=dtype, device=types.SimpleNamespace(type="cpu"))
            parameters = [(name, parameter(shape)) for name, shape in shapes.items()]
            parameters.append(("span_broad.weight", parameter((3,))))
            model = types.SimpleNamespace(max_len=16384,
                run=types.SimpleNamespace(model=types.SimpleNamespace(named_parameters=lambda: parameters)))
            self.worker._check_model(model, repo, torch, root)
            parameters[0] = (parameters[0][0], parameter((2,)))
            with self.assertRaisesRegex(ValueError, "vela2_model_identity_invalid"):
                self.worker._check_model(model, repo, torch, root)
            parameters[0] = (parameters[0][0], parameter((1,)))
            (root / weight_map["set_bias"]).write_bytes(
                struct.pack("<Q", len(header)) + header)  # wrong key in shard
            with self.assertRaises(ValueError):
                self.worker._check_model(model, repo, torch, root)

    def test_overflow_uses_complete_native_assembly_and_never_forwards(self):
        native = types.ModuleType("vela2_inference")
        native.system_one_to_predict = lambda state, questions: ({"parts": [], "questions": []}, [])
        class NoForward:
            max_len = 8192
            def _to_generic(self, request): return [], [], {}
            def _prep(self, row): return row
            def _assemble(self, row):
                self_test.assertEqual(self.max_len, 1_000_000)
                return {"ids": list(range(4097)), "trunc": {"shrink_cut": 0, "protected_cut": 0}}
            def system_one(self, **kwargs): raise AssertionError("inference after overflow")
        self_test = self
        model = NoForward()
        with patch.dict(sys.modules, {"vela2_inference": native}), \
                patch.object(self.worker, "_host_available_mb", return_value=100000), \
                patch.object(self.worker, "_rss", return_value=10):
            result = self.worker._predict(model, INPUT, 4096)
        self.assertEqual(model.max_len, 8192)
        self.assertEqual((result["status"], result["error"]), ("unsupported", "vela2_context_overflow"))
        self.assertFalse(result["raw_output"]["forward_executed"])

    def test_decoder_preflight_restores_native_limit_and_preserves_head(self):
        native = types.ModuleType("vela2_inference")
        native.system_one_to_predict = lambda state, questions: ({"parts": [], "questions": []}, [])
        class Render:
            max_len = 16384
            def _to_generic(self, request): return [], [], {}
            def _prep(self, row): return {"head": "router"}
            def _render(self, row):
                self_test.assertEqual(self.max_len, 1_000_000)
                return {"p_ids": [1, 2], "blocks": [{"ids": [3, 4]}], "n_tokens": 4,
                        "trunc": {"shrink_cut": 0, "protected_cut": 0}}
        self_test = self
        model = Render()
        with patch.dict(sys.modules, {"vela2_inference": native}):
            rec = self.worker._complete_record(model, INPUT["context"], {"type": "choice"})
        self.assertEqual((rec["n_tokens"], rec["head"], model.max_len), (4, "router", 16384))

    def test_backend_receives_exact_native_arrays(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is optional for the offline test suite")
        rec = {"ids": list(range(12)), "trunc": {"shrink_cut": 0, "protected_cut": 0}}
        expected = tuple(np.array([n], dtype=np.int64) for n in range(6))
        class Model:
            max_len = 8192
            def __init__(self, altered):
                self.altered = altered
                self.run = lambda *args: (None, None)
            def system_one(self, **kwargs):
                arrays = list(expected)
                if self.altered:
                    arrays[3] = np.array([999], dtype=np.int64)
                self.run(*arrays)
                return {"model": self_worker.REPO_ID, "answers": {"decision": {
                    "type": "choice", "choice": "c1", "probabilities": {"c0": 0.25, "c1": 0.75},
                    "confidence": 0.5}}, "usage": {"input_tokens": 12, "output_tokens": 0}}
        self_worker = self.worker
        with patch.object(self.worker, "_complete_record", return_value=rec), \
                patch.object(self.worker, "_expected_forward", return_value=expected), \
                patch.object(self.worker, "_host_available_mb", return_value=100000), \
                patch.object(self.worker, "_rss", return_value=10):
            good = self.worker._predict(Model(False), INPUT, 4096)
            changed = self.worker._predict(Model(True), INPUT, 4096)
        self.assertEqual(good["status"], "ok")
        self.assertTrue(good["raw_output"]["forward_executed"])
        self.assertEqual((changed["status"], changed["error"]), ("error", "vela2_inference_failed"))
        self.assertFalse(changed["raw_output"]["forward_executed"])

    def test_decoder_record_and_actual_embedding_tokens(self):
        rec = {"p_ids": [1, 2], "blocks": [{"kind": "q", "ids": [3, 4]}],
               "n_tokens": 4, "head": "router", "trunc": {"shrink_cut": 0, "protected_cut": 0}}
        class Tensor:
            def __init__(self, value): self.value = value
            def detach(self): return self
            def cpu(self): return self
            def tolist(self): return self.value
        class Embedding:
            def __init__(self): self.hook = None
            def register_forward_pre_hook(self, callback):
                self.hook = callback
                return types.SimpleNamespace(remove=lambda: setattr(self, "hook", None))
        class Backend:
            def __init__(self, changed_tokens):
                self.changed_tokens = changed_tokens
                self.embedding = Embedding()
                self.model = types.SimpleNamespace(backbone=types.SimpleNamespace(embed_tokens=self.embedding))
            def __call__(self, recs):
                self.embedding.hook(None, (Tensor([[1, 2]]),))
                self.embedding.hook(None, (Tensor([[3, 999] if self.changed_tokens else [3, 4]]),))
                return None
        class Model:
            max_len = 16384
            _repo_id = "vllm-sr/Vela-2.0-0.8B"
            def __init__(self, changed_record=False, changed_tokens=False):
                self.changed_record = changed_record
                self.run = Backend(changed_tokens)
            def system_one(self, **kwargs):
                payload = json.loads(json.dumps(rec))
                if self.changed_record:
                    payload["blocks"][0]["ids"][1] = 999
                self.run([payload])
                return {"model": self._repo_id, "answers": {"decision": {
                    "type": "choice", "choice": "c1", "probabilities": {"c0": 0.25, "c1": 0.75},
                    "confidence": 0.5}}, "usage": {"input_tokens": 4, "output_tokens": 0}}
        with patch.object(self.worker, "_complete_record", return_value=rec), \
                patch.object(self.worker, "_host_available_mb", return_value=100000), \
                patch.object(self.worker, "_rss", return_value=10):
            good = self.worker._predict(Model(), INPUT, 4096)
            changed_record = self.worker._predict(Model(changed_record=True), INPUT, 4096)
            changed_tokens = self.worker._predict(Model(changed_tokens=True), INPUT, 4096)
        self.assertEqual(good["status"], "ok")
        self.assertTrue(good["raw_output"]["forward_executed"])
        self.assertEqual(changed_record["status"], "error")
        self.assertFalse(changed_record["raw_output"]["forward_executed"])
        self.assertEqual(changed_tokens["status"], "error")
        self.assertTrue(changed_tokens["raw_output"]["forward_executed"])

    def test_encoder_loader_uses_local_automodel_once_and_passes_it_to_engine(self):
        calls = []
        class Vela2Model:
            def eval(self):
                calls.append("eval")
                return self
        native = Vela2Model()
        def from_pretrained(path, **kwargs):
            calls.append((path, kwargs))
            return native
        def engine(path, **kwargs):
            calls.append((path, kwargs))
            return types.SimpleNamespace()
        transformers = types.ModuleType("transformers")
        transformers.AutoModel = types.SimpleNamespace(from_pretrained=from_pretrained)
        inference = types.ModuleType("vela2_inference")
        inference.Vela2 = engine
        fake_torch = types.SimpleNamespace(float32=object())
        with patch.dict(sys.modules, {"transformers": transformers, "vela2_inference": inference}):
            _, mode = self.worker._load_engine(Path("/verified/local/snapshot"), self.worker.REPO_ID, 2, fake_torch)
        self.assertEqual(mode, "hf-automodel-fp32")
        self.assertEqual(calls[0][0], "/verified/local/snapshot")
        self.assertEqual(calls[0][1], {"trust_remote_code": True, "local_files_only": True,
                                       "dtype": fake_torch.float32, "attn_implementation": "sdpa"})
        self.assertEqual(calls[2][1]["model"], native)
        self.assertEqual(calls[2][1]["device"], "cpu")


if __name__ == "__main__":
    unittest.main()
