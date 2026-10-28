"""Offline length report contracts, using only synthetic aggregate fixtures."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import campaigns

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("length_comparison_analysis", ROOT / "scripts/analyze-length-comparison.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def row(target, index, *, status="ok", correct=True, kind="none", timing=10.0):
    return {"target": target, "domain": ("documentary", "mathematics", "chemistry")[index % 3],
            "language": ("fr", "en")[index % 2], "position": ("start", "middle", "end")[(index // 2) % 3],
            "family": f"family-{index % 9}", "status": status,
            "scored": status in {"ok", "abstain"}, "correct": correct if status == "ok" else False,
            "failure_kind": kind, "cached_failure": False if status == "ok" else None,
            "forward_executed": status == "ok" if status != "missing" else None,
            "measurements": {"adapter_duration_ms": timing if status != "missing" else None,
                             "decision_ms": timing - 1 if status == "ok" else None,
                             "inference_ms": timing - 2 if status == "ok" else None,
                             "http_ms": None, "native_tokens": 101 if status == "ok" else None,
                             "native_total_tokens": 121 if status == "ok" else None,
                             "native_padded_tokens": 104 if status == "ok" else None,
                             "rss_mib": 500 if status == "ok" else None,
                             "provider_input_tokens": None, "provider_output_tokens": None,
                             "reference_actual_tokens": target,
                             "reference_padded_tokens": (target + 7) // 8 * 8}}


def synthetic_rows():
    return [row(target, index) for target in analysis.TARGETS for index in range(54)]


def fake_source(label, *, raw=None, corpus=None):
    adapter = {"Jev": "jev_http"}.get(label, label.lower())
    return synthetic_rows(), {"run_id": "synthetic-run", "dataset_sha256": corpus or analysis.DATASET_SHA256,
                              "raw_sha256": raw or analysis.RAW_SHA256[label],
                              "seal_sha256": campaigns._hash(b"seal"), "identity": {"adapter": adapter}}


class LengthComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = [(label, self.root / label) for label in analysis.MODELS]
        for _, path in self.inputs:
            path.mkdir()
            (path / "seal.json").write_bytes(b"seal")
        pin = patch.dict(analysis.SEAL_SHA256, {label: campaigns._hash(b"seal") for label in analysis.MODELS})
        pin.start()
        self.addCleanup(pin.stop)

    def test_status_denominators_latency_and_distinct_token_units(self):
        rows = [row(100, 0), row(100, 1, status="unsupported", kind="target_unattainable"),
                row(100, 2, status="unsupported", kind="typed_overflow"),
                row(100, 3, status="error", kind="memory_guard"),
                row(100, 4, status="missing", kind="missing")]
        result = analysis._aggregate(rows)
        self.assertEqual((result["correct"], result["scored"], result["planned"]), (1, 1, 5))
        self.assertEqual(result["coverage"], .2)
        self.assertEqual(result["failure_kinds"]["target_unattainable"], 1)
        self.assertEqual(result["failure_kinds"]["typed_overflow"], 1)
        self.assertEqual(result["failure_kinds"]["memory_guard"], 1)
        self.assertEqual(result["statuses"]["missing"], 1)
        self.assertEqual(result["latency_ms"]["adapter_duration_ms"]["all_recorded"]["count"], 4)
        self.assertEqual(result["latency_ms"]["inference_ms"]["successful"]["count"], 1)
        self.assertEqual(result["latency_ms"]["inference_ms"]["by_status"]["error"]["count"], 0)
        self.assertEqual(result["resources"]["native_tokens"]["max"], 101)
        self.assertEqual(result["resources"]["native_total_tokens"]["max"], 121)
        self.assertEqual(result["resources"]["provider_input_tokens"]["count"], 0)
        self.assertEqual(result["resources"]["rss_mib"]["unreported"], 4)

    def test_report_is_reproducible_from_json_and_aggregate_only(self):
        def load(path):
            return fake_source(Path(path).name)
        with patch.object(analysis, "_source", side_effect=load):
            result = analysis.analyze(self.inputs, self.root / "report", ["Eos", "Noma", "Laya"])
        published = json.loads((self.root / "report/analysis.json").read_text())
        markdown = (self.root / "report/report.md").read_text()
        self.assertEqual(published, result)
        self.assertEqual(analysis._markdown(published), markdown)
        self.assertEqual(list(published["not_measured"]), ["Eos", "Laya", "Noma"])
        self.assertIsNone(published["not_measured"]["Eos"]["coverage"])
        self.assertEqual(published["models"]["Julia"]["overall"]["independent_families"], 9)
        self.assertIn("Longueur × domaine × langue × position", markdown)
        self.assertIn("Statuts et types d'échec", markdown)
        for forbidden in ("family-0", "synthetic-secret-context", str(self.root), "case_id", "raw_output"):
            self.assertNotIn(forbidden, markdown + (self.root / "report/analysis.json").read_text())
        with self.assertRaises(analysis.AnalysisError):
            analysis.analyze(self.inputs, self.root / "report")

    def test_resealed_trace_digest_and_mixed_corpus_are_rejected(self):
        for changed in ("raw", "seal", "corpus"):
            def load(path):
                label = Path(path).name
                rows, source = fake_source(label)
                if label == "GLiNER":
                    source[{"raw": "raw_sha256", "seal": "seal_sha256", "corpus": "dataset_sha256"}[changed]] = "0" * 64
                return rows, source
            with self.subTest(changed=changed), patch.object(analysis, "_source", side_effect=load):
                with self.assertRaises(analysis.AnalysisError):
                    analysis.analyze(self.inputs, self.root / changed)
                self.assertFalse((self.root / changed).exists())

    def test_missing_archive_or_model_is_rejected_before_output(self):
        with self.assertRaises(analysis.AnalysisError):
            analysis.analyze(self.inputs[:-1], self.root / "omitted")
        self.inputs[0][1].rename(self.root / "moved")
        with self.assertRaises(analysis._comparison.AnalysisError):
            analysis.analyze(self.inputs, self.root / "missing")
        self.assertFalse((self.root / "missing").exists())

    def test_seal_inventory_rejects_mutation_even_before_trace_pin(self):
        archive = self.root / "sealed"
        archive.mkdir()
        (archive / "raw.jsonl").write_bytes(b"{}\n")
        files = {"raw.jsonl": campaigns._hash(b"{}\n")}
        seal = {"schema_version": "deposium.archive-seal/v1", "files": files,
                "sha256": campaigns._hash(campaigns._encode(files))}
        (archive / "seal.json").write_bytes(campaigns._encode(seal))
        analysis._sealed_files(archive, {"raw.jsonl"})
        (archive / "raw.jsonl").write_bytes(b'{"changed":true}\n')
        with self.assertRaises(analysis._comparison.AnalysisError):
            analysis._sealed_files(archive, {"raw.jsonl"})


if __name__ == "__main__":
    unittest.main()
