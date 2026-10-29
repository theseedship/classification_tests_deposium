"""Versioned decision cases and reference isolation, using only the standard library."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from .registry import PACKS, load_registry

SCHEMA_VERSION = "deposium.case/v1"
RESEARCH_VERSION = "deposium.case/v2"
RESEARCH_CONTRACT = "bench.context-choice"
DEFAULT_DATASET = Path(__file__).resolve().parent.parent / "datasets" / "decisions-v1" / "cases.jsonl"


class CaseError(ValueError):
    """Malformed cases, references, or leaking partitions."""


def _object(value: Any, keys: set[str], where: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise CaseError(f"{where}: expected object with exactly {sorted(keys)}")


def _text(value: Any, where: str) -> None:
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise CaseError(f"{where}: expected non-empty text without control characters")


def _json(value: Any) -> None:
    if value is None or type(value) in (bool, int, str):
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, list):
        for item in value:
            _json(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _json(item)
        return
    raise CaseError("case: expected finite JSON values")


def typed_equal(left: Any, right: Any) -> bool:
    """JSON equality that does not conflate booleans with numbers."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(typed_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def pointer_tokens(pointer: Any) -> list[str]:
    """Parse RFC 6901 JSON pointers, rejecting malformed escape sequences."""
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise CaseError("assertion.path: expected JSON pointer")
    if re.search(r"~(?:[^01]|$)", pointer):
        raise CaseError("assertion.path: invalid JSON pointer escape")
    return [] if pointer == "" else [token.replace("~1", "/").replace("~0", "~")
                                      for token in pointer[1:].split("/")]


