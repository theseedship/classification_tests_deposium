"""Synthetic capability/plan choices using the existing shared choice engine.

No I/O occurs on import. References are authored judgments, not computed proof
of real tool behavior. Fixed observation cases do not execute an agent loop.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "datasets/capability-choice-v1"
DATASET_ID = "capability-choice-v1"
PREFIX = "ccv1-"
SPEC_FILES = ("specs-selection.json", "specs-arguments.json", "specs-observations.json")
SOURCE_FILES = ("catalogue.json", *SPEC_FILES)
LANGUAGES = ("fr", "en")
LETTERS = "abcd"
USE_CASES = {"geospatial", "open_data", "web", "local_rag", "cross_source"}


def _require(condition, reason):
    if not condition:
        raise ValueError("Capability corpus: " + reason)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _bilingual(value):
    return isinstance(value, dict) and set(value) == set(LANGUAGES) and all(_text(x) for x in value.values())


def _decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def source_bytes():
    """Read only this pack's named public source files, never a local overlay."""
    result = {}
    for name in SOURCE_FILES:
        path = DIRECTORY / name
        _require(path.is_file() and not path.is_symlink(), "missing or symlinked source: " + name)
        raw = path.read_bytes()
        _require(0 < len(raw) < 2 * 1024 * 1024, "invalid source size")
        result[name] = raw
    return result


def _sources(payloads=None):
    payloads = source_bytes() if payloads is None else payloads
    catalogue = _decode(payloads["catalogue.json"])
    _require(catalogue.get("schema_version") == "deposium.synthetic-capability-catalogue/v1", "catalogue version")
    cards = catalogue.get("tools")
    _require(isinstance(cards, list) and len(cards) == 32, "expected 32 synthetic capability cards")
    tools = {}
    for card in cards:
        _require(isinstance(card, dict) and set(card) == {"id", "plugin", "capability", "description"}, "card fields")
        identifier = card["id"]
        _require(_text(identifier) and re.fullmatch(r"[a-z]+\.[a-z]+", identifier)
                 and identifier not in tools and _text(card["plugin"]) and _text(card["capability"])
                 and _bilingual(card["description"]), "invalid capability card")
        tools[identifier] = card
    families = []
    for name in SPEC_FILES:
        spec = _decode(payloads[name])
        track = name.removeprefix("specs-").removesuffix(".json")
        _require(set(spec) == {"schema_version", "families"}
                 and spec["schema_version"] == "deposium.capability-specs/v1"
                 and isinstance(spec["families"], list) and len(spec["families"]) == 16, "specification contract")
        for index, family in enumerate(spec["families"]):
            _require(isinstance(family, dict) and set(family) == {
                "id", "task_type", "use_case", "difficulty", "tools", "context", "question", "choices", "answer", "rationale"
            }, "family fields")
            _require(family["id"] == f"{track}-{index + 1:02d}", "family ID/order")
            _require(_text(family["task_type"]) and re.fullmatch(r"[a-z][a-z0-9-]*", family["task_type"])
                     and family["use_case"] in USE_CASES and family["difficulty"] in {"D1", "D2", "D3"}, "family metadata")
            selected = family["tools"]
            _require(isinstance(selected, list) and len(selected) == len(set(selected)) == 8
                     and set(selected) <= set(tools), "compact catalogue must have eight known cards")
            _require(_bilingual(family["context"]) and _bilingual(family["question"])
                     and _text(family["rationale"]), "missing bilingual facts/question or rationale")
            choices = family["choices"]
            _require(isinstance(choices, list) and len(choices) == 4 and all(
                isinstance(x, dict) and set(x) == {"key", "fr", "en"} and all(_text(v) for v in x.values())
                for x in choices), "four bilingual proposal choices required")
            _require(len({x["key"] for x in choices}) == 4
                     and all(len({x[lang] for x in choices}) == 4 for lang in LANGUAGES)
                     and family["answer"] in {x["key"] for x in choices}, "invalid/duplicate choice reference")
            families.append((track, index, family))
    return tools, families, payloads


