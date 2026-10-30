"""Offline 27B admission checks; synthetic receipts never qualify a real model."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import campaigns
from deposium_bench.cases import candidate_request, parse_cases
from tests.test_upstream_native_pilot import upstream, encoded

ROOT = Path(__file__).resolve().parents[1]


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def lines(values):
    return b"".join(campaigns._encode(v) for v in values)


class D327ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packs = {}
        for phase, (name, _, _) in upstream.D327_PACKS.items():
            source = ROOT / "datasets" / name / "cases.jsonl"
            target = self.root / "datasets" / name / "cases.jsonl"
            target.parent.mkdir(parents=True)
            target.write_bytes(source.read_bytes())
            self.packs[phase], _ = parse_cases(source.read_bytes())
        indexed = {c["case_id"]: c for c in self.packs["capability"]}
        self.canary = [indexed[key] for key in upstream.D327_CANARY_IDS]
        (self.root / "native").mkdir()
        (self.root / "native/systemone-preflight.cpp").write_bytes((ROOT / "native/systemone-preflight.cpp").read_bytes())
        for relative in ("docs/D3_27B_CAPABILITY_PROTOCOL_20261030.md", "plans/d3-27b-capability-v1.json"):
            target = self.root / relative
            target.parent.mkdir(exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        self.model = self.root / upstream.D327_ASSETS["files"][0]["path"]
        self.model.write_text("synthetic unit-test placeholder, never model weights")
        self.assets = self.root / "assets.json"
        self.assets.write_text(json.dumps(upstream.D327_ASSETS))
        self.dataset = self.root / "canary.jsonl"
        self.dataset.write_bytes(lines(self.canary))
        self.audit = self.root / "audit.jsonl"
        self.args = argparse.Namespace(dataset=self.dataset, output=self.root / "results/session", model=self.model,
            assets_manifest=self.assets, source_root=self.root, binary=self.root / "llama-server",
            runtime_manifest=self.root / "runtime.json", preparation=self.audit,
            model_id=upstream.D327_ALIAS, decision_type="d3", task="choices", technical_only=False,
            execution_envelope=upstream.D327_ENVELOPE, phase="canary", preparation_receipt=self.root / "preparation.json",
            calibration_receipt=None, port=11438, context=4096, max_rss_mb=24576, min_free_mb=8192, max_seconds=600)
        self.rows = [encoded(c, upstream.D327_ALIAS) for c in self.packs["anchor"] + self.packs["capability"]]
        self.rows.append(encoded({"input": upstream.overflow_input(4096)}, upstream.D327_ALIAS, negative=True))
        self.audit.write_bytes(lines(self.rows))
        self.prep_receipt = {"schema_version": "deposium.d3-27b-native-preparation/v1",
            "execution_envelope": upstream.D327_ENVELOPE, "model_id": upstream.D327_ALIAS,
            "model_assets": deepcopy(upstream.D327_ASSETS), "native_revision": upstream.PIN,
            "helper": {"source_sha256": upstream.digest(ROOT / "native/systemone-preflight.cpp"),
                       "binary_sha256": "1" * 64, "build_manifest_sha256": "2" * 64},
            "audit_sha256": upstream.digest(self.audit), "case_count": 324, "overflow_controls": 1,
            "resources": {"rss_limit_mib": 2048, "reserve_mib": 8192, "max_seconds": 600,
                "rss_peak_mib": 128, "min_available_mib": 50000, "elapsed_seconds": 2,
                "stop_reason": None, "completed": True}}
        self.prep_payload = campaigns._encode(self.prep_receipt)
        self.args.preparation_receipt.write_bytes(self.prep_payload)
        self.prepared = upstream.preparation_map(self.audit, self.packs["anchor"] + self.packs["capability"],
                                               upstream.D327_ALIAS, 4096, exact_cases=True)
        self.runtime = {"repository": upstream.REPOSITORY, "revision": upstream.PIN, "binary_sha256": "3" * 64}

    def test_exact_27b_envelope_selects_all324_and_original_twelve_calibration_cases(self):
        with patch.object(upstream, "ROOT", self.root):
            envelope, prepared, canary = upstream.execution_envelope(self.args, upstream.D327_ASSETS, self.model, self.canary)
        self.assertEqual(envelope["admission_available_mib"], 32768)
        self.assertEqual(envelope["rss_limit_mib"], 24576)
        self.assertEqual(len(prepared), 324)
        self.assertEqual([c["case_id"] for c in canary], list(upstream.D327_CANARY_IDS))
        self.assertEqual({c["split"] for c in canary}, {"calibration"})

    def test_default_flash_clef_envelope_stays_at18g_and_never_implicitly_selects27b(self):
        args = deepcopy(self.args)
        args.execution_envelope = upstream.DEFAULT_ENVELOPE
        args.phase = args.preparation_receipt = None
        args.max_rss_mb = 18432
        assets = {"repo_id": "fixture/model", "files": [{"sha256": "4" * 64}]}
        for decision in ("d3", "clef"):
            args.decision_type = decision
            result, _, _ = upstream.execution_envelope(args, assets, Path("fixture.gguf"), self.canary)
            self.assertEqual(result, {"name": upstream.DEFAULT_ENVELOPE})
        with self.assertRaisesRegex(ValueError, "explicit_envelope"):
            upstream.execution_envelope(args, upstream.D327_ASSETS, self.model, self.canary)
        args.max_rss_mb = 24576
        with self.assertRaisesRegex(ValueError, "fixed_envelope"):
            upstream.execution_envelope(args, assets, Path("fixture.gguf"), self.canary)
        args.max_rss_mb, args.max_seconds = 18432, 1800
        with self.assertRaisesRegex(ValueError, "fixed_envelope"):
            upstream.execution_envelope(args, assets, Path("fixture.gguf"), self.canary)

    def test_wrong_asset_type_alias_phase_or_bounds_refuse_before_hash_or_launch(self):
        variants = [({"repo_id": "ggml-org/vllm-d3-flash-GGUF"}, {}),
                    ({"revision": "f" * 40}, {}), ({}, {"decision_type": "clef"}),
                    ({}, {"task": "passages"}), ({}, {"model_id": "d3-flash-q8"}),
                    ({}, {"execution_envelope": "unknown"}), ({}, {"phase": None}),
                    ({}, {"context": 8192}), ({}, {"max_rss_mb": 18432}),
                    ({}, {"min_free_mb": 4096}), ({}, {"max_seconds": 601}),
                    ({}, {"max_seconds": 599})]
        for asset_change, arg_change in variants:
            assets, args = {**deepcopy(upstream.D327_ASSETS), **asset_change}, deepcopy(self.args)
            for key, value in arg_change.items():
                setattr(args, key, value)
            self.assets.write_text(json.dumps(assets))
            with self.subTest(changes=arg_change or asset_change), patch.object(upstream, "ROOT", self.root), \
                    patch.object(upstream, "selected_inputs", return_value=(self.dataset.read_bytes(), {}, self.canary, None, self.canary[0])), \
                    patch.object(upstream, "digest", side_effect=AssertionError("invalid candidate reached a hash")), \
                    patch.object(upstream.subprocess, "Popen", side_effect=AssertionError("invalid candidate launched")), \
                    self.assertRaises(ValueError):
                upstream.pilot(args)
            self.assertFalse(self.args.output.exists())
        for entry_change in ({"path": "other.gguf"}, {"size": 1}, {"sha256": "f" * 64}):
            assets = deepcopy(upstream.D327_ASSETS)
            assets["files"][0].update(entry_change)
            with patch.object(upstream, "ROOT", self.root), self.assertRaises(ValueError):
                upstream.execution_envelope(self.args, assets, self.model, self.canary)

    def test_phase_binding_refuses_subset_reordering_and_changed_frozen_pack(self):
        with patch.object(upstream, "ROOT", self.root):
            for cases in (self.canary[:-1], list(reversed(self.canary)), self.packs["anchor"][:12]):
                with self.subTest(cases=len(cases)), self.assertRaisesRegex(ValueError, "phase_dataset"):
                    upstream.execution_envelope(self.args, upstream.D327_ASSETS, self.model, cases)
            path = self.root / "datasets/context-choice-v1/cases.jsonl"
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "frozen_dataset"):
                upstream.execution_envelope(self.args, upstream.D327_ASSETS, self.model, self.canary)

    def test_full_phase_requires_frozen_bytes_as_well_as_equivalent_case_objects(self):
        args = deepcopy(self.args)
        args.phase, args.max_seconds = "anchor", 444
        args.dataset = self.root / "reformatted-context.jsonl"
        args.dataset.write_bytes(lines(self.packs["anchor"]))
        with patch.object(upstream, "ROOT", self.root), self.assertRaisesRegex(ValueError, "full_phase_bytes"):
            upstream.execution_envelope(args, upstream.D327_ASSETS, self.model, self.packs["anchor"])

    def test_preparation_requires_all324_plus_exact_overflow_even_for_canary(self):
        self.assertEqual(len(self.prepared["request_tokens"]), 324)
        for mutate in (lambda r: r.pop(0),
                       lambda r: r.append({**deepcopy(r[0]), "case_id": "unexpected-extra"}),
                       lambda r: r[-1].update(request_body_sha256="f" * 64),
                       lambda r: r[0].update(request_body_sha256="f" * 64),
                       lambda r: r[0].update(weights_loaded=True)):
            rows = deepcopy(self.rows)
            mutate(rows)
            self.audit.write_bytes(lines(rows))
            with self.assertRaises(ValueError):
                upstream.preparation_map(self.audit, self.packs["anchor"] + self.packs["capability"],
                                         upstream.D327_ALIAS, 4096, exact_cases=True)

    def test_preparation_receipt_binds_model_helper_audit_and_actual_resource_observations(self):
        with patch.object(upstream, "ROOT", self.root):
            payload, actual = upstream.d327_preparation_receipt(self.args.preparation_receipt, self.audit, self.prepared)
        self.assertEqual(payload, self.prep_payload)
        self.assertEqual(actual, self.prep_receipt)
        for mutate in (lambda r: r.update(model_id="d3-flash-q8"),
                       lambda r: r["model_assets"].update(revision="f" * 40),
                       lambda r: r["helper"].update(source_sha256="f" * 64),
                       lambda r: r.update(audit_sha256="f" * 64),
                       lambda r: r.update(case_count=12),
                       lambda r: r["resources"].update(stop_reason="rss_limit"),
                       lambda r: r["resources"].update(completed=False),
                       lambda r: r["resources"].update(rss_peak_mib=2049),
                       lambda r: r["resources"].update(min_available_mib=8191),
                       lambda r: r["resources"].update(elapsed_seconds=601),
                       lambda r: r.update(extra="unknown")):
            receipt = deepcopy(self.prep_receipt)
            mutate(receipt)
            self.args.preparation_receipt.write_bytes(campaigns._encode(receipt))
            with patch.object(upstream, "ROOT", self.root), self.assertRaises(ValueError):
                upstream.d327_preparation_receipt(self.args.preparation_receipt, self.audit, self.prepared)

    def test_current_refused_memory_prevents_model_read_hash_launch_and_output_creation(self):
        original_digest = upstream.digest
        reads = []
        def checked_digest(path):
            reads.append(Path(path))
            if Path(path) == self.model:
                self.fail("weight hash occurred before admission")
            return original_digest(path)
        with patch.object(upstream, "ROOT", self.root), \
                patch.object(upstream, "validated_runtime", return_value=self.runtime), \
                patch.object(upstream, "memory_snapshot", return_value={"MemAvailable_mib": 29535.875}), \
                patch.object(upstream, "digest", side_effect=checked_digest), \
                patch.object(upstream.subprocess, "Popen", side_effect=AssertionError("resource refusal launched")), \
                self.assertRaisesRegex(ValueError, "insufficient_available_memory"):
            upstream.pilot(self.args)
        self.assertNotIn(self.model, reads)
        self.assertFalse(self.args.output.exists())

    def test_full_phase_cannot_start_without_genuine_calibration_receipt(self):
        self.args.phase, self.args.max_seconds = "anchor", 444
        self.args.dataset = self.root / "datasets/context-choice-v1/cases.jsonl"
        with patch.object(upstream, "ROOT", self.root), \
                patch.object(upstream, "validated_runtime", return_value=self.runtime), \
                patch.object(upstream, "memory_snapshot", side_effect=AssertionError("missing calibration reached admission")), \
                patch.object(upstream.subprocess, "Popen", side_effect=AssertionError("missing calibration launched")), \
                self.assertRaisesRegex(ValueError, "receipt_missing"):
            upstream.pilot(self.args)

    def test_selected27b_offline_mock_reaches_launch_only_after_all_preflight_gates(self):
        original_stat, original_digest = Path.stat, upstream.digest
        def synthetic_stat(path, *args, **kwargs):
            observed = original_stat(path, *args, **kwargs)
            if path == self.model:
                fields = list(observed)
                fields[6] = upstream.D327_ASSETS["files"][0]["size"]
                return os.stat_result(fields)
            return observed
        def synthetic_digest(path):
            return upstream.D327_ASSETS["files"][0]["sha256"] if Path(path) == self.model else original_digest(path)
        def empty_test_source_archive(path, payload):
            with tarfile.open(path, "w"):
                pass
        with patch.object(upstream, "ROOT", self.root), patch.object(Path, "stat", synthetic_stat), \
                patch.object(upstream, "validated_runtime", return_value=self.runtime), \
                patch.object(upstream, "memory_snapshot", return_value={"MemAvailable_mib": 50000}), \
                patch.object(upstream, "digest", side_effect=synthetic_digest), \
                patch.object(upstream.shared, "archive_bench_source", side_effect=empty_test_source_archive), \
                patch.object(upstream.socket, "socket"), \
                patch.object(upstream.subprocess, "Popen", side_effect=RuntimeError("synthetic_launch_stopped")) as launch, \
                self.assertRaisesRegex(RuntimeError, "synthetic_launch_stopped"):
            upstream.pilot(self.args)
        launch.assert_called_once()
        command = launch.call_args.args[0]
        self.assertEqual(command[command.index("--alias") + 1], upstream.D327_ALIAS)
        self.assertEqual(command[command.index("--ctx-size") + 1], "4096")
        self.assertEqual(command[command.index("--n-gpu-layers") + 1], "99")
        recorded = json.loads((self.args.output / "pilot.json").read_text())
        self.assertFalse(recorded["completed"])
        self.assertEqual(recorded["execution_envelope"]["name"], upstream.D327_ENVELOPE)

    def test_calibration_derivation_is_numeric_fixed_bounded_and_uses_all_twelve_calls(self):
        expected = {"rule": upstream.D327_BUDGET_RULE, "max_canary_adapter_ms": 1000,
                    "phase_max_seconds": {"anchor": 444, "capability": 564}}
        self.assertEqual(upstream.derive_phase_budgets([1000] * 12), expected)
        self.assertEqual(upstream.derive_phase_budgets([1000] * 11 + [1000.5])["phase_max_seconds"],
                         {"anchor": 445, "capability": 565})
        for durations in ([], [1000] * 11, [0] * 12, [True] * 12, [float("inf")] * 12, [30000] * 12):
            with self.subTest(durations=durations[:1]), self.assertRaises(ValueError):
                upstream.derive_phase_budgets(durations)

    def synthetic_canary(self):
        """Construct retained test bytes, without a model, HTTP call or service."""
        root = self.root / "synthetic-canary"
        campaign = root / "campaign"
        campaign.mkdir(parents=True)
        prep_path = root / "native-preparation.json"
        prep_path.write_bytes(campaigns._encode(self.prepared))
        session = {"endpoint": "http://127.0.0.1:11438/v1/systemone",
            "model": {"repo_id": upstream.D327_ASSETS["repo_id"], "revision": upstream.D327_ASSETS["revision"],
            "sha256": upstream.D327_ASSETS["files"][0]["sha256"], "alias": upstream.D327_ALIAS,
            "path": str(self.model)},
            "runtime": {"revision": upstream.PIN, "sha256": self.runtime["binary_sha256"]},
            "gateway": {"kind": "upstream_native_http_listener_no_application_gateway", "sha256": "4" * 64},
            "runtime_pin": {"sha256": "5" * 64},
            "harness": {"sha256": upstream.digest(upstream.__file__)},
            "settings": {"context": 4096, "parallel": 1, "concurrency": 1, "questions_per_call": 1,
                         "truncation": "reject_in_pinned_native_engine"},
            "max_rss_mb": 24576, "native_preparation": {"sha256": upstream.digest(prep_path)}}
        (root / "session.json").write_bytes(campaigns._encode(session))
        profile = {"schema_version": "deposium.candidate/v1", "profile_id": "synthetic-canary-only",
            "adapter": "systemone_local", "qualification": "model_isolated", "capabilities": ["bench.context-choice"],
            "revision": upstream.D327_ASSETS["revision"], "recordings": None, "timeout_seconds": 30,
            "model": {"endpoint": "http://127.0.0.1:11438/v1/systemone", "model_id": upstream.D327_ALIAS,
                "repo_id": upstream.D327_ASSETS["repo_id"], "session_manifest": str(root / "session.json"),
                "session_sha256": upstream.digest(root / "session.json"), "max_length": 4096,
                "max_rss_mb": 24576, "credential_env": upstream.AUTH_ENV}}
        (campaign / "profile.json").write_bytes(campaigns._encode(profile))
        cases = lines(self.canary)
        (campaign / "cases.jsonl").write_bytes(cases)
        session = json.loads((root / "session.json").read_bytes())
        identity = {key: session[key] for key in ("model", "runtime", "gateway", "harness", "runtime_pin", "settings", "max_rss_mb")}
        identity["adapter_sha256"] = upstream.digest(upstream.systemone_local.__file__)
        identity["choice_protocol_sha256"] = upstream.digest(Path(upstream.systemone_local.__file__).with_name("choice_protocol.py"))
        identity["native_preparation"] = session["native_preparation"]
        manifest = {"schema_version": "deposium.campaign/v1", "run_id": "synthetic-no-inference",
            "dataset_sha256": sha(cases), "case_ids": [c["case_id"] for c in self.canary], "case_count": 12,
            "profile_sha256": upstream.digest(campaign / "profile.json"), "qualification": "model_isolated",
            "input_protocol": "context_choice", "stack_context": {"components": [], "preflight_sha256": None},
            "adapter_provenance": {"adapter": "systemone_local", "qualification": "model_isolated", "available": True,
                "capabilities": ["bench.context-choice"], "session_sha256": upstream.digest(root / "session.json"),
                "identity": identity, "identity_sha256": sha(upstream.systemone_local._wire(identity))}}
        (campaign / "manifest.json").write_bytes(campaigns._encode(manifest))
        records = []
        for case in self.canary:
            body, mapping, wire = upstream.native_request(case["input"], upstream.D327_ALIAS)
            correct = case["reference"]["assertions"][0]["value"]
            wrong = next(o["id"] for o in case["input"]["options"] if o["id"] != correct)
            native_choice = next(key for key, value in mapping.items() if value == wrong)
            native = {"model": upstream.D327_ALIAS, "answers": {"answer": {"type": "choice", "choice": native_choice,
                "probabilities": {key: .7 if key == native_choice else .1 for key in mapping}, "confidence": .7}},
                "usage": {"input_tokens": 2, "output_tokens": 0}}
            records.append({"schema_version": "deposium.result/v1", "case_id": case["case_id"],
                "contract_id": case["contract_id"], "request_sha256": sha(campaigns._encode(candidate_request(case))),
                "status": "ok", "output": {"choice_id": wrong}, "error": None, "duration_ms": 1000,
                "raw_output": {"http_attempted": True, "http_status": 200, "native_request": body,
                    "option_mapping": mapping, "request_body_sha256": sha(wire), "native_preparation_count_match": True,
                    "prepared_input_tokens": 2, "usage": {"input_tokens": 2, "output_tokens": 0},
                    "observed_model": upstream.D327_ALIAS, "requested_model": upstream.D327_ALIAS,
                    "cached_failure": False, "native_usage_truncated": None, "native_result": native}})
        (campaign / "raw.jsonl").write_bytes(lines(records))
        (campaign / "report.md").write_text("Synthetic retained bytes; no inference.\n")
        (root / "pilot.json").write_bytes(campaigns._encode({"completed": True, "model_assets": upstream.D327_ASSETS,
            "runtime": self.runtime, "resources": {"stop_reason": None, "rss_peak_mib": 20000, "min_available_mib": 10000},
            "memory_before": {"MemAvailable_mib": 50000},
            "execution_envelope": {"name": upstream.D327_ENVELOPE, "phase": "canary", "max_seconds": 600},
            "actual_backend": {"kind": "metal", "decision_type": "vllm-d3", "offloaded_layers": 1, "total_layers": 1}}))
        (root / "preparation-receipt.json").write_bytes(self.prep_payload)
        self.reseal(root)
        receipt = {"schema_version": "deposium.d3-27b-calibration/v1", "execution_envelope": upstream.D327_ENVELOPE,
            "model_id": upstream.D327_ALIAS, "model_sha256": upstream.D327_ASSETS["files"][0]["sha256"],
            "preparation_receipt_sha256": sha(self.prep_payload), "canary_archive": str(root),
            "canary_seal_sha256": upstream.digest(root / "pilot-seal.json"),
            "derivation": upstream.derive_phase_budgets([1000] * 12)}
        path = self.root / "synthetic-calibration-receipt.json"
        path.write_bytes(campaigns._encode(receipt))
        return root, path, receipt

    def reseal(self, root, *, update_summary=True):
        campaign = root / "campaign"
        if update_summary:
            cases, _ = parse_cases((campaign / "cases.jsonl").read_bytes())
            records = [json.loads(line) for line in (campaign / "raw.jsonl").read_bytes().splitlines()]
            summary = {"schema_version": "deposium.campaign-summary/v1", "run_id": "synthetic-no-inference",
                "qualification": "model_isolated", "completion_status": "complete" if len(records) == len(cases) else "incomplete",
                "raw_sha256": upstream.digest(campaign / "raw.jsonl"), "metrics": upstream.summarize(cases, records)}
            (campaign / "summary.json").write_bytes(campaigns._encode(summary))
        files = {p.name: upstream.digest(p) for p in campaign.iterdir() if p.is_file() and p.name != "seal.json"}
        (campaign / "seal.json").write_bytes(campaigns._encode({"schema_version": "deposium.archive-seal/v1",
            "files": files, "sha256": sha(campaigns._encode(files))}))
        files = {str(p.relative_to(root)): upstream.digest(p) for p in root.rglob("*") if p.is_file() and p.name != "pilot-seal.json"}
        (root / "pilot-seal.json").write_bytes(campaigns._encode({"schema_version": "deposium.native-pilot-seal/v1", "files": files}))

    def test_sealed_synthetic_calibration_bytes_validate_purely_without_accuracy_gate(self):
        root, path, _ = self.synthetic_canary()
        self.assertEqual(json.loads((root / "campaign/summary.json").read_bytes())["metrics"]["passed_cases"], 0)
        with patch.object(upstream.subprocess, "Popen", side_effect=AssertionError("calibration launched")), \
                patch.object(upstream, "LocalSystemOneAdapter", side_effect=AssertionError("calibration loaded model")), \
                patch.object(upstream, "memory_snapshot", side_effect=AssertionError("calibration observed live runtime")):
            for phase, seconds in (("anchor", 444), ("capability", 564)):
                _, receipt = upstream.d327_calibration_receipt(path, phase, seconds, self.prep_payload,
                                                              self.prepared, self.canary, self.runtime)
                self.assertEqual(receipt["derivation"]["phase_max_seconds"][phase], seconds)

    def test_calibration_refuses_missing_actual_calls_wrong_bindings_and_rewritten_budget(self):
        root, path, receipt = self.synthetic_canary()
        raw = (root / "campaign/raw.jsonl").read_bytes()
        for mutate in (lambda r: r.pop(), lambda r: r[0]["raw_output"].update(http_attempted=False),
                       lambda r: r[0]["raw_output"].update(native_preparation_count_match=False),
                       lambda r: r[0]["raw_output"].update(observed_model="d3-flash-q8"),
                       lambda r: r[0].update(status="error"), lambda r: r[0].update(duration_ms=30000)):
            records = [json.loads(line) for line in raw.splitlines()]
            mutate(records)
            (root / "campaign/raw.jsonl").write_bytes(lines(records))
            self.reseal(root)
            receipt["canary_seal_sha256"] = upstream.digest(root / "pilot-seal.json")
            path.write_bytes(campaigns._encode(receipt))
            with self.assertRaises(ValueError):
                upstream.d327_calibration_receipt(path, "anchor", 444, self.prep_payload, self.prepared, self.canary, self.runtime)
        (root / "campaign/raw.jsonl").write_bytes(raw)
        self.reseal(root)
        receipt["canary_seal_sha256"] = upstream.digest(root / "pilot-seal.json")
        receipt["derivation"]["phase_max_seconds"]["anchor"] = 1200
        path.write_bytes(campaigns._encode(receipt))
        with self.assertRaisesRegex(ValueError, "budget_mismatch"):
            upstream.d327_calibration_receipt(path, "anchor", 1200, self.prep_payload, self.prepared, self.canary, self.runtime)

    def test_calibration_refuses_modified_or_unsealed_bytes(self):
        root, path, _ = self.synthetic_canary()
        (root / "campaign/raw.jsonl").write_text("tampered\n")
        with self.assertRaisesRegex(ValueError, "sealed_file_changed"):
            upstream.d327_calibration_receipt(path, "anchor", 444, self.prep_payload, self.prepared, self.canary, self.runtime)

    def test_calibration_requires_native_answer_probability_model_usage_and_choice_binding(self):
        root, path, receipt = self.synthetic_canary()
        original = (root / "campaign/raw.jsonl").read_bytes()
        mutations = (
            lambda raw: raw.pop("native_result"),
            lambda raw: raw["native_result"].update(model="d3-flash-q8"),
            lambda raw: raw["native_result"]["answers"]["answer"].update(choice="unknown"),
            lambda raw: raw["native_result"]["answers"]["answer"].update(probabilities={"c0": .25, "c1": .25, "c2": .25, "c3": .1}),
            lambda raw: raw["native_result"]["answers"]["answer"].update(confidence=1.5),
            lambda raw: raw["native_result"]["usage"].update(input_tokens=3),
            lambda raw: raw["native_result"]["usage"].update(truncated=True),
            lambda raw: raw.update(cached_failure=True),
            lambda raw: raw.update(requested_model="d3-flash-q8"),
        )
        for mutate in mutations:
            records = [json.loads(line) for line in original.splitlines()]
            mutate(records[0]["raw_output"])
            (root / "campaign/raw.jsonl").write_bytes(lines(records))
            self.reseal(root)
            receipt["canary_seal_sha256"] = upstream.digest(root / "pilot-seal.json")
            path.write_bytes(campaigns._encode(receipt))
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                upstream.d327_calibration_receipt(path, "anchor", 444, self.prep_payload, self.prepared, self.canary, self.runtime)
        records = [json.loads(line) for line in original.splitlines()]
        mapping = records[0]["raw_output"]["option_mapping"]
        other = next(value for value in mapping.values() if value != records[0]["output"]["choice_id"])
        records[0]["output"] = {"choice_id": other}
        (root / "campaign/raw.jsonl").write_bytes(lines(records))
        self.reseal(root)
        receipt["canary_seal_sha256"] = upstream.digest(root / "pilot-seal.json")
        path.write_bytes(campaigns._encode(receipt))
        with self.assertRaisesRegex(ValueError, "native_response_binding"):
            upstream.d327_calibration_receipt(path, "anchor", 444, self.prep_payload, self.prepared, self.canary, self.runtime)

    def test_calibration_requires_exact_profile_provenance_and_complete_summary(self):
        root, path, receipt = self.synthetic_canary()
        original_profile = (root / "campaign/profile.json").read_bytes()
        for changes in ({"repo_id": "fixture/other"}, {"max_length": 8192}, {"timeout_seconds": 29}):
            profile = json.loads(original_profile)
            if "timeout_seconds" in changes:
                profile.update(changes)
            else:
                profile["model"].update(changes)
            (root / "campaign/profile.json").write_bytes(campaigns._encode(profile))
            manifest = json.loads((root / "campaign/manifest.json").read_bytes())
            manifest["profile_sha256"] = upstream.digest(root / "campaign/profile.json")
            (root / "campaign/manifest.json").write_bytes(campaigns._encode(manifest))
            self.reseal(root)
            receipt["canary_seal_sha256"] = upstream.digest(root / "pilot-seal.json")
            path.write_bytes(campaigns._encode(receipt))
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "canary_binding"):
                upstream.d327_calibration_receipt(path, "anchor", 444, self.prep_payload, self.prepared, self.canary, self.runtime)
        (root / "campaign/profile.json").write_bytes(original_profile)
        manifest["profile_sha256"] = upstream.digest(root / "campaign/profile.json")
        (root / "campaign/manifest.json").write_bytes(campaigns._encode(manifest))
        self.reseal(root)
        summary = json.loads((root / "campaign/summary.json").read_bytes())
        summary["completion_status"] = "incomplete"
        (root / "campaign/summary.json").write_bytes(campaigns._encode(summary))
        self.reseal(root, update_summary=False)
        receipt["canary_seal_sha256"] = upstream.digest(root / "pilot-seal.json")
        path.write_bytes(campaigns._encode(receipt))
        with self.assertRaisesRegex(ValueError, "summary_incomplete"):
            upstream.d327_calibration_receipt(path, "anchor", 444, self.prep_payload, self.prepared, self.canary, self.runtime)

    def test_readiness_plan_remains_deferred_with_no_claimed_full_phase_budgets_or_scores(self):
        plan = json.loads((ROOT / "plans/d3-27b-capability-v1.json").read_text())
        self.assertEqual(plan["status"], "deferred_by_maintainer")
        self.assertEqual(plan["execution_status"], "not_run")
        self.assertEqual(plan["cases_scored"], 0)
        self.assertIsNone(plan["phase_budgets"]["anchor_max_seconds"])
        self.assertIsNone(plan["phase_budgets"]["capability_max_seconds"])
        self.assertEqual(plan["technical_canary"]["case_ids"], list(upstream.D327_CANARY_IDS))
        self.assertEqual(plan["inference_envelope"]["admission_available_mib"], 32768)


if __name__ == "__main__":
    unittest.main()
