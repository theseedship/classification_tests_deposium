"""Publication controls for CPU-worker pack exports and the macOS memory probes; no model needed."""
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import mastra_observation as observation

ROOT = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


exporter = module("export_cpu_pack_campaign", "scripts/export-cpu-pack-campaign.py")


class CpuPackExportTests(unittest.TestCase):
    def seal(self, root, members):
        files = {}
        for name, raw in members.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            files[name] = hashlib.sha256(raw).hexdigest()
        (root / "seal.json").write_text(json.dumps({"schema_version": "deposium.archive-seal/v1", "files": files}))

    def test_seal_requires_exact_inventory_and_unchanged_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.seal(root, {"manifest.json": b"{}", "raw.jsonl": b"{}\n"})
            self.assertEqual(len(exporter.verify_seal(root)), 64)
            (root / "extra.txt").write_bytes(b"not sealed")
            with self.assertRaisesRegex(ValueError, "inventory"):
                exporter.verify_seal(root)
            (root / "extra.txt").unlink()
            (root / "raw.jsonl").write_bytes(b"changed\n")
            with self.assertRaisesRegex(ValueError, "sealed file changed"):
                exporter.verify_seal(root)
            (root / "seal.json").write_text(json.dumps({"schema_version": "other/v1", "files": {"manifest.json": "0" * 64}}))
            with self.assertRaisesRegex(ValueError, "seal schema"):
                exporter.verify_seal(root)

    def test_frozen_pack_identities_match_the_tracked_datasets(self):
        for pack, (relative, total, families, digest) in exporter.DATASETS.items():
            payload = (ROOT / relative).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), digest, pack)
            cases = [json.loads(line) for line in payload.decode().splitlines()]
            self.assertEqual(len(cases), total, pack)
            self.assertEqual(len({c["translation_family"] for c in cases}), families, pack)

    def test_export_refuses_a_profile_outside_the_tracked_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.seal(root / "archive", {"manifest.json": b"{}", "summary.json": b"{}", "cases.jsonl": b"", "raw.jsonl": b""})
            args = type("Args", (), {"archive": root / "archive", "profile": root / "profile.json", "pack": "physics",
                                     "private_analysis": root / "private", "platform": "macOS arm64",
                                     "protocol": "docs/D3_LITE_MACOS_CPU_PROTOCOL_20261030.md"})()
            (root / "profile.json").write_text("{}")
            with self.assertRaises((ValueError, KeyError)):
                exporter.export(args)


class MacosMemoryProbeTests(unittest.TestCase):
    def test_mastra_snapshot_delegates_to_the_native_estimate_off_linux(self):
        with patch.object(observation.platform, "system", return_value="Darwin"), \
                patch("deposium_bench.native_resources.memory_snapshot",
                      return_value={"MemAvailable_mib": 4321.0, "MemTotal_mib": 65536.0, "method": "macos_free_inactive_speculative_estimate"}):
            self.assertEqual(observation.memory_snapshot()["MemAvailable_mib"], 4321.0)
        with patch.object(observation.platform, "system", return_value="Darwin"), \
                patch("deposium_bench.native_resources.memory_snapshot", side_effect=OSError("vm_stat")):
            self.assertNotIn("MemAvailable_mib", observation.memory_snapshot())

    def test_linux_snapshot_still_reads_proc_meminfo(self):
        with patch.object(observation.platform, "system", return_value="Linux"), \
                patch.object(observation.Path, "read_text", return_value="MemTotal:  2048 kB\nMemAvailable:  1024 kB\n"):
            snapshot = observation.memory_snapshot()
        self.assertEqual((snapshot["MemTotal_mib"], snapshot["MemAvailable_mib"]), (2.0, 1.0))


if __name__ == "__main__":
    unittest.main()


