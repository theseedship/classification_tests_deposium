"""Synthetic freeze, family separation and source-scope controls."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

from deposium_bench.cases import candidate_request, parse_cases

spec = importlib.util.spec_from_file_location("intent_v2_builder", Path(__file__).parents[1] / "scripts/build-chat-intent-v2-pack.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def configuration():
    return {"pack_id": "synthetic-intent-pack", "seed": "synthetic-seed",
            "calibration_fraction": .25, "character_similarity_threshold": .88,
            "token_jaccard_threshold": .70, "calibration_anchor_patterns": [r"\balpine\b"]}


def source_data():
    texts = ["Alpine request", "Second alpine request", "Hello world!", "Hello, world",
             "Synthetic cost request", "Weather tomorrow?", "Correct supplied text", "Unknown referent"]
    queue, reviews = [], []
    records = {environment: [] for environment in ("local", "production", "staging")}
    guide = b"<html><body>Synthetic policy</body></html>"
    guide_hash = builder.digest(guide)
    for i, text in enumerate(texts):
        environment = ("local", "production", "staging")[i % 3]
        source = "beta" if i == 4 else "owner"
        identity = environment + ":synthetic-" + str(i)
        group = builder.digest(text.encode())
        raw = {"source": source, "message_preview": text, "production_intent": "search_query",
               "method": "synthetic", "tier_used": "regex", "day": "2026-01-01",
               "terminal_state": "synthetic", "retrieval_outcome": None, "confidence": .7}
        records[environment].append({"source_record_id": identity, "source_environment": environment,
                                     "history_included": False, "external_voter_source_eligible": source == "owner", "raw": raw})
        queue.append({"exact_preview_group_id": group, "message_preview": text,
                      "representative_source_record_id": identity,
                      "in_reviewed_local_pilot": i == 0, "used_in_rubric_discussion": False})
        reviews.append({"schema_version": "deposium.intent-curation-review/v2-draft", "exact_preview_group_id": group,
                        "representative_source_record_id": identity, "decision": "ambiguous" if i == 7 else "labeled",
                        "label": None if i == 7 else "search_query", "ambiguity_reason": "missing_context" if i == 7 else None,
                        "topic": "", "policy_version": "rubric-v2-draft", "policy_sha256": guide_hash,
                        "input_scope": "message_preview_only", "reviewed_at": "2026-01-02T12:00:00Z",
                        "source_environments": [environment], "human_review_method": "manual_no_prelabels"})
    reviewed = builder.jsonl(reviews)
    return {"curated.complete.jsonl": reviewed,
            "curation-complete-manifest.json": builder.encoded({"output_sha256": builder.digest(reviewed), "policy_sha256": guide_hash}),
            "curation-queue.jsonl": builder.jsonl(queue), "grille-annotation-v2.html": guide,
            **{env + ".candidates.jsonl": builder.jsonl(rows) for env, rows in records.items()}}


class BuildIntentV2Tests(unittest.TestCase):
    def test_deterministic_freeze_and_valid_cases(self):
        first, manifest = builder.build(source_data(), configuration())
        second, _ = builder.build(source_data(), configuration())
        self.assertEqual(first, second)
        cases, _ = parse_cases(first["cases.jsonl"])
        self.assertEqual(len(cases), 7)
        self.assertEqual(cases[0]["split"], "calibration")
        self.assertEqual(manifest["excluded_ambiguous"], 1)
        self.assertEqual(manifest["model_calls"], 0)
        self.assertEqual(first["reviewed.frozen-original.jsonl"], source_data()["curated.complete.jsonl"])
        for name, digest in manifest["files"].items():
            self.assertEqual(builder.digest(first[name]), digest)

    def test_anchor_and_normalized_families_never_cross_splits(self):
        data = source_data()
        queue = builder.read_jsonl(data["curation-queue.jsonl"])
        groups = builder.assign_groups(queue, configuration())
        self.assertEqual(groups[queue[0]["exact_preview_group_id"]]["split_group_id"], groups[queue[1]["exact_preview_group_id"]]["split_group_id"])
        self.assertEqual(groups[queue[1]["exact_preview_group_id"]]["split"], "calibration")
        self.assertEqual(groups[queue[2]["exact_preview_group_id"]]["split_group_id"], groups[queue[3]["exact_preview_group_id"]]["split_group_id"])
        reversed_groups = builder.assign_groups(list(reversed(queue)), configuration())
        self.assertEqual(groups, reversed_groups)
        families = {}
        for assignment in groups.values():
            families.setdefault(assignment["split_group_id"], set()).add(assignment["split"])
        self.assertTrue(all(len(splits) == 1 for splits in families.values()))

    def test_transitive_near_variants_and_prior_pilot_quarantine(self):
        queue = [{"exact_preview_group_id": str(i), "message_preview": text,
                  "in_reviewed_local_pilot": i == 0} for i, text in enumerate([
                      "Compare the synthetic annual report with the synthetic monthly report.",
                      "Compare the synthetic annual report with the synthetic monthly reports."])]
        groups = builder.assign_groups(queue, configuration())
        self.assertEqual(len({r["split_group_id"] for r in groups.values()}), 1)
        self.assertTrue(all(r["split"] == "calibration" for r in groups.values()))

    def test_owner_only_subset_and_candidate_boundary(self):
        files, _ = builder.build(source_data(), configuration())
        owners, _ = parse_cases(files["cases.owner.jsonl"])
        self.assertEqual(len(owners), 6)
        self.assertTrue(all(c["evaluation"]["oracle"]["params"]["source"] == "owner" for c in owners))
        for case in owners:
            request = json.dumps(candidate_request(case))
            self.assertNotIn("source_record_id", request)
            self.assertNotIn("annotation_policy", request)
            self.assertNotIn("reviewed_at", request)
        exclusions = builder.read_jsonl(files["excluded.ambiguous.jsonl"])
        self.assertEqual(exclusions[0]["ambiguity_reason"], "missing_context")

    def test_reference_and_source_tampering_fail_closed(self):
        data = source_data()
        data["curated.complete.jsonl"] += b" "
        with self.assertRaisesRegex(ValueError, "RECEIPT"):
            builder.build(data, configuration())
        data = source_data()
        data["grille-annotation-v2.html"] += b" "
        with self.assertRaisesRegex(ValueError, "GUIDE"):
            builder.build(data, configuration())
        data = source_data()
        rows = builder.read_jsonl(data["production.candidates.jsonl"])
        rows[1]["external_voter_source_eligible"] = True
        data["production.candidates.jsonl"] = builder.jsonl(rows)
        with self.assertRaisesRegex(ValueError, "OWNER_SCOPE"):
            builder.build(data, configuration())


if __name__ == "__main__":
    unittest.main()
