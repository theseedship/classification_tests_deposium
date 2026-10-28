"""Offline, aggregate-only comparison of the four sealed context-length campaigns."""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from deposium_bench import campaigns
from deposium_bench.context_analysis import OVERFLOW_ERRORS, _measurements, _number, _stats
from deposium_bench.scoring import STATUSES, summarize

_spec = importlib.util.spec_from_file_location("model_comparison_analysis", ROOT / "scripts/analyze-model-comparison.py")
_comparison = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_comparison)
_sealed_files, _identity, _sha = (_comparison._sealed_files, _comparison._identity, _comparison._sha)

SCHEMA = "deposium.length-comparison-analysis/v1"
TARGETS = (100, 250, 500, 1000, 2000, 4000, 8000)
MODELS = ("Julia", "GLiNER", "Jev", "Indecis")
DATASET_SHA256 = "f721aec7ff08b3b4be6a2e3dcb5dd88ae2b1c0bea3a7fcf6f9ab0aefd92e492a"
RAW_SHA256 = {"Julia": "2994db7e3f05c8b0f982bed0a7d0e2a238ecffda397d01a36a92f7b2e2fd946d",
              "GLiNER": "f387d7872f9b6eeccae8bd7ecbca90f658585d93969e170584b8b0bfca6c0841",
              "Jev": "fa161c24ecf81e4e42da475ff4e2beea1af36959ecf5f8694f22ae6e9c01123c",
              "Indecis": "b61e2fb0c0cff50978cfc5ad9c6cabfe606e3560b157aac83b348ea7ffd6cc50"}
SEAL_SHA256 = {"Julia": "34de6c401b7c4e67c03c958547dcdf16a39e48f61deb4ac14783b732aab15a50",
               "GLiNER": "d1aba035256a29497a20a4ea9a92c5eb9bf4fdaf2d5cb76766865bb98948950c",
               "Jev": "f7be4b0a2663e388f05469e713d56eb6f5364582eab19a2f6c73a09a220889cf",
               "Indecis": "c28c83dae2ae277e4f30d5da8104a9917150f7a6065ef0d6829765d9c5391b18"}
PRODUCER_FILES = ("scripts/analyze-length-comparison.py", "scripts/analyze-model-comparison.py",
                  "deposium_bench/campaigns.py", "deposium_bench/cases.py",
                  "deposium_bench/scoring.py", "deposium_bench/context_analysis.py")
REQUIRED = {"manifest.json", "cases.jsonl", "profile.json", "raw.jsonl", "summary.json", "report.md"}
LABEL = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
MEMORY_ERRORS = {"julia_rss_limit", "gliner_rss_limit", "indecis_rss_limit", "laya_rss_limit"}
LATENCIES = ("adapter_duration_ms", "decision_ms", "inference_ms", "http_ms")
RESOURCES = ("native_tokens", "native_total_tokens", "native_padded_tokens", "rss_mib", "provider_input_tokens",
             "provider_output_tokens", "reference_actual_tokens", "reference_padded_tokens")


class AnalysisError(ValueError):
    pass


