"""Measure proposed graph-edge exposure from sealed, offline observations.

This is an engineering retrieval measure against unapproved proposals. It does
not judge whether an edge or a passage is supported by the source document.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

from .adapters import _json as _strict_json
from .graph_document import validate_plan
from .graph_evidence import (
    GraphEvidenceError, _capture_index, _edge_lists, _locator, _private,
    _read, _sealed_observation, _truncation, _write,
)
from .graph_snapshot import audit_snapshot, _sha


class GraphMeasurementError(GraphEvidenceError):
    """The inputs cannot support a comparable proposal measurement."""


def _reference_edges(packet: dict, documents: dict, relations: dict) -> dict:
    """Resolve references through passage, document and composite relation key."""
    by_id = defaultdict(list)
    for key in relations:
        by_id[key[0]].append(key)
    families = {}
    for family in packet["families"]:
        name = family["family_id"]
        reference = family.get("reference") or {}
        passages = {p["id"]: p for p in reference.get("passages", [])}
        if len(passages) != len(reference.get("passages", [])):
            raise GraphMeasurementError("graph measurement: duplicate reference passage")
        edges = []
        for edge in reference.get("edges", []):
            matches = by_id.get(edge["id"], [])
            if len(matches) != 1:
                raise GraphMeasurementError("graph measurement: reference relation ID not unique in capture")
            key = matches[0]
            row, stored = relations[key]["row"], relations[key]["properties"]
            if (row.get("source_id") != edge["source_id"]
                    or row.get("target_id") != edge["target_id"]
                    or not edge.get("passage_ids")):
                raise GraphMeasurementError("graph measurement: reference edge differs from capture")
            cited = []
            for passage_id in edge["passage_ids"]:
                passage = passages.get(passage_id)
                if passage is None or passage.get("doc_id") not in documents:
                    raise GraphMeasurementError("graph measurement: reference passage missing")
                cited.append((passage["doc_id"], passage["page"]))
            doc_ids = {doc_id for doc_id, _ in cited}
            if (len(doc_ids) != 1 or stored.get("doc_id") not in doc_ids
                    or documents[stored["doc_id"]]["folder_id"] != key[1]):
                raise GraphMeasurementError("graph measurement: reference edge document differs from capture")
            if any(page not in documents[doc_id]["pages"] for doc_id, page in cited):
                raise GraphMeasurementError("graph measurement: proposed page not in original")
            edges.append({"key": key, "doc_id": stored["doc_id"],
                          "pages": sorted({page for _, page in cited}),
                          "source_id": edge["source_id"], "target_id": edge["target_id"]})
        families[name] = {"bindings": family.get("bindings", {}), "edges": edges,
                          "status": family.get("status")}
    return families


def _eligibility(request: dict, family: dict, all_folders: set[str],
                 neighbor_centers: dict[tuple[str, str], set[str]] | None = None) -> tuple[str, list[dict]]:
    """Choose opportunities using only the frozen plan and proposed references."""
    edges = family["edges"]
    if family["status"] != "resolved" or not edges:
        return "no_resolved_edge_reference", []
    entry = request["entrypoint"]
    if entry not in {"helper", "strict_service"}:
        return "legacy_lacks_composite_locator", []
    value = request["input"]
    operation = value["operation"]
    if operation == "search":
        return "exploratory_node_search", []
    if operation not in {"path", "neighbors"}:
        return "operation_not_edge_targeted", []
    bindings = family["bindings"]
    center = bindings.get("dense_entity", bindings.get("A"))
    if value.get("entity") != center:
        return "different_center", []
    if operation == "path" and value.get("end_entity") != bindings.get("B"):
        return "different_path_endpoint", []
    selected = (value.get("folder_ids", all_folders) if entry == "helper"
                else request["service"].get("folder_ids", []))
    selected = set(selected)
    if not selected <= all_folders:
        raise GraphMeasurementError("graph measurement: plan selects uncaptured folder")
    if operation == "neighbors":
        center_id = value.get("entity_id")
        if center_id is None:
            matches = (neighbor_centers or {}).get((request["family_id"], value["entity"]), set())
            if len(matches) != 1:
                return "neighbor_center_not_uniquely_resolved_by_plan", []
            center_id = next(iter(matches))
        # G02 is a two-hop chain: the second edge does not touch its center.
        matching = [edge for edge in edges if edge["source_id"] == center_id
                    or edge["target_id"] == center_id]
    else:
        matching = edges
    eligible = [edge for edge in matching if edge["key"][1] in selected]
    return ("eligible", eligible) if eligible else ("reference_outside_selected_scope", [])


def _measure_opportunity(edge: dict, rendered: list, relations: dict, documents: dict,
                         owner: str, selected: set[str]) -> dict:
    exposed = verified = pages = False
    locator_states = Counter()
    for item in rendered:
        if not isinstance(item, dict) or item.get("id") != edge["key"][0]:
            continue
        # An ID seen alone is a weaker observation than the composite locator.
        exposed = True
        locator = _locator(item, relations, documents, owner, selected)
        locator_states[locator["status"]] += 1
        if tuple(locator.get("key") or ()) != edge["key"]:
            continue
        if locator.get("doc_id") == edge["doc_id"] and locator["status"] in {
                "rendered_pages_absent", "rendered_pages_invalid", "stored_pages_absent",
                "rendered_pages_not_stored", "original_page_absent",
                "locator_verified_pending_human"}:
            verified = True
        if (locator["status"] == "locator_verified_pending_human"
                and locator.get("doc_id") == edge["doc_id"]
                and set(edge["pages"]) <= {page["number"] for page in locator["pages"]}):
            pages = True
    return {"edge_id_exposed": exposed, "document_locator_verified": verified,
            "all_proposed_pages_rendered": pages, "locator_statuses": dict(locator_states)}


def measure_graph_proposals(archive: str | Path, observations: dict[str, str | Path],
                            output: str | Path) -> dict:
    """Write a new private archive and return only identifier-free aggregates.

    `observations` maps distinct run labels to sealed observation directories.
    Each run is measured independently; plans with different scopes are never
    pooled into a before/after denominator.
    """
    source, target = _private(archive), _private(output)
    if not source.is_dir() or target.exists() or not observations:
        raise GraphMeasurementError("graph measurement: source missing or destination already exists")
    roots = {label: _private(path) for label, path in observations.items()}
    if (len(roots) != len(observations) or any(not root.is_dir() for root in roots.values())
            or len(set(roots.values())) != len(roots)
            or any(target.is_relative_to(root) or root.is_relative_to(target)
                   for root in [source, *roots.values()])):
        raise GraphMeasurementError("graph measurement: observation paths overlap or are missing")
    producer_dependencies = {name: _sha(Path(__file__).with_name(name)) for name in (
        "graph_measurement.py", "graph_evidence.py", "graph_document.py",
        "graph_snapshot.py", "graph_review.py")}
    audit = audit_snapshot(source)
    if audit.get("status") != "archive_consistent":
        raise GraphMeasurementError("graph measurement: capture audit failed")
    packet_bytes = (source / "packet.json").read_bytes()
    packet = _strict_json(packet_bytes)
    scope = _read(source / "scope.private.json")
    owner = scope["owner_tenant_id"]
    folders = {str(folder) for folder in scope["folder_ids"]}
    documents, relations, original_hashes = _capture_index(source, packet, owner, folders)
    proposals = _read(source / "reference-proposals.private.json")
    if proposals.get("families") != packet.get("families"):
        raise GraphMeasurementError("graph measurement: proposals differ from captured packet")
    families = _reference_edges(packet, documents, relations)
    source_hashes = dict(audit["files_sha256"])
    source_hashes.update({name: _sha(source / name) for name in (
        "packet.json", "reference-proposals.private.json", "scope.private.json")})
    source_hashes.update({path.name: _sha(path) for path in sorted(source.glob("*.sql"))})
    for name, digest in original_hashes.items():
        source_hashes[name] = digest
    details = {}
    summaries = {}
    inventories = {}
    for label, root in roots.items():
        inventories[label] = _sealed_observation(root)
        if (root / "packet.private.json").read_bytes() != packet_bytes:
            raise GraphMeasurementError("graph measurement: observation packet differs")
        manifest = _read(root / "manifest.private.json")
        plan = _read(root / "plan.private.json")
        descriptor = manifest.get("snapshot", {})
        expected_counts = {kind: audit.get("public_summary", {}).get("snapshot_rows", {}).get(kind, 0)
                           for kind in ("entities", "relations", "pages", "enriched")}
        schema_path = Path(descriptor.get("schema_path", "")).resolve()
        if (manifest.get("packet_sha256") != sha256(packet_bytes).hexdigest()
                or manifest.get("plan_sha256") != _sha(root / "plan.private.json")
                or descriptor.get("sha256") != _sha(source / "snapshot.private.jsonl")
                or descriptor.get("path") != str((source / "snapshot.private.jsonl").resolve())
                or not schema_path.is_relative_to(source)
                or descriptor.get("schema_sha256") != audit["files_sha256"].get(schema_path.name)
                or descriptor.get("owner_tenant_id") != owner
                or {str(folder) for folder in descriptor.get("folder_ids", [])} != folders
                or descriptor.get("expected_counts") != expected_counts
                or plan.get("packet_sha256") != manifest.get("packet_sha256")
                or plan.get("snapshot_sha256") != descriptor.get("sha256")
                or manifest.get("repetitions") != 1):
            raise GraphMeasurementError("graph measurement: observation provenance differs")
        requests = validate_plan(plan, packet, manifest["packet_sha256"], scope)
        by_case = {request["case_id"]: request for request in requests}
        if len(by_case) != len(requests):
            raise GraphMeasurementError("graph measurement: duplicate case in plan")
        neighbor_centers = defaultdict(set)
        for request in requests:
            value = request["input"]
            if (value.get("operation") == "neighbors" and isinstance(value.get("entity_id"), str)
                    and isinstance(value.get("entity"), str)):
                neighbor_centers[(request["family_id"], value["entity"])].add(value["entity_id"])
        # Eligibility is frozen without inspecting any response or arm.
        eligibility = {}
        for request in requests:
            reason, edges = _eligibility(request, families[request["family_id"]], folders,
                                         neighbor_centers)
            eligibility[request["case_id"]] = {"reason": reason,
                "reference_keys": [list(edge["key"]) for edge in edges]}
        if not any(item["reference_keys"] for item in eligibility.values()):
            raise GraphMeasurementError("graph measurement: zero eligible reference opportunities")
        observations_by_key = {}
        lines = (root / "raw.private.jsonl").read_text(encoding="utf-8").split("\n")  # not splitlines(): U+2028
        if lines and lines[-1] == "":
            lines.pop()
        for line in lines:
            row = _strict_json(line)
            key = (row.get("arm"), row.get("case_id"), row.get("repetition"))
            if (key in observations_by_key or key[0] not in {"before", "after"}
                    or key[1] not in by_case or key[2] != 0
                    or row.get("family_id") != by_case[key[1]]["family_id"]
                    or row.get("entrypoint") != by_case[key[1]]["entrypoint"]):
                raise GraphMeasurementError("graph measurement: unexpected observation row")
            observations_by_key[key] = row
        if len(observations_by_key) != 2 * len(requests):
            raise GraphMeasurementError("graph measurement: incomplete observation series")
        outcomes = []
        for arm in ("before", "after"):
            for request in requests:
                case_id = request["case_id"]
                row = observations_by_key[(arm, case_id, 0)]
                response = row["response"]
                expected_source = manifest.get("sources", {}).get(arm, {}).get("files_sha256")
                runtime_capture = response.get("document_snapshot") if isinstance(response, dict) else None
                if (not isinstance(expected_source, dict) or not expected_source
                        or any(not isinstance(digest, str) or len(digest) != 64
                               for digest in expected_source.values())
                        or not isinstance(response, dict) or row.get("provenance_valid") is not True
                        or response.get("source_files_sha256") != expected_source
                        or not isinstance(runtime_capture, dict)
                        or runtime_capture.get("snapshot_sha256") != descriptor["sha256"]
                        or runtime_capture.get("schema_sha256") != descriptor["schema_sha256"]
                        or runtime_capture.get("expected_counts") != expected_counts
                        or runtime_capture.get("loaded_counts") != expected_counts
                        or response.get("network_attempts") != 0 or response.get("model_calls") != 0):
                    raise GraphMeasurementError("graph measurement: response provenance invalid")
                reason = eligibility[case_id]["reason"]
                if reason != "eligible":
                    continue
                selected = (request["input"].get("folder_ids", scope["folder_ids"])
                            if request["entrypoint"] == "helper"
                            else request["service"]["folder_ids"])
                value = response.get("output")
                rendered = _edge_lists(value) if isinstance(value, dict) else []
                if response.get("status") != "ok" or response.get("outcome") != "ok":
                    rendered = []
                for key in eligibility[case_id]["reference_keys"]:
                    ref = next(edge for edge in families[request["family_id"]]["edges"]
                               if edge["key"] == tuple(key))
                    measurement = _measure_opportunity(ref, rendered, relations, documents,
                                                       owner, {str(folder) for folder in selected})
                    outcomes.append({"arm": arm, "case_id": case_id,
                                     "family_id": request["family_id"], "reference_key": key,
                                     "transport_status": response.get("status"),
                                     "outcome": response.get("outcome"),
                                     "truncation": _truncation(value), **measurement})
        per_arm = {}
        for arm in ("before", "after"):
            cases = [x for x in outcomes if x["arm"] == arm]
            by_family = {}
            for family_id in sorted({x["family_id"] for x in cases}):
                family_rows = [x for x in cases if x["family_id"] == family_id]
                dedup = {}
                for row in family_rows:
                    state = dedup.setdefault(tuple(row["reference_key"]), {
                        "edge_id_exposed": False, "document_locator_verified": False,
                        "all_proposed_pages_rendered": False})
                    for metric in state:
                        state[metric] |= row[metric]
                by_family[family_id] = {
                    "eligible_cases": len({x["case_id"] for x in family_rows}),
                    "edge_case_opportunities": len(family_rows),
                    "distinct_reference_edges": len(dedup),
                    "opportunity_counts": {metric: sum(x[metric] for x in family_rows)
                                           for metric in next(iter(dedup.values()))},
                    "pool_counts": {metric: sum(x[metric] for x in dedup.values())
                                    for metric in next(iter(dedup.values()))},
                    "truncated_case_count": len({x["case_id"] for x in family_rows
                                                 if x["truncation"] == "truncated"}),
                }
            per_arm[arm] = by_family
        summaries[label] = {"plan_sha256": _sha(root / "plan.private.json"),
                            "requests": len(requests), "eligible_cases": sum(
                                x["reason"] == "eligible" for x in eligibility.values()),
                            "exclusions": dict(Counter(x["reason"] for x in eligibility.values()
                                                       if x["reason"] != "eligible")),
                            "arms": per_arm}
        details[label] = {"observation_path": str(root), "eligibility": eligibility,
                          "outcomes": outcomes}
    summary = {"schema_version": "deposium.graph-proposal-measurement/v1",
               "qualification": "mechanical_exposure_against_unapproved_proposals",
               "documentary_quality_scored": 0, "final_answers_scored": 0,
               "model_calls": 0, "thresholds": None, "runs": summaries,
               "limits": ["Same-plan arms only; scoped plan has a different denominator.",
                          "ID exposure does not prove document or page provenance.",
                          "A stored page locator does not prove that its passage supports the relation.",
                          "Search probes and legacy outputs are exploratory and excluded from primary eligibility."]}
    target.mkdir(mode=0o700)
    files = {"summary.json": json.dumps(summary, indent=2, ensure_ascii=False).encode() + b"\n",
             "measurement.private.json": json.dumps(details, indent=2, ensure_ascii=False).encode() + b"\n",
             "producer.graph_measurement.py": Path(__file__).read_bytes()}
    for name, raw in files.items():
        _write(target / name, raw)
    if (any(_sealed_observation(root) != inventories[label] for label, root in roots.items())
            or any(_sha(source / name) != digest for name, digest in source_hashes.items())
            or any(_sha(Path(__file__).with_name(name)) != digest
                   for name, digest in producer_dependencies.items())):
        raise GraphMeasurementError("graph measurement: source changed during measurement")
    seal = {"schema_version": "deposium.graph-proposal-measurement-seal/v1",
            "source_files_sha256": source_hashes,
            "observation_files_sha256": inventories,
            "producer_dependencies_sha256": producer_dependencies,
            "files": {name: sha256(raw).hexdigest() for name, raw in files.items()}}
    _write(target / "seal.json", json.dumps(seal, indent=2, sort_keys=True).encode() + b"\n")
    return summary
