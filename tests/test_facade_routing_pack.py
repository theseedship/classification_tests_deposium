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


class FacadeRoutingTierTests(unittest.TestCase):
    TIERS = {"facade-routing-advanced-v1": "fra1", "facade-routing-complex-v1": "frc1"}

    def load(self, dataset_id):
        cases, digest = load_cases(ROOT / "datasets" / dataset_id / "cases.jsonl")
        manifest = json.loads((ROOT / "datasets" / dataset_id / "manifest.json").read_text())
        self.assertEqual(manifest["cases_sha256"], digest)
        return cases

    def test_each_tier_is_balanced_and_frozen(self):
        for dataset_id, prefix in self.TIERS.items():
            with self.subTest(dataset_id):
                cases = self.load(dataset_id)
                self.assertEqual(len(cases), 96)
                self.assertTrue(all(c["case_id"].startswith(prefix + "-") for c in cases))
                self.assertEqual(Counter(c["split"] for c in cases), {"test": 64, "train": 16, "calibration": 16})
                self.assertEqual(set(Counter(c["evaluation"]["oracle"]["params"]["task"] for c in cases).values()), {12})
                self.assertEqual(set(Counter(c["reference"]["assertions"][0]["value"] for c in cases).values()), {12})
                self.assertEqual(facade_corpus.build_cases(dataset_id), cases)
                validate_cases(cases)

    def test_complex_tier_asks_for_the_first_category_and_carries_previous_turns(self):
        cases = self.load("facade-routing-complex-v1")
        self.assertEqual({c["input"]["question"] for c in cases}, set(facade_corpus.QUESTION_FIRST.values()))
        with_turn = [c for c in cases if c["input"]["context"].startswith(("Échange précédent", "Previous exchange"))]
        kinds = Counter(c["evaluation"]["oracle"]["params"]["kind"] for c in with_turn)
        self.assertEqual(kinds, {"context_turn": 28, "context_vague": 4})
        advanced = self.load("facade-routing-advanced-v1")
        self.assertEqual({c["input"]["question"] for c in advanced}, set(facade_corpus.QUESTION.values()))

    def test_tier_cases_are_validated_against_their_own_frozen_definition(self):
        for dataset_id in self.TIERS:
            case = deepcopy(self.load(dataset_id)[7])
            validate_cases([deepcopy(case)])
            case["reference"]["assertions"][0]["value"] = "a" if case["reference"]["assertions"][0]["value"] != "a" else "b"
            with self.assertRaises(ValueError):
                validate_cases([case])

    def test_tier_text_names_no_application_component(self):
        for dataset_id in self.TIERS:
            text = (ROOT / "datasets" / dataset_id / "specs.json").read_text().lower()
            for forbidden in ("deposium_", "mcp", "duckdb", "supabase", "mistral", "groq", "bed-llm", "intent-mapping"):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
