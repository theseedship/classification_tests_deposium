"""Offline controls for the fixed passage choice pilot and archive boundary."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench.campaigns import _encode, _hash, _prepare_profile
from deposium_bench.jev_http_adapter import JevHTTPAdapter
from deposium_bench.passage_dataset import load_dataset
from deposium_bench.passage_observation import (
    PassageObservationError, _logical_predictions, _seal, _verified_files, analyze, choice_plan, compose_rankings,
    observe_choice, select_pilot,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles/d3-lite-cpu-context.json"
JEV_PROFILE = ROOT / "profiles/jev-api-context.json"


class ArchiveFileBoundaryTests(unittest.TestCase):
    def test_archive_root_symlink_is_rejected_before_reading(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "archive"
            archive.mkdir()
            (archive / "raw.jsonl").write_bytes(b"{}\n")
            _seal(archive)
            alias = root / "alias"
            alias.symlink_to(archive, target_is_directory=True)
            with patch.object(Path, "read_bytes", side_effect=AssertionError("read through archive link")):
                with self.assertRaises(PassageObservationError):
                    _verified_files(alias, {"raw.jsonl"})

    def test_archive_rejects_symlinks_and_nonregular_entries_before_reading(self):
        for name in ("seal.json", "raw.jsonl", "extra"):
            for kind in ("symlink", "directory", "fifo"):
                with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    archive = root / "archive"
                    archive.mkdir()
                    (archive / "raw.jsonl").write_bytes(b"{}\n")
                    _seal(archive)
                    entry = archive / name
                    payload = entry.read_bytes() if entry.exists() else b"external\n"
                    if entry.exists():
                        entry.unlink()
                    if kind == "symlink":
                        external = root / "external"
                        external.write_bytes(payload)
                        entry.symlink_to(external)
                    elif kind == "directory":
                        entry.mkdir()
                    else:
                        os.mkfifo(entry)
                    # Also prevents a broken verifier from hanging on the FIFO.
                    with patch.object(Path, "read_bytes", side_effect=AssertionError("unsafe archive was read")):
                        with self.assertRaises(PassageObservationError):
                            _verified_files(archive, {"raw.jsonl"})


class FakeAdapter:
    instances = []

    def __init__(self, profile, path):
        self.provenance = {"available": True, "adapter": "fake"}
        self.closed = False
        self.seen = []
        self.responses = []
        self.instances.append(self)

    def predict(self, request):
        self.seen.append(request)
        if self.responses:
            return self.responses.pop(0)
        return {"status": "ok", "output": {"choice_id": "o1"}, "raw_output": {"forward_executed": True}, "error": None}

    def close(self):
        self.closed = True


class FakeResumeAdapter(FakeAdapter):
    _response = JevHTTPAdapter._response

    def __init__(self, profile, path):
        super().__init__(profile, path)
        self._key = None
        self._model = profile["model"]


class PassageObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, _ = load_dataset()
        cls.selected = select_pilot(cls.cases)

    def setUp(self):
        FakeAdapter.instances.clear()

    def _make_resume_parent(self, folder: Path, *, changed_plan: bool = False):
        folder.mkdir(parents=True, exist_ok=True)
        profile = json.loads(JEV_PROFILE.read_text())
        profile["model"]["budget_ledger"] = "budget.jsonl"
        profile_path = folder / "profile.json"
        profile_path.write_text(json.dumps(profile))
        archived_profile, source_hash, _ = _prepare_profile(profile_path)
        logical, physical = choice_plan(self.selected)
        source, dataset_hash = load_dataset()
        self.assertEqual(source, self.cases)
        parent = folder / "parent"
        parent.mkdir()
        native_rows = []
        for index, request in enumerate(physical[:104]):
            descriptions = [option["description"] for option in request["input"]["options"]]
            native = {"model": profile["model"]["model_id"],
                      "answers": {"answer": {"type": "choice", "choice": descriptions[0],
                                             "probabilities": {value: 1.0 if i == 0 else 0.0
                                                               for i, value in enumerate(descriptions)},
                                             "confidence": 1.0}},
                      "usage": {"input_tokens": 100, "output_tokens": 10}}
            raw = {"http_attempted": True, "cached_failure": False, "http_status": 200,
                   "attempt_id": f"attempt-{index}", "requested_model": native["model"],
                   "observed_model": native["model"] if index < 103 else None,
                   "usage": native["usage"] if index < 103 else None,
                   "native_result": native, "http_ms": 5.0}
            response = ({"status": "ok", "output": {"choice_id": request["input"]["options"][0]["id"]},
                         "raw_output": raw, "error": None} if index < 103 else
                        {"status": "error", "output": None, "raw_output": raw,
                         "error": "jev_response_invalid"})
            native_rows.append({"call_id": request["case_id"], "request_sha256": _hash(_encode(request)),
                                "response": response, "adapter_wall_ms": 6.0})
        physical_bytes = b"".join(_encode(request) for request in physical)
        if changed_plan:
            physical_bytes += b"{}\n"
        logical_bytes = b"".join(_encode(request) for request in logical)
        manifest = {"schema_version": "deposium.passage-choice-observation/v1",
                    "execution_scope": "remote_http_model_isolated", "split": "test",
                    "dataset_sha256": dataset_hash, "source_profile_sha256": source_hash,
                    "case_ids": [case["case_id"] for case in self.selected],
                    "physical_requests_sha256": _hash(physical_bytes),
                    "logical_requests_sha256": _hash(logical_bytes),
                    "budget": {"planned_unique_calls": 728}}
        summary = {"schema_version": "deposium.passage-choice-summary/v1",
                   "completion_status": "incomplete", "stop_reason": "adapter_unavailable",
                   "physical_attempted": 104, "physical_planned": 728,
                   "physical_statuses": {"ok": 103, "error": 1}}
        payloads = {"cases.jsonl": b"".join(_encode(case) for case in self.selected),
                    "dataset-manifest.json": (ROOT / "datasets/passage-evidence-v1/manifest.json").read_bytes(),
                    "logical-requests.jsonl": logical_bytes, "physical-requests.jsonl": physical_bytes,
                    "profile.json": _encode(archived_profile), "manifest.json": _encode(manifest),
                    "raw.jsonl": b"".join(_encode(row) for row in native_rows),
                    "logical-predictions.jsonl": b"".join(_encode(row) for row in _logical_predictions(logical, native_rows)),
                    "summary.json": _encode(summary), "adapter-initial.json": _encode({"available": True})}
        for name, payload in payloads.items():
            (parent / name).write_bytes(payload)
        _seal(parent)
        return profile_path, parent

    def test_jev_resume_reuses_104_and_predicts_only_remaining_624(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile, parent = self._make_resume_parent(root)
            original = {path.name: path.read_bytes() for path in parent.iterdir()}
            output = root / "resumed"
            summary = observe_choice(profile, output, adapter_factory=FakeResumeAdapter,
                                     memory_reader=lambda: {"MemAvailable_mib": 5000},
                                     allow_remote=True, resume_archive=parent)
            self.assertEqual(summary["completion_status"], "complete")
            self.assertEqual((summary["physical_inherited"], summary["physical_new"],
                              summary["physical_attempted"]), (104, 624, 728))
            self.assertEqual(len(FakeAdapter.instances[0].seen), 624)
            self.assertEqual({path.name: path.read_bytes() for path in parent.iterdir()}, original)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["resume_parent"],
                             {"path": str(parent), "seal_sha256": _hash(original["seal.json"]),
                              "physical_inherited": 104})
            records = [json.loads(line) for line in (output / "raw.jsonl").read_bytes().splitlines()]
            self.assertEqual(sum("revalidated_from" in row for row in records), 104)
            self.assertEqual(records[103]["revalidated_from"]["prior_error"], "jev_response_invalid")
            self.assertEqual(records[103]["response"]["status"], "ok")
            self.assertEqual(records[103]["response"]["raw_output"]["attempt_id"], "attempt-103")
            self.assertEqual(records[103]["response"]["raw_output"]["usage"],
                             {"input_tokens": 100, "output_tokens": 10})
            self.assertFalse((root / "budget.jsonl").exists())
            _verified_files(output, {"raw.jsonl", "manifest.json", "summary.json"})

    def test_jev_resume_rejects_no_opt_in_bad_profile_plan_and_seal_before_adapter(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile, parent = self._make_resume_parent(root)
            def refuse_factory(*_):
                raise AssertionError("adapter must not be created")
            def attempt(name, path=profile, source=parent, remote=True):
                with self.assertRaises((PassageObservationError, ValueError)):
                    observe_choice(path, root / name, adapter_factory=refuse_factory,
                                   memory_reader=lambda: {"MemAvailable_mib": 5000},
                                   allow_remote=remote, resume_archive=source)
                self.assertFalse((root / name).exists())
            attempt("no-opt-in", remote=False)
            different = json.loads(profile.read_text())
            different["model"]["model_id"] = "jev-1.14.0"
            different_path = root / "different.json"
            different_path.write_text(json.dumps(different))
            attempt("bad-profile", path=different_path)
            _, changed_plan = self._make_resume_parent(root / "other", changed_plan=True)
            attempt("bad-plan", source=changed_plan)
            (parent / "raw.jsonl").write_bytes((parent / "raw.jsonl").read_bytes() + b"\n")
            attempt("bad-seal")

    def test_jev_resume_rejects_symlinked_parent_before_adapter_or_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile, parent = self._make_resume_parent(root)
            alias = root / "parent-alias"
            alias.symlink_to(parent, target_is_directory=True)
            output = root / "resumed"
            with self.assertRaises(PassageObservationError):
                observe_choice(profile, output, adapter_factory=FakeResumeAdapter,
                               memory_reader=lambda: {"MemAvailable_mib": 5000},
                               allow_remote=True, resume_archive=alias)
            self.assertFalse(output.exists())
            self.assertFalse(FakeAdapter.instances)

    def test_fixed_selection_deduplicates_only_visible_input(self):
        logical, physical = choice_plan(self.selected)
        self.assertEqual((len(self.selected), len(logical), len(physical)), (128, 1408, 728))
        self.assertEqual({row["axis"] for row in logical}, {"relevance", "support", "answerability"})
        self.assertTrue(all(set(row) == {"case_id", "contract_id", "input"} for row in physical))
        self.assertTrue(all(row["case_id"].startswith("call-") for row in physical))
        self.assertTrue(all("annotations" not in json.dumps(row) for row in physical))
        self.assertEqual(len({row["case_id"] for row in physical}), len(physical))

    def test_complete_fake_observation_preserves_all_logical_predictions(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "choice"
            summary = observe_choice(PROFILE, output, adapter_factory=FakeAdapter,
                                     memory_reader=lambda: {"MemAvailable_mib": 20000})
            self.assertEqual(summary["completion_status"], "complete")
            self.assertEqual((summary["physical_attempted"], summary["logical_decisions"]), (728, 1408))
            self.assertTrue(FakeAdapter.instances[0].closed)
            self.assertTrue(all(set(row) == {"case_id", "contract_id", "input"}
                                for row in FakeAdapter.instances[0].seen))
            files = _verified_files(output, {"raw.jsonl", "logical-predictions.jsonl", "scores.json"})
            logical = [json.loads(row) for row in files["logical-predictions.jsonl"].splitlines()]
            self.assertEqual(len(logical), 1408)
            self.assertEqual(sum(row["status"] == "ok" for row in logical), 1408)
            baseline_dir = Path(folder) / "baseline"
            baseline_dir.mkdir()
            baseline_path = baseline_dir / "rankings.jsonl"
            baseline_path.write_text("".join(json.dumps({"case_id": case["case_id"], "status": "ok",
                                     "ranking": [passage["id"] for passage in case["passages"]]}) + "\n"
                                     for case in self.selected))
            _seal(baseline_dir)
            derived = Path(folder) / "analysis"
            report = analyze(output, baseline_path, derived)
            self.assertEqual(report["baseline"]["scored_cases"], 128)
            self.assertEqual(report["replacement"]["scored_cases"], 128)
            _verified_files(derived, {"analysis.json", "parents.json"})

    def test_analysis_protects_both_source_archives_including_output_aliases(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            choice = root / "choice"
            observe_choice(PROFILE, choice, adapter_factory=FakeAdapter,
                           memory_reader=lambda: {"MemAvailable_mib": 20000})
            baseline = root / "baseline"
            baseline.mkdir()
            predictions = baseline / "rankings.jsonl"
            predictions.write_bytes(b"".join(_encode({"case_id": case["case_id"], "status": "ok",
                                      "ranking": [passage["id"] for passage in case["passages"]]})
                                      for case in self.selected))
            _seal(baseline)
            snapshots = {archive: {path.name: path.read_bytes() for path in archive.iterdir()}
                         for archive in (choice, baseline)}
            for archive in (choice, baseline):
                alias = root / (archive.name + "-alias")
                alias.symlink_to(archive, target_is_directory=True)
                for output in (archive, archive / "analysis", archive / "new" / "analysis",
                               alias / "analysis", alias / "new" / "analysis"):
                    with self.subTest(archive=archive.name, output=output):
                        with self.assertRaises(ValueError):
                            analyze(choice, predictions, output)
                        for source, snapshot in snapshots.items():
                            self.assertEqual(set(path.name for path in source.iterdir()), set(snapshot))
                            self.assertEqual({path.name: path.read_bytes() for path in source.iterdir()}, snapshot)
                            _verified_files(source, set(snapshot) - {"seal.json"})

    def test_analysis_rejects_symlinked_sources_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            choice = root / "choice"
            observe_choice(PROFILE, choice, adapter_factory=FakeAdapter,
                           memory_reader=lambda: {"MemAvailable_mib": 20000})
            baseline = root / "baseline"
            baseline.mkdir()
            predictions = baseline / "rankings.jsonl"
            predictions.write_bytes(b"")
            _seal(baseline)
            choice_alias = root / "choice-alias"
            choice_alias.symlink_to(choice, target_is_directory=True)
            baseline_alias = root / "baseline-alias"
            baseline_alias.symlink_to(baseline, target_is_directory=True)
            for choice_source, baseline_source in ((choice_alias, predictions),
                                                    (choice, baseline_alias / predictions.name)):
                with self.subTest(choice=choice_source, baseline=baseline_source):
                    output = root / "analysis"
                    with self.assertRaises(PassageObservationError):
                        analyze(choice_source, baseline_source, output)
                    self.assertFalse(output.exists())
            external = root / "external-rankings.jsonl"
            predictions.rename(external)
            predictions.symlink_to(external)
            with self.assertRaises(PassageObservationError):
                analyze(choice, predictions, root / "analysis")
            self.assertFalse((root / "analysis").exists())

    def test_profile_rejected_before_archive_or_adapter(self):
        with tempfile.TemporaryDirectory() as folder:
            profile = json.loads(PROFILE.read_text())
            profile["adapter"] = "jev_http"
            path = Path(folder) / "bad.json"
            path.write_text(json.dumps(profile))
            output = Path(folder) / "choice"
            with self.assertRaises((PassageObservationError, ValueError)):
                observe_choice(path, output, adapter_factory=FakeAdapter,
                               memory_reader=lambda: {"MemAvailable_mib": 20000})
            self.assertFalse(output.exists())
            self.assertFalse(FakeAdapter.instances)

    def test_jev_requires_explicit_remote_permission_before_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "choice"
            with self.assertRaisesRegex(PassageObservationError, "--allow-remote"):
                observe_choice(JEV_PROFILE, output, adapter_factory=FakeAdapter,
                               memory_reader=lambda: {"MemAvailable_mib": 20000})
            self.assertFalse(output.exists())
            self.assertFalse(FakeAdapter.instances)

    def test_jev_rejects_changed_corpus_before_archive_or_adapter(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch("deposium_bench.passage_observation.load_dataset",
                      return_value=(self.cases, "0" * 64)):
            output = Path(folder) / "choice"
            with self.assertRaisesRegex(PassageObservationError, "pinned passage corpus"):
                observe_choice(JEV_PROFILE, output, adapter_factory=FakeAdapter,
                               memory_reader=lambda: {"MemAvailable_mib": 20000},
                               allow_remote=True)
            self.assertFalse(output.exists())
            self.assertFalse(FakeAdapter.instances)

    def test_jev_uses_same_plan_and_records_remote_resource_scope(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch("deposium_bench.passage_observation.minimum_available_mib",
                      side_effect=AssertionError("local model RAM guard called")):
            output = Path(folder) / "choice"
            summary = observe_choice(JEV_PROFILE, output, adapter_factory=FakeAdapter,
                                     memory_reader=lambda: {"MemAvailable_mib": 5000},
                                     allow_remote=True)
            self.assertEqual(summary["completion_status"], "complete")
            self.assertEqual((summary["selected_cases"], summary["logical_decisions"],
                              summary["physical_planned"], summary["physical_attempted"]),
                             (128, 1408, 728, 728))
            self.assertTrue(FakeAdapter.instances[0].closed)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["execution_scope"], "remote_http_model_isolated")
            self.assertEqual(manifest["resource_observation"],
                             {"memory_snapshots": "client_host_only", "remote_model_ram": "not_observed"})
            self.assertEqual(manifest["budget"]["minimum_available_mib"], 4096)
            self.assertEqual(manifest["budget"]["planned_unique_calls"], 728)
            self.assertEqual(manifest["source_profile_sha256"],
                             hashlib.sha256(JEV_PROFILE.read_bytes()).hexdigest())
            archived = json.loads((output / "profile.json").read_text())
            self.assertEqual(archived["model"]["model_id"], "jev-1.13.0")
            self.assertEqual(len((output / "physical-requests.jsonl").read_bytes().splitlines()), 728)
            _verified_files(output, {"raw.jsonl", "manifest.json", "profile.json"})

    def test_jev_missing_credential_stops_without_http_or_ledger_write(self):
        profile = json.loads(JEV_PROFILE.read_text())
        profile["model"]["budget_ledger"] = "budget.jsonl"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "jev.json"
            path.write_text(json.dumps(profile))
            output = Path(folder) / "choice"
            with patch.dict("os.environ", {"TYPESAFE_API_KEY": ""}), \
                    patch("deposium_bench.jev_http_adapter.HTTPSConnection",
                          side_effect=AssertionError("unexpected HTTP")):
                summary = observe_choice(path, output,
                                         memory_reader=lambda: {"MemAvailable_mib": 5000},
                                         allow_remote=True)
            self.assertEqual(summary["completion_status"], "incomplete")
            self.assertEqual(summary["stop_reason"], "adapter_initialization_failed")
            self.assertEqual(summary["physical_attempted"], 0)
            self.assertEqual(summary["adapter_initial"]["availability_error"], "jev_credential_missing")
            self.assertFalse((Path(folder) / "budget.jsonl").exists())
            self.assertEqual((output / "raw.jsonl").read_bytes(), b"")
            _verified_files(output, {"summary.json", "raw.jsonl"})

    def test_unsupported_profile_is_rejected_even_with_remote_permission(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "choice"
            with self.assertRaises(PassageObservationError):
                observe_choice(ROOT / "profiles/d3-nano-cpu-context.json", output,
                               adapter_factory=FakeAdapter,
                               memory_reader=lambda: {"MemAvailable_mib": 20000},
                               allow_remote=True)
            self.assertFalse(output.exists())
            self.assertFalse(FakeAdapter.instances)

    def test_memory_floor_stops_and_closes_with_no_empty_pass(self):
        readings = iter(({"MemAvailable_mib": 20000}, {"MemAvailable_mib": 3000}))
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "choice"
            summary = observe_choice(PROFILE, output, adapter_factory=FakeAdapter,
                                     memory_reader=lambda: next(readings, {"MemAvailable_mib": 3000}))
            self.assertEqual(summary["stop_reason"], "host_memory_pressure")
            self.assertEqual(summary["physical_attempted"], 0)
            self.assertEqual(summary["completion_status"], "incomplete")
            self.assertTrue(FakeAdapter.instances[0].closed)
            scores = json.loads((output / "scores.json").read_text())
            self.assertTrue(all(report["scoring_status"] == "no_scored_predictions" for report in scores.values()))
            _verified_files(output, {"summary.json", "scores.json"})

    def test_adapter_initialization_exception_is_archived(self):
        def failing_factory(profile, path):
            raise RuntimeError("initialization failed")
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "choice"
            summary = observe_choice(PROFILE, output, adapter_factory=failing_factory,
                                     memory_reader=lambda: {"MemAvailable_mib": 20000})
            self.assertEqual(summary["stop_reason"], "observation_failed")
            self.assertEqual(summary["fatal_type"], "RuntimeError")
            self.assertEqual(summary["physical_attempted"], 0)
            self.assertEqual(summary["completion_status"], "incomplete")
            _verified_files(output, {"raw.jsonl", "summary.json", "scores.json"})

    def test_failure_statuses_remain_distinct_and_archive_is_tamper_evident(self):
        def factory(profile, path):
            adapter = FakeAdapter(profile, path)
            adapter.responses = [
                {"status": "unsupported", "output": None, "raw_output": None, "error": "test_unsupported"},
                {"status": "error", "output": None, "raw_output": None, "error": "test_error"},
            ]
            return adapter
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "choice"
            summary = observe_choice(PROFILE, output, adapter_factory=factory,
                                     memory_reader=lambda: {"MemAvailable_mib": 20000})
            self.assertEqual(summary["physical_statuses"]["unsupported"], 1)
            self.assertEqual(summary["physical_statuses"]["error"], 1)
            raw = output / "raw.jsonl"
            raw.write_bytes(raw.read_bytes() + b"\n")
            with self.assertRaises(PassageObservationError):
                _verified_files(output, {"raw.jsonl"})

    def test_composition_ties_preserve_pool_or_baseline_order_and_conflict_gate(self):
        case = next(case for case in self.selected if case["scenario_id"] == "conflicting_evidence")
        logical, _ = choice_plan([case])
        rows = []
        for request in logical:
            row = {key: request[key] for key in ("case_id", "axis")}
            row.update({key: request[key] for key in ("passage_id", "claim_id") if key in request})
            row["status"] = "ok"
            row["choice_id"] = "o3" if request["axis"] == "answerability" else "o1"
            rows.append(row)
        original = [passage["id"] for passage in case["passages"]]
        reverse = list(reversed(original))
        report = compose_rankings([case], rows, [{"case_id": case["case_id"], "status": "ok", "ranking": reverse}])
        self.assertEqual(report["replacement_predictions"][0]["ranking"], original)
        self.assertEqual(report["complement_predictions"][0]["ranking"], reverse)
        self.assertEqual(report["full_pool_answerability_gate"][0]["decision"], "conflicting_visible_evidence")
        missing = compose_rankings([case], rows, [])
        self.assertEqual(missing["baseline"]["counts_by_status"]["missing"], 1)
        self.assertEqual(missing["complement"]["scored_cases"], 0)


if __name__ == "__main__":
    unittest.main()
