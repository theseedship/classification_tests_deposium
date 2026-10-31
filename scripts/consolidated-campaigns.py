"""Normalize named public campaign aggregates for presentation; never infer/rescore."""
from __future__ import annotations

import hashlib
import math
import re

EVIDENCE = "docs/evidence/"
CLEF = EVIDENCE + "clef-flash-20261029/analysis.json"
PHYSICS = EVIDENCE + "physics-flash-20261029/analysis.json"
PASSAGE_D3 = EVIDENCE + "passage-flash-20261029/analysis.json"
PASSAGE_CLEF = EVIDENCE + "passage-clef-flash-20261029/analysis.json"
PASSAGE_CPU = EVIDENCE + "passage-cpu-20261015/analysis.json"
PASSAGE_JEV = EVIDENCE + "passage-jev-20261015/analysis.json"
D3LITE_MACOS_CAPABILITY = EVIDENCE + "d3-lite-macos-20261030/capability.json"
D3LITE_MACOS_PHYSICS = EVIDENCE + "d3-lite-macos-20261030/physics.json"
D3LITE_MACOS_REPORT = "D3_LITE_MACOS_RESULTS_20261030.md"
VELA03_MACOS_CAPABILITY = EVIDENCE + "vela2-03-macos-20261030/capability.json"
VELA03_MACOS_PHYSICS = EVIDENCE + "vela2-03-macos-20261030/physics.json"
VELA03_MACOS_REPORT = "VELA2_03_MACOS_RESULTS_20261030.md"
D3NANO_MACOS_CAPABILITY = EVIDENCE + "d3-nano-macos-20261031/capability.json"
D3NANO_MACOS_PHYSICS = EVIDENCE + "d3-nano-macos-20261031/physics.json"
D3NANO_MACOS_REPORT = "D3_NANO_MACOS_RESULTS_20261031.md"
NEW_CONTEXT_IDS = {"ClefFlashQ8", "D3FlashQ8Upstream"}
STATUSES = {"ok", "missing", "unsupported", "error", "timeout", "abstain"}
DATASETS = {
    "context": "767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616",
    "capability": "0b409a09bb5358b5c8d7574cbd330799511851a2acd90676e2f092f3d3c75eb0",
    "physics": "e21cd2e0f4e35465b56158ba1fa07c8d8203be81a969c6edf4b7630d2f0d7307",
    "passage": "35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476",
}


