"""Offline model-campaign integrity checks; no weights, Torch or subprocess model."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from deposium_bench import campaigns
from deposium_bench.adapters import create_adapter, parse_profile
from deposium_bench.cases import DEFAULT_DATASET, candidate_request, load_cases

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datasets/document-task-v1/cases.jsonl"
PROFILE = ROOT / "profiles/julia-1-cpu-task.json"


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


class ModelCampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.adapter = Mock()
        self.adapter.capabilities = ["mcps.document-plan"]
        self.adapter.provenance = {"identity_sha256": "a" * 64,
                                   "qualification": "model_isolated", "adapter": "julia",
                                   "available": True, "model_revision": "a85b127321d580d65176c89ced8273f305745d85"}
        self.adapter.predict.return_value = {"status": "ok", "output": {"task": "catalog"},
                                             "raw_output": {"inference_ms": 1.5}, "error": None}

    def run_model(self, name="run", **kwargs):
        with patch.object(campaigns, "create_adapter", return_value=self.adapter):
            return campaigns.run_campaign(DATASET, PROFILE, self.root / name, **kwargs)

    def test_projection_preserves_all_inputs_and_identity_and_records_hashes(self):
        parent_cases, parent_hash = load_cases(DEFAULT_DATASET)
        cases, digest = load_cases(DATASET)
        projection = json.loads(DATASET.with_name("manifest.json").read_bytes())
        self.assertEqual(projection["parent_sha256"], parent_hash)
        self.assertEqual(projection["sha256"], digest)
        self.assertEqual(projection["case_count"], 14)
        selected = [case for case in parent_cases if case["contract_id"] == "mcps.document-plan"]
        self.assertEqual(len(cases), 14)
        self.assertEqual([case["case_id"] for case in cases], [case["case_id"] for case in selected])
        self.assertEqual({case["case_id"] for case in cases},
                         set(projection["core_case_ids"] + projection["context_extension_case_ids"]))
        for parent, projected in zip(selected, cases):
            self.assertEqual({k: v for k, v in parent.items() if k != "reference"},
                             {k: v for k, v in projected.items() if k != "reference"})
            assertions = [assertion for assertion in parent["reference"]["assertions"]
                          if assertion["path"] == "/task"]
            self.assertEqual(projected["reference"]["assertions"], assertions)
            self.assertEqual(len(assertions), 1)
        summary = self.run_model()
        manifest = json.loads((self.root / "run/manifest.json").read_bytes())
        self.assertEqual(manifest["dataset_sha256"], digest)
        self.assertEqual(manifest["case_ids"], [case["case_id"] for case in cases])
        self.assertEqual(manifest["qualification"], "model_isolated")
        self.assertEqual(manifest["input_protocol"], "current_equivalent")
        self.assertEqual(summary["metrics"]["total_cases"], 14)
        self.assertEqual([call.args[0] for call in self.adapter.predict.call_args_list],
                         [candidate_request(case) for case in cases])
        self.adapter.close.assert_called_once_with()

    def test_original_full_plan_dataset_refused_before_adapter_creation(self):
        with patch.object(campaigns, "create_adapter", side_effect=AssertionError("no model initialization")) as factory:
            with self.assertRaisesRegex(campaigns.CampaignError, "task-only"):
                campaigns.run_campaign(DEFAULT_DATASET, PROFILE, self.root / "full")
        factory.assert_not_called()
        self.assertFalse((self.root / "full").exists())

    def test_gliner_context_campaign_preserves_input_and_deterministic_stack_scope(self):
        from tests.test_schemas import gliner_profile
        profile = gliner_profile()
        path = self.root / "gliner.json"
        path.write_text(json.dumps(profile))
        dataset = ROOT / "datasets/context-choice-v1/cases.jsonl"
        cases, digest = load_cases(dataset)
        self.adapter.capabilities = ["bench.context-choice"]
        self.adapter.provenance.update(adapter="gliner", model_revision=profile["revision"])
        self.adapter.predict.return_value = {"status": "ok", "output": {"choice_id": "a"},
                                            "raw_output": {}, "error": None}
        with patch.object(campaigns, "create_adapter", return_value=self.adapter) as factory:
            summary = campaigns.run_campaign(dataset, path, self.root / "gliner-run", max_new_cases=2)
        self.assertEqual(factory.call_args.args[0], profile)
        prepared = json.loads((self.root / "gliner-run/profile.json").read_text())
        for key in ("local_dir", "assets_manifest", "prompt_path", "runtime_lock"):
            self.assertEqual(prepared["model"][key], str(self.root / profile["model"][key]))
        self.assertEqual(prepared["model"]["runtime_python"], "/missing/python")
        self.assertEqual([call.args[0] for call in self.adapter.predict.call_args_list],
                         [candidate_request(case) for case in cases[:2]])
        manifest = json.loads((self.root / "gliner-run/manifest.json").read_text())
        self.assertEqual(manifest["dataset_sha256"], digest)
        self.assertEqual(manifest["input_protocol"], "context_choice")
        self.assertEqual(manifest["proof_level"], "A")
        self.assertEqual(summary["metrics"]["total_cases"], 132)
        self.assertEqual(summary["metrics"]["scored_cases"], 2)
        self.assertTrue(all(not component["selected"] and component["omission_reason"] == "model_isolated_only"
                            for component in manifest["stack_context"]["components"]))
        self.adapter.close.assert_called_once_with()

    def test_gliner_factory_is_lazy_and_scope_refused_before_runtime(self):
        from tests.test_schemas import gliner_profile
        from deposium_bench.gliner_adapter import GLiNERProfileError
        profile = gliner_profile()
        path = self.root / "gliner.json"
        path.write_text(json.dumps(profile))
        with patch("deposium_bench.gliner_adapter.GLiNERAdapter", return_value=self.adapter) as factory:
            self.assertIs(create_adapter(profile, path), self.adapter)
            factory.assert_called_once_with(profile, path.resolve())
        with patch.object(campaigns, "create_adapter", side_effect=AssertionError("no runtime")):
            with self.assertRaisesRegex(campaigns.CampaignError, "declared capability"):
                campaigns.run_campaign(DATASET, path, self.root / "bad-scope")
        self.assertFalse((self.root / "bad-scope").exists())
        for change in ({"head_length": 512}, {"max_length": 4097}, {"threads": True}):
            invalid = json.loads(json.dumps(profile))
            invalid["model"].update(change)
            with self.subTest(change=change), self.assertRaises(GLiNERProfileError):
                parse_profile(json.dumps(invalid).encode())

    def test_indecis_campaign_uses_common_cases_and_isolates_stack(self):
        from deposium_bench.indecis_adapter import PATH_FIELDS
        profile_path = ROOT / "profiles/indecis-open-cpu-context.json"
        profile = json.loads(profile_path.read_bytes())
        dataset = ROOT / "datasets/context-choice-v1/cases.jsonl"
        cases, digest = load_cases(dataset)
        self.adapter.capabilities = ["bench.context-choice"]
        self.adapter.provenance.update(adapter="indecis", model_revision=profile["revision"])
        self.adapter.predict.return_value = {"status": "ok", "output": {"choice_id": "a"},
                                            "raw_output": {}, "error": None}
        with patch.object(campaigns, "create_adapter", return_value=self.adapter):
            summary = campaigns.run_campaign(dataset, profile_path, self.root / "indecis", max_new_cases=2)
        prepared = json.loads((self.root / "indecis/profile.json").read_bytes())
        for key in PATH_FIELDS:
            self.assertEqual(prepared["model"][key], str((profile_path.parent / profile["model"][key]).absolute().resolve()))
        self.assertEqual([call.args[0] for call in self.adapter.predict.call_args_list],
                         [candidate_request(case) for case in cases[:2]])
        manifest = json.loads((self.root / "indecis/manifest.json").read_bytes())
        self.assertEqual(manifest["dataset_sha256"], digest)
        self.assertEqual(manifest["input_protocol"], "context_choice")
        self.assertEqual(manifest["proof_level"], "A")
        self.assertEqual(summary["metrics"]["total_cases"], 132)
        self.assertEqual(summary["metrics"]["scored_cases"], 2)
        self.assertTrue(all(not item["selected"] and item["omission_reason"] == "model_isolated_only"
                            for item in manifest["stack_context"]["components"]))
        self.adapter.close.assert_called_once_with()

    def test_indecis_factory_is_lazy_and_rejects_other_contracts(self):
        profile_path = ROOT / "profiles/indecis-open-cpu-context.json"
        profile = json.loads(profile_path.read_bytes())
        with patch("deposium_bench.indecis_adapter.IndecisAdapter", return_value=self.adapter) as factory:
            self.assertIs(create_adapter(profile, profile_path), self.adapter)
            factory.assert_called_once_with(profile, profile_path.resolve())
        with patch.object(campaigns, "create_adapter", side_effect=AssertionError("no runtime")) as factory:
            with self.assertRaisesRegex(campaigns.CampaignError, "declared capability"):
                campaigns.run_campaign(DATASET, profile_path, self.root / "bad-indecis-scope")
        factory.assert_not_called()
        self.assertFalse((self.root / "bad-indecis-scope").exists())

    def test_adapter_closes_when_scoring_or_archive_finish_raises(self):
        with patch.object(campaigns, "_finish", side_effect=RuntimeError("forced_archive_failure")):
            with self.assertRaisesRegex(RuntimeError, "forced_archive_failure"):
                self.run_model()
        self.adapter.close.assert_called_once_with()
        self.assertTrue((self.root / "run/raw.jsonl").exists())

    def test_adapter_predict_exception_is_recorded_and_closed(self):
        self.adapter.predict.side_effect = RuntimeError("secret_private_value")
        summary = self.run_model(max_new_cases=1)
        self.assertEqual(summary["metrics"]["counts_by_status"]["error"], 1)
        self.assertEqual(summary["metrics"]["counts_by_status"]["missing"], 13)
        self.assertNotIn(b"secret_private_value", (self.root / "run/raw.jsonl").read_bytes())
        self.adapter.close.assert_called_once_with()

    def test_interrupt_closes_model_and_keeps_original_prefix(self):
        self.adapter.predict.side_effect = KeyboardInterrupt
        summary = self.run_model()
        self.assertEqual(summary["completion_status"], "interrupted")
        self.assertEqual(summary["metrics"]["scored_cases"], 0)
        self.adapter.close.assert_called_once_with()

    def test_resume_mismatching_runtime_identity_closes_and_preserves_parent(self):
        self.run_model(max_new_cases=1)
        before = snapshot(self.root / "run")
        self.adapter.reset_mock()
        self.adapter.provenance = {**self.adapter.provenance, "identity_sha256": "b" * 64}
        with patch.object(campaigns, "create_adapter", return_value=self.adapter):
            with self.assertRaisesRegex(campaigns.CampaignError, "provenance changed"):
                campaigns.resume_campaign(self.root / "run", self.root / "resumed")
        self.adapter.close.assert_called_once_with()
        self.adapter.predict.assert_not_called()
        self.assertEqual(snapshot(self.root / "run"), before)
        self.assertFalse((self.root / "resumed").exists())

    def test_resume_calls_only_missing_cases_and_closes_new_adapter(self):
        self.run_model(max_new_cases=2)
        before = snapshot(self.root / "run")
        previous_ids = {json.loads(line)["case_id"] for line in before["raw.jsonl"].splitlines()}
        self.adapter.reset_mock()
        with patch.object(campaigns, "create_adapter", return_value=self.adapter):
            summary = campaigns.resume_campaign(self.root / "run", self.root / "resumed")
        self.assertEqual(summary["completion_status"], "complete")
        self.assertEqual(self.adapter.predict.call_count, 12)
        self.assertTrue(previous_ids.isdisjoint(call.args[0]["case_id"]
                                               for call in self.adapter.predict.call_args_list))
        self.adapter.close.assert_called_once_with()
        self.assertEqual(snapshot(self.root / "run"), before)

    def test_rescore_model_archive_needs_no_runtime_weights_or_adapter(self):
        first = self.run_model()
        before = snapshot(self.root / "run")
        # The archived profile points to real local weight/runtime paths, but
        # neither presence nor loading is consulted by rescore.
        with patch.object(campaigns, "create_adapter", side_effect=AssertionError("weights forbidden")), \
                patch.object(campaigns, "build_preflight", side_effect=AssertionError("stack forbidden")):
            second = campaigns.rescore_campaign(self.root / "run", self.root / "rescore")
        self.assertEqual(second["metrics"], first["metrics"])
        self.assertEqual((self.root / "rescore/raw.jsonl").read_bytes(), before["raw.jsonl"])
        self.assertEqual((self.root / "rescore/cases.jsonl").read_bytes(), before["cases.jsonl"])
        self.assertEqual(snapshot(self.root / "run"), before)


if __name__ == "__main__":
    unittest.main()
