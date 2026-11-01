"""Facade routing with human confirmation: can a classifier tell when to ask a human?

One specification, two frozen packs with the same 90 FR/EN requests:

* `facade-routing-hitl-v1`: nine options, the eight routing categories plus
  "human confirmation" (ask the user to choose or confirm before acting);
* `facade-routing-hitl-8opt-v1`: the eight usual options only. A request that
  hesitates between two categories accepts either candidate; an irreversible
  request expects its category. Run with this pack, a model's own confidence
  can be thresholded offline to decide when to ask a human.

References are authored without access to any router rule. `validate_oracle`
rejects any case that differs from its frozen definition.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from .facade_corpus import INTRO, QUESTION

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "datasets/facade-routing-hitl-v1/specs.json"
CATEGORIES = ("search", "analyze", "visualize", "graph", "evaluate", "process", "system", "none")
# dataset id -> (case prefix, option keys, rotation step coprime with the option count)
PACKS = {"facade-routing-hitl-v1": ("frh1", CATEGORIES + ("hitl",), 2),
         "facade-routing-hitl-8opt-v1": ("frg1", CATEGORIES, 3)}
PREFIXES = tuple(prefix + "-" for prefix, *_ in PACKS.values())
LETTERS = "abcdefghi"


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def expected(family, with_hitl):
    """Reference category keys for one family in one pack variant."""
    if family["intent"] != "hitl":
        return [family["intent"]]
    return ["hitl"] if with_hitl else list(family["candidates"])


def _build(dataset_id):
    prefix, order, step = PACKS[dataset_id]
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    categories, families = spec["categories"], spec["families"]
    assert set(categories) == set(CATEGORIES) | {"hitl"} and len(families) == 45
    with_hitl = "hitl" in order
    cases = []
    for index, family in enumerate(families):
        shift = (index * step) % len(order)
        ordered = order[shift:] + order[:shift]
        letters = LETTERS[:len(ordered)]
        answers = [letters[ordered.index(key)] for key in expected(family, with_hitl)]
        assertion = ({"path": "/choice_id", "op": "equals", "value": answers[0]} if len(answers) == 1
                     else {"path": "/choice_id", "op": "one_of", "value": sorted(answers)})
        scenario = prefix + "-" + family["id"]
        for lang in ("fr", "en"):
            visible = {"context": INTRO[lang].format(request=family["request"][lang]), "question": QUESTION[lang],
                       "options": [{"id": letter, "description": categories[key][lang]} for letter, key in zip(letters, ordered)]}
            identity = f"{scenario}-{lang}"
            cases.append({
                "schema_version": "deposium.case/v2", "case_id": identity, "scenario_id": scenario,
                "translation_family": scenario, "document_ids": ["synthetic:" + scenario], "split": family["split"],
                "language": lang, "pack": "RESEARCH", "contract_id": "bench.context-choice", "input": visible,
                "reference": {"assertions": [assertion], "abstention_allowed": False,
                              "rationale": family["rationale"] + " Authored synthetic reference, written without access to any router rule; human review not performed."},
                "evaluation": {"domain": "documentary", "difficulty": family["difficulty"], "base_case_id": identity,
                               "related_contract_ids": ["mcps.scope-dispatch", "mcps.semantic-source-route"], "review": "agent_only",
                               "task_type": "routing.facade_hitl." + family["kind"],
                               "oracle": {"kind": "human_reference",
                                          "params": {"task": family["intent"], "benchmark_pack": dataset_id, "kind": family["kind"],
                                                     "candidates": family.get("candidates", [family["intent"]]),
                                                     "needs_human": family["intent"] == "hitl"},
                                          "choices": dict(zip(letters, ordered)), "base_input": deepcopy(visible)},
                               "length": None}})
    payload = "".join(encode(c) + "\n" for c in cases).encode("utf-8")
    count = lambda f: dict(sorted(Counter(map(f, cases)).items()))
    manifest = {"schema_version": "deposium.research-dataset/v1", "dataset_id": dataset_id, "version": "1.0.0-exploratory",
                "frozen_date": "2026-11-01", "status": "frozen_before_first_candidate_prediction",
                "case_schema": "deposium.case/v2", "cases_file": "cases.jsonl", "cases_sha256": hashlib.sha256(payload).hexdigest(),
                "spec_sha256": hashlib.sha256(SPEC.read_bytes()).hexdigest(), "case_count": len(cases),
                "family_count": len(families), "options_per_case": len(order),
                "counts_by_split": count(lambda c: c["split"]), "counts_by_language": count(lambda c: c["language"]),
                "counts_by_intent": count(lambda c: c["evaluation"]["oracle"]["params"]["task"]),
                "counts_by_kind": count(lambda c: c["evaluation"]["oracle"]["params"]["kind"]),
                "counts_by_assertion": count(lambda c: c["reference"]["assertions"][0]["op"]),
                "reference_review": "agent_only_pending_human", "authoring": spec["authoring"]}
    return payload, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"


@lru_cache(maxsize=None)
def _frozen(dataset_id):
    payload, manifest = _build(dataset_id)
    return payload, manifest, {json.loads(line)["case_id"]: json.loads(line) for line in payload.decode("utf-8").splitlines()}


def build(dataset_id):
    payload, manifest, _ = _frozen(dataset_id)
    return payload, manifest


def build_cases(dataset_id):
    return [deepcopy(case) for case in _frozen(dataset_id)[2].values()]


def validate_oracle(case):
    try:
        dataset_id = next(d for d, (prefix, *_r) in PACKS.items() if case["case_id"].startswith(prefix + "-"))
        frozen = _frozen(dataset_id)[2][case["case_id"]]
    except (KeyError, TypeError, StopIteration):
        raise ValueError("Unknown frozen facade-routing-hitl case") from None
    if case != frozen:
        raise ValueError("Facade-routing-hitl case differs from its frozen definition")
