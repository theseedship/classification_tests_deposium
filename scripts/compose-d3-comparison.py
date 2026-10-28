#!/usr/bin/env python3
"""Compose a 17–19-model Markdown comparison from sealed-analysis aggregates.

This is an offline presentation step. It does not inspect raw archives, rescore
cases, load candidates, or certify the historical Sol archives. The caller must
first verify the new aggregate against its sealed campaign archives.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

SCHEMA = "deposium.model-comparison-analysis/v1"
REFERENCE = "agent_only_pending_human"
BASE_DATASET_SHA = "767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616"
MASTRA_DATASET_SHA = "d66ec51d9b8d89f46b87b90b80bcd0d45abf1570fa9857c24d9ce39117935497"
BASE_SCORER_SHA = "d10a8b962ae2722c83218771fdffb4e16925d263fcca7d780cd14d4cab5a7084"
SOL_EXPORT_SHA = "6659ab61c392c0123eb46350595181ba5f2e6530b59713a21847f755ea4fe97c"
VELA_EXPORT_SHA = "53054c718cae191d117eb0afe7e84a2657ef9f73a1b922ab34a27d6801dd7c07"
D3_EXPORT_SHA = "971feed2559030d565320729f05331cbc8ddc0bec3e4e25992e09b17a256fe54"
OLD_LABELS = {"Jev", "Noma", "Vela08", "Eos", "Kai", "Vela03", "GLiNER",
              "Laya", "Julia", "Omni", "Indecis", "ModernJEV", "Muose"}
FROZEN_D3_LABELS = OLD_LABELS | {"D3edge", "D3lite", "D3nano"}
CURRENT_LABEL_SETS = (FROZEN_D3_LABELS, FROZEN_D3_LABELS | {"D3mini"},
                      FROZEN_D3_LABELS | {"D3mini", "D3flash"})
D3_MODELS = {
    "d3edge": ("vllm-sr/d3-edge", "18d61df78684675463af9ae732872478845c5a79"),
    "d3lite": ("vllm-sr/d3-lite", "a8d25a91ef75552803f7009d25b7bd435991abd9"),
    "d3nano": ("vllm-sr/d3-nano", "3aeb1c22a5632aac72353c36b3d0111c40e7dbf4"),
    "d3mini": ("vllm-sr/d3-mini", "a475367de0d8133a3c1a2a0dc12303d89cfa2ab4"),
    "d3flash": ("vllm-sr/d3-flash", "521525effa79469d899a570726547dd7f00da3af"),
}
BASE_GROUPS = {
    "domain": {"documentary": 76, "mathematics": 28, "chemistry": 28},
    "language": {"fr": 66, "en": 66},
    "difficulty": {"D1": 40, "D2": 40, "D3": 52},
    "split": {"train": 36, "calibration": 30, "test": 66},
}
MASTRA_GROUPS = {
    "by_language": {"fr": 12, "en": 12},
    "by_split": {"calibration": 6, "test": 18},
    "by_proposed_action": {"search": 8, "stats": 8, "fallback": 8},
}
HASH = re.compile(r"[0-9a-f]{64}\Z")


class CompositionError(ValueError):
    """An aggregate cannot safely be combined with the historical export."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CompositionError(reason)


def _integer(value: object, *, low: int = 0) -> bool:
    return type(value) is int and value >= low


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(path: Path, decode) -> tuple[dict, str]:
    _require(path.is_file() and not path.is_symlink(), "JSON source missing or symlinked")
    raw = path.read_bytes()
    _require(0 < len(raw) <= 32 * 1024 * 1024, "JSON source size invalid")
    data = decode(raw)
    _require(isinstance(data, dict), "aggregate must be an object")
    return data, _sha(raw)


