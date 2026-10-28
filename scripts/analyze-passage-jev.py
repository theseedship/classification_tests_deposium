#!/usr/bin/env python3
"""Publish the sealed JeV HTTP passage comparison without making model calls."""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.jev_http_adapter import _digest as jev_digest
from deposium_bench.passage_observation import (_jsonl, _verified_files, _logical_predictions, _scores,
                                               choice_plan, compose_rankings)
from deposium_bench.passage_dataset import export_requests, score_choices, score_rankings
from deposium_bench.campaigns import _encode, _hash

ORDER_PATH = ROOT / "scripts/analyze-passage-order-control.py"
_spec = importlib.util.spec_from_file_location("passage_order_control_frozen_for_jev", ORDER_PATH)
order = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(order)

MODEL = "jev-1.14.0"
CALLS = 728
INPUT_USD_PER_MILLION = Decimal("0.042")
SCHEMA = "deposium.passage-jev-http-order-control/v1"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _sha(value):
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _validate_resume(files, parent_archive, manifest, summary, physical, raw):
    """Tie inherited HTTP evidence to its original sealed, incomplete archive."""
    lineage = manifest.get("resume_parent")
    if lineage is None:
        if (parent_archive is not None or "physical_inherited" in summary or "physical_new" in summary
                or "resume_parent_seal_sha256" in summary
                or any("revalidated_from" in row for row in raw)):
            raise ValueError("Unexpected JeV resume provenance")
        return {"physical_inherited": 0, "physical_new": len(raw), "original_error_revalidated": 0}
    if parent_archive is None:
        raise ValueError("--resume-parent-archive is required for this resumed JeV archive")
    parent = Path(parent_archive).resolve()
    if (not isinstance(lineage, dict) or set(lineage) != {"path", "seal_sha256", "physical_inherited"}
            or str(parent) != lineage["path"] or lineage["physical_inherited"] != 104
            or summary.get("physical_inherited") != 104 or summary.get("physical_new") != len(raw) - 104
            or summary.get("resume_parent_seal_sha256") != lineage["seal_sha256"]
            or not _sha(lineage["seal_sha256"]) or order.digest(parent / "seal.json") != lineage["seal_sha256"]):
        raise ValueError("JeV resume metadata or parent seal differs")
    parent_files = _verified_files(parent, {"profile.json", "manifest.json", "summary.json",
                                            "physical-requests.jsonl", "raw.jsonl"})
    parent_manifest = json.loads(parent_files["manifest.json"])
    parent_summary = json.loads(parent_files["summary.json"])
    prior = _jsonl(parent_files["raw.jsonl"])
    if (parent_files["profile.json"] != files["profile.json"]
            or parent_files["physical-requests.jsonl"] != files["physical-requests.jsonl"]
            or parent_manifest.get("source_profile_sha256") != manifest.get("source_profile_sha256")
            or parent_manifest.get("dataset_sha256") != manifest.get("dataset_sha256")
            or parent_summary.get("completion_status") != "incomplete"
            or parent_summary.get("stop_reason") != "adapter_unavailable"
            or parent_summary.get("physical_attempted") != 104
            or parent_summary.get("physical_statuses") != {"ok": 103, "error": 1}
            or len(prior) != 104 or len(physical) != CALLS):
        raise ValueError("JeV resume parent is not the expected 104-call prefix")
    immutable_http = ("http_attempted", "cached_failure", "native_result", "input_sha256",
                      "request_body_sha256", "response_sha256", "http_ms", "requested_model",
                      "request_id", "http_status", "attempt_id")
    revalidated_errors = 0
    for index, (old, new) in enumerate(zip(prior, raw)):
        old_response, new_response = old["response"], new["response"]
        old_trace, new_trace = old_response.get("raw_output"), new_response.get("raw_output")
        provenance = new.get("revalidated_from")
        if (not isinstance(old_trace, dict) or not isinstance(new_trace, dict)
                or provenance != {"parent_seal_sha256": lineage["seal_sha256"],
                                  "prior_status": old_response.get("status"),
                                  "prior_error": old_response.get("error")}
                or old.get("call_id") != new.get("call_id")
                or old.get("request_sha256") != new.get("request_sha256")
                or old.get("adapter_wall_ms") != new.get("adapter_wall_ms")
                or any(old_trace.get(key) != new_trace.get(key) for key in immutable_http)):
            raise ValueError("Inherited JeV row differs from the sealed HTTP evidence")
        if index < 103:
            if old_response != new_response or old_response.get("status") != "ok":
                raise ValueError("Inherited successful JeV response changed")
        else:
            if (old_response.get("status") != "error" or old_response.get("error") != "jev_response_invalid"
                    or new_response.get("status") != "ok" or new_response.get("error") is not None):
                raise ValueError("Original JeV validation error was not revalidated")
            revalidated_errors += 1
    if any("revalidated_from" in row for row in raw[104:]) or revalidated_errors != 1:
        raise ValueError("JeV resume provenance extends beyond inherited calls")
    return {"physical_inherited": 104, "physical_new": len(raw) - 104, "original_error_revalidated": 1,
            "parent_seal_sha256": lineage["seal_sha256"],
            "unsettled_parent_reservation_input_tokens": 65536,
            "unsettled_parent_native_input_tokens": prior[-1]["response"]["raw_output"]["native_result"]["usage"]["input_tokens"]}


