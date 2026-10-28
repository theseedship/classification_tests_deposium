"""Offline validation, candidate projections and scoring for passage evidence.

This additive dataset boundary performs no inference, networking or model loading.
It deliberately does not relax the frozen context-choice corpus's exact oracles.
Character spans use Python Unicode offsets, start inclusive and end exclusive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from .choice_protocol import choice_row, validate_choice_input

VERSION = "deposium.passage-case/v1"
DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "datasets/passage-evidence-v1/cases.jsonl"
LANGUAGES = ("fr", "en", "de", "es", "it", "pt")
STATUSES = ("ok", "error", "timeout", "unsupported", "abstain", "missing")
QUERY_STATUSES = ("answerable", "insufficient_visible_evidence", "conflicting_visible_evidence")
PROJECTIONS = ("ranking", "relevance", "support", "answerability")
# This public decoding map belongs to the adapter/scorer, never candidate input.
CHOICE_LABELS = {"relevance": {"o1": 3, "o2": 2, "o3": 1, "o4": 0},
                 "support": {"o1": "supports", "o2": "refutes", "o3": "insufficient"},
                 "answerability": dict(zip(("o1", "o2", "o3"), QUERY_STATUSES))}

# Instructions follow the question language, independently of passage language.
_TEXT = {
    "fr": ("Question", "Passage", "À quel degré ce passage aide-t-il à répondre à la question ?",
           ("Il établit ou réfute directement le fait demandé.", "Il apporte une partie des preuves nécessaires.",
            "Il concerne le sujet sans permettre de trancher.", "Il n'est pas pertinent pour la question."),
           "Par rapport à l'affirmation suivante, que permet d'établir le passage ?",
           ("Il étaye l'affirmation.", "Il réfute l'affirmation.", "Il ne suffit pas pour trancher."),
           "Avec ces passages seuls, peut-on répondre à la question ?",
           ("Les preuves visibles permettent de répondre.", "Les preuves visibles sont insuffisantes.",
            "Les preuves visibles se contredisent sans résolution.")),
    "en": ("Question", "Passage", "How much does this passage help answer the question?",
           ("It directly establishes or refutes the requested fact.", "It supplies part of the necessary evidence.",
            "It concerns the topic without deciding the question.", "It is irrelevant to the question."),
           "What does the passage establish about the following claim?",
           ("It supports the claim.", "It refutes the claim.", "It provides insufficient evidence to decide."),
           "Can the question be answered from these passages alone?",
           ("The visible evidence allows an answer.", "The visible evidence is insufficient.",
            "The visible evidence conflicts without a resolution.")),
    "de": ("Frage", "Passage", "In welchem Maß hilft diese Passage, die Frage zu beantworten?",
           ("Sie belegt oder widerlegt unmittelbar den erfragten Sachverhalt.", "Sie liefert einen Teil der nötigen Belege.",
            "Sie betrifft das Thema, entscheidet die Frage aber nicht.", "Sie ist für die Frage nicht relevant."),
           "Was lässt sich aus der Passage über die folgende Aussage ableiten?",
           ("Sie stützt die Aussage.", "Sie widerlegt die Aussage.", "Die Belege reichen für eine Entscheidung nicht aus."),
           "Lässt sich die Frage allein anhand dieser Passagen beantworten?",
           ("Die sichtbaren Belege ermöglichen eine Antwort.", "Die sichtbaren Belege reichen nicht aus.",
            "Die sichtbaren Belege widersprechen sich ohne Auflösung.")),
    "es": ("Pregunta", "Pasaje", "¿En qué medida ayuda este pasaje a responder a la pregunta?",
           ("Establece o refuta directamente el hecho solicitado.", "Aporta parte de las pruebas necesarias.",
            "Trata el tema sin permitir resolver la pregunta.", "No es pertinente para la pregunta."),
           "¿Qué permite establecer el pasaje sobre la siguiente afirmación?",
           ("Respalda la afirmación.", "Refuta la afirmación.", "Las pruebas son insuficientes para decidir."),
           "¿Se puede responder a la pregunta solo con estos pasajes?",
           ("Las pruebas visibles permiten responder.", "Las pruebas visibles son insuficientes.",
            "Las pruebas visibles se contradicen sin resolución.")),
    "it": ("Domanda", "Passaggio", "In che misura questo passaggio aiuta a rispondere alla domanda?",
           ("Dimostra o confuta direttamente il fatto richiesto.", "Fornisce una parte delle prove necessarie.",
            "Riguarda l'argomento senza consentire di decidere.", "Non è pertinente alla domanda."),
           "Che cosa permette di stabilire il passaggio sulla seguente affermazione?",
           ("Sostiene l'affermazione.", "Confuta l'affermazione.", "Le prove non bastano per decidere."),
           "Si può rispondere alla domanda usando soltanto questi passaggi?",
           ("Le prove visibili permettono di rispondere.", "Le prove visibili sono insufficienti.",
            "Le prove visibili sono in conflitto senza una soluzione.")),
    "pt": ("Pergunta", "Passagem", "Em que medida esta passagem ajuda a responder à pergunta?",
           ("Estabelece ou refuta diretamente o facto pedido.", "Fornece parte das provas necessárias.",
            "Aborda o tema sem permitir decidir a questão.", "Não é pertinente para a pergunta."),
           "O que permite estabelecer a passagem sobre a seguinte afirmação?",
           ("Sustenta a afirmação.", "Refuta a afirmação.", "As provas são insuficientes para decidir."),
           "É possível responder à pergunta apenas com estas passagens?",
           ("As provas visíveis permitem responder.", "As provas visíveis são insuficientes.",
            "As provas visíveis estão em conflito sem resolução.")),
}


class PassageDatasetError(ValueError):
    """Invalid dataset, leaked partition, manifest or prediction."""


def _require(condition, message):
    if not condition:
        raise PassageDatasetError(message)


def _object(value, fields, where):
    _require(isinstance(value, dict) and set(value) == set(fields), f"{where}: unexpected fields")


def _text(value, where):
    _require(isinstance(value, str) and bool(value.strip()), f"{where}: nonblank text required")


def _finite_json(value):
    if value is None or type(value) in (bool, int, str):
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, list):
        for item in value:
            _finite_json(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _finite_json(item)
        return
    raise PassageDatasetError("Non-finite or non-JSON metadata")


def validate_cases(cases):
    """Validate all labels/spans and splits without consulting any candidate."""
    _require(isinstance(cases, list) and bool(cases), "Dataset must contain cases")
    ids, partitions = set(), {}
    for case in cases:
        _object(case, ("schema_version", "case_id", "family_id", "scenario_id", "split",
                       "question_language", "passage_language", "view", "query", "passages",
                       "annotations", "provenance"), "case")
        _require(case["schema_version"] == VERSION, "Unsupported passage case version")
        for field in ("case_id", "family_id", "scenario_id", "query"):
            _text(case[field], field)
        _require(case["case_id"] not in ids, "Duplicate case_id")
        ids.add(case["case_id"])
        _require(case["split"] in ("train", "calibration", "test"), "Invalid split")
        _require(case["view"] in ("full", "head_384"), "Invalid view")
        for field in ("question_language", "passage_language"):
            _require(case[field] in LANGUAGES, f"Invalid {field}")
        _require(isinstance(case["provenance"], dict) and bool(case["provenance"]), "Missing provenance")
        _finite_json(case["provenance"])
        passages = case["passages"]
        _require(isinstance(passages, list) and len(passages) == 4, "Exactly four passages required")
        by_id, documents = {}, set()
        for passage in passages:
            _object(passage, ("id", "document_id", "text", "language", "sha256"), "passage")
            for field in ("id", "document_id", "text"):
                _text(passage[field], f"passage.{field}")
            _require(passage["id"] not in by_id, "Duplicate passage ID")
            _require(passage["document_id"] not in documents, "Duplicate document ID within case")
            _require(passage["language"] == case["passage_language"], "Passage language differs from case")
            digest = hashlib.sha256(passage["text"].encode("utf-8")).hexdigest()
            _require(passage["sha256"] == digest, "Passage hash mismatch")
            if case["view"] == "head_384":
                _require(len(passage["text"]) <= 384, "head_384 exceeds 384 Unicode characters")
            by_id[passage["id"]] = passage
            documents.add(passage["document_id"])
        # scenario_id denotes a risk taxonomy, not an independent episode.
        # Concrete scenarios, translations and views share family_id instead.
        groups = [("family", case["family_id"])]
        groups.extend(("document", doc) for doc in documents)
        for group in groups:
            _require(group not in partitions or partitions[group] == case["split"],
                     f"Cross-split {group[0]} leakage: {group[1]}")
            partitions[group] = case["split"]
        _validate_annotations(case["annotations"], by_id)
    _validate_visible_oracles(cases)
    return cases


def _validate_annotations(annotations, passages):
    _object(annotations, ("review", "query_status", "relevance", "claims", "minimal_evidence_sets", "rationale"), "annotations")
    _require(annotations["review"] == "agent_only_pending_human", "Invalid review state")
    _require(annotations["query_status"] in QUERY_STATUSES, "Invalid query_status")
    _text(annotations["rationale"], "annotations.rationale")
    relevance = annotations["relevance"]
    _require(isinstance(relevance, list), "Relevance must be a list")
    grades = {}
    for item in relevance:
        _object(item, ("passage_id", "grade", "role"), "relevance")
        _require(isinstance(item["passage_id"], str) and item["passage_id"] in passages
                 and item["passage_id"] not in grades, "Unknown or duplicate relevance passage")
        _require(type(item["grade"]) is int and 0 <= item["grade"] <= 3, "Invalid relevance grade")
        _text(item["role"], "relevance.role")
        grades[item["passage_id"]] = item["grade"]
    _require(set(grades) == set(passages), "Relevance must cover every passage exactly once")
    claims = annotations["claims"]
    _require(isinstance(claims, list) and bool(claims), "Claims must be nonempty")
    claim_ids, has_conflicting_claim = set(), False
    for claim in claims:
        _object(claim, ("id", "text", "judgments"), "claim")
        _text(claim["id"], "claim.id")
        _text(claim["text"], "claim.text")
        _require(claim["id"] not in claim_ids, "Duplicate claim ID")
        claim_ids.add(claim["id"])
        _require(isinstance(claim["judgments"], list), "Judgments must be a list")
        seen, labels = set(), set()
        for judgment in claim["judgments"]:
            _object(judgment, ("passage_id", "label", "spans"), "judgment")
            pid, label = judgment["passage_id"], judgment["label"]
            _require(isinstance(pid, str) and pid in passages and pid not in seen,
                     "Unknown or duplicate judgment passage")
            _require(label in ("supports", "refutes", "insufficient"), "Invalid support label")
            seen.add(pid)
            labels.add(label)
            spans = judgment["spans"]
            _require(isinstance(spans, list) and bool(spans) == (label != "insufficient"),
                     "Supports/refutes require spans; insufficient requires none")
            span_ids = set()
            for span in spans:
                _object(span, ("start", "end", "text"), "span")
                start, end = span["start"], span["end"]
                _require(type(start) is int and type(end) is int and 0 <= start < end <= len(passages[pid]["text"]),
                         "Invalid span bounds")
                _require(isinstance(span["text"], str) and span["text"] == passages[pid]["text"][start:end],
                         "Span does not match visible text")
                _require((start, end) not in span_ids, "Duplicate span")
                span_ids.add((start, end))
        _require(seen == set(passages), "Each claim must cover every passage exactly once")
        has_conflicting_claim |= {"supports", "refutes"} <= labels
    sets = annotations["minimal_evidence_sets"]
    _require(isinstance(sets, list), "Evidence sets must be a list")
    _require(bool(sets) == (annotations["query_status"] == "answerable"),
             "Evidence sets must be nonempty exactly when answerable")
    seen_sets = set()
    for evidence in sets:
        _require(isinstance(evidence, list) and bool(evidence)
                 and all(isinstance(pid, str) and pid in grades and grades[pid] >= 2 for pid in evidence),
                 "Evidence sets require relevant visible passage IDs")
        _require(len(set(evidence)) == len(evidence), "Duplicate evidence-set member")
        key = frozenset(evidence)
        _require(key not in seen_sets, "Duplicate evidence set")
        seen_sets.add(key)
    _require(not any(a < b for a in seen_sets for b in seen_sets), "Evidence sets must be minimal")
    if annotations["query_status"] == "conflicting_visible_evidence":
        _require(has_conflicting_claim, "Conflict requires supporting and refuting evidence for the same claim")


def _request_gold(case, request, projection):
    """Read an oracle independently of the shared candidate-input projection."""
    annotations = case["annotations"]
    if projection == "ranking":
        grades = {item["passage_id"]: item["grade"] for item in annotations["relevance"]}
        return tuple(grades[p["id"]] for p in case["passages"])
    if projection == "relevance":
        return next(item["grade"] for item in annotations["relevance"] if item["passage_id"] == request["passage_id"])
    if projection == "support":
        claim = next(item for item in annotations["claims"] if item["id"] == request["claim_id"])
        return next(item["label"] for item in claim["judgments"] if item["passage_id"] == request["passage_id"])
    return annotations["query_status"]


def _validate_visible_oracles(cases):
    # Use the very same projection as export; case/view/document/claim metadata
    # cannot distinguish inputs that a candidate sees as identical.
    visible_labels = {}
    for case in cases:
        for projection in PROJECTIONS:
            for request in _requests(case, projection):
                identity = json.dumps([request["contract_id"], request["input"]],
                                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                gold = _request_gold(case, request, projection)
                location = "/".join(str(request[key]) for key in ("case_id", "axis", "passage_id", "claim_id") if key in request)
                previous = visible_labels.get(identity)
                _require(previous is None or previous[0] == gold,
                         f"Identical candidate inputs have conflicting annotations: {previous} versus {location}: {gold!r}")
                visible_labels[identity] = (gold, location)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def _read_jsonl(path, *, allow_empty=False):
    payload = Path(path).read_bytes()
    records = payload.decode("utf-8").split("\n")
    if records[-1] == "":
        records.pop()
    _require((bool(records) or allow_empty) and all(record.strip() for record in records), "Empty or blank JSONL record")
    return [json.loads(row, object_pairs_hook=_unique_object) for row in records], payload


def load_dataset(path=DEFAULT_DATASET, manifest_path=None):
    """Read exact bytes and verify the accompanying manifest's hash and counts."""
    path = Path(path)
    cases, payload = _read_jsonl(path)
    validate_cases(cases)
    manifest = json.loads(Path(manifest_path or path.parent / "manifest.json").read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_object)
    digest = hashlib.sha256(payload).hexdigest()
    _require(isinstance(manifest, dict), "Manifest must be an object")
    _finite_json(manifest)
    _require(manifest.get("cases_sha256") == digest, "Manifest cases_sha256 mismatch")
    _require(type(manifest.get("case_count")) is int and manifest["case_count"] == len(cases), "Manifest case_count mismatch")
    if "family_count" in manifest:
        _require(type(manifest["family_count"]) is int and
                 manifest["family_count"] == len({case["family_id"] for case in cases}), "Manifest family_count mismatch")
    return cases, digest