def _count(value: dict, *, total: int, field: str, qualified: str | None = None) -> None:
    _require(isinstance(value, dict) and value.get("total") == total,
             f"{field}: unexpected denominator")
    if qualified is None:
        scored, correct = value.get("scored"), value.get("correct")
        _require(_integer(scored) and scored <= total and _integer(correct) and correct <= scored,
                 f"{field}: invalid scored or correct count")
        statuses = value.get("statuses")
        _require(isinstance(statuses, dict) and
                 set(statuses) == {"ok", "unsupported", "missing", "error", "timeout", "abstain"}
                 and all(_integer(number) for number in statuses.values())
                 and sum(statuses.values()) == total,
                 f"{field}: invalid status coverage")
    else:
        valid, agreement = value.get("valid_decisions"), value.get("agreement_count")
        _require(_integer(valid) and valid <= total and _integer(agreement) and agreement <= valid,
                 f"{field}: invalid valid or agreement count")


def _source(source: object, *, mastra: bool) -> None:
    _require(isinstance(source, dict), "source provenance missing")
    keys = ("dataset_sha256", "manifest_sha256", "raw_sha256", "seal_sha256")
    _require(all(isinstance(source.get(key), str) and HASH.fullmatch(source[key]) for key in keys),
             "source hashes invalid")
    if mastra:
        _require(source.get("projection_version") == "mastra-read-choice/v1",
                 "Mastra projection mismatch")
        _require(isinstance(source.get("requests_sha256"), str) and HASH.fullmatch(source["requests_sha256"]),
                 "Mastra request hash invalid")
    else:
        _require(isinstance(source.get("scorer_sha256"), str) and HASH.fullmatch(source["scorer_sha256"]),
                 "base scorer hash invalid")


def _stats(value: object, *, total: int, field: str, unreported: bool) -> None:
    _require(isinstance(value, dict) and _integer(value.get("count")) and value["count"] <= total,
             f"{field}: statistic count invalid")
    if unreported:
        _require(_integer(value.get("unreported_calls")) and
                 value["count"] + value["unreported_calls"] == total,
                 f"{field}: statistic coverage invalid")
    if value["count"]:
        ordered = [value.get(key) for key in ("min", "median", "p95", "max")]
        _require(all(type(number) in (int, float) and math.isfinite(number) and number >= 0
                     for number in ordered) and ordered == sorted(ordered),
                 f"{field}: statistic distribution invalid")
    else:
        _require(all(value.get(key) is None for key in ("min", "median", "p95", "max")),
                 f"{field}: empty statistic distribution invalid")


