"""Offline case integrity and annotation isolation, independent of model services."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from deposium_bench.cases import (
    CaseError, candidate_request, load_cases, pointer_tokens, typed_equal, validate_cases,
)


def example_case(identity="test-fr", *, pack="DOC", language="fr"):
    return {
        "schema_version": "deposium.case/v1", "case_id": identity,
        "scenario_id": identity, "translation_family": identity,
        "document_ids": [f"synthetic:{identity}"], "split": "test",
        "language": language, "pack": pack, "contract_id": "mcps.document-plan",
        "input": {"message": "Liste les documents", "context": {"items": ["visible"]}},
        "reference": {"assertions": [{"path": "/decision", "op": "equals", "value": "catalog"}],
                      "abstention_allowed": False, "rationale": "Required catalogue decision."},
    }


class CaseValidationTests(unittest.TestCase):
    def test_shipped_corpus_has_all_packs_languages_and_unique_identities(self):
        cases, digest = load_cases()
        self.assertEqual(len(cases), 36)
        self.assertEqual(len({case["case_id"] for case in cases}), len(cases))
        self.assertEqual({case["pack"] for case in cases},
                         {"DOC", "FOLLOWUP", "PRESENTATION", "SOURCES", "EVIDENCE"})
        self.assertEqual({case["language"] for case in cases}, {"fr", "en"})
        self.assertRegex(digest, r"^[a-f0-9]{64}$")

    def test_missing_corpus_and_empty_cases_do_not_validate(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(CaseError):
                load_cases(Path(temp) / "missing.jsonl")
        for cases in ([], {}, None):
            with self.subTest(cases=cases), self.assertRaises(CaseError):
                validate_cases(cases)

    def test_identity_exact_structure_contract_and_document_integrity(self):
        case = example_case()
        with self.assertRaisesRegex(CaseError, "duplicate case_id"):
            validate_cases([case, deepcopy(case)])
        mutations = [
            ("case_id", ""), ("scenario_id", "invalid\nidentity"),
            ("translation_family", None), ("schema_version", "deposium.case/v0"),
            ("split", "other"), ("language", "de"), ("pack", "unknown"),
            ("contract_id", "missing.contract"), ("contract_id", "tantivy.search"),
            ("document_ids", "document"), ("document_ids", ["same", "same"]),
            ("document_ids", [True]), ("input", {}), ("input", []),
        ]
        for key, value in mutations:
            altered = deepcopy(case)
            altered[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(CaseError):
                validate_cases([altered])
        for change in ("missing", "extra"):
            altered = deepcopy(case)
            if change == "missing":
                del altered["reference"]
            else:
                altered["unknown"] = True
            with self.subTest(change=change), self.assertRaises(CaseError):
                validate_cases([altered])

    def test_scenarios_translations_and_documents_cannot_cross_any_split(self):
        for first_split, second_split in (("train", "test"), ("train", "calibration"),
                                          ("calibration", "test")):
            for group in ("scenario_id", "translation_family", "document_ids"):
                first, second = example_case("first-fr"), example_case("second-en", language="en")
                first["split"], second["split"] = first_split, second_split
                second[group] = deepcopy(first[group])
                with self.subTest(splits=(first_split, second_split), group=group):
                    with self.assertRaisesRegex(CaseError, "cross-split"):
                        validate_cases([first, second])
                    second["split"] = first_split
                    validate_cases([first, second])

    def test_references_cannot_be_absent_empty_or_vacuous(self):
        for reference in (None, {}, {"assertions": [], "abstention_allowed": False,
                                     "rationale": "No checks"}):
            case = example_case()
            case["reference"] = reference
            with self.subTest(reference=reference), self.assertRaises(CaseError):
                validate_cases([case])
        for value in (None, "", " \t", [], {}, {"empty": []}, [None, {"empty": ""}]):
            for path in ("", "/decision"):
                case = example_case()
                case["reference"]["assertions"] = [{"path": path, "op": "equals", "value": value}]
                with self.subTest(value=value, path=path), self.assertRaises(CaseError):
                    validate_cases([case])
        for value in (False, 0, {"count": 0}, [False]):
            case = example_case()
            case["reference"]["assertions"][0]["value"] = value
            validate_cases([case])

    def test_reference_types_operations_alternatives_and_duplicates(self):
        for key, value in (("abstention_allowed", 0), ("rationale", "")):
            case = example_case()
            case["reference"][key] = value
            with self.subTest(key=key), self.assertRaises(CaseError):
                validate_cases([case])
        for assertion in (
            {"path": "/x", "op": "unknown", "value": 1},
            {"path": "/x", "op": "one_of", "value": []},
            {"path": "/x", "op": "one_of", "value": [1, 1]},
            {"path": "/x", "op": "set_equals", "value": ["x", "x"]},
            {"path": "/x", "op": "set_equals", "value": "x"},
            {"path": "", "op": "one_of", "value": ["valid", {}]},
            {"path": "", "op": "one_of", "value": ["valid", {"empty": []}]},
            {"path": "/x", "op": "equals", "value": float("nan")},
        ):
            case = example_case()
            case["reference"]["assertions"] = [assertion]
            with self.subTest(assertion=assertion), self.assertRaises(CaseError):
                validate_cases([case])
        case = example_case()
        case["reference"]["assertions"] *= 2
        with self.assertRaisesRegex(CaseError, "duplicate assertion"):
            validate_cases([case])
        case["reference"]["assertions"] = [{"path": "/x", "op": "one_of", "value": [False, 0, 0.0]}]
        validate_cases([case])

    def test_input_rejects_annotations_recursively_and_non_json_types(self):
        for key in ("gold", "Expected", "expected_output", "reference", "reference_output",
                    "annotation", "annotations", "assertions", "rationale"):
            case = example_case()
            case["input"]["context"] = [{"nested": {key: "secret answer"}}]
            with self.subTest(key=key), self.assertRaisesRegex(CaseError, "forbidden"):
                candidate_request(case)
        for value in (float("inf"), float("nan"), {1: "bad key"}, {"a", "b"}, (1, 2), object()):
            case = example_case()
            case["input"]["invalid"] = value
            with self.subTest(value=value), self.assertRaises(CaseError):
                validate_cases([case])

    def test_candidate_request_isolates_references_and_deep_copies_input(self):
        case = example_case()
        original = deepcopy(case)
        request = candidate_request(case)
        self.assertEqual(set(request), {"case_id", "contract_id", "input"})
        self.assertNotIn("catalog", json.dumps(request))
        request["input"]["context"]["items"].append("changed")
        self.assertEqual(case, original)
        case["input"]["context"]["items"].append("source changed")
        self.assertNotIn("source changed", request["input"]["context"]["items"])

    def test_typed_json_equality_is_recursive(self):
        self.assertTrue(typed_equal({"a": [1, False]}, {"a": [1, False]}))
        for left, right in ((False, 0), (1, 1.0), ({"a": [True]}, {"a": [1]}),
                            ([1, 2], [2, 1]), ({"a": 1}, {"a": 1, "b": 2})):
            with self.subTest(left=left, right=right):
                self.assertFalse(typed_equal(left, right))

    def test_json_pointer_escapes_and_invalid_syntax(self):
        self.assertEqual(pointer_tokens(""), [])
        self.assertEqual(pointer_tokens("/a~1b/~0/~01/"), ["a/b", "~", "~1", ""])
        for path in (None, 1, "field", "/~", "/~2", "/~10~x"):
            with self.subTest(path=path), self.assertRaises(CaseError):
                pointer_tokens(path)


class CaseJsonlTests(unittest.TestCase):
    def load_payload(self, payload):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cases.jsonl"
            path.write_bytes(payload)
            return load_cases(path)

    def test_hash_exact_bytes_and_utf8_crlf_loading(self):
        payload = (json.dumps(example_case(), ensure_ascii=False) + "\r\n").encode("utf-8")
        cases, digest = self.load_payload(payload)
        self.assertEqual(cases, [example_case()])
        self.assertEqual(digest, hashlib.sha256(payload).hexdigest())

    def test_malformed_utf8_json_blank_records_duplicates_and_non_finite(self):
        valid = json.dumps(example_case()).encode("utf-8")
        payloads = (b"", b"\xff", b"{", b"{}\n", valid + b"\n\n", b"\n" + valid,
                    valid + b"\n \t\n", b'{"case_id":"a","case_id":"b"}',
                    valid.replace(b'"context":', b'"context":{},"context":', 1),
                    valid.replace(b'"visible"', b'NaN', 1),
                    valid.replace(b'"visible"', b'9' * 5000, 1), valid + b"\n" + valid)
        for payload in payloads:
            with self.subTest(payload=payload[:70]), self.assertRaises(CaseError):
                self.load_payload(payload)

    def test_unicode_line_separator_inside_string_is_not_a_record_delimiter(self):
        case = example_case()
        case["input"]["message"] = "first\u2028second\u2029third"
        payload = (json.dumps(case, ensure_ascii=False) + "\n").encode("utf-8")
        self.assertEqual(self.load_payload(payload)[0], [case])


if __name__ == "__main__":
    unittest.main()