def _source(path: Path) -> tuple[list[dict], dict]:
    payload, seal = _sealed_files(path, REQUIRED)
    _, manifest, cases, records, parent, checked = campaigns._archive(path)
    if (set(payload) != set(checked) or any(payload[name] != checked[name] for name in payload)
        or not parent["sealed"] or manifest.get("mode") != "run"
        or manifest.get("qualification") != "model_isolated"
        or manifest.get("input_protocol") != "context_choice"
        or manifest.get("dataset_sha256") != DATASET_SHA256
        or _sha(payload["cases.jsonl"]) != DATASET_SHA256
        or manifest.get("scorer") != campaigns._scorer_fingerprint()
        or len(cases) != 378 or len(records) != len(cases)
        or {record["case_id"] for record in records} != {case["case_id"] for case in cases}):
        raise AnalysisError("length_protocol_or_corpus_mismatch")
    metrics = summarize(cases, records)
    archived = campaigns._decode(payload["summary.json"])
    if (archived.get("schema_version") != "deposium.campaign-summary/v1"
        or archived.get("completion_status") != "complete" or archived.get("stop_reason") is not None
        or archived.get("scorer") != manifest["scorer"] or archived.get("metrics") != metrics
        or archived.get("raw_sha256") != _sha(payload["raw.jsonl"])
        or metrics["scored_cases"] == 0):
        raise AnalysisError("length_summary_or_coverage_invalid")
    profile = campaigns._decode(payload["profile.json"])
    identity = _identity(profile, manifest["adapter_provenance"])
    expected = {target: 0 for target in TARGETS}
    families = set()
    rows = []
    indexed = {record["case_id"]: record for record in records}
    tokenizer_hashes = set()
    for case, score in zip(cases, metrics["rows"]):
        length = case.get("evaluation", {}).get("length")
        if not isinstance(length, dict):
            raise AnalysisError("length_annotation_missing")
        target = length.get("target_tokens")
        if (target not in expected or length.get("position") not in {"start", "middle", "end"}
            or length.get("order") != "original"
            or case.get("evaluation", {}).get("domain") not in {"documentary", "mathematics", "chemistry"}
            or case.get("language") not in {"fr", "en"}
            or type(length.get("actual_tokens")) is not int
            or type(length.get("padded_tokens")) is not int):
            raise AnalysisError("length_grid_invalid")
        expected[target] += 1
        families.add(case["translation_family"])
        tokenizer_hashes.add(length.get("tokenizer_sha256"))
        record = indexed[case["case_id"]]
        error = record["error"]
        if error == "input_length_target_unattainable":
            kind = "target_unattainable"
        elif error in OVERFLOW_ERRORS:
            kind = "typed_overflow"
        elif error in MEMORY_ERRORS:
            kind = "memory_guard"
        elif score["status"] == "missing":
            kind = "missing"
        elif score["status"] in {"unsupported", "error", "timeout", "abstain"}:
            kind = score["status"] + "_other"
        else:
            kind = "none"
        measured = _measurements(record)
        raw = record["raw_output"] if isinstance(record["raw_output"], dict) else {}
        components = raw.get("token_components") if isinstance(raw.get("token_components"), dict) else {}
        measured["native_total_tokens"] = _number(components.get("total_tokens"))
        rows.append({"target": target, "domain": case["evaluation"]["domain"],
                     "language": case["language"], "position": length["position"],
                     "family": case["translation_family"], "status": score["status"],
                     "scored": score["scored"], "correct": score["passed"], "failure_kind": kind,
                     "cached_failure": measured["cached_failure"],
                     "forward_executed": measured["forward_executed"],
                     "measurements": {**measured, "reference_actual_tokens": length["actual_tokens"],
                                      "reference_padded_tokens": length["padded_tokens"]}})
    if sorted(expected.values()) != [54] * 7 or len(families) != 9 or None in tokenizer_hashes or len(tokenizer_hashes) != 1:
        raise AnalysisError("length_grid_invalid")
    source = {"run_id": manifest["run_id"], "dataset_sha256": manifest["dataset_sha256"],
              "manifest_sha256": parent["manifest_sha256"], "raw_sha256": parent["raw_sha256"],
              "summary_sha256": _sha(payload["summary.json"]), "seal_sha256": _sha(payload["seal.json"]),
              "seal_fingerprint": seal["sha256"], "scorer_sha256": manifest["scorer"]["sha256"],
              "reference_tokenizer_sha256": next(iter(tokenizer_hashes)),
              "identity": identity, "qualification": manifest["qualification"],
              "timing_freshness": {"campaign_mode": manifest["mode"],
                                   "rescore_creates_new_measurements": False}}
    return rows, source


