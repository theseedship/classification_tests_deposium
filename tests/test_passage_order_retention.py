"""Order/retention controls are offline implementation checks, not model scores."""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import passage_order_retention as order
from deposium_bench import __version__
from deposium_bench.adapters import RecordedAdapter
from deposium_bench.campaigns import _encode, _hash
from deposium_bench.passage_dataset import export_requests, load_dataset
from deposium_bench.passage_observation import _logical_predictions, _seal, choice_plan
from tests.test_passage_dataset import fixture

ROOT = Path(__file__).resolve().parents[1]


def rotations(*, suffix="order", query_status="answerable", grades=(3, 2, 1, 0)):
    base = fixture(suffix=suffix, query_status=query_status, grades=grades)
    base["query"] += " " + suffix
    cases = []
    for rotation in order.ROTATIONS:
        case = deepcopy(base)
        case["case_id"] += f"-r{rotation}"
        case["passages"] = base["passages"][rotation:] + base["passages"][:rotation]
        case["provenance"]["position_rotation"] = rotation
        cases.append(case)
    return cases


def fixed_choices(cases, choice="o1"):
    return [{key: value for key, value in row.items()
             if key in {"case_id", "axis", "passage_id", "claim_id"}} |
            {"status": "ok", "choice_id": choice}
            for axis in order.AXES for row in export_requests(cases, axis)]


def write_source(root, selected, dataset_digest, *, fail_statuses=(), prefix=None):
    """Author a labeled fake transport archive; never call a candidate/tool."""
    root.mkdir()
    logical, physical = choice_plan(selected)
    raw = []
    for i, request in enumerate(physical if prefix is None else physical[:prefix]):
        status = fail_statuses[i] if i < len(fail_statuses) else "ok"
        response = {"status": status, "output": {"choice_id": "o1"} if status == "ok" else None,
                    "raw_output": None, "error": None if status == "ok" else "deliberate_control"}
        raw.append({"call_id": request["case_id"], "request_sha256": _hash(_encode(request)),
                    "response": response, "adapter_wall_ms": 0})
    profile = {"schema_version": "deposium.candidate/v1", "profile_id": "synthetic-order-control",
               "adapter": "recorded", "qualification": "harness_control", "capabilities": ["bench.context-choice"],
               "model": None, "revision": None, "recordings": "recordings.jsonl", "timeout_seconds": 1}
    original_profile_bytes = (json.dumps(profile, indent=2) + "\n").encode()
    recordings = b"".join(_encode({"case_id": row["call_id"], **row["response"]}) for row in raw)
    (root / "recordings.jsonl").write_bytes(recordings)
    # Use the actual recorded transport's pure provenance construction. No
    # predict(), model, live service or synthetic tool is invoked.
    initial = RecordedAdapter(profile, root / "profile.json").provenance
    bench_files = {path.name: _hash(path.read_bytes()) for path in sorted((ROOT / "deposium_bench").glob("*.py"))}
    bench = {"version": __version__, "files": bench_files, "sha256": _hash(_encode(bench_files)),
             "schemas": {}, "git": None, "source_archive": "not_captured"}
    files = {"cases.jsonl": b"".join(_encode(case) for case in selected),
             "dataset-manifest.json": (ROOT / "datasets/passage-evidence-v1/manifest.json").read_bytes(),
             "profile.json": _encode(profile), "adapter-initial.json": _encode(initial),
             "logical-requests.jsonl": b"".join(_encode(row) for row in logical),
             "physical-requests.jsonl": b"".join(_encode(row) for row in physical),
             "raw.jsonl": b"".join(_encode(row) for row in raw),
             "logical-predictions.jsonl": b"".join(_encode(row) for row in _logical_predictions(logical, raw)),
             "scores.json": _encode({"control_only": True}),
             "summary.json": _encode({"schema_version": "deposium.passage-choice-summary/v1",
                 "selected_cases": len(selected), "logical_decisions": len(logical),
                 "physical_planned": len(physical), "physical_attempted": len(raw),
                 "physical_statuses": dict(order.Counter(row["response"]["status"] for row in raw)),
                 "adapter_initial": initial, "adapter_final": deepcopy(initial),
                 "completion_status": "complete" if len(raw) == len(physical) else "incomplete"})}
    files["manifest.json"] = _encode({"schema_version": "deposium.passage-choice-observation/v1",
        "qualification": "harness_control_not_model", "dataset_sha256": dataset_digest,
        "source_profile_sha256": _hash(original_profile_bytes), "bench": bench,
        "case_ids": [case["case_id"] for case in selected],
        "logical_requests_sha256": _hash(files["logical-requests.jsonl"]),
        "physical_requests_sha256": _hash(files["physical-requests.jsonl"])})
    for name, payload in files.items():
        (root / name).write_bytes(payload)
    _seal(root)
    return raw


