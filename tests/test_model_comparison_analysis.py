"""Offline aggregate comparison and archive-integrity regressions."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from deposium_bench import campaigns
from deposium_bench.cases import candidate_request, load_cases
from deposium_bench.mastra_observation import observation_summary
from deposium_bench.mastra_pilot import (DATASET as MASTRA_DATASET, PROJECTION_VERSION,
    candidate_request as mastra_request, load_review_dataset, resolve_choice)
from deposium_bench.scoring import summarize

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/analyze-model-comparison.py"
spec = importlib.util.spec_from_file_location("model_comparison_analysis", SCRIPT)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
BASE_DATASET = ROOT / "datasets/context-choice-v1/cases.jsonl"
PROFILE = json.loads((ROOT / "profiles/julia-1-cpu-context.json").read_text())


def write(path, name, value):
    (path / name).write_bytes(value if isinstance(value, bytes) else campaigns._encode(value))


def reseal(path):
    files = {p.name: campaigns._hash(p.read_bytes()) for p in path.iterdir() if p.name != "seal.json"}
    write(path, "seal.json", {"schema_version": "deposium.archive-seal/v1", "files": files,
                              "sha256": campaigns._hash(campaigns._encode(files))})


def base_fixture(path, *, status="ok"):
    path.mkdir()
    cases, digest = load_cases(BASE_DATASET)
    profile_bytes = campaigns._encode(PROFILE)
    provenance = {"adapter": "julia", "model_repo_id": PROFILE["model"]["repo_id"],
                  "model_revision": PROFILE["revision"], "init_wall_ms": 50.0}
    records = []
    for i, case in enumerate(cases):
        choice = case["reference"]["assertions"][0]["value"]
        output = {"choice_id": choice} if status == "ok" else None
        records.append({"schema_version": campaigns.RESULT_VERSION, "case_id": case["case_id"],
                        "contract_id": case["contract_id"],
                        "request_sha256": campaigns._hash(campaigns._encode(candidate_request(case))),
                        "status": status, "output": output,
                        "raw_output": {"rss_mb": 125.0} if i % 2 == 0 else {},
                        "error": None, "duration_ms": float(i + 1)})
    raw = b"".join(campaigns._encode(row) for row in records)
    manifest = {"schema_version": campaigns.CAMPAIGN_VERSION, "run_id": "synthetic-complete",
                "mode": "run", "qualification": "model_isolated", "input_protocol": "context_choice",
                "dataset_sha256": digest, "profile_sha256": campaigns._hash(profile_bytes),
                "case_ids": [c["case_id"] for c in cases], "case_count": len(cases),
                "stack_context": {"components": [], "preflight_sha256": None},
                "adapter_provenance": provenance, "scorer": campaigns._scorer_fingerprint()}
    summary = {"schema_version": "deposium.campaign-summary/v1", "completion_status": "complete",
               "scorer": manifest["scorer"], "metrics": summarize(cases, records),
               "raw_sha256": campaigns._hash(raw)}
    for name, value in (("manifest.json", manifest), ("cases.jsonl", BASE_DATASET.read_bytes()),
                        ("profile.json", profile_bytes), ("raw.jsonl", raw),
                        ("summary.json", summary), ("report.md", b"synthetic\n")):
        write(path, name, value)
    reseal(path)
    return cases


def mastra_fixture(path):
    path.mkdir()
    cases, digest = load_review_dataset(MASTRA_DATASET)
    requests = [mastra_request(c) for c in cases]
    records = []
    for i, (case, request) in enumerate(zip(cases, requests)):
        output = {"choice_id": request["input"]["options"][0]["id"]}
        records.append({"case_id": case["case_id"], "request_sha256": campaigns._hash(campaigns._encode(request)),
                        "response": {"status": "ok", "output": output, "raw_output": {"rss_mb": 100.0}, "error": None},
                        "decision": resolve_choice(case, output), "adapter_wall_ms": float(i + 2),
                        "selection_scored": False, "first_call": i == 0})
    raw = b"".join(campaigns._encode(r) for r in records)
    initial = {"adapter": "julia", "model_repo_id": PROFILE["model"]["repo_id"],
               "model_revision": PROFILE["revision"], "init_wall_ms": 10.0}
    manifest = {"schema_version": "deposium.mastra-read-observation/v1", "mode": "local_single_pass",
                "qualification": "isolated_model_observation", "dataset_sha256": digest,
                "projection_version": PROJECTION_VERSION,
                "budget": {"max_calls": 24},
                "requests_sha256": campaigns._hash(b"".join(campaigns._encode(r) for r in requests)),
                "case_ids": [c["case_id"] for c in cases]}
    summary = {"schema_version": "deposium.mastra-read-observation-summary/v1",
               "completion_status": "complete", "stop_reason": None,
               "adapter_initial": initial, "adapter_final": initial,
               "metrics": observation_summary(cases, records)}
    for name, value in (("manifest.json", manifest), ("cases.jsonl", MASTRA_DATASET.read_bytes()),
                        ("requests.jsonl", b"".join(campaigns._encode(r) for r in requests)),
                        ("raw.jsonl", raw), ("profile.json", PROFILE),
                        ("adapter-initial.json", initial), ("summary.json", summary)):
        write(path, name, value)
    reseal(path)


class ModelComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / "base"
        self.mastra = self.root / "mastra"
        base_fixture(self.base)
        mastra_fixture(self.mastra)

    def test_aggregates_rank_and_private_output_boundary(self):
        weak = self.root / "weak"
        base_fixture(weak, status="timeout")
        # Replace only one result with valid, keeping summary and seal aligned.
        rows = [json.loads(line) for line in (weak / "raw.jsonl").read_bytes().split(b"\n") if line]
        source_rows = [json.loads(line) for line in (self.base / "raw.jsonl").read_bytes().split(b"\n") if line]
        rows[0] = source_rows[0]
        write(weak, "raw.jsonl", b"".join(campaigns._encode(r) for r in rows))
        summary = json.loads((weak / "summary.json").read_text())
        cases, _ = load_cases(BASE_DATASET)
        summary["metrics"] = summarize(cases, rows)
        summary["raw_sha256"] = campaigns._hash((weak / "raw.jsonl").read_bytes())
        write(weak, "summary.json", summary)
        reseal(weak)
        result = analysis.analyze([("Aweak", weak), ("Zstrong", self.base)], self.root / "out",
                                  [("Zstrong", self.mastra), ("Aweak", self.mastra)])
        self.assertEqual(list(result["base"]), ["Zstrong", "Aweak"])
        self.assertEqual(result["base"]["Zstrong"]["counts"]["correct"], 132)
        self.assertEqual(result["base"]["Aweak"]["counts"]["statuses"]["timeout"], 131)
        self.assertEqual(result["base"]["Zstrong"]["groups"]["language"]["fr"]["total"], 66)
        self.assertEqual(result["base"]["Zstrong"]["worker_rss_mib"]["unreported_calls"], 66)
        self.assertEqual(result["mastra"]["Zstrong"]["reference_review"], "pending_human")
        self.assertEqual(result["mastra"]["Zstrong"]["cases_scored"], 0)
        report = (self.root / "out" / "report.md").read_text()
        published = json.loads((self.root / "out" / "analysis.json").read_text())
        self.assertEqual(analysis._markdown(published), report)
        self.assertNotIn("synthetic:ctx-", report)
        self.assertNotIn("case_id", (self.root / "out" / "analysis.json").read_text())
        self.assertNotIn("\u2028", report)
        with self.assertRaises(analysis.AnalysisError):
            analysis.analyze([("strong", self.base)], self.root / "out")

    def test_mutated_raw_even_with_reseal_rejected(self):
        rows = [json.loads(line) for line in (self.base / "raw.jsonl").read_bytes().split(b"\n") if line]
        rows[0]["output"] = {}
        write(self.base, "raw.jsonl", b"".join(campaigns._encode(r) for r in rows))
        reseal(self.base)
        with self.assertRaises(analysis.AnalysisError):
            analysis.analyze([("a", self.base)], self.root / "out")

    def test_mixed_corpus_or_scorer_rejected(self):
        manifest = json.loads((self.base / "manifest.json").read_text())
        manifest["scorer"]["sha256"] = "0" * 64
        write(self.base, "manifest.json", manifest)
        reseal(self.base)
        with self.assertRaises(analysis.AnalysisError):
            analysis.analyze([("a", self.base)], self.root / "out")
        base_fixture(self.root / "second")
        mixed = self.root / "second"
        data = (mixed / "cases.jsonl").read_bytes().replace(b"catalog-active-inventory", b"catalog-other-inventory")
        write(mixed, "cases.jsonl", data)
        reseal(mixed)
        with self.assertRaises((analysis.AnalysisError, campaigns.CampaignError, ValueError)):
            analysis.analyze([("a", mixed)], self.root / "out")

    def test_zero_scored_and_mastra_mutation_rejected(self):
        empty = self.root / "zero"
        base_fixture(empty, status="error")
        with self.assertRaises(analysis.AnalysisError):
            analysis.analyze([("a", empty)], self.root / "out")
        rows = [json.loads(line) for line in (self.mastra / "raw.jsonl").read_bytes().split(b"\n") if line]
        rows[0]["first_call"] = False
        write(self.mastra, "raw.jsonl", b"".join(campaigns._encode(row) for row in rows))
        reseal(self.mastra)
        with self.assertRaises(analysis.AnalysisError):
            analysis.analyze([("a", self.base)], self.root / "out", [("a", self.mastra)])

    def test_measurement_coverage_truncation_and_safe_provenance(self):
        rows = [json.loads(line) for line in (self.base / "raw.jsonl").read_bytes().splitlines() if line]
        rows[0]["raw_output"].update({"encoding_info": {"tokens": 17, "state_tokens_dropped": 2},
                                      "token_components": {"max_sequence_tokens": 17, "total_tokens": 41},
                                      "inference_ms": 4.0, "decision_ms": 5.0,
                                      "usage": {"input_tokens": 50, "output_tokens": 2}})
        rows[1]["raw_output"]["usage"] = {"input_tokens": 70, "output_tokens": 3}
        write(self.base, "raw.jsonl", b"".join(campaigns._encode(row) for row in rows))
        manifest = json.loads((self.base / "manifest.json").read_text())
        manifest["adapter_provenance"]["runtime"] = {"python": "3.12.3", "secret_path": "/private/example",
                                                      "malicious": "https://secret.example"}
        manifest["adapter_provenance"]["settings"] = {"threads": 2, "dtype": "float32",
                                                       "loading_mode": "hf-automodel-fp32",
                                                       "backbone_dtype": "bfloat16", "readout_dtype": "float32",
                                                       "permutation_average": False,
                                                       "endpoint": "https://secret.example", "max_length": 4096}
        write(self.base, "manifest.json", manifest)
        cases, _ = load_cases(BASE_DATASET)
        summary = json.loads((self.base / "summary.json").read_text())
        summary["metrics"] = summarize(cases, rows)
        summary["raw_sha256"] = campaigns._hash((self.base / "raw.jsonl").read_bytes())
        write(self.base, "summary.json", summary)
        reseal(self.base)
        result = analysis.analyze([("candidate", self.base)], self.root / "out")
        item = result["base"]["candidate"]
        native = item["measurements"]["native_tokens"]
        self.assertEqual(native["encoded_tokens"]["count"], 1)
        self.assertEqual(native["indecis_max_sequence_tokens"]["max"], 17)
        self.assertEqual(native["indecis_sum_tokens"]["max"], 41)
        self.assertEqual(item["measurements"]["provider_declared_tokens"]["input_tokens"]["sum"], 120)
        provider_by_domain = item["provider_token_groups"]["domain"]["documentary"]["input_tokens"]
        self.assertEqual((provider_by_domain["count"], provider_by_domain["min"], provider_by_domain["max"]),
                         (2, 50, 70))
        self.assertEqual(sum(group["input_tokens"]["count"] for group in item["provider_token_groups"]["language"].values()), 2)
        self.assertEqual(sum(group["input_tokens"]["count"] for group in item["provider_token_groups"]["domain_language"].values()), 2)
        self.assertEqual(item["measurements"]["truncation"]["laya_state_tokens_dropped"]["positive"], 1)
        self.assertEqual(item["measurements"]["truncation"]["state"]["unknown"], 132)
        self.assertEqual(item["measurements"]["timing_by_status"]["ok"]["inference_ms"]["count"], 1)
        self.assertEqual(item["identity"]["settings"], {"threads": 2, "dtype": "float32", "max_length": 4096,
                                                     "loading_mode": "hf-automodel-fp32",
                                                     "backbone_dtype": "bfloat16", "readout_dtype": "float32",
                                                     "permutation_average": False})
        self.assertEqual(item["identity"]["runtime"], {"python": "3.12.3"})
        self.assertNotIn("secret.example", (self.root / "out" / "analysis.json").read_text())
        published = json.loads((self.root / "out" / "analysis.json").read_text())
        report = (self.root / "out" / "report.md").read_text()
        self.assertEqual(analysis._markdown(published), report)
        self.assertIn("Tokens fournisseur base par domaine × langue", report)
        self.assertIn("float32+float32(readout)", report)
        self.assertEqual(sum(group["total"] for group in item["groups"]["task_type"].values()), 132)

    def test_mastra_routing_and_length_have_denominators(self):
        result = analysis.analyze([("candidate", self.base)], self.root / "out",
                                  [("candidate", self.mastra)])
        item = result["mastra"]["candidate"]
        self.assertEqual(sum(item["by_proposed_action_language"]["search"][language]["total"]
                             for language in ("fr", "en")), item["by_proposed_action"]["search"]["total"])
        self.assertEqual(item["candidate_visible_length"]["characters"]["count"], 24)
        self.assertEqual(item["measurements"]["native_tokens"]["encoded_tokens"]["count"], 0)
        self.assertEqual(item["measurements"]["truncation"]["state"]["unknown"], 24)
        report = (self.root / "out" / "report.md").read_text()
        self.assertIn("Mastra par action proposée et langue", report)
        self.assertIn("Types de tâche, tous domaines", report)

    def test_indecis_sum_excludes_gliner_total_tokens(self):
        gliner = {"status": "ok", "duration_ms": 1.0,
                  "raw_output": {"encoding_info": {"tokens": 102},
                                 "token_components": {"total_tokens": 102, "padded_tokens": 128}}}
        indecis = {"status": "ok", "duration_ms": 2.0,
                   "raw_output": {"encoding_info": {"tokens": 25},
                                  "token_components": {"max_sequence_tokens": 25, "total_tokens": 105}}}
        gliner_tokens = analysis._measurements([gliner])["native_tokens"]
        indecis_tokens = analysis._measurements([indecis])["native_tokens"]
        self.assertEqual(gliner_tokens["encoded_tokens"]["max"], 102)
        self.assertEqual(gliner_tokens["indecis_sum_tokens"]["count"], 0)
        self.assertEqual(gliner_tokens["indecis_sum_tokens"]["unreported_calls"], 1)
        self.assertEqual(indecis_tokens["indecis_max_sequence_tokens"]["max"], 25)
        self.assertEqual(indecis_tokens["indecis_sum_tokens"]["max"], 105)

    def test_small_model_native_sequences_and_refusals_are_separate_from_latency(self):
        records = [
            {"status": "ok", "duration_ms": 8.0,
             "raw_output": {"encoding_info": {"full_input_tokens": 90, "encoded_tokens": 90},
                            "inference_ms": 5.0, "decision_ms": 6.0}},
            {"status": "unsupported", "duration_ms": 1.0,
             "raw_output": {"encoding_info": {"full_input_tokens": 300, "encoded_tokens": 200},
                            "inference_ms": 999.0}},
            {"status": "ok", "duration_ms": 9.0,
             "raw_output": {"encoding_info": {"tokens_per_option": [50, 54, 52],
                                               "padded_batch_tokens": 162},
                            "inference_ms": 7.0}},
            {"status": "unsupported", "duration_ms": 0.5,
             "raw_output": {"encoding_info": {"tokens_per_pair": [4097, 4080],
                                               "padded_batch_tokens": 8177}}},
        ]
        measurement = analysis._measurements(records)
        native = measurement["native_tokens"]
        self.assertEqual((native["full_input_tokens"]["count"], native["full_input_tokens"]["max"]), (2, 300))
        self.assertEqual((native["encoded_tokens"]["count"], native["encoded_tokens"]["max"]), (2, 200))
        self.assertEqual((native["max_sequence_tokens"]["count"], native["max_sequence_tokens"]["max"]), (4, 4097))
        self.assertEqual((native["sum_sequence_tokens"]["count"], native["sum_sequence_tokens"]["max"]), (4, 8177))
        self.assertEqual((native["padded_batch_tokens"]["count"], native["padded_batch_tokens"]["max"]), (2, 8177))
        self.assertEqual(native["indecis_sum_tokens"]["count"], 0)
        self.assertEqual((measurement["timing_ok"]["inference_ms"]["count"],
                          measurement["timing_ok"]["inference_ms"]["max"]), (2, 7.0))
        self.assertEqual(measurement["timing"]["inference_ms"]["max"], 999.0)
        self.assertEqual(measurement["timing_ok"]["adapter_ms"]["count"], 2)

    def test_mixed_report_uses_generic_sequence_labels_and_ok_timing(self):
        result = analysis.analyze([("candidate", self.base)], self.root / "out")
        item = result["base"]["candidate"]
        item["identity"]["adapter"] = "small_model"
        item["measurements"] = analysis._measurements([{
            "status": "ok", "duration_ms": 8.0,
            "raw_output": {"encoding_info": {"tokens_per_option": [20, 24],
                                              "padded_batch_tokens": 48}, "inference_ms": 5.0}},
            {"status": "unsupported", "duration_ms": 0.5,
             "raw_output": {"encoding_info": {"tokens_per_option": [513, 500],
                                               "padded_batch_tokens": 1026}}}])
        report = analysis._markdown(result)
        self.assertIn("Temps base ok (ms)", report)
        self.assertIn("max_sequence_tokens", report)
        self.assertIn("sum_sequence_tokens", report)
        self.assertIn("padded_batch_tokens", report)
        self.assertNotIn("unsupported / inference_ms", report)
        self.assertNotIn("indecis_max_sequence_tokens", report)
        self.assertNotIn("indecis_sum_tokens", report)


if __name__ == "__main__":
    unittest.main()
