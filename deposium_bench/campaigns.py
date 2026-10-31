"""Shared campaign engine: immutable inputs, durable raw trace and derived scores.

Resume and rescore always produce a new archive. An adapter only receives the
candidate request, never the reference annotations held in the archived cases.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Callable
import uuid

from . import __version__
from .adapters import create_adapter, load_profile, parse_profile
from .cases import _json as validate_json, candidate_request, load_cases, parse_cases
from .git_inventory import InventoryError, inspect_stack
from .preflight import build_preflight
from .registry import load_registry
from .scoring import SCORER_VERSION, summarize

CAMPAIGN_VERSION = "deposium.campaign/v1"
RESULT_VERSION = "deposium.result/v1"
STATUSES = {"ok", "unsupported", "missing", "error", "timeout", "abstain"}


class CampaignError(ValueError):
    """An archive or campaign contract cannot be trusted."""


def _encode(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode(data: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise CampaignError("Archive has duplicate JSON keys.")
            result[key] = value
        return result
    try:
        result = json.loads(data, object_pairs_hook=unique,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        validate_json(result)
    except (ValueError, UnicodeError) as exc:
        raise CampaignError("Archive contains invalid JSON.") from exc
    if not isinstance(result, dict):
        raise CampaignError("Archive JSON record must be an object.")
    return result


def _write_new(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _source_fingerprint() -> dict:
    root = Path(__file__).parent
    files = {file.name: _hash(file.read_bytes()) for file in sorted(root.glob("*.py"))}
    schemas = {file.name: _hash(file.read_bytes()) for file in sorted((root.parent / "schemas").glob("*.json"))}
    try:
        git = inspect_stack(root.parent)["parent"]
    except InventoryError:
        git = None
    return {"version": __version__, "files": files, "sha256": _hash(_encode(files)),
            "schemas": schemas, "git": git, "source_archive": "not_captured"}


def _scorer_fingerprint() -> dict:
    root = Path(__file__).parent
    files = {name: _hash((root / name).read_bytes()) for name in
             ("scoring.py", "cases.py", "tool_plan.py", "tool_discovery.py", "tool_arguments.py", "tool_episodes.py", "local_tool_policy.py", "synthetic_tools.py", "research_corpus.py", "physics_corpus.py", "capability_corpus.py", "choice_protocol.py",
              "lengths.py", "data/context-distractors.json")}
    from .capability_corpus import SOURCE_FILES
    for name in SOURCE_FILES:
        relative = "datasets/capability-choice-v1/" + name
        files[relative] = _hash((root.parent / relative).read_bytes())
    return {"version": SCORER_VERSION, "files": files, "sha256": _hash(_encode(files))}


def _destination(output_dir: str | Path, stack_root: str | Path | None,
                 parent_archive: Path | None = None) -> Path:
    output = Path(output_dir).expanduser().absolute()
    if stack_root is not None and output.resolve().is_relative_to(Path(stack_root).resolve()):
        raise CampaignError("Campaign output must be outside the application stack.")
    if parent_archive is not None and output.resolve().is_relative_to(parent_archive.resolve()):
        raise CampaignError("A derived archive must be outside its original archive.")
    if output.exists() or output.is_symlink():
        raise FileExistsError("Campaign output already exists.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()  # exclusive allocation; no prior campaign is reused in place
    return output


def _limit(value: int | None) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise CampaignError("max_new_cases must be a non-negative integer.")


def _prepare_profile(profile_path: Path) -> tuple[dict, str, bytes | None]:
    profile, digest = load_profile(profile_path)
    recordings = None
    if profile["adapter"] in {"recorded", "fixture_arguments", "fixture_episode"}:
        recordings = (profile_path.parent / profile["recordings"]).read_bytes()
        profile = {**profile, "recordings": "recordings.jsonl"}
    elif profile["adapter"] in {"julia", "gliner", "decision2", "vela2", "d3"}:
        model = dict(profile["model"])
        for name in ("local_dir", "runtime_python", "assets_manifest", "prompt_path", "runtime_lock"):
            # Preserve venv executable symlinks; resolving them loses the venv.
            model[name] = os.path.abspath(profile_path.parent / model[name])
        profile = {**profile, "model": model}
    elif profile["adapter"] == "noma":
        from .noma_adapter import PATH_FIELDS
        model = dict(profile["model"])
        for name in PATH_FIELDS:
            # Keep the venv executable symlink rather than resolving to its base interpreter.
            model[name] = os.path.abspath(profile_path.parent / model[name])
        profile = {**profile, "model": model}
    elif profile["adapter"] == "small_model":
        from .small_model_adapter import COMMON_PATHS
        model = dict(profile["model"])
        extra = "prompt_path" if model["mode"] in {"omni", "liquid3"} else "template_path"
        for name in COMMON_PATHS | {extra}:
            model[name] = os.path.abspath(profile_path.parent / model[name])
        profile = {**profile, "model": model}
    elif profile["adapter"] == "vela3_fast":
        from .vela3_fast_adapter import PATH_FIELDS
        model = dict(profile["model"])
        for name in PATH_FIELDS:
            model[name] = os.path.abspath(profile_path.parent / model[name])
        profile = {**profile, "model": model}
    elif profile["adapter"] == "gliclass":
        from .gliclass_adapter import PATH_FIELDS
        model = dict(profile["model"])
        for name in PATH_FIELDS:
            model[name] = os.path.abspath(profile_path.parent / model[name])
        profile = {**profile, "model": model}
    elif profile["adapter"] == "laya":
        from .laya_adapter import PATH_FIELDS
        model = dict(profile["model"])
        for name in PATH_FIELDS:
            model[name] = os.path.abspath(profile_path.parent / model[name])
        profile = {**profile, "model": model}
    elif profile["adapter"] in {"jev_http", "decision3_http"}:
        model = dict(profile["model"])
        model["budget_ledger"] = os.path.abspath(profile_path.parent / model["budget_ledger"])
        profile = {**profile, "model": model}
    elif profile["adapter"] in {"systemone_local", "llama_cpp_json"}:
        model = dict(profile["model"])
        model["session_manifest"] = os.path.abspath(profile_path.parent / model["session_manifest"])
        profile = {**profile, "model": model}
    elif profile["adapter"] == "indecis":
        from .indecis_adapter import PATH_FIELDS
        model = dict(profile["model"])
        for name in PATH_FIELDS:
            model[name] = os.path.abspath(profile_path.parent / model[name])
        profile = {**profile, "model": model}
    return profile, digest, recordings


def _validate_output_scope(cases: list[dict], profile: dict) -> None:
    if profile["adapter"] not in {"julia", "gliner", "jev_http", "decision3_http", "indecis", "decision2", "vela2", "d3", "noma", "laya", "small_model", "systemone_local", "gliclass", "vela3_fast"}:
        return
    supported = [case for case in cases if case["contract_id"] in profile["capabilities"]]
    if not supported:
        raise CampaignError("Isolated model requires cases for its declared capability.")
    for case in supported:
        assertions = case["reference"]["assertions"]
        if case["contract_id"] == "bench.context-choice":
            ids = {option["id"] for option in case["input"]["options"]}
            if (len(assertions) != 1 or assertions[0]["path"] != "/choice_id"
                    or assertions[0]["op"] != "equals" or assertions[0]["value"] not in ids):
                raise CampaignError("Choice candidate requires one exact choice_id reference.")
            continue
        if (len(assertions) != 1 or assertions[0]["path"] != "/task"
                or assertions[0]["op"] != "equals"
                or assertions[0]["value"] not in ("catalog", "stored_summaries", "retrieve_answer")):
            raise CampaignError("Julia pilot supports the /task-only projection, not the full document plan.")


def _close_adapter(adapter: Any) -> None:
    close = getattr(adapter, "close", None)
    if callable(close):
        close()


def _stack_context(cases: list[dict], profile: dict, stack_root: str | Path | None) -> tuple[dict, bytes | None]:
    registry, registry_hash = load_registry()
    preflight = None
    inventory_status = "not_observed"
    if stack_root is not None:
        try:
            preflight = build_preflight(stack_root, selected_components=["deposium_MCPs"])
            inventory_status = "observed"
        except InventoryError:
            inventory_status = "unavailable"
    definitions = registry["components"] if preflight is None else preflight["components"]
    components = []
    for component in definitions:
        contracts = {contract["id"] for contract in component["contracts"]}
        linked_cases = [case for case in cases if case["contract_id"] in contracts or
                        contracts.intersection(case.get("evaluation", {}).get("related_contract_ids", []))]
        supported = (sorted(contracts & set(profile["capabilities"]))
                     if profile["adapter"] in {"mcps", "mcps_resident"} else [])
        selected = any(case["contract_id"] in supported for case in linked_cases)
        components.append({"id": component["id"], "path": component["path"],
                           "case_ids": [case["case_id"] for case in linked_cases],
                           "supported_contract_ids": supported, "selected": selected,
                           "omission_reason": None if selected else (
                               "harness_control_only" if profile["qualification"] == "harness_control" else
                               "model_isolated_only" if profile["qualification"] == "model_isolated" else
                               "no_cases_in_campaign" if not linked_cases else "no_supported_contract")})
    payload = _encode(preflight) if preflight is not None else None
    return {"registry_sha256": registry_hash, "inventory_status": inventory_status,
            "preflight_sha256": _hash(payload) if payload is not None else None,
            "components": components}, payload


def _manifest(cases: list[dict], dataset: bytes, profile: dict, source_profile_hash: str,
              adapter_provenance: dict, mode: str, parent: dict | None,
              stack_root: str | Path | None, stack_context: dict) -> dict:
    return {
        "schema_version": CAMPAIGN_VERSION, "run_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(), "mode": mode,
        "qualification": profile["qualification"],
        "proof_level": "harness_control" if profile["qualification"] == "harness_control" else "A",
        "input_protocol": ("generated_tool_proposals_v1" if profile["adapter"] == "llama_cpp_json" else
                           "fixture_episode_control" if profile["adapter"] == "fixture_episode" else
                           "fixture_arguments_control" if profile["adapter"] == "fixture_arguments" else
                           "recorded_control" if profile["adapter"] == "recorded" else
                           "context_choice" if "bench.context-choice" in profile["capabilities"] else "current_equivalent"),
        "dataset_sha256": _hash(dataset), "profile_sha256": _hash(_encode(profile)),
        "source_profile_sha256": source_profile_hash,
        "case_ids": [case["case_id"] for case in cases],
        "case_count": len(cases), "adapter_provenance": adapter_provenance,
        "stack_root": str(Path(stack_root).resolve()) if stack_root is not None else None,
        "stack_context": stack_context,
        "bench": _source_fingerprint(), "scorer": _scorer_fingerprint(),
        "parent_archive": parent,
        "limitations": ["This is not integrated routing or product qualification.",
                        "Synthetic initial cases require independent annotation review.",
                        "Source hashes identify local bytes but source archives are not captured.",
                        "Stack inventory is a non-atomic source observation, not active service evidence.",
                        "Completed raw records are never retried automatically.",
                        "Unrecorded calls interrupted mid-flight may execute again on resume."],
    }


def _create_archive(output: Path, manifest: dict, dataset: bytes, profile: dict,
                    recordings: bytes | None, preflight: bytes | None) -> None:
    _write_new(output / "cases.jsonl", dataset)
    _write_new(output / "profile.json", _encode(profile))
    if recordings is not None:
        _write_new(output / "recordings.jsonl", recordings)
    if preflight is not None:
        _write_new(output / "stack-preflight.json", preflight)
    _write_new(output / "manifest.json", _encode(manifest))


def _normal_result(case: dict, response: Any, elapsed_ms: float) -> dict:
    request_hash = _hash(_encode(candidate_request(case)))
    if (not isinstance(response, dict) or set(response) != {"status", "output", "raw_output", "error"}
            or not isinstance(response.get("status"), str) or response["status"] not in STATUSES
            or (response["error"] is not None and not isinstance(response["error"], str))):
        response = {"status": "error", "output": None, "raw_output": None,
                    "error": "Adapter returned an invalid result envelope."}
    try:
        validate_json(response)
        _encode(response)
    except (TypeError, ValueError):
        response = {"status": "error", "output": None, "raw_output": None,
                    "error": "Adapter returned a non-JSON result."}
    return {"schema_version": RESULT_VERSION, "case_id": case["case_id"],
            "contract_id": case["contract_id"], "request_sha256": request_hash,
            "status": response["status"], "output": response.get("output"),
            "raw_output": response.get("raw_output"), "error": response.get("error"),
            "duration_ms": elapsed_ms}


def _execute(output: Path, cases: list[dict], adapter: Any, prior: list[dict],
             *, max_new_cases: int | None,
             stop_requested: Callable[[], bool] | None = None) -> tuple[list[dict], bool]:
    completed = {record["case_id"] for record in prior}
    records = list(prior)
    count = 0
    interrupted = False
    with (output / "raw.jsonl").open("xb") as trace:
        for record in prior:
            trace.write(_encode(record))
        trace.flush()
        os.fsync(trace.fileno())
        try:
            for case in cases:
                if case["case_id"] in completed:
                    continue
                if max_new_cases is not None and count >= max_new_cases:
                    break
                if stop_requested is not None and stop_requested():
                    break
                record = observe_case(case, adapter)
                trace.write(_encode(record))
                trace.flush()
                os.fsync(trace.fileno())
                records.append(record)
                count += 1
        except KeyboardInterrupt:
            interrupted = True
    return records, interrupted


def observe_case(case: dict, adapter: Any) -> dict:
    """Shared admission and measurement boundary for campaigns and timing trials."""
    # Reference validation and snapshot construction belong to the harness,
    # outside the candidate-call clock. The adapter never receives annotations.
    request = candidate_request(case)
    start = time.perf_counter()
    length = case.get("evaluation", {}).get("length")
    if length is not None and not length["within_target"]:
        response = {"status": "unsupported", "output": None, "raw_output": None,
                    "error": "input_length_target_unattainable"}
    elif case["contract_id"] not in adapter.capabilities:
        response = {"status": "unsupported", "output": None, "raw_output": None,
                    "error": "Contract is not supported by this adapter."}
    else:
        try:
            response = adapter.predict(request)
        except Exception as exc:
            response = {"status": "error", "output": None, "raw_output": None,
                        "error": f"Adapter exception ({type(exc).__name__})."}
    return _normal_result(case, response, (time.perf_counter() - start) * 1000)


def render_report(summary: dict) -> str:
    metrics = summary["metrics"]
    lines = ["# Campagne Deposium", "", f"- Run : `{summary['run_id']}`",
             f"- Type : `{summary['qualification']}`; mode : `{summary['mode']}`",
             f"- Exécution : `{summary['completion_status']}`; verdict : `{metrics['verdict']}`",
             f"- Cas scorés : {metrics['scored_cases']} / {metrics['total_cases']}",
             f"- Cas réussis : {metrics['passed_cases']} / {metrics['total_cases']}",
             "", "Ce résultat concerne des contrôles du banc, un modèle ou un composant isolé.",
             "Il ne qualifie ni le routage intégré ni le parcours produit.",
             "", "| État | Nombre |", "|---|---:|"]
    for status, count in sorted(metrics["counts_by_status"].items()):
        lines.append(f"| {status} | {count} |")
    lines += ["", "| Pack | Scorés / total | Réussis / total |", "|---|---:|---:|"]
    for pack, counts in sorted(metrics["by_pack"].items()):
        lines.append(f"| {pack} | {counts['scored_cases']} / {counts['total_cases']} | "
                     f"{counts['passed_cases']} / {counts['total_cases']} |")
    lines += ["", "| Langue | Scorés / total | Réussis / total |", "|---|---:|---:|"]
    for language, counts in sorted(metrics["by_language"].items()):
        lines.append(f"| {language} | {counts['scored_cases']} / {counts['total_cases']} | "
                     f"{counts['passed_cases']} / {counts['total_cases']} |")
    lines += ["", "| Composant | Sélection | Traces | Cas scorés |", "|---|---|---:|---:|"]
    for component in summary["stack_coverage"]:
        selection = "replay demandé" if component["selected"] else component["omission_reason"]
        lines.append(f"| {component['path']} | {selection} | {component['recorded_cases']} | {component['scored_cases']} |")
    lines += ["", "Une sélection indique le périmètre demandé, pas sa disponibilité ou sa réussite.",
              "Les contrôles figés ne sollicitent aucun composant applicatif."]
    discovery = metrics.get("task_metrics", {}).get("bench.tool-discovery")
    if discovery is not None:
        eligible, observed = discovery["eligible_select_cases"], discovery["observed_select_cases"]
        def displayed(value):
            return "N/A" if value is None else f"{value:.4f}"
        lines += ["", "## Tool discovery (tool-ID level)", "",
                  f"Select-reference cases: {eligible}; valid metric observations: {observed}. "
                  "Missing, failed and invalid outputs contribute zero to all-eligible means.", "",
                  "| Metric | Sum / eligible select cases | Mean |", "|---|---:|---:|"]
        for name in ("shortlist_recall", "shortlist_precision", "final_recall", "final_precision"):
            lines.append(f"| {name} | {discovery[name + '_sum']:.4f} / {eligible} | "
                         f"{displayed(discovery[name + '_over_all_eligible'])} |")
        for name in ("final_sufficient", "final_minimal"):
            lines.append(f"| {name} | {discovery[name + '_cases']} / {eligible} | "
                         f"{displayed(discovery[name + '_over_all_eligible'])} |")
        lines += ["", f"Unnecessary final tools: {discovery['unnecessary_tools_sum']} over "
                  f"{observed} valid select-reference observations; observed mean "
                  f"{displayed(discovery['unnecessary_tools_mean_observed'])}. "
                  "This count does not assign zero unnecessary calls to unobserved outputs."]
    arguments = metrics.get("task_metrics", {}).get("bench.tool-arguments")
    if arguments is not None:
        total = arguments["eligible_cases"]
        lines += ["", "## Synthetic argument execution", "",
                  "Recorded proposals; the fixture tools actually execute. No model or product is qualified.",
                  "", "| Stage | Correct / eligible cases |", "|---|---:|"]
        for stage in ("tool", "arguments", "binding", "execution", "result"):
            lines.append(f"| {stage} | {arguments[stage + '_correct_cases']} / {total} |")
        lines += ["", f"Observed tool calls: {arguments['tool_calls_observed']}; "
                  f"cases with retained execution traces: {arguments['cases_with_execution_trace']} / {total}. "
                  "An absent trace is unobserved execution, not proof of zero calls."]
    episode = metrics.get("task_metrics", {}).get("bench.tool-episode")
    if episode is not None:
        total = episode["eligible_cases"]
        lines += ["", "## Synthetic tool episodes", "",
                  "Scripted policies receive actual fixture observations after each executed call. "
                  "This control does not qualify a model or product.", "",
                  f"Procedure correctness: {episode['procedure_correct_cases']} / {total}; "
                  f"task success: {episode['task_success_cases']} / {total} overall, "
                  f"{episode['task_success_cases']} / {episode['task_success_eligible_cases']} success-eligible cases.",
                  "", "| Stage | Correct / source-eligible cases |", "|---|---:|"]
        for stage in ("tool", "arguments", "binding", "execution", "result", "stopping", "budget"):
            lines.append(f"| {stage} | {episode[stage + '_correct_cases']} / {episode[stage + '_eligible_cases']} |")
        lines += ["", f"Observed policy invocations: {episode['policy_steps_observed']}; "
                  f"tool attempts: {episode['tool_call_attempts_observed']}; "
                  f"actual tool calls: {episode['tool_calls_observed']} "
                  f"({episode['tool_status_counts']['ok']} ok, "
                  f"{episode['tool_status_counts']['controlled_error']} controlled errors). "
                  f"Cases with validated retained traces: {episode['cases_with_execution_trace']} / {total}. "
                  "Missing or invalid traces leave execution unobserved; they do not establish zero calls."]
    lines += ["", "## Cas à examiner", ""]
    for row in metrics["rows"]:
        if not row["passed"]:
            # JSON records retain full explanations; escape Markdown delimiters here.
            case_id = row["case_id"].replace("`", "\\`").replace("\n", " ")
            lines.append(f"- `{case_id}` : {row['status']}; {row['reason']}")
    return "\n".join(lines) + "\n"


def _finish(output: Path, manifest: dict, cases: list[dict], records: list[dict],
            interrupted: bool = False) -> dict:
    metrics = summarize(cases, records)
    recorded_ids = {record["case_id"] for record in records}
    scored_ids = {row["case_id"] for row in metrics["rows"] if row["scored"]}
    coverage = [{**component,
                 "recorded_cases": len(recorded_ids & set(component["case_ids"])),
                 "scored_cases": len(scored_ids & set(component["case_ids"]))}
                for component in manifest["stack_context"]["components"]]
    summary = {"schema_version": "deposium.campaign-summary/v1", "run_id": manifest["run_id"],
               "archive_dir": str(output), "mode": manifest["mode"],
               "qualification": manifest["qualification"],
               "completion_status": "interrupted" if interrupted else (
                   "complete" if len(records) == len(cases) else "incomplete"),
               "scorer": manifest["scorer"], "metrics": metrics, "stack_coverage": coverage,
               "raw_sha256": _hash((output / "raw.jsonl").read_bytes())}
    _write_new(output / "summary.json", _encode(summary))
    _write_new(output / "report.md", render_report(summary).encode("utf-8"))
    files = {file.name: _hash(file.read_bytes()) for file in sorted(output.iterdir()) if file.is_file()}
    seal = {"schema_version": "deposium.archive-seal/v1", "files": files,
            "sha256": _hash(_encode(files))}
    _write_new(output / "seal.json", _encode(seal))
    return summary


def run_campaign(dataset_path: str | Path, profile_path: str | Path, output_dir: str | Path,
                 *, stack_root: str | Path | None = None, max_new_cases: int | None = None,
                 stop_requested: Callable[[], bool] | None = None) -> dict:
    _limit(max_new_cases)
    if stop_requested is not None and not callable(stop_requested):
        raise CampaignError("stop_requested must be a callable or None.")
    cases, dataset_hash = load_cases(dataset_path)
    dataset = Path(dataset_path).read_bytes()
    if _hash(dataset) != dataset_hash:
        raise CampaignError("Dataset changed while preparing the campaign.")
    path = Path(profile_path).resolve()
    profile, source_hash, recordings = _prepare_profile(path)
    original, original_hash = load_profile(path)
    if original_hash != source_hash:
        raise CampaignError("Profile changed while preparing the campaign.")
    _validate_output_scope(cases, profile)
    context, preflight = _stack_context(cases, profile, stack_root)
    output = _destination(output_dir, stack_root)
    adapter = create_adapter(original, path, stack_root=stack_root, recordings_data=recordings)
    try:
        manifest = _manifest(cases, dataset, profile, source_hash, adapter.provenance,
                             "run", None, stack_root, context)
        _create_archive(output, manifest, dataset, profile, recordings, preflight)
        records, interrupted = _execute(output, cases, adapter, [], max_new_cases=max_new_cases,
                                        stop_requested=stop_requested)
        # The manifest holds the adapter's provenance at start; an adapter may add
        # execution-time facts (worker restarts, relaunch timings, availability
        # changes). Persist the final view inside the sealed archive.
        _write_new(output / "adapter-final.json", _encode(getattr(adapter, "provenance", {})))
        return _finish(output, manifest, cases, records, interrupted)
    finally:
        _close_adapter(adapter)


def _archive(archive_dir: str | Path) -> tuple[Path, dict, list[dict], list[dict], dict, dict[str, bytes]]:
    root = Path(archive_dir).resolve()
    payloads = {}
    names = ("manifest.json", "cases.jsonl", "profile.json", "raw.jsonl", "recordings.jsonl",
             "stack-preflight.json", "adapter-final.json", "summary.json", "report.md", "seal.json")
    for name in names:
        path = root / name
        if path.is_symlink():
            raise CampaignError("Archive files must not be symbolic links.")
        if path.exists():
            payloads[name] = path.read_bytes()
    required = {"manifest.json", "cases.jsonl", "profile.json", "raw.jsonl"}
    if not required <= set(payloads):
        raise CampaignError("Archive is missing an input or its raw trace.")
    manifest = _decode(payloads["manifest.json"])
    if manifest.get("schema_version") != CAMPAIGN_VERSION:
        raise CampaignError("Unsupported campaign manifest version.")
    sealed = "seal.json" in payloads
    if not sealed and any(name in payloads for name in ("summary.json", "report.md")):
        raise CampaignError("Finished archive is missing its seal.")
    if sealed:
        seal = _decode(payloads["seal.json"])
        if seal.get("schema_version") != "deposium.archive-seal/v1" or not isinstance(seal.get("files"), dict):
            raise CampaignError("Invalid archive seal.")
        if seal.get("sha256") != _hash(_encode(seal["files"])):
            raise CampaignError("Archive seal fingerprint mismatch.")
        if not {"manifest.json", "cases.jsonl", "profile.json", "raw.jsonl", "summary.json", "report.md"} <= set(seal["files"]):
            raise CampaignError("Archive seal omits required files.")
        for name, digest in seal["files"].items():
            if Path(name).name != name or name in {".", ".."}:
                raise CampaignError("Invalid sealed archive path.")
            if name not in payloads or _hash(payloads[name]) != digest:
                raise CampaignError("Sealed archive was modified or a file is missing.")
    cases, digest = parse_cases(payloads["cases.jsonl"])
    if (digest != manifest.get("dataset_sha256") or [c["case_id"] for c in cases] != manifest.get("case_ids")
            or type(manifest.get("case_count")) is not int or manifest["case_count"] != len(cases)):
        raise CampaignError("Archived dataset differs from its manifest.")
    profile, profile_hash = parse_profile(payloads["profile.json"])
    if profile_hash != manifest.get("profile_sha256"):
        raise CampaignError("Archived candidate profile differs from its manifest.")
    if profile["adapter"] in {"recorded", "fixture_arguments", "fixture_episode"}:
        if (profile["recordings"] != "recordings.jsonl" or "recordings.jsonl" not in payloads or
                _hash(payloads["recordings.jsonl"]) !=
                manifest.get("adapter_provenance", {}).get("recordings_sha256")):
            raise CampaignError("Archived recordings differ from the executed snapshot.")
        if sealed and "recordings.jsonl" not in seal["files"]:
            raise CampaignError("Archive seal omits recordings.")
    context = manifest.get("stack_context")
    if not isinstance(context, dict) or not isinstance(context.get("components"), list):
        raise CampaignError("Archive has no stack coverage context.")
    if context.get("preflight_sha256") is not None:
        if ("stack-preflight.json" not in payloads or
                _hash(payloads["stack-preflight.json"]) != context["preflight_sha256"]):
            raise CampaignError("Archived stack observation differs from its manifest.")
        if sealed and "stack-preflight.json" not in seal["files"]:
            raise CampaignError("Archive seal omits the stack observation.")
    data = payloads["raw.jsonl"]
    if data and not data.endswith(b"\n"):
        raise CampaignError("Raw trace has an incomplete last record; original archive preserved.")
    case_map = {case["case_id"]: case for case in cases}
    records = []
    seen = set()
    for line in data.splitlines():
        record = _decode(line)
        fields = {"schema_version", "case_id", "contract_id", "request_sha256", "status",
                  "output", "raw_output", "error", "duration_ms"}
        if (set(record) != fields or not isinstance(record.get("case_id"), str)
                or record["case_id"] not in case_map or record["case_id"] in seen):
            raise CampaignError("Unknown or duplicate case in raw trace.")
        case = case_map[record["case_id"]]
        if (record.get("schema_version") != RESULT_VERSION or not isinstance(record.get("status"), str)
                or record["status"] not in STATUSES
                or record.get("contract_id") != case["contract_id"]
                or record.get("request_sha256") != _hash(_encode(candidate_request(case)))
                or (record["error"] is not None and not isinstance(record["error"], str))):
            raise CampaignError("Raw trace contract or input fingerprint mismatch.")
        duration = record.get("duration_ms")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
            raise CampaignError("Invalid recorded duration.")
        if profile["adapter"] == "llama_cpp_json" and case["contract_id"] in profile["capabilities"]:
            from .local_tool_policy import validate_trace, settings_for
            try:
                validate_trace(case, record, settings_for(profile["model"]))
            except (ValueError, KeyError, TypeError) as exc:
                raise CampaignError("Archived generated proposal trace is inconsistent.") from exc
        seen.add(record["case_id"])
        records.append(record)
    parent = {"archive_dir": str(root), "run_id": manifest["run_id"],
              "manifest_sha256": _hash(payloads["manifest.json"]),
              "raw_sha256": _hash(data), "sealed": sealed}
    return root, manifest, cases, records, parent, payloads


def resume_campaign(archive_dir: str | Path, output_dir: str | Path, *,
                    stack_root: str | Path | None = None, max_new_cases: int | None = None) -> dict:
    _limit(max_new_cases)
    root, previous, cases, records, parent, payloads = _archive(archive_dir)
    effective_stack = stack_root if stack_root is not None else previous["stack_root"]
    profile, _ = parse_profile(payloads["profile.json"])
    _validate_output_scope(cases, profile)
    recordings = payloads.get("recordings.jsonl")
    context, preflight = _stack_context(cases, profile, effective_stack)
    adapter = create_adapter(profile, root / "profile.json", stack_root=effective_stack, recordings_data=recordings)
    try:
        old_identity = previous["adapter_provenance"].get("identity_sha256")
        if not old_identity or adapter.provenance.get("identity_sha256") != old_identity:
            raise CampaignError("Adapter/runtime provenance changed; start a separate campaign.")
        dataset = payloads["cases.jsonl"]
        manifest = _manifest(cases, dataset, profile, previous["source_profile_sha256"],
                             adapter.provenance, "resume", parent, effective_stack, context)
        output = _destination(output_dir, effective_stack, root)
        _create_archive(output, manifest, dataset, profile, recordings, preflight)
        current, interrupted = _execute(output, cases, adapter, records, max_new_cases=max_new_cases)
        return _finish(output, manifest, cases, current, interrupted)
    finally:
        _close_adapter(adapter)


def rescore_campaign(archive_dir: str | Path, output_dir: str | Path) -> dict:
    """Score archived outputs only; adapter creation and inference are forbidden."""
    root, previous, cases, records, parent, payloads = _archive(archive_dir)
    profile, _ = parse_profile(payloads["profile.json"])
    recordings = payloads.get("recordings.jsonl")
    dataset = payloads["cases.jsonl"]
    preflight = payloads.get("stack-preflight.json")
    manifest = _manifest(cases, dataset, profile, previous["source_profile_sha256"],
                         previous["adapter_provenance"], "rescore", parent, previous["stack_root"], previous["stack_context"])
    output = _destination(output_dir, previous["stack_root"], root)
    _create_archive(output, manifest, dataset, profile, recordings, preflight)
    _write_new(output / "raw.jsonl", payloads["raw.jsonl"])
    return _finish(output, manifest, cases, records)
