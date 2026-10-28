"""Offline Liquid d1-3B native prompt and snapshot controls, without weights."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backend = _module("liquid_d1_backend_under_test", ROOT / "bridges/liquid-d1-backend.py")
prepare = _module("prepare_liquid_d1_assets_under_test", ROOT / "scripts/prepare-liquid-d1-assets.py")

VALUE = {"context": "state", "question": "choose", "options": [
    {"id": "hidden-b", "description": "Search"},
    {"id": "hidden-a", "description": "Count"}]}


class FakeTokenizer:
    all_special_tokens = ["<|im_end|>", "<image>"]
    def encode(self, text, add_special_tokens=False):
        assert not add_special_tokens
        return list(text.encode())


class FakeEngine:
    __module__ = "fake_liquid.runner"

    def __init__(self):
        self.tokenizer = FakeTokenizer()
        self.forward_calls = 0
        self.mismatch = False
        self.last_rendered = None

    def render(self, state, question):
        self.last_rendered = (state + "\n" + question.instructions + "\n"
                              + "\n".join(question.criteria.values()))
        return self.last_rendered

    def _logz_ids(self, rows):
        self._one_pass(input_ids=rows, logits_to_keep=1)
        return None


class FakeModel:
    def __init__(self):
        self.engine = FakeEngine()
        self.engine._one_pass = self._forward
        self.invalid = False

    def _forward(self, *, input_ids, logits_to_keep):
        self.engine.forward_calls += 1

    def system_one(self, state, questions):
        q = SimpleNamespace(**questions["answer"])
        names = list(q.criteria)
        row = self.engine.tokenizer.encode(self.engine.render(state, q), add_special_tokens=False)
        if self.engine.mismatch:
            row[-1] += 1
        self.engine._logz_ids([row])
        probabilities = {names[0]: .25, names[1]: .75}
        if self.invalid:
            probabilities[names[1]] = float("nan")
        return {"answers": {"answer": {"type": "choice", "choice": names[1],
                                       "confidence": .75, "probabilities": probabilities}},
                "usage": {"input_tokens": len(row), "output_tokens": 0}}


class LiquidBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package = ModuleType("fake_liquid")
        package.__path__ = []
        prompt = ModuleType("fake_liquid.prompt")
        prompt.as_question = lambda value: SimpleNamespace(**value)
        cls.old_package = sys.modules.get("fake_liquid")
        cls.old_prompt = sys.modules.get("fake_liquid.prompt")
        sys.modules["fake_liquid"] = package
        sys.modules["fake_liquid.prompt"] = prompt

    @classmethod
    def tearDownClass(cls):
        for name, old in (("fake_liquid", cls.old_package),
                          ("fake_liquid.prompt", cls.old_prompt)):
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old

    def predict(self, value=VALUE, *, mismatch=False, invalid=False):
        model = FakeModel()
        model.engine.mismatch = mismatch
        model.invalid = invalid
        with patch.object(backend, "_rss", return_value=100.0):
            result = backend.LiquidD1Backend(model).predict(value)
        return model, result

    def test_native_choice_uses_neutral_names_and_exact_forward_ids(self):
        model, result = self.predict()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"], {"choice_id": "hidden-a"})
        self.assertEqual(model.engine.forward_calls, 1)
        self.assertNotIn("hidden-a", model.engine.last_rendered)
        self.assertNotIn("hidden-b", model.engine.last_rendered)
        info = result["raw_output"]["encoding_info"]
        self.assertTrue(info["full_input_equal"])
        self.assertEqual(info["forward_count"], 1)
        self.assertEqual(info["expected_sha256"], info["native_sha256"])
        self.assertEqual(info["model_forward_count"], 1)
        self.assertEqual(info["expected_sha256"], info["model_forward_sha256"])
        self.assertNotIn("hidden-a", json.dumps(result["raw_output"]["native_result"]))

    def test_overlong_or_control_token_is_unsupported_before_forward(self):
        for value in ({**VALUE, "context": "x" * 4096},
                      {**VALUE, "question": "<|im_end|>"},
                      {**VALUE, "question": "<image>"}):
            with self.subTest(question=value["question"][:12]):
                model, result = self.predict(value)
                self.assertEqual(result["status"], "unsupported")
                self.assertEqual(result["error"], "small_model_context_overflow")
                self.assertFalse(result["raw_output"]["forward_executed"])
                self.assertEqual(model.engine.forward_calls, 0)

    def test_native_token_mismatch_and_invalid_distribution_are_errors(self):
        model, mismatch = self.predict(mismatch=True)
        self.assertEqual(mismatch["error"], "small_model_forward_encoding_mismatch")
        self.assertEqual(model.engine.forward_calls, 0)
        model, invalid = self.predict(invalid=True)
        self.assertEqual(invalid["error"], "small_model_distribution_invalid")
        self.assertEqual(model.engine.forward_calls, 1)

    def test_annotations_are_not_candidate_input(self):
        model = FakeModel()
        annotated = {**VALUE, "expected_choice": "hidden-a"}
        with self.assertRaises(ValueError):
            backend.LiquidD1Backend(model).predict(annotated)
        self.assertEqual(model.engine.forward_calls, 0)

    def test_initialize_rejects_wrong_parameter_count_or_device(self):
        local = "/tmp/pinned-liquid-d1-stub"
        fp32 = object()
        torch = ModuleType("torch")
        torch.float32 = fp32
        torch.set_num_threads = lambda _: None
        torch.set_num_interop_threads = lambda _: None
        transformers = ModuleType("transformers")

        class D1Model:
            def __init__(self, count, device):
                self.config = SimpleNamespace(model_type="lfm2_vl",
                                              text_config=SimpleNamespace(max_position_embeddings=32768))
                self.name_or_path = local
                self.parameter = SimpleNamespace(numel=lambda: count,
                                                 device=SimpleNamespace(type=device), dtype=fp32)
                tied = object()
                self.lm_head = SimpleNamespace(weight=tied)
                self.model = SimpleNamespace(language_model=SimpleNamespace(
                    embed_tokens=SimpleNamespace(weight=tied)))
                self.engine = SimpleNamespace(device=SimpleNamespace(type="cpu"), model=self,
                                              tokenizer=SimpleNamespace(name_or_path=local),
                                              system="none", state_style="json_only",
                                              option_style="desc", lead="", calibration=None)

            def parameters(self):
                return iter((self.parameter,))

            def to(self, _device):
                return self

            def eval(self):
                return self

            def tie_weights(self):
                return None

        config = {"mode": "liquid3", "max_length": 4096, "threads": 2,
                  "local_dir": local, "pins": {}}
        with patch.dict(sys.modules, {"torch": torch, "transformers": transformers}):
            for count, device in ((1, "cpu"), (3123483888, "cuda")):
                with self.subTest(count=count, device=device):
                    transformers.AutoModel = SimpleNamespace(
                        from_pretrained=lambda *_args, **_kwargs: D1Model(count, device))
                    with self.assertRaisesRegex(ValueError, "small_model_identity_invalid"):
                        backend.initialize(config)
            transformers.AutoModel = SimpleNamespace(
                from_pretrained=lambda *_args, **_kwargs: D1Model(3123483888, "cpu"))
            with patch.object(backend, "_rss", return_value=100.0):
                ready = backend.initialize(config).ready()
            self.assertEqual(ready["device"], "cpu")
            self.assertEqual(ready["dtype"], "float32")


def _blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class LiquidAssetsTests(unittest.TestCase):
    def test_pinned_snapshot_sources_and_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model = root / "snapshot"
            model.mkdir()
            siblings = []
            for name in ("model.safetensors", "config.json", *prepare.SOURCES):
                content = (name + " pinned bytes").encode()
                (model / name).write_bytes(content)
                item = {"rfilename": name, "size": len(content)}
                if name == "model.safetensors":
                    item["lfs"] = {"sha256": hashlib.sha256(content).hexdigest(),
                                   "size": len(content)}
                else:
                    item["blobId"] = _blob(content)
                siblings.append(item)
            metadata = root / "metadata.json"
            metadata.write_text(json.dumps({"id": prepare.REPO, "sha": prepare.REVISION,
                                            "siblings": siblings}))
            sources, output = root / "sources", root / "output"
            result = prepare.prepare(model, metadata, sources, output)
            self.assertFalse(result["inference"])
            self.assertEqual(result["source_files"], len(prepare.SOURCES))
            self.assertEqual({path.name for path in sources.iterdir()}, set(prepare.SOURCES))
            self.assertFalse((sources / "model.safetensors").exists())
            self.assertEqual(json.loads((output / "liquid3-assets.json").read_text())["revision"],
                             prepare.REVISION)
            # Wrong publisher identity must fail without creating outputs.
            wrong = root / "wrong.json"
            wrong.write_text(json.dumps({"id": prepare.REPO, "sha": "0" * 40,
                                         "siblings": siblings}))
            with self.assertRaises(ValueError):
                prepare.prepare(model, wrong, root / "new-sources", root / "new-output")
            self.assertFalse((root / "new-output").exists())


if __name__ == "__main__":
    unittest.main()
