#!/usr/bin/env python3
"""Prepare a reference-review pilot offline; never run or inspect a model."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "plans/reference-review-pilot-v1.json"
TEMPLATE = ROOT / "templates/reference-review-assessment.json"
SOURCES = {
    "physics": "datasets/physics-choice-v1/cases.jsonl",
    "passage": "datasets/passage-evidence-v1/cases.jsonl",
}
# Declared law/unit strata, not selected from any model's successes or errors.
PHYSICS = (
    "physics-uniform-distance", "physics-kinetic-energy",
    "physics-parallel-resistance", "physics-wave-speed", "physics-thin-lens",
    "physics-thermal-mixing", "physics-hydrostatic-pressure", "physics-missing-mass",
)
SCENARIOS = (
    "component_relation_collision", "variant_scope", "unit_condition_collision",
    "negation_exception", "distributed_binding", "missing_evidence",
    "conflicting_evidence", "heading_value_truncation",
)
BLANK = {
    "status": "not_started", "actor_type": None, "reviewer_alias": None,
    "judgment": None, "explanation": None, "wording_status": None,
    "wording_notes": None, "prior_exposure": None, "evidence_quotes": [],
}


class ReviewError(ValueError):
    """The plan, packet, or declared review is invalid."""


def require(condition, message):
    if not condition:
        raise ReviewError(message)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def jsonl(rows):
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def sources():
    data = {name: read_rows(ROOT / path) for name, path in SOURCES.items()}
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
              for path in SOURCES.values()}
    return data, hashes


def build_plan():
    """Build a deterministic diagnostic roster using authored strata only."""
    data, hashes = sources()
    selected = []
    for scenario in PHYSICS:
        for language in ("fr", "en"):
            matches = [c for c in data["physics"]
                       if c["scenario_id"] == scenario and c["language"] == language]
            require(len(matches) == 1, "Physics stratum is absent or ambiguous")
            c = matches[0]
            selected.append({"dataset": "physics", "case_id": c["case_id"],
                             "family_id": c["translation_family"], "stratum": scenario,
                             "language": language, "view": "full", "split": c["split"]})
    for scenario in SCENARIOS:
        # One lexicographically first existing family per authored scenario.
        # All translations/views keep their original split; no repartition occurs.
        family = min(c["family_id"] for c in data["passage"] if c["scenario_id"] == scenario)
        for language in ("fr", "en"):
            for view in ("full", "head_384"):
                matches = [c for c in data["passage"] if c["family_id"] == family
                           and c["question_language"] == c["passage_language"] == language
                           and c["view"] == view and c["provenance"]["position_rotation"] == 0]
                require(len(matches) == 1, "Passage stratum is absent or ambiguous")
                c = matches[0]
                selected.append({"dataset": "passage", "case_id": c["case_id"],
                                 "family_id": family, "stratum": scenario,
                                 "language": language, "view": view, "split": c["split"]})
    for index, row in enumerate(selected, 1):
        row["review_id"] = f"V{index:03d}"
        row["review_status"] = "not_started"
    return {"schema_version": "deposium.reference-review-pilot/v1",
            "purpose": "diagnostic_review_of_existing_agent_authored_v1_references",
            "human_review_status": "not_started", "human_judgments": 0,
            "selection": "declared_physics_laws_and_first_family_per_passage_scenario; no_model_outputs",
            "fresh_held_out": False, "source_sha256": hashes, "cases": selected}


def validate_plan(path=PLAN):
    plan = json.loads(Path(path).read_text())
    require(plan == build_plan(), "Plan differs from deterministic selection or source hashes")
    require(json.loads(TEMPLATE.read_text()) == BLANK, "Blank template must remain unassessed")
    return plan


def packet(plan):
    """Return reviewer inputs, empty assessments and coordinator-only references."""
    data, _ = sources()
    by_id = {kind: {c["case_id"]: c for c in rows} for kind, rows in data.items()}
    inputs, assessments, references = [], [], []
    for selected in plan["cases"]:
        c = by_id[selected["dataset"]][selected["case_id"]]
        rid = selected["review_id"]
        visible = {"review_id": rid, "task": selected["dataset"],
                   "language": selected["language"], "view": selected["view"]}
        reference = {"review_id": rid, "source_case_id": c["case_id"],
                     "reference_method": "agent_authored_pending_human", "judgments": []}

        def add(suffix, allowed, expected, text=None):
            jid = f"{rid}.{suffix}"
            assessments.append({"judgment_id": jid, **BLANK, "evidence_quotes": []})
            reference["judgments"].append({"judgment_id": jid, "allowed": allowed,
                                           "authored_reference": expected, "evidence_text": text})

        if selected["dataset"] == "physics":
            visible["input"] = c["input"]
            expected = next(a["value"] for a in c["reference"]["assertions"]
                            if a["path"] == "/choice_id")
            add("choice", [o["id"] for o in c["input"]["options"]], expected)
        else:
            ids = {p["id"]: f"p{i}" for i, p in enumerate(c["passages"], 1)}
            visible["query"] = c["query"]
            visible["passages"] = [{"id": ids[p["id"]], "text": p["text"]} for p in c["passages"]]
            visible["claims"] = [{"id": f"c{i}", "text": cl["text"]}
                                 for i, cl in enumerate(c["annotations"]["claims"], 1)]
            passages = {p["id"]: p["text"] for p in c["passages"]}
            for rel in c["annotations"]["relevance"]:
                pid = rel["passage_id"]
                add(f"relevance.{ids[pid]}", [0, 1, 2, 3], rel["grade"], passages[pid])
            for i, claim in enumerate(c["annotations"]["claims"], 1):
                for judgment in claim["judgments"]:
                    pid = judgment["passage_id"]
                    add(f"support.c{i}.{ids[pid]}", ["supports", "refutes", "insufficient"],
                        judgment["label"], passages[pid])
            add("answerability", ["answerable", "insufficient_visible_evidence",
                                  "conflicting_visible_evidence"], c["annotations"]["query_status"])
        inputs.append(visible)
        references.append(reference)
    return inputs, assessments, references


def coverage(plan):
    _, assessments, refs = packet(plan)
    judgments = [j for r in refs for j in r["judgments"]]
    return {"selected_inputs": len(plan["cases"]), "assessment_slots": len(assessments),
            "by_dataset": dict(Counter(c["dataset"] for c in plan["cases"])),
            "families_by_dataset": {d: len({c["family_id"] for c in plan["cases"] if c["dataset"] == d})
                                    for d in SOURCES},
            "language": dict(Counter(c["language"] for c in plan["cases"])),
            "passage_view": dict(Counter(c["view"] for c in plan["cases"] if c["dataset"] == "passage")),
            "split": dict(Counter(c["split"] for c in plan["cases"])),
            "authored_support_strata": dict(Counter(j["authored_reference"] for j in judgments
                                                    if ".support." in j["judgment_id"])),
            "authored_relevance_strata": dict(Counter(str(j["authored_reference"]) for j in judgments
                                                      if ".relevance." in j["judgment_id"])),
            "authored_answerability_strata": dict(Counter(j["authored_reference"] for j in judgments
                                                          if j["judgment_id"].endswith(".answerability"))),
            "human_review_status": "not_started", "human_judgments": 0}


def export_packet(plan, output):
    output = Path(output).resolve()
    require(output.is_relative_to((ROOT / "results").resolve()) and output != (ROOT / "results").resolve(),
            "Generated packets must be in a new ignored results/ subdirectory")
    require(not output.exists(), "Refusing to overwrite an existing packet")
    inputs, assessments, refs = packet(plan)
    (output / "reviewer").mkdir(parents=True)
    (output / "coordinator").mkdir()
    (output / "reviewer/inputs.jsonl").write_text(jsonl(inputs))
    (output / "reviewer/assessments.jsonl").write_text(jsonl(assessments))
    (output / "reviewer/INSTRUCTIONS.md").write_text((ROOT / "docs/REFERENCE_REVIEW_PILOT.md").read_text())
    (output / "coordinator/authored-references.jsonl").write_text(jsonl(refs))
    (output / "coordinator/manifest.json").write_text(encode(plan))
    return coverage(plan)


def audit(plan, rows):
    """Validate declared human work; completion never follows from empty forms."""
    _, _, refs = packet(plan)
    expected = {j["judgment_id"]: j for r in refs for j in r["judgments"]}
    seen, complete = set(), 0
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"judgment_id", *BLANK}, "Unexpected assessment fields")
        jid = row["judgment_id"]
        require(jid in expected and jid not in seen, "Unknown or duplicate judgment_id")
        seen.add(jid)
        if row["status"] == "not_started":
            require({k: row[k] for k in BLANK} == BLANK, "Pending assessments must remain blank")
            continue
        require(row["status"] == "completed", "Unknown assessment status")
        require(row["actor_type"] == "human", "Agent/automation work is not human review")
        require(isinstance(row["reviewer_alias"], str)
                and re.fullmatch(r"reviewer-[A-Za-z0-9]{3,32}", row["reviewer_alias"]),
                "Use an opaque reviewer- alias, not a name or email")
        require(type(row["judgment"]) in (str, int)
                and any(type(row["judgment"]) is type(v) and row["judgment"] == v
                        for v in expected[jid]["allowed"]), "Invalid judgment for task")
        require(isinstance(row["explanation"], str) and row["explanation"].strip(), "Explanation required")
        require(row["wording_status"] in ("acceptable", "issue", "unable_to_assess"), "Wording assessment required")
        require(row["wording_notes"] is None or isinstance(row["wording_notes"], str), "Invalid wording notes")
        if row["wording_status"] == "issue":
            require(isinstance(row["wording_notes"], str) and row["wording_notes"].strip(), "Explain wording issues")
        require(row["prior_exposure"] in ("none_declared", "dataset_or_references", "model_results", "unknown"),
                "Declare prior exposure explicitly")
        quotes = row["evidence_quotes"]
        require(isinstance(quotes, list) and all(isinstance(q, str) and q.strip() for q in quotes),
                "Evidence quotes must be nonempty strings")
        text = expected[jid]["evidence_text"]
        require(not quotes or text is not None and all(q in text for q in quotes), "Quote must occur in visible passage")
        if ".support." in jid and row["judgment"] in ("supports", "refutes"):
            require(bool(quotes), "Support/refutation needs an exact visible quote")
        complete += 1
    total = len(expected)
    status = "completed" if complete == total else "in_progress" if complete else "not_started"
    return {"review_status": status, "expected_judgments": total,
            "submitted_rows": len(rows), "missing_rows": total - len(seen),
            "human_declared_judgments": complete, "pending_judgments": total - complete,
            "identity_verification": "not_provided_by_this_offline_tool",
            "reference_approval": "not_implied_by_assessment_completion"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="Check deterministic plan, blank template and source hashes")
    export = sub.add_parser("export", help="Create new ignored reviewer/coordinator packets")
    export.add_argument("--output", required=True, type=Path)
    check = sub.add_parser("audit", help="Exit nonzero unless every slot has a declared human assessment")
    check.add_argument("--assessments", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        plan = validate_plan()
        if args.command == "check":
            report = coverage(plan)
        elif args.command == "export":
            report = export_packet(plan, args.output)
        else:
            report = audit(plan, read_rows(args.assessments))
        print(encode(report), end="")
        return 1 if args.command == "audit" and report["review_status"] != "completed" else 0
    except (ReviewError, OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"reference review error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
