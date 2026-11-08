"""Build private reviewed chat cases and explicitly synthetic fixture cases.

No data are read at import and no dataset is exported by this module. Callers
must keep real messages and generated cases in private storage. The oracle
checks annotation integrity, not independent semantic truth or authenticity of
human review. Fixed option positions are a limitation of this first version.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import json
from pathlib import Path
import re

CARDS_PATH = Path(__file__).parent / "data" / "intent-choice-cards.v1.json"
INTENTS = ("greeting", "meta_question", "search_query", "complex_analysis",
           "graph_query", "instruction", "web_search", "geo_analysis",
           "connector_search", "opendata")
LETTERS = "abcdefghij"
REPORT_FIELDS = ("source", "tier_used", "method", "day", "version_period",
                 "terminal_state", "retrieval_outcome")
FIXTURE_RATIONALE = (
    "Synthetic authored fixture reference; owner human review not performed."
)


def load_cards():
    """Load and validate the generic bilingual cards; return an independent copy."""
    cards = json.loads(CARDS_PATH.read_text(encoding="utf-8"))
    try:
        if (set(cards) != {"schema_version", "question_key", "max_state_chars",
                           "intro", "question", "intents"}
                or cards["schema_version"] != "deposium.intent-choice-cards/v1"
                or cards["question_key"] != "intent"
                or type(cards["max_state_chars"]) is not int
                or cards["max_state_chars"] != 1500
                or not isinstance(cards["intents"], list)
                or len(cards["intents"]) != 10):
            raise ValueError("Invalid intent cards contract")
        for field in ("intro", "question"):
            if set(cards[field]) != {"fr", "en"}:
                raise ValueError("Invalid card languages")
            for text in cards[field].values():
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("Empty card text")
                if field == "intro" and (text.count("{message}") != 1
                                        or text.replace("{message}", "").count("{")
                                        or text.replace("{message}", "").count("}")):
                    raise ValueError("Invalid message template")
        descriptions = {"fr": set(), "en": set()}
        for intent, letter, card in zip(INTENTS, LETTERS, cards["intents"]):
            if (set(card) != {"id", "option_id", "description"}
                    or card["id"] != intent or card["option_id"] != letter
                    or set(card["description"]) != {"fr", "en"}):
                raise ValueError("Invalid canonical intent order")
            for language, text in card["description"].items():
                if not isinstance(text, str) or not text.strip() or text in descriptions[language]:
                    raise ValueError("Empty or duplicate intent description")
                descriptions[language].add(text)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Malformed intent cards") from error
    return cards


def options(language):
    """Return ten fresh choices in canonical order, with localized descriptions."""
    if language not in ("fr", "en"):
        raise ValueError("Chat intent language must be fr or en")
    return [{"id": c["option_id"], "description": c["description"][language]}
            for c in load_cards()["intents"]]


def _review_date(value):
    if not isinstance(value, str):
        raise ValueError("reviewed_at must be an ISO date or timestamp")
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value).isoformat()
        if not re.match(r"^\d{4}-\d{2}-\d{2}T", value):
            raise ValueError("Invalid ISO timestamp")
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        raise ValueError("reviewed_at must be an ISO date or timestamp") from None


def _assertion(label, alternatives):
    if label not in INTENTS:
        raise ValueError("Unknown reviewed or authored intent label")
    mapping = dict(zip(INTENTS, LETTERS))
    if alternatives is None:
        return {"path": "/choice_id", "op": "equals", "value": mapping[label]}
    if (not isinstance(alternatives, list) or not alternatives
            or any(not isinstance(x, str) or x not in INTENTS for x in alternatives)
            or len(set(alternatives)) != len(alternatives) or label not in alternatives):
        raise ValueError("Alternatives must be unique intent IDs including the label")
    return {"path": "/choice_id", "op": "one_of",
            "value": [mapping[x] for x in alternatives]}


def _build(row, index, language, pack_id, fixture):
    if not isinstance(row, dict):
        raise ValueError("Expected a reviewed or synthetic fixture row")
    if type(index) is not int or index < 0:
        raise ValueError("Case index must be a nonnegative integer")
    if not isinstance(pack_id, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", pack_id):
        raise ValueError("Invalid benchmark pack ID")
    preview = row.get("message_preview")
    if not isinstance(preview, str) or not preview.strip():
        raise ValueError("message_preview must be nonempty text")
    label = row.get("label")
    alternatives = row.get("alternatives")
    if not fixture:
        if row.get("decision") not in ("confirmed", "corrected") or alternatives is not None:
            raise ValueError("Real cases require a confirmed or corrected human label")
        reviewed_date = _review_date(row.get("reviewed_at"))
        rationale = ("Human-reviewed production message; label confirmed or corrected by the "
                     f"owner on {reviewed_date}.")
    else:
        reviewed_date = None
        rationale = FIXTURE_RATIONALE
    assertion = _assertion(label, alternatives)
    cards = load_cards()
    localized_options = options(language)
    prefix = "cif1" if fixture else "cir1"
    scenario = f"{prefix}-{index:04d}"
    identity = f"{scenario}-{language}"
    visible = {"context": cards["intro"][language].format(message=preview[:cards["max_state_chars"]]),
               "question": cards["question"][language], "options": localized_options}
    params = {field: deepcopy(row.get(field)) for field in REPORT_FIELDS}
    params.update(benchmark_pack=pack_id, decision=None if fixture else row["decision"],
                  reviewed_date=reviewed_date, label=label, alternatives=deepcopy(alternatives))
    case = {
        "schema_version": "deposium.case/v2", "case_id": identity,
        "scenario_id": scenario, "translation_family": scenario,
        "document_ids": [f"{'synthetic' if fixture else 'private'}:{pack_id}:{index:04d}"],
        "split": "calibration" if fixture else "test", "language": language,
        "pack": "RESEARCH", "contract_id": "bench.context-choice", "input": visible,
        "reference": {"assertions": [assertion], "abstention_allowed": False, "rationale": rationale},
        "evaluation": {"domain": "documentary", "difficulty": "D2", "base_case_id": identity,
                       "related_contract_ids": ["mcps.scope-dispatch"], "review": "agent_only",
                       "task_type": "routing.chat-intent.fixture" if fixture else "routing.chat-intent.real",
                       "oracle": {"kind": "human_reference", "base_input": deepcopy(visible),
                                  "choices": dict(zip(LETTERS, INTENTS)), "params": params}, "length": None}}
    validate_oracle(case)
    return case


def make_case(row, index, language, pack_id):
    """Build a private TEST case from a joined, confirmed/corrected review row.

    Required row fields: message_preview, label, decision, reviewed_at. Production
    and prelabel predictions are never used as a label fallback. reviewed_at is
    normalized to its recorded calendar date; no current clock is consulted.
    """
    return _build(row, index, language, pack_id, fixture=False)


def make_fixture_case(row, index, language, pack_id):
    """Build a synthetic CALIBRATION case; optional alternatives are intent IDs.

    Alternatives are the full accepted set, including label. They use one_of in
    the shared runtime. The frozen v2 JSON Schema only allows equals, so such
    alternative cases need a separately authorized schema amendment for schema
    validation; this module deliberately leaves that schema untouched.
    """
    return _build(row, index, language, pack_id, fixture=True)


def validate_oracle(case):
    """Check reference/input integrity, not semantic truth or review authenticity.

    The snapshot and explicit label are archival checks: coordinated rewriting
    of both an annotation and its oracle requires external archive/hash review.
    """
    try:
        evaluation = case["evaluation"]
        oracle = evaluation["oracle"]
        params = oracle["params"]
        identity = re.fullmatch(r"(cir1|cif1)-([0-9]{4,})-(fr|en)", case["case_id"])
        if identity is None:
            raise ValueError("Invalid chat-intent identity")
        prefix, index, language = identity.groups()
        if index != f"{int(index):04d}":
            raise ValueError("Noncanonical chat-intent index")
        fixture = prefix == "cif1"
        scenario = f"{prefix}-{index}"
        pack_id = params["benchmark_pack"]
        if not isinstance(pack_id, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", pack_id):
            raise ValueError("Invalid benchmark pack ID")
        expected_fields = {
            "schema_version": "deposium.case/v2", "scenario_id": scenario,
            "translation_family": scenario, "language": language,
            "document_ids": [f"{'synthetic' if fixture else 'private'}:{pack_id}:{index}"],
            "split": "calibration" if fixture else "test", "pack": "RESEARCH",
            "contract_id": "bench.context-choice"}
        if any(case[k] != v for k, v in expected_fields.items()):
            raise ValueError("Chat-intent family or split identity changed")
        expected_eval = {"domain": "documentary", "difficulty": "D2", "base_case_id": case["case_id"],
                         "related_contract_ids": ["mcps.scope-dispatch"], "review": "agent_only",
                         "task_type": "routing.chat-intent.fixture" if fixture else "routing.chat-intent.real",
                         "length": None}
        if (set(evaluation) != set(expected_eval) | {"oracle"}
                or any(evaluation[k] != v for k, v in expected_eval.items())
                or set(oracle) != {"kind", "base_input", "choices", "params"}
                or oracle["kind"] != "human_reference"
                or oracle["choices"] != dict(zip(LETTERS, INTENTS))
                or set(params) != set(REPORT_FIELDS) | {"benchmark_pack", "decision", "reviewed_date", "label", "alternatives"}):
            raise ValueError("Chat-intent oracle definition changed")
        visible = case["input"]
        cards = load_cards()
        if (set(visible) != {"context", "question", "options"}
                or visible != oracle["base_input"]
                or visible["options"] != options(language)
                or visible["question"] != cards["question"][language]):
            raise ValueError("Chat-intent input or option order changed")
        before, after = cards["intro"][language].split("{message}")
        context = visible["context"]
        if (not isinstance(context, str) or not context.startswith(before) or not context.endswith(after)
                or not context[len(before):-len(after)].strip()
                or len(context[len(before):-len(after)]) > cards["max_state_chars"]):
            raise ValueError("Invalid bounded message preview")
        assertion = _assertion(params["label"], params["alternatives"])
        if fixture:
            if params["decision"] is not None or params["reviewed_date"] is not None:
                raise ValueError("A fixture must not claim human review")
            rationale = FIXTURE_RATIONALE
        else:
            if params["decision"] not in ("confirmed", "corrected") or params["alternatives"] is not None:
                raise ValueError("Invalid human review decision")
            reviewed_date = _review_date(params["reviewed_date"])
            if reviewed_date != params["reviewed_date"]:
                raise ValueError("Review date must be normalized")
            rationale = ("Human-reviewed production message; label confirmed or corrected by the "
                         f"owner on {reviewed_date}.")
        if case["reference"] != {"assertions": [assertion], "abstention_allowed": False, "rationale": rationale}:
            raise ValueError("Reference differs from its reviewed or authored label")
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        raise ValueError("Malformed chat-intent oracle") from error
