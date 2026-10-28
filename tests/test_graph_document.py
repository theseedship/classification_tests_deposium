"""Offline boundary tests; no private corpus or MCPs dependency required."""
from copy import deepcopy
import json
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import graph_document as graph


class GraphDocumentTests(unittest.TestCase):
    def setUp(self):
        self.scope = {"owner_tenant_id": "tenant", "space_id": "space", "folder_ids": ["1", "2"]}
        self.packet = {"snapshot": {"sha256": "a" * 64}, "families": [{"family_id": "G01", "status": "resolved"}]}
        self.plan = {"schema_version": "deposium.graph-document-plan/v1", "snapshot_sha256": "a" * 64,
                     "packet_sha256": "b" * 64, "requests": [{"case_id": "G01-name", "family_id": "G01",
                     "endpoint_mode": "name", "entrypoint": "helper", "input": {"operation": "search", "entity": "Alpha"},
                     "context": {"tenant_id": "tenant", "space_ids": ["space"]}, "service": {}}]}

    def valid(self, plan=None):
        return graph.validate_plan(self.plan if plan is None else plan, self.packet, "b" * 64, self.scope)

    def test_annotations_scope_mutation_and_empty_requests_rejected(self):
        self.assertEqual(len(self.valid()), 1)
        for change in ("annotation", "scope", "duplicate", "empty", "hash", "unresolved", "budget", "route"):
            plan = deepcopy(self.plan)
            row = plan["requests"][0]
            if change == "annotation": row["input"]["expected"] = "secret truth"
            elif change == "scope": row["context"]["tenant_id"] = "other"
            elif change == "duplicate": plan["requests"].append(deepcopy(row))
            elif change == "empty": plan["requests"] = []
            elif change == "hash": plan["snapshot_sha256"] = "c" * 64
            elif change == "unresolved": row["family_id"] = "G05"
            elif change == "budget": row["input"]["max_hops"] = 50
            else: row["input"]["entity_id"] = "an-id"
            with self.subTest(change=change), self.assertRaises(ValueError): self.valid(plan)

    def test_service_scope_subset_is_explicit_and_cannot_escape(self):
        row = self.plan["requests"][0]
        row["entrypoint"] = "strict_service"
        row["service"] = {"graph_name": "entity_graph_tenant_2", "folder_ids": ["2"]}
        self.valid()
        for key, value in (("folder_ids", ["3"]), ("owner_tenant_id", "other"), ("graph_name", "entity_graph_other_2")):
            plan = deepcopy(self.plan)
            plan["requests"][0]["service"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.valid(plan)

    def test_helper_selection_is_explicit_and_candidate_cannot_relabel_history(self):
        self.plan["requests"][0]["input"]["folder_ids"] = ["2"]
        self.valid()
        for folders in ([], ["3"], ["1", "3"], ["2", "2"], [2]):
            plan = deepcopy(self.plan)
            plan["requests"][0]["input"]["folder_ids"] = folders
            with self.subTest(folders=folders), self.assertRaises(ValueError): self.valid(plan)
        for candidate in ("main", graph.AFTER, "x" * 40):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                graph.observe_graph_documents("unused", "unused", "unused", "unused", candidate_revision=candidate)

    def test_native_service_cannot_pretend_to_resolve_a_name(self):
        row = self.plan["requests"][0]
        row["entrypoint"] = "legacy_service"
        row["input"] = {"operation": "path", "entity": "Alpha", "end_entity": "Beta"}
        row["service"] = {"graph_name": "entity_graph_tenant_1", "folder_ids": ["1"], "source_id": "a", "target_id": "b"}
        with self.assertRaises(ValueError): self.valid()
        row["endpoint_mode"] = "id"
        row["input"].update(entity_id="a", end_entity_id="b")
        self.valid()
        row["input"]["entity_id"] = "wrong"
        with self.assertRaises(ValueError): self.valid()

    def test_candidate_requires_real_git_ancestry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def git(*args):
                return subprocess.check_output(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                                                *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()
            git("init", "-q")
            git("commit", "--allow-empty", "-qm", "older")
            older = git("rev-parse", "HEAD")
            git("commit", "--allow-empty", "-qm", "baseline")
            baseline = git("rev-parse", "HEAD")
            git("commit", "--allow-empty", "-qm", "candidate")
            candidate = git("rev-parse", "HEAD")
            git("checkout", "--orphan", "unrelated")
            git("commit", "--allow-empty", "-qm", "unrelated")
            unrelated = git("rev-parse", "HEAD")
            with patch.object(graph, "AFTER", baseline):
                graph._require_candidate_descendant(root, candidate)
                for rejected in (older, unrelated, "0" * 40):
                    with self.subTest(rejected=rejected), self.assertRaisesRegex(ValueError, "descend"):
                        graph._require_candidate_descendant(root, rejected)

    def test_no_score_from_empty_missing_error_or_transport_ok(self):
        requests = self.valid()
        empty = graph.observation_summary(requests, [], 1, None)
        self.assertEqual(empty["completion_status"], "incomplete")
        self.assertEqual(empty["arms"]["after"]["missing"], 1)
        for outcome in ("empty", "error", "not_implemented", "ambiguous", "no_path", "limit_reached"):
            rows = [{"arm": arm, "entrypoint": "helper", "family_id": "G01",
                     "response": {"status": "ok", "outcome": outcome}} for arm in ("before", "after")]
            result = graph.observation_summary(requests, rows, 1, None)
            self.assertEqual(result["documentary_cases_scored"], 0)
            self.assertEqual(result["final_answers_scored"], 0)
            self.assertEqual(result["arms"]["after"]["outcomes_by_entrypoint"]["helper"], {outcome: 1})
            self.assertEqual(result["valid_observations"], 0)
            self.assertEqual(result["completion_status"], "incomplete")
        with self.assertRaises(ValueError): graph.observation_summary([], [], 1, None)

    def test_private_paths_symlinks_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "results").mkdir()
            (root / "results/outside").symlink_to(root)
            with patch.object(graph, "ROOT", root):
                self.assertEqual(graph._private(root / "results/new"), root / "results/new")
                for path in (root / "public", root / "results/outside/file"):
                    with self.assertRaises(ValueError): graph._private(path)
            path = root / "private.json"
            graph._write(path, b"original")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError): graph._write(path, b"replacement")
            self.assertEqual(path.read_bytes(), b"original")

    def test_observation_freezes_inputs_preserves_raw_failure_and_seals(self):
        (graph.ROOT / "results").mkdir(exist_ok=True)  # git-ignored, absent in a fresh clone
        with tempfile.TemporaryDirectory(dir=graph.ROOT / "results") as temp:
            base = Path(temp)
            source = base / "capture"
            source.mkdir()
            (source / "snapshot.private.jsonl").write_bytes(b"synthetic snapshot")
            (source / "schema.payload.private.json").write_bytes(b"synthetic schema")
            self.packet["snapshot"]["sha256"] = graph.file_sha(source / "snapshot.private.jsonl")
            packet_raw = graph._dump(self.packet)
            (source / "packet.json").write_bytes(packet_raw)
            (source / "scope.private.json").write_bytes(graph._dump(self.scope))
            self.plan["snapshot_sha256"] = self.packet["snapshot"]["sha256"]
            self.plan["packet_sha256"] = graph._sha(packet_raw)
            plan = base / "plan.json"
            plan.write_bytes(graph._dump(self.plan))
            invocations = []
            def native(request, snapshot, seconds):
                invocations.append(deepcopy(request))
                self.assertNotIn("reference", json.dumps(request))
                descriptor = request["fixture"]["document_snapshot"]
                return {"status": "ok", "outcome": "error", "output": None, "runtime": {"fake": True},
                        "source_files_sha256": {}, "network_attempts": 0,
                        "document_snapshot": {"snapshot_sha256": descriptor["sha256"],
                            "schema_sha256": descriptor["schema_sha256"], "loaded_counts": descriptor["expected_counts"]}}
            audit = {"status": "archive_consistent", "public_summary": {"snapshot_rows": {"entities": 2}}}
            with patch.object(graph, "audit_snapshot", return_value=audit), \
                 patch.object(graph, "validate_private_packet", return_value={"scope_evidence_consistency": "matched"}), \
                 patch.object(graph, "_available_mib", return_value=5000), \
                 patch.object(graph, "_snapshot", return_value={"files_sha256": {}}), \
                 patch.object(graph, "_invoke", side_effect=native):
                output = base / "new"
                summary = graph.observe_graph_documents(base / "mcps", source, plan, output)
                self.assertEqual(summary["completion_status"], "complete")
                self.assertEqual(summary["observed_executions"], 2)
                self.assertEqual(summary["documentary_cases_scored"], 0)
                self.assertEqual(len(invocations), 2)
                raw = [json.loads(line) for line in (output / "raw.private.jsonl").read_text().splitlines()]
                self.assertTrue(all(row["response"]["outcome"] == "error" for row in raw))
                seal = json.loads((output / "seal.json").read_text())
                self.assertTrue(all(graph.file_sha(output / name) == value for name, value in seal["files"].items()))
                with self.assertRaises(ValueError): graph.observe_graph_documents(base / "mcps", source, plan, output)
                with patch.object(graph, "_require_candidate_descendant") as ancestry:
                    candidate = graph.observe_graph_documents(base / "mcps", source, plan, base / "candidate", candidate_revision="c" * 40)
                    ancestry.assert_called_once_with(base / "mcps", "c" * 40)
                self.assertEqual(candidate["comparison_kind"], "candidate_against_805")
                self.assertEqual(candidate["revisions"], {"before": graph.AFTER, "after": "c" * 40})
                original = json.loads((output / "summary.json").read_text())
                self.assertEqual(original["revisions"], {"before": graph.BEFORE, "after": graph.AFTER})
            self.assertEqual((source / "packet.json").read_bytes(), packet_raw)
