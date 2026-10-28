"""Aggregate-only analysis fixtures; no adapter, model or service is started."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import campaigns
from deposium_bench.cases import load_cases
from deposium_bench.mastra_observation import observation_summary
from deposium_bench.mastra_pilot import (DATASET, PROJECTION_VERSION, candidate_request,
                                         load_review_dataset, resolve_choice)
from deposium_bench.noma_adapter import REPO_ID, REVISION, SOURCE_REVISION
from deposium_bench.scoring import summarize


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/analyze-noma-pilot.py"
spec = importlib.util.spec_from_file_location("noma_analysis_under_test", SCRIPT)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
PROFILE = Path(__file__).resolve().parents[1] / "profiles/noma-cpu-context.json"
BASE_DATASET = Path(__file__).resolve().parents[1] / "datasets/context-choice-v1/cases.jsonl"


def write(root, name, value):
    data = value if isinstance(value, bytes) else campaigns._encode(value)
    (root / name).write_bytes(data)


def seal(root):
    files = {path.name: campaigns._hash(path.read_bytes())
             for path in root.iterdir() if path.is_file() and path.name != "seal.json"}
    write(root, "seal.json", {"schema_version": "deposium.archive-seal/v1", "files": files,
                              "sha256": campaigns._hash(campaigns._encode(files))})


def mastra_fixture(root):
    root.mkdir()
    cases, digest = load_review_dataset()
    profile = json.loads(PROFILE.read_text())
    requests = [candidate_request(case) for case in cases]
    records = []
    for index, (case, request) in enumerate(zip(cases, requests)):
        response = ({"status": "ok", "output": {"choice_id": request["input"]["options"][0]["id"]},
                     "raw_output": {"native_tokens": 42, "rss_mb": 100.0,
                                    "decision_ms": 3.0, "inference_ms": 2.0,
                                    "forward_executed": True}, "error": None}
                    if index == 0 else
                    {"status": "unsupported", "output": None,
                     "raw_output": {"native_tokens": 0, "forward_executed": False, "rss_mb": 100.0},
                     "error": "noma_context_overflow"})
        records.append({"case_id": case["case_id"],
                        "request_sha256": campaigns._hash(campaigns._encode(request)),
                        "response": response,
                        "decision": resolve_choice(case, response["output"]) if index == 0 else None,
                        "adapter_wall_ms": 5.0 if index == 0 else 1.0,
                        "selection_scored": False, "first_call": index == 0})
    initial = {"adapter": "noma", "available": True, "model_repo_id": REPO_ID,
               "model_revision": REVISION, "source_revision": SOURCE_REVISION}
    manifest = {"schema_version": "deposium.mastra-read-observation/v1",
                "mode": "local_single_pass", "allow_remote": False,
                "qualification": "isolated_model_observation",
                "projection_version": PROJECTION_VERSION,
                "dataset_sha256": digest,
                "requests_sha256": campaigns._hash(b"".join(campaigns._encode(r) for r in requests)),
                "case_ids": [case["case_id"] for case in cases], "budget": {"max_calls": 24}}
    summary = {"schema_version": "deposium.mastra-read-observation-summary/v1",
               "completion_status": "complete", "stop_reason": None,
               "metrics": observation_summary(cases, records),
               "adapter_initial": initial, "adapter_final": initial}
    write(root, "cases.jsonl", DATASET.read_bytes())
    write(root, "requests.jsonl", b"".join(campaigns._encode(r) for r in requests))
    write(root, "raw.jsonl", b"".join(campaigns._encode(r) for r in records))
    for name, value in (("profile.json", profile), ("adapter-initial.json", initial),
                        ("manifest.json", manifest), ("summary.json", summary)):
        write(root, name, value)
    seal(root)
    return cases


def base_fixture(root):
    root.mkdir()
    cases, digest = load_cases(BASE_DATASET)
    profile = json.loads(PROFILE.read_text())
    profile_bytes = campaigns._encode(profile)
    raw = b""
    manifest = {"schema_version": campaigns.CAMPAIGN_VERSION, "run_id": "synthetic-test",
                "mode": "run", "qualification": "model_isolated",
                "input_protocol": "context_choice", "dataset_sha256": digest,
                "profile_sha256": campaigns._hash(profile_bytes),
                "case_ids": [case["case_id"] for case in cases], "case_count": len(cases),
                "stack_context": {"components": [], "preflight_sha256": None},
                "adapter_provenance": {"adapter": "noma", "model_repo_id": REPO_ID,
                                       "model_revision": REVISION, "source_revision": SOURCE_REVISION},
                "scorer": campaigns._scorer_fingerprint()}
    summary = {"schema_version": "deposium.campaign-summary/v1", "completion_status": "incomplete",
               "metrics": summarize(cases, []), "raw_sha256": campaigns._hash(raw)}
    write(root, "manifest.json", manifest)
    write(root, "cases.jsonl", BASE_DATASET.read_bytes())
    write(root, "profile.json", profile_bytes)
    write(root, "raw.jsonl", raw)
    write(root, "summary.json", summary)
    write(root, "report.md", b"# Synthetic test\n")
    seal(root)
    return cases


class NomaAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mastra = self.root / "mastra"
        self.base = self.root / "base"
        self.mastra_cases = mastra_fixture(self.mastra)
        self.base_cases = base_fixture(self.base)

    def test_regenerates_only_aggregates_without_model_import(self):
        output = self.root / "analysis.json"
        with patch.dict("sys.modules", {"noma": None}):
            report = analysis.analyze(self.mastra, self.base, output)
        self.assertEqual(report["schema_version"], analysis.SCHEMA)
        self.assertEqual(report["model"], REPO_ID)
        self.assertEqual(report["mastra"]["coverage"]["total"], 24)
        self.assertEqual(report["mastra"]["coverage"]["valid_decisions"], 1)
        self.assertEqual(report["base"]["counts"]["total"], 132)
        self.assertEqual(report["base"]["counts"]["scored"], 0)
        self.assertEqual(report["mastra"]["observations"]["timing_ok_only"]["first_call"]
                         ["decision_ms"]["count"], 1)
        self.assertEqual(report["mastra"]["observations"]["timing_ok_only"]["after_first_call"]
                         ["decision_ms"]["count"], 0)
        self.assertEqual(report["mastra"]["observations"]["native_tokens_forwarded"]["count"], 1)
        self.assertEqual(report["base"]["source"]["model_revision"], REVISION)
        self.assertEqual(report["base"]["source"]["source_revision"], SOURCE_REVISION)
        written = output.read_text()
        self.assertNotIn(self.mastra_cases[0]["candidate_input"]["message"], written)
        self.assertNotIn(self.base_cases[0]["input"]["context"], written)
        self.assertNotIn(self.mastra_cases[0]["case_id"], written)
        with self.assertRaises(analysis.AnalysisError):
            analysis.analyze(self.mastra, self.base, output)

    def test_tampered_seal_and_resealed_reference_or_projection_rejected(self):
        raw = self.mastra / "raw.jsonl"
        raw.write_bytes(raw.read_bytes() + b" ")
        with self.assertRaises(analysis.AnalysisError):
            analysis._mastra(self.mastra)
        mastra_fixture_replacement = self.root / "replacement"
        mastra_fixture(mastra_fixture_replacement)
        cases_path = mastra_fixture_replacement / "cases.jsonl"
        cases = analysis._load_lines(cases_path.read_bytes())
        cases[0]["reference"]["acceptable_choices"] = ["other-id"]
        write(cases_path.parent, cases_path.name, b"".join(campaigns._encode(c) for c in cases))
        seal(mastra_fixture_replacement)
        with self.assertRaises(analysis.AnalysisError):
            analysis._mastra(mastra_fixture_replacement)
        request_path = self.mastra / "requests.jsonl"
        requests = analysis._load_lines(request_path.read_bytes())
        requests[0]["input"]["question"] = "Changed projection"
        write(self.mastra, "requests.jsonl", b"".join(campaigns._encode(r) for r in requests))
        seal(self.mastra)
        with self.assertRaises(analysis.AnalysisError):
            analysis._mastra(self.mastra)

    def test_non_noma_profile_rejected_after_resigning(self):
        profile_path = self.mastra / "profile.json"
        profile = campaigns._decode(profile_path.read_bytes())
        profile["adapter"] = "indecis"
        write(self.mastra, "profile.json", profile)
        seal(self.mastra)
        with self.assertRaisesRegex(analysis.AnalysisError, "not_pinned_noma"):
            analysis._mastra(self.mastra)

    def test_lf_parser_keeps_unicode_line_separator_inside_json_string(self):
        data = campaigns._encode({"text": "before\u2028after"})
        self.assertEqual(analysis._load_lines(data), [{"text": "before\u2028after"}])
        with self.assertRaises(analysis.AnalysisError):
            analysis._load_lines(data.rstrip(b"\n"))
        with self.assertRaises(Exception):
            analysis._load_lines(b'{"x":1,"x":2}\n')


if __name__ == "__main__":
    unittest.main()
