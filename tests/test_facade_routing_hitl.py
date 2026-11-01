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

    def test_isolated_models_accept_either_listed_option_but_nothing_else(self):
        from deposium_bench.campaigns import CampaignError, _validate_output_scope
        cases = self.load("facade-routing-hitl-8opt-v1")
        _validate_output_scope(cases, {"adapter": "d3", "capabilities": ["bench.context-choice"]})
        for value in (["a", "z"], ["a"], "a,b"):
            bad = deepcopy(cases[0])
            bad["reference"]["assertions"] = [{"path": "/choice_id", "op": "one_of", "value": value}]
            with self.subTest(value=value), self.assertRaises(CampaignError):
                _validate_output_scope([bad], {"adapter": "d3", "capabilities": ["bench.context-choice"]})

    def test_no_request_is_reused_across_splits_between_facade_packs(self):
        import re
        def words(text):
            # Content words only: generic openings such as "find the documents" are not reuse.
            return {w for w in re.findall(r"\w+", text.lower()) if len(w) > 3}
        seen = []
        for dataset_id in ("facade-routing-v1", "facade-routing-advanced-v1", "facade-routing-complex-v1", "facade-routing-hitl-v1"):
            for case in self.load(dataset_id):
                # The quoted request only, without the shared "request sent to a document assistant" preamble.
                request = re.search(r"[«\"]\s*(.+?)\s*[»\"]\s*$", case["input"]["context"].rsplit("\n", 1)[-1]).group(1)
                seen.append((dataset_id, case["split"], case["language"], words(request), case["case_id"]))
        for i, a in enumerate(seen):
            for b in seen[i + 1:]:
                if a[0] != b[0] and a[2] == b[2] and a[1] != b[1]:
                    overlap = len(a[3] & b[3]) / len(a[3] | b[3])
                    self.assertLess(overlap, 0.5, (a[4], b[4]))

    def test_altered_case_is_rejected(self):
        for dataset_id in hitl.PACKS:
            case = deepcopy(self.load(dataset_id)[5])
            case["input"]["context"] += " "
            with self.assertRaises(ValueError):
                validate_cases([case])


if __name__ == "__main__":
    unittest.main()
