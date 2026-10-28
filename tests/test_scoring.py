"""Adversarial exact scoring and denominators, without inference or external judges."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from deposium_bench.cases import CaseError, load_cases
from deposium_bench.scoring import STATUSES, score_case, summarize
from tests.test_cases import example_case


class ScoringTests(unittest.TestCase):
    def score(self, output, *, value="catalog", operation="equals", path="/decision"):
        case = example_case()
        case["reference"]["assertions"] = [{"path": path, "op": operation, "value": value}]
        return score_case(case, {"case_id": case["case_id"], "status": "ok", "output": output})

    def test_positive_negative_and_empty_outputs(self):
        self.assertTrue(self.score({"decision": "catalog"})["passed"])
        self.assertFalse(self.score({"decision": "search"})["passed"])
        for output in (None, {}, [], "", " \t\n", {"decision": []}, {"decision": None}):
            with self.subTest(output=output):
                score = self.score(output)
                self.assertTrue(score["scored"])
                self.assertFalse(score["passed"])
                self.assertEqual(score["reason"], "empty_output")
        for output in (float("nan"), float("inf"), {1: "catalog"}, ("catalog",), {"catalog"}):
            with self.subTest(output=output):
                score = self.score(output)
                self.assertTrue(score["scored"])
                self.assertFalse(score["passed"])
                self.assertEqual(score["reason"], "invalid_json_output")

    def test_equals_distinguishes_numbers_booleans_and_nested_types(self):
        for expected, actual in ((True, 1), (False, 0), (1, 1.0),
                                 ({"a": [False]}, {"a": [0]})):
            with self.subTest(expected=expected, actual=actual):
                self.assertTrue(self.score({"decision": expected}, value=expected)["passed"])
                self.assertFalse(self.score({"decision": actual}, value=expected)["passed"])
        self.assertTrue(self.score(False, value=False, path="")["passed"])
        self.assertTrue(self.score(0, value=0, path="")["passed"])

    def test_one_of_only_accepts_typed_alternatives(self):
        alternatives = [False, "catalog", {"task": [1]}]
        for actual in alternatives:
            self.assertTrue(self.score({"decision": actual}, value=alternatives, operation="one_of")["passed"])
        for actual in (0, "search", {"task": [1.0]}):
            self.assertFalse(self.score({"decision": actual}, value=alternatives, operation="one_of")["passed"])

    def test_set_equals_is_unordered_typed_and_duplicate_free(self):
        expected = [False, 0, {"ids": ["a", "b"]}]
        self.assertTrue(self.score({"decision": list(reversed(expected))}, value=expected,
                                   operation="set_equals")["passed"])
        for actual in ([False, False, {"ids": ["a", "b"]}], [False, 0],
                       [False, 0, {"ids": ["b", "a"]}], "not a list"):
            with self.subTest(actual=actual):
                self.assertFalse(self.score({"decision": actual}, value=expected,
                                            operation="set_equals")["passed"])
        case = example_case()
        case["reference"]["assertions"].append({"path": "/ids", "op": "set_equals", "value": []})
        self.assertTrue(score_case(case, {"status": "ok", "output": {"decision": "catalog", "ids": []}})["passed"])
        self.assertFalse(score_case(case, {"status": "ok", "output": {"decision": "catalog", "ids": ["a"]}})["passed"])

    def test_json_pointer_root_escaped_keys_and_array_indexes(self):
        output = {"a/b": {"~": [{"": "catalog"}]}, "~1": "catalog"}
        self.assertTrue(self.score(output, path="/a~1b/~0/0/")["passed"])
        self.assertTrue(self.score(output, path="/~01")["passed"])
        self.assertTrue(self.score("catalog", path="")["passed"])
        for path in ("/missing", "/a~1b/~0/1", "/a~1b/~0/-1", "/a~1b/~0/00",
                     "/a~1b/~0/-", "/a~1b/~0/" + "9" * 5000, "/~01/child"):
            with self.subTest(path=path[:60]):
                score = self.score(output, path=path)
                self.assertFalse(score["passed"])
                self.assertEqual(score["checks"][0]["reason"], "missing_path")
        for path in ("not-pointer", "/~2"):
            with self.subTest(path=path), self.assertRaises(CaseError):
                self.score(output, path=path)

    def test_all_assertions_are_required(self):
        case = example_case()
        case["reference"]["assertions"].append({"path": "/count", "op": "equals", "value": 2})
        score = score_case(case, {"status": "ok", "output": {"decision": "catalog", "count": 1}})
        self.assertEqual([check["passed"] for check in score["checks"]], [True, False])
        self.assertFalse(score["passed"])

    def test_execution_states_and_abstention_are_distinct(self):
        case = example_case()
        for status in STATUSES:
            with self.subTest(status=status):
                score = score_case(case, {"status": status, "output": {"decision": "catalog"}})
                self.assertEqual(score["scored"], status in {"ok", "abstain"})
                self.assertEqual(score["passed"], status == "ok")
                if status not in {"ok", "abstain"}:
                    self.assertEqual(score["reason"], status)
        case["reference"]["abstention_allowed"] = True
        allowed = score_case(case, {"status": "abstain"})
        self.assertTrue(allowed["scored"])
        self.assertTrue(allowed["passed"])
        self.assertEqual(allowed["reason"], "allowed_abstention")

    def test_invalid_status_and_mismatching_identity_are_rejected(self):
        case = example_case()
        for result in (None, {}, {"status": "unknown"}, {"status": []}, {"status": {}},
                       {"status": "ok", "case_id": "another", "output": {"decision": "catalog"}}):
            with self.subTest(result=result), self.assertRaises(ValueError):
                score_case(case, result)


class SummaryTests(unittest.TestCase):
    def test_full_success_requires_every_case_to_be_scored_and_passed(self):
        cases = [example_case("decision"), example_case("abstention")]
        cases[1]["reference"]["abstention_allowed"] = True
        report = summarize(cases, [
            {"case_id": "decision", "status": "ok", "output": {"decision": "catalog"}},
            {"case_id": "abstention", "status": "abstain"},
        ])
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["scored_cases"], 2)
        self.assertEqual(report["passed_cases"], 2)
        self.assertEqual(report["failed_cases"], 0)
        self.assertEqual(report["coverage"], 1.0)
        self.assertEqual(report["accuracy_scored"], 1.0)
        self.assertEqual(report["accuracy_over_all"], 1.0)

    def test_missing_results_are_joined_by_identity_and_keep_denominators(self):
        cases = [example_case("doc-fr"), example_case("presentation-en", pack="PRESENTATION", language="en"),
                 example_case("doc-en", language="en")]
        results = [{"case_id": "doc-en", "status": "ok", "output": {"decision": "search"}},
                   {"case_id": "doc-fr", "status": "ok", "output": {"decision": "catalog"}}]
        report = summarize(cases, results)
        self.assertEqual([row["case_id"] for row in report["rows"]], [case["case_id"] for case in cases])
        self.assertEqual((report["total_cases"], report["scored_cases"], report["passed_cases"], report["failed_cases"]),
                         (3, 2, 1, 1))
        self.assertEqual(report["counts_by_status"]["missing"], 1)
        self.assertEqual(report["accuracy_over_all"], 1 / 3)
        self.assertEqual(report["accuracy_scored"], 1 / 2)
        self.assertEqual(report["coverage"], 2 / 3)
        self.assertEqual(report["verdict"], "fail")
        self.assertEqual(report["by_pack"]["DOC"]["total_cases"], 2)
        self.assertEqual(report["by_pack"]["DOC"]["scored_cases"], 2)
        self.assertEqual(report["by_pack"]["DOC"]["accuracy_scored"], 1 / 2)
        self.assertEqual(report["by_pack"]["PRESENTATION"]["scored_cases"], 0)
        self.assertEqual(report["by_pack"]["PRESENTATION"]["verdict"], "invalid")
        self.assertEqual(report["by_language"]["fr"]["accuracy_scored"], 1.0)
        self.assertEqual(report["by_language"]["en"]["total_cases"], 2)
        self.assertEqual(report["by_language"]["en"]["scored_cases"], 1)
        self.assertEqual(report["by_language"]["en"]["passed_cases"], 0)

    def test_counts_by_status_never_collapse_execution_failures_into_abstention(self):
        cases = [example_case(status) for status in STATUSES]
        results = [{"case_id": status, "status": status, "output": {"decision": "catalog"}}
                   for status in STATUSES]
        report = summarize(cases, results)
        self.assertEqual(report["counts_by_status"], dict.fromkeys(STATUSES, 1))
        self.assertEqual(report["scored_cases"], 2)
        self.assertEqual(report["failed_cases"], 1)
        self.assertEqual(report["coverage"], 2 / 6)

    def test_zero_scored_is_invalid_and_partial_coverage_cannot_pass(self):
        cases = [example_case("first"), example_case("second")]
        for results in ([], [{"case_id": "first", "status": "unsupported"},
                             {"case_id": "second", "status": "timeout"}]):
            report = summarize(cases, results)
            self.assertEqual(report["scored_cases"], 0)
            self.assertEqual(report["verdict"], "invalid")
            self.assertIsNone(report["accuracy_scored"])
            self.assertEqual(report["accuracy_over_all"], 0)
            self.assertEqual(report["coverage"], 0)
        report = summarize(cases, [{"case_id": "first", "status": "ok", "output": {"decision": "catalog"}}])
        self.assertEqual(report["accuracy_scored"], 1.0)
        self.assertEqual(report["verdict"], "fail")
        self.assertEqual(report["coverage"], 0.5)
        with self.assertRaises(CaseError):
            summarize([], [])

    def test_unknown_duplicate_missing_and_invalid_result_identities_rejected(self):
        cases = [example_case()]
        valid = {"case_id": cases[0]["case_id"], "status": "ok", "output": {"decision": "catalog"}}
        for results in (None, {}, [valid, deepcopy(valid)], [{"case_id": "unknown", "status": "ok"}],
                        [None], [{"status": "ok"}], [{"case_id": 1, "status": "ok"}],
                        [{"case_id": cases[0]["case_id"], "status": []}]):
            with self.subTest(results=results), self.assertRaises(ValueError):
                summarize(cases, results)

    def test_shipped_control_retains_intentional_failures_and_unscored_states(self):
        cases, _ = load_cases()
        path = Path(__file__).resolve().parents[1] / "fixtures" / "control-responses.jsonl"
        results = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        report = summarize(cases, results)
        self.assertEqual(report["total_cases"], len(cases))
        self.assertEqual(report["verdict"], "fail")
        self.assertGreater(report["failed_cases"], 0)
        self.assertGreater(report["passed_cases"], 0)
        for status in ("unsupported", "missing", "error", "timeout", "abstain"):
            self.assertGreater(report["counts_by_status"][status], 0)
        rows = {row["case_id"]: row for row in report["rows"]}
        self.assertFalse(rows["doc-compound-fr"]["passed"])
        self.assertFalse(rows["doc-compound-en"]["passed"])
        self.assertLess(report["coverage"], 1)


if __name__ == "__main__":
    unittest.main()
