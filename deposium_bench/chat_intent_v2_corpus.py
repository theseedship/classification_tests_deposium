"""Frozen, private human-labeled chat references; no data or inference at import.

Only the bounded message preview and generic frozen cards enter candidate input.
Review dates and annotation lineage are archival claims, not proof of review.
Keep real rows, cases, source identities and all derived archives private.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from .chat_intent_corpus import INTENTS, LETTERS, REPORT_FIELDS, _review_date

POLICY_ID = "rubric-v2-frozen-20261108"
CARDS_PATH = Path(__file__).parent / "data" / "intent-choice-cards.v2.json"
CARDS_SHA256 = "3ebdeff004bdd4b40c07bfbcdab5b5109095b0fe2a6b78220257b2630676c686"
OPTIONAL_FIELDS = (*REPORT_FIELDS, "source_environment", "source_record_id",
                   "external_voter_eligible", "annotation_policy_id", "annotation_policy_sha256")
PARAM_FIELDS = {*OPTIONAL_FIELDS, "benchmark_pack", "decision", "reviewed_at",
                "reviewed_date", "label", "split_group_id", "policy_id", "cards_sha256"}
_ID = r"[a-zA-Z0-9][a-zA-Z0-9._-]*"
_GROUP = r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}"


def load_cards():
    """Read an independent copy, rejecting any change to the frozen rubric bytes."""
    payload = CARDS_PATH.read_bytes()
    if hashlib.sha256(payload).hexdigest() != CARDS_SHA256:
        raise ValueError("Frozen v2 intent cards changed")
    cards = json.loads(payload)
    if (cards["schema_version"] != "deposium.intent-choice-cards/v2"
            or cards["policy_id"] != POLICY_ID
            or [c["id"] for c in cards["intents"]] != list(INTENTS)
            or [c["option_id"] for c in cards["intents"]] != list(LETTERS)):
        raise ValueError("Invalid frozen v2 intent cards")
    return cards


def options(language):
    """Return canonical a..j descriptions in the requested supported language."""
    if language not in ("fr", "en"):
        raise ValueError("Chat intent language must be fr or en")
    return [{"id": card["option_id"], "description": card["description"][language]}
            for card in load_cards()["intents"]]


def _metadata(row):
    result = {field: deepcopy(row.get(field)) for field in OPTIONAL_FIELDS}
    # Metadata never enters candidate input, but must remain finite plain JSON.
    try:
        json.dumps(result, allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError("Chat intent metadata must be finite JSON") from None
    if result["external_voter_eligible"] is not None and type(result["external_voter_eligible"]) is not bool:
        raise ValueError("external_voter_eligible must be boolean or null")
    digest = result["annotation_policy_sha256"]
    if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise ValueError("annotation_policy_sha256 must be a SHA-256 or null")
    return result


def _build(row, index, language, pack_id, split):
    if not isinstance(row, dict):
        raise ValueError("Expected a joined human-labeled row")
    if type(index) is not int or index < 0:
        raise ValueError("Case index must be a nonnegative integer")
    if not isinstance(pack_id, str) or not re.fullmatch(_ID, pack_id):
        raise ValueError("Invalid benchmark pack ID")
    if split not in ("calibration", "test"):
        raise ValueError("Real v2 cases require calibration or test split")
    preview = row.get("message_preview")
    if not isinstance(preview, str) or not preview.strip() or not preview[:1500].strip():
        raise ValueError("message_preview must contain nonempty bounded text")
    label = row.get("label")
    if not isinstance(label, str) or label not in INTENTS:
        raise ValueError("Unknown human-labeled intent")
    if row.get("decision") != "labeled":
        raise ValueError("Manual no-prelabel reference requires decision=labeled")
    if row.get("alternatives") is not None:
        raise ValueError("Real v2 references require one explicit label")
    literal_date = row.get("reviewed_at")
    reviewed_date = _review_date(literal_date)
    group = row.get("split_group_id")
    if not isinstance(group, str) or not re.fullmatch(_GROUP, group):
        raise ValueError("Invalid private split group ID")
    cards = load_cards()
    visible = {"context": cards["intro"][language].format(message=preview[:cards["max_state_chars"]]),
               "question": cards["question"][language], "options": options(language)}
    identity = f"cir2-{index:04d}-{language}"
    # Shared family identity enforces leakage checks across translated/derived rows.
    family = f"cir2g-{group}"
    params = _metadata(row)
    params.update(benchmark_pack=pack_id, decision="labeled", reviewed_at=literal_date,
                  reviewed_date=reviewed_date, label=label, split_group_id=group,
                  policy_id=POLICY_ID, cards_sha256=CARDS_SHA256)
    return {
        "schema_version": "deposium.case/v2", "case_id": identity,
        "scenario_id": family, "translation_family": family,
        "document_ids": [f"private:{pack_id}:{group}"], "split": split,
        "language": language, "pack": "RESEARCH", "contract_id": "bench.context-choice",
        "input": visible,
        "reference": {"assertions": [{"path": "/choice_id", "op": "equals",
                                       "value": LETTERS[INTENTS.index(label)]}],
                      "abstention_allowed": False,
                      "rationale": "Human-labeled production message without prelabels; owner annotation "
                                   f"recorded on {reviewed_date}; frozen policy {POLICY_ID}."},
        "evaluation": {"domain": "documentary", "difficulty": "D2", "base_case_id": identity,
                       "related_contract_ids": ["mcps.scope-dispatch"], "review": "agent_only",
                       "task_type": "routing.chat-intent.real.v2",
                       "oracle": {"kind": "human_reference", "base_input": deepcopy(visible),
                                  "choices": dict(zip(LETTERS, INTENTS)), "params": params},
                       "length": None}}


def make_case(row, index, language, pack_id, split):
    """Build one private case; callers freeze whole-family split assignments.

    Required row keys: message_preview, label, decision='labeled', reviewed_at,
    split_group_id. Optional archival fields are enumerated in OPTIONAL_FIELDS.
    Extra joined row fields are ignored and can never become candidate inputs.
    reviewed_at is retained literally alongside its normalized calendar date.
    """
    if language not in ("fr", "en"):
        raise ValueError("Chat intent language must be fr or en")
    case = _build(row, index, language, pack_id, split)
    validate_oracle(case)
    return case


def validate_oracle(case):
    """Reject altered inputs, references, provenance structure or frozen policy.

    A self-consistent split/annotation rewrite needs external frozen archive
    hashes to detect. Shared validate_cases enforces cross-case family splits.
    """
    try:
        match = re.fullmatch(r"cir2-([0-9]{4,})-(fr|en)", case["case_id"])
        if match is None or match[1] != f"{int(match[1]):04d}":
            raise ValueError("Invalid v2 chat case identity")
        params = case["evaluation"]["oracle"]["params"]
        if (set(params) != PARAM_FIELDS or params["policy_id"] != POLICY_ID
                or params["cards_sha256"] != CARDS_SHA256):
            raise ValueError("Invalid frozen v2 oracle policy or fields")
        language = match[2]
        cards = load_cards()
        context = case["input"]["context"]
        before, after = cards["intro"][language].split("{message}")
        if (not isinstance(context, str) or not context.startswith(before)
                or not context.endswith(after)):
            raise ValueError("Invalid bounded preview template")
        preview = context[len(before):-len(after)]
        if len(preview) > cards["max_state_chars"]:
            raise ValueError("Preview exceeds frozen bound")
        row = {field: deepcopy(params[field]) for field in OPTIONAL_FIELDS}
        row.update(message_preview=preview, label=params["label"], decision=params["decision"],
                   reviewed_at=params["reviewed_at"], split_group_id=params["split_group_id"])
        expected = _build(row, int(match[1]), language, params["benchmark_pack"], case["split"])
        # JSON comparison distinguishes bool from int, unlike Python ==.
        if json.dumps(case, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
            raise ValueError("V2 chat case differs from its frozen input/reference contract")
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError) as error:
        raise ValueError("Malformed v2 chat intent oracle") from error
