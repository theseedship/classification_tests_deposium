"""Observation transport tests with fake local adapters, without model weights."""
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import mastra_observation as observation
from deposium_bench.cli import main
from deposium_bench.campaigns import _encode, _hash
from deposium_bench.mastra_pilot import DATASET, load_review_dataset

PROFILE = Path(__file__).resolve().parents[1] / "profiles/indecis-open-cpu-context.json"
JEV_PROFILE = str(Path(__file__).resolve().parents[1] / "profiles/jev-api-context.json")
PROFILES = Path(__file__).resolve().parents[1] / "profiles"
LARGER_CPU_PROFILES = (
    ("decision2-nox-cpu-context.json", 24576),
    ("vela2-4-cpu-context.json", 24576),
    ("liquid-d1-3b-cpu-context.json", 22528),
)


class FakeAdapter:
    def __init__(self):
        self.provenance = {"available": True, "identity_sha256": "fake-adapter-control"}
        self.calls = []
        self.closed = False

    def predict(self, request):
        self.calls.append(deepcopy(request))
        return {"status": "ok", "output": {"choice_id": "a"}, "error": None,
                "raw_output": {"forward_executed": True, "decision_ms": 2.0, "inference_ms": 1.0, "rss_mb": 10.0}}

    def close(self):
        self.closed = True


