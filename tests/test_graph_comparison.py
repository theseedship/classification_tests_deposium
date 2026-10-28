"""Offline graph contract tests; services and snapshots are mocked only here."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import graph_comparison as graph


def _put(root: dict, path: list[str | int], value: object) -> None:
    cursor: dict | list = root
    for index, key in enumerate(path):
        last = index == len(path) - 1
        if isinstance(cursor, list):
            while len(cursor) <= key:
                cursor.append(None)
            if last:
                cursor[key] = deepcopy(value)
            else:
                if cursor[key] is None:
                    cursor[key] = [] if type(path[index + 1]) is int else {}
                cursor = cursor[key]
        else:
            if last:
                cursor[key] = deepcopy(value)
            else:
                cursor = cursor.setdefault(key, [] if type(path[index + 1]) is int else {})


class GraphComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture, self.raw_fixture = graph.load_controls()
        self.controls = {row["case_id"]: row for row in self.fixture["controls"]}

    def _mocks(self):
        invocations: list[tuple[str, str]] = []
        snapshots: list[tuple[str, str, tuple[str, ...]]] = []

        def snapshot(_root: Path, revision: str, destination: Path, *, extra_sources=()):
            snapshots.append((destination.name, revision, extra_sources))
            return {"revision": revision, "source_kind": "synthetic_test_snapshot",
                    "files_sha256": {"synthetic-source": destination.name},
                    "application_worktree_executed": False}

        def native(request: dict, snapshot_dir: Path, _bridge: Path) -> dict:
            arm = snapshot_dir.name
            invocations.append((request["case_id"], arm))
            response = {"status": "ok", "case_id": request["case_id"],
                        "runtime": {"engine": "synthetic-test", "arm": arm},
                        "network_attempts": 0,
                        "source_files_sha256": {"synthetic-source": arm}}
            for assertion in self.controls[request["case_id"]]["expected_" + arm]:
                _put(response, assertion["path"], assertion["equals"])
            return response

        return snapshot, native, snapshots, invocations

    def test_fixture_has_nonempty_distinct_oracles_and_scoped_entrypoints(self) -> None:
        self.assertGreater(len(self.controls), 0)
        self.assertEqual(len(self.controls), len(self.fixture["controls"]))
        self.assertEqual({c["entrypoint"] for c in self.fixture["controls"]},
                         {"helper", "legacy_service", "strict_service"})
        for control in self.fixture["controls"]:
            for arm in ("before", "after"):
                self.assertTrue(control["expected_" + arm], control["case_id"])
                self.assertTrue(any(row["path"] == ["outcome"] for row in control["expected_" + arm]),
                                control["case_id"])

    def test_empty_wrong_missing_and_bool_for_number_do_not_pass(self) -> None:
        expected = [{"path": ["outcome"], "equals": "ok"},
                    {"path": ["output", "hop_count"], "equals": 2}]
        for response in ({}, {"status": "ok"},
                         {"status": "ok", "outcome": "ok", "output": {}},
                         {"status": "ok", "outcome": "ok", "output": {"hop_count": 3}},
                         {"status": "ok", "outcome": "ok", "output": {"hop_count": True}},
                         {"status": "error", "outcome": "ok", "output": {"hop_count": 2}}):
            with self.subTest(response=response):
                self.assertFalse(graph.contract_check(expected, response)["passed"])
        self.assertTrue(graph.contract_check(expected, {"status": "ok", "outcome": "ok",
                                                        "output": {"hop_count": 2}})["passed"])
        for oracle in ([], None, {}, [{"path": [], "equals": "ok"}],
                       [{"path": ["output", True], "equals": 2}]):
            with self.subTest(oracle=oracle), self.assertRaises(ValueError):
                graph.contract_check(oracle, {"status": "ok"})

    def test_fixture_refuses_missing_empty_or_duplicate_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "controls.json"
            for change in ("missing_oracle", "empty_oracle", "duplicate_case"):
                fixture = deepcopy(self.fixture)
                if change == "missing_oracle":
                    del fixture["controls"][0]["expected_after"]
                elif change == "empty_oracle":
                    fixture["controls"][0]["expected_before"] = []
                else:
                    fixture["controls"][1]["case_id"] = fixture["controls"][0]["case_id"]
                path.write_text(json.dumps(fixture), encoding="utf-8")
                with self.subTest(change=change), self.assertRaises(ValueError):
                    graph.load_controls(path)

    def test_control_request_excludes_references_and_copies_fixture(self) -> None:
        original = deepcopy(self.fixture["controls"][0])
        request = graph.control_request(original, self.fixture["fixture"])
        self.assertEqual(set(request), set(graph.REQUEST_FIELDS) | {"fixture"})
        self.assertEqual(set(request["fixture"]), {"grants", "folders", "entities", "relations"})
        self.assertNotIn("expected_before", json.dumps(request))
        self.assertNotIn("expected_after", json.dumps(request))
        original["expected_after"] = [{"path": ["outcome"], "equals": "SECRET_GOLD"}]
        self.assertEqual(request, graph.control_request(original, self.fixture["fixture"]))
        request["fixture"]["entities"].clear()
        self.assertTrue(self.fixture["fixture"]["entities"])

    def test_reference_cannot_enter_request_through_fixture_override(self) -> None:
        control = deepcopy(self.fixture["controls"][0])
        control["fixture_overrides"] = {"reference": "SECRET_GOLD"}
        with self.assertRaises(ValueError):
            graph.control_request(control, self.fixture["fixture"])

    def test_mocked_comparison_archives_both_arms_and_alternates_order(self) -> None:
        snapshot, native, snapshots, invocations = self._mocks()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "app"
            app.mkdir()
            output = root / "comparison"
            with patch.object(graph, "_snapshot", side_effect=snapshot), patch.object(graph, "_native", side_effect=native):
                summary = graph.compare_graph_contracts(app, output, repetitions=2)
            self.assertEqual(summary["completion_status"], "complete")
            self.assertEqual(summary["comparison_kind"], "before_after_805")
            self.assertEqual(summary["revisions"], {"before": graph.BEFORE, "after": graph.AFTER})
            self.assertEqual(summary["observed_executions"], len(self.controls) * 4)
            self.assertEqual(summary["expected_executions"], len(self.controls) * 4)
            self.assertEqual(summary["arms"]["before"]["contract_checks_passed"], len(self.controls) * 2)
            self.assertEqual(summary["arms"]["after"]["contract_checks_passed"], len(self.controls) * 2)
            for arm in ("before", "after"):
                self.assertEqual(sum(summary["arms"][arm]["result_classes"].values()),
                                 summary["arms"][arm]["executed"])
            self.assertGreater(summary["arms"]["after"]["result_classes"].get("ok_zero_edges", 0), 0)
            self.assertGreater(summary["arms"]["before"]["result_classes"].get("not_implemented", 0), 0)
            self.assertGreater(summary["arms"]["before"]["result_classes"].get("error", 0), 0)
            self.assertGreater(summary["arms"]["after"]["result_classes"].get("ambiguous", 0), 0)
            self.assertEqual(summary["documentary_cases_scored"], 0)
            self.assertEqual(summary["product_candidate_status"], "not_implemented")
            self.assertEqual(summary["live_service_status"], "not_observed")
            self.assertEqual(snapshots, [("before", graph.BEFORE, graph.GRAPH_SOURCES),
                                         ("after", graph.AFTER, graph.GRAPH_SOURCES)])
            first = self.fixture["controls"][0]["case_id"]
            second = self.fixture["controls"][1]["case_id"]
            self.assertEqual(invocations[:4], [(first, "before"), (first, "after"),
                                               (second, "after"), (second, "before")])
            self.assertEqual(invocations[len(self.controls) * 2:len(self.controls) * 2 + 2],
                             [(first, "after"), (first, "before")])
            rows = [json.loads(line) for line in (output / "raw.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), len(invocations))
            self.assertTrue(all(row["contract_check"]["passed"] for row in rows))
            self.assertTrue(all(not row["documentary_scored"] and not row["response_quality_scored"] for row in rows))
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["sources"]["before"]["revision"], graph.BEFORE)
            self.assertEqual(manifest["sources"]["after"]["revision"], graph.AFTER)
            self.assertEqual(manifest["comparison_kind"], summary["comparison_kind"])
            self.assertEqual(manifest["revisions"], summary["revisions"])
            self.assertIn("bridges/graph-service-compare.mjs", manifest["bench_files_sha256"])
            seal = json.loads((output / "seal.json").read_text())
            for filename, expected in seal["files"].items():
                self.assertEqual(sha256((output / filename).read_bytes()).hexdigest(), expected)
            before_bytes = {name: (output / name).read_bytes() for name in seal["files"]}
            with patch.object(graph, "_snapshot") as snapshot_again, self.assertRaises(FileExistsError):
                graph.compare_graph_contracts(app, output)
            snapshot_again.assert_not_called()
            self.assertEqual(before_bytes, {name: (output / name).read_bytes() for name in seal["files"]})

    def test_provenance_mismatch_is_archived_as_failure(self) -> None:
        snapshot, native, _, _ = self._mocks()

        def wrong_source(request, snapshot_dir, bridge):
            response = native(request, snapshot_dir, bridge)
            if snapshot_dir.name == "after":
                response["source_files_sha256"] = {"synthetic-source": "wrong"}
            return response

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "app"
            app.mkdir()
            output = root / "comparison"
            with patch.object(graph, "_snapshot", side_effect=snapshot), patch.object(graph, "_native", side_effect=wrong_source):
                summary = graph.compare_graph_contracts(app, output)
            self.assertEqual(summary["arms"]["after"]["contract_checks_passed"], 0)
            self.assertEqual(summary["completion_status"], "incomplete")
            self.assertEqual(summary["stop_reason"], "provenance_mismatch")
            self.assertGreater(summary["arms"]["after"]["missing"], 0)
            rows = [json.loads(line) for line in (output / "raw.jsonl").read_text().splitlines()]
            rejected = [row for row in rows if row["arm"] == "after"]
            self.assertEqual(len(rejected), 1)
            response = rejected[0]["response"]
            self.assertEqual((response["status"], response["error"]), ("error", "graph_provenance_changed"))
            # The rejected bridge output stays in the archive instead of being replaced.
            self.assertEqual(response["raw_response"]["source_files_sha256"], {"synthetic-source": "wrong"})
            self.assertTrue(all(not row["contract_check"]["passed"] for row in rejected))

    def test_wall_budget_retains_partial_archive_and_denominator(self) -> None:
        snapshot, native, _, _ = self._mocks()
        clock = [0.0]

        def monotonic():
            clock[0] += 0.3
            return clock[0]

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "app"
            app.mkdir()
            output = root / "comparison"
            with patch.object(graph, "_snapshot", side_effect=snapshot), patch.object(graph, "_native", side_effect=native), \
                    patch.object(graph.time, "monotonic", side_effect=monotonic):
                summary = graph.compare_graph_contracts(app, output, max_seconds=1)
            self.assertEqual(summary["completion_status"], "incomplete")
            self.assertEqual(summary["stop_reason"], "wall_budget")
            self.assertGreater(summary["expected_executions"], summary["observed_executions"])
            self.assertEqual(sum(arm["missing"] for arm in summary["arms"].values()),
                             summary["expected_executions"] - summary["observed_executions"])
            self.assertEqual(len((output / "raw.jsonl").read_text().splitlines()), summary["observed_executions"])
            self.assertTrue((output / "seal.json").is_file())

    def test_refuses_output_in_application_before_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "app"
            app.mkdir()
            with patch.object(graph, "_snapshot") as snapshot, self.assertRaisesRegex(ValueError, "inside application"):
                graph.compare_graph_contracts(app, app / "unsafe")
            snapshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
