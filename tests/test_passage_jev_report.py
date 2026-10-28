import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench.campaigns import _encode, _hash
from deposium_bench.jev_http_adapter import _digest as jev_digest
from deposium_bench.passage_dataset import load_dataset
from deposium_bench.passage_observation import choice_plan, select_pilot

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/analyze-passage-jev.py"
spec = importlib.util.spec_from_file_location("passage_jev_report", SCRIPT)
jev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev)


def archive_files():
    profile = {"adapter": "jev_http", "qualification": "model_isolated",
               "capabilities": ["bench.context-choice"], "revision": None, "recordings": None,
               "model": {"model_id": jev.MODEL, "endpoint": "https://api.typesafe.ai/v1/systemone",
                         "budget_ledger": "/home/fixture-user/private-ledger.json", "credential_env": "TYPESAFE_API_KEY"}}
    initial = {"adapter": "jev_http", "qualification": "model_isolated", "available": True,
               "transport": "https_post_json", "input_protocol": "context_choice",
               "model": {"model_id": jev.MODEL, "budget_ledger": "/home/fixture-user/private-ledger.json"},
               "identity_sha256": "a" * 64, "adapter_sha256": "b" * 64, "profile_sha256": "c" * 64}
    summary = {"completion_status": "complete", "stop_reason": None,
               "physical_planned": jev.CALLS, "physical_attempted": jev.CALLS,
               "physical_statuses": {"ok": jev.CALLS},
               "adapter_initial": initial, "adapter_final": copy.deepcopy(initial)}
    manifest = {"execution_scope": "remote_http_model_isolated",
                "resource_observation": {"remote_model_ram": "not_observed"},
                "bench": {"files": {"jev_http_adapter.py": "b" * 64}}}
    cases, _ = load_dataset()
    _, physical = choice_plan(select_pilot(cases))
    assert len(physical) == jev.CALLS
    raw = []
    for i, request in enumerate(physical):
        usage = {"input_tokens": 100 + i % 3, "output_tokens": 10}
        selected = request["input"]["options"][0]
        raw.append({"call_id": request["case_id"], "request_sha256": _hash(_encode(request)),
                    "adapter_wall_ms": 3.0,
                    "response": {"status": "ok", "error": None, "output": {"choice_id": selected["id"]},
                                 "raw_output": {"http_attempted": True, "cached_failure": False,
                                                "http_status": 200, "requested_model": jev.MODEL,
                                                "observed_model": jev.MODEL,
                                                "native_result": {"model": jev.MODEL, "usage": usage,
                                                                  "answers": {"answer": {"choice": selected["description"]}}},
                                                "usage": usage, "attempt_id": f"attempt-{i}",
                                                "input_sha256": jev_digest(request["input"]),
                                                "request_body_sha256": "e" * 64,
                                                "response_sha256": "f" * 64, "http_ms": 2.0}}})
    return {"profile.json": _encode(profile), "manifest.json": _encode(manifest),
            "summary.json": _encode(summary), "adapter-initial.json": _encode(initial),
            "physical-requests.jsonl": b"".join(_encode(row) for row in physical),
            "raw.jsonl": b"".join(_encode(row) for row in raw)}


def partial_archive_files():
    """A self-contained trace shaped like the sealed 522-attempt interruption."""
    files = archive_files()
    physical = [json.loads(line) for line in files["physical-requests.jsonl"].splitlines()]
    raw = [json.loads(line) for line in files["raw.jsonl"].splitlines()][:522]
    rejected = raw[-1]["response"]
    native = rejected["raw_output"]["native_result"]
    options = physical[521]["input"]["options"]
    assert len(options) >= 2
    native["answers"]["answer"] = {
        "type": "choice", "choice": options[0]["description"], "confidence": 0.22,
        "probabilities": {option["description"]: 0.47 if i == 0 else 0.48 if i == 1 else 0.05
                          for i, option in enumerate(options)}}
    rejected.update(status="error", error="jev_response_invalid", output=None)
    rejected["raw_output"].update(observed_model=None, usage=None)
    files["raw.jsonl"] = b"".join(_encode(row) for row in raw)
    edit_json(files, "summary.json", lambda value: value.update(
        completion_status="incomplete", stop_reason="adapter_unavailable",
        physical_attempted=522, physical_statuses={"ok": 521, "error": 1},
        logical_statuses={"relevance": {"ok": 512, "error": 0, "missing": 0,
                                         "timeout": 0, "unsupported": 0, "abstain": 0},
                          "support": {"ok": 514, "error": 2, "missing": 252,
                                      "timeout": 0, "unsupported": 0, "abstain": 0},
                          "answerability": {"ok": 0, "error": 0, "missing": 128,
                                              "timeout": 0, "unsupported": 0, "abstain": 0}},
        adapter_final={**value["adapter_initial"], "available": False,
                       "availability_error": "jev_response_invalid"}))
    return files


def edit_json(files, name, fn):
    value = json.loads(files[name])
    fn(value)
    files[name] = _encode(value)


