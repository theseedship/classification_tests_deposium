"""Candidate-visible context choices, shared by inference and token preflight.

No tokenizer, model or file access occurs here. Option IDs identify answers;
only their descriptions enter the model row.
"""
from __future__ import annotations

CONTEXT_CHOICE_CONTRACT = "bench.context-choice"
CONTEXT_CHOICE_PROMPT = {
    "schema_version": "deposium.context-choice-prompt/v1",
    "input_protocol": "context_choice",
    "order": "as_supplied",
    "state_field": "context",
    "question_field": "question",
    "options_field": "options",
    "output_field": "choice_id",
}


class ChoiceProtocolError(ValueError):
    """Malformed candidate-visible context choice."""


def validate_choice_input(value) -> None:
    if not isinstance(value, dict) or set(value) != {"context", "question", "options"}:
        raise ChoiceProtocolError("Choice input requires exactly context, question and options.")
    if not isinstance(value["context"], str) or not isinstance(value["question"], str) or not value["question"].strip():
        raise ChoiceProtocolError("Choice context must be text and question must be nonblank text.")
    options = value["options"]
    if not isinstance(options, list) or not 2 <= len(options) <= 20:
        raise ChoiceProtocolError("Choice input requires between 2 and 20 options.")
    identifiers, descriptions = set(), set()
    for option in options:
        if (not isinstance(option, dict) or set(option) != {"id", "description"}
                or any(not isinstance(option[key], str) or not option[key].strip() for key in ("id", "description"))):
            raise ChoiceProtocolError("Choice options require nonblank id and description only.")
        if option["id"] in identifiers or option["description"] in descriptions:
            raise ChoiceProtocolError("Choice option IDs and descriptions must be unique.")
        identifiers.add(option["id"])
        descriptions.add(option["description"])


def choice_row(value) -> dict:
    validate_choice_input(value)
    return {"state": value["context"], "question": value["question"],
            "options": [option["description"] for option in value["options"]], "type": "choice"}


def ordered_choice_ids(value) -> list[str]:
    validate_choice_input(value)
    return [option["id"] for option in value["options"]]
