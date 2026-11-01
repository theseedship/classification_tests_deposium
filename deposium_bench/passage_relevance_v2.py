"""Passage relevance v2: a three-level realignment of the passage-evidence relevance projection.

Derived deterministically from the frozen passage-evidence-v1 pack, rotation-0
calibration and test pools (the pools of every published passage campaign).
Each case is one question and one passage, as in the v1 relevance projection,
with three options instead of four:

* direct: establishes or refutes the requested fact (v1 grade 3);
* partial: supplies part of the necessary evidence (v1 grade 2);
* no usable evidence: off-topic, or about another entity, condition or value
  than the one asked (v1 grades 1 and 0 merged).

Why: v1 separated "concerns the topic without deciding" (1) from "irrelevant"
(0). For the decoys of this pack (a sibling variant, another condition,
another subject with the same number) both descriptions fit, every observed
model splits them unpredictably, and no retrieval decision uses the
difference: neither passage may serve as evidence. Passages whose v1 role is
`value_premise` are excluded: they only matter through another passage that
binds the entity to the value, which a single-passage judgement cannot see.
Identical candidate inputs are kept once. No v1 reference is changed.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "datasets/passage-relevance-v2"
DATASET_ID = "passage-relevance-v2"
SOURCE = ROOT / "datasets/passage-evidence-v1/cases.jsonl"
SOURCE_SHA256 = "35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476"
PREFIX = "prv2"
SPLITS = ("calibration", "test")
EXCLUDED_ROLES = {"value_premise"}
LABELS = ("direct", "partial", "no_usable_evidence")
LETTERS = "abc"
GRADE_TO_LABEL = {3: "direct", 2: "partial", 1: "no_usable_evidence", 0: "no_usable_evidence"}
NO_EVIDENCE = {
    "fr": "Il n'apporte aucune preuve utilisable : il est hors sujet, ou porte sur une autre entité, condition ou valeur que celle demandée.",
    "en": "It provides no usable evidence: it is off-topic, or concerns another entity, condition or value than the one asked.",
    "de": "Sie liefert keinen verwertbaren Beleg: Sie ist themenfremd oder betrifft eine andere Einheit, Bedingung oder einen anderen Wert als den erfragten.",
    "es": "No aporta ninguna prueba utilizable: no trata el tema o se refiere a otra entidad, condición o valor distinto del solicitado.",
    "it": "Non fornisce alcuna prova utilizzabile: è fuori tema o riguarda un'entità, una condizione o un valore diversi da quelli richiesti.",
    "pt": "Não fornece nenhuma prova utilizável: está fora do tema ou refere-se a outra entidade, condição ou valor diferente do solicitado.",
}


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _build():
    from .passage_dataset import _TEXT, export_requests, load_dataset
    from .passage_observation import select_pilot
    source, digest = load_dataset(SOURCE)
    assert digest == SOURCE_SHA256, "passage-evidence-v1 changed"
    cases, seen = [], {}
    for split in SPLITS:
        selected = select_pilot(source, split)
        by_id = {case["case_id"]: case for case in selected}
        for request in export_requests(selected, "relevance"):
            case = by_id[request["case_id"]]
            item = next(i for i in case["annotations"]["relevance"] if i["passage_id"] == request["passage_id"])
            if item["role"] in EXCLUDED_ROLES:
                continue
            lang = case["question_language"]
            _, _, question, options, *_ = _TEXT[lang]
            texts = {"direct": options[0], "partial": options[1], "no_usable_evidence": NO_EVIDENCE[lang]}
            label = GRADE_TO_LABEL[item["grade"]]
            # Rotate the option order by the unrotated input digest so no position carries a label.
            base = hashlib.sha256(encode([request["input"]["context"], question]).encode()).hexdigest()
            shift = int(base[:8], 16) % len(LABELS)
            ordered = LABELS[shift:] + LABELS[:shift]
            visible = {"context": request["input"]["context"], "question": question,
                       "options": [{"id": letter, "description": texts[name]} for letter, name in zip(LETTERS, ordered)]}
            key = hashlib.sha256(encode(visible).encode()).hexdigest()
            if key in seen:
                # Identical visible input must carry the same reference; keep it once.
                assert seen[key] == (label, split), "identical input with a different reference or split"
                continue
            seen[key] = (label, split)
            family = case["family_id"]
            identity = f"{PREFIX}-{split}-{key[:16]}"
            answer = LETTERS[ordered.index(label)]
            cases.append({
                "schema_version": "deposium.case/v2", "case_id": identity,
                "scenario_id": f"{PREFIX}-{family}-{case['scenario_id']}", "translation_family": f"{PREFIX}-{family}",
                "document_ids": [f"synthetic:{PREFIX}-{family}"], "split": split, "language": lang, "pack": "RESEARCH",
                "contract_id": "bench.context-choice", "input": visible,
                "reference": {"assertions": [{"path": "/choice_id", "op": "equals", "value": answer}], "abstention_allowed": False,
                              "rationale": f"v1 relevance grade {item['grade']} ({item['role']}) mapped to {label}. "
                                           "Agent-authored synthetic reference; human review not performed."},
                "evaluation": {"domain": "documentary", "difficulty": "D2", "base_case_id": identity,
                               "related_contract_ids": ["mcps.semantic-source-route"], "review": "agent_only",
                               "task_type": "passage.relevance_v2." + item["role"],
                               "oracle": {"kind": "human_reference",
                                          "params": {"task": label, "benchmark_pack": DATASET_ID, "kind": item["role"],
                                                     "v1_grade": item["grade"], "scenario": case["scenario_id"],
                                                     "view": case["view"], "direction": f"{lang}->{case['passage_language']}"},
                                          "choices": dict(zip(LETTERS, ordered)), "base_input": deepcopy(visible)},
                               "length": None}})
    payload = "".join(encode(c) + "\n" for c in cases).encode("utf-8")
    count = lambda f: dict(sorted(Counter(map(f, cases)).items()))
    manifest = {"schema_version": "deposium.research-dataset/v1", "dataset_id": DATASET_ID, "version": "1.0.0-exploratory",
                "frozen_date": "2026-11-01", "status": "frozen_before_first_candidate_prediction",
                "case_schema": "deposium.case/v2", "cases_file": "cases.jsonl",
                "cases_sha256": hashlib.sha256(payload).hexdigest(), "source_dataset": "passage-evidence-v1",
                "source_sha256": SOURCE_SHA256, "selection": "rotation-0 calibration and test pools, unique visible inputs",
                "excluded_roles": sorted(EXCLUDED_ROLES), "case_count": len(cases), "options_per_case": 3,
                "counts_by_split": count(lambda c: c["split"]), "counts_by_language": count(lambda c: c["language"]),
                "counts_by_label": count(lambda c: c["evaluation"]["oracle"]["params"]["task"]),
                "counts_by_v1_grade": count(lambda c: str(c["evaluation"]["oracle"]["params"]["v1_grade"])),
                "counts_by_role": count(lambda c: c["evaluation"]["oracle"]["params"]["kind"]),
                "counts_by_answer_position": count(lambda c: c["reference"]["assertions"][0]["value"]),
                "reference_review": "agent_only_pending_human"}
    return payload, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"


@lru_cache(maxsize=1)
def _frozen():
    payload, manifest = _build()
    return payload, manifest, {json.loads(line)["case_id"]: json.loads(line) for line in payload.decode("utf-8").splitlines()}


def build():
    payload, manifest, _ = _frozen()
    return payload, manifest


def build_cases():
    return [deepcopy(case) for case in _frozen()[2].values()]


def validate_oracle(case):
    try:
        expected = _frozen()[2][case["case_id"]]
    except (KeyError, TypeError):
        raise ValueError("Unknown frozen passage-relevance-v2 case") from None
    if case != expected:
        raise ValueError("Passage-relevance-v2 case differs from its frozen definition")