def native_identity_fixture(source):
    """Synthetic native metadata only; no model, asset, session or service exists."""
    files = order._verified_files(source, {"profile.json", "manifest.json", "summary.json"})
    manifest, summary = json.loads(files["manifest.json"]), json.loads(files["summary.json"])
    profile = {"schema_version": "deposium.candidate/v1", "profile_id": "synthetic-native-metadata",
        "adapter": "systemone_local", "qualification": "model_isolated", "revision": "a" * 40,
        "capabilities": ["bench.context-choice"], "recordings": None, "timeout_seconds": 30,
        "model": {"endpoint": "http://127.0.0.1:11438/v1/systemone", "model_id": "fixture-model",
            "repo_id": "fixture/model", "session_manifest": "synthetic-session.json", "session_sha256": "b" * 64,
            "max_length": 4096, "max_rss_mb": 18432, "credential_env": "DEPOSIUM_BENCH_LOCAL_KEY"}}
    identity = {key: {"sha256": _hash(key.encode()),
                     "binary" if key in {"runtime", "gateway"} else "path": f"synthetic-{key}"}
                for key in ("model", "runtime", "gateway", "harness", "runtime_pin")}
    identity["model"].update(repo_id="fixture/model", revision="a" * 40, alias="fixture-model")
    identity.update(settings={"context": 4096, "parallel": 1, "concurrency": 1, "questions_per_call": 1,
                              "truncation": "reject_in_pinned_native_engine"}, max_rss_mb=18432,
                    adapter_sha256=manifest["bench"]["files"]["systemone_local.py"],
                    choice_protocol_sha256=manifest["bench"]["files"]["choice_protocol.py"])
    from deposium_bench.systemone_local import _wire
    initial = {"adapter": "systemone_local", "qualification": "model_isolated",
               "capabilities": ["bench.context-choice"], "available": True, "identity": identity,
               "identity_sha256": _hash(_wire(identity)), "session_sha256": "b" * 64,
               "model_execution": "not_observed"}
    manifest.update(qualification="isolated_model_observation_agent_only_references",
                    execution_scope="supervised_native_model_isolated",
                    source_profile_sha256=_hash((json.dumps(profile, indent=2) + "\n").encode()))
    manifest["native_supervision"] = {"session_sha256": "b" * 64,
                                       "profile_sha256": manifest["source_profile_sha256"]}
    files["profile.json"] = _encode(profile)
    files["adapter-initial.json"] = _encode(initial)
    summary.update(adapter_initial=deepcopy(initial), adapter_final=deepcopy(initial))
    return files, manifest, summary


class PassageOrderRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all_cases, cls.digest = load_dataset()
        cls.selected = order.select_order_cases(cls.all_cases)
        cls.plan = order.build_plan()

    def test_frozen_plan_exact_call_accounting_and_projection_boundary(self):
        plan = self.plan
        self.assertEqual(plan, json.loads((ROOT / "plans/passage-order-retention-v1.json").read_text()))
        self.assertEqual(plan["dataset"]["pools"], 512)
        self.assertEqual(plan["dataset"]["families"], 8)
        self.assertEqual(plan["logical_decisions"], 5632)
        self.assertEqual(plan["distinct_physical_calls"], 920)
        for axis, logical, physical in (("relevance", 2048, 264), ("support", 3072, 392),
                                         ("answerability", 512, 264)):
            self.assertEqual(plan["by_axis"][axis]["logical_decisions"], logical)
            self.assertEqual(plan["by_axis"][axis]["distinct_physical_calls"], physical)
        self.assertEqual(plan["retention_rule"]["cutoffs"], [1, 3, 4])
        self.assertEqual(plan["current_execution_budget"]["model_calls"], 0)

    def test_rotations_preserve_frozen_annotations_but_not_array_order(self):
        order.validate_rotations(self.selected)
        cases = rotations()
        for case in cases:
            case["annotations"]["relevance"].reverse()
        order.validate_rotations(cases)
        for changed in (cases[:-1], [cases[0], *cases[:-1]]):
            with self.subTest(cases=len(changed)), self.assertRaises(ValueError):
                order.validate_rotations(changed)
        damaged = deepcopy(cases)
        damaged[1]["passages"] = damaged[0]["passages"]
        with self.assertRaisesRegex(ValueError, "rotation must preserve"):
            order.validate_rotations(damaged)

    def test_single_passage_inputs_are_invariant_while_pool_order_is_visible(self):
        cases = rotations()
        for axis in ("relevance", "support"):
            requests = export_requests(cases, axis)
            p0 = [r for r in requests if r["passage_id"] == "p0"]
            self.assertEqual(len({_encode(r["input"]) for r in p0}), 1)
            self.assertNotIn("family", json.dumps(p0[0]["input"]))
        self.assertEqual(len({_encode(r["input"]) for r in export_requests(cases, "answerability")}), 4)

    def test_rotation_label_change_is_distinct_from_status_failure(self):
        cases = rotations()
        rows = fixed_choices(cases)
        row = next(r for r in rows if r["axis"] == "answerability" and r["case_id"].endswith("r1"))
        row["choice_id"] = "o2"
        report = order.score_order(cases, rows)
        overall = report["choice_scores"]["answerability"]["order_sensitivity"]["overall"]
        self.assertEqual(overall["complete_valid_groups"], 1)
        self.assertEqual(overall["label_disagreement_groups"], 1)
        self.assertEqual(overall["correctness_changed_groups"], 1)
        self.assertEqual(overall["all_rotations_correct_over_all"], 0)
        row.pop("choice_id")
        row["status"] = "timeout"
        failure = order.score_order(cases, rows)["choice_scores"]["answerability"]
        self.assertEqual(failure["counts_by_status"]["timeout"], 1)
        self.assertEqual(failure["order_sensitivity"]["overall"]["complete_valid_groups"], 0)
        self.assertIsNone(failure["order_sensitivity"]["overall"]["label_disagreement_over_complete"])

    def test_missing_choices_preserve_all_denominators_and_never_pass(self):
        report = order.score_order(rotations(), [])
        for axis in order.AXES:
            self.assertEqual(report["choice_scores"][axis]["accuracy_over_all"], 0)
            self.assertEqual(report["choice_scores"][axis]["scored_cases"], 0)
        metric = report["replacement"]["evidence_retention"]["metrics"]["sufficient_set@3"]
        self.assertEqual(metric["eligible_cases"], 4)
        self.assertEqual(metric["defined_cases"], 0)
        self.assertEqual(metric["mean_over_eligible_missing_zero"], 0)
        self.assertIsNone(metric["mean"])

    def test_unknown_duplicate_missing_and_empty_outputs_fail(self):
        cases = rotations()
        good = fixed_choices(cases)
        for changed in ([good[0], good[0]], [good[0] | {"case_id": "unknown", "status": "missing"}],
                        [good[0] | {"status": "missing"}], [good[0] | {"choice_id": ""}],
                        [good[0] | {"status": "error"}]):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                order.score_order(cases, changed)

    def test_joint_evidence_wrong_order_and_missing_rankings_are_penalized(self):
        cases = rotations()
        for case in cases:
            case["annotations"]["minimal_evidence_sets"] = [["p0", "p1"]]
        wrong = [{"case_id": c["case_id"], "status": "ok", "ranking": ["p2", "p3", "p0", "p1"]} for c in cases]
        report = order.evidence_retention(cases, wrong)["evidence_retention"]
        self.assertEqual(report["metrics"]["sufficient_set@3"]["mean"], 0)
        self.assertEqual(report["metrics"]["sufficient_set@4"]["mean"], 1)
        wrong[0] = {"case_id": cases[0]["case_id"], "status": "unsupported"}
        del wrong[1]
        metrics = order.evidence_retention(cases, wrong)["evidence_retention"]["metrics"]
        self.assertEqual(metrics["sufficient_set@4"]["eligible_cases"], 4)
        self.assertEqual(metrics["sufficient_set@4"]["defined_cases"], 2)
        self.assertEqual(metrics["sufficient_set@4"]["mean_over_eligible_missing_zero"], 0.5)

    def test_any_frozen_alternative_sufficient_set_is_accepted(self):
        cases = rotations()
        for case in cases:
            case["annotations"]["minimal_evidence_sets"] = [["p0"], ["p1"]]
        rankings = [{"case_id": c["case_id"], "status": "ok", "ranking": ["p1", "p2", "p3", "p0"]} for c in cases]
        metric = order.evidence_retention(cases, rankings)["evidence_retention"]["metrics"]["sufficient_set@1"]
        self.assertEqual(metric["mean_over_eligible_missing_zero"], 1)

    def test_conflict_capture_requires_both_sides_of_the_same_claim(self):
        cases = rotations(query_status="conflicting_visible_evidence")
        for case in cases:
            second = deepcopy(case["annotations"]["claims"][0])
            second.update(id="claim-2", text="Une autre affirmation.")
            for j in second["judgments"]:
                j.update(label="insufficient", spans=[])
            second["judgments"][2].update(label="refutes", spans=[{"start": 0, "end": 10,
                "text": case["passages"][[p["id"] for p in case["passages"]].index("p2")]["text"][:10]}])
            case["annotations"]["claims"].append(second)
        rankings = [{"case_id": c["case_id"], "status": "ok", "ranking": ["p0", "p2", "p3", "p1"]} for c in cases]
        metrics = order.evidence_retention(cases, rankings)["evidence_retention"]["metrics"]
        self.assertEqual(metrics["conflict_pair@3"]["mean"], 0)
        self.assertEqual(metrics["conflict_pair@4"]["mean"], 1)
        self.assertIsNone(metrics["sufficient_set@3"]["mean_over_eligible_missing_zero"])

    def test_no_evidence_is_inapplicable_and_zero_gain_ranking_stays_undefined(self):
        cases = rotations(query_status="insufficient_visible_evidence", grades=(0, 0, 0, 0))
        rankings = [{"case_id": c["case_id"], "status": "ok", "ranking": ["p0", "p1", "p2", "p3"]} for c in cases]
        report = order.evidence_retention(cases, rankings)
        self.assertEqual(report["evidence_retention"]["scoring_status"], "no_eligible_retention_cases")
        for metric in report["evidence_retention"]["metrics"].values():
            self.assertEqual(metric["eligible_cases"], 0)
            self.assertIsNone(metric["mean_over_eligible_missing_zero"])
        self.assertIsNone(report["ranking_scores"]["metrics"]["ndcg@3"]["mean"])

    def test_equal_relevance_can_change_retention_via_declared_input_order_ties(self):
        report = order.score_order(rotations(), fixed_choices(rotations()))
        relevance = report["choice_scores"]["relevance"]["order_sensitivity"]
        self.assertEqual(relevance["interpretation"], "single_passage_projection_invariant")
        self.assertEqual(relevance["overall"]["label_disagreement_groups"], 0)
        retention = report["replacement"]["evidence_retention"]["metrics"]
        self.assertEqual(retention["sufficient_set@1"]["mean_over_eligible_missing_zero"], 0.25)

    def test_archive_exact_reuse_preserves_unobserved_orders_without_execution(self):
        selected = [c for c in self.selected if c["provenance"]["position_rotation"] == 0]
        with tempfile.TemporaryDirectory() as tmp:
            source, destination = Path(tmp) / "source", Path(tmp) / "derived"
            raw = write_source(source, selected, self.digest,
                               fail_statuses=("error", "timeout", "unsupported", "abstain"))
            forbidden = ("socket.create_connection", "urllib.request.urlopen", "subprocess.Popen",
                         "deposium_bench.adapters.create_adapter", "deposium_bench.passage_observation.create_adapter",
                         "deposium_bench.passage_observation.observe_choice")
            with ExitStack() as stack:
                for target in forbidden:
                    stack.enter_context(patch(target, side_effect=AssertionError(f"offline analysis must not call {target}")))
                report = order.analyze_archive(source, destination)
            observations = report["source_observations"]
            self.assertEqual(observations["source_declared_qualification"], "harness_control_not_model")
            identity = observations["source_identity"]
            self.assertEqual(identity["qualification"], "harness_control")
            self.assertEqual(identity["adapter_identity_check"], "recorded_identity_rehashed")
            self.assertNotEqual(identity["source_profile_bytes_sha256"], identity["archived_profile_bytes_sha256"])
            self.assertEqual(observations["new_physical_calls"], 0)
            self.assertEqual(observations["target_physical_observed"], 728)
            self.assertEqual(observations["target_physical_unobserved"], 192)
            for status in ("error", "timeout", "unsupported", "abstain"):
                self.assertEqual(observations["source_physical_statuses"][status], 1)
                self.assertGreater(report["choice_scores"]["relevance"]["counts_by_status"][status], 0)
            self.assertGreater(report["choice_scores"]["answerability"]["counts_by_status"]["missing"], 0)
            self.assertEqual((source / "raw.jsonl").read_bytes(), b"".join(_encode(r) for r in raw))
            order._verified_files(destination, {"analysis.json", "parents.json"})
            with self.assertRaises((ValueError, OSError)):
                order.analyze_archive(source, destination)

    def test_archive_rejects_changed_physical_plan_and_forged_logical_projection(self):
        selected = [c for c in self.selected if c["provenance"]["position_rotation"] == 0]
        for filename in ("physical-requests.jsonl", "logical-predictions.jsonl", "summary.json"):
            with self.subTest(file=filename), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / "source"
                write_source(source, selected, self.digest)
                path = source / filename
                if filename.endswith(".jsonl"):
                    rows = order._jsonl(path.read_bytes())
                    rows[0]["case_id"] = "invented"
                    path.write_bytes(b"".join(_encode(row) for row in rows))
                else:
                    summary = json.loads(path.read_text())
                    summary["physical_attempted"] = 0
                    path.write_bytes(_encode(summary))
                (source / "seal.json").unlink()
                _seal(source)  # even a new internally valid seal cannot repair semantic lineage
                with self.assertRaises(ValueError):
                    order.analyze_archive(source, Path(tmp) / "derived")

    def test_partial_physical_trace_remains_partial_in_the_full_target(self):
        selected = [c for c in self.selected if c["provenance"]["position_rotation"] == 0]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write_source(source, selected, self.digest, fail_statuses=("timeout",), prefix=1)
            report = order.analyze_archive(source, Path(tmp) / "derived")
        observed = report["source_observations"]
        self.assertEqual(observed["source_completion_status"], "incomplete")
        self.assertEqual(observed["target_physical_observed"], 1)
        self.assertEqual(observed["target_physical_unobserved"], 919)
        self.assertEqual(report["choice_scores"]["answerability"]["counts_by_status"]["missing"], 512)
        self.assertEqual(report["choice_scores"]["answerability"]["accuracy_over_all"], 0)

    def test_source_native_metadata_identity_is_linked_and_runtime_changes_fail(self):
        selected = [c for c in self.selected if c["provenance"]["position_rotation"] == 0]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write_source(source, selected, self.digest, prefix=1)
            files, manifest, summary = native_identity_fixture(source)
        identity = order._source_identity(files, manifest, summary)
        self.assertEqual(identity["adapter"], "systemone_local")
        self.assertEqual(identity["model_repo_id"], "fixture/model")
        self.assertFalse(identity["live_runtime_checked_by_this_command"])
        self.assertNotEqual(identity["source_profile_bytes_sha256"], identity["archived_profile_bytes_sha256"])
        for variant in ("missing_runtime", "changed_model_hash", "changed_runtime_hash", "changed_code_hash"):
            with self.subTest(variant=variant):
                changed_files, changed_manifest, changed_summary = deepcopy((files, manifest, summary))
                initial = json.loads(changed_files["adapter-initial.json"])
                if variant == "missing_runtime":
                    del initial["identity"]["runtime"]
                    changed_summary.update(adapter_initial=deepcopy(initial), adapter_final=deepcopy(initial))
                    changed_files["adapter-initial.json"] = _encode(initial)
                elif variant == "changed_code_hash":
                    changed_manifest["bench"]["files"]["systemone_local.py"] = "0" * 64
                    changed_manifest["bench"]["sha256"] = _hash(_encode(changed_manifest["bench"]["files"]))
                else:
                    key = "model" if variant == "changed_model_hash" else "runtime"
                    changed_summary["adapter_final"]["identity"][key]["sha256"] = "0" * 64
                with self.assertRaises(ValueError):
                    order._source_identity(changed_files, changed_manifest, changed_summary)

    def test_d3_metadata_requires_adapter_hash_and_matching_complete_runtime_pins(self):
        from deposium_bench.d3_adapter import RUNTIME_NAMES
        selected = [c for c in self.selected if c["provenance"]["position_rotation"] == 0]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write_source(source, selected, self.digest, prefix=1)
            files, manifest, summary = native_identity_fixture(source)
        profile = json.loads((ROOT / "profiles/d3-lite-cpu-context.json").read_text())
        pins = {name: "1.2.3" for name in RUNTIME_NAMES}
        initial = {"adapter": "d3", "qualification": "model_isolated", "available": True,
            "capabilities": ["bench.context-choice"], "model": deepcopy(profile["model"]),
            "model_revision": profile["revision"], "model_repo_id": profile["model"]["repo_id"],
            "identity_sha256": _hash(b"synthetic D3 metadata, no inference"),
            "profile_sha256": _hash(_encode(profile)), "runtime_pins": pins, "runtime": deepcopy(pins),
            "device": "cpu", "backbone_dtype": "bfloat16", "readout_dtype": "float32",
            "adapter_sha256": manifest["bench"]["files"]["d3_adapter.py"],
            "choice_protocol_sha256": manifest["bench"]["files"]["choice_protocol.py"]}
        for name in ("worker_sha256", "model_assets_sha256", "assets_manifest_sha256", "runtime_python_sha256",
                     "runtime_lock_sha256", "prompt_sha256"):
            initial[name] = _hash(("synthetic " + name).encode())
        files["profile.json"], files["adapter-initial.json"] = _encode(profile), _encode(initial)
        summary.update(adapter_initial=deepcopy(initial), adapter_final=deepcopy(initial))
        manifest.pop("execution_scope")
        manifest.pop("native_supervision")
        result = order._source_identity(files, manifest, summary)
        self.assertEqual(result["adapter"], "d3")
        for variant in ("missing_adapter_hash", "runtime_pin_mismatch", "incomplete_runtime_pins"):
            with self.subTest(variant=variant):
                changed_files, changed_manifest, changed_summary = deepcopy((files, manifest, summary))
                changed = json.loads(changed_files["adapter-initial.json"])
                if variant == "missing_adapter_hash":
                    del changed["adapter_sha256"]
                    del changed_manifest["bench"]["files"]["d3_adapter.py"]
                    changed_manifest["bench"]["sha256"] = _hash(_encode(changed_manifest["bench"]["files"]))
                elif variant == "runtime_pin_mismatch":
                    changed["runtime"]["torch"] = "9.9.9"
                else:
                    del changed["runtime_pins"]["torch"]
                changed_files["adapter-initial.json"] = _encode(changed)
                changed_summary.update(adapter_initial=deepcopy(changed), adapter_final=deepcopy(changed))
                with self.assertRaises(ValueError):
                    order._source_identity(changed_files, changed_manifest, changed_summary)

    def test_archive_requires_full_source_provenance_and_exact_dataset_manifest(self):
        selected = [c for c in self.selected if c["provenance"]["position_rotation"] == 0]
        for variant in ("profile.json", "adapter-initial.json", "dataset-manifest.json", "bench"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / "source"
                write_source(source, selected, self.digest, prefix=1)
                if variant in {"profile.json", "adapter-initial.json"}:
                    (source / variant).unlink()
                else:
                    path = source / ("manifest.json" if variant == "bench" else variant)
                    value = json.loads(path.read_text())
                    if variant == "bench":
                        del value["bench"]
                    else:
                        value["review"] = "invented-review-state"
                    path.write_bytes(_encode(value))
                (source / "seal.json").unlink()
                _seal(source)
                with self.assertRaises(ValueError):
                    order.analyze_archive(source, Path(tmp) / "derived")

    def test_seal_change_after_shared_verification_is_rejected_before_output(self):
        selected = [c for c in self.selected if c["provenance"]["position_rotation"] == 0]
        with tempfile.TemporaryDirectory() as tmp:
            source, destination = Path(tmp) / "source", Path(tmp) / "derived"
            write_source(source, selected, self.digest, prefix=1)
            verified = order._verified_files

            def swap(*args, **kwargs):
                result = verified(*args, **kwargs)
                (source / "seal.json").write_bytes(b"{}\n")
                return result

            with patch.object(order, "_verified_files", side_effect=swap), self.assertRaisesRegex(ValueError, "seal changed"):
                order.analyze_archive(source, destination)
            self.assertFalse(destination.exists())

    def test_special_seal_is_rejected_before_reading_payload(self):
        for variant in ("symlink", "fifo"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / "source"
                source.mkdir()
                seal = source / "seal.json"
                if variant == "symlink":
                    target = Path(tmp) / "target"
                    target.write_text("{}")
                    seal.symlink_to(target)
                else:
                    os.mkfifo(seal)
                with patch.object(Path, "read_bytes", side_effect=AssertionError("special seal must not be read")), \
                        self.assertRaisesRegex(ValueError, "regular file"):
                    order.analyze_archive(source, Path(tmp) / "derived")

    def test_plan_cli_is_read_only_and_returns_the_frozen_plan(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(order.main(["plan"]), 0)
        self.assertEqual(json.loads(stdout.getvalue()), self.plan)


if __name__ == "__main__":
    unittest.main()
