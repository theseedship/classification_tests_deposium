import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("vulkan_probe_builder", ROOT / "scripts/build-uzu-vulkan-probe.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class VulkanProbeBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "Cargo.toml").write_text('[workspace.package]\nedition="2024"\n'
            '[workspace.dependencies]\nash="0.38.0"\ntokio="1.53.3"\nserde_json="1.0"\n')
        (self.source / "Cargo.lock").write_text("# synthetic lockfile\nversion = 4\n")
        self.output = self.root / "results" / "probe"

    def identity(self, command, cwd):
        self.assertEqual(cwd, self.source)
        if command[1] == "rev-parse":
            return builder.REVISION
        if command[1] == "remote":
            return builder.REPOSITORY
        return ""

    def test_preparation_retains_lock_and_pin_without_build_or_inference(self):
        with patch.object(builder, "ROOT", self.root), patch.object(builder, "captured", self.identity):
            result = builder.prepare(self.source, self.output)
        self.assertEqual(result["status"], "prepared_not_built")
        self.assertEqual((self.output / "Cargo.lock").read_bytes(), (self.source / "Cargo.lock").read_bytes())
        record = json.loads((self.output / "preparation.json").read_text())
        self.assertEqual(record["uzu_revision"], builder.REVISION)
        self.assertFalse(record["inference_run"])
        self.assertFalse(record["model_loaded"])
        self.assertEqual(record["helper_source_sha256"], builder.digest(builder.HELPER))
        manifest = (self.output / "Cargo.toml").read_text()
        self.assertIn('default-features = false', manifest)
        self.assertIn('features = ["vulkan"]', manifest)
        self.assertFalse((self.output / "target").exists())

    def test_identity_mismatch_and_dirty_source_refuse_output(self):
        for field in ("rev-parse", "remote", "status"):
            def altered(command, cwd):
                return "wrong" if command[1] == field else self.identity(command, cwd)
            with self.subTest(field=field), patch.object(builder, "ROOT", self.root), \
                    patch.object(builder, "captured", altered), self.assertRaises(ValueError):
                builder.prepare(self.source, self.output)
            self.assertFalse(self.output.exists())

    def test_existing_or_outside_results_output_refused(self):
        existing = self.root / "results" / "existing"
        existing.mkdir(parents=True)
        for output in (existing, self.root / "outside"):
            with patch.object(builder, "ROOT", self.root), self.assertRaises(ValueError):
                builder.prepare(self.source, output)


if __name__ == "__main__":
    unittest.main()
