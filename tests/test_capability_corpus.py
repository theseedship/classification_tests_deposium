"""Offline controls for frozen synthetic capability choices, not model results."""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import campaigns, capability_corpus as corpus
from deposium_bench.cases import candidate_request, validate_cases
from deposium_bench.choice_protocol import choice_row
from deposium_bench.context_analysis import analyze_context
from deposium_bench.research_corpus import build_cases as legacy_cases, validate_oracle
from deposium_bench.scoring import score_case, summarize

ROOT = Path(__file__).resolve().parents[1]
LEGACY_SHA256 = "767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616"


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode()


def snapshot(root):
    # Only called on newly created temporary test directories, never the workspace.
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class CapabilityCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = corpus.build_cases()
        cls.sources = corpus.source_bytes()

    def test_192_cases_48_families_and_declared_partitions(self):
        validate_cases(self.cases)
        self.assertEqual(len(self.cases), 192)
        self.assertEqual(len({c["case_id"] for c in self.cases}), 192)
        self.assertEqual(len({c["translation_family"] for c in self.cases}), 48)
        self.assertEqual(Counter(c["split"] for c in self.cases), {"train": 48, "calibration": 48, "test": 96})
        self.assertEqual(Counter(c["language"] for c in self.cases), {"fr": 96, "en": 96})
        self.assertEqual(Counter(c["evaluation"]["oracle"]["params"]["catalogue_variant"] for c in self.cases),
                         {"compact": 96, "expanded": 96})
        self.assertEqual(Counter(c["evaluation"]["oracle"]["params"]["track"] for c in self.cases),
                         {"selection": 64, "arguments": 64, "observations": 64})
        self.assertEqual({c["evaluation"]["oracle"]["params"]["use_case"] for c in self.cases},
                         {"geospatial", "open_data", "web", "local_rag", "cross_source"})

    def test_translations_catalogues_documents_and_scenarios_stay_in_family_split(self):
        families = defaultdict(list)
        for case in self.cases:
            families[case["translation_family"]].append(case)
        for family in families.values():
            self.assertEqual(len(family), 4)
            self.assertEqual({(c["language"], c["evaluation"]["oracle"]["params"]["catalogue_variant"])
                              for c in family}, {("fr", "compact"), ("en", "compact"),
                                                ("fr", "expanded"), ("en", "expanded")})
            self.assertEqual(len({c["split"] for c in family}), 1)
            self.assertEqual(len({c["scenario_id"] for c in family}), 1)
            self.assertEqual(len({tuple(c["document_ids"]) for c in family}), 1)
            self.assertEqual(len({json.dumps(c["evaluation"]["oracle"]["choices"], sort_keys=True) for c in family}), 1)
            self.assertEqual(len({json.dumps(c["reference"]["assertions"], sort_keys=True) for c in family}), 1)
            for lang in ("fr", "en"):
                compact, expanded = [c for c in family if c["language"] == lang]
                self.assertEqual(compact["input"]["question"], expanded["input"]["question"])
                self.assertEqual(compact["input"]["options"], expanded["input"]["options"])
                self.assertEqual(compact["input"]["context"].rsplit("\n\n", 1)[1],
                                 expanded["input"]["context"].rsplit("\n\n", 1)[1])

    def test_correct_positions_balanced_within_each_split_track_language_and_variant(self):
        groups = defaultdict(Counter)
        for case in self.cases:
            params = case["evaluation"]["oracle"]["params"]
            key = (case["split"], params["track"], case["language"], params["catalogue_variant"])
            groups[key][case["reference"]["assertions"][0]["value"]] += 1
        self.assertEqual(len(groups), 36)
        for (split, track, lang, variant), positions in groups.items():
            with self.subTest(split=split, track=track, language=lang, catalogue=variant):
                each = 2 if split == "test" else 1
                self.assertEqual(positions, {letter: each for letter in "abcd"})

    def test_visible_catalogues_have_8_or_32_cards_without_gold_or_metadata(self):
        all_cards = {t["id"] for t in json.loads(self.sources["catalogue.json"])["tools"]}
        for case in self.cases:
            request = candidate_request(case)
            row = choice_row(request["input"])
            self.assertEqual(set(row), {"state", "question", "options", "type"})
            self.assertEqual(row["options"], [o["description"] for o in case["input"]["options"]])
            self.assertEqual(row["state"], case["input"]["context"])
            self.assertEqual(row["question"], case["input"]["question"])
            rendered = json.dumps(row, ensure_ascii=False)
            for hidden in (case["case_id"], case["translation_family"], case["reference"]["rationale"]):
                self.assertNotIn(hidden, rendered)
            for field in ("reference", "evaluation", "oracle", "split", "choice_id"):
                self.assertNotIn(field, row)
            cards = set(re.findall(r"^([a-z]+\.[a-z]+):", row["state"], re.MULTILINE))
            params = case["evaluation"]["oracle"]["params"]
            self.assertEqual(len(cards), params["catalogue_size"])
            self.assertEqual(params["catalogue_size"], 8 if params["catalogue_variant"] == "compact" else 32)
            self.assertTrue(cards <= all_cards)
            if params["catalogue_variant"] == "expanded":
                self.assertEqual(cards, all_cards)

    def test_oracles_validate_all_cases_and_reject_wrong_empty_and_abstaining_outputs(self):
        for case in self.cases:
            validate_oracle(case)
            gold = case["reference"]["assertions"][0]["value"]
            correct = score_case(case, {"status": "ok", "output": {"choice_id": gold}})
            self.assertTrue(correct["scored"] and correct["passed"])
            wrong = next(letter for letter in "abcd" if letter != gold)
            for result in ({"status": "ok", "output": {"choice_id": wrong}},
                           {"status": "ok", "output": {}},
                           {"status": "ok", "output": None},
                           {"status": "abstain", "output": None}):
                self.assertFalse(score_case(case, result)["passed"])

    def test_case_input_gold_identity_and_annotation_tampering_is_rejected(self):
        original = self.cases[0]
        wrong = next(x for x in "abcd" if x != original["reference"]["assertions"][0]["value"])
        mutations = [
            lambda c: c["input"].update(context=c["input"]["context"] + " Altered fixture facts."),
            lambda c: c["input"]["options"][0].update(description="Different proposal"),
            lambda c: c["reference"]["assertions"][0].update(value=wrong),
            lambda c: c.update(split="test"),
            lambda c: c["evaluation"].update(difficulty="D3"),
            lambda c: c["evaluation"].update(task_type="capability.invented"),
            lambda c: c["evaluation"]["oracle"]["params"].update(use_case="web"),
            lambda c: c["evaluation"]["oracle"]["params"].update(catalogue_size=99),
            lambda c: c["evaluation"].update(base_case_id="ccv1-unknown-compact-fr"),
        ]
        for index, mutate in enumerate(mutations):
            changed = deepcopy(original)
            mutate(changed)
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                validate_oracle(changed)
        with self.assertRaises(ValueError):
            corpus.canonical_case("ccv1-unknown-compact-fr")

    def test_unknown_capabilities_duplicate_choices_and_bad_spec_metadata_are_rejected(self):
        mutations = [
            lambda s: s["families"][0]["tools"].__setitem__(0, "unknown.tool"),
            lambda s: s["families"][0].update(use_case="private_inventory"),
            lambda s: s["families"][0].update(difficulty="easy"),
            lambda s: s["families"][0].update(answer="unknown_choice"),
            lambda s: s["families"][0]["choices"][1].update(key=s["families"][0]["choices"][0]["key"]),
        ]
        for index, mutate in enumerate(mutations):
            payloads = dict(self.sources)
            spec = json.loads(payloads["specs-selection.json"])
            mutate(spec)
            payloads["specs-selection.json"] = encode(spec)
            with self.subTest(mutation=index), patch.object(corpus, "source_bytes", return_value=payloads), \
                    self.assertRaises(ValueError):
                corpus.build_cases()

    def test_cache_keys_source_bytes_and_defensive_copies_do_not_mix_revisions(self):
        old = deepcopy(self.cases[0])
        payloads = dict(self.sources)
        spec = json.loads(payloads["specs-selection.json"])
        spec["families"][0]["question"]["fr"] += " Dans cette fixture synthétique."
        payloads["specs-selection.json"] = encode(spec)
        old_legacy = legacy_cases()
        with patch.object(corpus, "source_bytes", return_value=payloads):
            changed = corpus.build_cases()[0]
            self.assertNotEqual(changed["input"]["question"], old["input"]["question"])
            self.assertEqual(corpus.canonical_case(old["case_id"]), changed)
            _, _, changed_manifest = corpus.encoded_dataset()
            changed_hash = changed_manifest["source_files_sha256"]["specs-selection.json"]
            self.assertEqual(changed_hash, hashlib.sha256(payloads["specs-selection.json"]).hexdigest())
            self.assertNotEqual(changed_hash, hashlib.sha256(self.sources["specs-selection.json"]).hexdigest())
            validate_oracle(changed)
            with self.assertRaises(ValueError):
                validate_oracle(old)
            self.assertEqual(legacy_cases(), old_legacy)
        self.assertEqual(corpus.canonical_case(old["case_id"]), old)
        validate_oracle(old)
        with self.assertRaises(ValueError):
            validate_oracle(changed)
        returned = corpus.canonical_case(old["case_id"])
        returned["input"]["question"] = "Mutated caller copy"
        self.assertEqual(corpus.canonical_case(old["case_id"]), old)

    def test_manifest_records_source_hashes_review_limits_and_no_campaign_claim(self):
        payload, manifest_bytes, manifest = corpus.encoded_dataset()
        self.assertEqual(json.loads(manifest_bytes), manifest)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), manifest["cases_sha256"])
        self.assertEqual([json.loads(line) for line in payload.splitlines()], self.cases)
        self.assertEqual(manifest["evaluation_status"], "not_run")
        self.assertEqual((manifest["cases_scored"], manifest["human_approved"]), (0, 0))
        self.assertEqual(manifest["human_review"], "not_performed")
        self.assertEqual(manifest["review"], "agent_only")
        self.assertEqual(set(manifest["source_files_sha256"]), set(corpus.SOURCE_FILES))
        for name, raw in self.sources.items():
            self.assertEqual(manifest["source_files_sha256"][name], hashlib.sha256(raw).hexdigest())
        self.assertTrue(any("no closed-loop harness" in line for line in manifest["limitations"]))

    def test_original_132_case_pack_is_unchanged_and_still_validates(self):
        path = ROOT / "datasets/context-choice-v1/cases.jsonl"
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), LEGACY_SHA256)
        self.assertEqual(len(legacy_cases()), 132)
        self.assertEqual([json.loads(line) for line in raw.splitlines()], legacy_cases())

    def test_frozen_pack_check_is_readonly_and_matches_published_exports(self):
        directory = ROOT / "datasets/capability-choice-v1"
        paths = [directory / name for name in (*corpus.SOURCE_FILES, "cases.jsonl", "manifest.json")]
        before = {p.name: p.read_bytes() for p in paths}
        result = corpus.check_dataset()
        self.assertEqual(result["case_count"], 192)
        self.assertEqual(before, {p.name: p.read_bytes() for p in paths})
        payload, manifest, _ = corpus.encoded_dataset()
        self.assertEqual(before["cases.jsonl"], payload)
        self.assertEqual(before["manifest.json"], manifest)

    def test_new_export_cannot_overwrite_and_checker_rejects_stale_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "fresh"
            corpus.write_dataset(destination)
            before = snapshot(destination)
            with self.assertRaises((ValueError, FileExistsError)):
                corpus.write_dataset(destination)
            self.assertEqual(snapshot(destination), before)
            for name, raw in self.sources.items():
                (destination / name).write_bytes(raw)
            with patch.object(corpus, "DIRECTORY", destination):
                corpus.check_dataset()
                for name in ("cases.jsonl", "manifest.json"):
                    path = destination / name
                    original = path.read_bytes()
                    path.write_bytes(original + b" ")
                    with self.subTest(file=name), self.assertRaises(ValueError):
                        corpus.check_dataset()
                    self.assertEqual(path.read_bytes(), original + b" ")
                    path.write_bytes(original)

    def test_zero_scored_and_execution_failures_never_establish_a_pass(self):
        cases = self.cases[:4]
        results = [{"case_id": c["case_id"], "status": status, "output": None}
                   for c, status in zip(cases, ("unsupported", "missing", "error", "timeout"))]
        report = summarize(cases, results)
        self.assertEqual(report["verdict"], "invalid")
        self.assertEqual(report["scored_cases"], 0)
        self.assertEqual(report["total_cases"], 4)
        for status in ("unsupported", "missing", "error", "timeout"):
            self.assertEqual(report["counts_by_status"][status], 1)
        missing = summarize(cases, [])
        self.assertEqual(missing["verdict"], "invalid")
        self.assertEqual(missing["counts_by_status"]["missing"], 4)


class CapabilityCampaignControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.root = Path(temp.name)
        all_cases = corpus.build_cases()
        cls.cases = [all_cases[i] for i in (0, 3, 64, 67, 128, 131, 4, 7)]
        dataset = cls.root / "cases.jsonl"
        dataset.write_bytes(b"".join(encode(c) for c in cls.cases))
        recordings = []
        statuses = ("ok", "ok", "ok", "abstain", "unsupported", "error", "timeout")
        for i, (case, status) in enumerate(zip(cls.cases, statuses)):
            gold = case["reference"]["assertions"][0]["value"]
            output = {"choice_id": gold} if i == 0 else (
                {"choice_id": next(x for x in "abcd" if x != gold)} if i == 1 else {} if i == 2 else None)
            recordings.append({"case_id": case["case_id"], "status": status, "output": output,
                               "raw_output": {"control": "recorded_synthetic_harness_only"},
                               "error": None if status in {"ok", "abstain"} else "synthetic_" + status})
        (cls.root / "responses.jsonl").write_bytes(b"".join(encode(r) for r in recordings))
        profile = json.loads((ROOT / "profiles/fixture-control.json").read_bytes())
        profile.update(profile_id="capability-recorded-control", capabilities=["bench.context-choice"],
                       recordings="responses.jsonl")
        profile_path = cls.root / "profile.json"
        profile_path.write_bytes(encode(profile))
        cls.archive = cls.root / "control"
        cls.summary = campaigns.run_campaign(dataset, profile_path, cls.archive, max_new_cases=7)
        cls.zero = campaigns.run_campaign(dataset, profile_path, cls.root / "zero", max_new_cases=0)

    def test_recorded_campaign_preserves_failures_and_qualifies_only_the_harness(self):
        metrics = self.summary["metrics"]
        self.assertEqual(self.summary["completion_status"], "incomplete")
        self.assertEqual((metrics["total_cases"], metrics["scored_cases"], metrics["passed_cases"]), (8, 4, 1))
        self.assertEqual(metrics["verdict"], "fail")
        self.assertEqual(metrics["counts_by_status"],
                         {"ok": 3, "abstain": 1, "unsupported": 1, "error": 1, "timeout": 1, "missing": 1})
        manifest = json.loads((self.archive / "manifest.json").read_bytes())
        self.assertEqual(manifest["proof_level"], "harness_control")
        self.assertEqual(manifest["qualification"], "harness_control")
        for name, raw in corpus.source_bytes().items():
            key = "datasets/capability-choice-v1/" + name
            self.assertEqual(manifest["scorer"]["files"][key], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.zero["metrics"]["verdict"], "invalid")
        self.assertEqual(self.zero["metrics"]["scored_cases"], 0)
        self.assertEqual(self.zero["metrics"]["counts_by_status"]["missing"], 8)

    def test_context_analysis_keeps_new_dimensions_and_never_reexecutes_or_edits_archive(self):
        before = snapshot(self.archive)
        with patch.object(campaigns, "create_adapter", side_effect=AssertionError("no inference during analysis")), \
                patch.object(campaigns, "build_preflight", side_effect=AssertionError("no application stack")):
            analysis = analyze_context(self.archive, self.root / "analysis")
        self.assertEqual(snapshot(self.archive), before)
        self.assertEqual(analysis["qualification"], "harness_control")
        self.assertEqual(analysis["counts"]["total_cases"], 8)
        self.assertEqual(analysis["counts"]["independent_families"], 4)
        self.assertEqual(analysis["counts"]["counts_by_status"], self.summary["metrics"]["counts_by_status"])
        self.assertEqual(set(analysis["groups"]["benchmark_pack"]), {"capability-choice-v1"})
        self.assertEqual(set(analysis["groups"]["catalogue_variant"]), {"compact", "expanded"})
        self.assertEqual(set(analysis["groups"]["task_type"]), {c["evaluation"]["task_type"] for c in self.cases})
        self.assertEqual(set(analysis["groups"]["use_case"]),
                         {c["evaluation"]["oracle"]["params"]["use_case"] for c in self.cases})
        for axis in ("benchmark_pack", "catalogue_variant", "task_type", "use_case"):
            self.assertEqual(sum(group["total_cases"] for group in analysis["groups"][axis].values()), 8)
        self.assertEqual(analysis["fallback_threshold"]["status"], "not_qualified")


if __name__ == "__main__":
    unittest.main()
