"""Explicit repeated timing trials using the campaign admission boundary."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import sys
import time

from . import campaigns
from .context_analysis import _measurements, _stats, _provider_usage
from .scoring import STATUSES, summarize


def _distribution(trials: list[dict]) -> dict:
    results = [trial["result"] for trial in trials]
    measurements = [_measurements(result) for result in results]
    return {"recorded_calls": len(trials),
            "counts_by_status": {status: sum(result["status"] == status for result in results) for status in STATUSES},
            "latency": {field: _stats([observation[field] for observation in measurements])
                        for field in ("adapter_duration_ms", "decision_ms", "inference_ms", "http_ms")},
            "successful_latency": {field: _stats([observation[field] for result, observation in zip(results, measurements)
                                                   if result["status"] == "ok"])
                                   for field in ("adapter_duration_ms", "decision_ms", "inference_ms", "http_ms")},
            "provider_usage": _provider_usage(measurements),
            "rss_mib": _stats([observation["rss_mib"] for observation in measurements])}


def _platform() -> dict:
    cpu_model = None
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    return {"python": platform.python_version(), "system": platform.system(), "kernel": platform.release(),
            "machine": platform.machine(), "logical_cpus": os.cpu_count(), "cpu_model": cpu_model,
            "python_executable_sha256": campaigns._hash(Path(sys.executable).read_bytes())}


def benchmark_timing(dataset_path: str | Path, profile_paths: list,
                     output_dir: str | Path, *, stack_root: str | Path | None = None,
                     launches: int = 3, warmup: int = 5, passes: int = 10) -> dict:
    """Initialize candidates sequentially, preserve every trial and close all workers."""
    for field, value, minimum, maximum in (("launches", launches, 1, 10), ("warmup", warmup, 0, 100), ("passes", passes, 1, 100)):
        if type(value) is not int or not minimum <= value <= maximum:
            raise campaigns.CampaignError(f"Timing {field} must be between {minimum} and {maximum}.")
    if not isinstance(profile_paths, list) or not 1 <= len(profile_paths) <= 10:
        raise campaigns.CampaignError("Timing requires between one and ten candidate profile paths.")
    cases, dataset_hash = campaigns.load_cases(dataset_path)
    planned_calls = launches * len(profile_paths) * (1 + warmup + passes * len(cases))
    if planned_calls > 100_000:
        raise campaigns.CampaignError("Timing is bounded to 100000 planned calls; lower launches, warmup or passes.")
    dataset = Path(dataset_path).read_bytes()
    if campaigns._hash(dataset) != dataset_hash:
        raise campaigns.CampaignError("Timing dataset changed during preparation.")
    prepared = []
    identities = set()
    for path in profile_paths:
        source = Path(path).resolve()
        profile, source_hash, recordings = campaigns._prepare_profile(source)
        if campaigns._hash(source.read_bytes()) != source_hash:
            raise campaigns.CampaignError("Timing profile changed during preparation.")
        campaigns._validate_output_scope(cases, profile)
        identity = profile["profile_id"]
        if identity in identities:
            raise campaigns.CampaignError("Timing candidate profile IDs must be unique.")
        identities.add(identity)
        assets = None
        if isinstance(profile.get("model"), dict) and profile["model"].get("assets_manifest"):
            asset_path = Path(profile["model"]["assets_manifest"])
            assets = asset_path.read_bytes()
            if len(assets) > 1024 * 1024:
                raise campaigns.CampaignError("Timing assets manifest exceeds the bounded size.")
        prepared.append({"candidate": identity, "profile": profile, "source_profile_sha256": source_hash,
                         "recordings": recordings, "assets_manifest": assets})
    scorer = campaigns._scorer_fingerprint()
    manifest = {"schema_version": "deposium.timing/v1", "created_at": datetime.now(timezone.utc).isoformat(),
                "dataset_sha256": dataset_hash, "case_ids": [case["case_id"] for case in cases],
                "independent_families": len({case["translation_family"] for case in cases}),
                "protocol": {"launches": launches, "warmup": warmup, "passes": passes,
                             "cold": "one first call on the first dataset case after each initialization",
                             "warmup_description": "cycle dataset cases in fixed order; recorded but excluded from measured-pass statistics",
                             "candidate_order": "profile order on even launch indexes; reversed on odd indexes",
                             "process_cold": "fresh local adapter; local worker process only for local models, remote server lifecycle/cache unobserved",
                             "total_planned_calls": planned_calls},
                "profiles": [{"candidate": entry["candidate"], "profile_sha256": campaigns._hash(campaigns._encode(entry["profile"])),
                              "source_profile_sha256": entry["source_profile_sha256"],
                              "assets_manifest_sha256": campaigns._hash(entry["assets_manifest"]) if entry["assets_manifest"] is not None else None}
                             for entry in prepared],
                "stack_root": str(Path(stack_root).resolve()) if stack_root is not None else None,
                "bench": campaigns._source_fingerprint(), "scorer": scorer, "platform": _platform(),
                "limitations": ["Explicit timing archive, not a campaign-schema archive or product qualification.",
                                "Repeated calls do not add independent quality examples.",
                                "Cold denotes the first call of a fresh adapter; local files may remain cached, and remote server lifecycle is unobserved.",
                                "Adapter, decision and inference measurements have distinct boundaries.",
                                "HTTP candidates perform explicit budgeted API calls; their durable ledger persists across launches and resumes." if any(entry["profile"]["adapter"] == "jev_http" for entry in prepared) else "No paid API, download or service change is performed by this runner.",
                                "HTTP time is client networking/TLS/queue; provider usage is post-hoc. Server timing, native tokens and RSS are unobserved."]}
    output = campaigns._destination(output_dir, stack_root)
    campaigns._write_new(output / "cases.jsonl", dataset)
    for index, entry in enumerate(prepared):
        candidate_dir = output / f"candidate-{index}"
        candidate_dir.mkdir()
        entry["archive_profile_path"] = candidate_dir / "profile.json"
        campaigns._write_new(entry["archive_profile_path"], campaigns._encode(entry["profile"]))
        if entry["recordings"] is not None:
            campaigns._write_new(candidate_dir / "recordings.jsonl", entry["recordings"])
        if entry["assets_manifest"] is not None:
            campaigns._write_new(candidate_dir / "assets-manifest.json", entry["assets_manifest"])
    campaigns._write_new(output / "timing-manifest.json", campaigns._encode(manifest))
    trials = []
    launches_observed = []
    first_identity = {}
    interrupted = False
    failure = None
    with (output / "trials.jsonl").open("xb") as handle:
        def record_trial(launch, entry, phase, pass_index, case, adapter):
            observation = campaigns.observe_case(case, adapter)
            trial = {"launch": launch, "candidate": entry["candidate"], "phase": phase,
                     "pass_index": pass_index, "result": observation}
            handle.write(campaigns._encode(trial))
            handle.flush()
            os.fsync(handle.fileno())
            trials.append(trial)
        try:
            for launch in range(launches):
                order = prepared if launch % 2 == 0 else list(reversed(prepared))
                for entry in order:
                    started = time.perf_counter()
                    adapter = campaigns.create_adapter(entry["profile"], entry["archive_profile_path"],
                                                       stack_root=stack_root, recordings_data=entry["recordings"])
                    try:
                        init_wall = (time.perf_counter() - started) * 1000
                        provenance = campaigns._decode(campaigns._encode(adapter.provenance))
                        identity = provenance.get("identity_sha256")
                        if not identity or (entry["candidate"] in first_identity and first_identity[entry["candidate"]] != identity):
                            raise campaigns.CampaignError("Timing candidate identity changed between launches.")
                        first_identity[entry["candidate"]] = identity
                        observation = {"launch": launch, "candidate": entry["candidate"], "init_wall_ms": init_wall,
                                       "adapter_provenance": provenance}
                        campaigns._write_new(output / f"launch-{launch}-{prepared.index(entry)}.json", campaigns._encode(observation))
                        launches_observed.append(observation)
                        record_trial(launch, entry, "cold", None, cases[0], adapter)
                        for iteration in range(warmup):
                            record_trial(launch, entry, "warmup", iteration, cases[iteration % len(cases)], adapter)
                        for iteration in range(passes):
                            for case in cases:
                                record_trial(launch, entry, "measured", iteration, case, adapter)
                    finally:
                        campaigns._close_adapter(adapter)
        except KeyboardInterrupt:
            interrupted = True
        except Exception as error:
            # Exception text may contain paths, provider logs or secrets.
            failure = type(error).__name__
    if campaigns._scorer_fingerprint() != scorer:
        failure = "scorer_changed"
    candidates = {}
    for entry in prepared:
        selected = [trial for trial in trials if trial["candidate"] == entry["candidate"]]
        pass_scores = []
        if failure != "scorer_changed":
            for launch in range(launches):
                for iteration in range(passes):
                    records = [trial["result"] for trial in selected if trial["phase"] == "measured"
                               and trial["launch"] == launch and trial["pass_index"] == iteration]
                    pass_scores.append({"launch": launch, "pass_index": iteration, "metrics": summarize(cases, records)})
        candidates[entry["candidate"]] = {
            "phases": {phase: _distribution([trial for trial in selected if trial["phase"] == phase])
                       for phase in ("cold", "warmup", "measured")},
            "initialization_ms": _stats([observation["init_wall_ms"] for observation in launches_observed
                                          if observation["candidate"] == entry["candidate"]]),
            "launches": [observation for observation in launches_observed if observation["candidate"] == entry["candidate"]],
            "per_pass_quality": pass_scores,
            "independent_families": manifest["independent_families"],
            "by_launch": {str(launch): _distribution([trial for trial in selected if trial["phase"] == "measured" and trial["launch"] == launch])
                          for launch in range(launches)}}
    summary = {"schema_version": "deposium.timing-summary/v1",
               "completion_status": "interrupted" if interrupted else "error" if failure else "complete",
               "error_type": failure, "archive_dir": str(output),
               "planned_calls": manifest["protocol"]["total_planned_calls"], "recorded_calls": len(trials),
               "independent_families": manifest["independent_families"], "candidates": candidates,
               "trials_sha256": campaigns._hash((output / "trials.jsonl").read_bytes()),
               "statistics_protocol": {"median": "arithmetic central pair", "p95": "nearest rank ceil(0.95*n)",
                                       "timeout": "recorded durations are censored; status denominators retained",
                                       "quality": "per measured pass; repeats do not increase family count"},
               "limitations": manifest["limitations"]}
    campaigns._write_new(output / "summary.json", campaigns._encode(summary))
    report = ["# Repeated timing observations", "", f"Status: {summary['completion_status']}; recorded calls: {len(trials)} / {summary['planned_calls']}.",
              f"Independent families: {summary['independent_families']}; temporal repetitions do not add families.", "",
              "| Candidate | Phase | Calls | OK | Errors | Timeouts | Adapter median ms | Decision median ms | Decision p95 ms | Decision count |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    def render(value):
        return "unobserved" if value is None else f"{value:.3f}"
    http_report = []
    for name, data in candidates.items():
        label = name.replace("|", "\\|")
        for phase, distribution in data["phases"].items():
            status = distribution["counts_by_status"]
            adapter = distribution["latency"]["adapter_duration_ms"]
            decision = distribution["latency"]["decision_ms"]
            report.append(f"| {label} | {phase} | {distribution['recorded_calls']} | {status['ok']} | "
                          f"{status['error']} | {status['timeout']} | {render(adapter['median'])} | {render(decision['median'])} | "
                          f"{render(decision['p95'])} | {decision['count']} |")
            http = distribution["latency"]["http_ms"]
            usage = distribution["provider_usage"]
            http_report.append(f"HTTP attempts {label}/{phase}: {usage['http_attempted_calls']}; cached failures {usage['cached_failure_calls']}; attempt flag unreported {usage['http_attempt_unreported_calls']}.")
            http_report.append(f"Client HTTP {label}/{phase}: median {render(http['median'])} ms; p95 {render(http['p95'])} ms; count {http['count']}.")
            http_report.extend(f"{field}: reported {usage[field]['count']} / {usage['recorded_calls']} calls; declared total {usage[field]['total']}."
                          for field in ("provider_input_tokens", "provider_output_tokens"))
    report += ["", *http_report, "", "Initialization is measured separately per launch in summary.json.",
               "Cold is a fresh-adapter first call; local caches are not cleared and remote server lifecycle is unobserved. Warmup is excluded from measured-pass statistics.",
               "All failure statuses remain visible in JSON; successful latency means status ok, not a correct answer.",
               "Per-pass quality and per-launch distributions are retained. These observations do not qualify a product or fallback policy.", ""]
    campaigns._write_new(output / "report.md", "\n".join(report).encode())
    files = {str(path.relative_to(output)): campaigns._hash(path.read_bytes())
             for path in sorted(output.rglob("*")) if path.is_file()}
    campaigns._write_new(output / "seal.json", campaigns._encode({"schema_version": "deposium.timing-seal/v1",
                                                                  "files": files, "sha256": campaigns._hash(campaigns._encode(files))}))
    return summary
