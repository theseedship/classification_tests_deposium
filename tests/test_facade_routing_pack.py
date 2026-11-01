import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench import facade_corpus  # noqa: E402
from deposium_bench.cases import load_cases, validate_cases  # noqa: E402


class FacadeRoutingPackTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.digest = load_cases(ROOT / "datasets/facade-routing-v1/cases.jsonl")
        self.manifest = json.loads((ROOT / "datasets/facade-routing-v1/manifest.json").read_text())

    def test_frozen_pack_rebuilds_byte_for_byte(self):
        result = subprocess.run([sys.executable, "scripts/build-facade-routing-pack.py", "--check"], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.manifest["cases_sha256"], self.digest)

    def test_balanced_categories_splits_languages_and_positions(self):
        self.assertEqual(len(self.cases), 80)
        self.assertEqual(Counter(c["split"] for c in self.cases), {"test": 48, "train": 16, "calibration": 16})
        self.assertEqual(set(Counter(c["evaluation"]["oracle"]["params"]["task"] for c in self.cases).values()), {10})
        self.assertEqual(Counter(c["language"] for c in self.cases), {"fr": 40, "en": 40})
        positions = Counter(c["reference"]["assertions"][0]["value"] for c in self.cases)
        self.assertEqual(set(positions), set("abcdefgh"))
        self.assertLessEqual(max(positions.values()) - min(positions.values()), 4)
        for case in self.cases:
            self.assertEqual(len(case["input"]["options"]), 8)
            answer = case["reference"]["assertions"][0]["value"]
            self.assertEqual(case["evaluation"]["oracle"]["choices"][answer], case["evaluation"]["oracle"]["params"]["task"])

    def test_translations_share_identity_split_and_reference(self):
        families = {}
        for case in self.cases:
            families.setdefault(case["translation_family"], []).append(case)
        self.assertEqual(len(families), 40)
        for pair in families.values():
            self.assertEqual({c["language"] for c in pair}, {"fr", "en"})
            self.assertEqual(len({c["split"] for c in pair}), 1)
            self.assertEqual(len({c["reference"]["assertions"][0]["value"] for c in pair}), 1)

    def test_any_altered_case_or_reference_is_rejected(self):
        for mutate in (lambda c: c["reference"]["assertions"][0].update(value="a" if c["reference"]["assertions"][0]["value"] != "a" else "b"),
                       lambda c: c["input"].update(context=c["input"]["context"] + " "),
                       lambda c: c.update(split="train" if c["split"] != "train" else "test"),
                       lambda c: c["input"]["options"].reverse()):
            case = deepcopy(self.cases[5])
            mutate(case)
            with self.assertRaises(ValueError):
                validate_cases([case])

    def test_public_text_names_no_application_component(self):
        text = (ROOT / "datasets/facade-routing-v1/specs.json").read_text().lower()
        for forbidden in ("deposium_", "mcp", "duckdb", "supabase", "mistral", "groq", "bed-llm", "intent-mapping"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(facade_corpus.build_cases(), self.cases)


if __name__ == "__main__":
    unittest.main()