class Campaigns:
    def __init__(self, inputs, require):
        self.inputs, self.require = inputs, require

    def hash(self, value):
        self.require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "campaign: invalid hash")
        return value

    def counts(self, correct, scored, total, statuses, families=None):
        self.require(type(total) is int and total > 0, "campaign: zero denominator")
        self.require(all(type(n) is int and 0 <= n <= total for n in (correct, scored))
                     and correct <= scored, "campaign: invalid counts")
        self.require(set(statuses) == STATUSES and all(type(n) is int and n >= 0 for n in statuses.values())
                     and sum(statuses.values()) == total and scored == statuses["ok"] + statuses["abstain"],
                     "campaign: inconsistent statuses")
        if families is not None:
            self.require(type(families) is int and 0 < families <= total, "campaign: invalid families")
        return {"correct": correct, "scored": scored, "total": total,
                "statuses": dict(statuses), "families": families}

    def native_counts(self, value):
        c = self.counts(value["passed_cases"], value["scored_cases"], value["total_cases"],
                        value["counts_by_status"], value["independent_families"])
        splits = value["counts_by_split"]
        self.require(bool(splits) and set(splits) <= {"train", "calibration", "test"}, "campaign: invalid splits")
        c["by_split"] = {}
        for name, group in splits.items():
            numbers = [group[k] for k in ("passed_cases", "scored_cases", "total_cases")]
            self.require(all(type(n) is int for n in numbers) and 0 <= numbers[0] <= numbers[1] <= numbers[2],
                         "campaign: invalid split counts")
            c["by_split"][name] = dict(zip(("correct", "scored", "total"), numbers))
        self.require(all(sum(g[k] for g in c["by_split"].values()) == c[k]
                         for k in ("correct", "scored", "total")), "campaign: inconsistent split sums")
        return c

    def partition(self, parent, groups):
        self.require(bool(groups) and all(sum(g[k] for g in groups.values()) == parent[k]
                     for k in ("correct", "scored", "total")), "campaign: inconsistent group sums")
        self.require(all(sum(g["statuses"][s] for g in groups.values()) == parent["statuses"][s]
                         for s in STATUSES), "campaign: inconsistent group statuses")

    def stats(self, value, maximum):
        self.require(type(value["count"]) is int and 0 <= value["count"] <= maximum,
                     "campaign: invalid timing coverage")
        fields = [value[k] for k in ("min", "median", "p95", "max")]
        self.require(all((v is None if not value["count"] else
                         type(v) in (int, float) and math.isfinite(v) and v >= 0) for v in fields),
                     "campaign: invalid timing value")
        if value["count"]:
            self.require(fields[0] <= fields[1] <= fields[3] and fields[0] <= fields[2] <= fields[3],
                         "campaign: inconsistent timing range")
        return {k: value[k] for k in ("count", "min", "median", "p95", "max")}

    def native(self, path, schema, asset_path):
        data = self.inputs.load(path)
        self.require(data["schema_version"] == schema and data["reference_review"] == "agent_only_pending_human"
                     and data["execution_scope"] == "isolated_direct_upstream_llama_cpp_no_application_gateway",
                     "campaign: changed qualification")
        asset = self.inputs.load(asset_path)
        model = data["model"]
        repo = model.get("model_repo_id", model.get("repo_id"))
        revision = model.get("model_revision", model.get("revision"))
        weight = model.get("model_sha256") or model["files"][0]["sha256"]
        self.require(repo == asset["repo_id"] and revision == asset["revision"]
                     and weight == asset["files"][0]["sha256"], "campaign: model/asset identity mismatch")
        runtime = data["runtime"]
        self.require(runtime["repository"] == "https://github.com/ggml-org/llama.cpp.git"
                     and runtime["revision"] == "efe3626b119ff81033e309c3ba07a770bef2c546"
                     and runtime["requested_backend"] == "metal", "campaign: runtime identity mismatch")
        self.require(runtime["binary_sha256"] == "d6ec60cbb70b61572c0f33305b6839952445fa35b9ee2f1355b71216ab28ada1",
                     "campaign: runtime binary mismatch")
        return data, {"adapter": "systemone_local", "model_repo_id": repo, "model_revision": revision,
                      "model_assets_sha256": weight, "runtime": dict(runtime)}

    @staticmethod
    def lock_pins(text):
        """Exact `name==version` pins of a runtime lock; comments and blanks are ignored."""
        pins = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.+!_-]*)", line)
            if match is None:
                raise ValueError("campaign: unpinned runtime lock line")
            pins[re.sub(r"[-_.]+", "-", match[1]).lower()] = match[2]
        return pins

    def cpu(self, path, asset_path, lock_path, profile_path):
        """A CPU-worker pack campaign exported by scripts/export-cpu-pack-campaign.py."""
        data = self.inputs.load(path)
        self.require(data["schema_version"] == "deposium.cpu-pack-campaign-public/v1"
                     and data["reference_review"] == "agent_only_pending_human"
                     and data["execution_scope"] == "isolated_cpu_worker_no_application_gateway",
                     "campaign: changed CPU qualification")
        asset, model, runtime = self.inputs.load(asset_path), data["model"], data["runtime"]
        profile = self.inputs.load(profile_path)
        profile_adapter = profile["adapter"]
        self.require(model["model_repo_id"] == asset["repo_id"] and model["model_revision"] == asset["revision"]
                     and model["assets_manifest"] == asset_path, "campaign: CPU model/asset identity mismatch")
        lock_bytes = self.inputs.read(lock_path)
        lock = self.lock_pins(lock_bytes.decode("utf-8"))
        self.require(runtime["adapter"] in ("d3", "vela2") and runtime["adapter"] == profile_adapter
                     and runtime["device"] == "cpu" and runtime["runtime_lock"] == lock_path
                     and runtime["runtime_lock_sha256"] == hashlib.sha256(lock_bytes).hexdigest()
                     and runtime["profile"] == profile_path, "campaign: CPU runtime identity mismatch")
        # The aggregate's pins must be the lock's own values, not merely present.
        pins = runtime["pins"]
        self.require(isinstance(pins, dict) and {"python", "torch", "transformers", "tokenizers", "safetensors"} <= set(pins)
                     and all(lock.get(name) == version for name, version in pins.items()),
                     "campaign: CPU runtime pins differ from the referenced lock")
        self.require(profile["profile_id"] == runtime["profile_id"] and profile["revision"] == asset["revision"]
                     and profile["model"]["repo_id"] == asset["repo_id"], "campaign: CPU profile mismatch")
        return data, {"adapter": runtime["adapter"], "model_repo_id": asset["repo_id"], "model_revision": asset["revision"],
                      "model_assets_sha256": model["model_assets_sha256"],
                      "runtime": {k: runtime[k] for k in ("device", "platform", "pins", "runtime_lock_sha256", "loading_mode")}}

    def phase(self, data, name, task, observation, model, source, report, total, families):
        phase = data["phases"][name]
        count = self.native_counts(phase["counts"])
        self.require(count["total"] == total and count["families"] == families and count["scored"] > 0,
                     "campaign: wrong denominator or zero scored cases")
        splits = {"context": {"train": 36, "calibration": 30, "test": 66},
                  "capability": {"train": 48, "calibration": 48, "test": 96},
                  "physics": {"calibration": 12, "test": 36}}
        self.require({k: v["total"] for k, v in count["by_split"].items()} == splits[task],
                     "campaign: changed split denominators")
        self.require(phase["included_in_full_pack_quality_denominator"] is True,
                     "campaign: canary cannot enter quality table")
        identity = phase["identity"]
        self.require(identity["dataset_sha256"] == DATASETS[task], "campaign: mixed dataset")
        for key in ("raw_sha256", "outer_seal_sha256", "scorer_sha256", "analysis_sha256"):
            self.hash(identity[key])
        groups = {axis: {key: self.native_counts(value) for key, value in values.items()}
                  for axis, values in phase["groups"].items()}
        for values in groups.values():
            self.partition(count, values)
        for split, group in count["by_split"].items():
            self.require(all(groups["split"][split][k] == group[k] for k in ("correct", "scored", "total")),
                         "campaign: split views differ")
        backend = phase["actual_backend"]
        if backend["kind"] == "cpu":
            precision = (backend.get("backbone_dtype"), backend.get("readout_dtype"), backend.get("dtype"))
            self.require(backend["device"] == "cpu" and type(backend["threads"]) is int and backend["threads"] > 0
                         and precision in (("bfloat16", "float32", None), (None, None, "float32")),
                         "campaign: CPU worker identity not observed")
        else:
            self.require(backend["kind"] == "metal" and backend["offloaded_layers"] == backend["total_layers"] > 0,
                         "campaign: Metal not observed")
        resource = phase["resources"]
        peak = resource.get("sampled_group_rss_peak_mib", resource.get("rss_peak_mib"))
        self.require(type(peak) in (int, float) and math.isfinite(peak) and peak >= 0
                     and resource["stop_reason"] is None, "campaign: invalid resource observation")
        return {"task": task, "observation": observation, "model": model, "counts": count, "groups": groups,
                "source": source, "report": report, "identity": dict(identity),
                "model_identity": {"model_repo_id": data["model"].get("model_repo_id", data["model"].get("repo_id")),
                                   "model_revision": data["model"].get("model_revision", data["model"].get("revision")),
                                   "model_assets_sha256": data["model"].get("model_sha256") or data["model"].get("model_assets_sha256")
                                   or data["model"]["files"][0]["sha256"],
                                   "runtime": dict(data["runtime"])},
                "adapter_ms": self.stats(phase["latency_ms"], count["statuses"]["ok"]),
                "session_group_peak_rss_mib": peak,
                "rss_scope": (resource.get("rss_scope") if backend["kind"] == "cpu" else
                              "Sampled owned process-group peak over fresh session startup, controls, warm-up and this pack; not total GPU memory")}

    def context_row(self, phase, identity, meta):
        c, groups = phase["counts"], phase["groups"]
        for axis, expected in {"domain": {"documentary": 76, "mathematics": 28, "chemistry": 28},
                               "split": {"train": 36, "calibration": 30, "test": 66},
                               "language": {"fr": 66, "en": 66}, "difficulty": {"D1": 40, "D2": 40, "D3": 52}}.items():
            self.require({k: v["total"] for k, v in groups[axis].items()} == expected,
                         "campaign: context group denominator mismatch")
        for evidence in meta["evidence"] + [meta["model_size"]["source"]]:
            self.inputs.read(evidence["path"])
        self.require(meta["source_analysis"] == phase["source"], "campaign: metadata source mismatch")
        return {"id": phase["observation"], "metadata": meta, "identity": identity,
                "context": {"counts": c, "groups": groups,
                            "source": {**phase["identity"], "seal_sha256": phase["identity"]["outer_seal_sha256"]}},
                "tool_proposal": None, "tool_proposal_status": "not_run",
                "resources": {"adapter_ms": phase["adapter_ms"], "initialization_ms": None,
                              "worker_rss_mib": {"count": 0, "min": None, "median": None, "p95": None, "max": None},
                              "session_process_group_peak_rss_mib": phase["session_group_peak_rss_mib"],
                              "sampled_gpu_allocated_peak_mib": None, "rss_scope": phase["rss_scope"]}}

    def passage_count(self, value):
        return self.counts(value["correct"], value["scored"], value["total"], value["statuses"], value["families"])

    def macro(self, score, count):
        classes = score["by_expected_label"]
        self.require(sum(v["total_decisions"] for v in classes.values()) == count["total"]
                     and sum(v["scored_decisions"] for v in classes.values()) == count["scored"],
                     "campaign: class denominators mismatch")
        values = [v["accuracy_scored"] for v in classes.values() if v["accuracy_scored"] is not None]
        self.require(all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in values),
                     "campaign: invalid class accuracy")
        macro = score["macro_accuracy_scored"]
        self.require((macro is None if not values else type(macro) in (int, float) and math.isfinite(macro)
                      and math.isclose(macro, sum(values) / len(values), abs_tol=1e-12)),
                     "campaign: inconsistent macro accuracy")
        self.require(math.isclose(sum((v["accuracy_scored"] or 0) * v["scored_decisions"]
                                      for v in classes.values()), count["correct"], abs_tol=1e-9),
                     "campaign: class correct counts mismatch")
        return macro

    def passage(self, path, schema, asset, observation, model, report):
        data, identity = self.native(path, schema, asset)
        sel = data["selection"]
        self.require(sel["sha256"] == DATASETS["passage"] and sel["split"] == "test"
                     and sel["rotation"] == 0 and sel["pools"] == 128 and sel["families"] == 8,
                     "campaign: passage selection mismatch")
        coverage = data["coverage"]
        self.require(coverage["physical_planned"] == 728 and coverage["logical_decisions"] == 1408
                     and type(coverage["physical_attempted"]) is int
                     and sum(coverage["physical_statuses"].values()) == coverage["physical_attempted"],
                     "campaign: physical/logical denominator mismatch")
        backend, resources = data["actual_backend"], data["resources"]
        self.require(backend["kind"] == "metal" and backend["offloaded_layers"] == backend["total_layers"] > 0,
                     "campaign: passage Metal not observed")
        self.require(type(resources["rss_peak_mib"]) in (int, float) and math.isfinite(resources["rss_peak_mib"])
                     and resources["rss_peak_mib"] >= 0, "campaign: invalid passage RSS")
        self.inputs.read("docs/" + report)
        rows = []
        for axis, total in (("relevance", 512), ("support", 768), ("answerability", 128)):
            item = data["axes"][axis]
            c = self.passage_count(item["counts"])
            self.require(c["total"] == total and c["families"] == 8, "campaign: passage axis denominator")
            groups = {name: {k: self.passage_count(v) for k, v in values.items()}
                      for name, values in item["groups"].items()}
            for values in groups.values():
                self.partition(c, values)
            confusion = item["confusion"]
            self.require(all(type(n) is int and n >= 0 for row in confusion.values() for n in row.values())
                         and sum(sum(r.values()) for r in confusion.values()) == c["total"]
                         and sum(r.get(label, 0) for label, r in confusion.items()) == c["correct"],
                         "campaign: inconsistent confusion matrix")
            self.require(c["statuses"] == coverage["logical_statuses"][axis], "campaign: axis coverage mismatch")
            rows.append({"task": "passage_" + axis, "observation": observation, "model": model, "counts": c,
                         "groups": groups, "macro_accuracy": self.macro(item, c),
                         "source": path, "report": report, "identity": {**identity, **data["source"]},
                         "physical_calls": item["distinct_physical_calls"],
                         "adapter_ms": self.stats(item["physical_adapter_ms"], item["distinct_physical_calls"]),
                         "session_group_peak_rss_mib": data["resources"]["rss_peak_mib"],
                         "rss_scope": "Sampled whole passage session, all axes including startup/controls/warm-up; not per-axis or total GPU allocation",
                         "confusion": confusion})
        return rows

    def legacy_score(self, score):
        total, scored = score["total_cases"], score["scored_cases"]
        metric = score["metrics"]["accuracy"]
        # Recover the integer numerator only when the published ratio supports it.
        numerator = score.get("accuracy_over_all", metric["mean_over_eligible_missing_zero"]) * total
        self.require(type(numerator) in (int, float) and math.isfinite(numerator)
                     and abs(numerator - round(numerator)) < 1e-9, "campaign: nonintegral legacy numerator")
        c = self.counts(round(numerator), scored, total, score["counts_by_status"], score["family_count"])
        self.require(metric["defined_cases"] == scored and metric["total_cases"] == total,
                     "campaign: legacy metric coverage mismatch")
        return c

    def load(self, metadata, capability):
        clef, ci = self.native(CLEF, "deposium.clef-flash-public/v1", "profiles/clef-flash-q8-assets.json")
        physics, di = self.native(PHYSICS, "deposium.physics-flash-public/v1", "profiles/d3-flash-q8-assets.json")
        new = [self.phase(clef, "context", "context", "ClefFlashQ8", "Clef Flash Q8 · direct Metal", CLEF,
                          "CLEF_FLASH_RESULTS_20261029.md", 132, 66),
               self.phase(physics, "fresh_context_anchor", "context", "D3FlashQ8Upstream", "D3 Flash Q8 · direct Metal",
                          PHYSICS, "PHYSICS_FLASH_RESULTS_20261029.md", 132, 66)]
        contexts = [self.context_row(p, identity, metadata[p["observation"]]) for p, identity in zip(new, (ci, di))]
        rows = [self.phase(clef, "capability", "capability", "ClefFlashQ8", "Clef Flash Q8 · direct Metal",
                           CLEF, "CLEF_FLASH_RESULTS_20261029.md", 192, 48),
                self.phase(clef, "physics", "physics", "ClefFlashQ8", "Clef Flash Q8 · direct Metal",
                           CLEF, "CLEF_FLASH_RESULTS_20261029.md", 48, 24),
                self.phase(physics, "physics", "physics", "D3FlashQ8Upstream", "D3 Flash Q8 · direct Metal",
                           PHYSICS, "PHYSICS_FLASH_RESULTS_20261029.md", 48, 24)]
        cpu_campaigns = (
            ("D3liteMacos", "D3 lite · macOS CPU", "profiles/d3-lite-assets.json", "profiles/d3-lite-macos-cpu.json",
             D3LITE_MACOS_REPORT, D3LITE_MACOS_CAPABILITY, D3LITE_MACOS_PHYSICS),
            ("Vela03Macos", "Vela 2.0 0.3B · macOS CPU", "profiles/vela2-03-assets.json", "profiles/vela2-03-macos-cpu.json",
             VELA03_MACOS_REPORT, VELA03_MACOS_CAPABILITY, VELA03_MACOS_PHYSICS),
            ("D3nanoMacos", "D3 nano · macOS CPU", "profiles/d3-nano-assets.json", "profiles/d3-nano-macos-cpu.json",
             D3NANO_MACOS_REPORT, D3NANO_MACOS_CAPABILITY, D3NANO_MACOS_PHYSICS),
        )
        for observation, model, assets, profile, report, capability_path, physics_path in cpu_campaigns:
            self.inputs.read("docs/" + report)
            for path, pack, total, families in ((capability_path, "capability", 192, 48), (physics_path, "physics", 48, 24)):
                data, _ = self.cpu(path, assets, "runtimes/d3-macos/runtime.lock", profile)
                rows.append(self.phase(data, pack, pack, observation, model, path, report, total, families))
        cp = capability["phases"]["capability"]
        rows.append({"task": "capability", "observation": "D3FlashQ8", "model": "D3 Flash Q8 · gateway Metal",
                     "counts": cp["counts"], "groups": cp["groups"], "source": capability["source"],
                     "report": capability["report"], "identity": capability["identity"], "adapter_ms": cp["adapter_ms"],
                     "session_group_peak_rss_mib": cp["session_group_peak_rss_mib"], "rss_scope": cp["rss_scope"]})
        rows += self.passage(PASSAGE_D3, "deposium.passage-flash-public/v1", "profiles/d3-flash-q8-assets.json",
                             "D3FlashQ8Upstream", "D3 Flash Q8 · direct Metal", "PASSAGE_FLASH_RESULTS_20261029.md")
        rows += self.passage(PASSAGE_CLEF, "deposium.passage-clef-flash-public/v1", "profiles/clef-flash-q8-assets.json",
                             "ClefFlashQ8", "Clef Flash Q8 · direct Metal", "PASSAGE_CLEF_RESULTS_20261029.md")
        cpu = self.inputs.load(PASSAGE_CPU)
        self.require(cpu["dataset_sha256"] == DATASETS["passage"] and cpu["cases"] == 128
                     and cpu["rotation"] == 0 and cpu["split"] == "test", "campaign: historical passage selection")
        jev = self.inputs.load(PASSAGE_JEV)
        self.require(jev["dataset_sha256"] == DATASETS["passage"] and jev["cases"] == 512
                     and jev["rotations"] == [0, 1, 2, 3], "campaign: Jev rotation selection")
        for model, obs, source, report, scores in (
            ("D3-lite · CPU", "D3lite", PASSAGE_CPU, "PASSAGE_CPU_RESULTS_20261015.md", cpu["choice_scores"]),
            ("Jev 1.14 · API", "Jev114", PASSAGE_JEV, "PASSAGE_JEV_RESULTS_20261015.md",
             {k: jev["original_rotation_zero"][k + "_scores"] for k in ("support", "answerability")}),
        ):
            self.inputs.read("docs/" + report)
            for axis, score in scores.items():
                count = self.legacy_score(score)
                groups = {name: {key: self.legacy_score(value) for key, value in values.items()}
                          for name, values in score["by"].items()}
                for values in groups.values():
                    self.partition(count, values)
                rows.append({"task": "passage_" + axis, "observation": obs, "model": model, "counts": count,
                             "groups": groups, "macro_accuracy": self.macro(score, count),
                             "source": source, "report": report, "identity": cpu["choice_model"] if obs == "D3lite" else
                     {k: jev["jev_http"][k] for k in ("adapter", "adapter_sha256", "identity_sha256", "profile_sha256", "returned_model")}})
        # The Jev relevance export repeats decisions over four rotations: never put 2048 in the 512-choice ranking.
        rows.append({"task": "passage_relevance_four_rotations", "observation": "Jev114", "model": "Jev 1.14 · API",
                     "counts": self.legacy_score(jev["relevance_scores"]),
                     "groups": {name: {key: self.legacy_score(value) for key, value in values.items()}
                                for name, values in jev["relevance_scores"]["by"].items()},
                     "macro_accuracy": self.macro(jev["relevance_scores"], self.legacy_score(jev["relevance_scores"])),
                     "source": PASSAGE_JEV, "report": "PASSAGE_JEV_RESULTS_20261015.md", "identity": {}})
        for row in rows:
            c = row["counts"]
            row["status"] = "complete" if c["scored"] == c["total"] else "partial" if c["scored"] else "not_run"
            peers = [r for r in rows if r["task"] == row["task"] and r["counts"]["total"] == c["total"]
                     and r["counts"]["scored"] == r["counts"]["total"]]
            row["rank_all"] = 1 + sum(r["counts"]["correct"] > c["correct"] for r in peers) if row["status"] == "complete" else None
            if row["task"] == "passage_relevance_four_rotations":
                row["rank_all"] = None
            test = c.get("by_split", {}).get("test")
            row["rank_test"] = (1 + sum(r["counts"]["by_split"]["test"]["correct"] > test["correct"] for r in peers)
                                if test and row["status"] == "complete" else None)
        return contexts, sorted(rows, key=lambda r: (r["task"], r["rank_all"] or 999, r["observation"]))
