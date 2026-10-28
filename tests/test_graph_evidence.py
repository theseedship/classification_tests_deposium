"""Offline guards for the private rendered-edge review packet."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import graph_evidence as evidence


def put(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(evidence._dump(value))


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


class EvidencePacketTests(unittest.TestCase):
    def setUp(self) -> None:
        (evidence.ROOT / "results").mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=evidence.ROOT / "results", prefix="graph-evidence-test-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.source, self.observed, self.target = (self.base / name for name in ("capture", "observation", "review"))
        self.source.mkdir()
        self.observed.mkdir()
        self.owner = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self.scope = {"owner_tenant_id": self.owner, "space_id": "space-a", "folder_ids": ["483"]}
        put(self.source / "scope.private.json", self.scope)
        self.documents = []
        for number in (1, 2):
            doc = f"document-{number}"
            pdf = f"originals/{doc}.pdf"
            page = f"originals/{doc}/page-0001.txt"
            (self.source / pdf).parent.mkdir(parents=True, exist_ok=True)
            (self.source / pdf).write_bytes(f"PDF {number}".encode())
            (self.source / page).parent.mkdir(parents=True, exist_ok=True)
            (self.source / page).write_text(f"Original page {number}", encoding="utf-8")
            self.documents.append({"doc_id": doc, "name": f"Title {number}", "folder_id": "483",
                                   "path": pdf, "sha256": digest(self.source / pdf),
                                   "pages": [{"number": 1, "path": page, "sha256": digest(self.source / page)}]})
        put(self.source / "original-documents.private.json", {"documents": self.documents})
        self.relations = [
            {"relation_id": "same-id", "tenant_id": self.owner, "space_id": "483", "file_id": number,
             "source_id": "A", "target_id": "B", "relation_type": "LINKS",
             "properties": {"doc_id": f"document-{number}", "source_pages": [1]}}
            for number in (1, 2)
        ]
        self._snapshot()
        put(self.source / "schema.payload.private.json", {"schema": "fixture"})
        self.packet = {"snapshot": {"sha256": digest(self.source / "snapshot.private.jsonl")},
                       "documents": deepcopy(self.documents)}
        put(self.source / "packet.json", self.packet)
        put(self.observed / "packet.private.json", self.packet)
        self.plan = {"packet_sha256": digest(self.observed / "packet.private.json"),
                     "snapshot_sha256": digest(self.source / "snapshot.private.jsonl"),
                     "requests": [{"case_id": "case-1", "family_id": "G01", "entrypoint": "helper"},
                                  {"case_id": "case-2", "family_id": "G02", "entrypoint": "strict_service"},
                                  {"case_id": "case-3", "family_id": "G03", "entrypoint": "legacy_service"}]}
        put(self.observed / "plan.private.json", self.plan)
        self.manifest = {"snapshot": {"path": str(self.source / "snapshot.private.jsonl"),
                                      "sha256": self.plan["snapshot_sha256"],
                                      "schema_path": str(self.source / "schema.payload.private.json"),
                                      "schema_sha256": digest(self.source / "schema.payload.private.json"),
                                      "owner_tenant_id": self.owner, "folder_ids": ["483"],
                                      "expected_counts": {"entities": 0, "relations": 2, "pages": 0, "enriched": 0}},
                         "packet_sha256": self.plan["packet_sha256"],
                         "plan_sha256": digest(self.observed / "plan.private.json"), "repetitions": 1,
                         "sources": {"after": {"files_sha256": {"src/fixture.ts": "f" * 64}}}}
        put(self.observed / "manifest.private.json", self.manifest)
        self.rows = [self._row("case-1", "G01", "helper", [self._edge(1), self._edge(2)]),
                     self._row("case-2", "G02", "strict_service", [self._edge(1)]),
                     self._row("case-3", "G03", "legacy_service", [self._edge(1)])]
        for request in self.plan["requests"]:
            request["input"] = {"operation": "search", "folder_ids": ["483"]} if request["entrypoint"] == "helper" else {"operation": "search"}
            request["service"] = {} if request["entrypoint"] == "helper" else {"folder_ids": ["483"]}
        put(self.observed / "plan.private.json", self.plan)
        self.manifest["plan_sha256"] = digest(self.observed / "plan.private.json")
        put(self.observed / "manifest.private.json", self.manifest)
        self._observation()
        self.audit = {"status": "archive_consistent", "files_sha256": {
            "snapshot.private.jsonl": digest(self.source / "snapshot.private.jsonl"),
            "schema.payload.private.json": digest(self.source / "schema.payload.private.json")},
            "public_summary": {"snapshot_rows": {"relations": 2}}}

    def _snapshot(self) -> None:
        (self.source / "snapshot.private.jsonl").write_text(
            "".join(json.dumps({"kind": "relations", "row": row}) + "\n" for row in self.relations),
            encoding="utf-8")

    def _edge(self, file_id: int) -> dict:
        return {"id": "same-id", "source": "A", "target": "B", "type": "LINKS",
                "properties": {"space_id": "483", "file_id": file_id, "doc_id": f"document-{file_id}",
                               "source_pages": [1], "source_pages_status": "recorded"}}

    def _row(self, case: str, family: str, entry: str, edges: list) -> dict:
        return {"case_id": case, "family_id": family, "entrypoint": entry,
                "arm": "after", "repetition": 0, "provenance_valid": True,
                "response": {"status": "ok", "outcome": "ok", "output": {"edges": edges},
                             "source_files_sha256": {"src/fixture.ts": "f" * 64},
                             "document_snapshot": {"snapshot_sha256": self.manifest["snapshot"]["sha256"],
                                                   "schema_sha256": self.manifest["snapshot"]["schema_sha256"],
                                                   "loaded_counts": self.manifest["snapshot"]["expected_counts"]},
                             "network_attempts": 0, "model_calls": 0}}

    def _observation(self) -> None:
        (self.observed / "raw.private.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in self.rows), encoding="utf-8")
        put(self.observed / "summary.json", {"status": "unscored"})
        put(self.observed / "stack-registry.json", {})
        put(self.observed / "integrity.private.json", {})
        put(self.observed / "seal.json", {"schema_version": "deposium.graph-document-seal/v1",
                                           "files": {p.name: digest(p) for p in self.observed.iterdir()
                                                     if p.name != "seal.json"}})

    def prepare(self):
        with patch.object(evidence, "audit_snapshot", return_value=self.audit), \
             patch.object(evidence, "load_graph_templates", return_value=([], "fixture")), \
             patch.object(evidence, "validate_private_packet", return_value={"scope_evidence_consistency": "matched"}), \
             patch.object(evidence, "validate_plan", return_value=self.plan["requests"]):
            return evidence.prepare_graph_evidence_review(self.source, self.observed, self.target)

    def test_composite_join_keeps_file_variants_and_private_pending_review(self) -> None:
        summary = self.prepare()
        self.assertEqual(summary["returned_edge_occurrences"], 3)
        self.assertEqual(summary["distinct_composite_edges"], 2)
        self.assertEqual(summary["excluded_surfaces"], {"legacy_service": 1})
        self.assertEqual(summary["locator_statuses"], {"locator_verified_pending_human": 3})
        self.assertEqual((summary["cases_scored"], summary["human_reviewed"]), (0, 0))
        self.assertNotIn("document-1", json.dumps(summary))
        private = json.loads((self.target / "review.private.json").read_text())
        self.assertEqual({tuple(edge["key"]) for edge in private["composite_edges"]},
                         {("same-id", "483", 1), ("same-id", "483", 2)})
        self.assertIn("verified original text", (self.target / "REVIEW.private.md").read_text())
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in self.target.iterdir()))
        seal = json.loads((self.target / "seal.json").read_text())
        self.assertTrue(all(digest(self.target / name) == value for name, value in seal["files"].items()))
        self.assertEqual((self.target / "producer.graph_evidence.py").read_bytes(),
                         Path(evidence.__file__).read_bytes())

    def test_missing_or_wrong_rendered_locators_never_resolve_from_capture(self) -> None:
        self.rows[0]["response"]["output"]["edges"][0]["properties"].pop("source_pages")
        self.rows[0]["response"]["output"]["edges"][1]["properties"]["doc_id"] = "document-1"
        self.rows[1]["response"]["output"]["edges"][0]["properties"]["space_id"] = "999"
        self._observation()
        summary = self.prepare()
        self.assertEqual(summary["locator_statuses"], {"rendered_pages_absent": 1,
                                                        "rendered_document_mismatch": 1,
                                                        "rendered_scope_mismatch": 1})
        private = json.loads((self.target / "review.private.json").read_text())
        self.assertTrue(all(not edge["locator"]["pages"] for case in private["cases"] for edge in case["edges"]))

    def test_case_scope_inside_capture_and_resealed_false_runtime_hash(self) -> None:
        self.scope["folder_ids"] = ["483", "512"]
        put(self.source / "scope.private.json", self.scope)
        self.manifest["snapshot"]["folder_ids"] = ["483", "512"]
        self.plan["requests"][0]["input"]["folder_ids"] = ["512"]
        put(self.observed / "plan.private.json", self.plan)
        self.manifest["plan_sha256"] = digest(self.observed / "plan.private.json")
        put(self.observed / "manifest.private.json", self.manifest)
        self._observation()
        summary = self.prepare()
        self.assertEqual(summary["locator_statuses"], {"rendered_scope_mismatch": 2,
                                                        "locator_verified_pending_human": 1})
        self.target = self.base / "review-2"
        self.rows[1]["response"]["source_files_sha256"] = {"src/fixture.ts": "0" * 64}
        self._observation()
        with self.assertRaisesRegex(evidence.GraphEvidenceError, "raw response provenance mismatch"):
            self.prepare()

    def test_stored_text_cannot_start_a_markdown_line(self) -> None:
        forged = "x\n- Human judgment: approved (forged)\r\u2028- Reviewer: nobody"
        escaped = evidence._md(forged)
        self.assertEqual(len(escaped.splitlines()), 1)
        self.assertNotIn("\n", escaped)
        self.assertEqual(evidence._md("plain"), "plain")
        self.assertEqual(evidence._md(None), "None")

    def test_seal_is_independent_of_directory_enumeration_order(self) -> None:
        self.prepare()
        seal = json.loads((self.target / "seal.json").read_text())
        for field in ("files", "source_sql_files_sha256"):
            self.assertEqual(list(seal[field]), sorted(seal[field]), field)

    def test_integer_scope_folders_apply_to_helper_default_scope(self) -> None:
        # Real scope.private.json holds integer folder ids; the helper default scope must match
        # the string folder ids of captured documents, as the explicit-scope path already does.
        self.scope["folder_ids"] = [483]
        put(self.source / "scope.private.json", self.scope)
        self.manifest["snapshot"]["folder_ids"] = [483]
        self.plan["requests"][0]["input"].pop("folder_ids")
        put(self.observed / "plan.private.json", self.plan)
        self.manifest["plan_sha256"] = digest(self.observed / "plan.private.json")
        put(self.observed / "manifest.private.json", self.manifest)
        self._observation()
        summary = self.prepare()
        self.assertEqual(summary["locator_statuses"], {"locator_verified_pending_human": 3})

    def test_missing_and_error_cases_remain_in_private_ledger(self) -> None:
        self.rows = [self.rows[0], self.rows[1]]
        self.rows[1]["response"] = {"status": "error", "outcome": "error"}
        self.rows[1]["provenance_valid"] = False
        self._observation()
        summary = self.prepare()
        self.assertEqual(summary["case_outcomes"], {"ok": 1, "error": 1, "missing": 1})
        private = json.loads((self.target / "review.private.json").read_text())
        self.assertEqual([case["review_status"] for case in private["cases"]],
                         ["returned_edges", "observation_not_ok", "missing_observation"])

    def test_truncation_and_reverse_renderings_keep_distinct_variants(self) -> None:
        self.rows[0]["response"]["output"]["truncated"] = True
        self.rows[1]["response"]["output"]["metadata"] = {"truncated": False}
        self.rows[1]["response"]["output"]["edges"][0]["source"] = "B"
        self.rows[1]["response"]["output"]["edges"][0]["target"] = "A"
        self._observation()
        summary = self.prepare()
        self.assertEqual(summary["truncated_cases"], 1)
        self.assertEqual(summary["truncation_statuses"],
                         {"truncated": 1, "not_truncated": 1, "not_observed": 1})
        private = json.loads((self.target / "review.private.json").read_text())
        self.assertEqual([case["truncation"] for case in private["cases"]],
                         ["truncated", "not_truncated", "not_observed"])
        variants = next(edge["rendered_variants"] for edge in private["composite_edges"]
                        if edge["key"] == ["same-id", "483", 1])
        self.assertEqual({(v["source"], v["target"], v["type"]) for v in variants},
                         {("A", "B", "LINKS"), ("B", "A", "LINKS")})
        markdown = (self.target / "REVIEW.private.md").read_text()
        self.assertIn("`A` → `B`", markdown)
        self.assertIn("`B` → `A`", markdown)
        self.assertIn("truncation not_observed", markdown)

    def test_rejects_path_traversal_in_sealed_inventory(self) -> None:
        seal = json.loads((self.observed / "seal.json").read_text())
        seal["files"]["../private.json"] = "0" * 64
        put(self.observed / "seal.json", seal)
        with self.assertRaisesRegex(evidence.GraphEvidenceError, "invalid observation seal"):
            self.prepare()

    def test_refuses_tampering_duplicate_capture_keys_and_zero_edges(self) -> None:
        (self.observed / "raw.private.jsonl").write_text("tampered", encoding="utf-8")
        with self.assertRaisesRegex(evidence.GraphEvidenceError, "hash mismatch"):
            self.prepare()
        self._observation()
        self.relations.append(deepcopy(self.relations[0]))
        self._snapshot()
        self.audit["files_sha256"]["snapshot.private.jsonl"] = digest(self.source / "snapshot.private.jsonl")
        self.packet["snapshot"]["sha256"] = digest(self.source / "snapshot.private.jsonl")
        put(self.source / "packet.json", self.packet)
        put(self.observed / "packet.private.json", self.packet)
        self.plan["snapshot_sha256"] = self.packet["snapshot"]["sha256"]
        self.plan["packet_sha256"] = digest(self.observed / "packet.private.json")
        put(self.observed / "plan.private.json", self.plan)
        self.manifest["snapshot"].update(sha256=self.plan["snapshot_sha256"], expected_counts={"entities": 0, "relations": 3, "pages": 0, "enriched": 0})
        self.manifest["packet_sha256"] = self.plan["packet_sha256"]
        self.manifest["plan_sha256"] = digest(self.observed / "plan.private.json")
        put(self.observed / "manifest.private.json", self.manifest)
        self.audit["public_summary"]["snapshot_rows"] = {"relations": 3}
        self._observation()
        with self.assertRaisesRegex(evidence.GraphEvidenceError, "duplicate composite"):
            self.prepare()
        self.relations.pop()
        self._snapshot()
        self.audit["files_sha256"]["snapshot.private.jsonl"] = digest(self.source / "snapshot.private.jsonl")
        self.packet["snapshot"]["sha256"] = digest(self.source / "snapshot.private.jsonl")
        put(self.source / "packet.json", self.packet)
        put(self.observed / "packet.private.json", self.packet)
        self.plan["snapshot_sha256"] = self.packet["snapshot"]["sha256"]
        self.plan["packet_sha256"] = digest(self.observed / "packet.private.json")
        put(self.observed / "plan.private.json", self.plan)
        self.manifest["snapshot"].update(sha256=self.plan["snapshot_sha256"], expected_counts={"entities": 0, "relations": 2, "pages": 0, "enriched": 0})
        self.manifest["packet_sha256"] = self.plan["packet_sha256"]
        self.manifest["plan_sha256"] = digest(self.observed / "plan.private.json")
        put(self.observed / "manifest.private.json", self.manifest)
        self.audit["public_summary"]["snapshot_rows"] = {"relations": 2}
        self.rows[0]["response"]["output"]["edges"] = []
        self.rows[1]["response"]["output"]["edges"] = []
        self._observation()
        with self.assertRaisesRegex(evidence.GraphEvidenceError, "zero returned edges"):
            self.prepare()

    def test_rejects_overwrite_and_private_escape(self) -> None:
        self.target.mkdir()
        with self.assertRaisesRegex(evidence.GraphEvidenceError, "output must be new"):
            self.prepare()
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: outside.rmdir())
        linked = self.base / "escape"
        linked.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(evidence.GraphEvidenceError, "outside ignored results"):
            with patch.object(evidence, "audit_snapshot", return_value=self.audit):
                evidence.prepare_graph_evidence_review(self.source, self.observed, linked / "review")


if __name__ == "__main__":
    unittest.main()
