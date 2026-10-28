from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import graph_measurement as measurement
from deposium_bench.graph_measurement import (
    GraphMeasurementError, _eligibility, _measure_opportunity, measure_graph_proposals,
)


class GraphMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.first = {"key": ("r1", "folder", 1), "doc_id": "doc", "pages": [3],
                      "source_id": "a", "target_id": "middle"}
        self.second = {"key": ("r2", "folder", 1), "doc_id": "doc", "pages": [4],
                       "source_id": "middle", "target_id": "b"}
        self.family = {"status": "resolved", "bindings": {"A": "start", "B": "end"},
                       "edges": [self.first, self.second]}

    def test_eligibility_is_fixed_by_plan_and_relation_topology(self):
        request = {"entrypoint": "helper", "input": {"operation": "neighbors",
                   "entity": "start", "entity_id": "a"}, "service": {}}
        reason, edges = _eligibility(request, self.family, {"folder"})
        self.assertEqual(reason, "eligible")
        self.assertEqual(edges, [self.first])
        request["input"]["operation"] = "search"
        self.assertEqual(_eligibility(request, self.family, {"folder"})[0],
                         "exploratory_node_search")
        request["input"]["operation"] = "path"
        request["input"]["end_entity"] = "end"
        self.assertEqual(_eligibility(request, self.family, {"folder"})[1],
                         [self.first, self.second])
        request["input"]["folder_ids"] = ["other"]
        with self.assertRaises(ValueError):
            _eligibility(request, self.family, {"folder"})
        request["input"]["folder_ids"] = []
        self.assertEqual(_eligibility(request, self.family, {"folder"})[0],
                         "reference_outside_selected_scope")

    def test_missing_page_is_never_inferred_from_capture(self):
        relations = {self.first["key"]: {"row": {"tenant_id": "tenant",
            "space_id": "folder", "file_id": 1, "relation_type": "REL",
            "source_id": "a", "target_id": "middle"},
            "properties": {"doc_id": "doc", "source_pages": [3]}}}
        documents = {"doc": {"folder_id": "folder", "pages": {3: {
            "path": "originals/page3.txt", "sha256": "x"}}, "name": "doc", "pdf": {}}}
        rendered = {"id": "r1", "type": "REL", "properties": {
            "space_id": "folder", "file_id": 1, "doc_id": "doc",
            "source_pages": None, "source_pages_status": "page_unresolved"}}
        result = _measure_opportunity(self.first, [rendered], relations, documents,
                                      "tenant", {"folder"})
        self.assertTrue(result["edge_id_exposed"])
        self.assertTrue(result["document_locator_verified"])
        self.assertFalse(result["all_proposed_pages_rendered"])
        rendered["properties"]["source_pages"] = [3]
        rendered["properties"]["source_pages_status"] = "recorded"
        self.assertTrue(_measure_opportunity(self.first, [rendered], relations,
                         documents, "tenant", {"folder"})["all_proposed_pages_rendered"])
        rendered["properties"]["file_id"] = 2
        wrong = _measure_opportunity(self.first, [rendered], relations, documents,
                                     "tenant", {"folder"})
        self.assertTrue(wrong["edge_id_exposed"])
        self.assertFalse(wrong["document_locator_verified"])

    def test_neighbor_name_needs_unique_plan_id_even_if_edge_order_changes(self):
        request = {"family_id": "G02", "entrypoint": "helper", "input": {
            "operation": "neighbors", "entity": "start"}, "service": {}}
        self.family["edges"].reverse()
        self.assertEqual(_eligibility(request, self.family, {"folder"})[0],
                         "neighbor_center_not_uniquely_resolved_by_plan")
        reason, edges = _eligibility(request, self.family, {"folder"},
                                    {("G02", "start"): {"a"}})
        self.assertEqual(reason, "eligible")
        self.assertEqual(edges, [self.first])
        self.assertEqual(_eligibility(request, self.family, {"folder"},
                         {("G02", "start"): {"a", "middle"}})[0],
                         "neighbor_center_not_uniquely_resolved_by_plan")


class GraphMeasurementArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source, self.observed = self.base / "source", self.base / "observed"
        self.source.mkdir()
        self.observed.mkdir()
        self._put(self.source / "snapshot.private.jsonl", b"snapshot\n")
        self._put(self.source / "schema.payload.private.json", b"schema\n")
        self._put(self.source / "scope.private.json", {"owner_tenant_id": "tenant",
                  "folder_ids": ["folder"]})
        self.edge = {"id": "r1", "source_id": "a", "target_id": "b",
                     "direction": "source_to_target", "passage_ids": ["p1"]}
        self.family = {"family_id": "G01", "status": "resolved",
                       "bindings": {"A": "start", "B": "end"},
                       "reference": {"edges": [self.edge], "passages": [{"id": "p1",
                           "doc_id": "doc", "page": 3}]}}
        self.packet = {"families": [self.family]}
        self._put(self.source / "packet.json", self.packet)
        self._put(self.source / "reference-proposals.private.json", self.packet)
        self._put(self.observed / "packet.private.json", self.packet)
        self.request = {"case_id": "case", "family_id": "G01", "entrypoint": "helper",
                        "input": {"operation": "path", "entity": "start", "entity_id": "a",
                                  "end_entity": "end", "end_entity_id": "b"}, "service": {}}
        self.plan = {"packet_sha256": self._hash(self.source / "packet.json"),
                     "snapshot_sha256": self._hash(self.source / "snapshot.private.jsonl"),
                     "requests": [self.request]}
        self._put(self.observed / "plan.private.json", self.plan)
        self.counts = {"entities": 0, "relations": 1, "pages": 0, "enriched": 0}
        self.descriptor = {"path": str((self.source / "snapshot.private.jsonl").resolve()),
                           "sha256": self.plan["snapshot_sha256"],
                           "schema_path": str((self.source / "schema.payload.private.json").resolve()),
                           "schema_sha256": self._hash(self.source / "schema.payload.private.json"),
                           "owner_tenant_id": "tenant", "folder_ids": ["folder"],
                           "expected_counts": self.counts}
        self.manifest = {"packet_sha256": self.plan["packet_sha256"],
                         "plan_sha256": self._hash(self.observed / "plan.private.json"),
                         "snapshot": self.descriptor, "repetitions": 1,
                         "sources": {arm: {"files_sha256": {"source.js": "a" * 64}}
                                     for arm in ("before", "after")}}
        self._put(self.observed / "manifest.private.json", self.manifest)
        self.rows = [self._row("before"), self._row("after")]
        self._raw_and_seal()
        self.audit = {"status": "archive_consistent", "files_sha256": {
            "snapshot.private.jsonl": self.plan["snapshot_sha256"],
            "schema.payload.private.json": self.descriptor["schema_sha256"]},
            "public_summary": {"snapshot_rows": self.counts}}
        self.documents = {"doc": {"folder_id": "folder", "pages": {3: {"path": "p3"}},
                                  "name": "doc", "pdf": {}}}
        self.relations = {("r1", "folder", 1): {"row": {"source_id": "a",
            "target_id": "b", "tenant_id": "tenant", "space_id": "folder",
            "file_id": 1, "relation_type": "REL"},
            "properties": {"doc_id": "doc", "source_pages": [3]}}}

    @staticmethod
    def _put(path, value):
        path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())

    @staticmethod
    def _hash(path):
        return sha256(path.read_bytes()).hexdigest()

    def _row(self, arm):
        rendered = {"id": "r1", "type": "REL", "source": "a", "target": "b",
                    "properties": {"space_id": "folder", "file_id": 1, "doc_id": "doc",
                                   "source_pages": [3], "source_pages_status": "recorded"}}
        return {"arm": arm, "case_id": "case", "family_id": "G01",
                "entrypoint": "helper", "repetition": 0, "provenance_valid": True,
                "response": {"status": "ok", "outcome": "ok", "output": {"edges": [rendered]},
                    "source_files_sha256": {"source.js": "a" * 64},
                    "document_snapshot": {"snapshot_sha256": self.descriptor["sha256"],
                        "schema_sha256": self.descriptor["schema_sha256"],
                        "expected_counts": dict(self.counts), "loaded_counts": dict(self.counts)},
                    "network_attempts": 0, "model_calls": 0}}

    def _raw_and_seal(self):
        self._put(self.observed / "raw.private.jsonl",
                  b"".join(json.dumps(row).encode() + b"\n" for row in self.rows))
        seal = {"schema_version": "deposium.graph-document-seal/v1",
                "files": {path.name: self._hash(path) for path in self.observed.iterdir()
                          if path.name != "seal.json"}}
        self._put(self.observed / "seal.json", seal)

    def _measure(self, dest="output"):
        with (patch.object(measurement, "_private", side_effect=lambda p: Path(p).resolve()),
              patch.object(measurement, "audit_snapshot", return_value=self.audit),
              patch.object(measurement, "_capture_index",
                           return_value=(self.documents, self.relations, {})),
              patch.object(measurement, "validate_plan", return_value=self.plan["requests"])):
            return measure_graph_proposals(self.source, {"run": self.observed}, self.base / dest)

    def test_resealed_raw_with_wrong_snapshot_is_rejected(self):
        self.rows[1]["response"]["document_snapshot"]["loaded_counts"]["relations"] = 0
        self._raw_and_seal()
        with self.assertRaisesRegex(GraphMeasurementError, "response provenance invalid"):
            self._measure()

    def test_zero_eligible_opportunities_are_rejected(self):
        self.request["input"] = {"operation": "search", "entity": "start"}
        self._put(self.observed / "plan.private.json", self.plan)
        self.manifest["plan_sha256"] = self._hash(self.observed / "plan.private.json")
        self._put(self.observed / "manifest.private.json", self.manifest)
        self._raw_and_seal()
        with self.assertRaisesRegex(GraphMeasurementError, "zero eligible"):
            self._measure()

    def test_integer_scope_folders_apply_to_helper_default_scope(self):
        # Real scope.private.json holds integer folder ids while captured documents use strings.
        self._put(self.source / "scope.private.json", {"owner_tenant_id": "tenant", "folder_ids": [7]})
        self.descriptor["folder_ids"] = [7]
        self._put(self.observed / "manifest.private.json", self.manifest)
        self.documents["doc"]["folder_id"] = "7"
        self.relations[("r1", "7", 1)] = self.relations.pop(("r1", "folder", 1))
        self.relations[("r1", "7", 1)]["row"]["space_id"] = "7"
        for row in self.rows:
            row["response"]["output"]["edges"][0]["properties"]["space_id"] = "7"
        self._raw_and_seal()
        arms = self._measure()["runs"]["run"]["arms"]
        for arm in ("before", "after"):
            counts = arms[arm]["G01"]["opportunity_counts"]
            self.assertEqual((counts["document_locator_verified"], counts["all_proposed_pages_rendered"]), (1, 1))

    def test_raw_rows_with_unicode_line_separators_are_read_per_json_line(self):
        # json.dumps(ensure_ascii=False) leaves U+2028/U+2029/U+0085 literal; splitlines() would cut there.
        self.rows[1]["response"]["note"] = "a\u2028b\u2029c\u0085d"
        self._put(self.observed / "raw.private.jsonl", b"".join(
            json.dumps(row, ensure_ascii=False).encode() + b"\n" for row in self.rows))
        seal = {"schema_version": "deposium.graph-document-seal/v1",
                "files": {path.name: self._hash(path) for path in self.observed.iterdir() if path.name != "seal.json"}}
        self._put(self.observed / "seal.json", seal)
        self.assertIn("runs", self._measure())

    def test_observation_seal_tamper_and_source_change_are_rejected(self):
        self._put(self.observed / "raw.private.jsonl", b"tampered\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self._measure()
        self._raw_and_seal()
        original = measurement._sealed_observation
        calls = 0

        def mutate_on_recheck(path):
            nonlocal calls
            result = original(path)
            calls += 1
            if calls == 2:
                self._put(self.source / "reference-proposals.private.json", b"changed\n")
            return result

        with patch.object(measurement, "_sealed_observation", side_effect=mutate_on_recheck):
            with self.assertRaisesRegex(GraphMeasurementError, "source changed"):
                self._measure("changed")


if __name__ == "__main__":
    unittest.main()