def _aggregate(rows: list[dict]) -> dict:
    planned = len(rows)
    scored = sum(row["scored"] for row in rows)
    correct = sum(row["correct"] for row in rows)
    recorded = sum(row["measurements"]["adapter_duration_ms"] is not None for row in rows)
    kinds = Counter(row["failure_kind"] for row in rows)
    status = Counter(row["status"] for row in rows)
    def timing(field, selected):
        values = [row["measurements"][field] for row in selected]
        stats = _stats(values)
        return {key: stats[key] for key in ("count", "min", "median", "p95", "max")}
    return {"planned": planned, "recorded": recorded, "scored": scored, "correct": correct,
            "coverage": scored / planned if planned else None,
            "accuracy_scored": correct / scored if scored else None,
            "accuracy_planned": correct / planned if planned else None,
            "independent_families": len({row["family"] for row in rows}),
            "statuses": {name: status[name] for name in STATUSES},
            "failure_kinds": {name: kinds[name] for name in ("target_unattainable", "typed_overflow",
                              "memory_guard", "missing", "unsupported_other", "error_other",
                              "timeout_other", "abstain_other")},
            "cached_failures": sum(row["cached_failure"] is True for row in rows),
            "cached_failure_unreported": sum(row["cached_failure"] is None for row in rows),
            "forward_executed": sum(row["forward_executed"] is True for row in rows),
            "forward_unreported": sum(row["forward_executed"] is None for row in rows),
            "latency_ms": {field: {"all_recorded": timing(field, rows),
                                   "successful": timing(field, [row for row in rows if row["status"] == "ok"]),
                                   "by_status": {name: timing(field, [row for row in rows if row["status"] == name])
                                                 for name in STATUSES}}
                           for field in LATENCIES},
            "resources": {field: {**timing(field, rows),
                                   "unreported": planned - timing(field, rows)["count"]}
                          for field in RESOURCES}}


def _groups(rows: list[dict]) -> dict:
    result = {}
    for fields in (("target",), ("target", "domain"), ("target", "language"),
                   ("target", "position"), ("target", "domain", "language", "position")):
        name = "_".join(fields)
        keys = sorted({tuple(row[field] for field in fields) for row in rows})
        result[name] = [{"dimensions": dict(zip(fields, key)),
                         "metrics": _aggregate([row for row in rows if tuple(row[field] for field in fields) == key])}
                        for key in keys]
    return result