def validate_jev_archive(files, parent_archive=None):
    """Validate either a complete trace or the explicitly interrupted 522-call prefix."""
    profile = json.loads(files["profile.json"])
    manifest = json.loads(files["manifest.json"])
    summary = json.loads(files["summary.json"])
    initial = json.loads(files["adapter-initial.json"])
    physical = _jsonl(files["physical-requests.jsonl"])
    raw = _jsonl(files["raw.jsonl"])
    model = profile.get("model")
    if (initial.get("available") is not True or profile.get("adapter") != "jev_http" or profile.get("qualification") != "model_isolated"
            or profile.get("capabilities") != ["bench.context-choice"]
            or profile.get("revision") is not None or profile.get("recordings") is not None
            or not isinstance(model, dict) or model.get("model_id") != MODEL
            or model.get("endpoint") != "https://api.typesafe.ai/v1/systemone"
            or manifest.get("execution_scope") != "remote_http_model_isolated"
            or manifest.get("resource_observation", {}).get("remote_model_ram") != "not_observed"
            or manifest.get("bench", {}).get("files", {}).get("jev_http_adapter.py") != initial.get("adapter_sha256")):
        raise ValueError("Sealed choice archive is not the pinned JeV HTTP observation")
    statuses = dict(Counter(row.get("response", {}).get("status") for row in raw))
    complete = (len(raw) == CALLS and statuses == {"ok": CALLS}
                and summary.get("completion_status") == "complete" and summary.get("stop_reason") is None)
    partial = (len(raw) == 522 and statuses == {"ok": 521, "error": 1}
               and raw[-1].get("response", {}).get("status") == "error"
               and raw[-1]["response"].get("error") == "jev_response_invalid"
               and summary.get("completion_status") == "incomplete"
               and summary.get("stop_reason") == "adapter_unavailable")
    if (not (complete or partial) or summary.get("physical_planned") != CALLS
            or summary.get("physical_attempted") != len(raw) or summary.get("physical_statuses") != statuses
            or summary.get("adapter_initial") != initial or len(physical) != CALLS):
        raise ValueError("JeV HTTP trace is neither complete nor the documented interrupted prefix")
    for identity in (initial, summary.get("adapter_final")):
        if (not isinstance(identity, dict) or identity.get("adapter") != "jev_http"
                or identity.get("qualification") != "model_isolated"
                or identity.get("transport") != "https_post_json"
                or identity.get("input_protocol") != "context_choice"
                or (identity.get("available") is not True and not
                    (partial and identity == summary.get("adapter_final")
                     and identity.get("availability_error") == "jev_response_invalid"))
                or identity.get("model", {}).get("model_id") != MODEL
                or identity.get("identity_sha256") != initial.get("identity_sha256")
                or identity.get("adapter_sha256") != initial.get("adapter_sha256")
                or not _sha(identity.get("identity_sha256")) or not _sha(identity.get("adapter_sha256"))):
            raise ValueError("JeV adapter identity or availability differs")
    order.old.validate_choice_trace(physical[:len(raw)], raw)
    resume = _validate_resume(files, parent_archive, manifest, summary, physical, raw)
    attempts, input_tokens, output_tokens = set(), 0, 0
    http_ms, adapter_ms = [], []
    unsettled_delta = resume.get("unsettled_parent_reservation_input_tokens", 0) - resume.get("unsettled_parent_native_input_tokens", 0)
    for index, (request, record) in enumerate(zip(physical, raw)):
        response = record["response"]
        trace = response.get("raw_output")
        if not isinstance(trace, dict):
            raise ValueError("JeV physical call has no HTTP trace")
        native = trace.get("native_result")
        invalid = partial and index == len(raw) - 1
        usage = native.get("usage") if invalid and isinstance(native, dict) else trace.get("usage")
        attempt = trace.get("attempt_id")
        options = request.get("input", {}).get("options")
        answer = native.get("answers", {}).get("answer") if isinstance(native, dict) else None
        descriptions = ({option["description"]: option["id"] for option in options}
                        if isinstance(options, list) and all(isinstance(option, dict) and
                        isinstance(option.get("description"), str) and
                        isinstance(option.get("id"), str) for option in options) else {})
        if ((not invalid and (response.get("status") != "ok" or response.get("error") is not None))
                or trace.get("http_attempted") is not True or trace.get("cached_failure") is not False
                or trace.get("http_status") != 200
                or trace.get("requested_model") != MODEL
                or trace.get("observed_model") != (None if invalid else MODEL)
                or not isinstance(native, dict) or native.get("model") != MODEL
                or not isinstance(answer, dict)
                or (response.get("output") != (None if invalid else
                    {"choice_id": descriptions.get(answer.get("choice"))}))
                or not descriptions or trace.get("input_sha256") != jev_digest(request["input"])
                or not isinstance(usage, dict) or set(usage) != {"input_tokens", "output_tokens"}
                or native.get("usage") != usage
                or type(usage["input_tokens"]) is not int or not 0 <= usage["input_tokens"] <= 65536
                or type(usage["output_tokens"]) is not int or usage["output_tokens"] < 0
                or not isinstance(attempt, str) or not attempt or attempt in attempts
                or not all(_sha(trace.get(key)) for key in ("input_sha256", "request_body_sha256", "response_sha256"))
                or not _finite(trace.get("http_ms"))):
            raise ValueError("JeV physical call lacks a successful versioned HTTP attempt")
        if invalid:
            probabilities = answer.get("probabilities", {})
            if (trace.get("usage") is not None or response.get("output") is not None
                    or answer.get("choice") not in probabilities or not probabilities
                    or any(not _finite(v) for v in probabilities.values())
                    or not probabilities[answer["choice"]] < max(probabilities.values())
                    or math.isclose(probabilities[answer["choice"]], max(probabilities.values()),
                                    rel_tol=0.0, abs_tol=4 * math.ulp(max(probabilities.values())))):
                raise ValueError("Interrupted JeV row is not the documented non-argmax contract failure")
        if invalid:
            unsettled_delta += 65536 - usage["input_tokens"]
        attempts.add(attempt)
        input_tokens += usage["input_tokens"]
        output_tokens += usage["output_tokens"]
        http_ms.append(trace["http_ms"])
        adapter_ms.append(record["adapter_wall_ms"])
    return {"adapter": "jev_http", "requested_model": MODEL, "returned_model": MODEL,
            "transport": "https_post_json", "identity_sha256": initial["identity_sha256"],
            "profile_sha256": initial["profile_sha256"],
            "adapter_sha256": initial["adapter_sha256"],
            "campaign_status": "incomplete" if partial else "complete",
            "planned_http_calls": CALLS, "validated_choice_calls": statuses.get("ok", 0),
            "protocol_error_calls": statuses.get("error", 0),
            "http_attempts": len(raw), "input_tokens": input_tokens, "output_tokens": output_tokens,
            "input_usd_per_million_tokens": str(INPUT_USD_PER_MILLION),
            "output_usd_per_million_tokens": "0",
            "budget_input_tokens_conservative_reconstructed": input_tokens + unsettled_delta,
            "estimated_usage_usd": str(Decimal(input_tokens) * INPUT_USD_PER_MILLION / Decimal(1_000_000)),
            "http_ms": order.old.stats(http_ms), "adapter_wall_ms": order.old.stats(adapter_ms),
            **resume}


