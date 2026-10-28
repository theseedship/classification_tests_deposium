"""Offline, synthetic checks of the documentary review boundary."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from deposium_bench.graph_review import (
    GraphReviewError, ROOT, load_graph_templates, materialize_graph_review,
    validate_private_packet,
)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def fixture(root: Path) -> dict:
    snapshot = b"synthetic snapshot for validation only\n"
    original = b"synthetic document bytes\n"
    page = "Alpha is linked to Beta. Beta is linked to Gamma in this synthetic document.\n".encode()
    (root / "snapshot.bin").write_bytes(snapshot)
    (root / "document.bin").write_bytes(original)
    (root / "page-1.txt").write_bytes(page)
    quote = "Alpha is linked to Beta"
    reference = {
        "status": "proposed", "reviewer": "synthetic-test-agent", "review_date": "2026-10-03",
        "conclusion": "A relation is proposed for later human review.",
        "entities": [{"id": "entity-a", "label": "Alpha"}, {"id": "entity-b", "label": "Beta"}],
        "edges": [{"id": "edge-ab", "source_id": "entity-a", "target_id": "entity-b",
                   "direction": "source_to_target", "passage_ids": ["passage-1"]}],
        "passages": [{"id": "passage-1", "doc_id": "doc-1", "page": 1,
                      "quote": quote, "quote_sha256": digest(quote.encode())}],
        "absence_review": None, "control_expected": None, "limits": None,
    }
    return {
        "schema_version": "deposium.graph-private-packet/v1",
        "snapshot": {"id": "synthetic-snapshot", "path": "snapshot.bin", "sha256": digest(snapshot),
                     "before_revision": "982f49d2b7ab85a6b52a91a4dac797559ebbc9df",
                     "after_revision": "eed8934ed597da12a8c79f14f872042e0658f253",
                     "scope_validation": {"status": "unverified", "method": "global_counter",
                                          "evidence_path": None, "evidence_sha256": None,
                                          "tenant_scope_sha256": None, "folder_scope_sha256": None}},
        "documents": [{"doc_id": "doc-1", "name": "Synthetic document", "folder_id": "folder-1",
                       "path": "document.bin", "sha256": digest(original),
                       "pages": [{"number": 1, "path": "page-1.txt", "sha256": digest(page)}]}],
        "families": [
            {"family_id": "G01", "split": "test", "status": "resolved",
             "bindings": {"A": "Alpha", "B": "Beta"}, "document_ids": ["doc-1"], "reference": reference},
            {"family_id": "G05", "split": "unassigned", "status": "unresolved",
             "bindings": {"A": "Alpha", "B": "Beta"}, "document_ids": ["doc-1"], "reference": None},
        ],
    }


class GraphReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.templates, self.template_sha = load_graph_templates()

    def test_public_templates_are_unresolved_and_paired(self) -> None:
        self.assertEqual(len(self.templates), 16)
        self.assertEqual(len({row["family_id"] for row in self.templates}), 8)
        self.assertTrue(all(row["reference_artifact"] is None and row["split"] == "unassigned"
                            and row["levels"]["C"] == "not_implemented" for row in self.templates))

    def test_public_manifest_fallback_keeps_private_precedence_and_hash_checks(self) -> None:
        source = ROOT / "datasets/graph-document-review-v0"
        raw = (source / "cases.review.jsonl").read_bytes()
        public_manifest = json.loads((source / "manifest.public.json").read_text())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = root / "cases.review.jsonl"
            cases.write_bytes(raw)
            public_path = root / "manifest.public.json"
            private_path = root / "manifest.review.json"
            wrong_public = deepcopy(public_manifest)
            wrong_public["cases_sha256"] = "0" * 64
            public_path.write_text(json.dumps(wrong_public))
            # Both manifests are synthetic fixtures; no private observations
            # are read or copied to exercise the local precedence contract.
            private_fixture = deepcopy(public_manifest)
            private_fixture["comparison"] = {"purpose": "Synthetic local manifest fixture."}
            private_path.write_text(json.dumps(private_fixture))
            rows, actual = load_graph_templates(cases)
            self.assertEqual(rows, self.templates)
            self.assertEqual(actual, digest(raw))

            private_path.unlink()
            with self.assertRaisesRegex(GraphReviewError, "template manifest mismatch"):
                load_graph_templates(cases)
            public_path.write_text(json.dumps(public_manifest))
            rows, actual = load_graph_templates(cases)
            self.assertEqual(rows, self.templates)
            self.assertEqual(actual, digest(raw))

            private_path.write_text(json.dumps(wrong_public))
            with self.assertRaisesRegex(GraphReviewError, "template manifest mismatch"):
                load_graph_templates(cases)
            private_path.unlink()

            # Rehashing an altered case does not bypass readiness/reference checks.
            altered = deepcopy(rows)
            altered[0]["reference_artifact"] = "synthetic-unreviewed-reference"
            altered_raw = b"".join((json.dumps(row) + "\n").encode() for row in altered)
            cases.write_bytes(altered_raw)
            public_manifest["cases_sha256"] = digest(altered_raw)
            public_path.write_text(json.dumps(public_manifest))
            with self.assertRaisesRegex(GraphReviewError, "template identity/readiness invalid"):
                load_graph_templates(cases)

    def test_partial_packet_keeps_denominator_and_no_score(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            packet = fixture(Path(temp))
            result = validate_private_packet(packet, self.templates, temp)
        self.assertEqual(result["status"], "not_ready")
        self.assertEqual(result["families_total"], 8)
        self.assertEqual(result["families_resolved"], 1)
        self.assertEqual(result["cases_total"], 16)
        self.assertEqual(result["cases_scored"], 0)
        self.assertEqual(result["product_C"], "not_implemented")
        self.assertEqual(result["scope_evidence_consistency"], "not_supplied")
        self.assertFalse(result["corpus_qualified"])

    def test_filtered_scope_evidence_must_be_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = fixture(root)
            tenant_id, folder_ids = "synthetic-tenant", ["folder-1"]
            tenant_hash = digest(tenant_id.encode())
            folder_hash = digest(json.dumps(folder_ids, separators=(",", ":")).encode())
            request = {"schema_version": "deposium.graph-filter-request/v1",
                       "method": "independent_filtered_query", "operation": "count_graph_edges_filtered",
                       "tenant_id": tenant_id, "folder_ids": folder_ids,
                       "filter_columns": ["tenant_id", "space_id"]}
            request_raw = json.dumps(request).encode()
            (root / "filter-request.json").write_bytes(request_raw)
            evidence = {"schema_version": "deposium.graph-scope-evidence/v1",
                        "method": "independent_filtered_query",
                        "filter_columns": ["tenant_id", "space_id"],
                        "tenant_id": tenant_id, "folder_ids": folder_ids,
                        "filter_request_path": "filter-request.json", "filter_request_sha256": digest(request_raw),
                        "per_folder_edge_counts": [{"folder_id": "folder-1", "edge_count": 1}],
                        "union_edge_count": 1,
                        "folders_disjoint": True}
            raw = json.dumps(evidence).encode()
            (root / "scope.json").write_bytes(raw)
            packet["snapshot"]["scope_validation"] = {
                "status": "filtered_evidence_provided", "method": "independent_filtered_query",
                "evidence_path": "scope.json", "evidence_sha256": digest(raw),
                "tenant_scope_sha256": tenant_hash, "folder_scope_sha256": folder_hash}
            result = validate_private_packet(packet, self.templates, root)
            self.assertEqual(result["scope_evidence_consistency"], "matched")
            self.assertEqual(result["scope_execution_status"], "not_verified_by_bench")
            self.assertFalse(result["corpus_qualified"])
            self.assertEqual(result["status"], "not_ready")  # seven families still unresolved
            bad = deepcopy(packet)
            bad["snapshot"]["scope_validation"]["method"] = "global_counter"
            with self.assertRaises(GraphReviewError):
                validate_private_packet(bad, self.templates, root)
            evidence["union_edge_count"] = 999_999  # Synthetic invalid count; not an operational observation.
            wrong = json.dumps(evidence).encode()
            (root / "scope.json").write_bytes(wrong)
            packet["snapshot"]["scope_validation"]["evidence_sha256"] = digest(wrong)
            with self.assertRaises(GraphReviewError):
                validate_private_packet(packet, self.templates, root)

    def test_rejects_empty_wrong_or_unverified_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = fixture(root)
            for change in ("empty_edges", "wrong_quote", "wrong_endpoint", "bad_document_hash", "bad_page_hash"):
                packet = deepcopy(base)
                ref = packet["families"][0]["reference"]
                if change == "empty_edges":
                    ref["edges"] = []
                elif change == "wrong_quote":
                    ref["passages"][0]["quote"] = "not in source page"
                    ref["passages"][0]["quote_sha256"] = digest(b"not in source page")
                elif change == "wrong_endpoint":
                    ref["edges"][0]["target_id"] = "invented-entity"
                elif change == "bad_document_hash":
                    packet["documents"][0]["sha256"] = "0" * 64
                elif change == "bad_page_hash":
                    packet["documents"][0]["pages"][0]["sha256"] = "0" * 64
                with self.subTest(change=change), self.assertRaises(GraphReviewError):
                    validate_private_packet(packet, self.templates, root)

    def test_g05_absence_requires_complete_documentary_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = fixture(root)
            item = packet["families"][1]
            item["status"] = "resolved"
            item["split"] = "test"
            ref = deepcopy(packet["families"][0]["reference"])
            ref["edges"] = []
            ref["passages"] = []
            ref["absence_review"] = {"finding": "documented_absent", "reviewed_pages": []}
            item["reference"] = ref
            with self.assertRaises(GraphReviewError):
                validate_private_packet(packet, self.templates, root)
            ref["absence_review"]["reviewed_pages"] = [{"doc_id": "doc-1", "page": 1}]
            result = validate_private_packet(packet, self.templates, root)
            self.assertEqual(result["families_resolved"], 2)
            self.assertEqual(result["status"], "not_ready")
            self.assertEqual(result["absence_completeness"], "not_verified_by_bench")

    def test_global_document_questions_cannot_use_subset_of_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = fixture(root)
            second = b"second synthetic document"
            second_page = b"Second synthetic page."
            (root / "document-2.bin").write_bytes(second)
            (root / "page-2.txt").write_bytes(second_page)
            packet["documents"].append({"doc_id": "doc-2", "name": "Second synthetic document",
                                        "folder_id": "folder-2", "path": "document-2.bin",
                                        "sha256": digest(second), "pages": [{"number": 1,
                                        "path": "page-2.txt", "sha256": digest(second_page)}]})
            for family in ("G05", "T01", "T02"):
                candidate = deepcopy(packet)
                candidate["families"] = [{"family_id": family, "split": "unassigned",
                                          "status": "unresolved", "bindings": {"A": "Alpha", "B": "Beta"}
                                          if family == "G05" else {}, "document_ids": ["doc-1"],
                                          "reference": None}]
                with self.subTest(family=family), self.assertRaises(GraphReviewError):
                    validate_private_packet(candidate, self.templates, root)
                candidate["families"][0]["document_ids"].append("doc-2")
                self.assertEqual(validate_private_packet(candidate, self.templates, root)["status"], "not_ready")

    def test_g02_binds_path_endpoints_and_preserves_traversal_direction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = fixture(root)
            item = deepcopy(packet["families"][0])
            item["family_id"] = "G02"
            item["bindings"] = {"A": "Alpha", "B": "Gamma"}
            ref = item["reference"]
            ref["entities"].append({"id": "entity-c", "label": "Gamma"})
            quote = "Beta is linked to Gamma"
            ref["passages"].append({"id": "passage-2", "doc_id": "doc-1", "page": 1,
                                    "quote": quote, "quote_sha256": digest(quote.encode())})
            ref["edges"].append({"id": "edge-bc", "source_id": "entity-b", "target_id": "entity-c",
                                 "direction": "source_to_target", "passage_ids": ["passage-2"]})
            packet["families"].append(item)
            self.assertEqual(validate_private_packet(packet, self.templates, root)["families_resolved"], 2)
            item["bindings"]["B"] = "Beta"
            with self.assertRaises(GraphReviewError):
                validate_private_packet(packet, self.templates, root)
            item["bindings"] = {"A": "Gamma", "B": "Alpha"}
            ref["edges"] = list(reversed(ref["edges"]))
            for edge in ref["edges"]:
                edge["direction"] = "target_to_source"
            self.assertEqual(validate_private_packet(packet, self.templates, root)["families_resolved"], 2)

    def test_g04_synthetic_control_is_not_a_resolved_real_case(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = fixture(root)
            packet["families"].append({"family_id": "G04", "split": "unassigned",
                                       "status": "synthetic_control",
                                       "bindings": {"ambiguous_name": "Synthetic homonym"},
                                       "document_ids": [], "reference": None})
            result = validate_private_packet(packet, self.templates, root)
            self.assertEqual(result["families_synthetic_control"], 1)
            self.assertEqual(result["families_resolved"], 1)
            self.assertEqual(result["cases_materialized"], 2)

    def test_g06_requires_bounded_non_exhaustive_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = fixture(root)
            item = deepcopy(packet["families"][0])
            item["family_id"] = "G06"
            item["bindings"] = {"dense_entity": "Alpha"}
            packet["families"].append(item)
            with self.assertRaises(GraphReviewError):
                validate_private_packet(packet, self.templates, root)
            item["reference"]["limits"] = {"max_hops": 3, "result_limit": 20,
                                            "claim_exhaustive": False}
            result = validate_private_packet(packet, self.templates, root)
            self.assertEqual(result["families_resolved"], 2)

    def test_materialization_separates_requests_from_private_reference(self) -> None:
        results = ROOT / "results"
        results.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=results) as temp:
            root = Path(temp)
            packet = fixture(root)
            source = root / "packet.json"
            source.write_text(json.dumps(packet), encoding="utf-8")
            output = root / "prepared"
            summary = materialize_graph_review(source, output)
            requests = json.loads((output / "requests.json").read_text())
            references = json.loads((output / "references.private.json").read_text())
            self.assertEqual(summary["cases_materialized"], 2)
            self.assertEqual({row["case_id"] for row in requests}, {"G01-fr", "G01-en"})
            self.assertNotIn("quote", json.dumps(requests))
            self.assertIn("quote", json.dumps(references))
            self.assertEqual((output / "packet.json").read_bytes(), source.read_bytes())
            self.assertEqual(summary["packet_sha256"], digest(source.read_bytes()))
            self.assertEqual(summary["requests_sha256"], digest((output / "requests.json").read_bytes()))
            self.assertEqual(summary["references_sha256"], digest((output / "references.private.json").read_bytes()))
            scopes = [row["candidate_input"]["scope"] for row in requests]
            self.assertEqual(scopes[0], scopes[1])
            self.assertEqual(scopes[0]["document_ids"], ["doc-1"])
            self.assertEqual(scopes[0]["document_sha256"], {"doc-1": packet["documents"][0]["sha256"]})
            self.assertEqual(scopes[0]["snapshot_sha256"], packet["snapshot"]["sha256"])
            self.assertEqual((output / "references.private.json").stat().st_mode & 0o777, 0o600)
            with self.assertRaises(GraphReviewError):
                materialize_graph_review(source, output)

    def test_binding_cannot_insert_reference_text_into_candidate_input(self) -> None:
        results = ROOT / "results"
        results.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=results) as temp:
            root = Path(temp)
            packet = fixture(root)
            packet["families"][0]["bindings"]["A"] = packet["families"][0]["reference"]["passages"][0]["quote"]
            source = root / "packet.json"
            source.write_text(json.dumps(packet), encoding="utf-8")
            with self.assertRaises(GraphReviewError):
                materialize_graph_review(source, root / "prepared")
            self.assertFalse((root / "prepared").exists())

    def test_private_paths_checked_before_read_and_sources_must_be_relative(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = fixture(root)
            packet["documents"][0]["path"] = str(root / "document.bin")
            with self.assertRaises(GraphReviewError):
                validate_private_packet(packet, self.templates, root)
        results = ROOT / "results"
        results.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=results) as temp:
            output = Path(temp) / "prepared"
            with self.assertRaisesRegex(GraphReviewError, "ignored private directory"):
                materialize_graph_review(ROOT / "README.md", output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
