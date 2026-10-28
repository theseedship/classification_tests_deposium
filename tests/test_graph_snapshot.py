"""Adversarial checks for the offline graph archive verifier."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from deposium_bench.graph_snapshot import audit_graph_snapshot


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def put(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: Path, data) -> None:
    put(path, json.dumps(data, sort_keys=True).encode())


def fixture(root: Path) -> None:
    owner = "synthetic-owner"
    folders = [str(100 + n) for n in range(9)]
    scope = {"owner_tenant_id": owner, "folder_ids": folders}
    write_json(root / "scope.private.json", scope)
    files, original_docs, rows, preflight = [], [], [], []
    for index, folder in enumerate(folders):
        doc = f"synthetic-document-{index}"
        pdf_path = f"originals/{doc}.pdf"
        text_path = f"originals/{doc}-1.txt"
        pdf = b"%PDF synthetic fixture\n"
        text = f"Synthetic text page {index}.\n".encode()
        put(root / pdf_path, pdf)
        put(root / text_path, text)
        files.append({"document_id": doc, "bucket_path": f"{owner}/{folder}", "user_id": owner,
                      "active": True, "mime_type": "application/pdf", "num_pages": 1, "id": index + 1})
        original_docs.append({"doc_id": doc, "folder_id": folder, "path": pdf_path, "sha256": sha(pdf),
                              "pages": [{"number": 1, "path": text_path, "sha256": sha(text)}],
                              "page_completeness_observed": {"metadata_pages": 1, "pdfinfo_pages": 1,
                                                             "extracted_pages": 1, "status": "all_pages_extracted"}})
        rows.extend([
            {"kind": "entities", "row": {"entity_id": f"e-{index}", "tenant_id": owner,
                                          "space_id": folder, "file_id": index + 1,
                                          "properties": {"doc_id": doc, "source_pages": [1]}}},
            {"kind": "relations", "row": {"relation_id": f"r-{index}", "tenant_id": owner,
                                           "space_id": folder, "file_id": index + 1,
                                           "properties": {"doc_id": doc, "source_pages": [1]}}},
            {"kind": "pages", "row": {"doc_id": f"{doc}_page_1", "tenant_id": owner,
                                       "space_id": folder, "metadata": {"page_number": 1}, "content": "indexed"}},
            {"kind": "pages", "row": {"doc_id": f"{doc}_fulltext_0", "tenant_id": owner,
                                       "space_id": folder, "metadata": {"page_number": 0}, "content": "chunk"}},
        ])
        preflight.append({"scope_id": folder, "is_total": False, "node_rows": "1",
                          "distinct_entity_ids": "1", "relation_rows": "1", "distinct_relation_ids": "1",
                          "enriched_page_rows": "0", "embeddings_page_rows": "2",
                          "distinct_page_document_keys": "2",
                          "nodes_with_doc_id": "1", "nodes_with_source_pages": "1",
                          "nodes_with_first_positive_page": "1", "relations_with_doc_id": "1",
                          "relations_with_source_pages": "1", "relations_with_first_positive_page": "1",
                          "relations_with_candidate_page_link": "1"})
    preflight.append({"scope_id": "__TOTAL__", "is_total": True, "node_rows": "9",
                      "distinct_entity_ids": "9", "relation_rows": "9", "distinct_relation_ids": "9",
                      "enriched_page_rows": "0", "embeddings_page_rows": "18",
                      "distinct_page_document_keys": "18",
                      "nodes_with_doc_id": "9", "nodes_with_source_pages": "9",
                      "nodes_with_first_positive_page": "9", "relations_with_doc_id": "9",
                      "relations_with_source_pages": "9", "relations_with_first_positive_page": "9",
                      "relations_with_candidate_page_link": "9"})
    write_json(root / "files.private.json", files)
    original = {"source_files_sha256": sha((root / "files.private.json").read_bytes()),
                "source_scope_sha256": sha((root / "scope.private.json").read_bytes()),
                "collection": {"document_count": 9, "page_count": 9, "empty_text_page_count": 0},
                "documents": original_docs}
    write_json(root / "original-documents.private.json", original)
    (root / "snapshot.private.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    for stem, data in (("preflight-capture", preflight), ("schema-capture", [{"table_name": "t"}]),
                       ("snapshot-capture", [{"kind": row["kind"],
                                                     "row_json": json.dumps(row["row"])} for row in rows])):
        sql = "SELECT synthetic_fixture"
        (root / f"{stem}.sql").write_text(sql)
        write_json(root / f"{stem}.payload.private.json",
                   [{"success": True, "query": sql, "rowCount": len(data), "data": data}])


class GraphSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        fixture(self.root)

    def test_archive_consistent_but_quality_unmeasured(self):
        result = audit_graph_snapshot(self.root)
        self.assertEqual(result["status"], "archive_consistent")
        self.assertEqual(result["quality_status"], "not_run")
        self.assertEqual(result["snapshot"]["indexed_pdf_pages"], 9)
        self.assertEqual(result["snapshot"]["fulltext_chunks"], 9)
        self.assertEqual(result["snapshot"]["graph_source_page_links_to_extracted_text"],
                         {"entities": 9, "relations": 9})

    def test_out_of_scope_row_fails_even_if_payload_agrees(self):
        path = self.root / "snapshot.private.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]["row"]["tenant_id"] = "another-owner"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        payload = self.root / "snapshot-capture.payload.private.json"
        captured = json.loads(payload.read_text())
        captured[0]["data"][0]["row_json"] = json.dumps(rows[0]["row"])
        write_json(payload, captured)
        self.assertIn("snapshot_row_outside_scope", audit_graph_snapshot(self.root)["issues"])

    def test_missing_indexed_pdf_page_fails(self):
        path = self.root / "snapshot.private.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows = [row for row in rows if row["row"].get("doc_id") != "synthetic-document-0_page_1"]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        result = audit_graph_snapshot(self.root)
        self.assertIn("indexed_pdf_page_set_mismatch", result["issues"])
        self.assertIn("preflight_total_mismatch", result["issues"])

    def test_modified_extracted_text_fails_hash(self):
        (self.root / "originals/synthetic-document-0-1.txt").write_text("changed")
        self.assertIn("original_page_hash_mismatch", audit_graph_snapshot(self.root)["issues"])

    def test_json_encoded_properties_and_metadata_are_checked(self):
        path = self.root / "snapshot.private.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]["row"]["properties"]["source_pages"] = "[1]"
        rows[0]["row"]["properties"] = json.dumps(rows[0]["row"]["properties"])
        rows[2]["row"]["metadata"] = json.dumps(rows[2]["row"]["metadata"])
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        payload = self.root / "snapshot-capture.payload.private.json"
        captured = json.loads(payload.read_text())
        for index in (0, 2):
            captured[0]["data"][index]["row_json"] = json.dumps(rows[index]["row"])
        write_json(payload, captured)
        self.assertEqual(audit_graph_snapshot(self.root)["issues"], {})

    def test_capture_stems_can_change(self):
        for old, new in (("preflight-capture", "preflight-other-run"),
                         ("schema-capture", "schema-other-run"),
                         ("snapshot-capture", "snapshot-other-run")):
            for suffix in (".sql", ".payload.private.json"):
                (self.root / f"{old}{suffix}").rename(self.root / f"{new}{suffix}")
        self.assertEqual(audit_graph_snapshot(self.root)["status"], "archive_consistent")

    def test_ambiguous_capture_is_incomplete_with_safe_summary(self):
        path = self.root / "preflight-capture.payload.private.json"
        (self.root / "preflight-other-run.payload.private.json").write_bytes(path.read_bytes())
        result = audit_graph_snapshot(self.root)
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("source_payload_missing_or_ambiguous", result["public_summary"]["issues"])
        self.assertNotIn("synthetic-owner", json.dumps(result["public_summary"]))

    def test_malformed_manifest_returns_generic_public_issue(self):
        (self.root / "files.private.json").write_text("{bad json")
        result = audit_graph_snapshot(self.root)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["public_summary"]["issues"], {"manifest_json_invalid": 1})

    def test_unreasonably_large_page_metadata_fails_without_allocation(self):
        files_path = self.root / "files.private.json"
        files = json.loads(files_path.read_text())
        files[0]["num_pages"] = 10**100
        write_json(files_path, files)
        original_path = self.root / "original-documents.private.json"
        original = json.loads(original_path.read_text())
        original["source_files_sha256"] = sha(files_path.read_bytes())
        write_json(original_path, original)
        result = audit_graph_snapshot(self.root)
        self.assertEqual(result["status"], "issues_found")
        self.assertIn("original_page_completeness_mismatch", result["issues"])

    def test_duplicate_snapshot_key_fails_even_when_final_value_matches(self):
        path = self.root / "snapshot.private.jsonl"
        lines = path.read_text().splitlines()
        lines[0] = lines[0].replace('"tenant_id": "synthetic-owner"',
                                    '"tenant_id": "wrong", "tenant_id": "synthetic-owner"', 1)
        path.write_text("\n".join(lines) + "\n")
        result = audit_graph_snapshot(self.root)
        self.assertIn("snapshot_line_invalid", result["issues"])


if __name__ == "__main__":
    unittest.main()