def _markdown(result: dict) -> str:
    def fmt(value):
        return "—" if value is None else f"{value:.1f}"
    models = {label: result["models"][label] for label in MODELS}
    lines = ["# Comparaison des campagnes de longueur", "",
             "Mesures exploratoires de modèles isolés sur les mêmes 378 variantes et neuf familles indépendantes.",
             "Corrects / scorés / prévus ; une absence de mesure ne compte jamais comme une erreur du modèle.", "",
             "## Vue globale", "",
             "| Modèle | Corrects / scorés / prévus | Couverture | Statuts ok / unsupported / error / timeout / missing / abstain | Cibles infaisables / dépassement natif / garde mémoire | Adaptateur ok médiane / p95 ms (n) | RSS worker max MiB (n) |",
             "|---|---:|---:|---|---|---:|---:|"]
    for label, item in models.items():
        m = item["overall"]; latency = m["latency_ms"]["adapter_duration_ms"]["successful"]
        rss = m["resources"]["rss_mib"]
        lines.append(f'| {label} | {m["correct"]}/{m["scored"]}/{m["planned"]} | {m["coverage"]:.1%} | '
                     f'{" / ".join(str(m["statuses"][s]) for s in ("ok", "unsupported", "error", "timeout", "missing", "abstain"))} | '
                     f'{m["failure_kinds"]["target_unattainable"]} / {m["failure_kinds"]["typed_overflow"]} / {m["failure_kinds"]["memory_guard"]} | '
                     f'{fmt(latency["median"])} / {fmt(latency["p95"])} ({latency["count"]}) | {fmt(rss["max"])} ({rss["count"]}) |')
    lines += ["", "## Par longueur de référence Julia", "",
              "| Cible | " + " | ".join(models) + " |",
              "|---:|" + "---:|" * len(models)]
    for target in TARGETS:
        cells = []
        for item in models.values():
            m = next(group["metrics"] for group in item["groups"]["target"] if group["dimensions"]["target"] == target)
            cells.append(f'{m["correct"]}/{m["scored"]}/{m["planned"]} ({m["coverage"]:.1%})')
        lines.append(f'| {target} | ' + " | ".join(cells) + " |")
    for group_name, title in (("target_domain", "Longueur × domaine"),
                              ("target_language", "Longueur × langue"),
                              ("target_position", "Longueur × position"),
                              ("target_domain_language_position", "Longueur × domaine × langue × position")):
        lines += ["", "## " + title, "", "| Groupe | " + " | ".join(models) + " |",
                  "|---|" + "---:|" * len(models)]
        first = next(iter(models.values()))["groups"][group_name]
        for index, group in enumerate(first):
            dimension = " / ".join(str(group["dimensions"][field]) for field in group_name.split("_"))
            cells = []
            for item in models.values():
                m = item["groups"][group_name][index]["metrics"]
                cells.append(f'{m["correct"]}/{m["scored"]}/{m["planned"]}')
            lines.append(f'| {dimension} | ' + " | ".join(cells) + " |")
    lines += ["", "## Statuts et types d'échec par longueur", "",
              "| Modèle | Cible | ok / unsupported / error / timeout / missing / abstain | Hors cible / dépassement natif / garde mémoire | Retours avec échec mémorisé rapporté |",
              "|---|---:|---|---|---:|"]
    for label, item in models.items():
        for group in item["groups"]["target"]:
            m = group["metrics"]
            lines.append(f'| {label} | {group["dimensions"]["target"]} | '
                         f'{" / ".join(str(m["statuses"][s]) for s in ("ok", "unsupported", "error", "timeout", "missing", "abstain"))} | '
                         f'{m["failure_kinds"]["target_unattainable"]} / {m["failure_kinds"]["typed_overflow"]} / {m["failure_kinds"]["memory_guard"]} | '
                         f'{m["cached_failures"]} ({m["cached_failure_unreported"]} sans drapeau) |')
    lines += ["", "## Mesures par longueur", "",
              "Chaque cellule donne médiane / p95 / maximum (n) ; les min et les mesures par statut sont dans analysis.json.",
              "Un temps natif absent après refus ou arrêt ne reçoit aucune valeur inventée.", "",
              "| Modèle | Cible | Adaptateur ok ms | Décision ok ms | Inférence ok ms | HTTP ok ms | Tokens de référence min–max (n) | Tokens natifs encodés min–max (n) | Tokens natifs cumulés min–max (n) | Tokens fournisseur entrée min–max (n) | RSS worker max MiB (n) |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    def times(m, field):
        s = m["latency_ms"][field]["successful"]
        return f'{fmt(s["median"])} / {fmt(s["p95"])} / {fmt(s["max"])} ({s["count"]})'
    def span(m, field):
        s = m["resources"][field]
        return f'{fmt(s["min"])}–{fmt(s["max"])} ({s["count"]})'
    for label, item in models.items():
        for group in item["groups"]["target"]:
            m = group["metrics"]
            lines.append(f'| {label} | {group["dimensions"]["target"]} | '
                         f'{times(m, "adapter_duration_ms")} | {times(m, "decision_ms")} | '
                         f'{times(m, "inference_ms")} | {times(m, "http_ms")} | '
                         f'{span(m, "reference_actual_tokens")} | {span(m, "native_tokens")} | '
                         f'{span(m, "native_total_tokens")} | {span(m, "provider_input_tokens")} | '
                         f'{fmt(m["resources"]["rss_mib"]["max"])} ({m["resources"]["rss_mib"]["count"]}) |')
    lines += ["", "Les cibles et tokens de référence utilisent le tokenizer Julia. Les tokens natifs encodés et les tokens déclarés par le fournisseur sont des métriques différentes.",
              "Indecis encode contexte et choix séparément : sa longueur maximale par séquence n'est pas la somme des tokens.",
              "Le temps HTTP Jev inclut le réseau client ; les traces ne prouvent ni absence de troncature serveur ni RSS serveur.",
              "Les enveloppes d'erreur répétées après une garde mémoire ne sont pas des dépassements indépendants et ne mesurent pas une inférence à cette longueur.",
              "Les p95 sont descriptifs par rang le plus proche ; les variantes d'une même famille ne sont pas indépendantes.",
              ("Modèles non mesurés dans ce protocole : " + ", ".join(result["not_measured"]) + "."
               if result["not_measured"] else "Aucun autre modèle n'a été déclaré dans ce rapport."),
              "Empreintes, provenance et dénominateurs complets : analysis.json. Aucun cas ni texte privé n'est publié.", ""]
    return "\n".join(lines)


def analyze(length: list[tuple[str, Path]], output_dir: str | Path,
            not_measured: list[str] | None = None) -> dict:
    not_measured = not_measured or []
    labels = [label for label, _ in length]
    if (set(labels) != set(MODELS) or len(labels) != 4 or any(not LABEL.fullmatch(label) for label in labels)
        or len(not_measured) != len(set(not_measured))
        or any(not LABEL.fullmatch(label) or label in labels for label in not_measured)):
        raise AnalysisError("labels_invalid_or_missing_campaign")
    paths = {label: Path(path).resolve() for label, path in length}
    target = Path(output_dir).absolute()
    if (target.exists() or target.is_symlink()
        or any(target.resolve().is_relative_to(path) for path in paths.values())):
        raise AnalysisError("output_not_exclusive")
    hashes = {name: _sha((ROOT / name).read_bytes()) for name in PRODUCER_FILES}
    sources = {label: _source(paths[label]) for label in MODELS}
    # Equal bytes, rather than equal labels or summary totals, bind every model to
    # exactly the same private, versioned input and reference snapshot.
    case_digests = {item[1]["dataset_sha256"] for item in sources.values()}
    if len(case_digests) != 1:
        raise AnalysisError("mixed_corpus")
    adapters = {"Julia": "julia", "GLiNER": "gliner", "Jev": "jev_http", "Indecis": "indecis"}
    if any(sources[label][1]["raw_sha256"] != RAW_SHA256[label]
           or sources[label][1]["seal_sha256"] != SEAL_SHA256[label]
           or sources[label][1]["identity"]["adapter"] != adapters[label]
           for label in MODELS):
        raise AnalysisError("archived_trace_or_model_identity_mismatch")
    result = {"schema_version": SCHEMA, "scope": "isolated_model_length_campaigns",
              "reference_review": "agent_only_pending_human", "target_tokens": list(TARGETS),
              "planned_cases": 378, "independent_families": 9,
              "producer_files_sha256": hashes,
              "statistics_protocol": {"median": "arithmetic central pair",
                                      "p95": "nearest rank ceil(0.95*n)",
                                      "successful": "status ok, including incorrect decisions",
                                      "independence": "translation_family, not variants"},
              "models": {label: {"source": sources[label][1],
                                 "overall": _aggregate(sources[label][0]),
                                 "groups": _groups(sources[label][0])}
                         for label in MODELS},
              "not_measured": {label: {"status": "not_run", "planned": 378,
                                       "scored": None, "correct": None, "coverage": None}
                               for label in sorted(not_measured)},
              "limitations": ["Reference target length uses Julia tokenizer, not a common native token budget.",
                              "Indecis native context sequence length is not the sum across choices.",
                              "HTTP provider tokens are declarations; server truncation and RSS are unobserved.",
                              "Worker RSS is a process high-water observation, not per-request allocation.",
                              "Descriptive isolated campaigns do not qualify product routing."]}
    if (any(_sha((ROOT / name).read_bytes()) != digest for name, digest in hashes.items())
        or any(_sha((path / "seal.json").read_bytes()) != sources[label][1]["seal_sha256"]
               for label, path in paths.items())):
        raise AnalysisError("source_changed_during_analysis")
    target.mkdir(parents=True, exist_ok=False)
    with (target / "analysis.json").open("xb") as stream:
        stream.write(campaigns._encode(result))
    with (target / "report.md").open("xb") as stream:
        stream.write(_markdown(result).encode("utf-8"))
    return result


def _label_path(value: str) -> tuple[str, Path]:
    label, separator, path = value.partition("=")
    if not separator or not LABEL.fullmatch(label) or not path:
        raise argparse.ArgumentTypeError("expected LABEL=ARCHIVE")
    return label, Path(path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=_label_path, action="append", required=True)
    parser.add_argument("--not-measured", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    analyze(args.length, args.output_dir, args.not_measured)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