def _links(use_case):
    # Declared registry relationships only; no application harness is called.
    return {
        "geospatial": ["geoai.server", "geoai.patterns", "mcps.scope-dispatch"],
        "open_data": ["mcps.semantic-source-route", "web-acquisition.fetch"],
        "web": ["web-acquisition.fetch", "mcps.semantic-source-route"],
        "local_rag": ["mcps.document-plan", "mcps.search", "mcps.evidence-attribution"],
        "cross_source": ["mcps.semantic-source-route", "mcps.evidence-attribution", "web-acquisition.fetch"],
    }[use_case]


def _assemble(payloads=None):
    tools, families, _ = _sources(payloads)
    cases = []
    for track, index, family in families:
        scenario = PREFIX + family["id"]
        split = ("train", "calibration", "test", "test")[index % 4]
        # Balanced within each split as well as track/language/catalogue variant.
        position = (index // 4 + index % 4) % 4
        answer = next(x for x in family["choices"] if x["key"] == family["answer"])
        ordered = [x for x in family["choices"] if x["key"] != family["answer"]]
        ordered.insert(position, answer)
        for variant in ("compact", "expanded"):
            identifiers = family["tools"] if variant == "compact" else list(tools)
            identifiers = sorted(identifiers, key=lambda key: hashlib.sha256(f"{scenario}:{key}".encode()).digest())
            for lang in LANGUAGES:
                intro = {
                    "en": "Synthetic capability catalogue (descriptions, not active-service claims). Only listed tools may be proposed; explicit availability, scope, arguments and budgets below take precedence. Choose the minimal sufficient proposal satisfying the request; do not add unrelated operations.",
                    "fr": "Catalogue synthétique de capacités (descriptions, sans affirmation de service actif). Seuls les outils listés peuvent être proposés ; disponibilité, périmètre, arguments et budgets explicites ci-dessous priment. Choisir la proposition minimale suffisante répondant à la demande ; ne pas ajouter d'opérations sans rapport.",
                }[lang]
                catalogue = "\n".join(f"{key}: {tools[key]['description'][lang]}" for key in identifiers)
                context = intro + "\n" + catalogue + "\n\n" + family["context"][lang]
                visible = {"context": context, "question": family["question"][lang],
                           "options": [{"id": letter, "description": item[lang]}
                                       for letter, item in zip(LETTERS, ordered, strict=True)]}
                identity = f"{scenario}-{variant}-{lang}"
                semantics = {letter: item["key"] for letter, item in zip(LETTERS, ordered, strict=True)}
                cases.append({
                    "schema_version": "deposium.case/v2", "case_id": identity,
                    "scenario_id": scenario, "translation_family": scenario,
                    "document_ids": ["synthetic:" + scenario], "split": split, "language": lang,
                    "pack": "RESEARCH", "contract_id": "bench.context-choice", "input": visible,
                    "reference": {"assertions": [{"path": "/choice_id", "op": "equals", "value": LETTERS[position]}],
                                  "abstention_allowed": False,
                                  "rationale": family["rationale"] + " Authored synthetic reference; human review not performed."},
                    "evaluation": {"domain": "documentary", "difficulty": family["difficulty"],
                                   "base_case_id": identity, "related_contract_ids": _links(family["use_case"]),
                                   "review": "agent_only", "task_type": "capability." + track + "." + family["task_type"],
                                   "oracle": {"kind": "human_reference", "params": {
                                       "task": family["answer"], "benchmark_pack": DATASET_ID,
                                       "use_case": family["use_case"], "catalogue_variant": variant,
                                       "catalogue_size": len(identifiers), "track": track,
                                   }, "choices": semantics, "base_input": deepcopy(visible)}, "length": None},
                })
    return cases


@lru_cache(maxsize=2)
def _index_from_snapshot(snapshot):
    return {case["case_id"]: case for case in _assemble(dict(snapshot))}


def _base_index(payloads=None):
    payloads = source_bytes() if payloads is None else payloads
    return _index_from_snapshot(tuple((name, payloads[name]) for name in SOURCE_FILES))


def canonical_case(identity):
    """Resolve only a known frozen authored case; return no candidate prediction."""
    try:
        return deepcopy(_base_index()[identity])
    except KeyError as exc:
        raise ValueError("Unknown capability-choice reference") from exc


def build_cases(payloads=None):
    from .cases import validate_cases
    result = deepcopy(list(_base_index(payloads).values()))
    validate_cases(result)
    return result


def encoded_dataset():
    sources = source_bytes()
    cases = build_cases(sources)
    payload = b"".join((json.dumps(c, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
                       for c in cases)
    counts = lambda function: dict(sorted(Counter(map(function, cases)).items()))
    manifest = {
        "schema_version": "deposium.research-dataset/v1", "dataset_id": DATASET_ID,
        "version": "1.0.0-exploratory", "case_schema": "deposium.case/v2", "cases_file": "cases.jsonl",
        "cases_sha256": hashlib.sha256(payload).hexdigest(), "case_count": len(cases),
        "family_count": len({c["translation_family"] for c in cases}), "languages": list(LANGUAGES),
        "contract_id": "bench.context-choice", "review": "agent_only", "human_review": "not_performed",
        "evaluation_status": "not_run", "cases_scored": 0, "human_approved": 0,
        "reference_kind": "frozen agent-authored judgments; structural checks do not prove semantic truth",
        "generator_version": "deposium.capability-corpus/v1",
        "source_files_sha256": {name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        "counts_by_split": counts(lambda c: c["split"]),
        "counts_by_language": counts(lambda c: c["language"]),
        "counts_by_track": counts(lambda c: c["evaluation"]["oracle"]["params"]["track"]),
        "counts_by_use_case": counts(lambda c: c["evaluation"]["oracle"]["params"]["use_case"]),
        "counts_by_catalogue": counts(lambda c: c["evaluation"]["oracle"]["params"]["catalogue_variant"]),
        "counts_by_correct_position": counts(lambda c: c["reference"]["assertions"][0]["value"]),
        "split_policy": "Interleaved 4 train/4 calibration/8 test families per track; all languages and catalogue variants stay in one family split. Choice positions balanced within each split.",
        "limitations": [
            "48 authored scenario families, not 192 independent observations or production requests.",
            "Closed choice among four proposals; not free-form tool generation, open-set discovery recall, argument execution or validated routing accuracy.",
            "Eight-card and 32-card variants share facts/references; catalogue cards are synthetic descriptions, not installed/active MCP tools.",
            "Observation cases select a next step from a frozen snapshot; no closed-loop harness or live tool execution is delivered.",
            "D1/D2/D3 describe authored context strata, not measured model difficulty or an escalation oracle.",
            "No model inference, application harness, latency, service or product qualification has run for this pack.",
        ],
    }
    return payload, (json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(), manifest


def check_dataset():
    payload, manifest_bytes, manifest = encoded_dataset()
    for name, expected in (("cases.jsonl", payload), ("manifest.json", manifest_bytes)):
        path = DIRECTORY / name
        _require(path.is_file() and not path.is_symlink() and path.read_bytes() == expected,
                 "stale or missing frozen export: " + name)
    return manifest


def write_dataset(destination):
    """Initial export only; never overwrite an existing reference or archive."""
    destination = Path(destination)
    _require(not destination.is_symlink(), "symlink destination")
    _require(not any((destination / name).exists() or (destination / name).is_symlink()
                     for name in ("cases.jsonl", "manifest.json")), "refusing to overwrite frozen exports")
    payload, manifest_bytes, manifest = encoded_dataset()
    destination.mkdir(parents=True, exist_ok=True)
    for name, raw in (("cases.jsonl", payload), ("manifest.json", manifest_bytes)):
        with (destination / name).open("xb") as handle:
            handle.write(raw)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", metavar="NEW_DIRECTORY")
    args = parser.parse_args(argv)
    try:
        manifest = check_dataset() if args.check else write_dataset(args.write)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps({"status": "valid_frozen_corpus", "dataset_id": DATASET_ID,
                      "cases": manifest["case_count"], "families": manifest["family_count"],
                      "sha256": manifest["cases_sha256"], "evaluation_status": "not_run", "cases_scored": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