def select_cases(cases, *, split=None, view=None, question_language=None, passage_language=None):
    """Select eligible cases; validate the whole corpus before filtering leaks."""
    validate_cases(cases)
    filters = {"split": split, "view": view, "question_language": question_language, "passage_language": passage_language}
    allowed = {"split": ("train", "calibration", "test"), "view": ("full", "head_384"),
               "question_language": LANGUAGES, "passage_language": LANGUAGES}
    for key, values in filters.items():
        if values is not None:
            values = [values] if isinstance(values, str) else list(values)
            _require(bool(values) and all(value in allowed[key] for value in values), f"Invalid {key} filter")
            filters[key] = values
    selected = [case for case in cases if all(values is None or case[key] in values for key, values in filters.items())]
    _require(bool(selected), "No eligible cases for these filters")
    return selected


def _requests(case, projection):
    if projection == "ranking":
        yield {"case_id": case["case_id"], "contract_id": "bench.passage-rerank",
               "input": {"query": case["query"], "passages": [{"id": p["id"], "text": p["text"]} for p in case["passages"]]}}
        return
    qword, pword, relevance_q, relevance_o, support_q, support_o, answer_q, answer_o = _TEXT[case["question_language"]]
    if projection == "answerability":
        context = f"{qword}: {case['query']}\n\n" + "\n\n".join(f"{pword} {i + 1}: {p['text']}" for i, p in enumerate(case["passages"]))
        items = [(None, None, context, answer_q, answer_o)]
    else:
        items = []
        for passage in case["passages"]:
            context = f"{qword}: {case['query']}\n\n{pword}: {passage['text']}"
            if projection == "relevance":
                items.append((passage["id"], None, context, relevance_q, relevance_o))
            else:
                for claim in case["annotations"]["claims"]:
                    items.append((passage["id"], claim["id"], context, f"{support_q}\n{claim['text']}", support_o))
    for pid, cid, context, question, descriptions in items:
        value = {"context": context, "question": question,
                 "options": [{"id": f"o{i + 1}", "description": desc} for i, desc in enumerate(descriptions)]}
        validate_choice_input(value)
        row = {"case_id": case["case_id"], "contract_id": "bench.context-choice", "axis": projection, "input": value}
        if pid is not None:
            row["passage_id"] = pid
        if cid is not None:
            row["claim_id"] = cid
        yield row