def _validate(data: dict, *, historical: bool = False, baseline: bool = False) -> None:
    _require(data.get("schema_version") == SCHEMA and data.get("scope") == "isolated_model_observations"
             and data.get("base_reference_review") == REFERENCE
             and data.get("base_rank_order") == "correct_over_all_132_descending",
             "aggregate protocol or reference review mismatch")
    base, mastra = data.get("base"), data.get("mastra")
    _require(isinstance(base, dict) and isinstance(mastra, dict) and set(base) == set(mastra),
             "base/Mastra model membership mismatch")
    _require(not (historical and baseline), "aggregate role invalid")
    wanted = (OLD_LABELS - {"Vela03", "Vela08"}) | {"Sol"} if historical else None
    if historical:
        _require(set(base) == wanted, "historical Sol export model membership changed")
    elif baseline:
        _require(set(base) == OLD_LABELS, "Vela export model membership changed")
    else:
        _require(set(base) in CURRENT_LABEL_SETS,
                 "new aggregate must contain frozen D3 models, then D3mini, then D3flash, without Sol")
        new = set(base) - OLD_LABELS
        for label in new:
            identity = base[label].get("identity") if isinstance(base[label], dict) else None
            settings = identity.get("settings") if isinstance(identity, dict) else None
            repo, revision = D3_MODELS[re.sub(r"[-_]", "", label).lower()]
            _require(isinstance(settings, dict) and isinstance(identity, dict)
                     and identity.get("adapter") == "d3"
                     and identity.get("model_repo_id") == repo
                     and identity.get("model_revision") == revision
                     and settings.get("device") == "cpu"
                     and settings.get("backbone_dtype") == "bfloat16"
                     and settings.get("readout_dtype") == "float32",
                     f"{label}: reviewed D3 model identity or CPU precision not evidenced")
    producer = data.get("producer_files_sha256")
    _require(isinstance(producer, dict) and producer and
             all(isinstance(name, str) and isinstance(digest, str) and HASH.fullmatch(digest)
                 for name, digest in producer.items()), "producer provenance invalid")
    dataset_base, dataset_mastra, scorer, request_hash = set(), set(), set(), set()
    for label, item in base.items():
        _require(isinstance(item, dict) and item.get("qualification") == "model_isolated",
                 f"{label}: base qualification invalid")
        _count(item.get("counts"), total=132, field=f"{label} base")
        _require(item["counts"].get("translation_families") == 66,
                 f"{label}: base family denominator invalid")
        groups = item.get("groups")
        _require(isinstance(groups, dict), f"{label}: base groups missing")
        for axis, expected in BASE_GROUPS.items():
            values = groups.get(axis)
            _require(isinstance(values, dict) and set(values) == set(expected),
                     f"{label}: {axis} groups mismatch")
            for group, total in expected.items():
                _count(values[group], total=total, field=f"{label} {axis}/{group}")
            _require(sum(values[group]["correct"] for group in expected) == item["counts"]["correct"]
                     and sum(values[group]["scored"] for group in expected) == item["counts"]["scored"],
                     f"{label}: {axis} counts disagree with base")
        _source(item.get("source"), mastra=False)
        _require(isinstance(item["source"].get("seal_fingerprint"), str) and
                 HASH.fullmatch(item["source"]["seal_fingerprint"]),
                 f"{label}: base seal fingerprint invalid")
        dataset_base.add(item["source"]["dataset_sha256"])
        scorer.add(item["source"]["scorer_sha256"])
        identity = item.get("identity")
        _require(isinstance(identity, dict) and identity.get("identity_sha256") and
                 identity.get("adapter") and identity.get("profile_id"),
                 f"{label}: base identity missing")
        _stats(item.get("timing", {}).get("successful_adapter_ms"), total=132,
               field=f"{label} base adapter timing", unreported=False)
        _stats(item.get("worker_rss_mib"), total=132,
               field=f"{label} base worker RSS", unreported=True)
        _stats(item.get("measurements", {}).get("native_tokens", {}).get("max_sequence_tokens"),
               total=132, field=f"{label} base native tokens", unreported=True)
        route = mastra[label]
        _require(isinstance(route, dict) and route.get("qualification") ==
                 "provisional_agreement_pending_human_review"
                 and route.get("reference_review") == "pending_human"
                 and route.get("cases_scored") == 0,
                 f"{label}: Mastra qualification invalid")
        _count(route.get("coverage"), total=24, field=f"{label} Mastra", qualified="agreement")
        for axis, expected in MASTRA_GROUPS.items():
            values = route.get(axis)
            _require(isinstance(values, dict) and set(values) == set(expected),
                     f"{label}: Mastra {axis} groups mismatch")
            for group, total in expected.items():
                _count(values[group], total=total, field=f"{label} Mastra {axis}/{group}",
                       qualified="agreement")
            _require(sum(values[group]["agreement_count"] for group in expected) ==
                     route["coverage"]["agreement_count"],
                     f"{label}: Mastra {axis} counts disagree")
        _source(route.get("source"), mastra=True)
        _require(isinstance(route["source"].get("seal_fingerprint"), str) and
                 HASH.fullmatch(route["source"]["seal_fingerprint"]),
                 f"{label}: Mastra seal fingerprint invalid")
        dataset_mastra.add(route["source"]["dataset_sha256"])
        request_hash.add(route["source"]["requests_sha256"])
        route_identity = route.get("identity")
        _require(isinstance(route_identity, dict) and
                 all(route_identity.get(key) == identity.get(key) for key in
                     ("adapter", "profile_id", "model_repo_id", "model_id", "model_revision",
                      "model_assets_sha256")),
                 f"{label}: base/Mastra model identity mismatch")
        _stats(route.get("timing", {}).get("successful_adapter_ms"), total=24,
               field=f"{label} Mastra adapter timing", unreported=False)
        _stats(route.get("worker_rss_mib"), total=24,
               field=f"{label} Mastra worker RSS", unreported=True)
        _stats(route.get("measurements", {}).get("native_tokens", {}).get("max_sequence_tokens"),
               total=24, field=f"{label} Mastra native tokens", unreported=True)
    _require(len(dataset_base) == len(dataset_mastra) == len(scorer) == len(request_hash) == 1,
             "within-aggregate corpus, scorer, or projection mismatch")
    _require(dataset_base == {BASE_DATASET_SHA} and dataset_mastra == {MASTRA_DATASET_SHA}
             and scorer == {BASE_SCORER_SHA}, "frozen corpus or scorer mismatch")
    _require(len({item["source"]["seal_sha256"] for item in base.values()}) == len(base)
             and len({item["source"]["seal_sha256"] for item in mastra.values()}) == len(mastra),
             "duplicate archive seal among model labels")
    ranking = data.get("base_ranking")
    _require(ranking == sorted(base, key=lambda name: (-base[name]["counts"]["correct"], name)),
             "aggregate base ranking invalid")


