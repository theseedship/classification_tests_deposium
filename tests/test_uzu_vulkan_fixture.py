"""Offline integrity controls for the synthetic fixture, without Uzu or weights."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("uzu_vulkan_fixture", Path(__file__).resolve().parents[1] / "native/uzu-vulkan-probe/generate_fixture.py")
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        (self.root / ".gitignore").write_text("results/\n")
        patcher = patch.object(fixture, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.output = self.root / "results" / "synthetic"

    def test_deterministic_archives_and_hashes(self):
        fixture.generate(self.output)
        second = self.root / "results" / "second"
        fixture.generate(second)
        for name in ("config.json", "tokenizer.json", "model.safetensors", "fixture.json"):
            self.assertEqual((self.output / name).read_bytes(), (second / name).read_bytes())
        receipt = json.loads((self.output / "fixture.json").read_text())
        for name, digest in receipt["files_sha256"].items():
            self.assertEqual(hashlib.sha256((self.output / name).read_bytes()).hexdigest(), digest)
        self.assertEqual(receipt["cases_scored"], 0)
        self.assertEqual(receipt["campaign"], "not_run")
        self.assertIsNone(receipt["expected_probabilities"])
        self.assertNotIn(str(self.root), json.dumps(receipt))
        self.assertEqual(receipt["inputs"], [[0], [1], [0, 1], [1, 0]])
        self.assertEqual([x["expected_error"] for x in receipt["negative_controls"]],
                         ["EmptyInput", "InvalidOptionCount", "InvalidOptionCount"])

    def test_safetensors_layout_dimensions_and_bf16_values(self):
        data = fixture.safetensors_bytes()
        length = struct.unpack("<Q", data[:8])[0]
        self.assertEqual(length % 8, 0)
        header = json.loads(data[8:8 + length])
        payload = data[8 + length:]
        metadata = header.pop("__metadata__")
        self.assertEqual(len(header), 6)
        self.assertEqual(len(metadata), 6)
        position = 0
        decoded = {}
        for name, dtype, shape, values in fixture.tensors():
            descriptor = header[name]
            start, end = descriptor["data_offsets"]
            self.assertEqual(start, position)
            self.assertEqual(descriptor["shape"], shape)
            self.assertEqual(descriptor["dtype"], dtype)
            count = shape[0] * shape[1]
            self.assertEqual(end - start, count * (2 if dtype == "BF16" else 4))
            if dtype == "BF16":
                actual = [struct.unpack("<f", b"\0\0" + payload[i:i + 2])[0] for i in range(start, end, 2)]
            else:
                actual = list(struct.unpack("<" + "f" * count, payload[start:end]))
            self.assertEqual(actual, values)
            self.assertTrue(any(actual))
            decoded[name] = actual
            spec = json.loads(metadata[name.removesuffix("weights") + "spec"])
            self.assertEqual(spec["type"], "FullPrecisionSpec")
            self.assertEqual(spec["layout"], "input_output" if "input_embedding" in name else "output_input")
            position = end
        self.assertEqual(position, len(payload))
        embedding = decoded["decoder.embedding.input_embedding.weights"]
        self.assertEqual(embedding[:64], [-x for x in embedding[64:]])
        readout = decoded["decoder.embedding.output_embedding.weights"]
        self.assertNotEqual(readout[:64], readout[64:])

    def test_real_layer_initializes_shortcut_and_dimensions_match(self):
        config = fixture.config()
        decoder = config["decoder_config"]
        self.assertEqual(decoder["vocab_size"], 2)
        transformer = decoder["transformer_config"]
        self.assertEqual(transformer["model_dim"], 64)
        self.assertEqual(transformer["hidden_dim"], 64)
        self.assertEqual(len(transformer["layer_configs"]), 1)
        layer = transformer["layer_configs"][0]
        self.assertIsNotNone(layer["pre_mixer_norm_config"])
        self.assertEqual(layer["mixer_config"]["head_dim"], 64)
        self.assertEqual(layer["mixer_config"]["num_heads"], 1)
        self.assertEqual(layer["mixer_config"]["num_groups"], 1)
        self.assertEqual(layer["mlp_config"]["type"], "DenseMLPConfig")
        self.assertIsNone(layer["rope_config"])
        self.assertEqual(config["token_codec_config"], {"type": "RawTextCodecConfig"})
        self.assertEqual(config["decision"]["codes"], ["a", "b"])
        self.assertEqual(set(config["generation_config"]), {"stop_token_ids", "temperature", "top_k", "top_p", "min_p", "banned_tokens", "repetition_penalty", "presence_penalty", "frequency_penalty", "suffix_repetition_length"})

    def test_tokenizer_covers_direct_id_inputs(self):
        fixture.generate(self.output)
        tokenizer = json.loads((self.output / "tokenizer.json").read_text())
        self.assertEqual(set(tokenizer["model"]["vocab"].values()), {0, 1})
        self.assertEqual(tokenizer["model"]["type"], "WordLevel")

    def test_overwrite_refused_and_original_preserved(self):
        fixture.generate(self.output)
        original = (self.output / "model.safetensors").read_bytes()
        with self.assertRaisesRegex(ValueError, "output_already_exists"):
            fixture.generate(self.output)
        self.assertEqual(original, (self.output / "model.safetensors").read_bytes())

    def test_outside_results_refused(self):
        with self.assertRaisesRegex(ValueError, "output_must_be_new_directory_under_results"):
            fixture.generate(self.root / "public")

    def test_symlink_escape_refused(self):
        (self.root / "results").mkdir()
        (self.root / "results" / "escape").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "output_must_be_new_directory_under_results"):
            fixture.generate(self.root / "results" / "escape" / "public")

    def test_unignored_output_refused(self):
        (self.root / ".gitignore").write_text("")
        with self.assertRaisesRegex(ValueError, "output_not_ignored"):
            fixture.generate(self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
