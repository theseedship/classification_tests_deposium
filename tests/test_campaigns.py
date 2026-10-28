"""Archive integrity and lifecycle checks with independent recorded controls."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import campaigns
from deposium_bench.adapters import create_adapter
from deposium_bench.cases import DEFAULT_DATASET

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles/fixture-control.json"


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def run_control(self, name="run", **kwargs):
        return campaigns.run_campaign(DEFAULT_DATASET, PROFILE, self.root / name, **kwargs)

    def unseal(self, name="run"):
        # Model a process killed after durable raw writes, before summary/seal.
        for file in ("seal.json", "summary.json", "report.md"):
            (self.root / name / file).unlink()

    def test_control_has_real_failures_and_every_status(self):
        summary = self.run_control()
        metrics = summary["metrics"]
        self.assertEqual(summary["completion_status"], "complete")
        self.assertEqual(metrics["total_cases"], 36)
        self.assertEqual(metrics["verdict"], "fail")
        self.assertGreater(metrics["failed_cases"], 0)
        self.assertGreater(metrics["passed_cases"], 0)
        self.assertLess(metrics["scored_cases"], 36)
        self.assertTrue(all(count > 0 for count in metrics["counts_by_status"].values()))
        self.assertIn("empty_output", {row["reason"] for row in metrics["rows"]})
        self.assertEqual(len(summary["stack_coverage"]), 15)
        self.assertFalse(any(c["selected"] for c in summary["stack_coverage"]))
        manifest = json.loads((self.root / "run/manifest.json").read_bytes())
        self.assertEqual(manifest["proof_level"], "harness_control")
        self.assertEqual(manifest["stack_context"]["inventory_status"], "not_observed")
        self.assertEqual(manifest["adapter_provenance"]["recordings_sha256"],
                         campaigns._hash((self.root / "run/recordings.jsonl").read_bytes()))

    def test_resume_calls_only_unrecorded_cases_and_preserves_parent(self):
        initial = self.run_control(max_new_cases=4)
        original = snapshot(self.root / "run")
        calls = []

        def factory(*args, **kwargs):
            adapter = create_adapter(*args, **kwargs)
            predict = adapter.predict
            def spy(request):
                self.assertEqual(set(request), {"case_id", "contract_id", "input"})
                self.assertNotIn("reference", request["input"])
                calls.append(request["case_id"])
                return predict(request)
            adapter.predict = spy
            return adapter

        with patch.object(campaigns, "create_adapter", side_effect=factory):
            resumed = campaigns.resume_campaign(self.root / "run", self.root / "resumed")
        self.assertEqual(initial["completion_status"], "incomplete")
        self.assertEqual(resumed["completion_status"], "complete")
        self.assertEqual(len(calls), 32)
        prior = [json.loads(line)["case_id"] for line in original["raw.jsonl"].splitlines()]
        self.assertTrue(set(prior).isdisjoint(calls))
        self.assertEqual(snapshot(self.root / "run"), original)
        self.assertEqual(resumed["metrics"], self.run_control("fresh")["metrics"])

    def test_rescore_has_no_adapter_or_stack_dependency_and_preserves_trace(self):
        first = self.run_control()
        original = snapshot(self.root / "run")
        with patch.object(campaigns, "create_adapter", side_effect=AssertionError("inference forbidden")), \
                patch.object(campaigns, "build_preflight", side_effect=AssertionError("live stack forbidden")):
            rescored = campaigns.rescore_campaign(self.root / "run", self.root / "rescore")
        self.assertEqual(rescored["metrics"], first["metrics"])
        self.assertEqual((self.root / "rescore/raw.jsonl").read_bytes(), original["raw.jsonl"])
        self.assertEqual(snapshot(self.root / "run"), original)

    def test_rescore_uses_validated_bytes_despite_concurrent_parent_change(self):
        first = self.run_control(max_new_cases=1)
        original = snapshot(self.root / "run")
        read_archive = campaigns._archive

        def edit_after_validation(path):
            loaded = read_archive(path)
            # Simulate another process replacing inputs after integrity checks.
            record = json.loads(original["raw.jsonl"])
            record["output"] = {}
            (Path(path) / "raw.jsonl").write_bytes(campaigns._encode(record))
            (Path(path) / "cases.jsonl").write_bytes(b"unvalidated concurrent replacement\n")
            return loaded

        with patch.object(campaigns, "_archive", side_effect=edit_after_validation):
            try:
                derived = campaigns.rescore_campaign(self.root / "run", self.root / "derived")
            except campaigns.CampaignError:
                # Refusing a changed parent is also safe; mixed evidence is not.
                return
        self.assertEqual(derived["metrics"], first["metrics"])
        self.assertEqual((self.root / "derived/raw.jsonl").read_bytes(), original["raw.jsonl"])
        self.assertEqual((self.root / "derived/cases.jsonl").read_bytes(), original["cases.jsonl"])
        verified = campaigns.rescore_campaign(self.root / "derived", self.root / "verified")
        self.assertEqual(verified["metrics"], derived["metrics"])

    def test_zero_calls_is_invalid_and_recoverable(self):
        summary = self.run_control(max_new_cases=0)
        self.assertEqual(summary["metrics"]["verdict"], "invalid")
        self.assertEqual(summary["metrics"]["scored_cases"], 0)
        self.assertEqual(summary["metrics"]["counts_by_status"]["missing"], 36)
        self.assertEqual(campaigns.resume_campaign(self.root / "run", self.root / "resume")["completion_status"], "complete")

    def test_interrupt_keeps_durable_results_then_resumes(self):
        def factory(*args, **kwargs):
            adapter = create_adapter(*args, **kwargs)
            predict = adapter.predict
            count = 0
            def interrupt(request):
                nonlocal count
                count += 1
                if count == 3:
                    raise KeyboardInterrupt
                return predict(request)
            adapter.predict = interrupt
            return adapter
        with patch.object(campaigns, "create_adapter", side_effect=factory):
            summary = self.run_control()
        self.assertEqual(summary["completion_status"], "interrupted")
        self.assertEqual(len((self.root / "run/raw.jsonl").read_bytes().splitlines()), 2)
        self.assertEqual(campaigns.resume_campaign(self.root / "run", self.root / "resume")["completion_status"], "complete")

    def test_inflight_exception_is_redacted_and_recorded_once(self):
        def factory(*args, **kwargs):
            adapter = create_adapter(*args, **kwargs)
            adapter.predict = lambda request: (_ for _ in ()).throw(RuntimeError("secret-test-value"))
            return adapter
        with patch.object(campaigns, "create_adapter", side_effect=factory):
            summary = self.run_control(max_new_cases=1)
        self.assertEqual(summary["metrics"]["counts_by_status"]["error"], 1)
        self.assertNotIn(b"secret-test-value", (self.root / "run/raw.jsonl").read_bytes())

    def test_prepared_fixture_bytes_are_the_executed_bytes(self):
        profile = json.loads(PROFILE.read_bytes())
        source = self.root / "source.jsonl"
        data = (ROOT / "fixtures/control-responses.jsonl").read_bytes()
        source.write_bytes(data)
        profile["recordings"] = "source.jsonl"
        path = self.root / "profile.json"
        path.write_text(json.dumps(profile))
        def factory(*args, **kwargs):
            source.write_bytes(b"corrupted after input snapshot")
            return create_adapter(*args, **kwargs)
        with patch.object(campaigns, "create_adapter", side_effect=factory):
            summary = campaigns.run_campaign(DEFAULT_DATASET, path, self.root / "run")
        self.assertEqual(summary["completion_status"], "complete")
        self.assertEqual((self.root / "run/recordings.jsonl").read_bytes(), data)
        campaigns.rescore_campaign(self.root / "run", self.root / "rescore")

    def test_runtime_identity_change_refuses_resume(self):
        self.run_control(max_new_cases=1)
        def factory(*args, **kwargs):
            adapter = create_adapter(*args, **kwargs)
            adapter.provenance["identity_sha256"] = "0" * 64
            return adapter
        with patch.object(campaigns, "create_adapter", side_effect=factory), self.assertRaises(campaigns.CampaignError):
            campaigns.resume_campaign(self.root / "run", self.root / "resume")
        self.assertFalse((self.root / "resume").exists())

    def test_unsealed_durable_prefix_can_resume(self):
        self.run_control(max_new_cases=2)
        self.unseal()
        original = snapshot(self.root / "run")
        summary = campaigns.resume_campaign(self.root / "run", self.root / "resume")
        self.assertEqual(summary["completion_status"], "complete")
        self.assertEqual(snapshot(self.root / "run"), original)

    def test_sealed_files_and_required_seal_cannot_be_changed(self):
        for name in ("raw.jsonl", "cases.jsonl", "profile.json", "recordings.jsonl", "summary.json", "seal.json"):
            with self.subTest(file=name):
                self.run_control(name)
                target = self.root / name / name
                if name == "seal.json":
                    target.unlink()
                else:
                    target.write_bytes(target.read_bytes() + b" ")
                before = snapshot(self.root / name)
                with self.assertRaises(campaigns.CampaignError):
                    campaigns.rescore_campaign(self.root / name, self.root / (name + "-rescore"))
                self.assertEqual(snapshot(self.root / name), before)

    def test_partial_corrupt_raw_trace_is_never_silently_repaired(self):
        self.run_control(max_new_cases=1)
        self.unseal()
        path = self.root / "run/raw.jsonl"
        valid = path.read_bytes()
        record = json.loads(valid)
        bad_records = [valid.rstrip(b"\n"), valid + valid, b"\n", b"not-json\n",
                       valid.replace(b'"duration_ms":', b'"duration_ms": 0, "duration_ms":'),
                       valid.replace(b'"raw_output":', b'"raw_output": NaN, "discarded":'),
                       valid.replace(b'"raw_output":', b'"raw_output": 1e309, "discarded":')]
        for key, value in (("case_id", "unknown"), ("case_id", []), ("status", []), ("status", "bad"),
                           ("request_sha256", "0" * 64), ("contract_id", "wrong"),
                           ("duration_ms", True), ("duration_ms", -1), ("error", {})):
            bad_records.append(campaigns._encode({**record, key: value}))
        for index, payload in enumerate(bad_records):
            with self.subTest(index=index):
                path.write_bytes(payload)
                with self.assertRaises(campaigns.CampaignError):
                    campaigns.rescore_campaign(self.root / "run", self.root / f"bad-{index}")
                self.assertEqual(path.read_bytes(), payload)

    def test_destinations_cannot_overwrite_original_or_application_stack(self):
        self.run_control()
        before = snapshot(self.root / "run")
        for destination in (self.root / "run", self.root / "run/child"):
            with self.assertRaises((campaigns.CampaignError, FileExistsError)):
                campaigns.rescore_campaign(self.root / "run", destination)
        with self.assertRaises(campaigns.CampaignError):
            campaigns._destination(self.root / "stack/output", self.root / "stack")
        self.assertEqual(snapshot(self.root / "run"), before)

    def test_cli_exit_status_separates_control_failure_and_invalid_run(self):
        for count, expected in ((36, 1), (0, 2)):
            process = subprocess.run([sys.executable, "-S", "-m", "deposium_bench", "run", "--profile", str(PROFILE),
                                      "--max-new-cases", str(count), "--output", str(self.root / f"cli-{count}"),
                                      "--format", "json"], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(process.returncode, expected, process.stderr)
            summary = json.loads(process.stdout)
            self.assertEqual(summary["metrics"]["total_cases"], 36)


if __name__ == "__main__":
    unittest.main()
