#!/usr/bin/env python3
"""Freeze a private, manually reviewed intent pack; never invoke a model.

Source previews and annotations must remain in ignored private storage. Family
grouping is a conservative lexical safeguard, not semantic duplicate proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deposium_bench.cases import validate_cases
from deposium_bench.chat_intent_v2_corpus import CARDS_SHA256, INTENTS, POLICY_ID, load_cards, make_case


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def jsonl(rows):
    return b"".join((json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode() for row in rows)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_jsonl(data):
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def normalized(text):
    text = "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))
    return " ".join(re.findall(r"[^\W_]+", text))


def assign_groups(rows, config):
    """Union exact/near lexical variants and configured calibration anchors.

    Neither labels nor recorded predictions determine similarity. A known pilot
    member sends its entire connected component to calibration. A seeded hash
    assigns every other whole component before any candidate is run.
    """
    seed = config["seed"]
    fraction = config["calibration_fraction"]
    if not isinstance(seed, str) or not seed or not 0 < fraction < 1:
        raise ValueError("INVALID_SPLIT_CONFIGURATION")
    threshold = config["character_similarity_threshold"]
    token_threshold = config["token_jaccard_threshold"]
    if not .8 <= threshold <= 1 or not .5 <= token_threshold <= 1:
        raise ValueError("INVALID_GROUP_THRESHOLDS")
    ids = [r["exact_preview_group_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("DUPLICATE_GROUP_ID")
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        a, b = find(i), find(j)
        parent[max(a, b)] = min(a, b)

    # Group exact candidate-visible collisions before full-preview heuristics.
    # Different suffixes beyond the frozen input bound never reach a candidate.
    bound = load_cards()["max_state_chars"]
    visible_members = {}
    for i, row in enumerate(rows):
        visible = row["message_preview"][:bound]
        if visible in visible_members:
            union(i, visible_members[visible])
        else:
            visible_members[visible] = i
    texts = [normalized(r["message_preview"]) for r in rows]
    tokens = [set(t.split()) for t in texts]
    for i in range(len(rows)):
        for j in range(i):
            if texts[i] == texts[j]:
                union(i, j)
            elif min(len(texts[i]), len(texts[j])) >= 30:
                a, b = tokens[i], tokens[j]
                jaccard = len(a & b) / len(a | b) if a | b else 0
                if jaccard >= token_threshold and SequenceMatcher(None, texts[i], texts[j], autojunk=False).ratio() >= threshold:
                    union(i, j)
    anchored = set()
    for pattern in config.get("calibration_anchor_patterns", []):
        compiled = re.compile(pattern, re.IGNORECASE)
        matches = [i for i, row in enumerate(rows) if compiled.search(row["message_preview"])]
        for i in matches:
            anchored.add(i)
            union(matches[0], i)
    members = {}
    for i in range(len(rows)):
        members.setdefault(find(i), []).append(i)
    assignments = {}
    for indices in members.values():
        group = digest("\n".join(sorted(ids[i] for i in indices)).encode())
        forced = any(i in anchored or rows[i].get("in_reviewed_local_pilot") or rows[i].get("used_in_rubric_discussion") for i in indices)
        sampled = int(digest((seed + ":" + group).encode()), 16) / 2**256 < fraction
        split = "calibration" if forced or sampled else "test"
        for i in indices:
            assignments[ids[i]] = {"split_group_id": group, "split": split,
                                   "reason": "prior_exposure_or_anchor" if forced else "seeded_group_hash",
                                   "group_size": len(indices)}
    return assignments


def build(source_bytes, config):
    review = read_jsonl(source_bytes["curated.complete.jsonl"])
    receipt = json.loads(source_bytes["curation-complete-manifest.json"])
    if digest(source_bytes["curated.complete.jsonl"]) != receipt["output_sha256"]:
        raise ValueError("REVIEW_RECEIPT_HASH_MISMATCH")
    queue = read_jsonl(source_bytes["curation-queue.jsonl"])
    if len(review) != len(queue):
        raise ValueError("INCOMPLETE_HUMAN_REVIEW")
    if len({r["exact_preview_group_id"] for r in review}) != len(review):
        raise ValueError("DUPLICATE_REVIEW_ID")
    reviewed = {r["exact_preview_group_id"]: r for r in review}
    sources = {}
    for environment in ("local", "production", "staging"):
        for row in read_jsonl(source_bytes[environment + ".candidates.jsonl"]):
            identity = row["source_record_id"]
            if identity in sources or row["source_environment"] != environment or row["history_included"] is not False:
                raise ValueError("INVALID_SOURCE_RECORD")
            sources[identity] = row
    guide_hash = digest(source_bytes["grille-annotation-v2.html"])
    if guide_hash != receipt["policy_sha256"]:
        raise ValueError("ANNOTATION_GUIDE_CHANGED")
    assignments = assign_groups(queue, config)
    cases, recordings, exclusions, index = [], [], [], []
    mapping = dict(zip(INTENTS, "abcdefghij"))
    for ordinal, item in enumerate(queue, 1):
        group_id = item["exact_preview_group_id"]
        ref = reviewed[group_id]
        source = sources[item["representative_source_record_id"]]
        raw = source["raw"]
        if (ref["representative_source_record_id"] != source["source_record_id"]
                or ref["policy_sha256"] != guide_hash
                or ref["policy_version"] != "rubric-v2-draft"
                or ref["input_scope"] != "message_preview_only"
                or ref["human_review_method"] != "manual_no_prelabels"
                or raw["message_preview"] != item["message_preview"]):
            raise ValueError("REFERENCE_PROVENANCE_MISMATCH")
        assignment = assignments[group_id]
        if ref["decision"] == "ambiguous":
            if ref["label"] is not None or not ref["ambiguity_reason"]:
                raise ValueError("INVALID_AMBIGUOUS_REFERENCE")
            exclusions.append({**ref, **assignment, "reason": "ambiguous_reference"})
            continue
        if ref["decision"] != "labeled" or ref["label"] not in mapping or ref["ambiguity_reason"] is not None:
            raise ValueError("INVALID_HUMAN_REFERENCE")
        remote_eligible = source["external_voter_source_eligible"] is True
        if remote_eligible != (raw["source"] == "owner"):
            raise ValueError("REMOTE_OWNER_SCOPE_MISMATCH")
        joined = {
            "message_preview": item["message_preview"], "label": ref["label"],
            "decision": "labeled", "reviewed_at": ref["reviewed_at"],
            **{k: raw.get(k) for k in ("source", "tier_used", "method", "day", "terminal_state", "retrieval_outcome")},
            "version_period": "unverified_deployment_period", "source_environment": source["source_environment"],
            "source_record_id": source["source_record_id"], "external_voter_eligible": remote_eligible,
            "split_group_id": assignment["split_group_id"], "annotation_policy_id": ref["policy_version"],
            "annotation_policy_sha256": guide_hash,
        }
        case = make_case(joined, ordinal, "fr", config["pack_id"], assignment["split"])
        cases.append(case)
        if raw["production_intent"] not in mapping:
            raise ValueError("INVALID_RECORDED_INTENT")
        recordings.append({"case_id": case["case_id"], "status": "ok",
                           "output": {"choice_id": mapping[raw["production_intent"]]},
                           "raw_output": {k: raw.get(k) for k in ("production_intent", "method", "tier_used", "confidence")},
                           "error": None})
        index.append({"case_id": case["case_id"], "exact_preview_group_id": group_id,
                      **assignment, "source_environment": source["source_environment"],
                      "external_voter_eligible": remote_eligible, "label": ref["label"],
                      "message_language": "not_human_verified", "prompt_language": "fr"})
    cases.sort(key=lambda c: (c["split"] != "calibration", c["case_id"]))
    if not cases or cases[0]["split"] != "calibration" or not any(c["split"] == "test" for c in cases):
        raise ValueError("BOTH_SPLITS_AND_CALIBRATION_WARMUP_REQUIRED")
    validate_cases(cases)
    case_map = {c["case_id"]: c for c in cases}
    recordings.sort(key=lambda r: list(case_map).index(r["case_id"]))
    owner_cases = [c for c in cases if c["evaluation"]["oracle"]["params"]["external_voter_eligible"]]
    owner_ids = {c["case_id"] for c in owner_cases}
    profile = {"schema_version": "deposium.candidate/v1", "profile_id": config["pack_id"] + "-recorded",
               "adapter": "recorded", "qualification": "harness_control", "capabilities": ["bench.context-choice"],
               "model": None, "timeout_seconds": 15, "revision": None, "recordings": "recordings-production.jsonl"}
    files = {
        "cases.jsonl": jsonl(cases),
        "cases.test.jsonl": jsonl([c for c in cases if c["split"] == "test"]),
        "cases.calibration.jsonl": jsonl([c for c in cases if c["split"] == "calibration"]),
        "cases.owner.jsonl": jsonl(owner_cases),
        "cases.owner.test.jsonl": jsonl([c for c in owner_cases if c["split"] == "test"]),
        "recordings-production.jsonl": jsonl(recordings),
        "recordings-production.owner.jsonl": jsonl([r for r in recordings if r["case_id"] in owner_ids]),
        "profile-recorded-production.json": encoded(profile),
        "profile-recorded-production.owner.json": encoded({**profile, "profile_id": profile["profile_id"] + "-owner", "recordings": "recordings-production.owner.jsonl"}),
        "excluded.ambiguous.jsonl": jsonl(exclusions), "case-index.jsonl": jsonl(index),
        "reviewed.frozen-original.jsonl": source_bytes["curated.complete.jsonl"],
        "annotation-guide.original.html": source_bytes["grille-annotation-v2.html"],
        "split-assignments.jsonl": jsonl([{"exact_preview_group_id": r["exact_preview_group_id"], **assignments[r["exact_preview_group_id"]]} for r in queue]),
    }
    from deposium_bench.chat_intent_v2_corpus import CARDS_PATH
    files["intent-choice-cards.frozen.json"] = CARDS_PATH.read_bytes()
    counts = {split: {"cases": sum(c["split"] == split for c in cases),
                      "labels": dict(Counter(c["evaluation"]["oracle"]["params"]["label"] for c in cases if c["split"] == split)),
                      "source_environments": dict(Counter(c["evaluation"]["oracle"]["params"]["source_environment"] for c in cases if c["split"] == split))}
              for split in ("calibration", "test")}
    protocol = {
        "schema_version": "deposium.intent-frozen-protocol/v2", "policy_id": POLICY_ID,
        "cards_sha256": CARDS_SHA256, "annotation_policy_id": "rubric-v2-draft", "annotation_policy_sha256": guide_hash,
        "adoption": "Existing manual references adopted unchanged under the frozen criteria; no labels changed by the builder.",
        "configuration": config, "input_scope": "message_preview_only", "prompt_language": "fr",
        "primary_split": "test", "secondary_split": "calibration",
        "warmup": "Full campaign dataset starts with a calibration case; native warmup never uses a test case.",
        "split_timing": "Retrospective after human annotation, before candidate model execution; not a prospective preregistered sample.",
        "similarity_limit": "Lexical heuristics and prior-topic quarantine; semantic paraphrase separation is not exhaustively verified.",
        "remote_scope": "owner representatives only; beta records are local-only",
        "connector_search": "No positive references; recall N/A, false positive predictions counted.",
        "message_language_gate": "Not assessable until message languages are verified; case.language is prompt language.",
        "gate": {"accuracy_at_least_recorded": True, "maximum_verified_language_regression_pp": 5,
                 "gpu_p95_ms_below": 500, "same_test_ids_required": True, "unverified_gates_prevent_go": True},
        "baseline_timing": "Recorded adapter replay latency is not production router latency; never compare those timings.",
        "fixed_option_order": True, "source_frequency_weighted": False,
    }
    files["protocol.frozen.json"] = encoded(protocol)
    manifest = {"schema_version": "deposium.intent-private-pack/v2", "pack_id": config["pack_id"],
                "policy_id": POLICY_ID, "cards_sha256": CARDS_SHA256,
                "source_sha256": {name: digest(data) for name, data in source_bytes.items()},
                "reviewed": len(review), "scored": len(cases), "excluded_ambiguous": len(exclusions),
                "ambiguity_reasons": dict(Counter(r["ambiguity_reason"] for r in exclusions)),
                "split_counts": counts, "owner_cases": len(owner_cases), "owner_test_cases": sum(c["split"] == "test" for c in owner_cases),
                "distinct_split_groups": len({a["split_group_id"] for a in assignments.values()}),
                "forced_calibration_cases": sum(a["reason"] == "prior_exposure_or_anchor" for a in assignments.values()),
                "model_calls": 0, "files": {name: digest(data) for name, data in files.items()}}
    files["manifest.json"] = encoded(manifest)
    files["README.md"] = ("# Private frozen chat-intent v2\n\n"
        "Human-reviewed previews only; no conversation history. Original annotations preserved.\n"
        "Run candidates on cases.jsonl (calibration first); report test separately.\n"
        "Remote candidates may receive cases.owner.jsonl only.\n"
        "The archived recorded baseline is a historical descriptive replay, not current application execution.\n"
        "No model execution or GPU qualification is established by pack generation.\n"
        "See protocol.frozen.json and manifest.json for hashes, limits, grouping and counts.\n").encode()
    return files, manifest


SOURCE_NAMES = ("curated.complete.jsonl", "curation-complete-manifest.json", "curation-queue.jsonl",
                "local.candidates.jsonl", "production.candidates.jsonl", "staging.candidates.jsonl", "grille-annotation-v2.html")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = args.source_root.resolve(strict=True)
    target = args.output.resolve()
    # git -C of the destination's repository supports an external private data checkout.
    owner = target.parent
    while not (owner / ".git").exists() and owner != owner.parent:
        owner = owner.parent
    for file in [source / name for name in SOURCE_NAMES]:
        if subprocess.run(["git", "-C", str(owner), "check-ignore", "-q", str(file)], capture_output=True).returncode != 0:
            raise ValueError("SOURCE_AND_OUTPUT_MUST_BE_GIT_IGNORED")
    source_bytes = {name: (source / name).read_bytes() for name in SOURCE_NAMES}
    files, manifest = build(source_bytes, json.loads(args.config.read_bytes()))
    # Check every payload, including files added after the manifest is formed,
    # before creating the destination or reading it in verification mode.
    for name in files:
        file = target / name
        if subprocess.run(["git", "-C", str(owner), "check-ignore", "-q", str(file)], capture_output=True).returncode != 0:
            raise ValueError("SOURCE_AND_OUTPUT_MUST_BE_GIT_IGNORED")
    if args.check:
        if any((target / name).read_bytes() != data for name, data in files.items()):
            raise ValueError("FROZEN_PACK_CHANGED")
    else:
        target.mkdir(mode=0o700)
        for name, data in files.items():
            with (target / name).open("xb") as stream:
                stream.write(data)
            (target / name).chmod(0o600)
    print(json.dumps({"mode": "verified" if args.check else "frozen", "reviewed": manifest["reviewed"],
                      "scored": manifest["scored"], "ambiguous": manifest["excluded_ambiguous"],
                      "splits": manifest["split_counts"], "owner_test_cases": manifest["owner_test_cases"], "model_calls": 0}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("PRIVATE_INTENT_V2_BUILD_FAILED", file=sys.stderr)
        raise SystemExit(2)
