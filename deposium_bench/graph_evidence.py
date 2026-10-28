"""Prepare a private, unscored human review of rendered graph edge locators.

This reads sealed observations and an audited capture; it never calls a model,
replays a graph query, or treats a stored page number as a qualified citation.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import quote

from .adapters import _json as _strict_json
from .graph_review import load_graph_templates, validate_private_packet
from .graph_snapshot import audit_snapshot, _sha
from .graph_document import validate_plan
from .mastra_pilot import ROOT, _dump


class GraphEvidenceError(ValueError):
    """An input cannot support a safe private review packet."""


def _private(path: str | Path) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_relative_to((ROOT / "results").resolve()):
        raise GraphEvidenceError("graph evidence: path outside ignored results/")
    git_env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    check = subprocess.run(["git", "check-ignore", "-q", str(resolved)], cwd=ROOT, env=git_env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    tracked = subprocess.run(["git", "ls-files", "-z", "--", str(resolved)], cwd=ROOT, env=git_env,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
    if check.returncode != 0 or tracked.returncode or tracked.stdout:
        raise GraphEvidenceError("graph evidence: path is tracked or not Git-ignored")
    return resolved


def _read(path: Path):
    try:
        return _strict_json(path.read_bytes())
    except (OSError, UnicodeError, ValueError) as exc:
        raise GraphEvidenceError("graph evidence: invalid JSON input") from exc


def _relative(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise GraphEvidenceError("graph evidence: unsafe source path")
    path = (root / value).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise GraphEvidenceError("graph evidence: missing or escaping source path")
    return path


def _sealed_observation(root: Path) -> dict[str, str]:
    seal = _read(root / "seal.json")
    files = seal.get("files") if isinstance(seal, dict) else None
    if (not isinstance(files, dict) or seal.get("schema_version") != "deposium.graph-document-seal/v1"
            or not files or any(not isinstance(name, str) or Path(name).name != name
                                or name == "seal.json" or not isinstance(digest, str)
                                or len(digest) != 64 for name, digest in files.items())):
        raise GraphEvidenceError("graph evidence: invalid observation seal")
    actual = {entry.name for entry in root.iterdir()}
    if actual != set(files) | {"seal.json"}:
        raise GraphEvidenceError("graph evidence: observation inventory differs from seal")
    for name, digest in files.items():
        path = _relative(root, name)
        if _sha(path) != digest:
            raise GraphEvidenceError("graph evidence: observation file hash mismatch")
    return files


def _capture_index(source: Path, packet: dict, owner: str, folders: set[str]) -> tuple[dict, dict, dict]:
    originals = _read(source / "original-documents.private.json")
    original_docs = originals.get("documents") if isinstance(originals, dict) else None
    packet_docs = packet.get("documents") if isinstance(packet, dict) else None
    if not isinstance(original_docs, list) or not isinstance(packet_docs, list):
        raise GraphEvidenceError("graph evidence: document manifests missing")
    documents: dict[str, dict] = {}
    original_hashes = {}
    for doc in original_docs:
        if not isinstance(doc, dict) or not isinstance(doc.get("doc_id"), str) or doc["doc_id"] in documents:
            raise GraphEvidenceError("graph evidence: malformed or duplicate original document")
        folder = doc.get("folder_id")
        if folder not in folders:
            raise GraphEvidenceError("graph evidence: original document outside captured folders")
        pdf = _relative(source, doc.get("path"))
        if _sha(pdf) != doc.get("sha256"):
            raise GraphEvidenceError("graph evidence: original PDF hash mismatch")
        original_hashes[doc["path"]] = doc["sha256"]
        pages = {}
        for page in doc.get("pages", []):
            if (not isinstance(page, dict) or type(page.get("number")) is not int
                    or page["number"] < 1 or page["number"] in pages):
                raise GraphEvidenceError("graph evidence: malformed or duplicate original page")
            path = _relative(source, page.get("path"))
            if _sha(path) != page.get("sha256"):
                raise GraphEvidenceError("graph evidence: original page hash mismatch")
            original_hashes[page["path"]] = page["sha256"]
            pages[page["number"]] = {"path": page["path"], "sha256": page["sha256"]}
        documents[doc["doc_id"]] = {"folder_id": folder, "name": doc.get("name"),
                                     "pdf": {"path": doc["path"], "sha256": doc["sha256"]},
                                     "pages": pages}
    packet_by_doc = {doc.get("doc_id"): doc for doc in packet_docs if isinstance(doc, dict)}
    if len(packet_by_doc) != len(packet_docs) or set(packet_by_doc) != set(documents):
        raise GraphEvidenceError("graph evidence: packet and original document sets differ")
    for doc_id, doc in packet_by_doc.items():
        original = documents[doc_id]
        if (doc.get("folder_id") != original["folder_id"] or doc.get("path") != original["pdf"]["path"]
                or doc.get("sha256") != original["pdf"]["sha256"]
                or {(p.get("number"), p.get("path"), p.get("sha256")) for p in doc.get("pages", [])}
                   != {(number, page["path"], page["sha256"]) for number, page in original["pages"].items()}):
            raise GraphEvidenceError("graph evidence: packet and original documents differ")

    relations = {}
    with (source / "snapshot.private.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            try:
                item = _strict_json(line)
            except ValueError as exc:
                raise GraphEvidenceError("graph evidence: malformed captured row") from exc
            if not isinstance(item, dict):
                raise GraphEvidenceError("graph evidence: malformed captured row")
            if item.get("kind") != "relations":
                continue
            row = item.get("row")
            if not isinstance(row, dict):
                raise GraphEvidenceError("graph evidence: malformed captured relation")
            rid, folder, file_id = row.get("relation_id"), row.get("space_id"), row.get("file_id")
            if (not isinstance(rid, str) or not rid or not isinstance(folder, str)
                    or folder not in folders or row.get("tenant_id") != owner
                    or type(file_id) is not int or file_id < 0):
                raise GraphEvidenceError("graph evidence: relation outside captured scope or malformed key")
            key = (rid, folder, file_id)
            if key in relations:
                raise GraphEvidenceError("graph evidence: duplicate composite relation key")
            props = row.get("properties")
            if isinstance(props, str):
                try:
                    props = _strict_json(props)
                except ValueError as exc:
                    raise GraphEvidenceError("graph evidence: malformed stored relation properties") from exc
            if not isinstance(props, dict):
                raise GraphEvidenceError("graph evidence: malformed stored relation properties")
            if props.get("doc_id") not in documents or documents[props["doc_id"]]["folder_id"] != folder:
                raise GraphEvidenceError("graph evidence: captured relation document outside folder")
            relations[key] = {"row": row, "properties": props}
    return documents, relations, original_hashes


def _edge_lists(output: dict) -> list:
    edges = output.get("edges")
    nested = output.get("path")
    nested_edges = nested.get("edges") if isinstance(nested, dict) else None
    if edges is not None and nested_edges is not None and edges != nested_edges:
        raise GraphEvidenceError("graph evidence: inconsistent path edge copies")
    value = edges if edges is not None else nested_edges
    if value is None:
        value = output.get("connections", [])
    if not isinstance(value, list):
        raise GraphEvidenceError("graph evidence: malformed rendered edge list")
    return value


def _truncation(output: object) -> str:
    if not isinstance(output, dict):
        return "not_observed"
    metadata = output.get("metadata")
    values = [output.get("truncated"), metadata.get("truncated") if isinstance(metadata, dict) else None]
    if any(value is True for value in values):
        return "truncated"
    if any(value is False for value in values):
        return "not_truncated"
    return "not_observed"


def _rendered_variant(item: dict) -> dict:
    edge = item["edge"]
    return {"source": edge.get("source"), "target": edge.get("target"),
            "type": edge.get("type"), "locator": item["locator"]}


def _locator(edge: dict, relations: dict, documents: dict, owner: str, folders: set[str]) -> dict:
    props = edge.get("properties")
    if not isinstance(props, dict):
        return {"status": "missing_rendered_properties", "key": None, "doc_id": None, "pages": []}
    rid, folder, file_id = edge.get("id"), props.get("space_id"), props.get("file_id")
    if (not isinstance(rid, str) or not rid or not isinstance(folder, str)
            or type(file_id) is not int or file_id < 0):
        return {"status": "missing_composite_key", "key": None, "doc_id": props.get("doc_id"), "pages": []}
    key = (rid, folder, file_id)
    locator = {"key": list(key), "doc_id": props.get("doc_id"), "rendered_pages": props.get("source_pages"),
               "rendered_page_status": props.get("source_pages_status"), "pages": []}
    if folder not in folders:
        return {**locator, "status": "rendered_scope_mismatch"}
    captured = relations.get(key)
    if captured is None:
        return {**locator, "status": "relation_not_in_capture"}
    row, stored = captured["row"], captured["properties"]
    if row.get("tenant_id") != owner or row.get("space_id") != folder or row.get("file_id") != file_id:
        return {**locator, "status": "captured_scope_mismatch"}
    if (edge.get("type") != row.get("relation_type")
            or ("stored_source_id" in props and props["stored_source_id"] != row.get("source_id"))
            or ("stored_target_id" in props and props["stored_target_id"] != row.get("target_id"))):
        return {**locator, "status": "rendered_relation_mismatch"}
    doc_id = props.get("doc_id")
    if not isinstance(doc_id, str) or not doc_id.strip():
        return {**locator, "status": "missing_rendered_document"}
    if doc_id != stored.get("doc_id"):
        return {**locator, "status": "rendered_document_mismatch"}
    document = documents.get(doc_id)
    if document is None or document["folder_id"] != folder:
        return {**locator, "status": "document_wrong_scope"}
    locator["document"] = {"name": document["name"], "pdf": document["pdf"]}
    pages = props.get("source_pages")
    if pages is None or pages == []:
        return {**locator, "status": "rendered_pages_absent"}
    if (not isinstance(pages, list) or any(type(page) is not int or page < 1 for page in pages)
            or len(set(pages)) != len(pages) or props.get("source_pages_status") != "recorded"):
        return {**locator, "status": "rendered_pages_invalid"}
    stored_pages = stored.get("source_pages")
    if isinstance(stored_pages, str):
        try:
            stored_pages = _strict_json(stored_pages)
        except ValueError:
            stored_pages = [piece.strip() for piece in stored_pages.split(",")]
    if type(stored_pages) is int:
        stored_pages = [stored_pages]
    if not isinstance(stored_pages, list):
        return {**locator, "status": "stored_pages_absent"}
    normalized = set()
    for page in stored_pages:
        if isinstance(page, str) and page.isdecimal():
            page = int(page)
        if type(page) is int and page > 0:
            normalized.add(page)
    if not set(pages) <= normalized:
        return {**locator, "status": "rendered_pages_not_stored"}
    for number in pages:
        original = document["pages"].get(number)
        if original is None:
            return {**locator, "status": "original_page_absent", "pages": []}
        locator["pages"].append({"number": number, **original})
    return {**locator, "status": "locator_verified_pending_human"}


def _write(path: Path, raw: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)


def _md(value: object) -> str:
    """Keep stored graph text from becoming Markdown structure or links."""
    text = " ".join(str(value).splitlines())  # a stored value must not start a new Markdown line
    return escape(text, quote=True).replace("`", "&#96;").replace("[", "&#91;").replace("]", "&#93;")


def prepare_graph_evidence_review(archive: str | Path, observation: str | Path,
                                  output: str | Path, *, arm: str = "after") -> dict:
    """Seal a private review packet; return only aggregate, identifier-free counts."""
    if arm not in {"before", "after"}:
        raise GraphEvidenceError("graph evidence: arm must be before or after")
    source, observed, target = _private(archive), _private(observation), _private(output)
    producer_bytes = Path(__file__).read_bytes()
    if (not source.is_dir() or not observed.is_dir() or target.exists()
            or target.is_relative_to(source) or target.is_relative_to(observed)):
        raise GraphEvidenceError("graph evidence: output must be new and separate from inputs")
    inventory = _sealed_observation(observed)
    audit = audit_snapshot(source)
    if audit.get("status") != "archive_consistent":
        raise GraphEvidenceError("graph evidence: captured archive audit failed")
    source_sql_hashes = {p.name: _sha(p) for p in sorted(source.glob("*.sql"))}
    packet_raw = (observed / "packet.private.json").read_bytes()
    if (source / "packet.json").read_bytes() != packet_raw:
        raise GraphEvidenceError("graph evidence: observed packet differs from captured packet")
    packet = _strict_json(packet_raw)
    templates, _ = load_graph_templates()
    review = validate_private_packet(packet, templates, source)
    if review.get("scope_evidence_consistency") != "matched":
        raise GraphEvidenceError("graph evidence: packet scope evidence not matched")
    scope = _read(source / "scope.private.json")
    owner, folders = scope.get("owner_tenant_id"), {str(f) for f in scope.get("folder_ids", [])}
    manifest, plan = _read(observed / "manifest.private.json"), _read(observed / "plan.private.json")
    descriptor = manifest.get("snapshot", {})
    schema_path = Path(descriptor.get("schema_path", "")).resolve()
    expected_counts = {kind: audit.get("public_summary", {}).get("snapshot_rows", {}).get(kind, 0)
                       for kind in ("entities", "relations", "pages", "enriched")}
    if (not isinstance(owner, str) or not owner or not folders
            or descriptor.get("sha256") != _sha(source / "snapshot.private.jsonl")
            or descriptor.get("schema_sha256") != audit.get("files_sha256", {}).get(
                Path(descriptor.get("schema_path", "")).name)
            or not schema_path.is_relative_to(source)
            or not schema_path.name.startswith("schema")
            or Path(descriptor.get("path", "")).resolve() != (source / "snapshot.private.jsonl").resolve()
            or descriptor.get("owner_tenant_id") != owner
            or {str(f) for f in descriptor.get("folder_ids", [])} != folders
            or descriptor.get("expected_counts") != expected_counts
            or manifest.get("packet_sha256") != sha256(packet_raw).hexdigest()
            or packet.get("snapshot", {}).get("sha256") != descriptor.get("sha256")
            or manifest.get("plan_sha256") != _sha(observed / "plan.private.json")
            or plan.get("packet_sha256") != manifest.get("packet_sha256")
            or plan.get("snapshot_sha256") != descriptor.get("sha256")):
        raise GraphEvidenceError("graph evidence: observation and capture disagree")
    if (not isinstance(plan.get("requests"), list) or not isinstance(manifest.get("repetitions"), int)
            or manifest["repetitions"] < 1):
        raise GraphEvidenceError("graph evidence: invalid observation plan")
    requests = validate_plan(plan, packet, manifest["packet_sha256"], scope)
    expected = {request["case_id"]: request for request in requests}
    if len(expected) != len(requests):
        raise GraphEvidenceError("graph evidence: duplicate planned case")
    documents, relations, original_hashes = _capture_index(source, packet, owner, folders)
    cases, occurrences, seen = [], defaultdict(list), set()
    excluded = Counter()
    with (observed / "raw.private.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = _strict_json(line)
            key = (row.get("arm"), row.get("case_id"), row.get("repetition"))
            if (key in seen or row.get("case_id") not in expected or row.get("arm") not in {"before", "after"}
                    or type(row.get("repetition")) is not int or not 0 <= row["repetition"] < manifest["repetitions"]
                    or row.get("entrypoint") != expected[row["case_id"]].get("entrypoint")
                    or row.get("family_id") != expected[row["case_id"]].get("family_id")):
                raise GraphEvidenceError("graph evidence: unexpected or duplicate observation row")
            seen.add(key)
            if row["arm"] != arm:
                continue
            response = row.get("response")
            if not isinstance(response, dict):
                raise GraphEvidenceError("graph evidence: malformed observation response")
            entry = row["entrypoint"]
            request = expected[row["case_id"]]
            selected_folders = (request["input"].get("folder_ids", scope["folder_ids"])
                                if entry == "helper" else request["service"].get("folder_ids", []))
            selected_folders = {str(folder) for folder in selected_folders}
            if response.get("status") == "ok" and row.get("provenance_valid") is True:
                runtime_source = manifest.get("sources", {}).get(arm, {})
                runtime_capture = response.get("document_snapshot")
                if (response.get("source_files_sha256") != runtime_source.get("files_sha256")
                        or not isinstance(runtime_capture, dict)
                        or runtime_capture.get("snapshot_sha256") != descriptor["sha256"]
                        or runtime_capture.get("schema_sha256") != descriptor["schema_sha256"]
                        or runtime_capture.get("loaded_counts") != descriptor["expected_counts"]
                        or response.get("network_attempts") != 0
                        or response.get("model_calls") != 0):
                    raise GraphEvidenceError("graph evidence: raw response provenance mismatch")
            case = {"case_id": row["case_id"], "family_id": row["family_id"],
                    "entrypoint": entry, "arm": arm, "repetition": row["repetition"],
                    "transport_status": response.get("status"), "outcome": response.get("outcome"),
                    "provenance_valid": row.get("provenance_valid") is True,
                    "truncation": _truncation(response.get("output")),
                    "support_review": "pending_human", "edges": []}
            if entry not in {"helper", "strict_service"}:
                excluded[entry] += 1
                case["review_status"] = "excluded_surface"
            elif response.get("status") != "ok" or response.get("outcome") != "ok":
                case["review_status"] = "observation_not_ok"
            elif row.get("provenance_valid") is not True:
                case["review_status"] = "observation_provenance_unverified"
            else:
                output_value = response.get("output")
                if not isinstance(output_value, dict):
                    raise GraphEvidenceError("graph evidence: malformed successful graph output")
                case["review_status"] = "returned_edges"
                for ordinal, edge in enumerate(_edge_lists(output_value)):
                    if not isinstance(edge, dict):
                        raise GraphEvidenceError("graph evidence: malformed rendered edge")
                    locator = _locator(edge, relations, documents, owner, selected_folders)
                    occurrence = {"case_id": row["case_id"], "family_id": row["family_id"],
                                  "arm": arm, "entrypoint": entry, "repetition": row["repetition"],
                                  "edge_ordinal": ordinal, "edge": edge, "locator": locator,
                                  "support_review": "pending_human"}
                    case["edges"].append(occurrence)
                    if locator.get("key"):
                        occurrences[tuple(locator["key"])].append(occurrence)
            cases.append(case)
    for request in plan["requests"]:
        for repetition in range(manifest["repetitions"]):
            if (arm, request["case_id"], repetition) in seen:
                continue
            cases.append({"case_id": request["case_id"], "family_id": request["family_id"],
                          "entrypoint": request["entrypoint"], "arm": arm, "repetition": repetition,
                          "transport_status": "missing", "outcome": "missing",
                          "provenance_valid": False, "support_review": "pending_human",
                          "truncation": "not_observed",
                          "review_status": "missing_observation", "edges": []})
    if not cases or not any(case["edges"] for case in cases):
        raise GraphEvidenceError("graph evidence: zero returned edges for requested arm")
    statuses = Counter(occ["locator"]["status"] for case in cases for occ in case["edges"])
    summary = {"schema_version": "deposium.graph-evidence-summary/v1", "status": "pending_human",
               "arm": arm, "cases": len(cases), "returned_edge_occurrences": sum(len(c["edges"]) for c in cases),
               "distinct_composite_edges": len(occurrences), "locator_statuses": dict(statuses),
               "excluded_surfaces": dict(excluded), "case_outcomes": dict(Counter(c["outcome"] or c["transport_status"] for c in cases)),
               "truncated_cases": sum(c["truncation"] == "truncated" for c in cases),
               "truncation_statuses": dict(Counter(c["truncation"] for c in cases)),
               "cases_scored": 0, "human_reviewed": 0, "support_review": "pending_human",
               "citation_qualification": "not_run", "model_calls": 0}
    review_json = {"schema_version": "deposium.graph-evidence-private/v1", "summary": summary,
                   "source_archive": str(source), "observation_archive": str(observed),
                   "cases": cases, "composite_edges": [
                       {"key": list(key), "occurrence_count": len(items),
                        "rendered_variants": list({json.dumps(_rendered_variant(item), sort_keys=True):
                                                    _rendered_variant(item) for item in items}.values())}
                       for key, items in sorted(occurrences.items())]}
    lines = ["# Private graph edge evidence review", "", "Human review pending. Page links are stored locators, not qualified citations.", "",
             "Review each relation against the linked original page. Check whether the direction, predicate and scope support the intended statement; record any contradiction or missing context.", ""]
    for composite_key, items in sorted(occurrences.items()):
        lines.append(f"## Relation {json.dumps(list(composite_key))}")
        variants = {json.dumps(_rendered_variant(item), sort_keys=True): _rendered_variant(item)
                    for item in items}
        for index, variant in enumerate(variants.values(), 1):
            locator = variant["locator"]
            lines.append(f"- Rendered variant {index}: `{_md(variant['source'])}` → `{_md(variant['target'])}` · `{_md(variant['type'])}` · {locator['status']} · document `{_md(locator.get('doc_id'))}` · pages `{_md(locator.get('rendered_pages'))}`")
            document = locator.get("document")
            if document:
                pdf = os.path.relpath(source / document["pdf"]["path"], target)
                lines.append(f"  - Document: {_md(document['name'])} · [verified PDF]({quote(pdf, safe='/.-_')})")
            for page in locator.get("pages", []):
                link = os.path.relpath(source / page["path"], target)
                lines.append(f"  - Page {page['number']}: [verified original text]({quote(link, safe='/.-_')}) · SHA-256 `{page['sha256']}`")
        lines.append("- Occurrences: " + "; ".join(
            f"{item['case_id']}/{item['family_id']}/{item['entrypoint']}/repeat-{item['repetition']}/edge-{item['edge_ordinal']}"
            for item in items))
        lines.append("- Human judgment: pending_human (relation support, page context, direction, scope).")
        lines.append("")
    lines.append("# Case and surface ledger")
    lines.append("")
    for case in cases:
        lines.append(f"- {case['case_id']} · {case['family_id']} · {case['entrypoint']} · repeat {case['repetition']}: {case['outcome'] or case['transport_status']} · {case['review_status']} · truncation {case['truncation']} · {len(case['edges'])} rendered edges")
    lines.append("")
    source_before = dict(audit["files_sha256"])
    source_before["packet.json"] = sha256(packet_raw).hexdigest()
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    _write(target / "review.private.json", _dump(review_json))
    _write(target / "REVIEW.private.md", ("\n".join(lines) + "\n").encode("utf-8"))
    _write(target / "summary.json", _dump(summary))
    _write(target / "producer.graph_evidence.py", producer_bytes)
    if (_sealed_observation(observed) != inventory
            or any(_sha(source / name) != digest for name, digest in source_before.items())
            or any(_sha(source / name) != digest for name, digest in source_sql_hashes.items())
            or any(_sha(_relative(source, name)) != digest for name, digest in original_hashes.items())
            or Path(__file__).read_bytes() != producer_bytes):
        raise GraphEvidenceError("graph evidence: source changed while preparing review")
    _write(target / "seal.json", _dump({"schema_version": "deposium.graph-evidence-seal/v1",
                                       "source_observation_files_sha256": inventory,
                                       "source_snapshot_files_sha256": source_before,
                                       "source_sql_files_sha256": source_sql_hashes,
                                       "source_original_files_sha256": original_hashes,
                                       "files": {p.name: _sha(p) for p in sorted(target.iterdir()) if p.name != "seal.json"}}))
    return summary