def export_requests(cases, projection="ranking", **filters):
    """Whitelist candidate input; labels, document IDs and provenance stay outside."""
    _require(projection in PROJECTIONS, "Unknown projection")
    return [request for case in select_cases(cases, **filters) for request in _requests(case, projection)]


def candidate_row(request):
    """Adapt an exported choice request through the existing model-row protocol."""
    _require(isinstance(request, dict) and request.get("contract_id") == "bench.context-choice", "Choice request required")
    return choice_row(request["input"])


def _metric_summary(rows, names):
    summary = {}
    for name in names:
        values = [row[name] for row in rows if row[name] is not None]
        eligible = [row for row in rows if row.get("metric_eligible", {}).get(name, True)]
        observed_mean = sum(values) / len(values) if values else None
        summary[name] = {"mean": observed_mean, "mean_conditional_on_observed": observed_mean,
                         "mean_over_eligible_missing_zero": sum(row[name] or 0 for row in eligible) / len(eligible) if eligible else None,
                         "eligible_cases": len(eligible), "defined_cases": len(values), "total_cases": len(rows),
                         "defined_fraction": len(values) / len(rows) if rows else 0}
    return summary


def _summarize(rows, metric_names):
    def group(items):
        scored = sum(row["status"] == "ok" for row in items)
        return {"total_cases": len(items), "scored_cases": scored,
                "family_count": len({row["family_id"] for row in items}),
                "coverage": scored / len(items) if items else 0,
                "counts_by_status": {status: sum(row["status"] == status for row in items) for status in STATUSES},
                "metrics": _metric_summary(items, metric_names)}
    dimensions = ("question_language", "passage_language", "language_direction", "view", "split", "scenario_id", "query_status")
    status = "scored" if any(row["status"] == "ok" for row in rows) else "no_scored_predictions"
    return {"schema_version": "deposium.passage-score/v1", "evaluation_status": "offline_scored", "scoring_status": status,
            "qualification": "exploratory_pending_human_review",
            **group(rows), "by": {field: {value: group([row for row in rows if row[field] == value])
                                          for value in sorted({row[field] for row in rows})} for field in dimensions},
            "rows": rows}


