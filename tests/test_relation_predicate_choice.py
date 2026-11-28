"""Offline checks of the directional contrasts and candidate-only boundary."""
from collections import Counter, defaultdict
from copy import deepcopy
import json
import unittest

from deposium_bench.cases import candidate_request, load_cases, validate_cases
from deposium_bench.relation_predicate_corpus import DATASET, frozen_files
from deposium_bench.scoring import score_case, summarize
from deposium_bench.systemone_local import native_request


class RelationPredicateChoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, _ = load_cases(DATASET / "cases.jsonl")

    def test_artifacts_rebuild_and_no_family_crosses_a_split(self):
        for name, content in frozen_files().items():
            self.assertEqual((DATASET / name).read_bytes(), content)
        self.assertEqual(Counter(case["split"] for case in self.cases),
                         {"train": 18, "calibration": 18, "test": 18})
        groups = defaultdict(list)
        for case in self.cases:
            groups[case["translation_family"]].append(case)
        self.assertEqual(len(groups), 9)
        for family in groups.values():
            self.assertEqual(Counter(case["language"] for case in family), {"fr": 3, "en": 3})
            self.assertEqual(len({case["split"] for case in family}), 1)
            self.assertEqual(len({tuple(case["document_ids"]) for case in family}), 1)
        leaked = deepcopy(self.cases[0])
        leaked["split"] = "test"
        with self.assertRaises(ValueError):
            validate_cases([self.cases[1], leaked])

    def test_direction_and_evidence_contrasts(self):
        groups = defaultdict(dict)
        for case in self.cases:
            group = (case["translation_family"], case["language"])
            variant = case["evaluation"]["task_type"].split(".")[1]
            groups[group][variant] = case
        reverse_predicates = Counter()
        for group in groups.values():
            forward, reverse, negative = (group[key] for key in ("forward", "reverse", "no-evidence"))
            a, b, snippet = forward["input"]["context"].splitlines()
            self.assertEqual(reverse["input"]["context"].splitlines(),
                             ["A" + b[1:], "B" + a[1:], snippet])
            self.assertEqual(negative["input"]["context"].splitlines()[:2], [a, b])
            self.assertNotEqual(negative["input"]["context"].splitlines()[2], snippet)
            for case in (reverse, negative):
                self.assertEqual(case["input"]["options"], forward["input"]["options"])
                self.assertEqual(case["input"]["question"], forward["input"]["question"])
            self.assertEqual(negative["evaluation"]["oracle"]["gold_predicate"], "none")
            reverse_predicates[reverse["evaluation"]["oracle"]["gold_predicate"]] += 1
        self.assertEqual(reverse_predicates, {"none": 10, "teacher_of": 2, "disciple_of": 2,
                                               "has_part": 2, "part_of": 2})

    def test_shared_scorer_rejects_empty_wrong_and_technical_abstention(self):
        results = []
        for case in self.cases:
            variant = case["evaluation"]["task_type"].split(".")[1]
            if variant == "no-evidence":
                label = "none"
            else:
                label = case["evaluation"]["oracle"]["gold_predicate"]
            mapping = case["evaluation"]["oracle"]["choices"]
            matching = [option for option, predicate in mapping.items() if predicate == label]
            self.assertEqual(len(matching), 1)
            choice = matching[0]
            good = {"case_id": case["case_id"], "status": "ok", "output": {"choice_id": choice}}
            results.append(good)
            self.assertTrue(score_case(case, good)["passed"])
            for wrong in [option for option in mapping if option != choice] + ["unknown"]:
                self.assertFalse(score_case(case, {"status": "ok", "output": {"choice_id": wrong}})["passed"])
            self.assertFalse(score_case(case, {"status": "ok", "output": {}})["passed"])
            self.assertFalse(score_case(case, {"status": "abstain", "output": None})["passed"])
        report = summarize(self.cases, results[:-1])
        self.assertEqual((report["total_cases"], report["scored_cases"], report["passed_cases"]), (54, 53, 53))
        self.assertEqual(report["counts_by_status"]["missing"], 1)

    def test_loopback_wire_contains_only_candidate_fields(self):
        for case in self.cases:
            request = candidate_request(case)
            self.assertEqual(set(request), {"case_id", "contract_id", "input"})
            value = request["input"]
            payload, mapping, wire = native_request(value, "fixture")
            self.assertEqual(json.loads(wire), payload)
            self.assertEqual(payload, {
                "model": "fixture", "state": value["context"],
                "questions": {"answer": {
                    "type": "choice", "instructions": value["question"],
                    "criteria": {f"c{i}": option["description"] for i, option in enumerate(value["options"])},
                }},
            })
            self.assertEqual(list(mapping.values()), [option["id"] for option in value["options"]])
            for hidden in (case["case_id"], case["translation_family"], case["document_ids"][0],
                           "gold_predicate", "reference", "rationale", "split"):
                self.assertNotIn(hidden.encode(), wire)

    def test_reference_and_excerpts_are_frozen(self):
        for key in ("reference", "input"):
            case = deepcopy(self.cases[0])
            if key == "reference":
                case[key]["assertions"][0]["value"] = "d"
            else:
                case[key]["context"] += " "
            with self.assertRaisesRegex(ValueError, "frozen synthetic specification"):
                validate_cases([case])
