import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench import facade_hitl_corpus as hitl  # noqa: E402
from deposium_bench.cases import load_cases, validate_cases  # noqa: E402


class FacadeRoutingHitlTests(unittest.TestCase):
    def load(self, dataset_id):
        cases, digest = load_cases(ROOT / "datasets" / dataset_id / "cases.jsonl")
        self.assertEqual(json.loads((ROOT / "datasets" / dataset_id / "manifest.json").read_text())["cases_sha256"], digest)
        return cases

    def test_frozen_packs_rebuild(self):
        result = subprocess.run([sys.executable, "scripts/build-facade-routing-hitl.py", "--check"], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_variants_share_requests_and_differ_only_in_the_confirmation_option(self):
        nine, eight = self.load("facade-routing-hitl-v1"), self.load("facade-routing-hitl-8opt-v1")
        self.assertEqual(len(nine), len(eight), 90)
        for a, b in zip(nine, eight):
            self.assertEqual((a["input"]["context"], a["split"], a["language"]), (b["input"]["context"], b["split"], b["language"]))
            self.assertEqual((len(a["input"]["options"]), len(b["input"]["options"])), (9, 8))
            params = a["evaluation"]["oracle"]["params"]
            answer9 = a["reference"]["assertions"][0]
            answer8 = b["reference"]["assertions"][0]
            self.assertEqual(a["evaluation"]["oracle"]["choices"][answer9["value"]], "hitl" if params["needs_human"] else params["task"])
            chosen8 = answer8["value"] if answer8["op"] == "one_of" else [answer8["value"]]
            self.assertEqual(sorted(b["evaluation"]["oracle"]["choices"][x] for x in chosen8), sorted(params["candidates"]))
        self.assertEqual(Counter(c["evaluation"]["oracle"]["params"]["needs_human"] for c in nine), {True: 32, False: 58})

    def test_altered_case_is_rejected(self):
        for dataset_id in hitl.PACKS:
            case = deepcopy(self.load(dataset_id)[5])
            case["input"]["context"] += " "
            with self.assertRaises(ValueError):
                validate_cases([case])


if __name__ == "__main__":
    unittest.main()