def _row_metadata(case, status):
    return {key: case[key] for key in ("case_id", "family_id", "question_language", "passage_language", "view", "split", "scenario_id")} | {
        "language_direction": f"{case['question_language']}->{case['passage_language']}",
        "query_status": case["annotations"]["query_status"], "status": status}


def _index_predictions(predictions, expected, key):
    _require(isinstance(predictions, list), "Predictions must be a list")
    indexed = {}
    for prediction in predictions:
        _require(isinstance(prediction, dict), "Prediction must be an object")
        _finite_json(prediction)
        identity = key(prediction)
        _require(identity in expected and identity not in indexed, "Unknown or duplicate prediction identity")
        _require(prediction.get("status") in STATUSES[:-1], "Invalid prediction status")
        indexed[identity] = prediction
    return indexed


def score_rankings(cases, predictions):
    """Score frozen full-pool permutations; failures/missing stay in denominators."""
    validate_cases(cases)
    expected = {case["case_id"] for case in cases}
    indexed = _index_predictions(predictions, expected, lambda row: row.get("case_id") if isinstance(row.get("case_id"), str) else None)
    names = [f"ndcg@{k}" for k in (1, 3, 4)] + ["mrr@4"] + [f"recall@{k}" for k in (1, 3, 4)]
    rows = []
    for case in cases:
        prediction = indexed.get(case["case_id"], {"status": "missing"})
        _require(set(prediction) <= {"case_id", "status", "ranking", "error"}, "Unexpected ranking prediction fields")
        row = _row_metadata(case, prediction["status"]) | dict.fromkeys(names)
        grades = {item["passage_id"]: item["grade"] for item in case["annotations"]["relevance"]}
        relevant = {pid for pid, grade in grades.items() if grade >= 2}
        row["metric_eligible"] = {name: (any(grades.values()) if name.startswith("ndcg") else bool(relevant)) for name in names}
        ranking = prediction.get("ranking")
        if prediction["status"] == "ok":
            _require(isinstance(ranking, list) and all(isinstance(pid, str) for pid in ranking)
                     and len(ranking) == len(grades) and set(ranking) == set(grades), "Ranking must permute all passage IDs exactly once")
            def dcg(values):
                return sum((2 ** grade - 1) / math.log2(i + 2) for i, grade in enumerate(values))
            for k in (1, 3, 4):
                ideal = dcg(sorted(grades.values(), reverse=True)[:k])
                row[f"ndcg@{k}"] = dcg([grades[pid] for pid in ranking[:k]]) / ideal if ideal else None
            row["mrr@4"] = next((1 / (i + 1) for i, pid in enumerate(ranking) if pid in relevant), None)
            for k in (1, 3, 4):
                row[f"recall@{k}"] = len(set(ranking[:k]) & relevant) / len(relevant) if relevant else None
        else:
            _require(ranking is None or ranking == [], "Unsuccessful prediction must not supply a ranking")
        rows.append(row)
    report = _summarize(rows, names)
    report["metric_policy"] = {"ndcg_gain": "2**grade-1", "discount": "log2(rank+1)",
                               "relevant_grade_minimum": 2, "no_relevant_passages": "mrr/recall undefined",
                               "zero_ideal_gain": "ndcg undefined",
                               "mean": "conditional on observed valid predictions",
                               "mean_over_eligible_missing_zero": "failures and missing predictions count zero only when gold defines the metric"}
    if report["scored_cases"] and all(item["defined_cases"] == 0 for item in report["metrics"].values()):
        report["scoring_status"] = "no_defined_metrics"
    return report