def _assert_public(data):
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False)
    for private in ("/home/", "/tmp/", "budget_ledger", "credential_env", "TYPESAFE_API_KEY"):
        if private in serialized:
            raise ValueError("Public aggregate contains a private profile locator or credential field")


def aggregate(choice_archive, original_baseline, balanced_baseline, resume_parent_archive=None):
    files = _verified_files(choice_archive, {"profile.json", "manifest.json", "summary.json",
                                             "adapter-initial.json", "physical-requests.jsonl", "raw.jsonl"})
    jev = validate_jev_archive(files, resume_parent_archive)
    cases, inputs, expected_bytes = order.full_test_cases()
    bf = _verified_files(balanced_baseline, {"ranking-inputs.jsonl", "predictions.jsonl", "native-rows.jsonl", "manifest.json"})
    bm = json.loads(bf["manifest.json"])
    base, native = _jsonl(bf["predictions.jsonl"]), _jsonl(bf["native-rows.jsonl"])
    order.validate_full_baseline(cases, inputs, bf["ranking-inputs.jsonl"], base, native, bm)
    cf = _verified_files(choice_archive, {"cases.jsonl", "logical-requests.jsonl", "logical-predictions.jsonl", "scores.json"})
    initial_cases = _jsonl(cf["cases.jsonl"])
    cm = json.loads(cf["manifest.json"])
    obf = _verified_files(original_baseline, {"ranking-inputs.jsonl", "predictions.jsonl", "native-rows.jsonl", "manifest.json"})
    order.old.validate_frozen_selection(initial_cases, cm, obf["ranking-inputs.jsonl"])
    order.old.validate_baseline_trace(initial_cases, _jsonl(obf["ranking-inputs.jsonl"]),
        _jsonl(obf["predictions.jsonl"]), _jsonl(obf["native-rows.jsonl"]), json.loads(obf["manifest.json"]))
    planned, physical = choice_plan(initial_cases)
    raw = _jsonl(cf["raw.jsonl"])
    logical = _logical_predictions(planned, raw)
    if (planned != _jsonl(cf["logical-requests.jsonl"]) or physical != _jsonl(cf["physical-requests.jsonl"])
            or logical != _jsonl(cf["logical-predictions.jsonl"])
            or cm.get("physical_requests_sha256") != _hash(cf["physical-requests.jsonl"])
            or cm.get("logical_requests_sha256") != _hash(cf["logical-requests.jsonl"])):
        raise ValueError("JeV archive plan or logical predictions changed")
    scores = _scores(initial_cases, logical)
    if scores != json.loads(cf["scores.json"]):
        raise ValueError("Archived partial scores differ from common scorer")
    by_id = {row["case_id"]: row for row in physical}
    calls = {row["call_id"]: row for row in raw}
    relevance, used = [], set()
    for request in export_requests(cases, "relevance"):
        cid, choice = order.reuse_relevance_request(request, by_id, calls)
        used.add(cid)
        relevance.append({"case_id": request["case_id"], "axis": "relevance", "passage_id": request["passage_id"],
                          "status": "ok", "choice_id": choice, "source_call_id": cid})
    if len(used) != 264 or len(relevance) != 2048:
        raise ValueError("Balanced relevance coverage is incomplete")
    comparison = compose_rankings(cases, relevance, base)
    controls = [{"case_id": c["case_id"], "status": "ok", "ranking": [p["id"] for p in c["passages"]]} for c in cases]
    reverse = [{**r, "ranking": list(reversed(r["ranking"]))} for r in controls]
    predictions = {"input_order": controls, "reversed_order": reverse, "baseline": base,
                   "replacement": comparison["replacement_predictions"], "complement": comparison["complement_predictions"]}
    ranks = {key: order.old.compact(score_rankings(cases, rows)) for key, rows in predictions.items()}
    per_rotation = {}
    for rotation in order.ROTATIONS:
        selected = [c for c in cases if c["provenance"]["position_rotation"] == rotation]
        ids = {c["case_id"] for c in selected}
        per_rotation[str(rotation)] = {key: order.old.compact(score_rankings(selected, [r for r in rows if r["case_id"] in ids]))
                                       for key, rows in predictions.items()}
    projected = [sum(calls["call-" + _hash(_encode({"contract_id": r["contract_id"], "input": r["input"]}))]["adapter_wall_ms"]
                     for r in export_requests([c], "relevance")) for c in cases]
    native_ms = [row["latency_ms"] for row in native]
    data = {"schema_version": SCHEMA, "qualification": "synthetic_remote_http_model_isolated_pending_human_review",
            "cases": 512, "families": 8, "split": "test", "rotations": list(order.ROTATIONS),
            "dataset_sha256": order.DATASET_SHA256, "ranking_input_sha256": order.FULL_INPUT_SHA256,
            "new_http_calls_for_rotations": 0, "unique_source_jev_relevance_http_calls": len(used),
            "replayed_relevance_choices": len(relevance), "rankings": ranks, "by_rotation": per_rotation,
            "evidence_capture": {key: order.old.evidence_capture(cases, rows) for key, rows in predictions.items()},
            "grade_ties": order.tie_summary(cases, relevance),
            "relevance_scores": order.old.compact(score_choices(cases, [{k:v for k,v in r.items() if k != "source_call_id"} for r in relevance], "relevance")),
            "latency_ms": {"bge_one_pool_actual": order.old.stats(native_ms),
                "jev_four_relevance_choices_replayed_client_projection": order.old.stats(projected),
                "complement_sequential_projection": order.old.stats([a+b for a,b in zip(native_ms, projected)])},
            "original_rotation_zero": {"scope": "128 cases; partial support, no answerability observation",
                "support_scores": order.old.compact(scores["support"]),
                "answerability_scores": order.old.compact(scores["answerability"]),
                "support_and_answerability_diagnostics": order.original_choice_confusion(cf)},
            "jev_http": jev,
            "baseline_profile": {"image": bm["image"], "model": bm["model"], "observed_provider": bm["cpu_proof"]["provider"],
                "cpu_binary_sha256": bm["cpu_binary"]["sha256"], "source_revision": bm.get("source_revision")},
            "source": {"choice_seal_sha256": order.digest(Path(choice_archive)/"seal.json"),
                "original_baseline_seal_sha256": order.digest(Path(original_baseline)/"seal.json"),
                "balanced_baseline_seal_sha256": order.digest(Path(balanced_baseline)/"seal.json"),
                "producer_sha256": order.digest(__file__), "order_producer_sha256": order.digest(ORDER_PATH),
                "original_producer_sha256": order.digest(order._old_path)}}
    _assert_public(data)
    return data


