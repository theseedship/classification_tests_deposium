"""Build the frozen, synthetic directional relation choices."""
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from .cases import RESEARCH_CONTRACT, RESEARCH_VERSION

DATASET_ID = "relation-predicate-choice-v1"
PREFIX = "rpc1-"
DATASET = Path(__file__).resolve().parents[1] / "datasets" / DATASET_ID
LABELS = {
    "disciple_of": ("A was an apprentice or student of B.", "A a été l'élève ou l'apprenti de B."),
    "teacher_of": ("A taught B as a student or apprentice.", "A a formé B en tant qu'élève ou apprenti."),
    "criticizes": ("A explicitly criticizes B or B's work.", "A critique explicitement B ou le travail de B."),
    "translated_by": ("A was translated by B.", "A a été traduit par B."),
    "edited_by": ("A was edited by B.", "B a assuré le travail éditorial sur A."),
    "part_of": ("A is a constituent part of B.", "A est un composant de B."),
    "has_part": ("A contains B as a constituent part.", "A comprend B comme composant."),
    "uses": ("A employs B as a separate tool.", "A se sert de B comme outil séparé."),
    "none": ("The excerpt establishes none of the listed relations from A to B.",
             "L'extrait n'établit aucune des relations proposées de A vers B."),
}
INSTRUCTIONS = (
    "Using only the excerpt, which relation does it establish from entity A to entity B?",
    "En vous fondant uniquement sur l'extrait, quelle relation établit-il de l'entité A vers l'entité B ?",
)


@lru_cache(maxsize=1)
def _canonical():
    specs = json.loads((DATASET / "specs.json").read_bytes())
    cases = {}
    for index, spec in enumerate(specs):
        family = PREFIX + spec["family"]
        labels = [*spec["options"], "none"]
        # Hold presentation fixed across perspectives and controls in each family.
        rotation = index % len(labels)
        labels = labels[rotation:] + labels[:rotation]
        for language_index, language in enumerate(("en", "fr")):
            options = [{"id": key, "description": LABELS[label][language_index]}
                       for key, label in zip("abcd", labels)]
            choices = {option["id"]: label for option, label in zip(options, labels)}
            for variant, reverse, no_evidence in (
                ("forward", False, False), ("reverse", True, False), ("no-evidence", False, True),
            ):
                a, b = [(entity[0], entity[language_index + 1]) for entity in spec["entities"]]
                if reverse:
                    a, b = b, a
                excerpt = spec[language][no_evidence]
                header = ("Excerpt", "Extrait")[language_index]
                visible = {
                    "context": f"A: {a[0]} ({a[1]})\nB: {b[0]} ({b[1]})\n{header}: {excerpt}",
                    "question": INSTRUCTIONS[language_index],
                    "options": options,
                }
                gold = "none" if no_evidence else spec["reverse" if reverse else "gold"]
                answer = labels.index(gold)
                case_id = f"{family}-{language}-{variant}"
                cases[case_id] = {
                    "schema_version": RESEARCH_VERSION, "case_id": case_id, "scenario_id": family,
                    "translation_family": family, "document_ids": [f"synthetic:{family}"],
                    "split": spec["split"], "language": language, "pack": "RESEARCH",
                    "contract_id": RESEARCH_CONTRACT, "input": visible,
                    "reference": {
                        "assertions": [{"path": "/choice_id", "op": "equals", "value": options[answer]["id"]}],
                        "abstention_allowed": False,
                        "rationale": "Exact authored answer for this excerpt and endpoint order. Human review pending.",
                    },
                    "evaluation": {
                        "domain": "documentary", "difficulty": "D2", "base_case_id": case_id,
                        "related_contract_ids": ["mcps.evidence-attribution"], "review": "agent_only",
                        "task_type": f"relation-predicate.{variant}", "length": None,
                        "oracle": {"choices": choices, "gold_predicate": gold},
                    },
                }
    return cases


def validate_oracle(case):
    if case != _canonical().get(case["evaluation"]["base_case_id"]):
        raise ValueError("Relation-predicate case differs from its frozen synthetic specification.")


def frozen_files():
    cases = list(_canonical().values())
    wire = "".join(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n" for case in cases).encode()
    manifest = {
        "schema_version": "deposium.research-dataset/v1",
        "dataset_id": DATASET_ID, "version": "1.0.0-exploratory", "case_schema": RESEARCH_VERSION,
        "cases_file": "cases.jsonl", "contract_id": RESEARCH_CONTRACT,
        "cases_sha256": hashlib.sha256(wire).hexdigest(),
        "spec_sha256": hashlib.sha256((DATASET / "specs.json").read_bytes()).hexdigest(),
        "case_count": len(cases), "family_count": len({case["translation_family"] for case in cases}),
        "counts_by_split": dict(Counter(case["split"] for case in cases)),
        "counts_by_language": dict(Counter(case["language"] for case in cases)),
        "reference_review": "agent_only_pending_human",
    }
    return {"cases.jsonl": wire, "manifest.json": (json.dumps(manifest, indent=2) + "\n").encode()}
