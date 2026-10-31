"""Facade routing pack (issue #56): eight generic tool categories, forty FR/EN request families.

Frozen synthetic closed choices; references are authored without access to any
router rule. `validate_oracle` rejects any case that differs from its frozen
definition, as the physics pack does.
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
INTRO = {"fr": "Demande adressée à un assistant documentaire : « {request} »",
         "en": "Request sent to a document assistant: \"{request}\""}
QUESTION = {"fr": "Quelle catégorie d'outils l'assistant doit-il utiliser pour cette demande ?",
            "en": "Which tool category should the assistant use for this request?"}


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _build():
    spec = json.loads((DIRECTORY / "specs.json").read_text(encoding="utf-8"))
    categories, families = spec["categories"], spec["families"]
    assert tuple(categories) == ORDER and len(families) == 40
    cases, rank = [], Counter()
    for index, family in enumerate(families):
        intent = family["intent"]
        assert intent in ORDER
        split = SPLITS[rank[intent]]
        rank[intent] += 1
        shift = (index * 3) % len(ORDER)
        ordered = ORDER[shift:] + ORDER[:shift]
        answer = LETTERS[ordered.index(intent)]
        scenario = "frv1-" + family["id"]
        for lang in ("fr", "en"):
            visible = {"context": INTRO[lang].format(request=family["request"][lang]), "question": QUESTION[lang],
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
                               "oracle": {"kind": "human_reference", "params": {"task": intent, "benchmark_pack": DATASET_ID, "kind": family["kind"]},
                                          "choices": {letter: key for letter, key in zip(LETTERS, ordered)}, "base_input": deepcopy(visible)},
                               "length": None}})
    payload = "".join(encode(c) + "\n" for c in cases).encode("utf-8")
    count = lambda f: dict(sorted(Counter(map(f, cases)).items()))
    manifest = {"schema_version": "deposium.research-dataset/v1", "dataset_id": DATASET_ID, "version": "1.0.0-exploratory",
                "frozen_date": "2026-10-31", "status": "frozen_before_first_candidate_prediction",
                "case_schema": "deposium.case/v2", "cases_file": "cases.jsonl", "cases_sha256": hashlib.sha256(payload).hexdigest(),
                "spec_sha256": hashlib.sha256((DIRECTORY / "specs.json").read_bytes()).hexdigest(),
                "case_count": len(cases), "family_count": len(families), "options_per_case": len(ORDER),
                "counts_by_language": count(lambda c: c["language"]), "counts_by_split": count(lambda c: c["split"]),
                "counts_by_category": count(lambda c: c["evaluation"]["oracle"]["params"]["task"]),
                "counts_by_kind": count(lambda c: c["evaluation"]["oracle"]["params"]["kind"]),
                "counts_by_answer_position": count(lambda c: c["reference"]["assertions"][0]["value"]),
                "reference_review": "agent_only_pending_human",
                "authoring": spec["authoring"]}
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
        raise ValueError("Unknown frozen facade-routing case") from None
    if case != expected:
        raise ValueError("Facade-routing case differs from its frozen definition")
