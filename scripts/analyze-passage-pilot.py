#!/usr/bin/env python3
"""Publish aggregate passage metrics from sealed observations, without inference."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.passage_observation import (_verified_files, _jsonl, compose_rankings,
                                              choice_plan, _logical_predictions, _scores, select_pilot)
from deposium_bench.passage_dataset import export_requests, load_dataset
from deposium_bench.campaigns import _encode, _hash

DATASET_SHA256 = "35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476"
SELECTION_SHA256 = "e79262de0cad7b920be3d3ad8f3d6e247170a8d7025385087bf044ab7ab475a7"
RANKING_INPUT_SHA256 = "44c91f74862e2588e643a0d1202df635f5cf91d22313a88611ccafca0cc174df"
IMAGE = "sha256:4c5c2098b21735baf7d3b05206c59c5da69fd4a604194ed258802200f4bcb7d2"
CPU_BINARY_SHA256 = "0cca8fc00aeb5dfb15fe2c737ecd23433daed99437b7ebe037a34793176d1759"
CPU_FINGERPRINT_SHA256 = "fe8554f54474197cbe3039759d550ef83ac449699add3733a921ce231d1d68bf"
MODEL_PATH = "/app/local_models/bge-reranker-v2-m3/model_int8.onnx"
MODEL_SHA256 = "dd1b7800bdfde4afd4aab79ea75752250e11fa043ddc397cbf8e8a1c9a809b44"
NATIVE_BINARY_PATH = "/usr/local/bin/deposium-turbov3"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compact(score):
    return {key: value for key, value in score.items() if key != "rows"}


def stats(values):
    values = sorted(values)
    if not values:
        return {"count": 0, "median": None, "p95": None, "max": None}
    return {"count": len(values), "median": statistics.median(values),
            "p95": values[max(0, __import__('math').ceil(.95 * len(values)) - 1)], "max": max(values)}


def evidence_capture(cases, predictions):
    by_id = {row["case_id"]: row for row in predictions}
    result = {}
    for kind in ("sufficient_set", "conflict_pair"):
        expected = "answerable" if kind == "sufficient_set" else "conflicting_visible_evidence"
        eligible = [case for case in cases if case["annotations"]["query_status"] == expected]
        for k in (1, 3):
            hits = observed = 0
            for case in eligible:
                row = by_id.get(case["case_id"], {})
                if row.get("status") != "ok":
                    continue
                observed += 1
                top = set(row["ranking"][:k])
                if kind == "sufficient_set":
                    hit = any(set(ids) <= top for ids in case["annotations"]["minimal_evidence_sets"])
                else:
                    # Supporting and refuting evidence must concern the SAME claim.
                    hit = any({"supports", "refutes"} <= {j["label"] for j in claim["judgments"]
                              if j["passage_id"] in top} for claim in case["annotations"]["claims"])
                hits += bool(hit)
            result[f"{kind}@{k}"] = {"correct": hits, "observed": observed, "eligible": len(eligible),
                                    "rate_over_eligible": hits / len(eligible) if eligible else None}
    return result


def validate_frozen_selection(cases, choice_manifest, baseline_inputs):
    """Resolve the authored gold from the frozen corpus, not an archive claim."""
    full, dataset_sha256 = load_dataset()
    expected = select_pilot(full, "test")
    ids_sha256 = hashlib.sha256(("\n".join(sorted(case["case_id"] for case in expected)) + "\n").encode()).hexdigest()
    ranking_bytes = b"".join(_encode(row) for row in export_requests(expected, "ranking"))
    if (dataset_sha256 != DATASET_SHA256 or ids_sha256 != SELECTION_SHA256
            or _hash(ranking_bytes) != RANKING_INPUT_SHA256):
        raise ValueError("Local frozen passage reference changed")
    if (cases != expected or choice_manifest.get("case_ids") != [case["case_id"] for case in expected]
            or choice_manifest.get("split") != "test"
            or choice_manifest.get("dataset_sha256") != DATASET_SHA256
            or baseline_inputs != ranking_bytes):
        raise ValueError("Archived selection differs from frozen test cases")


def validate_choice_trace(physical, raw):
    """Require one ordered, finite trace per planned call, including failures."""
    if len(physical) != len(raw) or len({row.get("case_id") for row in physical}) != len(physical):
        raise ValueError("Choice physical trace count or identity changed")
    for request, record in zip(physical, raw):
        elapsed = record.get("adapter_wall_ms")
        if (record.get("call_id") != request["case_id"]
                or record.get("request_sha256") != _hash(_encode(request))
                or not isinstance(record.get("response"), dict)
                or record["response"].get("status") not in ("ok", "error", "timeout", "unsupported", "abstain")
                or type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
            raise ValueError("Choice physical response lacks planned request or valid timing")


def validate_baseline_trace(cases, inputs, predictions, native, manifest):
    """Tie one CPU pool observation and finite cost to each frozen ranking."""
    if (manifest.get("status") != "complete" or manifest.get("scores_observed") != len(cases)
            or manifest.get("input_sha256") != RANKING_INPUT_SHA256
            or manifest.get("image") != IMAGE or manifest.get("model") != "bge-reranker-v2-m3"
            or manifest.get("running_binary_sha256") != CPU_BINARY_SHA256
            or manifest.get("cpu_binary", {}).get("sha256") != CPU_BINARY_SHA256
            or manifest.get("cpu_binary", {}).get("fingerprint_sha256") != CPU_FINGERPRINT_SHA256
            or manifest.get("cpu_proof", {}).get("provider") != "cpu"
            or manifest.get("container_cleanup") != "removed_with_anonymous_volumes"
            or manifest.get("mounted_artifact_sha256", {}).get(NATIVE_BINARY_PATH) != CPU_BINARY_SHA256
            or manifest.get("mounted_artifact_sha256", {}).get(MODEL_PATH) != MODEL_SHA256):
        raise ValueError("Native CPU baseline identity or completion is unproven")
    profile = manifest.get("profile")
    if (not isinstance(profile, dict) or profile.get("top_k") != 4 or profile.get("max_seq_len") != 512
            or profile.get("cpus") != 2 or profile.get("memory_bytes") != 4 * 1024 ** 3
            or profile.get("network") != "none" or profile.get("gpu_devices") != 0
            or profile.get("rerank_session_pool") != 1):
        raise ValueError("Native CPU baseline resource profile changed")
    if len(inputs) != len(cases) or len(predictions) != len(cases) or len(native) != len(cases):
        raise ValueError("Native CPU baseline rows missing or repeated")
    expected_ids = [case["case_id"] for case in cases]
    if ([row.get("case_id") for row in inputs] != expected_ids
            or [row.get("case_id") for row in predictions] != expected_ids
            or [row.get("case_id") for row in native] != expected_ids):
        raise ValueError("Native CPU baseline case order or identity changed")
    for prediction, observation in zip(predictions, native):
        elapsed = observation.get("latency_ms")
        if (prediction.get("status") != "ok" or observation.get("status") != "ok"
                or prediction.get("ranking") != observation.get("ranking")
                or type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
            raise ValueError("Native CPU prediction and measured pool disagree")


def aggregate(choice, baseline):
    cf = _verified_files(choice, {"cases.jsonl", "logical-requests.jsonl", "physical-requests.jsonl",
                                  "logical-predictions.jsonl", "raw.jsonl", "summary.json", "manifest.json", "scores.json"})
    bf = _verified_files(baseline, {"ranking-inputs.jsonl", "predictions.jsonl", "native-rows.jsonl", "manifest.json"})
    cases = _jsonl(cf["cases.jsonl"])
    logical = _jsonl(cf["logical-predictions.jsonl"])
    base = _jsonl(bf["predictions.jsonl"])
    summary = json.loads(cf["summary.json"])
    cm = json.loads(cf["manifest.json"])
    bm = json.loads(bf["manifest.json"])
    raw = _jsonl(cf["raw.jsonl"])
    native = _jsonl(bf["native-rows.jsonl"])
    baseline_inputs = _jsonl(bf["ranking-inputs.jsonl"])
    validate_frozen_selection(cases, cm, bf["ranking-inputs.jsonl"])
    planned_logical, planned_physical = choice_plan(cases)
    if (planned_logical != _jsonl(cf["logical-requests.jsonl"])
            or planned_physical != _jsonl(cf["physical-requests.jsonl"])
            or _logical_predictions(planned_logical, raw) != logical
            or cm.get("logical_requests_sha256") != _hash(cf["logical-requests.jsonl"])
            or cm.get("physical_requests_sha256") != _hash(cf["physical-requests.jsonl"])):
        raise ValueError("Archived inputs or logical lineage changed")
    validate_choice_trace(planned_physical, raw)
    validate_baseline_trace(cases, baseline_inputs, base, native, bm)
    comparison = compose_rankings(cases, logical, base)
    choice_scores = _scores(cases, logical)
    if choice_scores != json.loads(cf["scores.json"]):
        raise ValueError("Stored choice scores differ from common scorer")
    if (summary.get("completion_status") != "complete" or summary.get("stop_reason") is not None
            or summary.get("physical_planned") != len(planned_physical)
            or summary.get("physical_attempted") != len(raw)
            or summary.get("logical_decisions") != len(logical)
            or summary.get("selected_cases") != len(cases)):
        raise ValueError("Public completed-pilot export requires both completed archives")
    if len(cases) != 128 or len(base) != 128 or len(raw) != 728:
        raise ValueError("Frozen pilot denominators changed")
    calls = {row["call_id"]: row for row in raw}
    per_case = {case["case_id"]: {axis: [] for axis in ("relevance", "support", "answerability")} for case in cases}
    for row in logical:
        per_case[row["case_id"]][row["axis"]].append(calls[row["call_id"]]["adapter_wall_ms"])
    bt = {row["case_id"]: row["latency_ms"] for row in native}
    costs = {axis: stats([sum(axes[axis]) for axes in per_case.values()])
             for axis in ("relevance", "support", "answerability")}
    costs["baseline_pool"] = stats(list(bt.values()))
    costs["complement_pool"] = stats([bt[cid] + sum(axes["relevance"]) for cid, axes in per_case.items()])
    costs["complement_with_gate_pool"] = stats([bt[cid] + sum(axes["relevance"]) + sum(axes["answerability"])
                                               for cid, axes in per_case.items()])
    rss = [(row["response"].get("raw_output") or {}).get("rss_mb") for row in raw]
    ranks = {key: compact(comparison[key]) for key in ("baseline", "replacement", "complement")}
    capture = {key: evidence_capture(cases, preds) for key, preds in (
        ("baseline", base), ("replacement", comparison["replacement_predictions"]),
        ("complement", comparison["complement_predictions"]))}
    identity = summary["adapter_initial"]
    return {"schema_version": "deposium.passage-pilot-comparison/v1", "date": "2026-10-15",
            "qualification": "synthetic_isolated_pending_human_review", "cases": len(cases),
            "families": len({c["family_id"] for c in cases}), "split": "test", "rotation": 0,
            "dataset_sha256": cm["dataset_sha256"],
            "physical_calls": len(raw), "logical_choices": len(logical),
            "choice_scores": {key: compact(value) for key, value in choice_scores.items()},
            "rankings": ranks, "evidence_capture": capture, "pool_cost_ms_without_cache": costs,
            "physical_call_ms": stats([row["adapter_wall_ms"] for row in raw]),
            "choice_rss_mib": stats([v for v in rss if isinstance(v, (int, float))]),
            "choice_initialization_ms": identity.get("init_wall_ms"),
            "baseline_resource_peaks": bm.get("resource_peaks"), "baseline_elapsed_ms": bm.get("elapsed_ms"),
            "choice_model": {key: identity.get(key) for key in ("model_repo_id", "model_revision", "identity_sha256", "settings")},
            "baseline_profile": {**{key: bm.get(key) for key in ("image", "model", "profile", "mounted_artifact_sha256", "image_original_binary", "running_binary_sha256", "source_revision", "token_preflight")},
                                 "cpu_binary": {key: bm.get("cpu_binary", {}).get(key) for key in
                                    ("sha256", "size_bytes", "fingerprint_sha256", "cargo_features", "source_revision")},
                                 "observed_provider": bm.get("cpu_proof", {}).get("provider")},
            "source": {"choice_seal_sha256": digest(Path(choice) / "seal.json"),
                       "baseline_seal_sha256": digest(Path(baseline) / "seal.json"),
                       "producer_sha256": digest(__file__)}}


def number(value):
    return "non défini" if value is None else f"{value:.3f}"


def rank_value(score, metric):
    m = score["metrics"][metric]
    return f"{number(m['mean_over_eligible_missing_zero'])} ({m['defined_cases']}/{m['eligible_cases']}/{m['total_cases']})"


def render(data):
    r = data["rankings"]
    lines = ["# Passages multilingues : pilote CPU du 15 octobre 2026", "",
             "128 cas synthétiques du split test, huit familles, huit directions de langue, deux vues, rotation 0.",
             "Références et traductions non revues humainement. Aucun outil ni réponse finale évalué.", "",
             "## Classement : référence, remplacement et complément", "",
             "Valeur pénalisant absents/erreurs sur les cas éligibles ; entre parenthèses : définis / éligibles / total.", "",
             "| Méthode | nDCG@1 | nDCG@3 | MRR@4 | Rappel@1 | Rappel@3 |", "|---|---:|---:|---:|---:|---:|"]
    names = {"baseline": "BGE v2-m3 INT8 CPU", "replacement": "D3-lite classes seules", "complement": "D3-lite + BGE pour les égalités"}
    for key in r:
        lines.append("| " + names[key] + " | " + " | ".join(rank_value(r[key], m) for m in ("ndcg@1", "ndcg@3", "mrr@4", "recall@1", "recall@3")) + " |")
    for axis in ("language_direction", "view", "scenario_id"):
        lines += ["", f"## nDCG@1 par {axis}", "", "| Groupe | BGE | D3-lite | Complément |", "|---|---:|---:|---:|"]
        for group in r["baseline"]["by"][axis]:
            lines.append("| " + group + " | " + " | ".join(rank_value(r[key]["by"][axis][group], "ndcg@1") for key in names) + " |")
    lines += ["", "## Décisions séparées", "", "| Axe | Réussites / total | Couverture | Macro sur classes observées |", "|---|---:|---:|---:|"]
    for axis, score in data["choice_scores"].items():
        success = round(score["accuracy_over_all"] * score["total_decisions"])
        lines.append(f"| {axis} | {success}/{score['total_decisions']} | {score['scored_cases']}/{score['total_decisions']} | {number(score['macro_accuracy_scored'])} |")
    for axis, score in data["choice_scores"].items():
        lines += ["", f"### {axis} : par classe", "", "| Classe de référence | Réussites / total |", "|---|---:|"]
        for label, row in score["by_expected_label"].items():
            n = row["total_decisions"]
            successes = round(row["accuracy_over_all"] * n) if n else 0
            lines.append(f"| {label} | {successes}/{n} |")
        lines += ["", f"### {axis} : par direction", "", "| Direction | Réussites / total |", "|---|---:|"]
        for label, row in score["by"]["language_direction"].items():
            n = row["total_cases"]
            m = row["metrics"]["accuracy"]["mean_over_eligible_missing_zero"]
            lines.append(f"| {label} | {round(m*n)}/{n} |")
    lines += ["", "## Conservation des preuves", "", "| Méthode | Ensemble suffisant @1 | Ensemble suffisant @3 | Appui + réfutation @3 |", "|---|---:|---:|---:|"]
    for key, metrics in data["evidence_capture"].items():
        cells = [f"{metrics[m]['correct']}/{metrics[m]['eligible']}" for m in ("sufficient_set@1", "sufficient_set@3", "conflict_pair@3")]
        lines.append("| " + names[key] + " | " + " | ".join(cells) + " |")
    lines += ["", "## Coût CPU par pool de quatre passages", "",
              "Reconstruction sans cache : somme des appels logiques mesurés. La composition additionne deux campagnes séquentielles, pas un pipeline intégré.",
              "Support et possibilité de répondre sont des fonctions supplémentaires, séparées du classement.", "",
              "| Opération | Médiane s | p95 s | Pools |", "|---|---:|---:|---:|"]
    for label, values in data["pool_cost_ms_without_cache"].items():
        lines.append(f"| {label} | {values['median']/1000:.3f} | {values['p95']/1000:.3f} | {values['count']} |")
    lines += ["", f"D3 : {data['physical_calls']} appels physiques pour {data['logical_choices']} choix logiques ; maximum RSS échantillonné {number(data['choice_rss_mib']['max'])} Mio.",
              "Les pics mémoire du processus BGE et de son conteneur sont consignés séparément dans le JSON ; ils ne représentent pas la même portée que le RSS du worker D3.",
              "Les temps BGE incluent docker exec, curl et la boucle HTTP locale ; ils ne sont pas le seul temps du forward.", "",
              "## Provenance et limites", "",
              f"Corpus : `{data['dataset_sha256']}`.",
              f"Producteur : `scripts/analyze-passage-pilot.py`, SHA-256 `{data['source']['producer_sha256']}`.",
              "Les sceaux des deux campagnes et les identités des modèles figurent dans analysis.json.",
              "Huit familles seulement, gabarits partagés, vues parfois identiques ; aucun intervalle traitant les variantes comme indépendantes.",
              "Aucune qualification de remplacement produit, filtre automatique, recherche initiale, autre ordre ou chat réel.", ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--choice-archive", type=Path)
    p.add_argument("--baseline-archive", type=Path)
    p.add_argument("--render-json", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.render_json is not None:
        if args.choice_archive or args.baseline_archive:
            p.error("render-json and archive inputs are mutually exclusive")
        data = json.loads(args.render_json.read_text())
        if data["source"]["producer_sha256"] != digest(__file__):
            raise ValueError("Producer changed since aggregate publication")
    else:
        if args.choice_archive is None or args.baseline_archive is None:
            p.error("Both sealed archives are required")
        data = aggregate(args.choice_archive, args.baseline_archive)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "analysis.json").write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    (args.output / "report.md").write_text(render(data))


if __name__ == "__main__":
    main()