def compose(current: dict, old: dict, vela: dict,
            d3: dict | None = None) -> tuple[dict, dict]:
    """Validate composition; return base and Mastra mappings, including Sol."""
    _validate(current)
    _validate(old, historical=True)
    _validate(vela, baseline=True)
    has_larger_d3 = set(current["base"]) != FROZEN_D3_LABELS
    _require(not has_larger_d3 or d3 is not None,
             "historical D3 JSON required for D3mini or D3flash")
    if d3 is not None:
        _validate(d3)
        _require(set(d3["base"]) == FROZEN_D3_LABELS,
                 "historical D3 export model membership changed")
        for label in FROZEN_D3_LABELS:
            _require(current["base"][label] == d3["base"][label] and
                     current["mastra"][label] == d3["mastra"][label],
                     f"{label}: frozen D3 aggregate metrics changed")
    old_base, old_mastra = old["base"], old["mastra"]
    new_base, new_mastra = current["base"], current["mastra"]
    for label in OLD_LABELS:
        _require(new_base[label] == vela["base"][label] and
                 new_mastra[label] == vela["mastra"][label],
                 f"{label}: Vela historical aggregate metrics changed")
    shared = set(old_base) & set(new_base)
    _require(len(shared) == 11, "unexpected historical overlap")
    for label in shared:
        _require(old_base[label] == new_base[label] and old_mastra[label] == new_mastra[label],
                 f"{label}: historical aggregate metrics changed")
    new_base_sources = {item["source"]["dataset_sha256"] for item in new_base.values()}
    old_base_sources = {item["source"]["dataset_sha256"] for item in old_base.values()}
    new_mastra_sources = {item["source"]["dataset_sha256"] for item in new_mastra.values()}
    old_mastra_sources = {item["source"]["dataset_sha256"] for item in old_mastra.values()}
    _require(new_base_sources == old_base_sources and new_mastra_sources == old_mastra_sources,
             "base or Mastra corpus differs from historical Sol")
    _require({item["source"]["scorer_sha256"] for item in new_base.values()} ==
             {item["source"]["scorer_sha256"] for item in old_base.values()},
             "base scorer differs from historical Sol")
    _require({item["source"]["requests_sha256"] for item in new_mastra.values()} ==
             {item["source"]["requests_sha256"] for item in old_mastra.values()},
             "Mastra candidate projection differs from historical Sol")
    return {**new_base, "Sol": old_base["Sol"]}, {**new_mastra, "Sol": old_mastra["Sol"]}


def ranked(models: dict, score) -> list[tuple[int, str, bool]]:
    """Competition ranks: a tie at first place yields 1, 1, 3."""
    names = sorted(models, key=lambda name: (-score(models[name]), name))
    rows = []
    for index, name in enumerate(names):
        points = score(models[name])
        rank = 1 + sum(score(item) > points for item in models.values())
        tie = sum(score(item) == points for item in models.values()) > 1
        rows.append((rank, name, tie))
    return rows