def _empty(value: Any) -> bool:
    """No decision content; false and zero are substantive JSON values."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, dict):
        return all(_empty(item) for item in value.values())
    if isinstance(value, list):
        return all(_empty(item) for item in value)
    return False


def _no_annotations(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {"gold", "expected", "expected_output", "reference", "reference_output",
                               "annotation", "annotations", "assertions", "rationale"}:
                raise CaseError("case.input: reference/annotation field is forbidden")
            _no_annotations(item)
    elif isinstance(value, list):
        for item in value:
            _no_annotations(item)


def validate_cases(cases: Any) -> list[dict]:
    """Validate identity, reference structure, and scenario/document split integrity."""
    if not isinstance(cases, list) or not cases:
        raise CaseError("cases: expected non-empty list")
    registry, _ = load_registry()
    contracts = {contract["id"]: component["packs"] for component in registry["components"]
                 for contract in component["contracts"]}
    # Benchmark-native task, deliberately separate from the application stack
    # inventory: a recorded plan fixture cannot qualify an application service.
    native_contracts = {"bench.tool-plan": ["PRODUCT"]}
    seen: set[str] = set()
    partitions: dict[tuple[str, str], str] = {}
    keys = {"schema_version", "case_id", "scenario_id", "translation_family", "document_ids",
            "split", "language", "pack", "contract_id", "input", "reference"}
    for case in cases:
        research = isinstance(case, dict) and case.get("schema_version") == RESEARCH_VERSION
        _object(case, keys | ({"evaluation"} if research else set()), "case")
        if case["schema_version"] not in {SCHEMA_VERSION, RESEARCH_VERSION}:
            raise CaseError("case: unsupported schema_version")
        for key in ("case_id", "scenario_id", "translation_family", "contract_id"):
            _text(case[key], f"case.{key}")
        if case["case_id"] in seen:
            raise CaseError("cases: duplicate case_id")
        seen.add(case["case_id"])
        for key, choices in (("split", {"train", "calibration", "test"}),
                             ("language", {"fr", "en", "de", "es", "it", "pt"} if research else {"fr", "en"}),
                             ("pack", {"RESEARCH"} if research else PACKS)):
            if not isinstance(case[key], str) or case[key] not in choices:
                raise CaseError(f"case.{key}: unknown value")
        if research:
            if case["contract_id"] != RESEARCH_CONTRACT:
                raise CaseError("research case: invalid isolated capability")
            _validate_evaluation(case, contracts)
        elif case["pack"] not in contracts.get(case["contract_id"],
                                               native_contracts.get(case["contract_id"], ())):
            raise CaseError("case.contract_id: unknown contract or incompatible pack")
        documents = case["document_ids"]
        if not isinstance(documents, list):
            raise CaseError("case.document_ids: expected list")
        for doc in documents:
            _text(doc, "case.document_ids")
        if len(documents) != len(set(documents)):
            raise CaseError("case.document_ids: duplicate IDs")
        groups = [("scenario", case["scenario_id"]), ("translation", case["translation_family"])]
        groups.extend(("document", doc) for doc in documents)
        for group in groups:
            if group in partitions and partitions[group] != case["split"]:
                raise CaseError(f"cases: cross-split {group[0]} leakage: {group[1]}")
            partitions[group] = case["split"]
        if not isinstance(case["input"], dict) or not case["input"]:
            raise CaseError("case.input: expected non-empty object")
        _json(case["input"])
        _no_annotations(case["input"])
        reference = case["reference"]
        _object(reference, {"assertions", "abstention_allowed", "rationale"}, "reference")
        if type(reference["abstention_allowed"]) is not bool:
            raise CaseError("reference.abstention_allowed: expected boolean")
        _text(reference["rationale"], "reference.rationale")
        assertions = reference["assertions"]
        if not isinstance(assertions, list) or not assertions:
            raise CaseError("reference.assertions: expected non-empty list")
        meaningful = False
        assertion_ids: set[tuple[str, str]] = set()
        for assertion in assertions:
            _object(assertion, {"path", "op", "value"}, "assertion")
            pointer_tokens(assertion["path"])
            if not isinstance(assertion["op"], str) or assertion["op"] not in {"equals", "one_of", "set_equals"}:
                raise CaseError("assertion.op: unknown operation")
            identity = assertion["path"], assertion["op"]
            if identity in assertion_ids:
                raise CaseError("reference: duplicate assertion")
            assertion_ids.add(identity)
            value = assertion["value"]
            _json(value)
            if assertion["op"] in {"one_of", "set_equals"}:
                if not isinstance(value, list) or (assertion["op"] == "one_of" and not value):
                    raise CaseError("assertion.value: expected alternatives or set list")
                if any(typed_equal(a, b) for i, a in enumerate(value) for b in value[i + 1:]):
                    raise CaseError("assertion.value: duplicate alternatives or set members")
            root_values = value if assertion["op"] == "one_of" else [value]
            if assertion["path"] == "" and any(_empty(item) for item in root_values):
                raise CaseError("reference: empty root expectation cannot certify a decision")
            meaningful |= any(not _empty(item) for item in root_values)
        if not meaningful:
            raise CaseError("reference: assertions contain no substantive expectation")
        if case["contract_id"] == "bench.tool-plan":
            from .tool_plan import validate_case
            validate_case(case)
        if research:
            from .research_corpus import validate_oracle
            validate_oracle(case)
            if case["evaluation"]["length"] is not None:
                from .lengths import validate_variant_input
                validate_variant_input(case)
    return cases


def _validate_evaluation(case: dict, contracts: dict) -> None:
    """Research annotations are archival metadata, never a model request."""
    from .choice_protocol import validate_choice_input
    metadata = case["evaluation"]
    _object(metadata, {"domain", "difficulty", "base_case_id", "related_contract_ids", "review",
                       "task_type", "oracle", "length"}, "evaluation")
    for field, choices in (("domain", {"documentary", "mathematics", "chemistry", "physics"}),
                           ("difficulty", {"D1", "D2", "D3"}), ("review", {"agent_only"})):
        if not isinstance(metadata[field], str) or metadata[field] not in choices:
            raise CaseError(f"evaluation.{field}: invalid value")
    for field in ("base_case_id", "task_type"):
        _text(metadata[field], f"evaluation.{field}")
    links = metadata["related_contract_ids"]
    if (not isinstance(links, list) or not links or any(not isinstance(link, str) or link not in contracts for link in links)
            or len(set(links)) != len(links)):
        raise CaseError("evaluation: links must name existing application contracts")
    if not isinstance(metadata["oracle"], dict) or not metadata["oracle"]:
        raise CaseError("evaluation: missing independent reference definition")
    validate_choice_input(case["input"])
    if metadata["length"] is not None:
        length = metadata["length"]
        _object(length, {"target_tokens", "actual_tokens", "content_tokens", "head_tokens", "padded_tokens",
                         "position", "order", "tokenizer_sha256", "tokenizer_revision", "base_input_sha256",
                         "generator_version", "within_target"}, "evaluation.length")
        for field in ("target_tokens", "actual_tokens", "content_tokens", "head_tokens", "padded_tokens"):
            if type(length[field]) is not int or not 1 <= length[field] <= 131072:
                raise CaseError("length: token counts must be bounded positive integers")
        if length["actual_tokens"] != length["content_tokens"] + length["head_tokens"]:
            raise CaseError("length: component counts do not sum to actual tokens")
        if length["padded_tokens"] != (length["actual_tokens"] + 7) // 8 * 8:
            raise CaseError("length: invalid reference padding count")
        for field in ("tokenizer_sha256", "base_input_sha256"):
            if not isinstance(length[field], str) or not re.fullmatch(r"[0-9a-f]{64}", length[field]):
                raise CaseError("length: invalid content hash")
        if (not isinstance(length["tokenizer_revision"], str)
                or not re.fullmatch(r"[0-9a-f]{40}", length["tokenizer_revision"])):
            raise CaseError("length: tokenizer revision must be pinned")
        if (not isinstance(length["position"], str) or length["position"] not in {"start", "middle", "end"}
                or not isinstance(length["order"], str) or length["order"] not in {"original", "reversed"}
                or length["generator_version"] != "deposium.length-generator/v1"
                or type(length["within_target"]) is not bool
                or length["within_target"] != (abs(length["actual_tokens"] - length["target_tokens"]) <= max(1, length["target_tokens"] * .05))):
            raise CaseError("length: invalid variant or target eligibility")


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise CaseError("cases: duplicate JSON key")
        value[key] = item
    return value


def parse_cases(payload: bytes) -> tuple[list[dict], str]:
    """Validate one captured JSONL snapshot and hash those exact bytes."""
    try:
        # JSONL records end at LF; U+2028/U+2029 are valid within JSON strings.
        lines = payload.decode("utf-8").split("\n")
        if lines[-1] == "":
            lines.pop()
        if any(not line.strip() for line in lines):
            raise CaseError("cases: blank JSONL record")
        cases = [json.loads(line, object_pairs_hook=_unique_keys) for line in lines]
    except CaseError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise CaseError("cases: cannot read valid UTF-8 JSONL") from exc
    return validate_cases(cases), hashlib.sha256(payload).hexdigest()


def load_cases(path: str | Path | None = None) -> tuple[list[dict], str]:
    """Load JSONL without tolerating blank records; hash the exact original bytes."""
    try:
        return parse_cases(Path(path or DEFAULT_DATASET).read_bytes())
    except OSError as exc:
        raise CaseError("cases: cannot read valid UTF-8 JSONL") from exc


def candidate_request(case: dict) -> dict:
    """Only identity, contract and candidate-visible data cross the adapter boundary."""
    validate_cases([case])
    return deepcopy({"case_id": case["case_id"], "contract_id": case["contract_id"],
                     "input": case["input"]})
