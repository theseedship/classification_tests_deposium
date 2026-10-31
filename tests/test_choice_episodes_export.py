import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/choice-episodes-20261031"


class ChoiceEpisodesPublicAggregateTests(unittest.TestCase):
    def setUp(self):
        self.main = json.loads((EVIDENCE / "analysis.json").read_text())
        self.first = json.loads((EVIDENCE / "d3-mini-attempt-001.json").read_text())
        self.manifest = json.loads((ROOT / "datasets/tool-episodes-choice-v1/manifest.json").read_text())

    def test_aggregates_bind_the_frozen_pack_and_tracked_profiles(self):
        for document in (self.main, self.first):
            self.assertEqual(document["dataset_sha256"], self.manifest["cases_sha256"])
            self.assertEqual(document["reference_review"], "agent_only_pending_human")
            for run in document["runs"]:
                self.assertTrue((ROOT / run["identity"]["profile"]).is_file())
                self.assertTrue((ROOT / run["identity"]["inner_profile"]).is_file())
        self.assertEqual([r["label"] for r in self.main["runs"]], ["D3liteMacos", "Vela03Macos", "D3nanoMacos", "D3miniMacos"])

    def test_counts_are_consistent_and_failures_stay_in_denominators(self):
        for run in self.main["runs"] + self.first["runs"]:
            c = run["counts"]
            self.assertEqual(sum(c["all"]["statuses"].values()), 32)
            self.assertEqual(c["train"]["total_cases"] + c["test"]["total_cases"], 32)
            self.assertEqual(c["fr"]["total_cases"] + c["en"]["total_cases"], 32)
            for key in ("procedure_correct_cases", "task_success_cases"):
                self.assertEqual(c["train"][key] + c["test"][key], c["all"][key])
                self.assertEqual(c["fr"][key] + c["en"][key], c["all"][key])
            self.assertEqual(c["all"]["task_success_eligible_cases"], 12)
            self.assertEqual(sum(m["cases"] for m in run["expected_to_final_reason"]), 32)
            self.assertEqual(sum(run["chosen_position"].values()),
                             sum(v for s, v in run["execution"]["inner_call_statuses"].items() if s == "ok"))
            self.assertLessEqual(run["execution"]["tool_calls_executed"], run["execution"]["tool_call_attempts"])

    def test_main_runs_completed_cleanly_and_attempt_001_records_the_operator_interruption(self):
        for run in self.main["runs"]:
            self.assertEqual(run["counts"]["all"]["statuses"], {"ok": 32}, run["label"])
        statuses = self.first["runs"][0]["counts"]["all"]["statuses"]
        self.assertEqual(statuses, {"error": 16, "ok": 16})

    def test_public_files_contain_no_local_paths_menus_or_raw_responses(self):
        for path in EVIDENCE.iterdir():
            text = path.read_text()
            for forbidden in ("/Users/", "/private/", "/tmp/", "/home/", "choice_input", "raw_output", "\"menu\""):
                self.assertNotIn(forbidden, text, (path.name, forbidden))


if __name__ == "__main__":
    unittest.main()
