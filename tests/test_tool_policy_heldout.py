"""Frozen held-out tool-policy pack: invariants checked without any model or tool call."""
import hashlib
import json
from pathlib import Path
import unittest

from deposium_bench import local_tool_policy as local, tool_arguments as arguments, tool_episodes as episodes
from deposium_bench.cases import candidate_request, load_cases
from deposium_bench.synthetic_tools import artifact_id

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "datasets/tool-policy-heldout-v1"
CANARY = ROOT / "datasets/tool-policy-canary-v1"


class HeldOutPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = (PACK / "cases.jsonl").read_bytes()
        cls.cases = load_cases(PACK / "cases.jsonl")[0]
        cls.manifest = json.loads((PACK / "manifest.json").read_bytes())
        cls.by_id = {c["case_id"]: c for c in cls.cases}

    def test_manifest_binds_exact_bytes_and_inventory(self):
        m = self.manifest
        self.assertEqual(hashlib.sha256(self.payload).hexdigest(), m["cases_sha256"])
        self.assertEqual(len(self.cases), m["case_count"], 24)
        self.assertEqual(len({c["translation_family"] for c in self.cases}), m["family_count"], 12)
        self.assertEqual({c["split"] for c in self.cases}, {"test"})
        self.assertEqual(m["counts_by_split"], {"train": 0, "calibration": 0, "test": 24})
        for contract, count in m["counts_by_contract"].items():
            self.assertEqual(sum(c["contract_id"] == contract for c in self.cases), count)
        self.assertEqual(m["status"], "frozen_before_first_candidate_prediction")
        self.assertEqual(m["qualification_at_freeze"]["real_model_cases"], 0)
        self.assertEqual({f["family_id"] for f in m["families"]}, {c["scenario_id"] for c in self.cases})

    def test_every_identity_is_new_relative_to_the_train_canary(self):
        train = load_cases(CANARY / "cases.jsonl")[0]
        train_text = json.dumps([c["input"] for c in train], ensure_ascii=False)
        self.assertFalse({c["case_id"] for c in self.cases} & {c["case_id"] for c in train})
        self.assertFalse({c["scenario_id"] for c in self.cases} & {c["scenario_id"] for c in train})
        for c in self.cases:
            for doc in c["document_ids"]:
                self.assertNotIn(doc, train_text)
            inp = c["input"]
            for key in ("scope_id",):
                if key in inp:
                    self.assertNotIn(inp[key], train_text)
            if "dataset" in inp:
                self.assertNotIn(inp["dataset"]["dataset_id"], train_text)
            for card in inp.get("catalogue", []):
                self.assertNotIn(card["tool_id"], train_text)

    def test_translation_pairs_share_structure_and_reference(self):
        for family in self.manifest["families"]:
            fr, en = (self.by_id[i] for i in family["case_ids"])
            self.assertEqual((fr["language"], en["language"]), ("fr", "en"))
            self.assertEqual(fr["reference"], en["reference"])
            self.assertNotEqual(fr["input"]["request"], en["input"]["request"])
            a, b = dict(fr["input"]), dict(en["input"])
            a.pop("request"), b.pop("request")
            if "catalogue" in a:
                for x, y in zip(a.pop("catalogue"), b.pop("catalogue")):
                    self.assertNotEqual(x["description"], y["description"])
                    x, y = dict(x), dict(y)
                    x.pop("description"), y.pop("description")
                    self.assertEqual(x, y)
            self.assertEqual(a, b)

    def test_candidate_projections_exclude_identities_faults_and_references(self):
        """Check the task-specific projections the adapter actually sends, not the transport envelope."""
        for c in self.cases:
            task, contract = c["input"], c["contract_id"]
            if contract == "bench.tool-discovery":
                transport = candidate_request(c)
                self.assertEqual(set(transport), {"case_id", "contract_id", "input"})
                projections = [transport["input"]]
            elif contract == "bench.tool-arguments":
                projections = [arguments.candidate_input(task, arguments.expected_lookup(task))]
            else:
                projections = [episodes._State(task).projection(0.0, 0)]
                # Before any actual lookup, table values reach the policy only through observations.
                if task["dataset"]["values"]:
                    self.assertNotIn(json.dumps(task["dataset"]["values"]), json.dumps(projections[0]))
            for projection in projections:
                projected = json.dumps(projection, ensure_ascii=False)
                for forbidden in (c["case_id"], c["scenario_id"], c["translation_family"], *c["document_ids"],
                                  "rationale", "assertions", "\"test\"", "lookup_events", "disable_sum_after_lookup",
                                  "faults", "budgets\": {\"max_steps"):
                    self.assertNotIn(forbidden, projected, (c["case_id"], forbidden))

    def test_literal_totals_match_authored_values_and_fixture_oracles(self):
        for c in self.cases:
            inp, ref = c["input"], {a["path"]: a["value"] for a in c["reference"]["assertions"]}
            if c["contract_id"] == "bench.tool-arguments":
                self.assertEqual(ref["/execution/value"], sum(inp["dataset"]["values"]))
                self.assertEqual(ref["/execution/unit"], inp["dataset"]["unit"])
                self.assertTrue(artifact_id(inp).startswith("artifact:"))
            if c["contract_id"] == "bench.tool-episode":
                expected = episodes.expected_outcome(inp)
                self.assertEqual({k: ref["/outcome/" + k] for k in ("decision", "reason", "value", "unit")}, expected)
                self.assertEqual(ref["/checks/task_success"], expected["decision"] == "success")
                self.assertEqual(inp["schema_version"], "deposium.tool-episode-input/v2")
                self.assertEqual(inp["budgets"]["max_elapsed_ms"], 60000)
        literals = {"th105": 75, "th106": 32, "th107": 52, "th108": 42}
        for prefix, total in literals.items():
            ref = {a["path"]: a["value"] for a in self.by_id[prefix + "-en"]["reference"]["assertions"]}
            self.assertEqual(ref.get("/execution/value", ref.get("/outcome/value")), total)

    def test_episode_outcomes_cover_the_four_outcomes_absent_from_train(self):
        outcomes = {(a["value"] for a in c["reference"]["assertions"] if a["path"] == "/outcome/reason").__next__()
                    for c in self.cases if c["contract_id"] == "bench.tool-episode"}
        self.assertEqual(outcomes, {"complete", "persistent_error", "no_data", "partial_data", "unavailable"})
        successes = [c for c in self.cases if c["contract_id"] == "bench.tool-episode"
                     and any(a["path"] == "/checks/task_success" and a["value"] for a in c["reference"]["assertions"])]
        self.assertEqual(len(successes), 4)

    def test_discovery_alternatives_are_eligible_available_minimal_and_cover_three_decisions(self):
        decisions = set()
        for c in self.cases:
            if c["contract_id"] != "bench.tool-discovery":
                continue
            cards = {t["tool_id"]: t for t in c["input"]["catalogue"]}
            alternatives = c["reference"]["assertions"][0]["value"]
            sets = [frozenset(a["tool_ids"]) for a in alternatives]
            self.assertEqual(len(set(sets)), len(sets))
            for a in alternatives:
                decisions.add((a["decision"], a["reason"]))
                self.assertEqual(bool(a["tool_ids"]), a["decision"] == "select")
                for tool in a["tool_ids"]:
                    self.assertTrue(cards[tool]["eligible"] and cards[tool]["available"], tool)
                self.assertLessEqual(len(a["tool_ids"]), c["input"]["shortlist_limit"])
            for x in sets:
                for y in sets:
                    self.assertFalse(x < y, "superset alternative")
            self.assertTrue(any(not t["eligible"] or not t["available"] for t in cards.values()), c["case_id"])
        self.assertEqual(decisions, {("select", "ready"), ("clarify", "missing_information"), ("no_suitable", "unavailable")})

    def test_prompt_v2_names_no_pack_identity_and_v1_requests_still_rebuild(self):
        text = json.dumps([c["input"] for c in self.cases], ensure_ascii=False)
        v2 = local.PROMPTS["deposium.local-tool-policy-prompt/v2"]
        for token in ("ledger", "th1", "canary", "75", "52", "42", "32"):
            self.assertNotIn(token, v2)
        settings = {"model_id": "synthetic", "max_length": 4096, "max_output_tokens": 256, "seed": 1,
                    "prompt_version": "deposium.local-tool-policy-prompt/v1"}
        body = local.request_body("bench.tool-discovery", {"x": 1}, settings)
        self.assertEqual(body["messages"][0]["content"], local.PROMPTS["deposium.local-tool-policy-prompt/v1"])
        settings["prompt_version"] = local.PROMPT_VERSION
        self.assertEqual(local.request_body("bench.tool-discovery", {"x": 1}, settings)["messages"][0]["content"], v2)
        self.assertNotEqual(v2, local.PROMPTS["deposium.local-tool-policy-prompt/v1"])
        self.assertIn("shortlist", v2)
        del text


if __name__ == "__main__":
    unittest.main()
