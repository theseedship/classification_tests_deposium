#!/usr/bin/env python3
"""Check frozen grids and shared scorers offline; never judge or run a model.

The controls deliberately know the authored references. Passing establishes
implementation/reference consistency, not semantic truth or human review.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deposium_bench import capability_corpus, passage_corpus
from deposium_bench import passage_dataset as passages
from deposium_bench.cases import load_cases
from deposium_bench.scoring import SCORER_VERSION, score_case, summarize
from deposium_bench.tool_plan import validate_output
from deposium_bench.tool_discovery import OUTPUT_VERSION as DISCOVERY_OUTPUT, validate_output as validate_discovery_output


class AuditError(ValueError):
    """A declared, nonempty implementation check failed."""


def require(condition, message):
    if not condition:
        raise AuditError(message)


def read_json(root, relative):
    try:
        return json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise AuditError(f"{relative}: missing or invalid public JSON") from None


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_choice_pack(cases, *, source, digest, reference_check):
    """Exercise actual shared scorers, rather than implementing a second one."""
    require(isinstance(cases, list) and bool(cases), f"{source}: zero cases")
    positive = wrong = empty = 0

    def control(case, output, expected):
        result = score_case(case, {"status": "ok", "output": output})
        require(isinstance(result, dict) and result.get("scored") is True
                and result.get("passed") is expected, f"{source}: scorer control failed")

    for case in cases:
        assertion = case["reference"]["assertions"]
        if case["contract_id"] == "bench.context-choice":
            require(len(assertion) == 1 and assertion[0]["path"] == "/choice_id"
                    and assertion[0]["op"] == "equals", f"{source}: unsupported choice reference")
            target = assertion[0]["value"]
            options = case["input"]["options"]
            require(len(options) == 4 and sum(o["id"] == target for o in options) == 1,
                    f"{source}: no unique reference choice")
            for option in options:
                expected = option["id"] == target
                control(case, {"choice_id": option["id"]}, expected)
                positive += expected
                wrong += not expected
        elif case["contract_id"] == "bench.tool-plan":
            require(len(assertion) == 1 and assertion[0]["path"] == ""
                    and assertion[0]["op"] == "one_of" and len(assertion[0]["value"]) == 2,
                    f"{source}: unsupported plan reference")
            for proposal in assertion[0]["value"]:
                control(case, proposal, True)
                positive += 1
            premature = deepcopy(assertion[0]["value"][0])
            premature["decision"] = "success"
            control(case, premature, False)
            bad_value = deepcopy(assertion[0]["value"][0])
            bad_value["calls"][0]["arguments"]["field"] = "quantity"
            validate_output(bad_value, case["input"])
            control(case, bad_value, False)
            wrong += 2
        elif case["contract_id"] == "bench.tool-discovery":
            require(len(assertion) == 1 and assertion[0]["path"] == "/selection"
                    and assertion[0]["op"] == "one_of", f"{source}: unsupported discovery reference")
            for selection in assertion[0]["value"]:
                proposal = {"schema_version": DISCOVERY_OUTPUT,
                            "shortlist": list(selection["tool_ids"]),
                            "selection": deepcopy(selection)}
                control(case, proposal, True)
                positive += 1
            if assertion[0]["value"][0]["decision"] == "select":
                wrong_selection = {"decision": "clarify", "tool_ids": [], "reason": "missing_information"}
            else:
                available = [t["tool_id"] for t in case["input"]["catalogue"] if t["eligible"] and t["available"]]
                require(bool(available), f"{source}: missing typed negative control")
                wrong_selection = {"decision": "select", "tool_ids": available[:1], "reason": "ready"}
            bad = {"schema_version": DISCOVERY_OUTPUT,
                   "shortlist": list(wrong_selection["tool_ids"]), "selection": wrong_selection}
            validate_discovery_output(bad, case["input"])
            control(case, bad, False)
            bad = deepcopy(proposal)
            bad["selection"]["decision"] = "success"
            control(case, bad, False)
            wrong += 2
        else:
            raise AuditError(f"{source}: unqualified audit contract")
        for output in ({}, None):
            control(case, output, False)
            empty += 1

    size = len(cases)
    require(positive > 0 and wrong > 0 and empty > 0, f"{source}: empty control denominator")
    status_counts = {}
    for status in ("missing", "unsupported", "error", "timeout"):
        predictions = [] if status == "missing" else [
            {"case_id": case["case_id"], "status": status} for case in cases]
        metrics = summarize(cases, predictions)
        require(metrics["total_cases"] == size and metrics["scored_cases"] == 0
                and metrics["passed_cases"] == 0 and metrics["verdict"] == "invalid"
                and metrics["counts_by_status"][status] == size,
                f"{source}: failed/missing outcomes escaped denominator")
        status_counts[status] = size
    abstain = summarize(cases, [{"case_id": case["case_id"], "status": "abstain"} for case in cases])
    require(abstain["total_cases"] == size and abstain["scored_cases"] == size
            and abstain["passed_cases"] == 0 and abstain["verdict"] == "fail"
            and abstain["counts_by_status"]["abstain"] == size,
            f"{source}: technical abstention passed")
    return {"source": source, "sha256": digest, "cases": size,
            "families": len({c["translation_family"] for c in cases}),
            "languages": dict(sorted(Counter(c["language"] for c in cases).items())),
            "reference_check": reference_check,
            "positive_controls": positive, "wrong_controls": wrong, "empty_controls": empty,
            "unscored_controls": 4 * size,
            "accounting_probes": {"total_cases_per_probe": size,
                                  "counts_by_status": status_counts, "abstain_controls": size}}


def check_passage_pack(cases, digest, selected_ids):
    require(isinstance(cases, list) and bool(cases), "passages: zero cases")
    selected = [case for case in cases if case["case_id"] in selected_ids]
    require(len(selected_ids) == len(selected) == 32, "passages: missing or empty control subset")
    totals = {"ranking": len(cases)}
    controls = {}
    for axis, labels in passages.CHOICE_LABELS.items():
        totals[axis] = len(passages.export_requests(cases, projection=axis))
        requests = passages.export_requests(selected, projection=axis)
        size = len(requests)
        require(size > 0, "passages: zero decision denominator")
        identities = [{key: row[key] for key in ("case_id", "axis", "passage_id", "claim_id")
                       if key in row} for row in requests]
        missing = passages.score_choices(selected, [], axis)
        require(missing["total_cases"] == size and missing["scored_cases"] == 0
                and missing["scoring_status"] == "no_scored_predictions"
                and missing["counts_by_status"]["missing"] == size
                and missing["accuracy_over_all"] == 0, "passages: missing denominator failed")
        positive = wrong = 0
        for choice_id, label in labels.items():
            predictions = [{**identity, "status": "ok", "choice_id": choice_id} for identity in identities]
            report = passages.score_choices(selected, predictions, axis)
            require(report["total_cases"] == size and report["scored_cases"] == size
                    and len(report["rows"]) == size, "passages: scorer control denominator failed")
            expected_correct = 0
            for original, scored in zip(missing["rows"], report["rows"], strict=True):
                expected = int(original["expected_label"] == label)
                require(type(scored["accuracy"]) is int and scored["accuracy"] == expected,
                        "passages: scorer accepted a wrong choice or rejected its reference")
                expected_correct += expected
                positive += expected
                wrong += not expected
            require(report["accuracy_over_all"] == expected_correct / size,
                    "passages: aggregate accuracy drift")
        require(positive == size and wrong == size * (len(labels) - 1), "passages: incomplete choice grid")
        empty = 0
        # Fail-fast validators stop on the first malformed prediction. Report
        # two probes, not a fictitious per-decision empty-output denominator.
        for value in (None, ""):
            try:
                passages.score_choices(selected, [{**identities[0], "status": "ok", "choice_id": value}], axis)
            except ValueError:
                empty += 1
            else:
                raise AuditError("passages: empty choice was accepted")
        status_counts = {"missing": size}
        for status in ("unsupported", "error", "timeout"):
            report = passages.score_choices(selected, [{**identity, "status": status} for identity in identities], axis)
            require(report["total_cases"] == size and report["scored_cases"] == 0
                    and report["counts_by_status"][status] == size
                    and report["scoring_status"] == "no_scored_predictions"
                    and report["accuracy_over_all"] == 0, "passages: failure denominator failed")
            status_counts[status] = size
        controls[axis] = {"total_decisions": size, "positive_controls": positive,
                          "wrong_controls": wrong, "empty_controls": empty,
                          "empty_control_scope": "first_request_only",
                          "unscored_controls": 4 * size, "accounting_counts_by_status": status_counts}
    return {"source": "datasets/passage-evidence-v1/cases.jsonl", "sha256": digest,
            "cases": len(cases), "families": len({c["family_id"] for c in cases}),
            "question_languages": dict(sorted(Counter(c["question_language"] for c in cases).items())),
            "passage_languages": dict(sorted(Counter(c["passage_language"] for c in cases).items())),
            "reference_check": "frozen_agent_reference_and_visible_span_consistency",
            "projection_decisions": totals,
            "control_subset": {"source": "plans/reference-review-pilot-v1.json", "cases": len(selected),
                               "families": len({c["family_id"] for c in selected}),
                               "selection": "existing_fixed_strata_no_model_outputs", "fresh_held_out": False},
            "choice_controls": controls,
            "ranking_scorer_controls": {"status": "not_run_by_this_check", "cases_tested": 0}}


def audit(root=ROOT):
    root = Path(root)
    specs = (
        ("context-choice-v1", 132, "programmatic_science_oracles_and_frozen_agent_documentary_references"),
        ("physics-choice-v1", 48, "programmatic_oracle_consistency"),
        ("capability-choice-v1", 192, "frozen_agent_reference_consistency"),
        ("tool-plan-pilot-v1", 2, "frozen_agent_alternative_plan_consistency"),
        ("tool-discovery-v1", 12, "frozen_agent_minimal_set_reference_consistency"),
    )
    packs, hashes = [], {}
    for name, expected_count, kind in specs:
        source = f"datasets/{name}/cases.jsonl"
        manifest_path = f"datasets/{name}/manifest.json"
        try:
            cases, digest = load_cases(root / source)
        except (OSError, ValueError):
            raise AuditError(f"{source}: corpus could not be validated") from None
        require(len(cases) == expected_count, f"{source}: missing cases")
        manifest = read_json(root, manifest_path)
        require(manifest.get("cases_sha256") == digest, f"{source}: manifest hash mismatch")
        hashes[source], hashes[manifest_path] = digest, sha256(root / manifest_path)
        packs.append(check_choice_pack(cases, source=source, digest=digest, reference_check=kind))
    frozen = capability_corpus.check_dataset()
    require(frozen["cases_sha256"] == packs[2]["sha256"], "capability: canonical corpus mismatch")
    passage_source = "datasets/passage-evidence-v1/cases.jsonl"
    try:
        cases, digest = passages.load_dataset(root / passage_source)
    except (OSError, ValueError):
        raise AuditError("passages: corpus could not be validated") from None
    regenerated = passage_corpus.build_cases()
    require(len(cases) == len(regenerated) == 1536
            and hashlib.sha256(passage_corpus.encode_cases(regenerated)).hexdigest() == digest,
            "passages: frozen regeneration mismatch")
    hashes[passage_source] = digest
    hashes["datasets/passage-evidence-v1/manifest.json"] = sha256(root / "datasets/passage-evidence-v1/manifest.json")
    plan_path = "plans/reference-review-pilot-v1.json"
    plan = read_json(root, plan_path)
    hashes[plan_path] = sha256(root / plan_path)
    require(plan.get("source_sha256", {}).get(passage_source) == digest,
            "passages: control-plan source mismatch")
    selected_ids = {row["case_id"] for row in plan["cases"] if row["dataset"] == "passage"}
    passage_report = check_passage_pack(cases, digest, selected_ids)
    # Execution fixtures have a different evidence boundary. Validate their
    # sources here; only their explicit profile run executes the local tools.
    execution_source = "datasets/tool-arguments-v1/cases.jsonl"
    execution_manifest = "datasets/tool-arguments-v1/manifest.json"
    execution_cases, execution_digest = load_cases(root / execution_source)
    execution = read_json(root, execution_manifest)
    require(len(execution_cases) == 4 and execution["cases_sha256"] == execution_digest,
            "tool-arguments: missing cases or manifest mismatch")
    hashes[execution_source] = execution_digest
    hashes[execution_manifest] = sha256(root / execution_manifest)
    for field, public_path in (("control_profile", "profiles/tool-arguments-control.json"),
                               ("control_recordings", "fixtures/tool-arguments-control.jsonl")):
        require(execution[field] == public_path
                and execution[field + "_sha256"] == sha256(root / public_path),
                "tool-arguments: control source mismatch")
        hashes[public_path] = sha256(root / public_path)
    execution_report = {"source": execution_source, "sha256": execution_digest,
                        "cases": 4, "families": len({c["translation_family"] for c in execution_cases}),
                        "reference_check": "bounded_fixture_and_exact_integer_reference_consistency",
                        "tool_execution": "not_run_by_this_check", "scorer_controls": "not_run_by_this_check"}
    # Fingerprint the implementation actually imported from this checkout,
    # separately from data read through the testable root parameter.
    for name in ("cases.py", "scoring.py", "research_corpus.py", "physics_corpus.py",
                 "capability_corpus.py", "tool_plan.py", "passage_dataset.py",
                 "passage_corpus.py", "choice_protocol.py", "registry.py", "tool_discovery.py",
                 "tool_arguments.py", "synthetic_tools.py"):
        relative = "deposium_bench/" + name
        hashes[relative] = sha256(ROOT / relative)
    hashes["scripts/check-reference-grids.py"] = sha256(Path(__file__))
    return {"schema_version": "deposium.reference-grid-check/v1",
            "status": "implementation_checks_passed", "control_kind": "scripted_not_model",
            "scorer_version": SCORER_VERSION,
            "runtime": {"implementation": sys.implementation.name,
                        "python": ".".join(map(str, sys.version_info[:3]))},
            "semantic_truth": "not_established_by_this_check",
            "human_review": {"provided_by_this_check": 0, "status": "not_provided"},
            "model_inference": "not_run", "choice_packs": packs, "passage_pack": passage_report,
            "execution_fixtures": [execution_report],
            "sources_sha256": dict(sorted(hashes.items()))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        report = audit()
    except (AuditError, OSError, ValueError, KeyError, TypeError):
        parser.exit(2, "Reference-grid implementation checks failed; no semantic or model qualification follows.\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
