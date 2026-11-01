import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench import passage_relevance_v2 as v2  # noqa: E402
from deposium_bench.cases import load_cases, validate_cases  # noqa: E402


class PassageRelevanceV2Tests(unittest.TestCase):
    def setUp(self):
        self.cases, self.digest = load_cases(ROOT / "datasets/passage-relevance-v2/cases.jsonl")

    def test_frozen_pack_rebuilds_from_v1(self):
        result = subprocess.run([sys.executable, "scripts/build-passage-relevance-v2.py", "--check"], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads((ROOT / "datasets/passage-relevance-v2/manifest.json").read_text())["cases_sha256"], self.digest)

    def test_mapping_exclusions_and_rotation(self):
        params = [c["evaluation"]["oracle"]["params"] for c in self.cases]
        self.assertEqual(len(self.cases), 512)
        self.assertNotIn("value_premise", {p["kind"] for p in params})
        for c, p in zip(self.cases, params):
            self.assertEqual(p["task"], v2.GRADE_TO_LABEL[p["v1_grade"]])
            answer = c["reference"]["assertions"][0]["value"]
            self.assertEqual(c["evaluation"]["oracle"]["choices"][answer], p["task"])
            self.assertEqual(len(c["input"]["options"]), 3)
        positions = Counter(c["reference"]["assertions"][0]["value"] for c in self.cases)
        self.assertLess(max(positions.values()) - min(positions.values()), 40)
        self.assertEqual(len({json.dumps(c["input"], sort_keys=True) for c in self.cases}), 512)

    def test_altered_reference_is_rejected(self):
        case = deepcopy(self.cases[3])
        value = case["reference"]["assertions"][0]["value"]
        case["reference"]["assertions"][0]["value"] = "a" if value != "a" else "b"
        with self.assertRaises(ValueError):
            validate_cases([case])


if __name__ == "__main__":
    unittest.main()
