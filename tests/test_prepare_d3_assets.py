"""Reject malformed checkpoint headers without loading any model."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("d3_asset_preparer", ROOT / "scripts/prepare-d3-assets.py")
preparer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparer)


class D3HeaderTests(unittest.TestCase):
    def write(self, header, data=b"\0" * 8):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "weights.safetensors"
        raw = header if isinstance(header, bytes) else json.dumps(header).encode()
        path.write_bytes(len(raw).to_bytes(8, "little") + raw + data)
        return path

    def test_scalars_count_as_one_element(self):
        p = self.write({"scalar": {"dtype": "F32", "shape": [], "data_offsets": [0, 4]},
                        "vector": {"dtype": "BF16", "shape": [2], "data_offsets": [4, 8]}})
        self.assertEqual(preparer.tensor_counts(p), {"F32": 1, "BF16": 2})

    def test_inconsistent_or_overlapping_ranges_rejected(self):
        for shape, bounds in (([3], [0, 4]), ([1], [0, 9]), ([True], [0, 4])):
            with self.subTest(shape=shape, bounds=bounds):
                p = self.write({"x": {"dtype": "F32", "shape": shape, "data_offsets": bounds}})
                with self.assertRaises(ValueError):
                    preparer.tensor_counts(p)
        p = self.write({"x": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]},
                        "y": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}})
        with self.assertRaises(ValueError):
            preparer.tensor_counts(p)

    def test_duplicate_keys_and_unbounded_header_rejected(self):
        p = self.write(b'{"x":{},"x":{}}')
        with self.assertRaises(ValueError):
            preparer.tensor_counts(p)
        p.write_bytes((16 * 1024 * 1024 + 1).to_bytes(8, "little"))
        with self.assertRaises(ValueError):
            preparer.tensor_counts(p)

    def test_all_shards_are_counted_and_missing_or_extra_weights_rejected(self):
        for mode in ("mini", "flash"):
            names = preparer.WEIGHT_FILES[mode]
            selected = set(names) | {"readout.safetensors"}
            counts = {name: {"BF16": 2} for name in names}
            counts["readout.safetensors"] = {"F32": 255 * preparer.HIDDEN[mode]}
            def read(path):
                return counts[Path(path).name]
            with self.subTest(mode=mode), patch.object(preparer, "tensor_counts", side_effect=read) as reader, patch.dict(preparer.BACKBONE_ELEMENTS, {mode: 2 * len(names)}):
                self.assertEqual(preparer.reviewed_tensor_counts(mode, Path("unused"), selected), counts)
                self.assertEqual(reader.call_count, len(names) + 1)
                for wrong in (selected - {names[-1]}, selected | {"extra.safetensors"}):
                    with self.assertRaises(ValueError):
                        preparer.reviewed_tensor_counts(mode, Path("unused"), wrong)
                counts[names[-1]] = {"F16": 2}
                with self.assertRaises(ValueError):
                    preparer.reviewed_tensor_counts(mode, Path("unused"), selected)

    def test_correct_head_cannot_hide_incomplete_backbone(self):
        names = preparer.WEIGHT_FILES["mini"]
        counts = {name: {"BF16": 2} for name in names}
        counts["readout.safetensors"] = {"F32": 255 * preparer.HIDDEN["mini"]}
        with patch.object(preparer, "tensor_counts", side_effect=lambda path: counts[Path(path).name]):
            with self.assertRaises(ValueError):
                preparer.reviewed_tensor_counts("mini", Path("unused"), set(counts))