class PublishedCpuPackTests(unittest.TestCase):
    EVIDENCE = ROOT / "docs/evidence/d3-lite-macos-20261030"

    def test_capability_and_physics_aggregates_keep_full_denominators_and_split_sums(self):
        expected = {"capability": (192, 168, {"train": 48, "calibration": 48, "test": 96}),
                    "physics": (48, 14, {"calibration": 12, "test": 36})}
        for pack, (total, passed, splits) in expected.items():
            data = json.loads((self.EVIDENCE / f"{pack}.json").read_text())
            self.assertEqual(data["schema_version"], "deposium.cpu-pack-campaign-public/v1")
            self.assertEqual(data["execution_scope"], "isolated_cpu_worker_no_application_gateway")
            phase = data["phases"][pack]
            counts = phase["counts"]
            self.assertEqual((counts["total_cases"], counts["scored_cases"], counts["passed_cases"]), (total, total, passed), pack)
            self.assertEqual({k: v["total_cases"] for k, v in counts["counts_by_split"].items()}, splits, pack)
            self.assertEqual(sum(counts["counts_by_status"].values()), total)
            self.assertEqual(counts["counts_by_status"]["ok"], total)
            for axis, groups in phase["groups"].items():
                self.assertEqual(sum(g["total_cases"] for g in groups.values()), total, (pack, axis))
                self.assertEqual(sum(g["passed_cases"] for g in groups.values()), passed, (pack, axis))
            self.assertEqual(phase["actual_backend"]["kind"], "cpu")
            self.assertIsNone(phase["resources"]["stop_reason"])
            self.assertLessEqual(phase["resources"]["rss_peak_mib"], data["runtime"]["max_rss_mb"])
            self.assertEqual(data["runtime"]["pins"]["torch"], "2.14.0")
            self.assertEqual(data["model"]["model_revision"], "a8d25a91ef75552803f7009d25b7bd435991abd9")

    def test_nano_partial_capability_distinguishes_attempted_from_cached_timeouts(self):
        data = json.loads((ROOT / "docs/evidence/d3-nano-macos-20261031/capability.json").read_text())
        phase = data["phases"]["capability"]
        self.assertEqual(phase["counts"]["counts_by_status"]["timeout"], 150)
        self.assertEqual(phase["attempts"], {**phase["attempts"], "attempted_cases": 43, "unsuccessful_attempted": 1,
                                             "cached_unattempted": 149, "fail_closed_after_first_failure": True,
                                             "first_failure_case_index": 42})
        second = json.loads((ROOT / "docs/evidence/d3-nano-macos-20261031/capability-002.json").read_text())["phases"]["capability"]
        self.assertEqual((second["counts"]["passed_cases"], second["counts"]["scored_cases"], second["counts"]["counts_by_status"]["timeout"]), (188, 192, 0))
        self.assertEqual((second["attempts"]["attempted_cases"], second["attempts"]["cached_unattempted"]), (192, 0))
        self.assertLessEqual(second["latency_ms"]["max"], 300000)
        complete = json.loads((ROOT / "docs/evidence/d3-nano-macos-20261031/physics.json").read_text())["phases"]["physics"]
        self.assertEqual((complete["attempts"]["cached_unattempted"], complete["attempts"]["fail_closed_after_first_failure"]), (0, False))

    def test_mini_complete_packs_under_calibrated_timeouts_with_no_restart(self):
        evidence = ROOT / "docs/evidence/d3-mini-macos-20261031"
        capability = json.loads((evidence / "capability.json").read_text())["phases"]["capability"]
        physics = json.loads((evidence / "physics.json").read_text())["phases"]["physics"]
        context = json.loads((evidence / "context.json").read_text())["phases"]["context"]
        self.assertEqual((capability["counts"]["passed_cases"], capability["counts"]["counts_by_split"]["test"]["passed_cases"]), (192, 96))
        self.assertEqual((physics["counts"]["passed_cases"], physics["counts"]["counts_by_split"]["test"]["passed_cases"]), (39, 32))
        self.assertEqual((context["counts"]["passed_cases"], context["counts"]["counts_by_split"]["test"]["passed_cases"]), (119, 60))
        for phase, limit in ((capability, 300000), (physics, 120000), (context, 120000)):
            self.assertEqual(phase["counts"]["counts_by_status"]["timeout"], 0)
            self.assertLessEqual(phase["latency_ms"]["max"], limit)
            self.assertEqual((phase["attempts"]["worker_restarts"], phase["attempts"]["worker_restart_events"], phase["attempts"]["cached_unattempted"]), (0, [], 0))

    def test_published_files_contain_no_local_paths_or_raw_output(self):
        for name in ("analysis.json", "capability.json", "physics.json", "report.md"):
            text = (self.EVIDENCE / name).read_text()
            for forbidden in ("/Users/", "/private/", "/tmp/", "raw_output", "pid"):
                self.assertNotIn(forbidden, text, (name, forbidden))


