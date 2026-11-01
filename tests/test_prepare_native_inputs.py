"""Native preparation driver with a fake vocabulary-only helper: no model, weights or network."""
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
SPEC = importlib.util.spec_from_file_location("prepare_native_inputs", ROOT / "scripts/prepare-native-inputs.py")
prep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prep)

FAKE_HELPER = r'''#!{python}
import hashlib, json, sys
args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
failed = False
for line in sys.stdin:
    row = json.loads(line)
    body = row["native_request_json"].encode()
    keys = sorted(json.loads(body)["questions"]["answer"]["criteria"], key=lambda k: int(k[1:]))
    over = row["case_id"] == "synthetic-native-overflow"
    tokens = [1] * (int(args["--max-tokens"]) + 1 if over else 3)
    failed |= over
    print(json.dumps({{"schema_version": "deposium.native-systemone-encoding/v1",
        "source_revision": "{pin}", "decision_type": args["--decision-type"], "case_id": row["case_id"],
        "status": "unsupported" if over else "within_limit", "max_tokens": int(args["--max-tokens"]),
        "vocab_only": True, "weights_loaded": False, "inference_context_created": False,
        "forward_executed": False, "native_input_prepared": True, "variant_count": 1,
        "request_body_sha256": hashlib.sha256(body).hexdigest(), "request_body_bytes": len(body),
        "variants": [{{"index": 0, "token_count": len(tokens), "token_ids": tokens,
            "token_ids_sha256": hashlib.sha256(json.dumps(tokens, separators=(",", ":")).encode()).hexdigest(),
            "within_limit": not over, "option_keys": keys}}]}}))
sys.exit(2 if failed else 0)
'''


class PrepareNativeInputsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "results").mkdir()
        self.model = self.root / "fixture-Q8_0.gguf"
        self.model.write_bytes(b"not a real model")
        self.assets = self.root / "assets.json"
        self.assets.write_text(json.dumps({"schema_version": "deposium.model-assets/v1", "repo_id": "fixture/model-GGUF",
            "revision": "a" * 40, "files": [{"path": self.model.name, "size": self.model.stat().st_size,
                                             "sha256": hashlib.sha256(self.model.read_bytes()).hexdigest()}]}))
        self.helper = self.root / "fake-helper"
        self.helper.write_text(FAKE_HELPER.format(python=sys.executable, pin=prep.upstream.PIN))
        self.helper.chmod(self.helper.stat().st_mode | stat.S_IXUSR)

    def args(self, dataset, output="results/prep"):
        return prep.parser().parse_args(["--helper", str(self.helper), "--model", str(self.model),
            "--assets-manifest", str(self.assets), "--dataset", str(ROOT / dataset),
            "--model-id", "fixture-q8", "--output", str(self.root / output), "--min-free-mb", "1"])

    def run_prepare(self, args):
        args.technical_only = False
        with patch.object(prep, "ROOT", self.root):
            return prep.prepare(args)

    def test_eight_option_pack_is_prepared_and_bound_by_the_launcher_validator(self):
        summary = self.run_prepare(self.args("datasets/facade-routing-v1/cases.jsonl"))
        self.assertEqual((summary["prepared_inputs"], summary["max_tokens"]), (80, 3))
        self.assertFalse(summary["weights_loaded"] or summary["forward_executed"])
        audit = self.root / "results/prep/native-preparation.jsonl"
        rows = [json.loads(line) for line in audit.read_text().splitlines()]
        self.assertEqual(rows[-1]["case_id"], "synthetic-native-overflow")
        self.assertEqual(len(rows[0]["variants"][0]["option_keys"]), 8)

    def test_refuses_existing_output_outside_results_and_changed_model(self):
        with self.assertRaisesRegex(ValueError, "new_local_output"):
            self.run_prepare(self.args("datasets/facade-routing-v1/cases.jsonl", output="elsewhere"))
        self.model.write_bytes(b"changed weights!")
        with self.assertRaisesRegex(ValueError, "hash_mismatch"):
            self.run_prepare(self.args("datasets/facade-routing-v1/cases.jsonl"))


if __name__ == "__main__":
    unittest.main()
