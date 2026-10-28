#!/usr/bin/env python3
"""Balanced four-order passage report from sealed CPU and D3 observations."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.campaigns import _encode, _hash
from deposium_bench.passage_dataset import (CHOICE_LABELS, export_requests, load_dataset,
                                            score_choices, score_rankings, select_cases)
from deposium_bench.passage_observation import (_jsonl, _verified_files, compose_rankings)

_old_path = ROOT / "scripts/analyze-passage-pilot.py"
_spec = importlib.util.spec_from_file_location("passage_pilot_report_frozen", _old_path)
old = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(old)

DATASET_SHA256 = old.DATASET_SHA256
FULL_INPUT_SHA256 = "06e3321ef8397ea231d189245256c4145aefb14f2aaf55d6190eff71b037c1b9"
ROTATIONS = (0, 1, 2, 3)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def full_test_cases():
    cases, dataset_hash = load_dataset()
    if dataset_hash != DATASET_SHA256:
        raise ValueError("Frozen dataset changed")
    selected = select_cases(cases, split="test")
    counts = Counter(case["provenance"]["position_rotation"] for case in selected)
    if (len(selected) != 512 or counts != Counter({rotation: 128 for rotation in ROTATIONS})
            or len({case["family_id"] for case in selected}) != 8):
        raise ValueError("Four-order test selection changed")
    inputs = export_requests(selected, "ranking")
    payload = b"".join(_encode(request) for request in inputs)
    if _hash(payload) != FULL_INPUT_SHA256:
        raise ValueError("Frozen full-test ranking input hash changed")
    return selected, inputs, payload


def validate_full_baseline(cases, inputs, payload, predictions, native, manifest):
    """Verify exact sealed-input lineage and one measured CPU pool per case."""
    if (len(inputs) != 512 or payload != b"".join(_encode(request) for request in inputs)
            or _hash(payload) != FULL_INPUT_SHA256
            or manifest.get("input_sha256") != FULL_INPUT_SHA256
            or manifest.get("status") != "complete" or manifest.get("scores_observed") != 512
            or manifest.get("image") != old.IMAGE or manifest.get("model") != "bge-reranker-v2-m3"
            or manifest.get("running_binary_sha256") != old.CPU_BINARY_SHA256
            or manifest.get("cpu_binary", {}).get("sha256") != old.CPU_BINARY_SHA256
            or manifest.get("cpu_binary", {}).get("fingerprint_sha256") != old.CPU_FINGERPRINT_SHA256
            or manifest.get("cpu_proof", {}).get("provider") != "cpu"
            or manifest.get("container_cleanup") != "removed_with_anonymous_volumes"
            or manifest.get("mounted_artifact_sha256", {}).get(old.NATIVE_BINARY_PATH) != old.CPU_BINARY_SHA256
            or manifest.get("mounted_artifact_sha256", {}).get(old.MODEL_PATH) != old.MODEL_SHA256):
        raise ValueError("Balanced native CPU identity or input is unproven")
    profile = manifest.get("profile")
    if (not isinstance(profile, dict) or profile.get("top_k") != 4 or profile.get("max_seq_len") != 512
            or profile.get("cpus") != 2 or profile.get("memory_bytes") != 4 * 1024 ** 3
            or profile.get("network") != "none" or profile.get("gpu_devices") != 0
            or profile.get("rerank_session_pool") != 1):
        raise ValueError("Balanced native CPU resource profile changed")
    ids = [case["case_id"] for case in cases]
    if (len(predictions) != len(ids) or len(native) != len(ids)
            or [row.get("case_id") for row in inputs] != ids
            or [row.get("case_id") for row in predictions] != ids
            or [row.get("case_id") for row in native] != ids):
        raise ValueError("Balanced native CPU rows missing, duplicated, or reordered")
    for prediction, observation in zip(predictions, native):
        latency = observation.get("latency_ms")
        if (prediction.get("status") != "ok" or observation.get("status") != "ok"
                or prediction.get("ranking") != observation.get("ranking")
                or type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0):
            raise ValueError("Balanced native CPU prediction or cost trace differs")
    score_rankings(cases, predictions)  # exact full-pool permutations and identities


def replay_relevance(cases, choice_files):
    """Reuse only exact candidate-visible relevance inputs; no new model calls."""
    requests = export_requests(cases, "relevance")
    physical = _jsonl(choice_files["physical-requests.jsonl"])
    raw = _jsonl(choice_files["raw.jsonl"])
    if len(physical) != len(raw) or len(raw) != 728:
        raise ValueError("Original D3 physical trace incomplete")
    old.validate_choice_trace(physical, raw)
    calls = {record["call_id"]: record for record in raw}
    physical_by_id = {request["case_id"]: request for request in physical}
    if len(calls) != len(raw):
        raise ValueError("Duplicate D3 physical call")
    logical, used = [], set()
    for request in requests:
        call_id, choice_id = reuse_relevance_request(request, physical_by_id, calls)
        used.add(call_id)
        logical.append({"case_id": request["case_id"], "axis": "relevance",
                        "passage_id": request["passage_id"], "status": "ok",
                        "choice_id": choice_id, "source_call_id": call_id})
    if len(logical) != 2048 or len(used) != 264:
        raise ValueError("Rotated relevance replay cardinality changed")
    return logical, calls, used


def reuse_relevance_request(request, physical_by_id, calls):
    """Match a rotated logical ID solely through identical visible input."""
    identity = _hash(_encode({"contract_id": request["contract_id"], "input": request["input"]}))
    call_id = "call-" + identity
    record = calls.get(call_id)
    source_request = physical_by_id.get(call_id)
    if (record is None or source_request is None
            or source_request["contract_id"] != request["contract_id"]
            or source_request["input"] != request["input"]):
        raise ValueError("Rotated relevance input was never physically observed")
    response = record["response"]
    choice = response.get("output")
    if (response.get("status") != "ok" or not isinstance(choice, dict)
            or set(choice) != {"choice_id"} or choice["choice_id"] not in CHOICE_LABELS["relevance"]):
        raise ValueError("Rotated relevance choice absent or invalid")
    return call_id, choice["choice_id"]


def original_choice_confusion(choice_files):
    """Diagnostic precision and recall from original 128-case gold, never 512."""
    scores = json.loads(choice_files["scores.json"])
    predictions = _jsonl(choice_files["logical-predictions.jsonl"])
    result = {}
    for axis, expected_count in (("support", 768), ("answerability", 128)):
        labels = list(CHOICE_LABELS[axis].values())
        rows = scores[axis]["rows"]
        actual = {(row["case_id"], row["axis"], row.get("passage_id"), row.get("claim_id")): row
                  for row in predictions if row["axis"] == axis}
        if len(rows) != expected_count or len(actual) != expected_count:
            raise ValueError("Original choice diagnostic denominator changed")
        matrix = {str(gold): {str(pred): 0 for pred in labels} for gold in labels}
        failures = {str(gold): {} for gold in labels}
        for row in rows:
            key = (row["case_id"], row["axis"], row.get("passage_id"), row.get("claim_id"))
            observed = actual.pop(key, None)
            if observed is None or observed["status"] != row["status"]:
                raise ValueError("Original choice diagnostic identity differs")
            gold = str(row["expected_label"])
            if observed["status"] == "ok":
                predicted = str(CHOICE_LABELS[axis][observed["choice_id"]])
                matrix[gold][predicted] += 1
            else:
                counts = failures[gold]
                counts[observed["status"]] = counts.get(observed["status"], 0) + 1
        if actual:
            raise ValueError("Unmatched original choice predictions")
        per_class = {}
        for label in labels:
            name = str(label)
            true_positive = matrix[name][name]
            predicted_total = sum(matrix[gold][name] for gold in matrix)
            gold_total = sum(matrix[name].values()) + sum(failures[name].values())
            per_class[name] = {"true_positive": true_positive, "predicted": predicted_total,
                               "gold": gold_total, "precision": true_positive / predicted_total if predicted_total else None,
                               "recall_over_all": true_positive / gold_total if gold_total else None}
        result[axis] = {"source_cases": 128, "total_decisions": expected_count,
                        "confusion_gold_rows_predicted_columns": matrix,
                        "non_ok_by_gold": failures, "per_class": per_class}
    return result


def tie_summary(cases, relevance_rows):
    values = {(row["case_id"], row["passage_id"]): CHOICE_LABELS["relevance"][row["choice_id"]]
              for row in relevance_rows}
    rows = []
    for case in cases:
        grades = [values[(case["case_id"], passage["id"])] for passage in case["passages"]]
        rows.append({"case_id": case["case_id"], "rotation": case["provenance"]["position_rotation"],
                     "language_direction": case["question_language"] + "->" + case["passage_language"],
                     "scenario_id": case["scenario_id"], "view": case["view"],
                     "top_grade_tie": grades.count(max(grades)) > 1,
                     "any_grade_tie": len(set(grades)) < len(grades)})
    def summarize(group):
        return {"cases": len(group), "top_grade_ties": sum(row["top_grade_tie"] for row in group),
                "any_grade_ties": sum(row["any_grade_tie"] for row in group)}
    return {"overall": summarize(rows), "by": {axis: {str(value): summarize([row for row in rows if row[axis] == value])
                                                       for value in sorted({row[axis] for row in rows})}
                                             for axis in ("rotation", "language_direction", "scenario_id", "view")}}


def aggregate(choice_archive, original_baseline, balanced_baseline):
    original = old.aggregate(choice_archive, original_baseline)
    cases, ranking_inputs, expected_bytes = full_test_cases()
    files = _verified_files(balanced_baseline, {"ranking-inputs.jsonl", "predictions.jsonl",
                                              "native-rows.jsonl", "manifest.json"})
    if files["ranking-inputs.jsonl"] != expected_bytes:
        raise ValueError("Balanced ranking inputs differ from frozen 512-case export")
    predictions = _jsonl(files["predictions.jsonl"])
    native = _jsonl(files["native-rows.jsonl"])
    manifest = json.loads(files["manifest.json"])
    validate_full_baseline(cases, ranking_inputs, files["ranking-inputs.jsonl"], predictions, native, manifest)
    choice_files = _verified_files(choice_archive, {"raw.jsonl", "physical-requests.jsonl", "summary.json",
                                                    "scores.json", "logical-predictions.jsonl"})
    relevance, calls, used = replay_relevance(cases, choice_files)
    original_diagnostics = original_choice_confusion(choice_files)
    comparison = compose_rankings(cases, relevance, predictions)
    order_control = [{"case_id": case["case_id"], "status": "ok",
                      "ranking": [passage["id"] for passage in case["passages"]]} for case in cases]
    reversed_control = [{"case_id": row["case_id"], "status": "ok", "ranking": list(reversed(row["ranking"]))}
                        for row in order_control]
    ranking_predictions = {"input_order": order_control, "reversed_order": reversed_control,
                           "baseline": predictions, "replacement": comparison["replacement_predictions"],
                           "complement": comparison["complement_predictions"]}
    ranks = {name: old.compact(score_rankings(cases, rows)) for name, rows in ranking_predictions.items()}
    by_rotation = {}
    for rotation in ROTATIONS:
        subset = [case for case in cases if case["provenance"]["position_rotation"] == rotation]
        subset_ids = {case["case_id"] for case in subset}
        by_rotation[str(rotation)] = {name: old.compact(score_rankings(subset, [row for row in rows if row["case_id"] in subset_ids]))
                                      for name, rows in ranking_predictions.items()}
    timings = {(row["case_id"], row["passage_id"]): calls[row["source_call_id"]]["adapter_wall_ms"]
               for row in relevance}
    projected = [sum(timings[(case["case_id"], passage["id"])] for passage in case["passages"])
                 for case in cases]
    native_ms = [row["latency_ms"] for row in native]
    return {"schema_version": "deposium.passage-order-control/v1",
            "qualification": "synthetic_isolated_pending_human_review", "dataset_sha256": DATASET_SHA256,
            "split": "test", "cases": 512, "families": 8, "rotations": list(ROTATIONS),
            "main_comparison": "equal_weight_four_rotations", "new_d3_calls": 0,
            "replayed_relevance_choices": len(relevance), "unique_source_d3_relevance_calls": len(used),
            "ranking_input_sha256": FULL_INPUT_SHA256,
            "rankings": ranks, "by_rotation": by_rotation,
            "relevance_scores": old.compact(score_choices(cases, [{k: v for k, v in row.items() if k != "source_call_id"}
                                                                for row in relevance], "relevance")),
            "evidence_capture": {name: old.evidence_capture(cases, rows) for name, rows in ranking_predictions.items()},
            "grade_ties": tie_summary(cases, relevance),
            "cost_ms": {"bge_one_pool_actual": old.stats(native_ms),
                        "d3_four_relevance_choices_replayed_projection": old.stats(projected),
                        "complement_sequential_projection": old.stats([a + b for a, b in zip(native_ms, projected)])},
            "original_rotation_zero": {"choice_archive": Path(choice_archive).name,
                                       "baseline_archive": Path(original_baseline).name,
                                       "rankings": original["rankings"],
                                       "support_scores": original["choice_scores"]["support"],
                                       "answerability_scores": original["choice_scores"]["answerability"],
                                       "support_and_answerability_diagnostics": original_diagnostics,
                                       "scope": "128 original-order cases only; no rotated support or answerability predictions"},
            "baseline_profile": {"image": manifest["image"], "model": manifest["model"],
                                 "running_binary_sha256": manifest["running_binary_sha256"],
                                 "cpu_binary": manifest["cpu_binary"], "cpu_proof": manifest["cpu_proof"],
                                 "source_revision": manifest.get("source_revision"),
                                 "resource_peaks": manifest.get("resource_peaks")},
            "source": {"choice_seal_sha256": digest(Path(choice_archive) / "seal.json"),
                       "original_baseline_seal_sha256": digest(Path(original_baseline) / "seal.json"),
                       "balanced_baseline_seal_sha256": digest(Path(balanced_baseline) / "seal.json"),
                       "producer_sha256": digest(__file__), "original_producer_sha256": digest(_old_path)}}


def render(data):
    names = ("input_order", "reversed_order", "baseline", "replacement", "complement")
    label = {"input_order": "Ordre d'entrée", "reversed_order": "Ordre inversé",
             "baseline": "BGE CPU", "replacement": "D3-lite classes", "complement": "D3-lite + BGE (égalités)"}
    metric = ("ndcg@1", "ndcg@3", "mrr@4", "recall@1", "recall@3")
    lines = ["# Contrôle d'ordre équilibré : passages multilingues", "",
             "512 cas synthétiques du split test, huit familles et quatre rotations de poids égal.",
             "La rotation 0 est conservée comme observation historique ; le tableau principal couvre les quatre ordres.",
             "Références et traductions non revues humainement ; aucun parcours produit mesuré.", "",
             "## Classement, quatre rotations", "",
             "Valeurs pénalisant erreurs et absences sur cas éligibles ; parenthèses : définis / éligibles / total.", "",
             "| Méthode | nDCG@1 | nDCG@3 | MRR@4 | Rappel@1 | Rappel@3 |", "|---|---:|---:|---:|---:|---:|"]
    for name in names:
        lines.append("| " + label[name] + " | " + " | ".join(old.rank_value(data["rankings"][name], m) for m in metric) + " |")
    lines += ["", "## nDCG@1 par rotation", "", "| Rotation | Ordre d'entrée | Ordre inversé | BGE | D3-lite | Complément |", "|---|---:|---:|---:|---:|---:|"]
    for rotation, ranks in data["by_rotation"].items():
        lines.append("| " + rotation + " | " + " | ".join(old.rank_value(ranks[name], "ndcg@1") for name in names) + " |")
    for axis in ("language_direction", "scenario_id", "view"):
        lines += ["", f"## nDCG@1 par {axis}", "", "| Groupe | Ordre d'entrée | Ordre inversé | BGE | D3-lite | Complément |", "|---|---:|---:|---:|---:|---:|"]
        for group in data["rankings"]["baseline"]["by"][axis]:
            lines.append("| " + group + " | " + " | ".join(old.rank_value(data["rankings"][name]["by"][axis][group], "ndcg@1") for name in names) + " |")
    ties = data["grade_ties"]["overall"]
    lines += ["", "## Preuves et égalités", "", "| Méthode | Ensemble suffisant @3 | Appui et réfutation du même claim @3 |", "|---|---:|---:|"]
    for name in names:
        capture = data["evidence_capture"][name]
        lines.append(f"| {label[name]} | {capture['sufficient_set@3']['correct']}/{capture['sufficient_set@3']['eligible']} | {capture['conflict_pair@3']['correct']}/{capture['conflict_pair@3']['eligible']} |")
    lines += ["", f"Égalité du meilleur grade D3 : {ties['top_grade_ties']}/{ties['cases']} pools ; une égalité quelconque : {ties['any_grade_ties']}/{ties['cases']}.",
              "Comptages par rotation, direction, scénario et vue : analysis.json.", "",
              "## Coûts CPU", "",
              "BGE : un appel natif mesuré par pool. D3 : somme projetée de quatre temps de choix physiques préexistants par pool ; aucun nouvel appel D3 pour les rotations.",
              "La projection D3 n'est pas une mesure d'un rejeu sans cache. Soutien et possibilité de répondre ne font pas partie du coût de classement.", "",
              "| Opération | Médiane s | p95 s | Pools |", "|---|---:|---:|---:|"]
    for key in ("bge_one_pool_actual", "d3_four_relevance_choices_replayed_projection",
                "complement_sequential_projection"):
        values = data["cost_ms"][key]
        lines.append(f"| {key} | {values['median']/1000:.3f} | {values['p95']/1000:.3f} | {values['count']} |")
    lines += ["", "## Portée", "",
              "Les scores de soutien et de possibilité de répondre concernent seulement les 128 cas de rotation 0 ; leurs archives et scores figurent dans analysis.json.",
              "Les choix D3 de pertinence sont rejoués par entrée visible identique, sans nouvelle inférence. Aucun choix de réponse n'est imputé aux pools tournés.",
              "Le binaire CPU BGE est identifié par hash ; sa révision source exacte reste non établie.",
              "Huit familles et gabarits partagés limitent l'inférence ; aucun intervalle ne traite les rotations comme indépendantes.",
              "Aucun verdict de remplacement produit, de recherche initiale ou de chat réel.",
              f"Corpus : `{data['dataset_sha256']}` ; export ranking 512 : `{data['ranking_input_sha256']}`.",
              f"Producteur : `{data['source']['producer_sha256']}`.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--choice-archive", type=Path)
    parser.add_argument("--original-baseline-archive", type=Path)
    parser.add_argument("--balanced-baseline-archive", type=Path)
    parser.add_argument("--render-json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.render_json is not None:
        if any((args.choice_archive, args.original_baseline_archive, args.balanced_baseline_archive)):
            parser.error("--render-json excludes archive inputs")
        data = json.loads(args.render_json.read_text())
        if (data["source"]["producer_sha256"] != digest(__file__)
                or data["source"]["original_producer_sha256"] != digest(_old_path)):
            raise ValueError("Producer changed since balanced aggregate publication")
    else:
        if not all((args.choice_archive, args.original_baseline_archive, args.balanced_baseline_archive)):
            parser.error("All three sealed archives are required")
        data = aggregate(args.choice_archive, args.original_baseline_archive, args.balanced_baseline_archive)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "analysis.json").write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    (args.output / "report.md").write_text(render(data))


if __name__ == "__main__":
    main()
