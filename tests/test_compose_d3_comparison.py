"""Synthetic composition checks; copied aggregate rows are fixtures, not results."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.worker_transport import decode

SCRIPT = ROOT / "scripts/compose-d3-comparison.py"
spec = importlib.util.spec_from_file_location("d3_composer", SCRIPT)
composer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(composer)


def add_d3(current, label, source="D3nano"):
    for protocol in ("base", "mastra"):
        row = deepcopy(current[protocol][source])
        current[protocol][label] = row
        identity = row["identity"]
        repo, revision = composer.D3_MODELS[label.lower()]
        identity.update(adapter="d3", model_repo_id=repo, model_revision=revision,
                        profile_id=label.lower() + "-cpu-context-v1",
                        identity_sha256=hashlib.sha256(f"fixture:identity:{label}".encode()).hexdigest(),
                        model_assets_sha256=hashlib.sha256(f"fixture:assets:{label}".encode()).hexdigest())
        identity["settings"].pop("dtype", None)
        identity["settings"].update(device="cpu", backbone_dtype="bfloat16", readout_dtype="float32")
        for field in ("manifest_sha256", "raw_sha256", "seal_sha256", "seal_fingerprint"):
            row["source"][field] = hashlib.sha256(f"fixture:{protocol}:{label}:{field}".encode()).hexdigest()
    current["base_ranking"] = sorted(current["base"],
                                     key=lambda name: (-current["base"][name]["counts"]["correct"], name))


def fixtures(extra=()):
    vela = decode((ROOT / "docs/evidence/model-comparison-vela2-20261011/analysis.json").read_bytes())
    old = decode((ROOT / "docs/evidence/model-comparison-complete-20261010-sol/analysis.json").read_bytes())
    current = deepcopy(vela)
    for label, source in (("D3edge", "Vela03"), ("D3lite", "Vela03"), ("D3nano", "Vela08")):
        add_d3(current, label, source)
    for label in extra:
        add_d3(current, label)
    return current, old, vela


class CompositionTests(unittest.TestCase):
    def test_ties_have_same_rank_and_explicit_marker(self):
        current, old, vela = fixtures()
        base, mastra = composer.compose(current, old, vela)
        rows = composer.ranked(base, lambda item: item["counts"]["correct"])
        ranks = {label: (rank, tie) for rank, label, tie in rows}
        self.assertEqual(ranks["D3edge"], ranks["D3lite"])
        self.assertTrue(ranks["D3edge"][1])
        report = composer.render(base, mastra, current_hash="a" * 64, old_hash="b" * 64,
                                 vela_hash="d" * 64, producer_hash="c" * 64,
                                 current=current, old=old, vela=vela)
        self.assertIn("ex æquo | D3edge", report)
        self.assertIn("ex æquo | D3lite", report)
        self.assertIn("Routage Mastra : accord provisoire", report)
        self.assertIn("Mastra : FR (accord provisoire)", report)
        self.assertIn("Mastra : EN (accord provisoire)", report)
        self.assertIn("Accords / décisions valides / total", report)
        self.assertIn("backbone bfloat16, readout float32", report)

    def test_different_sol_corpus_is_rejected(self):
        current, old, vela = fixtures()
        for item in old["base"].values():
            item["source"]["dataset_sha256"] = "0" * 64
        with self.assertRaisesRegex(composer.CompositionError, "frozen corpus"):
            composer.compose(current, old, vela)

    def test_duplicate_sol_is_rejected(self):
        current, old, vela = fixtures()
        current["base"]["Sol"] = deepcopy(old["base"]["Sol"])
        current["mastra"]["Sol"] = deepcopy(old["mastra"]["Sol"])
        with self.assertRaisesRegex(composer.CompositionError, "without Sol"):
            composer.compose(current, old, vela)

    def test_bad_denominator_is_rejected(self):
        current, old, vela = fixtures()
        current["base"]["D3edge"]["groups"]["language"]["fr"]["total"] = 65
        with self.assertRaisesRegex(composer.CompositionError, "unexpected denominator"):
            composer.compose(current, old, vela)

    def test_historical_metric_changed_with_same_source_is_rejected(self):
        current, old, vela = fixtures()
        current["base"]["Jev"]["timing"]["initialization_ms"] = 1.0
        with self.assertRaisesRegex(composer.CompositionError, "Vela historical aggregate metrics changed"):
            composer.compose(current, old, vela)

    def test_sol_export_common_metric_changed_with_same_source_is_rejected(self):
        current, old, vela = fixtures()
        old["base"]["Jev"]["timing"]["initialization_ms"] = 1.0
        with self.assertRaisesRegex(composer.CompositionError, "historical aggregate metrics changed"):
            composer.compose(current, old, vela)

    def test_d3_precision_identity_is_checked(self):
        current, old, vela = fixtures()
        current["base"]["D3edge"]["identity"]["settings"]["readout_dtype"] = "bfloat16"
        with self.assertRaisesRegex(composer.CompositionError, "D3 model identity or CPU precision"):
            composer.compose(current, old, vela)

    def test_progressive_model_sets_and_frozen_d3_rows(self):
        for labels, expected in (((), 17), (("D3mini",), 18),
                                 (("D3mini", "D3flash"), 19)):
            current, old, vela = fixtures(labels)
            d3 = fixtures()[0]
            if labels:
                with self.assertRaisesRegex(composer.CompositionError, "historical D3 JSON required"):
                    composer.compose(current, old, vela)
            base, mastra = composer.compose(current, old, vela, d3)
            self.assertEqual(len(base), expected)
            self.assertEqual(set(base), set(mastra))
            report = composer.render(base, mastra, current_hash="a" * 64,
                                     old_hash="b" * 64, vela_hash="c" * 64,
                                     d3_hash="d" * 64, producer_hash="e" * 64,
                                     current=current, old=old, vela=vela)
            self.assertIn(f": {expected} modèles", report)
            self.assertIn("Export D3 historique de contrôle", report)
            if labels:
                self.assertIn("D3mini", report)
            if "D3flash" in labels:
                self.assertIn("D3flash", report)

    def test_flash_without_mini_and_unknown_model_are_rejected(self):
        for labels in (("D3flash",), ("D3mini", "D3unknown")):
            current, old, vela = fixtures(labels[:1])
            if "D3unknown" in labels:
                current["base"]["D3unknown"] = deepcopy(current["base"]["D3mini"])
                current["mastra"]["D3unknown"] = deepcopy(current["mastra"]["D3mini"])
            current["base_ranking"] = sorted(current["base"],
                                             key=lambda name: (-current["base"][name]["counts"]["correct"], name))
            with self.assertRaisesRegex(composer.CompositionError, "frozen D3 models"):
                composer.compose(current, old, vela, fixtures()[0])

    def test_frozen_d3_metric_and_new_model_revision_are_checked(self):
        current, old, vela = fixtures(("D3mini", "D3flash"))
        d3 = fixtures()[0]
        current["base"]["D3nano"]["timing"]["initialization_ms"] = 1.0
        with self.assertRaisesRegex(composer.CompositionError, "frozen D3 aggregate metrics changed"):
            composer.compose(current, old, vela, d3)
        current, old, vela = fixtures(("D3mini", "D3flash"))
        current["mastra"]["D3flash"]["identity"]["model_revision"] = "0" * 40
        with self.assertRaisesRegex(composer.CompositionError, "base/Mastra model identity mismatch"):
            composer.compose(current, old, vela, d3)
        current, old, vela = fixtures(("D3mini",))
        for protocol in ("base", "mastra"):
            current[protocol]["D3mini"]["identity"]["model_revision"] = "0" * 40
        with self.assertRaisesRegex(composer.CompositionError, "D3 model identity or CPU precision"):
            composer.compose(current, old, vela, d3)

    def test_published_legacy_report_renders_byte_for_byte(self):
        current = decode((ROOT / "docs/evidence/model-comparison-d3-20261011/analysis.json").read_bytes())
        old = decode((ROOT / "docs/evidence/model-comparison-complete-20261010-sol/analysis.json").read_bytes())
        vela = decode((ROOT / "docs/evidence/model-comparison-vela2-20261011/analysis.json").read_bytes())
        manifest = json.loads((ROOT / "docs/evidence/model-comparison-d3-overview-20261011/manifest.json").read_text())
        base, mastra = composer.compose(current, old, vela)
        report = composer.render(base, mastra, current_hash=manifest["current_json_sha256"],
                                 old_hash=manifest["sol_json_sha256"],
                                 vela_hash=manifest["vela_json_sha256"],
                                 producer_hash=manifest["producer_sha256"],
                                 current=current, old=old, vela=vela)
        self.assertEqual(report.encode(),
                         (ROOT / "docs/evidence/model-comparison-d3-overview-20261011/report.md").read_bytes())

    def test_cli_writes_only_to_new_destination(self):
        current, _, _ = fixtures()
        with tempfile.TemporaryDirectory(prefix="d3-composer-fixture-") as temporary:
            temporary = Path(temporary)
            inputs = temporary / "inputs"
            inputs.mkdir()
            synthetic = inputs / "synthetic-current.json"
            synthetic.write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")
            output = temporary / "composed"
            command = [sys.executable, "-B", str(SCRIPT), "--bench-root", str(ROOT),
                       "--current-json", str(synthetic),
                       "--vela-json", str(ROOT / "docs/evidence/model-comparison-vela2-20261011/analysis.json"),
                       "--sol-json", str(ROOT / "docs/evidence/model-comparison-complete-20261010-sol/analysis.json"),
                       "--output-dir", str(output)]
            first = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("17 modèles", (output / "report.md").read_text(encoding="utf-8"))
            self.assertNotIn("d3_json_sha256", json.loads((output / "manifest.json").read_text()))
            second = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("already exists", second.stderr)

    def test_cli_requires_pinned_d3_for_mini_and_records_it_only_when_used(self):
        current = decode((ROOT / "docs/evidence/model-comparison-d3-20261011/analysis.json").read_bytes())
        add_d3(current, "D3mini")
        with tempfile.TemporaryDirectory(prefix="d3-composer-pinned-") as temporary:
            temporary = Path(temporary)
            inputs = temporary / "inputs"
            inputs.mkdir()
            synthetic = inputs / "current.json"
            synthetic.write_text(json.dumps(current), encoding="utf-8")
            d3_path = ROOT / "docs/evidence/model-comparison-d3-20261011/analysis.json"
            command = [sys.executable, "-B", str(SCRIPT), "--bench-root", str(ROOT),
                       "--current-json", str(synthetic),
                       "--vela-json", str(ROOT / "docs/evidence/model-comparison-vela2-20261011/analysis.json"),
                       "--sol-json", str(ROOT / "docs/evidence/model-comparison-complete-20261010-sol/analysis.json"),
                       "--output-dir", str(temporary / "out")]
            missing = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertIn("historical D3 JSON required", missing.stderr)
            self.assertFalse((temporary / "out").exists())
            tampered = inputs / "tampered.json"
            tampered.write_bytes(d3_path.read_bytes() + b" ")
            rejected = subprocess.run(command + ["--d3-json", str(tampered)],
                                      capture_output=True, text=True, check=False)
            self.assertIn("historical D3 JSON bytes changed", rejected.stderr)
            self.assertFalse((temporary / "out").exists())
            accepted = subprocess.run(command + ["--d3-json", str(d3_path)],
                                      capture_output=True, text=True, check=False)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            manifest = json.loads((temporary / "out/manifest.json").read_text())
            self.assertEqual(manifest["models"], 18)
            self.assertEqual(manifest["d3_json_sha256"], composer.D3_EXPORT_SHA)
            add_d3(current, "D3flash")
            synthetic.write_text(json.dumps(current), encoding="utf-8")
            flash_command = command.copy()
            flash_command[-1] = str(temporary / "out-flash")
            flash = subprocess.run(flash_command + ["--d3-json", str(d3_path)],
                                   capture_output=True, text=True, check=False)
            self.assertEqual(flash.returncode, 0, flash.stderr)
            flash_manifest = json.loads((temporary / "out-flash/manifest.json").read_text())
            self.assertEqual(flash_manifest["models"], 19)
            self.assertIn("D3flash", (temporary / "out-flash/report.md").read_text())


if __name__ == "__main__":
    unittest.main()