def edit_raw(files, fn):
    rows = [json.loads(line) for line in files["raw.jsonl"].splitlines()]
    fn(rows)
    files["raw.jsonl"] = b"".join(_encode(row) for row in rows)


class JevReportTests(unittest.TestCase):
    def test_interrupted_http_prefix_preserves_native_usage_and_protocol_error(self):
        files = partial_archive_files()
        result = jev.validate_jev_archive(files)
        self.assertEqual(result["campaign_status"], "incomplete")
        self.assertEqual((result["planned_http_calls"], result["http_attempts"]), (728, 522))
        self.assertEqual((result["validated_choice_calls"], result["protocol_error_calls"]), (521, 1))
        self.assertEqual((result["physical_inherited"], result["physical_new"]), (0, 522))
        self.assertEqual(result["input_tokens"], sum(100 + i % 3 for i in range(522)))
        self.assertEqual(result["output_tokens"], 5220)
        self.assertNotIn("/home/", json.dumps(result))

        broken = copy.deepcopy(files)
        edit_raw(broken, lambda rows: rows[-1]["response"]["raw_output"]
                 ["native_result"]["answers"]["answer"].update(
                     probabilities={description: 0.5 for description in rows[-1]["response"]
                                    ["raw_output"]["native_result"]["answers"]["answer"]
                                    ["probabilities"]}))
        with self.assertRaisesRegex(ValueError, "non-argmax"):
            jev.validate_jev_archive(broken)

    def test_interrupted_prefix_rejects_loss_or_tampering_of_relevance_http(self):
        files = partial_archive_files()
        lost = copy.deepcopy(files)
        edit_raw(lost, lambda rows: rows.pop(263))
        with self.assertRaises(ValueError):
            jev.validate_jev_archive(lost)
        tampered = copy.deepcopy(files)
        edit_raw(tampered, lambda rows: rows[263]["response"]["raw_output"].update(
            observed_model="jev-1.13.0"))
        with self.assertRaises(ValueError):
            jev.validate_jev_archive(tampered)

    def test_complete_http_trace_counts_actual_usage_without_private_profile(self):
        files = archive_files()
        result = jev.validate_jev_archive(files)
        self.assertEqual(result["http_attempts"], 728)
        self.assertEqual(result["input_tokens"], sum(100 + i % 3 for i in range(728)))
        self.assertEqual(result["output_tokens"], 7280)
        self.assertNotIn("/home/", json.dumps(result))
        self.assertNotIn("TYPESAFE_API_KEY", json.dumps(result))

    def test_wrong_adapter_version_and_fake_or_failed_http_are_rejected(self):
        changes = (
            lambda f: edit_json(f, "profile.json", lambda v: v.update(adapter="d3")),
            lambda f: edit_json(f, "profile.json", lambda v: v["model"].update(model_id="jev-1.13.0")),
            lambda f: edit_raw(f, lambda rows: rows[0]["response"]["raw_output"].update(observed_model="jev-1.13.0")),
            lambda f: edit_raw(f, lambda rows: rows[0]["response"]["raw_output"].update(http_attempted=False)),
            lambda f: edit_raw(f, lambda rows: rows[0]["response"].update(status="error", error="jev_http_unauthorized")),
            lambda f: edit_json(f, "summary.json", lambda v: v.update(completion_status="incomplete")),
            lambda f: f.update({"raw.jsonl": f["raw.jsonl"].splitlines(keepends=True)[0]}),
        )
        for change in changes:
            with self.subTest(change=change):
                files = archive_files()
                change(files)
                with self.assertRaises(ValueError):
                    jev.validate_jev_archive(files)

    def test_public_output_rejects_private_profile_locators(self):
        for secret in ("/home/fixture-user/private-ledger.json", "budget_ledger", "credential_env",
                       "TYPESAFE_API_KEY", "/tmp/private.json"):
            with self.subTest(secret=secret):
                with self.assertRaisesRegex(ValueError, "private"):
                    jev._assert_public({"unsafe": secret})

    def test_render_json_is_byte_stable_and_checks_producer_hash(self):
        names = ("input_order", "reversed_order", "baseline", "replacement", "complement")
        capture = {"sufficient_set@3": {"correct": 1, "eligible": 1},
                   "conflict_pair@3": {"correct": 1, "eligible": 1}}
        latency = {"count": 512, "median": 1000, "p95": 2000}
        data = {"schema_version": jev.SCHEMA, "rankings": {name: {"by": {axis: {"one": {}}
                    for axis in ("language_direction", "scenario_id", "view")}} for name in names},
                "by_rotation": {"0": {name: {} for name in names}},
                "evidence_capture": {name: capture for name in names},
                "grade_ties": {"overall": {"top_grade_ties": 1, "cases": 512}},
                "original_rotation_zero": {"support_scores": {"scored_cases": 514,
                    "total_decisions": 768, "accuracy_over_all": .5,
                    "counts_by_status": {"ok": 514, "error": 2, "missing": 252}},
                    "answerability_scores": {"scored_cases": 0, "total_decisions": 128,
                                             "accuracy_over_all": .0,
                                             "counts_by_status": {"ok": 0, "missing": 128}}},
                "latency_ms": {key: latency for key in ("bge_one_pool_actual",
                    "jev_four_relevance_choices_replayed_client_projection",
                    "complement_sequential_projection")},
                "jev_http": {"returned_model": jev.MODEL, "campaign_status": "incomplete",
                             "http_attempts": 522, "validated_choice_calls": 521,
                             "protocol_error_calls": 1, "physical_inherited": 104,
                             "physical_new": 418, "original_error_revalidated": 1,
                             "http_ms": {"median": 1000, "p95": 2000},
                             "input_tokens": 1000, "output_tokens": 100,
                             "estimated_usage_usd": "0.000042"},
                "dataset_sha256": "dataset", "ranking_input_sha256": "ranking",
                "source": {"producer_sha256": jev.order.digest(SCRIPT),
                           "order_producer_sha256": jev.order.digest(jev.ORDER_PATH),
                           "original_producer_sha256": jev.order.digest(jev.order._old_path)}}
        with tempfile.TemporaryDirectory() as directory, patch.object(
                jev.order.old, "rank_value", return_value="0"):
            root = Path(directory)
            source = root / "input.json"
            source.write_text(json.dumps(data, sort_keys=True))
            jev.main(["--render-json", str(source), "--output", str(root / "first")])
            jev.main(["--render-json", str(root / "first/analysis.json"), "--output", str(root / "second")])
            self.assertEqual((root / "first/analysis.json").read_bytes(),
                             (root / "second/analysis.json").read_bytes())
            self.assertEqual((root / "first/report.md").read_bytes(),
                             (root / "second/report.md").read_bytes())
            report = (root / "first/report.md").read_text()
            self.assertIn("0/128", report)
            self.assertIn("| answerability | 0/128 | — non mesuré |", report)
            self.assertNotIn("| answerability | 0/128 | 0.000", report)
            data["source"]["producer_sha256"] = "changed"
            source.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "Producer changed"):
                jev.main(["--render-json", str(source), "--output", str(root / "third")])

    def test_resume_requires_sealed_parent_and_exact_inherited_http_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "parent"
            parent.mkdir()
            child = partial_archive_files()
            prior = copy.deepcopy(child)
            prior_raw = [json.loads(line) for line in prior["raw.jsonl"].splitlines()][:104]
            failed = prior_raw[-1]["response"]
            failed.update(status="error", error="jev_response_invalid", output=None)
            failed["raw_output"].update(observed_model=None, usage=None)
            prior["raw.jsonl"] = b"".join(_encode(row) for row in prior_raw)
            edit_json(prior, "summary.json", lambda v: v.update(
                completion_status="incomplete", stop_reason="adapter_unavailable",
                physical_attempted=104, physical_statuses={"ok": 103, "error": 1}))
            digests = {}
            for name, payload in prior.items():
                (parent / name).write_bytes(payload)
                digests[name] = _hash(payload)
            (parent / "seal.json").write_bytes(_encode({"schema_version": "deposium.archive-seal/v1",
                                                       "files": digests, "sha256": _hash(_encode(digests))}))
            seal_hash = hashlib.sha256((parent / "seal.json").read_bytes()).hexdigest()
            edit_json(child, "manifest.json", lambda v: v.update(resume_parent={
                "path": str(parent.resolve()), "seal_sha256": seal_hash, "physical_inherited": 104}))
            edit_json(child, "summary.json", lambda v: v.update(
                physical_inherited=104, physical_new=418, resume_parent_seal_sha256=seal_hash))
            edit_raw(child, lambda rows: [rows[i].update(revalidated_from={
                "parent_seal_sha256": seal_hash,
                "prior_status": prior_raw[i]["response"]["status"],
                "prior_error": prior_raw[i]["response"]["error"]}) for i in range(104)])
            with self.assertRaisesRegex(ValueError, "resume-parent-archive"):
                jev.validate_jev_archive(child)
            result = jev.validate_jev_archive(child, parent)
            self.assertEqual((result["physical_inherited"], result["physical_new"],
                              result["original_error_revalidated"]), (104, 418, 1))
            forged = copy.deepcopy(child)
            edit_raw(forged, lambda rows: rows[0]["response"]["raw_output"].update(
                response_sha256="0" * 64))
            with self.assertRaisesRegex(ValueError, "Inherited JeV row"):
                jev.validate_jev_archive(forged, parent)
            forged = copy.deepcopy(child)
            edit_raw(forged, lambda rows: rows[103]["revalidated_from"].update(
                prior_error="not-an-error"))
            with self.assertRaisesRegex(ValueError, "Inherited JeV row"):
                jev.validate_jev_archive(forged, parent)


if __name__ == "__main__":
    unittest.main()
