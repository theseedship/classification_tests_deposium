"""Facade routing packs (issue #56): eight generic tool categories, FR/EN request families.

Three frozen tiers share the categories and the option rotation: easy
(`facade-routing-v1`, 40 families), advanced (48) and complex (48, which may
carry a previous exchange and asks for the category to use first). Synthetic
closed choices; references are authored without access to any router rule.
`validate_oracle` rejects any case that differs from its frozen definition.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "datasets/facade-routing-v1"
DATASET_ID = "facade-routing-v1"
ORDER = ("search", "analyze", "visualize", "graph", "evaluate", "process", "system", "none")
LETTERS = "abcdefgh"
SPLITS = ("train", "calibration", "test", "test", "test")
SPLITS_SIX = ("train", "calibration", "test", "test", "test", "test")
INTRO = {"fr": "Demande adressée à un assistant documentaire : « {request} »",
         "en": "Request sent to a document assistant: \"{request}\""}
INTRO_PREVIOUS = {"fr": "Échange précédent — {previous}\nNouvelle demande adressée à un assistant documentaire : « {request} »",
                  "en": "Previous exchange — {previous}\nNew request sent to a document assistant: \"{request}\""}
QUESTION = {"fr": "Quelle catégorie d'outils l'assistant doit-il utiliser pour cette demande ?",
            "en": "Which tool category should the assistant use for this request?"}
QUESTION_FIRST = {"fr": "Quelle catégorie d'outils l'assistant doit-il utiliser en premier pour cette demande ?",
                  "en": "Which tool category should the assistant use first for this request?"}
# dataset id -> (case prefix, families, splits per category, question, frozen date, version)
PACKS = {
    "facade-routing-v1": ("frv1", 40, SPLITS, QUESTION, "2026-10-31", "1.0.0-exploratory"),
    "facade-routing-advanced-v1": ("fra1", 48, SPLITS_SIX, QUESTION, "2026-11-01", "1.0.0-exploratory"),
    "facade-routing-complex-v1": ("frc1", 48, SPLITS_SIX, QUESTION_FIRST, "2026-11-01", "1.0.0-exploratory"),
}
PREFIXES = tuple(prefix + "-" for prefix, *_ in PACKS.values())


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _build(dataset_id=DATASET_ID):
    prefix, family_count, splits, question, frozen_date, version = PACKS[dataset_id]
    directory = ROOT / "datasets" / dataset_id
    spec = json.loads((directory / "specs.json").read_text(encoding="utf-8"))
    categories, families = spec["categories"], spec["families"]
    assert tuple(categories) == ORDER and len(families) == family_count
    cases, rank = [], Counter()
    for index, family in enumerate(families):
        intent = family["intent"]
        assert intent in ORDER
        split = splits[rank[intent]]
        rank[intent] += 1
        shift = (index * 3) % len(ORDER)
        ordered = ORDER[shift:] + ORDER[:shift]
        answer = LETTERS[ordered.index(intent)]
        scenario = prefix + "-" + family["id"]
        for lang in ("fr", "en"):
            previous = family.get("previous")
            context = (INTRO_PREVIOUS[lang].format(previous=previous[lang], request=family["request"][lang]) if previous
                       else INTRO[lang].format(request=family["request"][lang]))
            visible = {"context": context, "question": question[lang],
                       "options": [{"id": letter, "description": categories[key][lang]} for letter, key in zip(LETTERS, ordered)]}
            identity = f"{scenario}-{lang}"
            cases.append({
                "schema_version": "deposium.case/v2", "case_id": identity, "scenario_id": scenario,
                "translation_family": scenario, "document_ids": ["synthetic:" + scenario], "split": split,
                "language": lang, "pack": "RESEARCH", "contract_id": "bench.context-choice", "input": visible,
                "reference": {"assertions": [{"path": "/choice_id", "op": "equals", "value": answer}], "abstention_allowed": False,
                              "rationale": family["rationale"] + " Authored synthetic reference, written without access to any router rule; human review not performed."},
                "evaluation": {"domain": "documentary", "difficulty": family["difficulty"], "base_case_id": identity,
                               "related_contract_ids": ["mcps.scope-dispatch", "mcps.semantic-source-route"], "review": "agent_only",
                               "task_type": "routing.facade." + family["kind"],
                               "oracle": {"kind": "human_reference", "params": {"task": intent, "benchmark_pack": dataset_id, "kind": family["kind"]},
                                          "choices": {letter: key for letter, key in zip(LETTERS, ordered)}, "base_input": deepcopy(visible)},
                               "length": None}})
    payload = "".join(encode(c) + "\n" for c in cases).encode("utf-8")
    count = lambda f: dict(sorted(Counter(map(f, cases)).items()))
    manifest = {"schema_version": "deposium.research-dataset/v1", "dataset_id": dataset_id, "version": version,
                "frozen_date": frozen_date, "status": "frozen_before_first_candidate_prediction",
                "case_schema": "deposium.case/v2", "cases_file": "cases.jsonl", "cases_sha256": hashlib.sha256(payload).hexdigest(),
                "spec_sha256": hashlib.sha256((directory / "specs.json").read_bytes()).hexdigest(),
                "case_count": len(cases), "family_count": len(families), "options_per_case": len(ORDER),
                "counts_by_language": count(lambda c: c["language"]), "counts_by_split": count(lambda c: c["split"]),
                "counts_by_category": count(lambda c: c["evaluation"]["oracle"]["params"]["task"]),
                "counts_by_kind": count(lambda c: c["evaluation"]["oracle"]["params"]["kind"]),
                "counts_by_answer_position": count(lambda c: c["reference"]["assertions"][0]["value"]),
                "reference_review": "agent_only_pending_human",
                "authoring": spec["authoring"]}
    return payload, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"




@lru_cache(maxsize=None)
def _frozen(dataset_id=DATASET_ID):
    payload, manifest = _build(dataset_id)
    return payload, manifest, {json.loads(line)["case_id"]: json.loads(line) for line in payload.decode("utf-8").splitlines()}


def build(dataset_id=DATASET_ID):
    payload, manifest, _ = _frozen(dataset_id)
    return payload, manifest


def build_cases(dataset_id=DATASET_ID):
    return [deepcopy(case) for case in _frozen(dataset_id)[2].values()]


def _pack_of(case_id):
    for dataset_id, (prefix, *_rest) in PACKS.items():
        if isinstance(case_id, str) and case_id.startswith(prefix + "-"):
            return dataset_id
    raise KeyError(case_id)


def validate_oracle(case):
    try:
        expected = _frozen(_pack_of(case["case_id"]))[2][case["case_id"]]
    except (KeyError, TypeError):
        raise ValueError("Unknown frozen facade-routing case") from None
    if case != expected:
        raise ValueError("Facade-routing case differs from its frozen definition")
