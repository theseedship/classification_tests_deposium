"""Repeated timing lifecycle and evidence checks without models or services."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from deposium_bench import adapters, campaigns
from deposium_bench.cases import DEFAULT_DATASET, load_cases
from deposium_bench.timing import benchmark_timing

ROOT = Path(__file__).resolve().parents[1]


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        cases, _ = load_cases(DEFAULT_DATASET)
        self.cases = cases[:2]
        self.dataset = self.root / "cases.jsonl"
        self.dataset.write_bytes(b"".join(campaigns._encode(case) for case in self.cases))
        self.profiles = []
        for name in ("first", "second"):
            profile = json.loads((ROOT / "profiles/fixture-control.json").read_bytes())
            profile.update(profile_id=name, recordings=str(ROOT / "fixtures/control-responses.jsonl"))
            path = self.root / f"{name}.json"
            path.write_bytes(campaigns._encode(profile))
            self.profiles.append(path)
        self.created = []
        self.received = []

    def factory(self, profile, path, **kwargs):
        # Use a genuine offline recorded-control adapter, with lifecycle spies.
        adapter = adapters.create_adapter(profile, path, **kwargs)
        predict = adapter.predict
        def observed(request):
            self.received.append((profile["profile_id"], request))
            return predict(request)
        adapter.predict = observed
        adapter.close = Mock()
        self.created.append(adapter)
        return adapter

    def run_timing(self, **kwargs):
        with patch.object(campaigns, "create_adapter", side_effect=self.factory), \
                patch.object(campaigns, "build_preflight", side_effect=AssertionError("no live stack")):
            return benchmark_timing(self.dataset, self.profiles, self.root / "timing",
                                    launches=kwargs.pop("launches", 2), warmup=kwargs.pop("warmup", 1),
                                    passes=kwargs.pop("passes", 2), **kwargs)

    def test_alternates_candidates_freezes_inputs_records_phases_and_closes(self):
        original = self.dataset.read_bytes(), [path.read_bytes() for path in self.profiles]
        summary = self.run_timing()
        self.assertEqual(summary["completion_status"], "complete")
        self.assertEqual(summary["recorded_calls"], 24)
        manifest = json.loads((self.root / "timing/timing-manifest.json").read_bytes())
        self.assertEqual(manifest["protocol"]["warmup"], 1)
        self.assertEqual(manifest["protocol"]["passes"], 2)
        self.assertEqual(manifest["protocol"]["launches"], 2)
        self.assertIn("first call", manifest["protocol"]["cold"])
        self.assertIn("cycle dataset", manifest["protocol"]["warmup_description"])
        self.assertEqual(manifest["protocol"]["total_planned_calls"], 24)
        self.assertEqual(len(self.created), 4)
        for adapter in self.created:
            adapter.close.assert_called_once_with()
        trials = [json.loads(line) for line in (self.root / "timing/trials.jsonl").read_bytes().splitlines()]
        blocks = [(trials[i]["launch"], trials[i]["candidate"]) for i in (0, 6, 12, 18)]
        self.assertEqual(blocks, [(0, "first"), (0, "second"), (1, "second"), (1, "first")])
        self.assertEqual([trial["phase"] for trial in trials[:6]], ["cold", "warmup"] + ["measured"] * 4)
        self.assertEqual(summary["independent_families"], 1)
        self.assertEqual(summary["candidates"]["first"]["phases"]["measured"]["recorded_calls"], 8)
        self.assertEqual(len(summary["candidates"]["first"]["per_pass_quality"]), 4)
        for _, request in self.received:
            self.assertEqual(set(request), {"case_id", "contract_id", "input"})
            self.assertNotIn("reference", request["input"])
        self.assertEqual(original, (self.dataset.read_bytes(), [path.read_bytes() for path in self.profiles]))
        seal = json.loads((self.root / "timing/seal.json").read_bytes())
        self.assertEqual(seal["sha256"], campaigns._hash(campaigns._encode(seal["files"])))
        for name, digest in seal["files"].items():
            self.assertEqual(campaigns._hash((self.root / "timing" / name).read_bytes()), digest)

    def test_errors_keep_denominators_and_have_no_invented_engine_times(self):
        actual = self.factory
        def failing(*args, **kwargs):
            adapter = actual(*args, **kwargs)
            adapter.predict = Mock(side_effect=RuntimeError("private_secret"))
            return adapter
        with patch.object(campaigns, "create_adapter", side_effect=failing):
            summary = benchmark_timing(self.dataset, self.profiles[:1], self.root / "timing",
                                       launches=1, warmup=0, passes=1)
        measured = summary["candidates"]["first"]["phases"]["measured"]
        self.assertEqual(measured["counts_by_status"]["error"], 2)
        self.assertEqual(measured["latency"]["adapter_duration_ms"]["count"], 2)
        self.assertEqual(measured["latency"]["decision_ms"]["count"], 0)
        self.assertNotIn(b"private_secret", (self.root / "timing/trials.jsonl").read_bytes())
        self.created[0].close.assert_called_once_with()

    def test_interrupt_preserves_durable_prefix_and_closes_adapter(self):
        actual = self.factory
        def interrupting(*args, **kwargs):
            adapter = actual(*args, **kwargs)
            predict = adapter.predict
            count = 0
            def predict_interrupt(request):
                nonlocal count
                count += 1
                if count == 3:
                    raise KeyboardInterrupt
                return predict(request)
            adapter.predict = predict_interrupt
            return adapter
        with patch.object(campaigns, "create_adapter", side_effect=interrupting):
            summary = benchmark_timing(self.dataset, self.profiles, self.root / "timing", launches=1, warmup=1, passes=1)
        self.assertEqual(summary["completion_status"], "interrupted")
        self.assertEqual(summary["recorded_calls"], 2)
        self.created[0].close.assert_called_once_with()
        self.assertTrue((self.root / "timing/trials.jsonl").read_bytes().endswith(b"\n"))
        self.assertEqual(summary["candidates"]["first"]["per_pass_quality"][0]["metrics"]["counts_by_status"]["missing"], 2)

    def test_between_launch_identity_change_stops_and_closes_new_adapter(self):
        actual = self.factory
        def changing(*args, **kwargs):
            adapter = actual(*args, **kwargs)
            if len(self.created) == 2:
                adapter.provenance["identity_sha256"] = "0" * 64
            return adapter
        with patch.object(campaigns, "create_adapter", side_effect=changing):
            summary = benchmark_timing(self.dataset, self.profiles[:1], self.root / "timing", launches=2, warmup=0, passes=1)
        self.assertEqual(summary["completion_status"], "error")
        self.assertEqual(summary["error_type"], "CampaignError")
        self.assertEqual(summary["recorded_calls"], 3)
        self.created[1].close.assert_called_once_with()

    def test_refuses_overwrite_stack_outputs_duplicate_ids_and_invalid_counts(self):
        self.run_timing(launches=1, warmup=0, passes=1)
        with self.assertRaises(FileExistsError):
            self.run_timing()
        with self.assertRaises(campaigns.CampaignError):
            benchmark_timing(self.dataset, self.profiles, self.root / "stack/output", stack_root=self.root / "stack")
        with self.assertRaises(campaigns.CampaignError):
            benchmark_timing(self.dataset, [self.profiles[0], self.profiles[0]], self.root / "duplicate")
        for key, value in (("launches", True), ("warmup", -1), ("passes", 0)):
            with self.subTest(key=key), self.assertRaises(campaigns.CampaignError):
                benchmark_timing(self.dataset, self.profiles, self.root / key, **{key: value})

    def test_large_trial_plan_rejected_before_adapter_or_output_allocation(self):
        output = self.root / "oversized"
        # A bounded fake loader is enough to exercise the preflight arithmetic;
        # no large file, archive or worker is created.
        with patch.object(campaigns, "load_cases", return_value=(self.cases * 50, "unused")), \
                patch.object(campaigns, "create_adapter") as factory, \
                patch.object(campaigns, "_destination") as destination, \
                self.assertRaisesRegex(campaigns.CampaignError, "100000"):
            benchmark_timing(self.dataset, self.profiles, output, launches=10, warmup=100, passes=100)
        factory.assert_not_called()
        destination.assert_not_called()
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
