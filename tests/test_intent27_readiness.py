"""Synthetic private-pack gates; no weights, network or model execution."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
import unittest

from deposium_bench import campaigns, chat_intent_v2_corpus as corpus
from tests import test_d3_27b_readiness as legacy
from tests.test_upstream_native_pilot import upstream, encoded

ROOT = Path(__file__).resolve().parents[1]


def payload(cases):
    return b"".join(campaigns._encode(case) for case in cases)


class Intent27ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = legacy.D327ReadinessTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.pack = self.root / "private-pack"
        self.pack.mkdir()
        self.cases = [corpus.make_case({"message_preview": f"Synthetic request number {i}.",
            "label": "search_query", "decision": "labeled", "reviewed_at": "2026-01-02T12:00:00Z",
            "split_group_id": f"synthetic-family-{i}"}, i, "en", "synthetic-pack",
            "calibration" if i < 14 else "test") for i in range(17)]
        for name, data in {"cases.jsonl": payload(self.cases), "protocol.frozen.json": b'{"synthetic":true}',
                           "intent-choice-cards.frozen.json": corpus.CARDS_PATH.read_bytes()}.items():
            (self.pack / name).write_bytes(data)
        self.pin_pack()
        self.args = deepcopy(self.fixture.args)
        self.args.execution_envelope = upstream.INTENT27_ENVELOPE
        self.args.intent_pack_root = self.pack
        self.args.intent_pack_manifest_sha256 = upstream.digest(self.pack / "manifest.json")
        self.args.dataset.write_bytes(payload(self.cases[:12]))

    def pin_pack(self):
        files = {p.name: upstream.digest(p) for p in self.pack.iterdir() if p.name != "manifest.json"}
        (self.pack / "manifest.json").write_bytes(campaigns._encode({
            "schema_version": "deposium.intent-private-pack/v2", "files": files}))

    def envelope(self, cases=None):
        return upstream.execution_envelope(self.args, upstream.D327_ASSETS, self.fixture.model,
                                           self.cases[:12] if cases is None else cases)

    def study(self):
        return self.envelope()[0]["study_binding"]

    def install_preparation(self):
        f = self.fixture
        f.canary = self.cases[:12]
        rows = [encoded(case, upstream.D327_ALIAS) for case in self.cases]
        for row in rows:
            row["variants"][0]["option_keys"] = [f"c{i}" for i in range(10)]
        rows.append(encoded({"input": upstream.overflow_input(4096)}, upstream.D327_ALIAS, negative=True))
        f.audit.write_bytes(payload(rows))
        f.prepared = upstream.preparation_map(f.audit, self.cases, upstream.D327_ALIAS, 4096, exact_cases=True)
        receipt = deepcopy(f.prep_receipt)
        receipt.update(schema_version="deposium.d3-27b-native-preparation/v2",
                       execution_envelope=upstream.INTENT27_ENVELOPE, study_binding=self.study(),
                       case_count=len(self.cases), audit_sha256=upstream.digest(f.audit))
        f.prep_payload = campaigns._encode(receipt)
        self.args.preparation_receipt.write_bytes(f.prep_payload)

    def synthetic_canary(self):
        self.install_preparation()
        f = self.fixture
        root, path, receipt = f.synthetic_canary()
        pilot = json.loads((root / "pilot.json").read_bytes())
        pilot["native_exit_code"] = 0
        pilot["execution_envelope"].update(name=upstream.INTENT27_ENVELOPE, study_binding=self.study())
        (root / "pilot.json").write_bytes(campaigns._encode(pilot))
        f.reseal(root)
        receipt.update(schema_version="deposium.d3-27b-calibration/v2",
                       execution_envelope=upstream.INTENT27_ENVELOPE, study_binding=self.study(),
                       canary_seal_sha256=upstream.digest(root / "pilot-seal.json"),
                       derivation=upstream.derive_phase_budgets([1000] * 12, study=self.study()))
        path.write_bytes(campaigns._encode(receipt))
        return root, path, receipt

    def test_canary_is_first_twelve_calibration_full_preparation_covers_entire_pack(self):
        envelope, preparation, canary = self.envelope()
        self.assertEqual(preparation, self.cases)
        self.assertEqual(canary, self.cases[:12])
        self.assertEqual({c["split"] for c in canary}, {"calibration"})
        self.assertEqual(envelope["admission_available_mib"], 32768)
        self.assertEqual(envelope["rss_limit_mib"], 24576)
        self.assertEqual(envelope["study_binding"]["case_count"], 17)
        self.args.phase, self.args.max_seconds = "intent", 214
        self.args.dataset = self.pack / "cases.jsonl"
        self.assertEqual(self.envelope(self.cases)[1], self.cases)

    def test_bad_pin_changed_member_and_foreign_rubric_fail_before_model_load(self):
        with patch.object(upstream.subprocess, "Popen", side_effect=AssertionError("model launched")):
            self.args.intent_pack_manifest_sha256 = "f" * 64
            with self.assertRaisesRegex(ValueError, "manifest_mismatch"):
                self.envelope()
            self.args.intent_pack_manifest_sha256 = upstream.digest(self.pack / "manifest.json")
            (self.pack / "cases.jsonl").write_bytes(payload(self.cases) + b"\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                self.envelope()
            changed = deepcopy(self.cases)
            changed[0]["input"]["question"] = "Synthetic changed question"
            (self.pack / "cases.jsonl").write_bytes(payload(changed))
            self.pin_pack()
            self.args.intent_pack_manifest_sha256 = upstream.digest(self.pack / "manifest.json")
            with self.assertRaises(ValueError):
                self.envelope()

    def test_no_test_warmup_subsets_or_reordered_canary_and_exact_full_bytes(self):
        for changed in (self.cases[1:13], list(reversed(self.cases[:12])), self.cases[:11], self.cases[-3:]):
            with self.subTest(selection=len(changed)), self.assertRaisesRegex(ValueError, "phase_dataset"):
                self.envelope(changed)
        self.args.phase, self.args.max_seconds = "intent", 214
        self.args.dataset.write_text("\n".join(json.dumps(c) for c in self.cases) + "\n")
        with self.assertRaisesRegex(ValueError, "full_phase_bytes"):
            self.envelope(self.cases)

    def test_explicit_envelope_has_no_fallback_to_legacy_or_flash(self):
        for name in (upstream.D327_ENVELOPE, upstream.DEFAULT_ENVELOPE, upstream.SMALL_ENVELOPE):
            self.args.execution_envelope = name
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "explicit_envelope"):
                self.envelope()

    def test_preparation_receipt_binds_new_pack_and_cannot_borrow_old_receipt(self):
        self.install_preparation()
        f = self.fixture
        upstream.d327_preparation_receipt(self.args.preparation_receipt, f.audit, f.prepared, study=self.study())
        receipt = json.loads(f.prep_payload)
        for field in ("dataset_sha256", "pack_manifest_sha256", "canary_sha256"):
            changed = deepcopy(receipt)
            changed["study_binding"][field] = "f" * 64
            self.args.preparation_receipt.write_bytes(campaigns._encode(changed))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "binding"):
                upstream.d327_preparation_receipt(self.args.preparation_receipt, f.audit, f.prepared, study=self.study())
        with self.assertRaises(ValueError):
            upstream.d327_preparation_receipt(self.args.preparation_receipt, f.audit, f.prepared)

    def test_calibration_checks_real_call_receipts_and_budget_without_accuracy_gate(self):
        root, path, receipt = self.synthetic_canary()
        f = self.fixture
        self.assertEqual(json.loads((root / "campaign/summary.json").read_bytes())["metrics"]["passed_cases"], 0)
        with patch.object(upstream.subprocess, "Popen", side_effect=AssertionError("calibration launched")):
            upstream.d327_calibration_receipt(path, "intent", 214, f.prep_payload,
                f.prepared, f.canary, f.runtime, study=self.study())
            for seconds in (213, 1800):
                with self.subTest(seconds=seconds), self.assertRaisesRegex(ValueError, "budget_mismatch"):
                    upstream.d327_calibration_receipt(path, "intent", seconds, f.prep_payload,
                        f.prepared, f.canary, f.runtime, study=self.study())
        receipt["study_binding"]["dataset_sha256"] = "f" * 64
        path.write_bytes(campaigns._encode(receipt))
        with self.assertRaisesRegex(ValueError, "binding"):
            upstream.d327_calibration_receipt(path, "intent", 214, f.prep_payload,
                f.prepared, f.canary, f.runtime, study=self.study())

    def test_sampled_memory_refusal_prevents_model_hash_and_launch(self):
        self.install_preparation()
        f = self.fixture
        study = self.study()
        original = upstream.digest
        def observed_digest(path):
            self.assertNotEqual(Path(path), f.model, "weights read before admission")
            return original(path)
        with patch.object(upstream, "ROOT", f.root), \
                patch.object(upstream, "execution_envelope", return_value=(
                    {"name": upstream.INTENT27_ENVELOPE, "study_binding": study}, self.cases, f.canary)), \
                patch.object(upstream, "validated_runtime", return_value=f.runtime), \
                patch.object(upstream, "memory_snapshot", return_value={"MemAvailable_mib": 32767}), \
                patch.object(upstream, "digest", side_effect=observed_digest), \
                patch.object(upstream.subprocess, "Popen", side_effect=AssertionError("model launched")), \
                self.assertRaisesRegex(ValueError, "insufficient_available_memory"):
            upstream.pilot(self.args)
        self.assertFalse(self.args.output.exists())

    def test_resealed_foreign_study_or_failed_native_exit_cannot_supply_calibration(self):
        root, path, receipt = self.synthetic_canary()
        f = self.fixture
        original = (root / "pilot.json").read_bytes()
        for mutation in (lambda p: p["execution_envelope"]["study_binding"].update(dataset_sha256="f" * 64),
                         lambda p: p.update(native_exit_code=1), lambda p: p.update(native_exit_code=False)):
            pilot = json.loads(original)
            mutation(pilot)
            (root / "pilot.json").write_bytes(campaigns._encode(pilot))
            f.reseal(root)
            receipt["canary_seal_sha256"] = upstream.digest(root / "pilot-seal.json")
            path.write_bytes(campaigns._encode(receipt))
            with self.assertRaisesRegex(ValueError, "canary_binding"):
                upstream.d327_calibration_receipt(path, "intent", 214, f.prep_payload,
                    f.prepared, f.canary, f.runtime, study=self.study())

    def test_missing_actual_native_call_cannot_be_hidden_by_resealing(self):
        root, path, receipt = self.synthetic_canary()
        f = self.fixture
        records = [json.loads(line) for line in (root / "campaign/raw.jsonl").read_bytes().splitlines()]
        records[0]["raw_output"]["http_attempted"] = False
        (root / "campaign/raw.jsonl").write_bytes(payload(records))
        f.reseal(root)
        receipt["canary_seal_sha256"] = upstream.digest(root / "pilot-seal.json")
        path.write_bytes(campaigns._encode(receipt))
        with self.assertRaises(ValueError):
            upstream.d327_calibration_receipt(path, "intent", 214, f.prep_payload,
                f.prepared, f.canary, f.runtime, study=self.study())

    def test_overslow_calibration_refuses_instead_of_clamping_phase_budget(self):
        self.assertEqual(upstream.derive_phase_budgets([1000] * 12, study=self.study())["phase_max_seconds"], {"intent": 214})
        study = {**self.study(), "case_count": 1000}
        with self.assertRaisesRegex(ValueError, "exceeds_declared_cap"):
            upstream.derive_phase_budgets([1000] * 12, study=study)
