"""Closed-choice step policy for bounded tool episodes.

At every step the harness enumerates the legal-looking next actions from the
candidate-visible projection alone, renders them as a `bench.context-choice`
input, and lets a choice adapter (a classifier such as D3 or Vela) pick one.
The chosen proposal is then executed by the ordinary episode runtime, whose
actual observation feeds the next step. The model never writes an action: this
measures step selection over a fixed menu, not free-form tool generation.

Everything the menu contains is derived from the projection, so a pure rescore
re-derives every menu and rendered input and verifies the retained trace.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

from .cases import CaseError, typed_equal
from .choice_protocol import validate_choice_input
from .synthetic_tools import canonical
from .tool_episodes import CONTRACT, PROJECTION_VERSION, run_episode

TRACE_VERSION = "deposium.choice-episode-trace/v1"
MENU_VERSION = "deposium.choice-episode-menu/v1"
CHOICE_CONTRACT = "bench.context-choice"
SOURCES = ("adapters.py", "synthetic_tools.py", "tool_episodes.py", "choice_episodes.py", "choice_protocol.py")
# Terminal proposals offered at every step, in this fixed order. Success is only
# offered once an actual sum receipt exists, so a premature success claim cannot
# be chosen; the generative contract keeps that failure mode, this mode removes it.
FINISHES = (("clarify", "missing_information"), ("clarify", "partial_data"), ("stop", "no_data"),
            ("stop", "unavailable"), ("stop", "persistent_error"))
_FINISH_TEXT = {
    "missing_information": "Terminer : demander une précision, l'identifiant du tableau manque / Finish: ask for clarification, the table identifier is missing",
    "partial_data": "Terminer : demander une précision, les données consultées sont partielles / Finish: ask for clarification, the retrieved data is partial",
    "no_data": "Terminer : s'arrêter sans résultat, le tableau consulté est vide / Finish: stop without a result, the retrieved table is empty",
    "unavailable": "Terminer : s'arrêter sans résultat, l'outil de somme est devenu indisponible / Finish: stop without a result, the sum tool became unavailable",
    "persistent_error": "Terminer : s'arrêter sans résultat, les consultations autorisées ont toutes échoué / Finish: stop without a result, every permitted lookup failed",
}


def _yes(value):
    return "oui / yes" if value else "non / no"


def _observations(projection):
    artifact = result = None
    for receipt in projection["observations"]:
        if receipt["status"] != "ok":
            continue
        if receipt["tool_id"] == "fixture.lookup":
            artifact, result = receipt["artifact"], None
        elif receipt["tool_id"] == "fixture.sum":
            result = receipt
    return artifact, result


def menu(projection):
    """Candidate next actions, from the projection only; no hidden fault or reference is read."""
    if not isinstance(projection, dict) or projection.get("schema_version") != PROJECTION_VERSION:
        raise CaseError("choice-episode: invalid projection")
    known, scope = projection["known_parameters"], projection["scope_id"]
    artifact, result = _observations(projection)
    items = []
    if known["dataset_id"] is not None:
        items.append({"id": "call-lookup",
                      "description": f"Appeler fixture.lookup sur le tableau {known['dataset_id']} dans le périmètre {scope} / Call fixture.lookup on table {known['dataset_id']} within scope {scope}",
                      "action": {"action": "call", "tool_id": "fixture.lookup",
                                 "arguments": {"dataset_id": known["dataset_id"], "scope_id": scope}}})
    if artifact is not None:
        items.append({"id": "call-sum",
                      "description": f"Appeler fixture.sum sur l'artefact {artifact['artifact_id'][:16]}… (colonne {known['column']}, unité {known['unit']}) / Call fixture.sum on artifact {artifact['artifact_id'][:16]}… (column {known['column']}, unit {known['unit']})",
                      "action": {"action": "call", "tool_id": "fixture.sum",
                                 "arguments": {"artifact_id": artifact["artifact_id"], "column": known["column"],
                                               "unit": known["unit"], "scope_id": scope}}})
    if result is not None:
        items.append({"id": "finish-success",
                      "description": f"Terminer : annoncer le total réel {result['value']} {result['unit']} renvoyé par fixture.sum / Finish: report the actual total {result['value']} {result['unit']} returned by fixture.sum",
                      "action": {"action": "finish", "decision": "success", "reason": "complete",
                                 "value": result["value"], "unit": result["unit"]}})
    for decision, reason in FINISHES:
        items.append({"id": "finish-" + reason, "description": _FINISH_TEXT[reason],
                      "action": {"action": "finish", "decision": decision, "reason": reason, "value": None, "unit": None}})
    return items


def render(projection, items):
    """Bilingual text projection of the episode state plus the menu as choice options."""
    known = projection["known_parameters"]
    lines = ["Épisode d'outils synthétiques borné / Bounded synthetic tool episode.",
             "Demande / Request: " + projection["request"],
             "Périmètre autorisé / Permitted scope: " + projection["scope_id"],
             "Paramètres connus / Known parameters: identifiant du tableau / dataset id = "
             + ("absent / missing" if known["dataset_id"] is None else known["dataset_id"])
             + f"; colonne / column = {known['column']}; unité / unit = {known['unit']}",
             "Outils / Tools:"]
    for tool in projection["tools"]:
        lines.append(f"- {tool['tool_id']}: disponible / available = {_yes(tool['available'])}; "
                     f"éligible maintenant / eligible now = {_yes(tool['eligible'])}; arguments: {', '.join(tool['arguments'])}")
    observations = projection["observations"]
    lines.append(f"Observations réelles / Actual observations ({len(observations)}):")
    if not observations:
        lines.append("- aucune / none")
    for number, receipt in enumerate(observations, 1):
        after = receipt.get("availability", {})
        if receipt["status"] != "ok":
            lines.append(f"{number}. {receipt['tool_id']} → erreur contrôlée / controlled error: {receipt['error']}; "
                         f"fixture.sum disponible ensuite / available afterwards = {_yes(after.get('fixture.sum', True))}")
        elif receipt["tool_id"] == "fixture.lookup":
            artifact = receipt["artifact"]
            lines.append(f"{number}. fixture.lookup → ok; artefact / artifact {artifact['artifact_id'][:16]}…; "
                         f"complet / complete = {_yes(artifact['complete'])}; {len(artifact['values'])} valeurs / values; "
                         f"fixture.sum disponible ensuite / available afterwards = {_yes(after.get('fixture.sum', True))}")
        else:
            lines.append(f"{number}. fixture.sum → ok; total / total = {receipt['value']} {receipt['unit']}")
    history = projection["history"]
    lines.append(f"Propositions précédentes / Previous proposals ({len(history)}):")
    if not history:
        lines.append("- aucune / none")
    for number, entry in enumerate(history, 1):
        proposal = entry["proposal"]
        label = (proposal.get("tool_id") if isinstance(proposal, dict) and proposal.get("action") == "call"
                 else f"finish {proposal.get('decision')}/{proposal.get('reason')}" if isinstance(proposal, dict) else "invalid")
        lines.append(f"{number}. {label} → {entry['guard']['code']}")
    budget = projection["remaining_budget"]
    lines.append("Budget restant / Remaining budget: "
                 f"étapes / steps = {budget['policy_steps']}; appels d'outil / tool calls = {budget['tool_calls']}; "
                 f"consultations / lookups = {budget['lookup_attempts']}; temps / time = {int(budget['elapsed_ms'])} ms")
    value = {"context": "\n".join(lines),
             "question": "Quelle est la prochaine action correcte de ce workflow ? / What is the correct next action of this workflow?",
             "options": [{"id": item["id"], "description": item["description"]} for item in items]}
    validate_choice_input(value)
    return value


def _sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class ChoiceStepPolicy:
    """Called by run_episode after each actual observation; delegates the pick to a choice adapter."""
    def __init__(self, inner, case_id):
        self.inner, self.case_id, self.steps = inner, case_id, []

    def predict(self, projected):
        from .adapters import _envelope, _normalize_envelope
        items = menu(projected)
        value = render(projected, items)
        response = _normalize_envelope(self.inner.predict({"case_id": self.case_id, "contract_id": CHOICE_CONTRACT, "input": value}))
        self.steps.append({"index": len(self.steps) + 1, "choice_input": value, "choice_input_sha256": _sha(value),
                           "menu": deepcopy(items), "response": deepcopy(response)})
        return _resolve(response, items)


def _resolve(response, items):
    from .adapters import _envelope
    if response["status"] != "ok":
        return _envelope(response["status"], error=response["error"])
    output = response["output"]
    chosen = output.get("choice_id") if isinstance(output, dict) else None
    for item in items:
        if item["id"] == chosen:
            return _envelope("ok", output=deepcopy(item["action"]))
    return _envelope("error", error="choice_episode_unknown_choice")


def validate_trace(case, result):
    """Pure check: every menu and rendered input re-derives from the retained projection."""
    from .tool_episodes import validate_receipt
    raw = result.get("raw_output")
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "inner_identity_sha256", "steps", "episode"}:
        raise CaseError("choice-episode: trace required")
    if raw["schema_version"] != TRACE_VERSION or not isinstance(raw["inner_identity_sha256"], str):
        raise CaseError("choice-episode: invalid trace version")
    output = result.get("output") if result.get("status") == "ok" else raw["episode"]
    if result.get("status") == "ok" and raw["episode"] is not None:
        raise CaseError("choice-episode: duplicate episode output")
    validate_receipt(case["input"], output)
    steps = output["steps"]
    if not isinstance(raw["steps"], list) or len(raw["steps"]) != len(steps):
        raise CaseError("choice-episode: trace step count mismatch")
    for index, (trace, step) in enumerate(zip(raw["steps"], steps)):
        if not isinstance(trace, dict) or set(trace) != {"index", "choice_input", "choice_input_sha256", "menu", "response"}:
            raise CaseError("choice-episode: invalid trace step")
        items = menu(step["candidate_input"])
        value = render(step["candidate_input"], items)
        if (trace["index"] != index + 1 or not typed_equal(trace["menu"], items)
                or not typed_equal(trace["choice_input"], value) or trace["choice_input_sha256"] != _sha(value)):
            raise CaseError("choice-episode: menu or rendered input mismatch")
        response = trace["response"]
        if not isinstance(response, dict) or set(response) != {"status", "output", "raw_output", "error"}:
            raise CaseError("choice-episode: invalid retained response")
        expected = _resolve(response, items)
        if step["policy_status"] != expected["status"] or not typed_equal(step["proposal"], expected["output"]):
            raise CaseError("choice-episode: proposal does not follow the retained choice")


def validate_model_profile(profile):
    from .adapters import AdapterError
    model = profile.get("model")
    if (not isinstance(model, dict) or set(model) != {"inner_profile"} or not isinstance(model["inner_profile"], str)
            or not model["inner_profile"].strip() or model["inner_profile"].endswith("/")):
        raise AdapterError("choice_episode requires model.inner_profile naming a context-choice profile.")
    if profile["capabilities"] != [CONTRACT] or profile["recordings"] is not None:
        raise AdapterError("choice_episode drives bench.tool-episode only and records nothing itself.")
    revision = profile["revision"]
    if profile["qualification"] == "model_isolated":
        import re
        if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
            raise AdapterError("choice_episode model profiles pin the inner model revision.")
    elif profile["qualification"] != "harness_control" or revision is not None:
        raise AdapterError("choice_episode is model_isolated with a revision or harness_control without one.")
    if profile["timeout_seconds"] < 1:
        raise AdapterError("choice_episode profiles require at least the bounded one-second envelope.")


class ChoiceEpisodeAdapter:
    def __init__(self, profile, profile_path, inner=None):
        from .adapters import AdapterError, _base_provenance, _identity, create_adapter, load_profile
        validate_model_profile(profile)
        path = Path(profile_path).resolve()
        inner_path = (path.parent / profile["model"]["inner_profile"]).resolve()
        inner_profile, inner_hash = load_profile(inner_path)
        if (CHOICE_CONTRACT not in inner_profile["capabilities"]
                or inner_profile["adapter"] in {"fixture_episode", "fixture_arguments", "llama_cpp_json", "choice_episode"}):
            raise AdapterError("choice_episode needs an inner bench.context-choice adapter.")
        if inner_profile["revision"] != profile["revision"] or inner_profile["qualification"] != profile["qualification"]:
            raise AdapterError("choice_episode must mirror the inner profile revision and qualification.")
        if profile["timeout_seconds"] < inner_profile["timeout_seconds"]:
            raise AdapterError("choice_episode timeout cannot undercut the inner per-call timeout.")
        self.inner = create_adapter(inner_profile, inner_path) if inner is None else inner
        self.capabilities = [CONTRACT]
        base, identity = _base_provenance(profile, path)
        sources = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest() for name in SOURCES}
        inner_identity = self.inner.provenance.get("identity_sha256")
        self.provenance = {**base, "adapter": "choice_episode", "policy_mode": "closed_choice_step_menu_v1",
                           "inner_profile_sha256": inner_hash, "inner": deepcopy(self.inner.provenance),
                           "runtime_sources": sources, "available": bool(self.inner.provenance.get("available", True)),
                           "adapter_sha256": _identity(sources),
                           "identity_sha256": _identity({**identity, "inner_identity_sha256": inner_identity,
                                                         "inner_profile_sha256": inner_hash, "runtime_sources": sources})}

    def predict(self, request):
        from .adapters import _envelope, _request
        request = _request(request)
        if request["contract_id"] != CONTRACT:
            return _envelope("unsupported", error="unsupported_contract")
        policy = ChoiceStepPolicy(self.inner, request["case_id"])
        status, error, output = run_episode(request["input"], policy)
        self.provenance["inner"] = deepcopy(self.inner.provenance)
        self.provenance["available"] = bool(self.inner.provenance.get("available", True))
        trace = {"schema_version": TRACE_VERSION, "inner_identity_sha256": self.inner.provenance.get("identity_sha256"),
                 "steps": policy.steps, "episode": None if status == "ok" else output}
        if status != "ok":
            return _envelope(status, raw_output=trace, error=error)
        return _envelope("ok", output=output, raw_output=trace)

    def close(self):
        close = getattr(self.inner, "close", None)
        if callable(close):
            close()