def _score(correct: int, scored: int, total: int) -> str:
    return f"{correct}/{scored}/{total}"


def _metric(stats: object, *, mib: bool = False) -> str:
    if not isinstance(stats, dict) or not _integer(stats.get("count")) or not stats["count"]:
        return "— (0)"
    median, p95 = stats.get("median"), stats.get("p95")
    if not all(type(value) in (int, float) and math.isfinite(value) for value in (median, p95)):
        return "— (0)"
    factor = 1024 if mib else 1
    return f"{median/factor:.1f} / {p95/factor:.1f} ({stats['count']})"


def _rss_peak(stats: object) -> str:
    if not isinstance(stats, dict) or not _integer(stats.get("count")) or not stats["count"]:
        return "— (0)"
    value = stats.get("max")
    if type(value) not in (int, float) or not math.isfinite(value):
        return "— (0)"
    return f"{value/1024:.2f} ({stats['count']})"


def _rank_table(title: str, models: dict, score, detail, *, header="Réussites / scorés / total") -> list[str]:
    lines = [f"## {title}", "", f"| Rang | Modèle | {header} |",
             "|---:|---|---:|"]
    for rank, label, tie in ranked(models, score):
        lines.append(f"| {rank}{' ex æquo' if tie else ''} | {label} | {detail(models[label])} |")
    return lines + [""]


def _base_axis(models: dict, axis: str, group: str) -> list[str]:
    return _rank_table(f"{axis} : {group}", models,
                       lambda item: item["groups"][axis][group]["correct"],
                       lambda item: _score(**{key: item["groups"][axis][group][key]
                                              for key in ("correct", "scored", "total")}))


