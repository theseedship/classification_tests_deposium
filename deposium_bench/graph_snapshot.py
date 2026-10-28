"""Offline integrity checks for a private, scoped graph corpus archive.

This module has no database, service, PDF parser, or model dependency. It checks
the collected bytes and their internal links; it cannot qualify graph answers.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
from pathlib import Path
import re

from .adapters import _json as _strict_json


KINDS = {"entities": "entity_id", "relations": "relation_id", "pages": "doc_id", "enriched": "doc_id"}
PAGE_ID = re.compile(r"^(?P<doc>.+)_page_(?P<number>[1-9][0-9]*)$")
FULLTEXT_ID = re.compile(r"^(?P<doc>.+)_fulltext_(?P<number>0|[1-9][0-9]*)$")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def _incomplete(issues: Counter, hashes: dict) -> dict:
    public = {"status": "incomplete", "qualification": "offline_archive_consistency_only",
              "quality_status": "not_run", "documentary_cases_scored": 0,
              "issues": dict(issues), "warnings": {}}
    return {"schema_version": "deposium.graph-snapshot-integrity/v1", **public,
            "files_sha256": hashes, "public_summary": public}


def _source_paths(root: Path, family: str, issues: Counter) -> tuple[Path, Path] | None:
    matches = sorted(root.glob(f"{family}*.payload.private.json"))
    if len(matches) != 1:
        issues["source_payload_missing_or_ambiguous"] += 1
        return None
    payload = matches[0]
    stem = payload.name.removesuffix(".payload.private.json")
    sql = root / f"{stem}.sql"
    if not sql.is_file():
        issues["source_sql_missing"] += 1
        return None
    return payload, sql


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path):
    return _strict_json(path.read_bytes())


def _object(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = _strict_json(value)
        except (ValueError, TypeError):
            return None
        return decoded if isinstance(decoded, dict) else None
    return None


def _pages(value):
    if isinstance(value, str):
        try:
            value = _strict_json(value)
        except ValueError:
            value = [part.strip() for part in value.split(",")]
    if type(value) is int:
        value = [value]
    if not isinstance(value, list):
        return None
    result = []
    for item in value:
        if isinstance(item, str) and item.isdecimal():
            item = int(item)
        if type(item) is not int or item < 1:
            return None
        result.append(item)
    return result


def _source(path: Path, query_path: Path, issues: Counter):
    try:
        value = _json(path)
        if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
            raise ValueError
        result = value[0]
        if result.get("success") is not True or result.get("query") != query_path.read_text(encoding="utf-8"):
            issues["source_query_or_status_mismatch"] += 1
        if type(result.get("rowCount")) is not int or not isinstance(result.get("data"), list) or result["rowCount"] != len(result["data"]):
            issues["source_row_count_mismatch"] += 1
        return result.get("data", []) if isinstance(result.get("data"), list) else []
    except (OSError, ValueError, TypeError, KeyError):
        issues["source_payload_invalid"] += 1
        return []


def _stored_path(root: Path, relative: object, issues: Counter) -> Path | None:
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or ".." in Path(relative).parts):
        issues["original_path_invalid"] += 1
        return None
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
        issues["original_path_invalid"] += 1
        return None
    return candidate


def _count(row: dict, key: str, issues: Counter) -> int | None:
    value = row.get(key)
    if isinstance(value, str) and value.isdecimal():
        value = int(value)
    if type(value) is not int or value < 0:
        issues["preflight_count_invalid"] += 1
        return None
    return value


def audit_snapshot(root: str | Path) -> dict:
    """Check one private archive and return aggregate, identifier-free findings.

    No files are written. The caller may serialize the result under ``root``.
    A clean audit means archive consistency only, never a quality PASS.
    """
    root = Path(root)
    issues: Counter = Counter()
    warnings: Counter = Counter()
    source_paths = {family: _source_paths(root, family, issues)
                    for family in ("preflight", "schema", "snapshot")}
    names = ["scope.private.json", "files.private.json", "snapshot.private.jsonl",
             "original-documents.private.json"]
    names.extend(paths[0].name for paths in source_paths.values() if paths is not None)
    hashes = {}
    for name in names:
        path = root / name
        if not path.is_file():
            issues["archive_file_missing"] += 1
        else:
            hashes[name] = _sha(path)
    if issues:
        return _incomplete(issues, hashes)

    receipt_path = root / "collection-receipt.private.json"
    if receipt_path.is_file():
        try:
            receipt = _json(receipt_path)
        except (OSError, ValueError):
            receipt = None
            issues["receipt_invalid"] += 1
        receipt_files = receipt.get("files_sha256", {}) if isinstance(receipt, dict) else {}
        if (not isinstance(receipt, dict) or not isinstance(receipt_files, dict)
                or receipt.get("snapshot_sha256") != hashes["snapshot.private.jsonl"]):
            issues["receipt_snapshot_hash_mismatch"] += 1
        else:
            for name, expected in receipt_files.items():
                if not isinstance(name, str) or Path(name).name != name or not SHA256.fullmatch(str(expected)):
                    issues["receipt_file_entry_invalid"] += 1
                    continue
                path = root / name
                if not path.is_file() or _sha(path) != expected:
                    issues["receipt_file_hash_mismatch"] += 1
        hashes[receipt_path.name] = _sha(receipt_path)
    else:
        warnings["collection_receipt_absent"] += 1

    try:
        scope, files, originals = (_json(root / name) for name in
                                   ("scope.private.json", "files.private.json", "original-documents.private.json"))
    except (OSError, ValueError):
        issues["manifest_json_invalid"] += 1
        return _incomplete(issues, hashes)
    if not isinstance(originals, dict):
        issues["original_manifest_invalid"] += 1
        originals = {}
    owner = scope.get("owner_tenant_id") if isinstance(scope, dict) else None
    folders = [str(item) for item in scope.get("folder_ids", [])] if isinstance(scope, dict) else []
    if not isinstance(owner, str) or not owner or len(folders) != 9 or len(set(folders)) != 9:
        issues["scope_invalid"] += 1
    if not isinstance(files, list) or not files:
        issues["file_manifest_invalid"] += 1
        files = []
    by_doc = {}
    by_folder = defaultdict(set)
    for file in files:
        if not isinstance(file, dict) or not isinstance(file.get("document_id"), str):
            issues["file_manifest_invalid"] += 1
            continue
        doc = file["document_id"]
        if doc in by_doc:
            issues["duplicate_manifest_document"] += 1
        by_doc[doc] = file
        folder = str(file.get("bucket_path", "")).split("/")[-1]
        if (folder not in folders or file.get("bucket_path") != f"{owner}/{folder}"
                or file.get("user_id") != owner or file.get("active") is not True
                or file.get("mime_type") != "application/pdf"):
            issues["file_outside_scope"] += 1
        by_folder[folder].add(doc)
    if len(by_doc) != 9:
        issues["document_count_mismatch"] += 1

    original_docs = originals.get("documents", []) if isinstance(originals, dict) else []
    if not isinstance(original_docs, list):
        original_docs = []
        issues["original_manifest_invalid"] += 1
    for label, name in (("source_files_sha256", "files.private.json"),
                        ("source_scope_sha256", "scope.private.json")):
        if originals.get(label) != hashes[name]:
            issues["original_source_hash_mismatch"] += 1
    actual_pages = set()
    empty_original_pages = 0
    verified_pdfs = verified_text_pages = 0
    seen_original_docs = set()
    for document in original_docs:
        if not isinstance(document, dict):
            issues["original_manifest_invalid"] += 1
            continue
        doc = document.get("doc_id")
        file = by_doc.get(doc)
        if doc in seen_original_docs:
            issues["duplicate_original_document"] += 1
        seen_original_docs.add(doc)
        if file is None or document.get("folder_id") != str(file.get("bucket_path", "")).split("/")[-1]:
            issues["original_document_scope_mismatch"] += 1
        pdf = _stored_path(root, document.get("path"), issues)
        if pdf is not None:
            if document.get("sha256") != _sha(pdf) or not SHA256.fullmatch(str(document.get("sha256", ""))):
                issues["original_pdf_hash_mismatch"] += 1
            else:
                verified_pdfs += 1
        pages = document.get("pages", [])
        if not isinstance(pages, list):
            issues["original_manifest_invalid"] += 1
            pages = []
        numbers = []
        for page in pages:
            if not isinstance(page, dict) or type(page.get("number")) is not int:
                issues["original_page_invalid"] += 1
                continue
            number = page["number"]
            numbers.append(number)
            if (doc, number) in actual_pages:
                issues["duplicate_original_page"] += 1
            actual_pages.add((doc, number))
            text_path = _stored_path(root, page.get("path"), issues)
            if text_path is not None:
                if page.get("sha256") != _sha(text_path) or not SHA256.fullmatch(str(page.get("sha256", ""))):
                    issues["original_page_hash_mismatch"] += 1
                else:
                    verified_text_pages += 1
                if not text_path.read_text(encoding="utf-8").strip():
                    empty_original_pages += 1
        expected = file.get("num_pages") if file else None
        observed = document.get("page_completeness_observed", {})
        if (type(expected) is not int or expected < 1 or len(numbers) != expected
                or any(number != index for index, number in enumerate(sorted(numbers), 1))
                or not isinstance(observed, dict)
                or any(observed.get(key) != expected for key in
                       ("metadata_pages", "pdfinfo_pages", "extracted_pages"))
                or observed.get("status") != "all_pages_extracted"):
            issues["original_page_completeness_mismatch"] += 1
    if seen_original_docs != set(by_doc):
        issues["original_document_set_mismatch"] += 1
    collection = originals.get("collection", {})
    if (not isinstance(collection, dict) or collection.get("document_count") != len(original_docs)
            or collection.get("page_count") != len(actual_pages)
            or collection.get("empty_text_page_count") != empty_original_pages):
        issues["original_collection_count_mismatch"] += 1

    preflight = _source(*source_paths["preflight"], issues)
    schema = _source(*source_paths["schema"], issues)
    captured = _source(*source_paths["snapshot"], issues)
    if not schema:
        issues["schema_empty"] += 1
    pre_by_folder = {}
    total = None
    for row in preflight:
        if not isinstance(row, dict):
            issues["preflight_row_invalid"] += 1
        elif row.get("is_total") is True:
            if total is not None:
                issues["preflight_duplicate_total"] += 1
            total = row
        elif row.get("is_total") is False:
            folder = str(row.get("scope_id"))
            if folder in pre_by_folder:
                issues["preflight_duplicate_folder"] += 1
            pre_by_folder[folder] = row
        else:
            issues["preflight_row_invalid"] += 1
    if set(pre_by_folder) != set(folders) or total is None or len(preflight) != len(folders) + 1:
        issues["preflight_scope_mismatch"] += 1

    counts = Counter()
    folder_counts = defaultdict(Counter)
    folder_ids = defaultdict(lambda: defaultdict(set))
    ids = defaultdict(Counter)
    page_document_keys = defaultdict(set)
    pdf_page_keys = set()
    fulltext_indices = defaultdict(set)
    graph_page_links = Counter()
    source_pages_count = Counter()
    rows_without_source_pages = Counter()
    graph_file_ids = set()
    relation_page_candidates = []
    matched_raw = 0
    raw = captured if isinstance(captured, list) else []
    with (root / "snapshot.private.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            try:
                item = _strict_json(line)
            except ValueError:
                issues["snapshot_line_invalid"] += 1
                continue
            if not isinstance(item, dict) or item.get("kind") not in KINDS or not isinstance(item.get("row"), dict):
                issues["snapshot_line_invalid"] += 1
                continue
            kind, row = item["kind"], item["row"]
            if matched_raw < len(raw):
                captured_item = raw[matched_raw]
                try:
                    if captured_item.get("kind") != kind or _strict_json(captured_item["row_json"]) != row:
                        issues["snapshot_payload_mismatch"] += 1
                except (AttributeError, KeyError, TypeError, ValueError):
                    issues["snapshot_payload_mismatch"] += 1
            matched_raw += 1
            counts[kind] += 1
            folder = str(row.get("space_id"))
            folder_counts[folder][kind] += 1
            if row.get("tenant_id") != owner or folder not in folders:
                issues["snapshot_row_outside_scope"] += 1
            identifier = row.get(KINDS[kind])
            if not isinstance(identifier, str) or not identifier:
                issues["snapshot_identifier_invalid"] += 1
            else:
                ids[kind][identifier] += 1
                folder_ids[folder][kind].add(identifier)
            if kind in ("entities", "relations"):
                graph_file_ids.add(row.get("file_id"))
                props = _object(row.get("properties"))
                if props is None:
                    issues["graph_properties_invalid"] += 1
                    continue
                doc = props.get("doc_id")
                file = by_doc.get(doc)
                if file is None or doc not in by_folder.get(folder, set()):
                    issues["graph_document_scope_mismatch"] += 1
                metric_prefix = "nodes" if kind == "entities" else "relations"
                if isinstance(doc, str) and doc.strip():
                    folder_counts[folder][f"{metric_prefix}_with_doc_id"] += 1
                raw_pages = props.get("source_pages")
                if raw_pages is not None and raw_pages not in ([], ""):
                    folder_counts[folder][f"{metric_prefix}_with_source_pages"] += 1
                source_pages = _pages(props.get("source_pages"))
                if source_pages is None:
                    issues["graph_source_pages_invalid"] += 1
                    continue
                if not source_pages:
                    rows_without_source_pages[kind] += 1
                    continue
                folder_counts[folder][f"{metric_prefix}_with_first_positive_page"] += 1
                if kind == "relations" and isinstance(doc, str) and doc.strip():
                    relation_page_candidates.append((folder, doc, source_pages[0]))
                source_pages_count[kind] += len(source_pages)
                for number in source_pages:
                    if (doc, number) not in actual_pages:
                        issues["graph_source_page_missing"] += 1
                    else:
                        graph_page_links[kind] += 1
            elif kind == "pages":
                doc_id = row.get("doc_id")
                metadata = _object(row.get("metadata"))
                if metadata is None:
                    issues["page_metadata_invalid"] += 1
                    continue
                match = PAGE_ID.fullmatch(doc_id) if isinstance(doc_id, str) else None
                chunk = FULLTEXT_ID.fullmatch(doc_id) if isinstance(doc_id, str) else None
                if match:
                    doc, number = match.group("doc"), int(match.group("number"))
                    page_document_keys[folder].add(doc)
                    if doc not in by_folder.get(folder, set()) or metadata.get("page_number") != number or (doc, number) not in actual_pages:
                        issues["indexed_pdf_page_mismatch"] += 1
                    if (doc, number) in pdf_page_keys:
                        issues["duplicate_indexed_pdf_page"] += 1
                    pdf_page_keys.add((doc, number))
                    folder_counts[folder]["pdf_pages"] += 1
                elif chunk:
                    doc, number = chunk.group("doc"), int(chunk.group("number"))
                    page_document_keys[folder].add(doc_id)
                    if doc not in by_folder.get(folder, set()) or metadata.get("page_number") != 0:
                        issues["fulltext_chunk_mismatch"] += 1
                    if number in fulltext_indices[doc]:
                        issues["duplicate_fulltext_chunk"] += 1
                    fulltext_indices[doc].add(number)
                    folder_counts[folder]["fulltext_chunks"] += 1
                else:
                    issues["indexed_doc_id_unclassified"] += 1
    if matched_raw != len(raw):
        issues["snapshot_payload_row_count_mismatch"] += abs(matched_raw - len(raw))
    if pdf_page_keys != actual_pages:
        issues["indexed_pdf_page_set_mismatch"] += len(pdf_page_keys ^ actual_pages)
    for indices in fulltext_indices.values():
        if indices != set(range(len(indices))):
            issues["fulltext_chunk_sequence_gap"] += 1
    if set(fulltext_indices) != set(by_doc):
        warnings["documents_without_fulltext_chunks"] += len(set(by_doc) - set(fulltext_indices))
    for folder, doc, number in relation_page_candidates:
        if (doc, number) in pdf_page_keys:
            folder_counts[folder]["relations_with_candidate_page_link"] += 1

    metric_columns = ("nodes_with_doc_id", "nodes_with_source_pages", "nodes_with_first_positive_page",
                      "relations_with_doc_id", "relations_with_source_pages",
                      "relations_with_first_positive_page", "relations_with_candidate_page_link")
    for column in metric_columns:
        if total is not None and _count(total, column, issues) != sum(folder_counts[folder][column] for folder in folders):
            issues["preflight_metric_total_mismatch"] += 1
        for folder in folders:
            row = pre_by_folder.get(folder)
            if row is not None and _count(row, column, issues) != folder_counts[folder][column]:
                issues["preflight_metric_folder_mismatch"] += 1

    mapping = {"entities": ("node_rows", "distinct_entity_ids"),
               "relations": ("relation_rows", "distinct_relation_ids"),
               "enriched": ("enriched_page_rows", None),
               "pages": ("embeddings_page_rows", None)}
    for kind, (column, distinct_column) in mapping.items():
        if total is not None and _count(total, column, issues) != counts[kind]:
            issues["preflight_total_mismatch"] += 1
        if distinct_column and total is not None and _count(total, distinct_column, issues) != len(ids[kind]):
            issues["preflight_distinct_mismatch"] += 1
        for folder in folders:
            row = pre_by_folder.get(folder)
            if row is not None and _count(row, column, issues) != folder_counts[folder][kind]:
                issues["preflight_folder_mismatch"] += 1
            if row is not None and distinct_column:
                if _count(row, distinct_column, issues) != len(folder_ids[folder][kind]):
                    issues["preflight_folder_distinct_mismatch"] += 1
        if total is not None:
            per_folder_sum = sum(_count(row, column, issues) or 0 for row in pre_by_folder.values())
            if per_folder_sum != _count(total, column, issues):
                issues["preflight_nonadditive_total"] += 1
    if total is not None and _count(total, "distinct_page_document_keys", issues) != len(set().union(*page_document_keys.values())):
        issues["preflight_page_key_mismatch"] += 1
    for folder in folders:
        row = pre_by_folder.get(folder)
        if row is not None and _count(row, "distinct_page_document_keys", issues) != len(page_document_keys[folder]):
            issues["preflight_folder_page_key_mismatch"] += 1
    duplicate_occurrences = {kind: sum(n - 1 for n in identifiers.values()) for kind, identifiers in ids.items()}
    if any(duplicate_occurrences.values()):
        warnings["duplicate_identifier_occurrences_preserved"] = sum(duplicate_occurrences.values())
    if any(rows_without_source_pages.values()):
        warnings["graph_rows_without_source_pages"] = sum(rows_without_source_pages.values())
    if graph_file_ids and not graph_file_ids <= {file.get("id") for file in files if isinstance(file, dict)}:
        warnings["graph_file_ids_not_in_file_manifest"] = len(graph_file_ids - {file.get("id") for file in files if isinstance(file, dict)})
    result = {
        "schema_version": "deposium.graph-snapshot-integrity/v1",
        "status": "archive_consistent" if not issues else "issues_found",
        "qualification": "offline_archive_consistency_only",
        "execution_provenance": "archived_collector_observation_not_reexecuted",
        "quality_status": "not_run", "documentary_cases_scored": 0,
        "originals": {"documents": len(original_docs), "pdfs_hash_verified": verified_pdfs,
                      "pages": len(actual_pages), "page_texts_hash_verified": verified_text_pages,
                      "empty_extracted_pages": empty_original_pages,
                      "pdfinfo_page_counts": "collector_record_verified_against_manifest_not_reexecuted"},
        "snapshot": {"rows": dict(counts), "distinct_identifiers": {kind: len(value) for kind, value in ids.items()},
                     "duplicate_identifier_occurrences": duplicate_occurrences,
                     "indexed_pdf_pages": len(pdf_page_keys),
                     "fulltext_chunks": sum(len(value) for value in fulltext_indices.values()),
                     "graph_source_page_references": dict(source_pages_count),
                     "graph_source_page_links_to_extracted_text": dict(graph_page_links),
                     "graph_rows_without_source_pages": dict(rows_without_source_pages),
                     "folders": [{"ordinal": index + 1, "counts": dict(folder_counts[folder])}
                                 for index, folder in enumerate(folders)]},
        "files_sha256": hashes, "issues": dict(issues), "warnings": dict(warnings),
        "limits": ["Indexed page text is not byte-comparable to PDF extraction by this audit.",
                   "Valid document and page links do not establish graph semantics or answer quality.",
                   "No live database, service, model, or product route was rerun."],
    }
    result["public_summary"] = {
        "status": result["status"], "qualification": result["qualification"],
        "quality_status": result["quality_status"], "documentary_cases_scored": 0,
        "original_documents": len(original_docs), "original_pages": len(actual_pages),
        "snapshot_rows": dict(counts), "indexed_pdf_pages": len(pdf_page_keys),
        "fulltext_chunks": result["snapshot"]["fulltext_chunks"],
        "rows_without_source_pages": dict(rows_without_source_pages),
        "issues": dict(issues), "warnings": dict(warnings),
    }
    return result


def audit_graph_snapshot(path: str | Path) -> dict:
    """Stable API for the CLI; returns private details and a safe public summary."""
    try:
        return audit_snapshot(path)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, AttributeError, IndexError):
        return _incomplete(Counter({"archive_malformed": 1}), {})
