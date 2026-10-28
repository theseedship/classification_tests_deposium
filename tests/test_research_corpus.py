"""Exact-oracle and corpus integrity checks; no model or external service."""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from deposium_bench.cases import candidate_request, validate_cases
from deposium_bench.research_corpus import build_cases, parse_formula, validate_oracle, write_dataset
from deposium_bench.scoring import score_case

ROOT = Path(__file__).resolve().parents[1]


def base_hash(case):
    data = (json.dumps(case["input"], sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()
    return hashlib.sha256(data).hexdigest()


class ResearchCorpusTests(unittest.TestCase):
    def setUp(self):
        self.cases = build_cases()
        self.by_task = {case["evaluation"]["task_type"]: case for case in self.cases if case["language"] == "fr"}

    def answer(self, task):
        case = self.by_task[task]
        letter = case["reference"]["assertions"][0]["value"]
        return case["evaluation"]["oracle"]["choices"][letter]

    def test_counts_classes_difficulty_and_splits(self):
        validate_cases(self.cases)
        self.assertEqual(len(self.cases), 132)
        self.assertEqual(len({c["translation_family"] for c in self.cases}), 66)
        self.assertEqual(Counter(c["language"] for c in self.cases), {"fr": 66, "en": 66})
        self.assertEqual(Counter(c["evaluation"]["domain"] for c in self.cases),
                         {"documentary": 76, "mathematics": 28, "chemistry": 28})
        self.assertEqual(Counter(c["evaluation"]["difficulty"] for c in self.cases),
                         {"D1": 40, "D2": 40, "D3": 52})
        self.assertEqual(Counter(c["split"] for c in self.cases),
                         {"train": 36, "calibration": 30, "test": 66})
        for task in ("catalog", "stored_summaries", "retrieve_answer"):
            selected = [c for c in self.cases if c["evaluation"]["domain"] == "documentary"
                        and c["evaluation"]["oracle"]["params"]["task"] == task]
            self.assertEqual(len(selected), 24)
            self.assertEqual(Counter(c["evaluation"]["difficulty"] for c in selected),
                             {"D1": 8, "D2": 8, "D3": 8})
            self.assertEqual(Counter(c["split"] for c in selected),
                             {"train": 8, "calibration": 4, "test": 12})
            self.assertEqual(Counter(c["evaluation"]["difficulty"] for c in selected if c["split"] == "test"),
                             {"D1": 4, "D2": 4, "D3": 4})

    def test_translations_share_order_split_and_semantics_without_position_leak(self):
        groups = defaultdict(list)
        for case in self.cases:
            groups[case["translation_family"]].append(case)
        for family in groups.values():
            self.assertEqual(len(family), 2)
            fr, en = family
            self.assertEqual(fr["split"], en["split"])
            self.assertEqual(fr["evaluation"]["oracle"]["choices"], en["evaluation"]["oracle"]["choices"])
            self.assertEqual(fr["reference"]["assertions"], en["reference"]["assertions"])
            self.assertEqual([o["id"] for o in fr["input"]["options"]],
                             [o["id"] for o in en["input"]["options"]])
        for language in ("fr", "en"):
            counts = Counter(c["reference"]["assertions"][0]["value"] for c in self.cases if c["language"] == language)
            self.assertEqual(counts, {"a": 17, "b": 17, "c": 16, "d": 16})
        for domain in ("mathematics", "chemistry"):
            main = [c for c in self.cases if c["evaluation"]["domain"] == domain
                    and not c["evaluation"]["oracle"]["kind"].startswith("insufficient_")]
            self.assertEqual(Counter(c["split"] for c in main), {"train": 6, "calibration": 6, "test": 12})

    def test_known_mathematical_results_independent_of_answer_letter(self):
        self.assertEqual(self.answer("fraction-addition"), "1/2")
        self.assertEqual(self.answer("square-expansion"), ["1", "2", "1"])
        self.assertEqual(self.answer("function-types"), {"application_order": ["f", "g"], "output_dimension": 1})
        self.assertEqual(self.answer("matrix-product"), [2, 4])
        self.assertEqual(self.answer("principal-root"), "abs(x)")
        self.assertEqual(self.answer("chain-derivative"), ["2", "2"])
        self.assertEqual(self.answer("cancel-keep-domain"), {"coefficients": ["2", "1"], "excluded": ["2"]})
        self.assertEqual(self.answer("quantity-dimension"), {"L": -1, "mol": 1})
        self.assertEqual(self.answer("extraneous-equation-root"), {"roots": []})
        self.assertEqual(self.answer("transpose-chain"), [2, 5])
        self.assertEqual(self.answer("polynomial-remainder"), ["3", "1"])
        self.assertEqual(self.answer("conditional-probability"), "3/5")

    def test_atoms_charge_stoichiometry_units_and_multistep_quantities(self):
        self.assertEqual(self.answer("group-atom-count"), {"Ca": 1, "H": 2, "O": 2})
        self.assertEqual(self.answer("water-balance"), [2, 1, 2])
        self.assertEqual(self.answer("ionic-neutrality"), [1, 2])
        self.assertEqual(self.answer("molar-concentration"), {"value": "1/10", "unit": "mol/L"})
        self.assertEqual(self.answer("nested-complex-count"), {"C": 6, "Fe": 1, "K": 4, "N": 6})
        self.assertEqual(self.answer("combustion-balance"), [2, 7, 4, 6])
        self.assertEqual(self.answer("conserved-dilution"), {"value": "1/20", "unit": "mol/L"})
        self.assertEqual(self.answer("atoms-and-charge"), [6, 1, 14, 6, 2, 7])
        self.assertEqual(self.answer("limiting-reactant"), {"value": "2", "unit": "mol"})
        self.assertEqual(self.answer("aliquot-and-mix"), {"value": "7/40", "unit": "mol/L"})
        self.assertEqual(self.answer("precipitate-mass"), {"value": "287/1000", "unit": "g"})
        self.assertEqual(self.answer("hydrate-water-fraction"), "180/499")
        self.assertEqual(parse_formula("Al2(SO4)3"), {"Al": 2, "O": 12, "S": 3})
        for formula in ("Ca(OH", "H0", "", "Na+", "H2O)", "CuSO4·", "C()2"):
            with self.subTest(formula=formula), self.assertRaises(ValueError):
                parse_formula(formula)

    def test_wrong_gold_false_facts_empty_outputs_and_technical_abstention_fail(self):
        for case in self.cases:
            gold = case["reference"]["assertions"][0]["value"]
            wrong = next(letter for letter in "abcd" if letter != gold)
            altered = deepcopy(case)
            altered["reference"]["assertions"][0]["value"] = wrong
            with self.subTest(case=case["case_id"]), self.assertRaises(ValueError):
                validate_oracle(altered)
            for result in ({"status": "ok", "output": {"choice_id": wrong}},
                           {"status": "ok", "output": {}}, {"status": "abstain", "output": None}):
                self.assertFalse(score_case(case, result)["passed"])
        for mutate in (lambda c: c["evaluation"]["oracle"]["params"].update(expression="7"),
                       lambda c: c["input"].update(context="p=7, q=9"),
                       lambda c: c["input"]["options"][0].update(description="The gold answer"),
                       lambda c: c.update(scenario_id="changed"),
                       lambda c: c.update(document_ids=["other-document"]),
                       lambda c: c.update(case_id="changed-base-id"),
                       lambda c: c["input"].update(context="Annex. " + c["input"]["context"])):
            altered = deepcopy(self.by_task["fraction-addition"])
            mutate(altered)
            with self.assertRaises(ValueError):
                validate_oracle(altered)

    def test_length_wrappers_preserve_once_only_facts_and_verified_base_hash(self):
        case = self.by_task["formula-not-structure"]
        variant = deepcopy(case)
        variant["case_id"] += "--length-test"
        variant["input"]["context"] = "Unrelated sample A.\n\n" + case["input"]["context"] + "\n\nUnrelated sample B."
        variant["input"]["options"].reverse()
        variant["evaluation"]["length"] = {"order": "reversed", "base_input_sha256": base_hash(case)}
        validate_oracle(variant)
        for mutate in (lambda c: c["input"].update(context=c["input"]["context"] + case["input"]["context"]),
                       lambda c: c["input"].update(question="Changed question"),
                       lambda c: c["evaluation"]["length"].update(base_input_sha256="0" * 64),
                       lambda c: c["evaluation"]["length"].update(order="original")):
            altered = deepcopy(variant)
            mutate(altered)
            with self.assertRaises(ValueError):
                validate_oracle(altered)

    def test_insufficiency_is_a_semantic_choice_and_science_has_countermodels(self):
        insufficient = [c for c in self.cases if any(
            c["evaluation"]["oracle"]["choices"][a["value"]] == "insufficient_information"
            for a in c["reference"]["assertions"])]
        self.assertEqual(len(insufficient), 12)
        self.assertEqual(Counter(c["evaluation"]["domain"] for c in insufficient),
                         {"documentary": 4, "mathematics": 4, "chemistry": 4})
        self.assertTrue(all(c["reference"]["abstention_allowed"] is False for c in insufficient))
        self.assertTrue(all("witnesses" in c["evaluation"]["oracle"]["params"] or
                            "witness_volumes" in c["evaluation"]["oracle"]["params"]
                            for c in insufficient if c["evaluation"]["domain"] != "documentary"))
        self.assertTrue(all(c["evaluation"]["review"] == "agent_only" for c in self.cases))

    def test_candidate_boundary_hides_oracle_and_metadata(self):
        for case in self.cases:
            request = candidate_request(case)
            self.assertEqual(set(request), {"case_id", "contract_id", "input"})
            self.assertEqual(set(request["input"]), {"context", "question", "options"})
            self.assertNotIn("reference", request["input"])
            self.assertNotIn("evaluation", request["input"])
            self.assertNotIn("oracle", request["input"])

    def test_committed_bytes_match_builder_hash_and_write_never_overwrites(self):
        source = ROOT / "datasets/context-choice-v1"
        manifest = json.loads((source / "manifest.json").read_text())
        payload = (source / "cases.jsonl").read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), manifest["cases_sha256"])
        self.assertEqual([json.loads(line) for line in payload.splitlines()], self.cases)
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "fresh"
            written = write_dataset(destination)
            self.assertEqual(written["cases_sha256"], manifest["cases_sha256"])
            self.assertEqual((destination / "cases.jsonl").read_bytes(), payload)
            with self.assertRaises(FileExistsError):
                write_dataset(destination)
            self.assertEqual((destination / "cases.jsonl").read_bytes(), payload)
        first = build_cases()
        first[0]["input"]["question"] = "Unrelated mutation"
        self.assertNotEqual(build_cases()[0]["input"]["question"], "Unrelated mutation")


if __name__ == "__main__":
    unittest.main()