def _choice_key(row):
    values = tuple(row.get(key) for key in ("case_id", "axis", "passage_id", "claim_id"))
    _require(all(value is None or isinstance(value, str) for value in values), "Invalid choice identity")
    return values


def score_choices(cases, predictions, projection):
    """Exact accuracy for an exported axis, with references computed separately."""
    _require(projection in CHOICE_LABELS, "Choice projection required")
    validate_cases(cases)
    requests = [request for case in cases for request in _requests(case, projection)]
    indexed = _index_predictions(predictions, {_choice_key(row) for row in requests}, _choice_key)
    by_case = {case["case_id"]: case for case in cases}
    rows = []
    for request in requests:
        case = by_case[request["case_id"]]
        prediction = indexed.get(_choice_key(request), {"status": "missing"})
        _require(set(prediction) <= {"case_id", "axis", "passage_id", "claim_id", "status", "choice_id", "error"}, "Unexpected choice prediction fields")
        gold = _request_gold(case, request, projection)
        choice = prediction.get("choice_id")
        if prediction["status"] == "ok":
            _require(isinstance(choice, str) and choice in CHOICE_LABELS[projection], "Unknown or empty choice ID")
            accuracy = int(CHOICE_LABELS[projection][choice] == gold)
        else:
            _require(choice is None, "Unsuccessful prediction must not supply a choice")
            accuracy = None
        rows.append(_row_metadata(case, prediction["status"]) | {key: value for key, value in request.items()
                    if key in ("axis", "passage_id", "claim_id")} | {"accuracy": accuracy, "expected_label": gold})
    report = _summarize(rows, ["accuracy"])
    report["projection"] = projection
    report["total_decisions"] = len(rows)
    report["source_cases"] = len(cases)
    report["accuracy_over_all"] = sum(row["accuracy"] or 0 for row in rows) / len(rows)
    by_label = {}
    for label in CHOICE_LABELS[projection].values():
        items = [row for row in rows if row["expected_label"] == label]
        values = [row["accuracy"] for row in items if row["accuracy"] is not None]
        by_label[str(label)] = {"total_decisions": len(items), "scored_decisions": len(values),
                              "accuracy_scored": sum(values) / len(values) if values else None,
                              "accuracy_over_all": sum(values) / len(items) if items else None}
    report["by_expected_label"] = by_label
    defined = [item["accuracy_scored"] for item in by_label.values() if item["accuracy_scored"] is not None]
    report["macro_accuracy_scored"] = sum(defined) / len(defined) if defined else None
    report["macro_accuracy_defined_classes"] = len(defined)
    return report


