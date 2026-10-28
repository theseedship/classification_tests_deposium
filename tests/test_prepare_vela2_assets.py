import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_vela2", ROOT / "scripts/prepare-vela2-assets.py")
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


class VelaAssetPreparationTests(unittest.TestCase):
    def fixture(self, root, mode="03"):
        snapshot = root / "snapshot"
        snapshot.mkdir()
        data = b"publisher bytes\n"
        (snapshot / "config.json").write_bytes(data)
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        metadata = {"id": PREPARE.MODELS[mode][0], "sha": PREPARE.MODELS[mode][1],
                    "siblings": [{"rfilename": "config.json", "size": len(data), "blobId": blob},
                                 {"rfilename": "onnx/model.onnx", "size": 8,
                                  "lfs": {"size": 8, "sha256": hashlib.sha256(b"12345678").hexdigest()
                                          if mode == "4" else "a" * 64}}]}
        meta = root / "metadata.json"
        meta.write_text(json.dumps(metadata))
        return snapshot, meta

    def test_selected_torch_inventory_excludes_onnx_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot, meta = self.fixture(root)
            output = root / "manifest.json"
            receipt = PREPARE.prepare("03", snapshot, meta, output)
            self.assertEqual(receipt["excluded_files"], ["onnx/model.onnx"])
            self.assertFalse(receipt["inference"])
            manifest = json.loads(output.read_text())
            self.assertEqual([item["path"] for item in manifest["files"]], ["config.json"])
            before = output.read_bytes()
            with self.assertRaises(FileExistsError):
                PREPARE.prepare("03", snapshot, meta, output)
            self.assertEqual(output.read_bytes(), before)

    def test_changed_bytes_and_extra_source_refused_before_manifest(self):
        for mutation in ("changed", "extra"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                snapshot, meta = self.fixture(root)
                if mutation == "changed":
                    path = snapshot / "config.json"
                    path.write_bytes(b"X" + path.read_bytes()[1:])
                else:
                    (snapshot / "unverified.py").write_text("raise RuntimeError()\n")
                output = root / "manifest.json"
                with self.assertRaises(ValueError):
                    PREPARE.prepare("03", snapshot, meta, output)
                self.assertFalse(output.exists())

    def test_vela4_pinned_metadata_and_exact_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot, meta = self.fixture(root, "4")
            # Vela4 has no ONNX exclusion: every published file must be present.
            (snapshot / "onnx").mkdir()
            (snapshot / "onnx/model.onnx").write_bytes(b"12345678")
            output = root / "vela4-assets.json"
            receipt = PREPARE.prepare("4", snapshot, meta, output)
            self.assertEqual(receipt["excluded_files"], [])
            self.assertEqual(receipt["repo_id"], "vllm-sr/Vela-2.0-4B")
            self.assertEqual(len(json.loads(output.read_text())["files"]), 2)
            with self.assertRaises(FileExistsError):
                PREPARE.prepare("4", snapshot, meta, output)


if __name__ == "__main__":
    unittest.main()
