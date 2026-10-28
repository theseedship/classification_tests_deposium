"""Mutation checks for the offline passage boundary; no models or services."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import passage_dataset as dataset


def fixture(*, suffix="one", split="test", query_status="answerable", grades=(3, 2, 1, 0)):
    passages = [{"id": f"p{i}", "document_id": f"doc-{suffix}-{i}",
                 "text": f"Document {i}: une preuve vérifiable.", "language": "fr"} for i in range(4)]
    for passage in passages:
        passage["sha256"] = hashlib.sha256(passage["text"].encode()).hexdigest()
    judgments = [{"passage_id": p["id"], "label": "insufficient", "spans": []} for p in passages]
    if query_status in ("answerable", "conflicting_visible_evidence"):
        judgments[0].update(label="supports", spans=[{"start": 0, "end": 10, "text": passages[0]["text"][:10]}])
    if query_status == "conflicting_visible_evidence":
        judgments[1].update(label="refutes", spans=[{"start": 0, "end": 10, "text": passages[1]["text"][:10]}])
    return {"schema_version": dataset.VERSION, "case_id": f"case-{suffix}", "family_id": f"family-{suffix}",
            "scenario_id": f"scenario-{suffix}", "split": split, "question_language": "fr", "passage_language": "fr",
            "view": "full", "query": "Quel document permet de conclure ?", "passages": passages,
            "annotations": {"review": "agent_only_pending_human", "query_status": query_status,
                            "relevance": [{"passage_id": p["id"], "grade": grade, "role": f"hidden-role-{i}"}
                                          for i, (p, grade) in enumerate(zip(passages, grades))],
                            "claims": [{"id": "claim-1", "text": "La conclusion est établie.", "judgments": judgments}],
                            "minimal_evidence_sets": [["p0"]] if query_status == "answerable" else [],
                            "rationale": "HIDDEN RATIONALE FOR REVIEW"},
            "provenance": {"source": "synthetic", "private_note": "HIDDEN PROVENANCE"}}


def write_fixture(folder, cases):
    path = Path(folder) / "cases.jsonl"
    payload = "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases).encode()
    path.write_bytes(payload)
    manifest = {"cases_sha256": hashlib.sha256(payload).hexdigest(), "case_count": len(cases),
                "family_count": len({case["family_id"] for case in cases})}
    (path.parent / "manifest.json").write_text(json.dumps(manifest))
    return path


class PassageValidationTests(unittest.TestCase):
    def test_checked_in_corpus_validates_multilingual_views_and_visible_labels(self):
        cases, digest = dataset.load_dataset()
        self.assertEqual(len(cases), 1536)
        self.assertEqual(len(digest), 64)
        self.assertEqual(len({case["family_id"] for case in cases}), 24)
        self.assertEqual({case["question_language"] for case in cases}, set(dataset.LANGUAGES))
        self.assertEqual({case["view"] for case in cases}, {"full", "head_384"})
        clipped = [case for case in cases if case["view"] == "head_384"
                   and case["scenario_id"] == "heading_value_truncation"]
        self.assertEqual(len(clipped), 96)
        for case in clipped:
            self.assertEqual({item["grade"] for item in case["annotations"]["relevance"]}, {0})
            self.assertEqual(case["annotations"]["query_status"], "insufficient_visible_evidence")

    def test_valid_joint_evidence_conflict_and_empty_support(self):
        answerable = fixture()
        answerable["annotations"]["relevance"][0]["grade"] = 2
        answerable["annotations"]["minimal_evidence_sets"] = [["p0", "p1"]]
        for judgment in answerable["annotations"]["claims"][0]["judgments"]:
            judgment.update(label="insufficient", spans=[])
        cases = [answerable, fixture(suffix="conflict", query_status="conflicting_visible_evidence"),
                 fixture(suffix="none", query_status="insufficient_visible_evidence", grades=(0, 0, 0, 0))]
        for case in cases:
            case["query"] += " " + case["case_id"]
        dataset.validate_cases(cases)

    def test_conflict_must_concern_one_claim(self):
        case = fixture(query_status="conflicting_visible_evidence")
        first = case["annotations"]["claims"][0]
        second = deepcopy(first)
        second.update(id="claim-2", text="Une autre conclusion est établie.")
        first["judgments"][1].update(label="insufficient", spans=[])
        second["judgments"][0].update(label="insufficient", spans=[])
        case["annotations"]["claims"].append(second)
        with self.assertRaisesRegex(dataset.PassageDatasetError, "same claim"):
            dataset.validate_cases([case])
        # Several claims remain valid when at least one has both polarities.
        first["judgments"][1] = deepcopy(second["judgments"][1])
        dataset.validate_cases([case])

    def test_visible_oracles_are_consistent_across_cases_and_views(self):
        for axis in ("relevance", "support", "answerability"):
            with self.subTest(axis=axis):
                first, second = fixture(), fixture(suffix="copy")
                second["view"] = "head_384"
                # Ranking sees the opaque passage IDs; choices do not. Ensure
                # the relevance assertion exercises the choice identity itself.
                for passage in second["passages"]:
                    passage["id"] += "-copy"
                for item in second["annotations"]["relevance"]:
                    item["passage_id"] += "-copy"
                for claim in second["annotations"]["claims"]:
                    for judgment in claim["judgments"]:
                        judgment["passage_id"] += "-copy"
                second["annotations"]["minimal_evidence_sets"] = [["p0-copy"]]
                if axis == "relevance":
                    second["annotations"]["relevance"][0]["grade"] = 2
                elif axis == "support":
                    second["annotations"]["claims"][0]["judgments"][0].update(label="insufficient", spans=[])
                else:
                    second["annotations"].update(query_status="insufficient_visible_evidence", minimal_evidence_sets=[])
                with self.assertRaisesRegex(dataset.PassageDatasetError, "conflicting annotations"):
                    dataset.validate_cases([first, second])
                # Distinct actual candidate inputs may legitimately differ.
                second["query"] += " Précisez ce cas."
                dataset.validate_cases([first, second])

    def test_visible_oracles_ignore_hidden_ids_but_keep_visible_claims(self):
        first, second = fixture(), fixture(suffix="copy")
        second["annotations"]["claims"][0]["id"] = "another-hidden-id"
        dataset.validate_cases([first, second])
        second["annotations"]["claims"][0]["judgments"][0].update(label="insufficient", spans=[])
        with self.assertRaisesRegex(dataset.PassageDatasetError, "conflicting annotations"):
            dataset.validate_cases([first, second])
        second["annotations"]["claims"][0]["text"] = "Une affirmation différente."
        dataset.validate_cases([first, second])

    def test_rejects_mutated_ids_labels_hashes_spans_and_minimal_sets(self):
        mutations = [
            lambda c: c.update(schema_version="unknown"),
            lambda c: c.update(language="en"),
            lambda c: c.update(question_language="xx"),
            lambda c: c.update(query=""),
            lambda c: c.update(passages=[]),
            lambda c: c["passages"][1].update(id="p0"),
            lambda c: c["passages"][1].update(document_id=c["passages"][0]["document_id"]),
            lambda c: c["passages"][0].update(sha256="0" * 64),
            lambda c: c["passages"][0].update(language="en"),
            lambda c: c["annotations"].update(review="human_approved"),
            lambda c: c["annotations"].update(relevance=[]),
            lambda c: c["annotations"]["relevance"][0].update(grade=True),
            lambda c: c["annotations"]["relevance"][0].update(grade=float("nan")),
            lambda c: c["annotations"]["relevance"][0].update(grade=4),
            lambda c: c["annotations"]["relevance"][0].update(passage_id="missing"),
            lambda c: c["annotations"]["relevance"][1].update(passage_id="p0"),
            lambda c: c["annotations"].update(claims=[]),
            lambda c: c["annotations"]["claims"].append(deepcopy(c["annotations"]["claims"][0])),
            lambda c: c["annotations"]["claims"][0]["judgments"].pop(),
            lambda c: c["annotations"]["claims"][0]["judgments"][0].update(label="maybe"),
            lambda c: c["annotations"]["claims"][0]["judgments"][0].update(spans=[]),
            lambda c: c["annotations"]["claims"][0]["judgments"][0]["spans"][0].update(start=True),
            lambda c: c["annotations"]["claims"][0]["judgments"][0]["spans"][0].update(end=999),
            lambda c: c["annotations"]["claims"][0]["judgments"][0]["spans"][0].update(text="invented"),
            lambda c: c["annotations"]["claims"][0]["judgments"][1].update(spans=[{"start": 0, "end": 1, "text": "D"}]),
            lambda c: c["annotations"].update(minimal_evidence_sets=[]),
            lambda c: c["annotations"].update(minimal_evidence_sets=[["p2"]]),
            lambda c: c["annotations"].update(minimal_evidence_sets=[["p0", "p0"]]),
            lambda c: c["annotations"].update(minimal_evidence_sets=[["p0"], ["p0", "p1"]]),
            lambda c: c["annotations"].update(query_status="conflicting_visible_evidence", minimal_evidence_sets=[]),
            lambda c: c["provenance"].update(bad=float("inf")),
        ]
        for i, mutate in enumerate(mutations):
            case = fixture()
            mutate(case)
            with self.subTest(mutation=i), self.assertRaises(dataset.PassageDatasetError):
                dataset.validate_cases([case])
        for invalid in ([], [fixture(), fixture()]):
            with self.assertRaises(dataset.PassageDatasetError):
                dataset.validate_cases(invalid)

    def test_partition_isolation_across_translations_views_and_shared_documents(self):
        for field in ("family_id", "document"):
            first, second = fixture(), fixture(suffix="two", split="train")
            if field == "document":
                second["passages"][0]["document_id"] = first["passages"][0]["document_id"]
            else:
                second[field] = first[field]
            second["question_language"] = "en"
            second["view"] = "head_384"
            with self.subTest(field=field), self.assertRaises(dataset.PassageDatasetError):
                dataset.validate_cases([first, second])
            second["split"] = first["split"]
            dataset.validate_cases([first, second])
        first, second = fixture(), fixture(suffix="two", split="train")
        second["scenario_id"] = first["scenario_id"]
        dataset.validate_cases([first, second])

    def test_head_view_bounds_and_unicode_span_coordinates(self):
        case = fixture()
        passage = case["passages"][0]
        passage["text"] = "Été 🌱：preuve"
        passage["sha256"] = hashlib.sha256(passage["text"].encode()).hexdigest()
        case["annotations"]["claims"][0]["judgments"][0]["spans"] = [{"start": 4, "end": 5, "text": "🌱"}]
        case["view"] = "head_384"
        dataset.validate_cases([case])
        passage["text"] += "x" * 400
        passage["sha256"] = hashlib.sha256(passage["text"].encode()).hexdigest()
        with self.assertRaises(dataset.PassageDatasetError):
            dataset.validate_cases([case])

    def test_identical_visible_passages_cannot_inherit_hidden_different_labels(self):
        case = fixture(query_status="insufficient_visible_evidence", grades=(0, 0, 0, 0))
        for passage in case["passages"]:
            passage["text"] = "Identical neutral prefix, without evidence."
            passage["sha256"] = hashlib.sha256(passage["text"].encode()).hexdigest()
        dataset.validate_cases([case])
        case["annotations"]["relevance"][1]["grade"] = 1
        with self.assertRaises(dataset.PassageDatasetError):
            dataset.validate_cases([case])
        case["annotations"]["relevance"][1]["grade"] = 0
        case["annotations"]["claims"][0]["judgments"][1].update(
            label="supports", spans=[{"start": 0, "end": 9, "text": "Identical"}])
        with self.assertRaises(dataset.PassageDatasetError):
            dataset.validate_cases([case])

    def test_manifest_exact_bytes_counts_and_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_fixture(folder, [fixture()])
            cases, digest = dataset.load_dataset(path)
            self.assertEqual(cases, [fixture()])
            self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaises(ValueError):
                dataset.load_dataset(path)
            path = write_fixture(folder, [fixture()])
            manifest_path = path.parent / "manifest.json"
            original = json.loads(manifest_path.read_text())
            for key, value in (("case_count", True), ("family_count", 2), ("cases_sha256", "bad")):
                manifest_path.write_text(json.dumps(original | {key: value}))
                with self.subTest(key=key), self.assertRaises(dataset.PassageDatasetError):
                    dataset.load_dataset(path)
            path.write_text('{"case_id":"a","case_id":"b"}\n')
            with self.assertRaises(dataset.PassageDatasetError):
                dataset.load_dataset(path)


class PassageProjectionTests(unittest.TestCase):
    def test_whitelist_isolation_localization_and_existing_protocol(self):
        for language in dataset.LANGUAGES:
            case = fixture()
            case["question_language"] = language
            for projection, count in (("ranking", 1), ("relevance", 4), ("support", 4), ("answerability", 1)):
                rows = dataset.export_requests([case], projection)
                self.assertEqual(len(rows), count)
                for row in rows:
                    visible = json.dumps(row["input"], ensure_ascii=False)
                    for hidden in (case["case_id"], case["family_id"], case["scenario_id"], "HIDDEN", "hidden-role", "agent_only", "doc-one"):
                        self.assertNotIn(hidden, visible)
                    if projection == "ranking":
                        self.assertEqual(set(row["input"]), {"query", "passages"})
                        self.assertEqual(set(row["input"]["passages"][0]), {"id", "text"})
                    else:
                        model_row = dataset.candidate_row(row)
                        self.assertEqual(set(model_row), {"state", "question", "options", "type"})
                        self.assertNotIn("o1", model_row["options"])
                        self.assertEqual(row["input"]["options"][0]["id"], "o1")
                if projection != "ranking":
                    self.assertEqual(rows[0]["input"]["question"].split("\n")[0],
                                     dataset._TEXT[language][{"relevance": 2, "support": 4, "answerability": 6}[projection]])

    def test_filters_report_no_empty_success_and_do_not_hide_leaks(self):
        first, second = fixture(), fixture(suffix="two", split="train")
        second["question_language"] = "en"
        second["view"] = "head_384"
        selected = dataset.select_cases([first, second], split="train", question_language=["en"], view="head_384")
        self.assertEqual(selected, [second])
        for filters in ({"split": "calibration"}, {"question_language": []}, {"split": "invalid"}):
            with self.assertRaises(dataset.PassageDatasetError):
                dataset.select_cases([first, second], **filters)
        second["family_id"] = first["family_id"]
        with self.assertRaises(dataset.PassageDatasetError):
            dataset.select_cases([first, second], split="test")


class PassageScoringTests(unittest.TestCase):
    def test_ranking_metric_math_and_failed_missing_denominators(self):
        cases = [fixture(suffix=str(i)) for i in range(4)]
        predictions = [{"case_id": cases[0]["case_id"], "status": "ok", "ranking": ["p3", "p2", "p1", "p0"]},
                       {"case_id": cases[1]["case_id"], "status": "error"},
                       {"case_id": cases[2]["case_id"], "status": "timeout"}]
        report = dataset.score_rankings(cases, predictions)
        row = report["rows"][0]
        self.assertEqual(row["ndcg@1"], 0)
        expected_ndcg = (1 / math.log2(3) + 3 / math.log2(4) + 7 / math.log2(5)) / (7 + 3 / math.log2(3) + 1 / math.log2(4))
        self.assertAlmostEqual(row["ndcg@4"], expected_ndcg)
        self.assertEqual(row["mrr@4"], 1 / 3)
        self.assertEqual(row["recall@1"], 0)
        self.assertEqual(row["recall@3"], .5)
        self.assertEqual(row["recall@4"], 1)
        self.assertEqual(report["total_cases"], 4)
        self.assertEqual(report["scored_cases"], 1)
        self.assertEqual(report["counts_by_status"]["missing"], 1)
        self.assertEqual(report["metrics"]["ndcg@4"]["defined_cases"], 1)
        self.assertEqual(report["by"]["question_language"]["fr"]["total_cases"], 4)
        self.assertNotIn("pass", report.values())

    def test_perfect_and_all_zero_rankings_are_not_both_perfect(self):
        good, poor = fixture(), fixture(suffix="poor", query_status="insufficient_visible_evidence", grades=(0, 0, 0, 0))
        poor["query"] = "Que dit cet autre ensemble de documents ?"
        report = dataset.score_rankings([good, poor], [{"case_id": c["case_id"], "status": "ok", "ranking": ["p0", "p1", "p2", "p3"]} for c in (good, poor)])
        self.assertEqual(report["rows"][0]["ndcg@4"], 1)
        for name in report["metrics"]:
            self.assertIsNone(report["rows"][1][name])
        self.assertEqual(report["metrics"]["ndcg@4"]["defined_cases"], 1)
        self.assertEqual(report["metrics"]["ndcg@4"]["eligible_cases"], 1)
        missing = dataset.score_rankings([good], [])
        self.assertEqual(missing["scored_cases"], 0)
        self.assertIsNone(missing["metrics"]["ndcg@4"]["mean"])

    def test_missing_predictions_penalize_eligible_mean_without_zeroing_undefined(self):
        first, second = fixture(), fixture(suffix="missing")
        prediction = {"case_id": first["case_id"], "status": "ok", "ranking": ["p0", "p1", "p2", "p3"]}
        report = dataset.score_rankings([first, second], [prediction])
        metric = report["metrics"]["ndcg@4"]
        self.assertEqual(metric["mean_conditional_on_observed"], 1)
        self.assertEqual(metric["mean_over_eligible_missing_zero"], .5)
        self.assertEqual(metric["eligible_cases"], 2)
        poor = fixture(suffix="poor", query_status="insufficient_visible_evidence", grades=(0, 0, 0, 0))
        undefined = dataset.score_rankings([poor], [prediction | {"case_id": poor["case_id"]}])
        for value in undefined["metrics"].values():
            self.assertEqual(value["eligible_cases"], 0)
            self.assertIsNone(value["mean_over_eligible_missing_zero"])

    def test_wrong_empty_duplicate_rankings_and_statuses_are_rejected(self):
        case = fixture()
        for ranking in ([], ["p0"], ["p0", "p1", "p2", "p2"], ["p0", "p1", "p2", "unknown"], "p0", [True, "p1", "p2", "p3"]):
            with self.subTest(ranking=ranking), self.assertRaises(dataset.PassageDatasetError):
                dataset.score_rankings([case], [{"case_id": case["case_id"], "status": "ok", "ranking": ranking}])
        for predictions in ([{"case_id": "wrong", "status": "error"}],
                            [{"case_id": case["case_id"], "status": "missing"}],
                            [{"case_id": case["case_id"], "status": "error", "ranking": ["p0"]}],
                            [{"case_id": case["case_id"], "status": "error"}] * 2):
            with self.assertRaises(dataset.PassageDatasetError):
                dataset.score_rankings([case], predictions)

    def test_choice_score_all_axes_correct_wrong_empty_and_partial_coverage(self):
        case = fixture()
        for axis in dataset.CHOICE_LABELS:
            requests = dataset.export_requests([case], axis)
            empty = dataset.score_choices([case], [], axis)
            self.assertEqual(empty["scored_cases"], 0)
            self.assertIsNone(empty["metrics"]["accuracy"]["mean"])
            predictions = []
            for request, row in zip(requests, empty["rows"]):
                choice = next(key for key, label in dataset.CHOICE_LABELS[axis].items() if label == row["expected_label"])
                predictions.append({key: value for key, value in request.items() if key in ("case_id", "axis", "passage_id", "claim_id")} |
                                   {"status": "ok", "choice_id": choice})
            report = dataset.score_choices([case], predictions, axis)
            self.assertEqual(report["metrics"]["accuracy"]["mean"], 1)
            self.assertEqual(report["accuracy_over_all"], 1)
            predictions[0]["choice_id"] = next(key for key in dataset.CHOICE_LABELS[axis] if key != predictions[0]["choice_id"])
            self.assertLess(dataset.score_choices([case], predictions, axis)["accuracy_over_all"], 1)
            predictions[0]["choice_id"] = ""
            with self.assertRaises(dataset.PassageDatasetError):
                dataset.score_choices([case], predictions, axis)


class PassageCLITests(unittest.TestCase):
    def test_overwrite_rejects_input_paths_and_filesystem_aliases(self):
        for command in ("export", "score"):
            for protected in ("dataset", "manifest", "predictions"):
                if command == "export" and protected == "predictions":
                    continue
                for alias in ("direct", "relative", "symlink", "hardlink"):
                    with self.subTest(command=command, protected=protected, alias=alias), tempfile.TemporaryDirectory() as folder:
                        path = write_fixture(folder, [fixture()])
                        manifest = path.parent / "manifest.json"
                        predictions = path.parent / "predictions.jsonl"
                        predictions.write_text(json.dumps({"case_id": "case-one", "status": "ok",
                                                           "ranking": ["p0", "p1", "p2", "p3"]}) + "\n")
                        source = {"dataset": path, "manifest": manifest, "predictions": predictions}[protected]
                        output = source
                        if alias == "relative":
                            (path.parent / "nested").mkdir()
                            output = path.parent / "nested" / ".." / source.name
                        elif alias == "symlink":
                            output = path.parent / "alias"
                            output.symlink_to(source)
                        elif alias == "hardlink":
                            output = path.parent / "alias"
                            output.hardlink_to(source)
                        before = {item: item.read_bytes() for item in (path, manifest, predictions)}
                        argv = [command, "--dataset", str(path), "--output", str(output), "--overwrite"]
                        # Cover both default and explicit manifest resolution.
                        if protected == "manifest" and alias in ("symlink", "hardlink"):
                            argv += ["--manifest", str(manifest)]
                        if command == "score":
                            argv += ["--predictions", str(predictions)]
                        with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as error:
                            dataset.main(argv)
                        self.assertEqual(error.exception.code, 2)
                        self.assertEqual({item: item.read_bytes() for item in before}, before)

    def test_validate_export_score_offline_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder, patch("socket.socket", side_effect=AssertionError("network forbidden")):
            path = write_fixture(folder, [fixture()])
            output = Path(folder) / "requests.jsonl"
            with redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(dataset.main(["validate", "--dataset", str(path)]), 0)
            self.assertEqual(json.loads(stdout.getvalue())["evaluation_status"], "not_run")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(dataset.main(["export", "--dataset", str(path), "--output", str(output)]), 0)
            self.assertEqual(len(output.read_text().splitlines()), 1)
            before = output.read_bytes()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(dataset.main(["export", "--dataset", str(path), "--output", str(output), "--overwrite"]), 0)
            self.assertEqual(output.read_bytes(), before)
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                dataset.main(["export", "--dataset", str(path), "--output", str(output)])
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(output.read_bytes(), before)
            predictions = Path(folder) / "predictions.jsonl"
            predictions.write_text(json.dumps({"case_id": "case-one", "status": "ok", "ranking": ["p0", "p1", "p2", "p3"]}) + "\n")
            report_path = Path(folder) / "score.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(dataset.main(["score", "--dataset", str(path), "--predictions", str(predictions), "--output", str(report_path)]), 0)
            self.assertEqual(json.loads(report_path.read_text())["metrics"]["ndcg@4"]["mean"], 1)
            predictions.write_text("")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(dataset.main(["score", "--dataset", str(path), "--predictions", str(predictions),
                                               "--output", str(report_path), "--overwrite"]), 0)
            empty_report = json.loads(report_path.read_text())
            self.assertEqual(empty_report["scoring_status"], "no_scored_predictions")
            self.assertEqual(empty_report["scored_cases"], 0)
            self.assertIn("dataset_sha256", empty_report)


if __name__ == "__main__":
    unittest.main()
