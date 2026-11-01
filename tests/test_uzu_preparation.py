"""Uzu preparation receipt from a fake helper: no model, weights, Rust build or network."""
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_uzu_inputs", ROOT / "scripts/prepare-uzu-inputs.py")
prep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prep)

FAKE = r'''#!{python}
import json, sys
for line in sys.stdin:
    row = json.loads(line)
    body = json.loads(row["native_request_json"])
    n = len(body["state"].split()) + 3
    print(json.dumps({{"case_id": row["case_id"], "status": "prepared", "token_ids": list(range(n)), "error": None}}))
'''


class UzuPreparationTests(unittest.TestCase):
    def test_receipt_binds_every_request_and_a_refused_overflow(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "results").mkdir()
            helper = root / "helper"
            helper.write_text(FAKE.format(python=sys.executable))
            helper.chmod(helper.stat().st_mode | stat.S_IXUSR)
            assets = root / "assets.json"
            assets.write_text("{}")
            args = prep.argparse.Namespace(helper=helper, pack=root, assets_manifest=assets,
                                           dataset=ROOT / "datasets/facade-routing-v1/cases.jsonl",
                                           output=root / "results/prep", model_id="pack-test", max_tokens=4096)
            with patch.object(prep, "ROOT", root), patch.object(prep, "verify_pack", lambda *a: {}):
                summary = prep.prepare(args)
            receipt = json.loads((root / "results/prep/preparation.json").read_text())
            self.assertEqual(summary["requests"], 80)
            self.assertEqual(receipt["renderer"], "hanashi::decision::DecisionEncoding")
            self.assertGreater(receipt["overflow_control"]["input_tokens"], 4096)
            self.assertEqual(receipt["assets_sha256"], hashlib.sha256(b"{}").hexdigest())
            self.assertFalse(receipt["weights_loaded"] or receipt["forward_executed"])


if __name__ == "__main__":
    unittest.main()
