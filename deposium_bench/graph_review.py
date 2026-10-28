"""Offline preparation of documentary graph review cases.

This is a review format, not a graph runner or a scorer. Importing it performs no
I/O. Private source files are read only when a packet is explicitly validated.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from string import Formatter
from typing import Any

from .adapters import _json as _strict_json

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "datasets/graph-document-review-v0/cases.review.jsonl"
TEMPLATE_VERSION = "deposium.graph-document-review/v0"
PACKET_VERSION = "deposium.graph-private-packet/v1"
SHA = re.compile(r"[0-9a-f]{64}\Z")
BEFORE_REVISION = "982f49d2b7ab85a6b52a91a4dac797559ebbc9df"
AFTER_REVISION = "eed8934ed597da12a8c79f14f872042e0658f253"
FAMILIES = {f"G{i:02}" for i in range(1, 7)} | {"T01", "T02"}
RELATIONAL = {"G01", "G02", "G03", "G04", "G06"}


class GraphReviewError(ValueError):
    """Invalid public template or private reference packet."""


def _exact(value: Any, keys: set[str], where: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise GraphReviewError(f"{where}: expected exactly {sorted(keys)}")
    return value


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise GraphReviewError(f"{where}: non-empty text required")
    return value


def _hash(value: Any, where: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise GraphReviewError(f"{where}: expected SHA-256 hex")
    return value


def _list(value: Any, where: str) -> list:
    if not isinstance(value, list) or not value:
        raise GraphReviewError(f"{where}: non-empty list required")
    return value


def _unique(values: list, where: str) -> None:
    if len(values) != len(set(values)):
        raise GraphReviewError(f"{where}: duplicate identity")


def _read_json(path: Path) -> Any:
    try:
        return _strict_json(path.read_bytes())
    except (OSError, UnicodeError, ValueError) as exc:
        raise GraphReviewError("invalid or unreadable JSON input") from exc


def load_graph_templates(path: str | Path = TEMPLATES) -> tuple[list[dict], str]:
    """Validate the public, unresolved 8-family/16-language template register."""
    path = Path(path)
    try:
        raw = path.read_bytes()
        rows = [_strict_json(line) for line in raw.splitlines() if line.strip()]
    except (OSError, UnicodeError, ValueError) as exc:
        raise GraphReviewError("invalid or unreadable template file") from exc
    digest = sha256(raw).hexdigest()
    private_manifest = path.with_name("manifest.review.json")
    manifest_path = (private_manifest if private_manifest.exists() or private_manifest.is_symlink()
                     else path.with_name("manifest.public.json"))
    manifest = _read_json(manifest_path)
    _exact(manifest, {"schema_version", "dataset_id", "cases_file", "cases_sha256",
                      "case_count", "family_count", "status", "comparison", "limitations"}, "manifest")
    if (manifest["schema_version"] != "deposium.graph-document-review-manifest/v0"
            or manifest["cases_file"] != path.name or manifest["cases_sha256"] != digest
            or manifest["case_count"] != 16 or manifest["family_count"] != 8
            or manifest["status"] != "unresolved_review_only"):
        raise GraphReviewError("template manifest mismatch")
    if len(rows) != 16:
        raise GraphReviewError("expected exactly 16 templates")
    pairs: dict[str, set[str]] = {}
    ids: list[str] = []
    for row in rows:
        _exact(row, {"schema_version", "case_id", "family_id", "translation_family",
                     "language", "split", "status", "template", "slots", "reference_artifact",
                     "levels"}, "template")
        family = row["family_id"]
        if (row["schema_version"] != TEMPLATE_VERSION or family not in FAMILIES
                or row["language"] not in {"fr", "en"}
                or row["case_id"] != f"{family}-{row['language']}"
                or row["translation_family"] != family or row["split"] != "unassigned"
                or row["status"] != "unresolved" or row["reference_artifact"] is not None):
            raise GraphReviewError("template identity/readiness invalid")
        expected_levels = {"A": "not_implemented" if family.startswith("T") else "not_run",
                           "B": "not_run", "C": "not_implemented"}
        if row["levels"] != expected_levels:
            raise GraphReviewError("template levels invalid")
        template = _text(row["template"], "template.text")
        slots = _list(row["slots"], "template.slots") if family not in {"T01", "T02"} else row["slots"]
        if not isinstance(slots, list) or any(not isinstance(s, str) or not s for s in slots):
            raise GraphReviewError("template.slots invalid")
        _unique(slots, "template.slots")
        try:
            fields = [name for _, name, _, _ in Formatter().parse(template) if name is not None]
        except ValueError as exc:
            raise GraphReviewError("malformed template") from exc
        if sorted(fields) != sorted(slots) or any("." in s or "[" in s for s in fields):
            raise GraphReviewError("template slots do not match placeholders")
        ids.append(row["case_id"])
        pairs.setdefault(family, set()).add(row["language"])
    _unique(ids, "templates")
    if set(pairs) != FAMILIES or any(languages != {"fr", "en"} for languages in pairs.values()):
        raise GraphReviewError("templates must contain FR/EN pair for every family")
    return rows, digest


def _verified_file(root: Path, relative: Any, expected_sha: Any, where: str) -> bytes:
    _hash(expected_sha, f"{where}.sha256")
    _text(relative, f"{where}.path")
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise GraphReviewError(f"{where}: source path must be relative to private packet")
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
        raise GraphReviewError(f"{where}: missing or out-of-packet source file")
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise GraphReviewError(f"{where}: source file unreadable") from exc
    if not raw or sha256(raw).hexdigest() != expected_sha:
        raise GraphReviewError(f"{where}: source hash mismatch")
    return raw


def _document_index(packet: dict, root: Path) -> dict[str, dict]:
    documents: dict[str, dict] = {}
    for doc in _list(packet["documents"], "documents"):
        _exact(doc, {"doc_id", "name", "folder_id", "path", "sha256", "pages"}, "document")
        doc_id = _text(doc["doc_id"], "document.doc_id")
        name = _text(doc["name"], "document.name")
        folder_id = _text(doc["folder_id"], "document.folder_id")
        if doc_id in documents:
            raise GraphReviewError("duplicate document ID")
        _verified_file(root, doc["path"], doc["sha256"], "document")
        pages: dict[int, str] = {}
        for page in _list(doc["pages"], "document.pages"):
            _exact(page, {"number", "path", "sha256"}, "page")
            number = page["number"]
            if type(number) is not int or number < 1 or number in pages:
                raise GraphReviewError("page number invalid/duplicate")
            raw = _verified_file(root, page["path"], page["sha256"], "page")
            try:
                pages[number] = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise GraphReviewError("page text must be UTF-8") from exc
            if not pages[number].strip() or "\x00" in pages[number]:
                raise GraphReviewError("page text must be non-empty UTF-8 text")
        documents[doc_id] = {"name": name, "folder_id": folder_id,
                             "sha256": doc["sha256"], "pages": pages}
    return documents


def _scope_validation(value: Any, root: Path, docs: dict[str, dict]) -> bool:
    scope = _exact(value, {"status", "method", "evidence_path", "evidence_sha256",
                           "tenant_scope_sha256", "folder_scope_sha256"}, "scope_validation")
    if scope["status"] == "unverified":
        if (scope["method"] not in {"unverified", "global_counter"}
                or scope["evidence_path"] is not None or scope["evidence_sha256"] is not None):
            raise GraphReviewError("unverified scope cannot cite filtered evidence")
        return False
    if scope["status"] != "filtered_evidence_provided" or scope["method"] not in {
            "independent_filtered_query", "corrected_diagnostic"}:
        raise GraphReviewError("scope validation method/status invalid")
    _hash(scope["tenant_scope_sha256"], "scope tenant hash")
    _hash(scope["folder_scope_sha256"], "scope folder hash")
    raw = _verified_file(root, scope["evidence_path"], scope["evidence_sha256"], "scope evidence")
    try:
        evidence = _strict_json(raw)
    except (UnicodeError, ValueError) as exc:
        raise GraphReviewError("scope evidence must be JSON") from exc
    _exact(evidence, {"schema_version", "method", "filter_columns", "tenant_id",
                      "folder_ids", "filter_request_path", "filter_request_sha256",
                      "per_folder_edge_counts", "union_edge_count", "folders_disjoint"}, "scope evidence")
    tenant_id = _text(evidence["tenant_id"], "scope tenant")
    folder_ids = _list(evidence["folder_ids"], "scope folders")
    for folder_id in folder_ids:
        _text(folder_id, "scope folder")
    _unique(folder_ids, "scope folders")
    expected_tenant_hash = sha256(tenant_id.encode("utf-8")).hexdigest()
    expected_folder_hash = sha256(json.dumps(sorted(folder_ids), ensure_ascii=False,
                                            separators=(",", ":")).encode("utf-8")).hexdigest()
    if (evidence["schema_version"] != "deposium.graph-scope-evidence/v1"
            or evidence["method"] != scope["method"]
            or evidence["filter_columns"] != ["tenant_id", "space_id"]
            or expected_tenant_hash != scope["tenant_scope_sha256"]
            or expected_folder_hash != scope["folder_scope_sha256"]
            or evidence["folders_disjoint"] is not True):
        raise GraphReviewError("scope evidence is not a tenant-and-folder filtered diagnostic")
    request = _verified_file(root, evidence["filter_request_path"],
                             evidence["filter_request_sha256"], "filter request")
    try:
        request_object = _strict_json(request)
    except (UnicodeError, ValueError) as exc:
        raise GraphReviewError("filter request must be structured JSON") from exc
    _exact(request_object, {"schema_version", "method", "operation", "tenant_id",
                            "folder_ids", "filter_columns"}, "filter request")
    if (request_object["schema_version"] != "deposium.graph-filter-request/v1"
            or request_object["method"] != scope["method"]
            or request_object["operation"] != "count_graph_edges_filtered"
            or request_object["tenant_id"] != tenant_id
            or request_object["folder_ids"] != folder_ids
            or request_object["filter_columns"] != ["tenant_id", "space_id"]):
        raise GraphReviewError("filter request does not match declared tenant and folders")
    counts = _list(evidence["per_folder_edge_counts"], "per-folder edge counts")
    for row in counts:
        _exact(row, {"folder_id", "edge_count"}, "per-folder count")
        if row["folder_id"] not in folder_ids or type(row["edge_count"]) is not int or row["edge_count"] < 0:
            raise GraphReviewError("invalid filtered edge count")
    if len(counts) != len(folder_ids) or {row["folder_id"] for row in counts} != set(folder_ids):
        raise GraphReviewError("filtered counts must cover every folder once")
    union = evidence["union_edge_count"]
    if type(union) is not int or union < 0 or sum(row["edge_count"] for row in counts) != union:
        raise GraphReviewError("filtered union edge count disagrees with disjoint folders")
    if any(doc["folder_id"] not in folder_ids for doc in docs.values()):
        raise GraphReviewError("document folder is outside verified scope")
    return True


def _reference(reference: dict, family: str, docs: dict[str, dict], selected: list[str],
               bindings: dict[str, str]) -> None:
    _exact(reference, {"status", "reviewer", "review_date", "conclusion", "entities",
                       "edges", "passages", "absence_review", "control_expected", "limits"}, "reference")
    if reference["status"] not in {"proposed", "human_reviewed"}:
        raise GraphReviewError("reference status must be proposed or human_reviewed")
    _text(reference["reviewer"], "reference.reviewer")
    if not isinstance(reference["review_date"], str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", reference["review_date"]):
        raise GraphReviewError("reference.review_date invalid")
    try:
        date.fromisoformat(reference["review_date"])
    except ValueError as exc:
        raise GraphReviewError("reference.review_date invalid") from exc
    _text(reference["conclusion"], "reference.conclusion")
    entities = _list(reference["entities"], "reference.entities") if family.startswith("G") else reference["entities"]
    if not isinstance(entities, list):
        raise GraphReviewError("reference.entities invalid")
    entity_ids = []
    for entity in entities:
        _exact(entity, {"id", "label"}, "entity")
        entity_ids.append(_text(entity["id"], "entity.id"))
        _text(entity["label"], "entity.label")
    _unique(entity_ids, "entities")
    if family in {"G01", "G02", "G03", "G05"} and len(entity_ids) < 2:
        raise GraphReviewError("reference needs two distinct entities")
    edges = reference["edges"]
    passages = reference["passages"]
    if not isinstance(edges, list) or not isinstance(passages, list):
        raise GraphReviewError("reference edges/passages must be lists")
    passage_ids = []
    for passage in passages:
        _exact(passage, {"id", "doc_id", "page", "quote", "quote_sha256"}, "passage")
        pid = _text(passage["id"], "passage.id")
        doc_id = _text(passage["doc_id"], "passage.doc_id")
        page = passage["page"]
        quote = _text(passage["quote"], "passage.quote")
        if (doc_id not in selected or type(page) is not int or page not in docs[doc_id]["pages"]
                or quote not in docs[doc_id]["pages"][page]
                or sha256(quote.encode("utf-8")).hexdigest() != _hash(passage["quote_sha256"], "passage.quote_sha256")):
            raise GraphReviewError("passage not found in verified document page")
        passage_ids.append(pid)
    _unique(passage_ids, "passages")
    edge_ids = []
    for edge in edges:
        _exact(edge, {"id", "source_id", "target_id", "direction", "passage_ids"}, "edge")
        edge_ids.append(_text(edge["id"], "edge.id"))
        if (edge["source_id"] not in entity_ids or edge["target_id"] not in entity_ids
                or edge["direction"] not in {"source_to_target", "target_to_source"}
                or not isinstance(edge["passage_ids"], list) or not edge["passage_ids"]
                or not set(edge["passage_ids"]) <= set(passage_ids)):
            raise GraphReviewError("edge lacks valid endpoints, direction or passage")
    _unique(edge_ids, "edges")
    if family in RELATIONAL and (not edges or not passages):
        raise GraphReviewError("relational reference requires documented edge")
    if family == "G02" and len(edges) not in {2, 3}:
        raise GraphReviewError("G02 needs a documented 2-3 edge path")
    if family == "G02":
        oriented = [(e["source_id"], e["target_id"]) if e["direction"] == "source_to_target"
                    else (e["target_id"], e["source_id"]) for e in edges]
        if any(left[1] != right[0] for left, right in zip(oriented, oriented[1:])):
            raise GraphReviewError("G02 edges are not a continuous ordered path")
        labels = {entity["id"]: entity["label"] for entity in entities}
        if labels[oriented[0][0]] != bindings["A"] or labels[oriented[-1][1]] != bindings["B"]:
            raise GraphReviewError("G02 path endpoints do not match bound entities")
    used_passages = {pid for edge in edges for pid in edge["passage_ids"]}
    if family == "G03" and len({p["doc_id"] for p in passages if p["id"] in used_passages}) < 2:
        raise GraphReviewError("G03 needs passages from multiple documents")
    if family == "G04" and len({e["label"] for e in entities}) == len(entities):
        raise GraphReviewError("G04 requires ambiguous label across distinct entity IDs")
    if family == "G06":
        limits = _exact(reference["limits"], {"max_hops", "result_limit", "claim_exhaustive"}, "limits")
        if (limits["max_hops"] != 3 or type(limits["result_limit"]) is not int
                or limits["result_limit"] < 1 or limits["claim_exhaustive"] is not False):
            raise GraphReviewError("G06 needs fixed bounds and no exhaustiveness claim")
    elif reference["limits"] is not None:
        raise GraphReviewError("limits only apply to G06")
    absence = reference["absence_review"]
    if family == "G05":
        _exact(absence, {"finding", "reviewed_pages"}, "absence_review")
        if absence["finding"] not in {"documented_absent", "documented_present", "unresolved"}:
            raise GraphReviewError("G05: invalid finding")
        if absence["finding"] == "unresolved":
            raise GraphReviewError("G05 unresolved cannot be a resolved reference")
        checked = _list(absence["reviewed_pages"], "absence_review.reviewed_pages")
        checked_ids = []
        for item in checked:
            _exact(item, {"doc_id", "page"}, "reviewed page")
            if item["doc_id"] not in selected or type(item["page"]) is not int or item["page"] not in docs[item["doc_id"]]["pages"]:
                raise GraphReviewError("G05 reviewed page not in verified corpus")
            checked_ids.append((item["doc_id"], item["page"]))
        _unique(checked_ids, "G05 reviewed pages")
        if absence["finding"] == "documented_absent" and set(checked_ids) != {
                (doc_id, page) for doc_id in selected for page in docs[doc_id]["pages"]}:
            raise GraphReviewError("G05 documentary absence needs complete declared page scope")
        if absence["finding"] == "documented_absent" and edges:
            raise GraphReviewError("G05 absent finding cannot cite expected edges")
        if absence["finding"] == "documented_present" and (not edges or not passages):
            raise GraphReviewError("G05 present finding needs a documented relation")
    elif absence is not None:
        raise GraphReviewError("absence_review only applies to G05")
    control = reference["control_expected"]
    if family in {"T01", "T02"}:
        if edges or not passages:
            raise GraphReviewError("controls require documentary passages and no graph edges")
        _exact(control, {"kind", "documents"}, "control_expected")
        if control["kind"] != ("inventory" if family == "T01" else "summaries"):
            raise GraphReviewError("control kind invalid")
        rows = _list(control["documents"], "control_expected.documents")
        if family == "T01":
            for row in rows:
                _exact(row, {"doc_id", "name"}, "inventory document")
                _text(row["name"], "inventory name")
                if row["doc_id"] not in docs or row["name"] != docs[row["doc_id"]]["name"]:
                    raise GraphReviewError("inventory name differs from snapshot manifest")
        else:
            for row in rows:
                _exact(row, {"doc_id", "fr", "en"}, "summary document")
                _text(row["fr"], "French document summary")
                _text(row["en"], "English document summary")
        if len(rows) != len(selected) or {row["doc_id"] for row in rows} != set(selected):
            raise GraphReviewError("control must cover every selected document exactly once")
        if {p["doc_id"] for p in passages} != set(selected):
            raise GraphReviewError("control passages must cover every document")
    elif control is not None:
        raise GraphReviewError("control_expected only applies to T01/T02")


def validate_private_packet(packet: dict, templates: list[dict], packet_root: str | Path) -> dict:
    """Verify local source bytes and references; unresolved families remain counted."""
    _exact(packet, {"schema_version", "snapshot", "documents", "families"}, "packet")
    if packet["schema_version"] != PACKET_VERSION:
        raise GraphReviewError("private packet schema version invalid")
    snapshot = _exact(packet["snapshot"], {"id", "path", "sha256", "before_revision",
                                           "after_revision", "scope_validation"}, "snapshot")
    _text(snapshot["id"], "snapshot.id")
    _hash(snapshot["sha256"], "snapshot.sha256")
    if snapshot["before_revision"] != BEFORE_REVISION or snapshot["after_revision"] != AFTER_REVISION:
        raise GraphReviewError("snapshot comparison revisions differ from #805 pair")
    root = Path(packet_root)
    _verified_file(root, snapshot["path"], snapshot["sha256"], "snapshot")
    docs = _document_index(packet, root)
    scope_consistent = _scope_validation(snapshot["scope_validation"], root, docs)
    families: dict[str, dict] = {}
    for item in _list(packet["families"], "families"):
        _exact(item, {"family_id", "split", "status", "bindings", "document_ids", "reference"}, "family")
        family = item["family_id"]
        if family not in FAMILIES or family in families:
            raise GraphReviewError("unknown or duplicate family")
        if item["split"] not in {"unassigned", "calibration", "test"}:
            raise GraphReviewError("invalid family split")
        if item["status"] not in {"unresolved", "resolved", "synthetic_control"}:
            raise GraphReviewError("invalid family status")
        selected = item["document_ids"]
        if not isinstance(selected, list) or any(doc_id not in docs for doc_id in selected):
            raise GraphReviewError("family references an unknown document")
        _unique(selected, "family documents")
        if family in {"G05", "T01", "T02"} and set(selected) != set(docs):
            raise GraphReviewError("global document question must cover the entire packet corpus")
        bindings = item["bindings"]
        if not isinstance(bindings, dict):
            raise GraphReviewError("bindings must be an object")
        expected_slots = {row["language"]: set(row["slots"]) for row in templates if row["family_id"] == family}
        if set(bindings) != set.union(*expected_slots.values()):
            raise GraphReviewError("bindings do not match family template slots")
        for key, value in bindings.items():
            _text(key, "binding key")
            _text(value, "binding value")
        if item["status"] == "unresolved":
            if item["reference"] is not None:
                raise GraphReviewError("unresolved family must have null reference")
        elif item["status"] == "synthetic_control":
            if family != "G04" or item["reference"] is not None or selected:
                raise GraphReviewError("G04 synthetic control must have no real reference/documents")
        else:
            if not selected or item["split"] == "unassigned":
                raise GraphReviewError("resolved family needs documents and assigned split")
            _reference(item["reference"], family, docs, selected, bindings)
        families[family] = item
    document_splits: dict[str, str] = {}
    for item in families.values():
        if item["split"] == "unassigned":
            continue
        for doc_id in item["document_ids"]:
            old = document_splits.setdefault(doc_id, item["split"])
            if old != item["split"]:
                raise GraphReviewError("document crosses splits")
    resolved = sum(item["status"] == "resolved" for item in families.values())
    synthetic = sum(item["status"] == "synthetic_control" for item in families.values())
    reviewed = sum(item["status"] == "resolved" and item["reference"]["status"] == "human_reviewed"
                   for item in families.values())
    return {"status": "ready_for_review" if resolved == 8 and scope_consistent else "not_ready",
            "families_total": 8, "families_resolved": resolved,
            "families_synthetic_control": synthetic, "families_human_reviewed": reviewed, "cases_total": 16,
            "cases_materialized": 2 * resolved, "cases_scored": 0,
            "scope_evidence_consistency": "matched" if scope_consistent else "not_supplied",
            "scope_execution_status": "not_verified_by_bench", "corpus_qualified": False,
            "absence_completeness": "not_verified_by_bench",
            "evaluation_status": "not_run", "product_C": "not_implemented"}


def materialize_graph_review(packet_path: str | Path, output_dir: str | Path,
                             templates_path: str | Path = TEMPLATES) -> dict:
    """Create a new private review archive, separating requests and annotations."""
    packet_path = Path(packet_path).resolve()
    target = Path(output_dir).resolve()
    private_roots = [ROOT / "results", ROOT / "datasets/private", ROOT / "data/private"]
    if not any(packet_path.is_relative_to(root.resolve()) for root in private_roots):
        raise GraphReviewError("private packet must be in an ignored private directory")
    if not target.is_relative_to((ROOT / "results").resolve()):
        raise GraphReviewError("review archive must be under ignored results/")
    if target.exists():
        raise GraphReviewError("review output already exists")
    templates, digest = load_graph_templates(templates_path)
    try:
        packet_raw = packet_path.read_bytes()
        packet = _strict_json(packet_raw)
    except (OSError, UnicodeError, ValueError) as exc:
        raise GraphReviewError("invalid or unreadable private packet") from exc
    summary = validate_private_packet(packet, templates, packet_path.parent)
    families = {item["family_id"]: item for item in packet["families"]}
    requests, annotations = [], []
    snapshot = packet["snapshot"]
    common_scope = {"snapshot_id": snapshot["id"], "snapshot_sha256": snapshot["sha256"],
                    "document_ids": sorted(doc["doc_id"] for doc in packet["documents"]),
                    "document_sha256": {doc["doc_id"]: doc["sha256"] for doc in packet["documents"]},
                    "tenant_scope_sha256": snapshot["scope_validation"]["tenant_scope_sha256"],
                    "folder_scope_sha256": snapshot["scope_validation"]["folder_scope_sha256"]}
    for row in templates:
        item = families.get(row["family_id"])
        if item is None or item["status"] != "resolved":
            continue
        message = row["template"].format_map(item["bindings"])
        _text(message, "materialized request")
        reference = item["reference"]
        if (any(len(p["quote"]) >= 16 and p["quote"] in message for p in reference["passages"])
                or len(reference["conclusion"]) >= 16 and reference["conclusion"] in message):
            raise GraphReviewError("reference text leaked into candidate request")
        request = {"case_id": row["case_id"], "family_id": row["family_id"],
                   "language": row["language"], "split": item["split"],
                   "candidate_input": {"message": message, "scope": deepcopy(common_scope)}}
        if any(key in request["candidate_input"] for key in ("reference", "annotations", "expected")):
            raise GraphReviewError("annotation leaked to candidate input")
        requests.append(request)
        annotations.append({"case_id": row["case_id"], "family_id": row["family_id"],
                            "snapshot_id": packet["snapshot"]["id"],
                            "document_ids": item["document_ids"], "reference": item["reference"],
                            "status": item["status"]})
    requests_raw = (json.dumps(requests, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    references_raw = (json.dumps(annotations, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    summary = {**summary, "schema_version": "deposium.graph-review-preparation/v1",
               "template_sha256": digest, "snapshot_sha256": packet["snapshot"]["sha256"],
               "packet_sha256": sha256(packet_raw).hexdigest(),
               "requests_sha256": sha256(requests_raw).hexdigest(),
               "references_sha256": sha256(references_raw).hexdigest(),
               "model_calls": 0, "service_calls": 0}
    try:
        target.mkdir(parents=True, exist_ok=False, mode=0o700)
    except OSError as exc:
        raise GraphReviewError("review output already exists or cannot be created") from exc
    def write(name: str, raw: bytes) -> None:
        fd = os.open(target / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(raw)
    write("packet.json", packet_raw)
    write("requests.json", requests_raw)
    write("references.private.json", references_raw)
    write("summary.json", (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return summary
