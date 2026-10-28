"""Offline asset verification with genuine Git/LFS digests and tiny tensor bytes."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_vela3_fast", ROOT / "scripts/prepare-vela3-fast-assets.py")
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


def tensor_bytes(*, dtype="F32", count=2, scalar=True, bad_range=False):
    """Two vector values and one real scalar exercise the published count policy."""
    width = {"F32": 4, "F16": 2}[dtype]
    vector_size = count * width
    header = {"__metadata__": {"format": "pt"},
              "vector": {"dtype": dtype, "shape": [count], "data_offsets": [0, vector_size]}}
    if scalar:
        header["log_tau"] = {"dtype": dtype, "shape": [],
                             "data_offsets": [vector_size, vector_size + width]}
    payload = b"\0" * (vector_size + int(scalar) * width)
    if bad_range:
        header["vector"]["data_offsets"][1] += width
    encoded = json.dumps(header, separators=(",", ":")).encode()
    return len(encoded).to_bytes(8, "little") + encoded + payload


def publisher_item(name, data, *, lfs=False):
    item = {"rfilename": name, "size": len(data)}
    if lfs:
        item["lfs"] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    else:
        item["blobId"] = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    return item


class Vela3FastAssetPreparationTests(unittest.TestCase):
    def fixture(self, root, *, weights=None):
        snapshot = root / "snapshot"
        snapshot.mkdir()
        contents = {name: ("reviewed synthetic bytes: " + name + "\n").encode()
                    for name in PREPARE.REQUIRED - {"model.safetensors"}}
        contents["model.safetensors"] = tensor_bytes() if weights is None else weights
        contents["README.md"] = b"Synthetic publisher card; never executed.\n"
        for name, data in contents.items():
            (snapshot / name).write_bytes(data)
        # Optional adapter heads are published but deliberately not downloaded.
        siblings = [publisher_item(name, data, lfs=name.endswith(".safetensors"))
                    for name, data in sorted(contents.items())]
        siblings.append(publisher_item("span_head.safetensors", b"not downloaded", lfs=True))
        metadata = {"id": PREPARE.REPO_ID, "sha": PREPARE.REVISION, "siblings": siblings}
        path = root / "metadata.json"
        path.write_text(json.dumps(metadata))
        return snapshot, path, contents

    @contextmanager
    def reviewed_fixture(self, contents):
        # Adapt only the fixed published identity to this tiny fixture. The real
        # publisher parser, byte digests and safetensors validator are untouched.
        sha = lambda name: hashlib.sha256(contents[name]).hexdigest()
        with patch.object(PREPARE, "WEIGHT_SIZE", len(contents["model.safetensors"])), \
                patch.object(PREPARE, "WEIGHT_SHA256", sha("model.safetensors")), \
                patch.object(PREPARE, "TENSOR_ELEMENTS", 3), \
                patch.object(PREPARE, "OFFICIAL_HELPERS", {name: sha(name) for name in PREPARE.OFFICIAL_HELPERS}), \
                patch.object(PREPARE, "OFFICIAL_METADATA", {name: sha(name) for name in PREPARE.OFFICIAL_METADATA}):
            yield

    def assert_refused(self, snapshot, metadata, output):
        with self.assertRaises(ValueError):
            PREPARE.prepare(snapshot, metadata, output)
        self.assertFalse(output.exists())

    def test_real_git_lfs_and_scalar_counts_create_exact_manifest_without_optional_heads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot, metadata, contents = self.fixture(root)
            output = root / "new/manifest.json"
            with self.reviewed_fixture(contents):
                manifest = PREPARE.prepare(snapshot, metadata, output)
            self.assertEqual(json.loads(output.read_text()), manifest)
            self.assertEqual(set(manifest), {"schema_version", "repo_id", "revision", "files"})
            self.assertEqual(manifest["repo_id"], PREPARE.REPO_ID)
            self.assertEqual(manifest["revision"], PREPARE.REVISION)
            self.assertEqual([item["path"] for item in manifest["files"]], sorted(contents))
            for item in manifest["files"]:
                self.assertEqual(item["sha256"], hashlib.sha256(contents[item["path"]]).hexdigest())
                self.assertEqual(item["size"], len(contents[item["path"]]))
            self.assertNotIn("span_head.safetensors", {item["path"] for item in manifest["files"]})
            before = output.read_bytes()
            with self.reviewed_fixture(contents), self.assertRaises(ValueError):
                PREPARE.prepare(snapshot, metadata, output)
            self.assertEqual(output.read_bytes(), before)

    def test_destinations_must_be_new_outside_snapshot_and_not_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot, metadata, contents = self.fixture(root)
            existing = root / "existing.json"
            existing.write_bytes(b"original archive")
            symlink = root / "link.json"
            symlink.symlink_to(existing)
            with self.reviewed_fixture(contents):
                for output in (existing, symlink, snapshot / "manifest.json"):
                    with self.subTest(output=output), self.assertRaises(ValueError):
                        PREPARE.prepare(snapshot, metadata, output)
            self.assertEqual(existing.read_bytes(), b"original archive")
            self.assertFalse((snapshot / "manifest.json").exists())

    def test_wrong_revision_repo_duplicate_paths_and_forged_publisher_metadata_are_refused(self):
        changes = (lambda m: m.update(sha="0" * 40), lambda m: m.update(id="unknown/model"),
                   lambda m: m["siblings"].append(deepcopy(m["siblings"][0])),
                   lambda m: m["siblings"][0].update(rfilename="../escape"),
                   lambda m: m["siblings"][0].pop("blobId"),
                   lambda m: m["siblings"][0].update(blobId="0" * 40),
                   lambda m: next(i for i in m["siblings"] if i["rfilename"] == "model.safetensors")["lfs"].update(sha256="a" * 64))
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                snapshot, metadata, contents = self.fixture(root)
                value = json.loads(metadata.read_text())
                change(value)
                metadata.write_text(json.dumps(value))
                with self.reviewed_fixture(contents):
                    self.assert_refused(snapshot, metadata, root / "manifest.json")

    def test_changed_git_or_lfs_bytes_fail_real_digest_checks(self):
        for name in ("config.json", "model.safetensors"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                snapshot, metadata, contents = self.fixture(root)
                original = (snapshot / name).read_bytes()
                (snapshot / name).write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
                with self.reviewed_fixture(contents):
                    self.assert_refused(snapshot, metadata, root / "manifest.json")

    def test_reauthored_metadata_cannot_authorize_changed_official_helpers_or_tokenizer(self):
        for name in ("vela3_encoder.py", "config.json", "tokenizer_config.json", "tokenizer.json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                snapshot, metadata, contents = self.fixture(root)
                changed = (snapshot / name).read_bytes().replace(b"reviewed", b"tampered")
                (snapshot / name).write_bytes(changed)
                value = json.loads(metadata.read_text())
                item = next(i for i in value["siblings"] if i["rfilename"] == name)
                item.update(publisher_item(name, changed))
                metadata.write_text(json.dumps(value))
                with self.reviewed_fixture(contents):
                    self.assert_refused(snapshot, metadata, root / "manifest.json")

    def test_extra_adapter_weights_sources_missing_required_and_symlinks_are_refused(self):
        for mode in ("extra_weight", "extra_source", "missing_tokenizer", "symlink"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                snapshot, metadata, contents = self.fixture(root)
                if mode == "extra_weight":
                    (snapshot / "span_head.safetensors").write_bytes(b"not downloaded")
                elif mode == "extra_source":
                    (snapshot / "unreviewed.py").write_text("raise RuntimeError('must never execute')\n")
                elif mode == "missing_tokenizer":
                    (snapshot / "tokenizer.json").unlink()
                else:
                    outside = root / "outside.py"
                    outside.write_bytes((snapshot / "vela3_encoder.py").read_bytes())
                    (snapshot / "vela3_encoder.py").unlink()
                    (snapshot / "vela3_encoder.py").symlink_to(outside)
                with self.reviewed_fixture(contents):
                    self.assert_refused(snapshot, metadata, root / "manifest.json")

    def test_real_safetensors_validation_refuses_wrong_dtype_count_or_byte_ranges(self):
        cases = (tensor_bytes(dtype="F16"), tensor_bytes(count=3), tensor_bytes(scalar=False),
                 tensor_bytes(bad_range=True), b"invalid prefix")
        for weights in cases:
            with self.subTest(size=len(weights)), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                snapshot, metadata, contents = self.fixture(root, weights=weights)
                with self.reviewed_fixture(contents):
                    self.assert_refused(snapshot, metadata, root / "manifest.json")


if __name__ == "__main__":
    unittest.main()