def render(base: dict, mastra: dict, *, current_hash: str, old_hash: str,
           vela_hash: str, producer_hash: str, current: dict, old: dict, vela: dict,
           d3_hash: str | None = None) -> str:
    model_count = len(base)
    d3_count = len(base) - len(OLD_LABELS) - 1  # Sol is added by composition.
    lines = [f"# Comparaison D3 et candidats historiques : {model_count} modèles", "",
             "Mesures de modèles isolés sur 132 choix de base et 24 propositions Mastra FR/EN.",
             "Les références de base sont annotées par agent et attendent une revue humaine.",
             "Mastra mesure un accord avec des propositions provisoires : zéro référence humaine",
             "qualifiée, zéro outil exécuté et aucun parcours de réponse finale observé.", "",
             "Les classements portent sur le nombre de choix corrects sur le dénominateur complet.",
             "Une couverture réduite reste visible dans la colonne « scorés ».",
             "Les ex aequo partagent un rang; chaque axe est trié indépendamment.", ""]
    lines += _rank_table("Classement général : bases", base,
                         lambda item: item["counts"]["correct"],
                         lambda item: _score(item["counts"]["correct"], item["counts"]["scored"], 132))
    lines += _rank_table("Routage Mastra : accord provisoire", mastra,
                         lambda item: item["coverage"]["agreement_count"],
                         lambda item: _score(item["coverage"]["agreement_count"],
                                             item["coverage"]["valid_decisions"], 24),
                         header="Accords / décisions valides / total")
    for action in ("search", "stats", "fallback"):
        lines += _rank_table(f"Mastra : {action} (accord provisoire)", mastra,
                             lambda item, action=action: item["by_proposed_action"][action]["agreement_count"],
                             lambda item, action=action: _score(
                                 item["by_proposed_action"][action]["agreement_count"],
                                 item["by_proposed_action"][action]["valid_decisions"], 8),
                             header="Accords / décisions valides / total")
    for language in ("fr", "en"):
        lines += _rank_table(f"Mastra : {language.upper()} (accord provisoire)", mastra,
                             lambda item, language=language: item["by_language"][language]["agreement_count"],
                             lambda item, language=language: _score(
                                 item["by_language"][language]["agreement_count"],
                                 item["by_language"][language]["valid_decisions"], 12),
                             header="Accords / décisions valides / total")
    for axis, groups in (("domain", ("documentary", "mathematics", "chemistry")),
                         ("language", ("fr", "en"))):
        for group in groups:
            lines += _base_axis(base, axis, group)
    lines += ["## Difficultés et splits : bases", "",
              "| Modèle | D1 /40 | D2 /40 | D3 /52 | Train /36 | Calibration /30 | Test /66 |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for label in sorted(base, key=lambda name: (-base[name]["counts"]["correct"], name)):
        item = base[label]
        cells = []
        for axis, group in (("difficulty", "D1"), ("difficulty", "D2"), ("difficulty", "D3"),
                            ("split", "train"), ("split", "calibration"), ("split", "test")):
            value = item["groups"][axis][group]
            cells.append(_score(value["correct"], value["scored"], value["total"]))
        lines.append("| " + label + " | " + " | ".join(cells) + " |")
    lines += ["", "## Ressources, latences et tokens", "",
              "Latences et tokens : médiane / p95 (nombre d'observations). RAM : maximum",
              "des pics RSS worker rapportés, en Gio (nombre d'observations) ;",
              "Jev est une API distante : RAM serveur non observée. Latences adaptateur d'un",
              "seul passage, sans garantie de queue. Tokens natifs = longueur maximale de",
              "séquence par choix ; champs absents affichés explicitement.", "",
              "| Modèle | Appareil / précision | RSS base max Gio | Base ms | Mastra ms | Tokens base | Tokens Mastra |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for label in sorted(base, key=lambda name: (-base[name]["counts"]["correct"], name)):
        b, m = base[label], mastra[label]
        identity = b["identity"]
        settings = identity.get("settings") if isinstance(identity.get("settings"), dict) else {}
        device = identity.get("device") or settings.get("device") or "distant/inconnu"
        if identity.get("adapter") == "d3":
            precision = f"backbone {settings['backbone_dtype']}, readout {settings['readout_dtype']}"
        else:
            precision = settings.get("dtype") or "non observée"
        rss = "non observée" if label == "Jev" else _rss_peak(b.get("worker_rss_mib"))
        cells = [label, f"{device} / {precision}", rss,
                 _metric(b.get("timing", {}).get("successful_adapter_ms")),
                 _metric(m.get("timing", {}).get("successful_adapter_ms")),
                 _metric(b.get("measurements", {}).get("native_tokens", {}).get("max_sequence_tokens")),
                 _metric(m.get("measurements", {}).get("native_tokens", {}).get("max_sequence_tokens"))]
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", f"Les {['trois', 'quatre', 'cinq'][d3_count - 3]} D3 utilisent un backbone BF16 et un readout FP32.",
              "Plusieurs pilotes CPU antérieurs sont en FP32 ; Noma est déjà en BF16,",
              "et certains anciens agrégats n'exposent aucun dtype. RAM et latence restent des axes",
              "distincts des classements de choix. Les 76 cas documentaires pèsent davantage",
              "dans le total que les 28 cas de chaque domaine scientifique.", "",
              "## Provenance de composition", "",
              f"- JSON agrégé D3, SHA-256 : `{current_hash}` ; {model_count - 1} modèles.",
              f"- Export Vela de contrôle, SHA-256 : `{vela_hash}` ; 13 agrégats inchangés.",
              f"- Export historique Sol, SHA-256 : `{old_hash}` ; seul Sol est ajouté."]
    if d3_hash is not None:
        lines.append(f"- Export D3 historique de contrôle, SHA-256 : `{d3_hash}` ; 16 agrégats inchangés.")
    lines += [f"- Producteur de cette synthèse, SHA-256 : `{producer_hash}`.",
              "- Producteur agrégé D3 (fichiers versionnés) : " +
              ", ".join(f"`{name}` `{digest}`" for name, digest in
                        sorted(current["producer_files_sha256"].items())) + ".",
              "- Producteur historique (fichiers versionnés) : " +
              ", ".join(f"`{name}` `{digest}`" for name, digest in
                        sorted(old["producer_files_sha256"].items())) + ".",
              "- Producteur Vela de contrôle (fichiers versionnés) : " +
              ", ".join(f"`{name}` `{digest}`" for name, digest in
                        sorted(vela["producer_files_sha256"].items())) + ".",
              "- Corpus bases : `" + next(iter({item["source"]["dataset_sha256"] for item in base.values()})) + "`.",
              "- Corpus Mastra : `" + next(iter({item["source"]["dataset_sha256"] for item in mastra.values()})) + "`.",
              "- Scorer bases : `" + next(iter({item["source"]["scorer_sha256"] for item in base.values()})) + "`.",
              "- Cette composition vérifie les JSON agrégés entiers des modèles historiques ;",
              "  elle ne revérifie pas les archives raw Sol ni D3.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench-root", type=Path, required=True,
                        help="Worktree providing deposium_bench.worker_transport.decode")
    parser.add_argument("--current-json", type=Path, required=True)
    parser.add_argument("--vela-json", type=Path, required=True,
                        help="Unchanged 13-model Vela export used to verify historical metrics")
    parser.add_argument("--sol-json", type=Path, required=True)
    parser.add_argument("--d3-json", type=Path,
                        help="Pinned 16-model D3 export required for mini and flash comparisons")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.bench_root.resolve()
    _require((root / "deposium_bench/worker_transport.py").is_file(), "bench root invalid")
    sys.path.insert(0, str(root))
    from deposium_bench.worker_transport import decode

    current, current_hash = _read(args.current_json, decode)
    vela, vela_hash = _read(args.vela_json, decode)
    old, old_hash = _read(args.sol_json, decode)
    d3, d3_hash = _read(args.d3_json, decode) if args.d3_json is not None else (None, None)
    _require(vela_hash == VELA_EXPORT_SHA, "historical Vela JSON bytes changed")
    _require(old_hash == SOL_EXPORT_SHA, "historical Sol JSON bytes changed")
    _require(d3_hash is None or d3_hash == D3_EXPORT_SHA, "historical D3 JSON bytes changed")
    base, mastra = compose(current, old, vela, d3)
    target = args.output_dir.absolute()
    _require(not target.exists() and not target.is_symlink(), "output destination already exists")
    _require(not target.resolve().is_relative_to(args.current_json.resolve().parent)
             and not target.resolve().is_relative_to(args.vela_json.resolve().parent)
             and not target.resolve().is_relative_to(args.sol_json.resolve().parent)
             and (args.d3_json is None or
                  not target.resolve().is_relative_to(args.d3_json.resolve().parent)),
             "output destination must be separate from sources")
    producer_hash = _sha(Path(__file__).read_bytes())
    report = render(base, mastra, current_hash=current_hash, old_hash=old_hash,
                    vela_hash=vela_hash, producer_hash=producer_hash,
                    current=current, old=old, vela=vela, d3_hash=d3_hash)
    _require(_sha(args.current_json.read_bytes()) == current_hash and
             _sha(args.vela_json.read_bytes()) == vela_hash and
             _sha(args.sol_json.read_bytes()) == old_hash and
             (args.d3_json is None or _sha(args.d3_json.read_bytes()) == d3_hash) and
             _sha(Path(__file__).read_bytes()) == producer_hash,
             "composition source changed before output")
    manifest = {"schema_version": "deposium.composed-comparison/v1",
                "scope": "aggregate_only_no_raw_archive_verification", "models": len(base),
                "current_json_sha256": current_hash, "vela_json_sha256": vela_hash,
                "sol_json_sha256": old_hash,
                "producer_sha256": producer_hash, "report_sha256": _sha(report.encode("utf-8"))}
    if d3_hash is not None:
        manifest["d3_json_sha256"] = d3_hash
    target.mkdir(parents=True, exist_ok=False)
    with (target / "report.md").open("x", encoding="utf-8") as output:
        output.write(report)
    with (target / "manifest.json").open("x", encoding="utf-8") as output:
        json.dump(manifest, output, ensure_ascii=False, sort_keys=True, indent=2)
        output.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CompositionError, ValueError) as exc:
        raise SystemExit(f"composition refused: {exc}") from None