def _write(path, payload, overwrite=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if overwrite else "x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)


def _protect_inputs(output, inputs):
    """Reject lexical, symlink and hardlink aliases before opening output."""
    output = Path(output)
    for source in inputs:
        source = Path(source)
        aliases = output.resolve() == source.resolve()
        if not aliases and output.exists() and source.exists():
            aliases = output.samefile(source)
        _require(not aliases, f"Output aliases protected input: {source}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline passage dataset: validate, export inputs, score existing predictions.")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "export", "score"):
        sub = commands.add_parser(command)
        sub.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
        sub.add_argument("--manifest", type=Path)
        if command != "validate":
            sub.add_argument("--split", choices=("train", "calibration", "test"), action="append")
            sub.add_argument("--view", choices=("full", "head_384"), action="append")
            sub.add_argument("--question-language", choices=LANGUAGES, action="append")
            sub.add_argument("--passage-language", choices=LANGUAGES, action="append")
            sub.add_argument("--projection", choices=PROJECTIONS, default="ranking")
            sub.add_argument("--output", type=Path, required=True)
            sub.add_argument("--overwrite", action="store_true")
        if command == "score":
            sub.add_argument("--predictions", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command != "validate":
            inputs = [args.dataset, args.manifest or args.dataset.parent / "manifest.json"]
            if args.command == "score":
                inputs.append(args.predictions)
            _protect_inputs(args.output, inputs)
        cases, digest = load_dataset(args.dataset, args.manifest)
        if args.command == "validate":
            report = {"status": "valid", "case_count": len(cases), "family_count": len({c["family_id"] for c in cases}),
                      "cases_sha256": digest, "evaluation_status": "not_run", "review": "agent_only_pending_human"}
        else:
            filters = {key: getattr(args, key) for key in ("split", "view", "question_language", "passage_language")}
            selected = select_cases(cases, **filters)
            if args.command == "export":
                requests = export_requests(selected, args.projection)
                payload = "".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in requests)
                report = {"evaluation_status": "not_run", "requests": len(requests), "projection": args.projection}
            else:
                predictions, prediction_bytes = _read_jsonl(args.predictions, allow_empty=True)
                report = score_rankings(selected, predictions) if args.projection == "ranking" else score_choices(selected, predictions, args.projection)
                report.update(dataset_sha256=digest, predictions_sha256=hashlib.sha256(prediction_bytes).hexdigest(),
                              eligible_cases=len(selected), excluded_cases=len(cases) - len(selected), filters=filters)
                payload = json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
                report = {key: value for key, value in report.items() if key not in ("rows", "by")}
            _write(args.output, payload, args.overwrite)
            report.update(eligible_cases=len(selected), excluded_cases=len(cases) - len(selected), filters=filters,
                          dataset_sha256=digest, output=str(args.output))
        print(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        parser.exit(2, f"Passage dataset error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