class MastraObservationTests(unittest.TestCase):
    def setUp(self):
        self.cases, _ = load_review_dataset()

    def test_missing_cases_and_errors_remain_in_denominator(self):
        records = [{"case_id": self.cases[0]["case_id"], "response": {"status": "timeout"},
                    "decision": None, "adapter_wall_ms": 100.0}]
        result = observation.observation_summary(self.cases, records)
        self.assertEqual(result["coverage"]["statuses"], {"timeout": 1, "missing": 23})
        self.assertEqual(result["coverage"]["total"], 24)
        self.assertEqual(result["cases_scored"], 0)
        self.assertIsNone(result["coverage"]["agreement_over_valid"])
        self.assertEqual(result["semantic_verdict"], "not_qualified")

    def test_forward_flags_distinguish_unknown_from_explicit_zero(self):
        records = [{"case_id": self.cases[0]["case_id"],
                    "response": {"status": "error", "raw_output": {"forward_executed": False}},
                    "decision": None}]
        result = observation.observation_summary(self.cases, records)
        self.assertEqual(result["forward_executed"], 0)
        self.assertEqual(result["forward_execution_flags"], {"true": 0, "false": 1, "unknown": 0})
        records[0]["response"]["raw_output"] = {"inference_ms": 1.0}
        result = observation.observation_summary(self.cases, records)
        self.assertIsNone(result["forward_executed"])
        self.assertEqual(result["forward_execution_flags"], {"true": 0, "false": 0, "unknown": 1})
        records[0]["response"]["raw_output"] = {"forward_executed": 1}
        self.assertEqual(observation.observation_summary(self.cases, records)["forward_execution_flags"]["unknown"], 1)

    def test_latency_of_successes_does_not_absorb_timeout_or_cached_error(self):
        records = [{"case_id": self.cases[i]["case_id"], "response": {"status": status},
                    "decision": None, "adapter_wall_ms": elapsed}
                   for i, (status, elapsed) in enumerate((("ok", 20.0), ("timeout", 30000.0), ("error", 0.01)))]
        result = observation.observation_summary(self.cases, records)
        self.assertEqual(result["timing_scope"], "all_recorded_calls_including_failures")
        self.assertEqual(result["timing"]["adapter_wall_ms"]["count"], 3)
        self.assertEqual(result["timing_by_status"]["ok"]["adapter_wall_ms"]["median_ms"], 20.0)
        self.assertEqual(result["timing_by_status"]["timeout"]["adapter_wall_ms"]["median_ms"], 30000.0)
        self.assertEqual(result["timing_by_status"]["error"]["adapter_wall_ms"]["count"], 1)

    def test_http_cached_failures_exclude_local_cached_errors(self):
        records = [{"case_id": self.cases[index]["case_id"], "decision": None,
                    "response": {"status": "error", "raw_output": raw}}
                   for index, raw in enumerate([
                       {"cached_failure": True, "forward_executed": False},
                       {"cached_failure": True, "http_attempted": False, "cause_attempt_id": "fake-attempt"}])]
        result = observation.observation_summary(self.cases, records)
        self.assertEqual(result["http"]["cached_failure"], 1)
        self.assertEqual(result["http"]["attempted"], 0)

    def test_duplicate_or_unknown_results_rejected(self):
        row = {"case_id": "unknown"}
        for records in ([row], [row, row]):
            with self.assertRaises(ValueError):
                observation.observation_summary(self.cases, records)

    def test_cli_requires_valid_decision_without_using_provisional_agreement(self):
        scenarios = [
            ("complete", 0, 0, 1),
            ("complete", 1, 0, 0),
            ("incomplete", 1, 1, 1),
        ]
        for completion, valid, agreements, expected in scenarios:
            with self.subTest(completion=completion, valid=valid, agreements=agreements):
                summary = {"completion_status": completion, "stop_reason": None,
                           "metrics": {"coverage": {"total": 24, "valid_decisions": valid,
                                                     "agreement_count": agreements},
                                       "cases_scored": 0, "semantic_verdict": "not_qualified"}}
                output = io.StringIO()
                with patch.object(observation, "observe_local", return_value=summary) as observe, \
                        redirect_stdout(output):
                    result = main(["observe-mastra-read", "--profile", str(PROFILE),
                                   "--output", "unused-mocked-output"])
                self.assertEqual(result, expected)
                self.assertEqual(json.loads(output.getvalue()), summary)
                observe.assert_called_once()
                self.assertIs(observe.call_args.kwargs["allow_remote"], False)

    def test_cli_remote_requires_explicit_flag(self):
        summary = {"completion_status": "complete", "stop_reason": None,
                   "metrics": {"coverage": {"valid_decisions": 1}}}
        with patch.object(observation, "observe_local", return_value=summary) as observe, \
                redirect_stdout(io.StringIO()):
            self.assertEqual(main(["observe-mastra-read", "--profile", JEV_PROFILE,
                                   "--output", "unused-mocked-output", "--allow-remote"]), 0)
        self.assertIs(observe.call_args.kwargs["allow_remote"], True)

    def test_paid_profile_rejected_before_factory_or_archive(self):
        profile = {"adapter": "jev_http", "capabilities": ["bench.context-choice"]}
        with tempfile.TemporaryDirectory() as root, patch.object(observation, "load_profile", return_value=(profile, "sha")), \
                patch.object(observation, "create_adapter") as factory:
            output = Path(root) / "forbidden"
            with self.assertRaisesRegex(ValueError, "local choice models"):
                observation.observe_local(DATASET, PROFILE, output)
            factory.assert_not_called()
            self.assertFalse(output.exists())

    def test_memory_gate_precedes_model_and_archive(self):
        with tempfile.TemporaryDirectory() as root, patch.object(observation, "memory_snapshot", return_value={"MemAvailable_mib": 512}), \
                patch.object(observation, "create_adapter") as factory:
            output = Path(root) / "low-memory"
            with self.assertRaisesRegex(ValueError, "available RAM"):
                observation.observe_local(DATASET, PROFILE, output)
            factory.assert_not_called()
            self.assertFalse(output.exists())

    def test_mastra_budget_retains_legacy_300_and_allows_larger_cpu_600(self):
        legacy = ("decision2-eos-cpu-context.json", "vela2-08-cpu-context.json",
                  "omni-cpu-context.json", "indecis-open-cpu-context.json")
        for name in legacy:
            with self.subTest(profile=name), tempfile.TemporaryDirectory() as root, \
                    patch.object(observation, "create_adapter") as factory:
                output = Path(root) / "budget-rejected"
                with self.assertRaisesRegex(ValueError, "1..300 seconds"):
                    observation.observe_local(DATASET, PROFILES / name, output, max_seconds=301)
                factory.assert_not_called()
                self.assertFalse(output.exists())
        for name in (item[0] for item in LARGER_CPU_PROFILES):
            with self.subTest(profile=name), tempfile.TemporaryDirectory() as root, \
                    patch.object(observation, "memory_snapshot", return_value={"MemAvailable_mib": 0}), \
                    patch.object(observation, "create_adapter") as factory:
                output = Path(root) / "memory-rejected"
                # Passing the budget check reaches the pre-archive RAM gate.
                with self.assertRaisesRegex(ValueError, "available RAM"):
                    observation.observe_local(DATASET, PROFILES / name, output, max_seconds=600)
                factory.assert_not_called()
                self.assertFalse(output.exists())
        with tempfile.TemporaryDirectory() as root, \
                patch.object(observation, "memory_snapshot", return_value={"MemAvailable_mib": 0}), \
                patch.object(observation, "create_adapter") as factory:
            output = Path(root) / "d3-memory-rejected"
            with self.assertRaisesRegex(ValueError, "available RAM"):
                observation.observe_local(DATASET, PROFILES / "d3-nano-cpu-context.json", output,
                                          max_seconds=600)
            factory.assert_not_called()
            self.assertFalse(output.exists())
        for name in (item[0] for item in LARGER_CPU_PROFILES):
            with self.subTest(profile=name), tempfile.TemporaryDirectory() as root, \
                    patch.object(observation, "create_adapter") as factory:
                output = Path(root) / "budget-rejected"
                with self.assertRaisesRegex(ValueError, "1..600 seconds"):
                    observation.observe_local(DATASET, PROFILES / name, output, max_seconds=601)
                factory.assert_not_called()
                self.assertFalse(output.exists())

    def test_larger_cpu_ram_gate_is_model_specific_and_precedes_archive(self):
        for name, minimum in LARGER_CPU_PROFILES:
            with self.subTest(profile=name, available=minimum - 1), \
                    tempfile.TemporaryDirectory() as root, \
                    patch.object(observation, "memory_snapshot",
                                 return_value={"MemAvailable_mib": minimum - 1}), \
                    patch.object(observation, "_stack_context") as stack, \
                    patch.object(observation, "create_adapter") as factory:
                output = Path(root) / "low-memory"
                with self.assertRaisesRegex(ValueError, "available RAM"):
                    observation.observe_local(DATASET, PROFILES / name, output, max_seconds=600)
                stack.assert_not_called()
                factory.assert_not_called()
                self.assertFalse(output.exists())
            adapter = FakeAdapter()
            with self.subTest(profile=name, available=minimum), \
                    tempfile.TemporaryDirectory() as root, \
                    patch.object(observation, "memory_snapshot",
                                 return_value={"MemAvailable_mib": minimum}), \
                    patch.object(observation, "_stack_context", return_value=({}, None)), \
                    patch.object(observation, "create_adapter", return_value=adapter) as factory:
                output = Path(root) / "admitted"
                summary = observation.observe_local(DATASET, PROFILES / name, output, max_seconds=600)
                factory.assert_called_once()
                self.assertEqual(summary["completion_status"], "complete")
                self.assertEqual(len(adapter.calls), 24)
                self.assertTrue((output / "seal.json").is_file())
                self.assertTrue(adapter.closed)

    def test_larger_cpu_reserves_four_gib_between_calls(self):
        for name, minimum in LARGER_CPU_PROFILES:
            readings = iter((minimum, 4095))
            adapter = FakeAdapter()
            with self.subTest(profile=name), tempfile.TemporaryDirectory() as root, \
                    patch.object(observation, "memory_snapshot",
                                 side_effect=lambda: {"MemAvailable_mib": next(readings, 4095)}), \
                    patch.object(observation, "_stack_context", return_value=({}, None)), \
                    patch.object(observation, "create_adapter", return_value=adapter):
                summary = observation.observe_local(DATASET, PROFILES / name, Path(root) / "pressure")
                self.assertEqual(summary["stop_reason"], "host_memory_pressure")
                self.assertEqual(summary["completion_status"], "incomplete")
                self.assertEqual(adapter.calls, [])
                self.assertTrue(adapter.closed)
        readings = iter((7168, 4095))
        adapter = FakeAdapter()
        with tempfile.TemporaryDirectory() as root, \
                patch.object(observation, "memory_snapshot",
                             side_effect=lambda: {"MemAvailable_mib": next(readings, 4095)}), \
                patch.object(observation, "_stack_context", return_value=({}, None)), \
                patch.object(observation, "create_adapter", return_value=adapter):
            summary = observation.observe_local(DATASET, PROFILES / "decision2-eos-cpu-context.json",
                                                Path(root) / "legacy")
            self.assertEqual(summary["completion_status"], "complete")
            self.assertEqual(len(adapter.calls), 24)

    def test_small_model_ram_prerequisite_rejects_before_stack_model_and_archive(self):
        for mode in ("omni", "muose", "modernjev"):
            profile = Path(__file__).resolve().parents[1] / "profiles" / {
                "omni": "omni-cpu-context.json",
                "muose": "muose-cpu-context.json",
                "modernjev": "modernjev-cpu-context.json",
            }[mode]
            for available in (5119, 5120, 5500, 6143):
                with self.subTest(mode=mode, available=available), tempfile.TemporaryDirectory() as root, \
                        patch.object(observation, "memory_snapshot", return_value={"MemAvailable_mib": available}), \
                        patch.object(observation, "create_adapter", return_value=FakeAdapter()) as factory, \
                        patch.object(observation, "_stack_context", return_value=({}, None)) as stack:
                    output = Path(root) / "low-memory"
                    with self.assertRaisesRegex(ValueError, "available RAM"):
                        observation.observe_local(DATASET, profile, output)
                    stack.assert_not_called()
                    factory.assert_not_called()
                    self.assertFalse(output.exists())

    def test_small_model_ram_prerequisite_accepts_boundary(self):
        profile = Path(__file__).resolve().parents[1] / "profiles/muose-cpu-context.json"
        adapter = FakeAdapter()
        with tempfile.TemporaryDirectory() as root, \
                patch.object(observation, "memory_snapshot", return_value={"MemAvailable_mib": 6144}), \
                patch.object(observation, "create_adapter", return_value=adapter) as factory:
            output = Path(root) / "boundary"
            summary = observation.observe_local(DATASET, profile, output)
            factory.assert_called_once()
            self.assertTrue((output / "seal.json").is_file())
            self.assertEqual(summary["completion_status"], "complete")
            self.assertEqual(summary["metrics"]["coverage"]["valid_decisions"], 24)
            self.assertEqual(summary["metrics"]["cases_scored"], 0)
            self.assertTrue(adapter.closed)

    def test_remote_rejects_changed_corpus_before_adapter_or_archive(self):
        with tempfile.TemporaryDirectory() as root:
            modified = deepcopy(self.cases)
            modified[0]["candidate_input"]["message"] += " Additional request."
            dataset = Path(root) / "cases.jsonl"
            dataset.write_bytes(b"".join(_encode(case) for case in modified))
            output = Path(root) / "denied"
            with patch.object(observation, "create_adapter") as factory:
                with self.assertRaisesRegex(ValueError, "frozen synthetic"):
                    observation.observe_local(dataset, JEV_PROFILE, output, allow_remote=True)
            factory.assert_not_called()
            self.assertFalse(output.exists())

    def test_remote_uses_real_budget_with_mock_http_and_no_local_ram_gate(self):
        from deposium_bench.jev_http_adapter import JevHTTPAdapter
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            profile = json.loads(Path(JEV_PROFILE).read_text())
            profile["model"]["budget_ledger"] = str(root / "budget.jsonl")
            profile_path = root / "profile.json"
            profile_path.write_bytes(_encode(profile))
            bodies = []
            def http(_, body):
                decoded = json.loads(body)
                bodies.append(decoded)
                options = list(decoded["questions"]["answer"]["criteria"])
                native = {"model": "jev-1.13.0", "answers": {"answer": {
                    "type": "choice", "choice": options[0], "confidence": .8,
                    "probabilities": {option: value for option, value in zip(options, [.8, .1, .1])}}},
                    "usage": {"input_tokens": 17, "output_tokens": 2}}
                return 200, "fake-request", json.dumps(native).encode(), 3.0
            with patch.dict(os.environ, {"TYPESAFE_API_KEY": "synthetic-test-credential"}), \
                    patch.object(JevHTTPAdapter, "_http", http), \
                    patch.object(observation, "memory_snapshot", return_value={"MemAvailable_mib": 0}):
                output = root / "remote"
                summary = observation.observe_local(DATASET, profile_path, output, allow_remote=True)
            self.assertEqual(len(bodies), 24)
            for case, body in zip(self.cases, bodies):
                request = observation.candidate_request(case)["input"]
                self.assertEqual(set(body), {"model", "state", "questions"})
                self.assertEqual(body["state"], request["context"])
                self.assertEqual(body["questions"]["answer"]["instructions"], request["question"])
                self.assertEqual(body["questions"]["answer"]["criteria"],
                                 {option["description"]: None for option in request["options"]})
            events = [json.loads(line) for line in (root / "budget.jsonl").read_text().splitlines()]
            self.assertEqual(sum(event["kind"] == "reservation" for event in events), 24)
            self.assertEqual(sum(event["kind"] == "settlement" for event in events), 24)
            self.assertEqual(summary["metrics"]["http"]["input_tokens"], 24 * 17)
            self.assertEqual(summary["metrics"]["http"]["attempted"], 24)
            self.assertIsNone(summary["metrics"]["forward_executed"])
            self.assertEqual(summary["metrics"]["timing"]["http_ms"]["count"], 24)
            self.assertEqual(summary["metrics"]["timing"]["inference_ms"]["count"], 0)
            self.assertEqual(summary["metrics"]["coverage"]["valid_decisions"], 24)
            self.assertEqual(summary["metrics"]["cases_scored"], 0)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["mode"], "remote_single_pass")
            self.assertIsNone(manifest["budget"]["rss_guard_mib"])
            self.assertEqual(manifest["budget"]["http_policy"]["max_requests"], 800)

    def test_remote_budget_exhaustion_stops_http_without_dropping_cases(self):
        from deposium_bench.jev_http_adapter import JevHTTPAdapter
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            profile = json.loads(Path(JEV_PROFILE).read_text())
            profile["model"]["budget_ledger"] = str(root / "budget.jsonl")
            profile["model"]["max_requests"] = 1
            profile_path = root / "profile.json"
            profile_path.write_bytes(_encode(profile))
            calls = []
            def http(_, body):
                calls.append(body)
                options = list(json.loads(body)["questions"]["answer"]["criteria"])
                native = {"model": "jev-1.13.0", "answers": {"answer": {
                    "type": "choice", "choice": options[0], "confidence": 1.0,
                    "probabilities": {option: float(index == 0) for index, option in enumerate(options)}}},
                    "usage": {"input_tokens": 17, "output_tokens": 2}}
                return 200, "fake-request", json.dumps(native).encode(), 3.0
            with patch.dict(os.environ, {"TYPESAFE_API_KEY": "synthetic-test-credential"}), \
                    patch.object(JevHTTPAdapter, "_http", http), \
                    patch.object(observation, "memory_snapshot", return_value={}):
                summary = observation.observe_local(DATASET, profile_path, root / "remote", allow_remote=True)
            self.assertEqual(len(calls), 1)
            self.assertEqual(summary["metrics"]["coverage"]["statuses"], {"ok": 1, "error": 23})
            self.assertEqual(summary["metrics"]["coverage"]["total"], 24)
            self.assertEqual(summary["metrics"]["http"]["attempted"], 1)
            events = [json.loads(line) for line in (root / "budget.jsonl").read_text().splitlines()]
            self.assertEqual([event["kind"] for event in events], ["policy", "reservation", "settlement"])
            records = [json.loads(line) for line in (root / "remote/raw.jsonl").read_text().splitlines()]
            self.assertTrue(all(row["response"]["error"] == "jev_request_budget_exhausted" for row in records[1:]))

    def test_bounded_observation_is_sealed_unscored_and_reference_free(self):
        adapter = FakeAdapter()
        with tempfile.TemporaryDirectory() as root, patch.object(observation, "memory_snapshot", return_value={"MemAvailable_mib": 10000}), \
                patch.object(observation, "create_adapter", return_value=adapter):
            output = Path(root) / "observation"
            summary = observation.observe_local(DATASET, PROFILE, output)
            self.assertEqual(summary["completion_status"], "complete")
            self.assertTrue(adapter.closed)
            self.assertEqual(len(adapter.calls), 24)
            for request in adapter.calls:
                self.assertEqual(set(request), {"case_id", "contract_id", "input"})
                self.assertEqual(set(request["input"]), {"question", "context", "options"})
                self.assertNotIn("reference", request["input"])
            self.assertEqual(summary["metrics"]["cases_scored"], 0)
            self.assertEqual(summary["metrics"]["coverage"]["agreement_count"], 8)
            seal = json.loads((output / "seal.json").read_text())
            self.assertEqual(seal["sha256"], _hash(_encode(seal["files"])))
            for name, digest in seal["files"].items():
                self.assertEqual(_hash((output / name).read_bytes()), digest)
            with self.assertRaises(FileExistsError):
                observation.observe_local(DATASET, PROFILE, output)

    def test_invalid_choice_never_becomes_executable_decision(self):
        adapter = FakeAdapter()
        adapter.predict = lambda request: {"status": "ok", "output": {"choice_id": "outside"},
                                           "raw_output": None, "error": None}
        with tempfile.TemporaryDirectory() as root, patch.object(observation, "memory_snapshot", return_value={"MemAvailable_mib": 10000}), \
                patch.object(observation, "create_adapter", return_value=adapter):
            summary = observation.observe_local(DATASET, PROFILE, Path(root) / "invalid")
            self.assertEqual(summary["metrics"]["coverage"]["statuses"], {"error": 24})
            self.assertEqual(summary["metrics"]["coverage"]["valid_decisions"], 0)
            self.assertTrue(adapter.closed)


if __name__ == "__main__":
    unittest.main()