class ConsolidatedCpuLoaderTests(unittest.TestCase):
    def test_cpu_loader_refuses_pins_that_differ_from_the_referenced_lock(self):
        campaigns = module("consolidated_campaigns_for_cpu", "scripts/consolidated-campaigns.py")

        class Inputs:
            def read(self, relative):
                return (ROOT / relative).read_bytes()

            def load(self, relative):
                return json.loads(self.read(relative))

        def require(value, message):
            if not value:
                raise ValueError(message)
        loader = campaigns.Campaigns(Inputs(), require)
        path = "docs/evidence/d3-lite-macos-20261030/physics.json"
        data, identity = loader.cpu(path, "profiles/d3-lite-assets.json", "runtimes/d3-macos/runtime.lock",
                                    "profiles/d3-lite-macos-cpu.json")
        self.assertEqual(identity["runtime"]["pins"]["torch"], "2.14.0")
        lock = campaigns.Campaigns.lock_pins((ROOT / "runtimes/d3-macos/runtime.lock").read_text())
        self.assertEqual(lock["torch"], "2.14.0")
        with self.assertRaisesRegex(ValueError, "unpinned"):
            campaigns.Campaigns.lock_pins("torch>=2\n")
        good = json.loads((ROOT / path).read_text())
        for change in ({"torch": "0.0.0"}, {"python": "3.12.0"}, {"nonexistent": "1.0"}):
            broken = json.loads(json.dumps(good))
            broken["runtime"]["pins"].update(change)
            drifted = type("Inputs", (), {"read": lambda self, rel: (ROOT / rel).read_bytes(),
                                          "load": lambda self, rel: broken if rel == path else json.loads((ROOT / rel).read_bytes())})()
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "pins differ"):
                campaigns.Campaigns(drifted, require).cpu(path, "profiles/d3-lite-assets.json",
                                                          "runtimes/d3-macos/runtime.lock", "profiles/d3-lite-macos-cpu.json")


class Vela2RestartPolicyTests(unittest.TestCase):
    def test_vela2_timeout_schedules_a_bounded_restart_instead_of_failing_closed(self):
        from deposium_bench import vela2_adapter as vela2
        adapter = vela2.Vela2Adapter.__new__(vela2.Vela2Adapter)
        adapter._restarts, adapter._restart_pending, adapter._sequence, adapter._process = 0, False, 7, None
        adapter._failure, adapter._closed = None, False
        adapter.provenance = {"worker_restarts": [], "available": True}
        adapter._model = {"repo_id": vela2.REPO_ID}
        outcome = adapter._timeout_outcome()
        self.assertEqual((outcome["status"], outcome["error"], adapter._restart_pending), ("timeout", "vela2_inference_timeout", True))
        self.assertEqual(outcome["raw_output"]["cached_failure"], False)
        self.assertEqual(adapter.provenance["worker_restarts"], [{"after_sequence": 7, "restart": 1, "reason": "vela2_inference_timeout"}])
        adapter._restarts = vela2.MAX_WORKER_RESTARTS
        with patch.object(vela2.Vela2Adapter, "close"):
            closed = adapter._timeout_outcome()
        self.assertEqual((closed["status"], adapter._failure["error"], adapter.provenance["available"]),
                         ("timeout", "vela2_inference_timeout", False))


class Vela2MacosProbeTests(unittest.TestCase):
    def test_vela2_adapter_and_worker_use_platform_probes(self):
        from deposium_bench import vela2_adapter as vela2
        with patch.object(vela2.platform, "system", return_value="Darwin"), \
                patch("deposium_bench.native_resources.memory_snapshot",
                      return_value={"MemAvailable_mib": 999.5, "MemTotal_mib": 65536.0}):
            self.assertEqual(vela2.Vela2Adapter._host_available_mb(), 999.5)
        with patch.object(vela2.platform, "system", return_value="Darwin"), \
                patch("deposium_bench.native_resources.memory_snapshot", side_effect=OSError("vm_stat")):
            with self.assertRaisesRegex(OSError, "vela2_host_memory_unknown"):
                vela2.Vela2Adapter._host_available_mb()
        worker = module("vela2_worker_rss_test", "bridges/vela2-worker.py")
        usage = type("Usage", (), {"ru_maxrss": 3 * 1048576})()
        with patch.object(worker.resource, "getrusage", return_value=usage):
            with patch.object(worker.sys, "platform", "darwin"):
                self.assertEqual(worker._rss(), 3.0)
            with patch.object(worker.sys, "platform", "linux"):
                self.assertEqual(worker._rss(), 3072.0)
