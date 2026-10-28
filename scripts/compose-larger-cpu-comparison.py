#!/usr/bin/env python3
"""Join three sealed CPU pilots to the frozen 19-model overview, offline.

``--current-json`` is an analyze-model-comparison.py export containing either
the three new candidates alone or those candidates plus any frozen candidates.
``--historical-json`` is the published 19-model overview manifest. Historical
rows are copied from its pinned exports; no historical archive is rerun or
rescored. The six new campaign archives are checked against their seals and
the hashes recorded in the new aggregate.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.worker_transport import decode

LEGACY_PATH = ROOT / "scripts/compose-d3-comparison.py"
spec = importlib.util.spec_from_file_location("frozen_d3_composer", LEGACY_PATH)
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)

HISTORICAL_MANIFEST_SHA = "5cc6133e80c470d783b331adc4df03e16ec3efb79cfae06f02eb01af1c5d21f9"
HISTORICAL_LABELS = legacy.FROZEN_D3_LABELS | {"D3mini", "D3flash", "Sol"}
NEW_MODELS = {
    "vllm-sr/Decision-2.0-Nox-4B": ("ae269ecf34a0b3a89026bc1afd9c995279212fad", "decision2"),
    "vllm-sr/Vela-2.0-4B": ("d692394127f6f87fc581d8634c9558fe4776efce", "vela2"),
    "LiquidAI/d1-3B": ("051bcc464b01b9f92942b364d9586b0ef5912432", "small_model"),
}
HASH = re.compile(r"[0-9a-f]{64}\Z")
LABEL = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,39}\Z")


CompositionError = legacy.CompositionError


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise CompositionError(reason)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path, *, max_bytes: int = 32 * 1024 * 1024) -> tuple[dict, str]:
    require(path.is_file() and not path.is_symlink(), f"source missing or symlinked: {path}")
    raw = path.read_bytes()
    require(0 < len(raw) <= max_bytes, f"source size invalid: {path}")
    data = decode(raw)
    require(isinstance(data, dict), f"JSON object required: {path}")
    return data, sha(raw)


def historical(path: Path) -> tuple[dict, dict]:
    """Resolve and validate every export pinned by the 19-model manifest."""
    manifest, manifest_hash = read_json(path)
    require(manifest_hash == HISTORICAL_MANIFEST_SHA, "19-model manifest bytes changed")
    require(manifest.get("schema_version") == "deposium.composed-comparison/v1"
            and manifest.get("scope") == "aggregate_only_no_raw_archive_verification"
            and manifest.get("models") == 19, "historical overview contract changed")
    evidence = path.parent.parent
    paths = {
        "current": evidence / "model-comparison-d3-larger-20261011/analysis.json",
        "sol": evidence / "model-comparison-complete-20261010-sol/analysis.json",
        "vela": evidence / "model-comparison-vela2-20261011/analysis.json",
        "d3": evidence / "model-comparison-d3-20261011/analysis.json",
    }
    keys = {"current": "current_json_sha256", "sol": "sol_json_sha256",
            "vela": "vela_json_sha256", "d3": "d3_json_sha256"}
    exports = {}
    for name, source in paths.items():
        exports[name], digest = read_json(source)
        require(digest == manifest.get(keys[name]), f"frozen {name} export bytes changed")
    report = path.parent / "report.md"
    require(report.is_file() and not report.is_symlink()
            and sha(report.read_bytes()) == manifest.get("report_sha256"),
            "historical overview report bytes changed")
    require(sha(LEGACY_PATH.read_bytes()) == manifest.get("producer_sha256"),
            "historical overview producer bytes changed")
    legacy._validate(exports["current"])
    legacy._validate(exports["sol"], historical=True)
    legacy._validate(exports["vela"], baseline=True)
    legacy._validate(exports["d3"])
    base, mastra = legacy.compose(exports["current"], exports["sol"],
                                  exports["vela"], exports["d3"])
    require(set(base) == set(mastra) == HISTORICAL_LABELS, "historical membership changed")
    return {"base": base, "mastra": mastra}, {
        "manifest_sha256": manifest_hash,
        "analysis_sha256": manifest["current_json_sha256"],
        "sol_sha256": manifest["sol_json_sha256"],
        "report_sha256": manifest["report_sha256"],
    }


def _new_row(label: str, base: dict, route: dict, historical_rows: dict) -> str:
    """Validate denominators, references, provenance and pinned model identity."""
    require(isinstance(base, dict) and isinstance(route, dict), f"{label}: row missing")
    require(base.get("qualification") == "model_isolated", f"{label}: base qualification")
    legacy._count(base.get("counts"), total=132, field=f"{label} base")
    require(base["counts"]["scored"] > 0, f"{label}: zero scored base cases")
    require(base["counts"].get("translation_families") == 66, f"{label}: translation families")
    groups = base.get("groups")
    require(isinstance(groups, dict), f"{label}: base groups missing")
    for axis, expected in legacy.BASE_GROUPS.items():
        values = groups.get(axis)
        require(isinstance(values, dict) and set(values) == set(expected), f"{label}: {axis} groups")
        for group, total in expected.items():
            legacy._count(values[group], total=total, field=f"{label} {axis}/{group}")
        require(sum(values[group]["correct"] for group in expected) == base["counts"]["correct"]
                and sum(values[group]["scored"] for group in expected) == base["counts"]["scored"],
                f"{label}: {axis} totals")
    legacy._source(base.get("source"), mastra=False)
    require(HASH.fullmatch(str(base["source"].get("seal_fingerprint", ""))) is not None,
            f"{label}: base seal fingerprint")
    identity = base.get("identity")
    require(isinstance(identity, dict), f"{label}: identity missing")
    repo = identity.get("model_repo_id")
    require(repo in NEW_MODELS, f"{label}: unreviewed model repository")
    revision, adapter = NEW_MODELS[repo]
    settings = identity.get("settings")
    require(identity.get("model_revision") == revision and identity.get("adapter") == adapter
            and isinstance(identity.get("profile_id"), str)
            and HASH.fullmatch(str(identity.get("identity_sha256", ""))) is not None
            and HASH.fullmatch(str(identity.get("model_assets_sha256", ""))) is not None
            and isinstance(settings, dict) and settings.get("device") == "cpu",
            f"{label}: pinned CPU identity mismatch")
    legacy._stats(base.get("timing", {}).get("successful_adapter_ms"), total=132,
                  field=f"{label} base timing", unreported=False)
    legacy._stats(base.get("worker_rss_mib"), total=132,
                  field=f"{label} base RSS", unreported=True)
    legacy._stats(base.get("measurements", {}).get("native_tokens", {}).get("max_sequence_tokens"),
                  total=132, field=f"{label} base tokens", unreported=True)
    require(route.get("qualification") == "provisional_agreement_pending_human_review"
            and route.get("reference_review") == "pending_human"
            and route.get("cases_scored") == 0,
            f"{label}: Mastra reference or qualification mismatch")
    legacy._count(route.get("coverage"), total=24, field=f"{label} Mastra", qualified="agreement")
    require(route["coverage"]["valid_decisions"] > 0, f"{label}: zero valid Mastra decisions")
    for axis, expected in legacy.MASTRA_GROUPS.items():
        values = route.get(axis)
        require(isinstance(values, dict) and set(values) == set(expected), f"{label}: Mastra {axis}")
        for group, total in expected.items():
            legacy._count(values[group], total=total, field=f"{label} Mastra {axis}/{group}",
                          qualified="agreement")
        require(sum(values[group]["agreement_count"] for group in expected) ==
                route["coverage"]["agreement_count"], f"{label}: Mastra {axis} total")
    legacy._source(route.get("source"), mastra=True)
    require(HASH.fullmatch(str(route["source"].get("seal_fingerprint", ""))) is not None,
            f"{label}: Mastra seal fingerprint")
    rid = route.get("identity")
    require(isinstance(rid, dict) and all(rid.get(key) == identity.get(key) for key in
            ("adapter", "profile_id", "model_repo_id", "model_id", "model_revision",
             "model_assets_sha256")), f"{label}: base/Mastra identity mismatch")
    legacy._stats(route.get("timing", {}).get("successful_adapter_ms"), total=24,
                  field=f"{label} Mastra timing", unreported=False)
    legacy._stats(route.get("worker_rss_mib"), total=24,
                  field=f"{label} Mastra RSS", unreported=True)
    legacy._stats(route.get("measurements", {}).get("native_tokens", {}).get("max_sequence_tokens"),
                  total=24, field=f"{label} Mastra tokens", unreported=True)
    sample = next(iter(historical_rows["base"].values()))
    sample_route = next(iter(historical_rows["mastra"].values()))
    require(base["source"]["dataset_sha256"] == sample["source"]["dataset_sha256"]
            and base["source"]["scorer_sha256"] == sample["source"]["scorer_sha256"]
            and route["source"]["dataset_sha256"] == sample_route["source"]["dataset_sha256"]
            and route["source"]["requests_sha256"] == sample_route["source"]["requests_sha256"],
            f"{label}: corpus, scorer or Mastra projection differs")
    return repo


def compose(current: dict, frozen: dict) -> tuple[dict, dict, dict]:
    require(current.get("schema_version") == legacy.SCHEMA
            and current.get("scope") == "isolated_model_observations"
            and current.get("base_reference_review") == legacy.REFERENCE
            and current.get("base_rank_order") == "correct_over_all_132_descending",
            "current aggregate protocol or reference mismatch")
    base, mastra = current.get("base"), current.get("mastra")
    require(isinstance(base, dict) and isinstance(mastra, dict) and set(base) == set(mastra),
            "current base/Mastra membership mismatch")
    old = set(base) & HISTORICAL_LABELS
    new = set(base) - HISTORICAL_LABELS
    require(len(new) == 3 and len(base) <= 22 and
            all(isinstance(label, str) and LABEL.fullmatch(label) for label in new),
            "current aggregate needs exactly three new, uniquely named models")
    for label in old:
        require(base[label] == frozen["base"][label] and mastra[label] == frozen["mastra"][label],
                f"{label}: frozen historical aggregate changed")
    require(current.get("base_ranking") ==
            sorted(base, key=lambda label: (-base[label]["counts"]["correct"], label)),
            "current base ranking invalid")
    producer = current.get("producer_files_sha256")
    require(isinstance(producer, dict) and producer and
            all(isinstance(k, str) and HASH.fullmatch(str(v)) for k, v in producer.items()),
            "current producer provenance invalid")
    repos = [_new_row(label, base[label], mastra[label], frozen) for label in new]
    require(set(repos) == set(NEW_MODELS), "three distinct pinned model families required")
    all_base = {**frozen["base"], **{label: base[label] for label in new}}
    all_mastra = {**frozen["mastra"], **{label: mastra[label] for label in new}}
    require(len({item["source"]["seal_sha256"] for item in all_base.values()}) == 22
            and len({item["source"]["seal_sha256"] for item in all_mastra.values()}) == 22,
            "archive seal reused across model labels")
    return all_base, all_mastra, {label: (base[label], mastra[label]) for label in new}


def verify_archives(new: dict, archive_root: Path) -> list[dict]:
    """Check all bytes sealed by each new archive, without evaluating decisions."""
    require(archive_root.is_dir() and not archive_root.is_symlink(), "archive root missing")
    wanted = {item["source"]["seal_sha256"] for rows in new.values() for item in rows}
    found: dict[str, Path] = {}
    for directory in archive_root.iterdir():
        if directory.is_symlink() or not directory.is_dir():
            continue
        seal = directory / "seal.json"
        if seal.is_file() and not seal.is_symlink():
            digest = sha(seal.read_bytes())
            if digest in wanted:
                require(digest not in found, "ambiguous matching archive seal")
                found[digest] = directory
    require(set(found) == wanted and len(wanted) == 6, "new sealed archives missing")
    proof = []
    for label, (base, mastra) in sorted(new.items()):
        for kind, item in (("base", base), ("mastra", mastra)):
            source = item["source"]
            directory = found[source["seal_sha256"]]
            entries = list(directory.iterdir())
            require(all(p.is_file() and not p.is_symlink() for p in entries),
                    f"{label}: archive inventory invalid")
            seal, _ = read_json(directory / "seal.json", max_bytes=1024 * 1024)
            files = seal.get("files")
            required = ({"manifest.json", "cases.jsonl", "profile.json", "raw.jsonl",
                         "summary.json", "report.md"} if kind == "base" else
                        {"manifest.json", "cases.jsonl", "requests.jsonl", "profile.json",
                         "raw.jsonl", "summary.json", "adapter-initial.json"})
            require(seal.get("schema_version") == "deposium.archive-seal/v1"
                    and isinstance(files, dict) and required <= set(files) and
                    seal.get("sha256") == sha((json.dumps(files, ensure_ascii=False,
                                                          sort_keys=True, allow_nan=False) + "\n").encode())
                    and set(p.name for p in entries) == set(files) | {"seal.json"},
                    f"{label}: archive seal invalid")
            for name, digest in files.items():
                require(isinstance(name, str) and Path(name).name == name and name not in {".", ".."}
                        and HASH.fullmatch(str(digest)) is not None
                        and sha((directory / name).read_bytes()) == digest,
                        f"{label}: sealed file changed")
            manifest, _ = read_json(directory / "manifest.json")
            summary, _ = read_json(directory / "summary.json")
            require(summary.get("completion_status") == "complete", f"{label}: archive incomplete")
            require(source["seal_fingerprint"] == seal["sha256"]
                    and source["manifest_sha256"] == files.get("manifest.json")
                    and source["raw_sha256"] == files.get("raw.jsonl"),
                    f"{label}: archive source hashes differ")
            if kind == "base":
                identity = manifest.get("adapter_provenance", {})
                model = identity.get("model", {})
                require(files.get("cases.jsonl") == source["dataset_sha256"]
                        and manifest.get("dataset_sha256") == source["dataset_sha256"]
                        and manifest.get("scorer", {}).get("sha256") == source["scorer_sha256"]
                        and manifest.get("case_count") == 132
                        and manifest.get("qualification") == "model_isolated"
                        and manifest.get("run_id") == source.get("run_id")
                        and summary.get("raw_sha256") == source["raw_sha256"]
                        and identity.get("identity_sha256") == item["identity"]["identity_sha256"]
                        and identity.get("model_repo_id") == item["identity"]["model_repo_id"]
                        and identity.get("model_revision") == item["identity"]["model_revision"],
                        f"{label}: base archive protocol or identity mismatch")
                if item["identity"]["model_repo_id"] == "LiquidAI/d1-3B":
                    require(isinstance(model, dict) and model.get("mode") == "liquid3",
                            f"{label}: Liquid runtime mode mismatch")
            else:
                initial, _ = read_json(directory / "adapter-initial.json")
                profile, _ = read_json(directory / "profile.json")
                require(files.get("requests.jsonl") == source["requests_sha256"]
                        and manifest.get("requests_sha256") == source["requests_sha256"]
                        and manifest.get("dataset_sha256") == source["dataset_sha256"]
                        and manifest.get("projection_version") == source["projection_version"]
                        and manifest.get("qualification") == "isolated_model_observation"
                        and len(manifest.get("case_ids", [])) == 24
                        and initial.get("identity_sha256") == item["identity"]["identity_sha256"]
                        and initial.get("model_repo_id") == item["identity"]["model_repo_id"]
                        and initial.get("model_revision") == item["identity"]["model_revision"],
                        f"{label}: Mastra archive protocol or identity mismatch")
                if item["identity"]["model_repo_id"] == "LiquidAI/d1-3B":
                    require(isinstance(profile.get("model"), dict)
                            and profile["model"].get("mode") == "liquid3",
                            f"{label}: Liquid Mastra runtime mode mismatch")
            proof.append({"label": label, "kind": kind, "archive": directory.name,
                          "seal_sha256": source["seal_sha256"], "files_verified": len(files)})
    return proof


def render(base: dict, mastra: dict, *, current_hash: str, historical_hash: str,
           producer_hash: str, archives: list[dict]) -> str:
    lines = [f"# Comparaison CPU et historique : {len(base)} modèles", "",
             "132 choix de base (66 FR, 66 EN) et 24 propositions de routage Mastra (12 FR, 12 EN).",
             "Références de base `agent_only_pending_human` ; propositions Mastra `pending_human`.",
             "Le routage est un accord provisoire : zéro outil exécuté et zéro parcours produit qualifié.",
             "Corrects / scorés / total, ou accords / décisions valides / total. Les erreurs et absences",
             "restent dans le dénominateur. Chaque classement est trié indépendamment ; ex æquo visibles.", ""]
    lines += legacy._rank_table("Classement général : bases", base,
             lambda x: x["counts"]["correct"],
             lambda x: legacy._score(x["counts"]["correct"], x["counts"]["scored"], 132))
    lines += legacy._rank_table("Routage Mastra : accord provisoire", mastra,
             lambda x: x["coverage"]["agreement_count"],
             lambda x: legacy._score(x["coverage"]["agreement_count"], x["coverage"]["valid_decisions"], 24),
             header="Accords / décisions valides / total")
    for action in ("search", "stats", "fallback"):
        lines += legacy._rank_table(f"Mastra : {action} (accord provisoire)", mastra,
                 lambda x, action=action: x["by_proposed_action"][action]["agreement_count"],
                 lambda x, action=action: legacy._score(x["by_proposed_action"][action]["agreement_count"],
                                                        x["by_proposed_action"][action]["valid_decisions"], 8),
                 header="Accords / décisions valides / total")
    for lang in ("fr", "en"):
        lines += legacy._rank_table(f"Mastra : {lang.upper()} (accord provisoire)", mastra,
                 lambda x, lang=lang: x["by_language"][lang]["agreement_count"],
                 lambda x, lang=lang: legacy._score(x["by_language"][lang]["agreement_count"],
                                                    x["by_language"][lang]["valid_decisions"], 12),
                 header="Accords / décisions valides / total")
    for axis, groups in (("domain", ("documentary", "mathematics", "chemistry")),
                         ("language", ("fr", "en"))):
        for group in groups:
            lines += legacy._base_axis(base, axis, group)
    lines += ["## Difficultés et splits : bases", "",
              "| Modèle | D1 /40 | D2 /40 | D3 /52 | Train /36 | Calibration /30 | Test /66 |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for label in sorted(base, key=lambda n: (-base[n]["counts"]["correct"], n)):
        item = base[label]
        cells = [legacy._score(**{key: item["groups"][axis][group][key]
                                   for key in ("correct", "scored", "total")})
                 for axis, group in (("difficulty", "D1"), ("difficulty", "D2"), ("difficulty", "D3"),
                                     ("split", "train"), ("split", "calibration"), ("split", "test"))]
        lines.append("| " + label + " | " + " | ".join(cells) + " |")
    lines += ["", "## Ressources, latences et tokens", "",
              "Médiane / p95 (n) pour latences et tokens ; RSS worker max en Gio (n).",
              "Jev distant : RAM serveur non observée. Une passe CPU par nouveau candidat ;",
              "latences descriptives, sans débit ni garantie de service.", "",
              "| Modèle | Appareil / précision | RSS base max Gio | Base ms | Mastra ms | Tokens base | Tokens Mastra |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for label in sorted(base, key=lambda n: (-base[n]["counts"]["correct"], n)):
        b, m = base[label], mastra[label]
        identity = b["identity"]
        settings = identity.get("settings") or {}
        device = identity.get("device") or settings.get("device") or "distant/inconnu"
        if "backbone_dtype" in settings and "readout_dtype" in settings:
            precision = f"backbone {settings['backbone_dtype']}, readout {settings['readout_dtype']}"
        else:
            precision = settings.get("dtype") or "non observée"
        rss = "non observée" if label == "Jev" else legacy._rss_peak(b.get("worker_rss_mib"))
        lines.append("| " + " | ".join((label, f"{device} / {precision}", rss,
                     legacy._metric(b.get("timing", {}).get("successful_adapter_ms")),
                     legacy._metric(m.get("timing", {}).get("successful_adapter_ms")),
                     legacy._metric(b.get("measurements", {}).get("native_tokens", {}).get("max_sequence_tokens")),
                     legacy._metric(m.get("measurements", {}).get("native_tokens", {}).get("max_sequence_tokens")))) + " |")
    lines += ["", "## Provenance", "",
              f"- Manifeste de l'overview 19 modèles, SHA-256 : `{historical_hash}`.",
              f"- Nouvel agrégat, SHA-256 : `{current_hash}` ; producteur : `analyze-model-comparison.py`.",
              f"- Producteur de cette synthèse, SHA-256 : `{producer_hash}`.",
              f"- Six archives nouvelles scellées et contrôlées : {', '.join(row['archive'] for row in archives)}.",
              "- Les 19 agrégats historiques sont copiés depuis les exports épinglés sans rejeu ni rescore.",
              "- Les références et dénominateurs restent exploratoires ; aucune qualification produit.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-json", type=Path, required=True)
    parser.add_argument("--historical-json", type=Path, required=True,
                        help="Frozen 19-model overview manifest.json")
    parser.add_argument("--archive-root", type=Path, required=True,
                        help="Directory containing the six new sealed campaign directories")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    frozen, pins = historical(args.historical_json)
    current, current_hash = read_json(args.current_json)
    base, mastra, new = compose(current, frozen)
    archives = verify_archives(new, args.archive_root)
    target = args.output_dir.absolute()
    require(not target.exists() and not target.is_symlink(), "output destination already exists")
    for source in (args.current_json.parent, args.historical_json.parent):
        require(not target.resolve().is_relative_to(source.resolve()),
                "output destination must be separate from JSON sources")
    require(target.resolve() != args.archive_root.resolve() and
            all(not target.resolve().is_relative_to(args.archive_root.resolve() / row["archive"])
                for row in archives),
            "output destination overlaps a source archive")
    producer_hash = sha(Path(__file__).read_bytes())
    report = render(base, mastra, current_hash=current_hash,
                    historical_hash=pins["manifest_sha256"], producer_hash=producer_hash,
                    archives=archives)
    require(sha(args.current_json.read_bytes()) == current_hash
            and sha(args.historical_json.read_bytes()) == pins["manifest_sha256"]
            and sha(Path(__file__).read_bytes()) == producer_hash,
            "composition source changed before output")
    manifest = {"schema_version": "deposium.composed-larger-cpu-comparison/v1",
                "scope": "new_sealed_archives_plus_frozen_historical_aggregates",
                "models": len(base), "current_json_sha256": current_hash,
                "historical_manifest_sha256": pins["manifest_sha256"],
                "historical_analysis_sha256": pins["analysis_sha256"],
                "historical_sol_sha256": pins["sol_sha256"],
                "new_archives": archives, "producer_sha256": producer_hash,
                "report_sha256": sha(report.encode("utf-8"))}
    target.mkdir(parents=True, exist_ok=False)
    with (target / "report.md").open("x", encoding="utf-8") as f:
        f.write(report)
    with (target / "manifest.json").open("x", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CompositionError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"composition refused: {exc}") from None
