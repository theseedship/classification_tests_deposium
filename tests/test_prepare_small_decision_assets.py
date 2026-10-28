"""Offline snapshot verification tests with tiny stand-ins for model weights."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare-small-decision-assets.py"
spec = importlib.util.spec_from_file_location("prepare_small_decision_assets", SCRIPT)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def _blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class PrepareSmallDecisionAssetsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def fixture(self, mode):
        repo, revision, sources, _ = prepare.MODELS[mode]
        model = self.root / "snapshot"
        model.mkdir()
        indexed = {}
        for name in ("model.safetensors", "config.json", *sources):
            payload = (name + " exact publisher bytes\n").encode()
            (model / name).write_bytes(payload)
            item = {"rfilename": name, "size": len(payload)}
            if name == "model.safetensors":
                item["lfs"] = {"sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
            else:
                item["blobId"] = _blob(payload)
            indexed[name] = item
        metadata = self.root / "hub.json"
        metadata.write_text(json.dumps({"id": repo, "sha": revision, "siblings": list(indexed.values())}))
        source = self.root / "source" if sources else None
        output = self.root / "out"
        return model, metadata, source, output

    def test_all_modes_emit_exact_manifest_and_only_small_source_copies(self):
        for mode in prepare.MODELS:
            with self.subTest(mode=mode):
                with tempfile.TemporaryDirectory() as folder:
                    self.root = Path(folder)
                    model, metadata, source, output = self.fixture(mode)
                    # Hub snapshots often include ignored cache metadata.
                    (model / ".cache").mkdir()
                    (model / ".cache" / "ignored").write_text("cache")
                    (model / ".git").write_text("gitdir: elsewhere\n")
                    result = prepare.prepare(mode, model, metadata, source, output)
                    self.assertFalse(result["inference"])
                    _, revision, sources, stem = prepare.MODELS[mode]
                    manifest = json.loads((output / (stem + "-assets.json")).read_text())
                    self.assertEqual(manifest["revision"], revision)
                    self.assertEqual({item["path"] for item in manifest["files"]},
                                     {"model.safetensors", "config.json", *sources})
                    if sources:
                        self.assertEqual({path.name for path in source.iterdir()}, set(sources))
                        self.assertFalse((source / "model.safetensors").exists())
                        source_manifest = json.loads((output / (stem + "-source-assets.json")).read_text())
                        self.assertEqual({item["path"] for item in source_manifest["files"]}, set(sources))
                    else:
                        self.assertFalse(any("source" in path.name for path in output.iterdir()))

    def test_changed_weight_and_source_are_rejected(self):
        for name in ("model.safetensors", "model.py"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)
                model, metadata, source, output = self.fixture("muose")
                path = model / name
                path.write_bytes(b"z" * path.stat().st_size)
                with self.assertRaisesRegex(ValueError, "mismatch"):
                    prepare.prepare("muose", model, metadata, source, output)
                self.assertFalse(output.exists())

    def test_wrong_identity_missing_file_and_extra_file_are_rejected(self):
        for kind in ("identity", "missing", "extra"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)
                model, metadata, source, output = self.fixture("kai")
                if kind == "identity":
                    value = json.loads(metadata.read_text())
                    value["sha"] = "0" * 40
                    metadata.write_text(json.dumps(value))
                elif kind == "missing":
                    (model / "config.json").unlink()
                else:
                    (model / "extra.txt").write_text("unlisted")
                with self.assertRaises(ValueError):
                    prepare.prepare("kai", model, metadata, source, output)
                self.assertFalse(output.exists())

    def test_missing_blob_metadata_and_symlinks_are_rejected(self):
        for kind in ("blob", "file_link", "directory_link"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)
                model, metadata, source, output = self.fixture("modernjev")
                if kind == "blob":
                    value = json.loads(metadata.read_text())
                    value["siblings"][1].pop("blobId")
                    metadata.write_text(json.dumps(value))
                elif kind == "file_link":
                    (model / "link.py").symlink_to(model / "predict.py")
                else:
                    (model / ".cache").symlink_to(self.root)
                with self.assertRaises(ValueError):
                    prepare.prepare("modernjev", model, metadata, source, output)
                self.assertFalse(output.exists())

    def test_source_option_and_fresh_destinations(self):
        model, metadata, source, output = self.fixture("muose")
        with self.assertRaises(ValueError):
            prepare.prepare("muose", model, metadata, None, output)
        output.mkdir()
        with self.assertRaises(FileExistsError):
            prepare.prepare("muose", model, metadata, source, output)


if __name__ == "__main__":
    unittest.main()