def render(data):
    if data.get("schema_version") != SCHEMA or data.get("jev_http", {}).get("returned_model") != MODEL:
        raise ValueError("JeV report schema or observed model differs")
    names = ("input_order", "reversed_order", "baseline", "replacement", "complement")
    label = {"input_order": "Ordre d'entrée", "reversed_order": "Ordre inversé",
             "baseline": "BGE CPU", "replacement": "JeV 1.14.0 seul",
             "complement": "JeV 1.14.0 + BGE (égalités)"}
    metric = ("ndcg@1", "ndcg@3", "mrr@4", "recall@1", "recall@3")
    lines = ["# JeV 1.14.0 : passages multilingues", "",
             "512 cas synthétiques du split test, huit familles, quatre rotations de poids égal.",
             "Références et traductions non revues humainement ; aucun parcours produit mesuré.", "",
             "## Classement, quatre rotations", "",
             "Valeurs pénalisant erreurs et absences ; parenthèses : définis / éligibles / total.", "",
             "| Méthode | nDCG@1 | nDCG@3 | MRR@4 | Rappel@1 | Rappel@3 |",
             "|---|---:|---:|---:|---:|---:|"]
    for name in names:
        lines.append("| " + label[name] + " | " + " | ".join(
            order.old.rank_value(data["rankings"][name], m) for m in metric) + " |")
    lines += ["", "## nDCG@1 par rotation", "",
              "| Rotation | Ordre d'entrée | Ordre inversé | BGE | JeV | Complément |",
              "|---|---:|---:|---:|---:|---:|"]
    for rotation in sorted(data["by_rotation"], key=int):
        ranks = data["by_rotation"][rotation]
        lines.append("| " + rotation + " | " + " | ".join(
            order.old.rank_value(ranks[name], "ndcg@1") for name in names) + " |")
    for axis in ("language_direction", "scenario_id", "view"):
        lines += ["", f"## nDCG@1 par {axis}", "",
                  "| Groupe | Ordre d'entrée | Ordre inversé | BGE | JeV | Complément |",
                  "|---|---:|---:|---:|---:|---:|"]
        for group in sorted(data["rankings"]["baseline"]["by"][axis]):
            lines.append("| " + group + " | " + " | ".join(
                order.old.rank_value(data["rankings"][name]["by"][axis][group], "ndcg@1")
                for name in names) + " |")
    lines += ["", "## Conservation des preuves", "",
              "| Méthode | Ensemble suffisant @3 | Appui et réfutation du même claim @3 |",
              "|---|---:|---:|"]
    for name in names:
        capture = data["evidence_capture"][name]
        lines.append(f"| {label[name]} | {capture['sufficient_set@3']['correct']}/{capture['sufficient_set@3']['eligible']} | "
                     f"{capture['conflict_pair@3']['correct']}/{capture['conflict_pair@3']['eligible']} |")
    ties = data["grade_ties"]["overall"]
    lines += ["", f"Égalité du meilleur grade JeV : {ties['top_grade_ties']}/{ties['cases']} pools.",
              "Les diagnostics d'appui et de possibilité de répondre portent seulement sur les 128 cas initiaux.", "",
              "| Axe JeV initial | Couverture OK | Exactitude sur tous les choix | Erreurs / manquants |",
              "|---|---:|---:|---:|"]
    for axis, key in (("support", "support_scores"), ("answerability", "answerability_scores")):
        score = data["original_rotation_zero"][key]
        accuracy = (f"{score['accuracy_over_all']:.3f} ({score['total_decisions']} choix, manquants pénalisés)"
                    if score["scored_cases"] else "— non mesuré")
        counts = score.get("counts_by_status", {})
        lines.append(f"| {axis} | {score['scored_cases']}/{score['total_decisions']} | {accuracy} | "
                     f"{counts.get('error', 0)} / {counts.get('missing', 0)} |")
    lines += ["", "## Temps et usage HTTP", "",
              "BGE : durée mesurée d'un appel natif CPU par pool. JeV : durées client mesurées autour des appels HTTP physiques initiaux ; "
              "les quatre choix de pertinence par pool tourné sont une projection par réutilisation d'entrées identiques.",
              "Aucun nouvel appel JeV pour les rotations. La somme BGE + JeV est une projection séquentielle, pas un pipeline intégré.",
              "Le temps HTTP inclut réseau et serveur ; la mémoire et le temps d'inférence du modèle distant ne sont pas observés.", "",
              "| Opération | Médiane s | p95 s | Pools |", "|---|---:|---:|---:|"]
    for key in ("bge_one_pool_actual", "jev_four_relevance_choices_replayed_client_projection",
                "complement_sequential_projection"):
        values = data["latency_ms"][key]
        lines.append(f"| {key} | {values['median']/1000:.3f} | {values['p95']/1000:.3f} | {values['count']} |")
    jev = data["jev_http"]
    lines += ["", f"Campagne {jev.get('campaign_status', 'complete')} : {jev['http_attempts']}/728 tentatives HTTP 200 distinctes, modèle natif `{MODEL}` ; "
              f"{jev.get('protocol_error_calls', 0)} erreur de contrat conservée. Le classement dispose de tous les jugements nécessaires.",
              f"Origine : {jev['physical_inherited']} appels hérités d'une archive scellée, "
              f"{jev['physical_new']} nouveaux appels HTTP ; "
              f"{jev['original_error_revalidated']} réponse initialement rejetée puis revalidée hors réseau.",
              f"Durée HTTP par tentative : médiane {jev['http_ms']['median']/1000:.3f} s, "
              f"p95 {jev['http_ms']['p95']/1000:.3f} s.",
              f"Usage retourné : {jev['input_tokens']} tokens d'entrée et {jev['output_tokens']} tokens de sortie.",
              f"Estimation au tarif déclaré de 0,042 USD par million de tokens d'entrée, sorties gratuites : "
              f"{Decimal(jev['estimated_usage_usd']):.6f} USD ; ce n'est pas une facture fournisseur.", "",
              "## Portée", "",
              "Le classement est complet sur 512 cas ; le soutien reste partiel sur les 128 cas initiaux et la réponse possible non mesurée. "
              "L’exactitude sur tous les choix inclut les manquants : zéro réponse observée ne signifie pas 0 % de qualité.",
              "Le binaire CPU BGE est identifié par hash ; sa révision source exacte reste non établie.",
              "Huit familles et des gabarits partagés limitent l'inférence ; les rotations ne sont pas indépendantes.",
              "Les réponses rejetées conservent chacune leur réservation de 65 536 tokens dans le journal local ; "
              "ces réserves sont distinctes de l’estimation fondée sur les usages retournés."
              if jev["original_error_revalidated"] else "Aucune réservation héritée non soldée n'est déclarée.",
              "Aucun verdict de remplacement produit, recherche initiale ou chat réel.",
              f"Corpus : `{data['dataset_sha256']}` ; export ranking 512 : `{data['ranking_input_sha256']}`.",
              f"Producteur : `{data['source']['producer_sha256']}`.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--choice-archive", type=Path)
    parser.add_argument("--original-baseline-archive", type=Path)
    parser.add_argument("--balanced-baseline-archive", type=Path)
    parser.add_argument("--resume-parent-archive", type=Path)
    parser.add_argument("--render-json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.render_json is not None:
        if any((args.choice_archive, args.original_baseline_archive, args.balanced_baseline_archive,
                args.resume_parent_archive)):
            parser.error("--render-json excludes archive inputs")
        data = json.loads(args.render_json.read_text())
        source = data.get("source", {})
        if (source.get("producer_sha256") != order.digest(__file__)
                or source.get("order_producer_sha256") != order.digest(ORDER_PATH)
                or source.get("original_producer_sha256") != order.digest(order._old_path)):
            raise ValueError("Producer changed since JeV aggregate publication")
        _assert_public(data)
    else:
        if not all((args.choice_archive, args.original_baseline_archive, args.balanced_baseline_archive)):
            parser.error("All three sealed archives are required")
        data = aggregate(args.choice_archive, args.original_baseline_archive, args.balanced_baseline_archive,
                         args.resume_parent_archive)
    output_json = json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"
    output_md = render(data)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "analysis.json").write_text(output_json)
    (args.output / "report.md").write_text(output_md)


if __name__ == "__main__":
    main()
