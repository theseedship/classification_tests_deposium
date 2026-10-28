"""Nox4 asset preparation checks without model code or weights."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_decision2", ROOT / "scripts/prepare-decision2-assets.py")
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


class NoxAssetPreparationTests(unittest.TestCase):
    def fixture(self, root):
        snapshot = root / "snapshot"
        snapshot.mkdir()
        payload = b"pinned upstream bytes\n"
        (snapshot / "config.json").write_bytes(payload)
        blob = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
        metadata = {"id": PREPARE.REPO_ID, "sha": PREPARE.REVISION, "siblings": [
            {"rfilename": "config.json", "size": len(payload), "blobId": blob}]}
        path = root / "metadata.json"
        path.write_text(json.dumps(metadata))
        return snapshot, path

    def test_exact_pinned_snapshot_generates_new_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot, metadata = self.fixture(root)
            output = root / "assets.json"
            receipt = PREPARE.prepare(snapshot, metadata, output)
            manifest = json.loads(output.read_text())
            self.assertEqual((manifest["repo_id"], manifest["revision"]),
                             (PREPARE.REPO_ID, PREPARE.REVISION))
            self.assertEqual(receipt["verified_files"], 1)
            self.assertFalse(receipt["inference"])
            with self.assertRaises(FileExistsError):
                PREPARE.prepare(snapshot, metadata, output)

    def test_changed_revision_bytes_and_extra_file_are_rejected(self):
        for mutation in ("revision", "bytes", "extra"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                snapshot, metadata = self.fixture(root)
                if mutation == "revision":
                    data = json.loads(metadata.read_text())
                    data["sha"] = "0" * 40
                    metadata.write_text(json.dumps(data))
                elif mutation == "bytes":
                    (snapshot / "config.json").write_bytes(b"changed upstream bytes\n")
                else:
                    (snapshot / "unverified.py").write_text("pass\n")
                output = root / "assets.json"
                with self.assertRaises(ValueError):
                    PREPARE.prepare(snapshot, metadata, output)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
