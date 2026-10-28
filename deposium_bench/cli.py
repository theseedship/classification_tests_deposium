"""CLI for offline preflight, controls and explicit component campaigns."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .git_inventory import InventoryError
from .preflight import build_preflight, render_summary, write_manifest
from .registry import RegistryError, load_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Préflight et campagnes du banc de décisions Deposium.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-registry", help="Valider le registre sans stack.")
    validate.add_argument("--registry", help="Registre JSON alternatif.")
    # Internal source-audit tools are available only with the ignored local bundle.
    private_catalog = (Path(__file__).with_name("decisions.py").is_file()
                       and (Path(__file__).parent / "data/decision-registry.json").is_file())
    if private_catalog:
        decisions = commands.add_parser("validate-decisions", help="Valider les décisions et leur couverture sans inférence.")
        decisions.add_argument("--decisions", help="Registre de décisions JSON alternatif.")
        decisions.add_argument("--registry", help="Registre de stack JSON alternatif.")
        decisions.add_argument("--stack-root", help="Comparer explicitement les sources locales aux empreintes auditées.")
        decisions.add_argument("--external-root", action="append", default=[], metavar="ID=PATH",
                               help="Racine Git externe explicite pour la vérification des sources; répétable.")
        catalog = commands.add_parser("decision-catalog", help="Afficher le catalogue Markdown issu du registre validé.")
        catalog.add_argument("--decisions", help="Registre de décisions JSON alternatif.")
        catalog.add_argument("--registry", help="Registre de stack JSON alternatif.")
    preflight = commands.add_parser("preflight", help="Inspecter une stack locale sans l'exécuter.")
    preflight.add_argument("--stack-root", required=True, help="Racine Git de deposium_fullstack.")
    preflight.add_argument("--registry", help="Registre JSON alternatif.")
    preflight.add_argument("--component", action="append", dest="components", help="ID à inspecter; option répétable.")
    preflight.add_argument("--output", help="Nouveau manifeste JSON; refuse tout écrasement.")
    preflight.add_argument("--format", choices=("text", "json"), default="text")
    preflight.add_argument("--strict", action="store_true", help="Échouer aussi sur les avertissements de provenance.")
    cases = commands.add_parser("validate-cases", help="Valider le corpus sans exécuter de candidat.")
    cases.add_argument("--dataset", help="Corpus JSONL alternatif.")
    graph_validate = commands.add_parser("validate-graph-review", help="Valider les 16 gabarits FR/EN sans corpus privé.")
    graph_prepare = commands.add_parser("prepare-graph-review", help="Préparer les références privées sans modèle ni score.")
    for command in (graph_validate, graph_prepare):
        command.add_argument("--dataset", help="Gabarits graph-document-review/v0 alternatifs.")
    graph_prepare.add_argument("--packet", required=True, help="Paquet documentaire privé dans un dossier ignoré.")
    graph_prepare.add_argument("--output", required=True, help="Nouvelle archive privée sous results/.")
    graph_audit = commands.add_parser("audit-graph-snapshot", help="Vérifier hors ligne une capture privée; aucun score de qualité.")
    graph_audit.add_argument("--archive", required=True, help="Répertoire de capture locale, sans accès au service.")
    graph_compare = commands.add_parser("compare-graph-contracts", help="Vrais services MCPs avant/après #805 sur DuckDB synthétique isolé.")
    graph_compare.add_argument("--mcps-root", required=True)
    graph_compare.add_argument("--output", required=True)
    graph_compare.add_argument("--before", help="SHA complet, défaut parent de #805.")
    graph_compare.add_argument("--after", help="SHA complet, défaut #805.")
    graph_compare.add_argument("--repetitions", type=int, default=1)
    graph_compare.add_argument("--max-seconds", type=int, default=300)
    graph_documents = commands.add_parser("observe-graph-documents", help="Observer les vrais services sur la capture privée; aucun score documentaire.")
    graph_documents.add_argument("--mcps-root", required=True)
    graph_documents.add_argument("--archive", required=True, help="Capture source privée auditée.")
    graph_documents.add_argument("--plan", required=True, help="Appels figés sans annotations.")
    graph_documents.add_argument("--output", required=True, help="Nouvelle archive sous results/.")
    graph_documents.add_argument("--repetitions", type=int, default=1)
    graph_documents.add_argument("--max-seconds", type=int, default=300)
    graph_documents.add_argument("--candidate-revision", help="SHA complet d'un correctif candidat; baseline #805 et nouvelles archives obligatoires.")
    graph_evidence = commands.add_parser("prepare-graph-evidence-review", help="Relier les arêtes observées aux pages privées pour revue humaine, sans score.")
    graph_evidence.add_argument("--archive", required=True, help="Capture source privée auditée.")
    graph_evidence.add_argument("--observation", required=True, help="Archive scellée d'observation graphe.")
    graph_evidence.add_argument("--output", required=True, help="Nouveau dossier privé sous results/.")
    graph_evidence.add_argument("--arm", choices=("before", "after"), default="after")
    graph_measurement = commands.add_parser("measure-graph-proposals", help="Mesurer la récupération des références proposées dans des observations scellées.")
    graph_measurement.add_argument("--archive", required=True)
    graph_measurement.add_argument("--observation", action="append", required=True, metavar="LABEL=PATH")
    graph_measurement.add_argument("--output", required=True)
    mastra_validate = commands.add_parser("validate-mastra-read", help="Valider les cas de revue Mastra sans inférence.")
    mastra_prepare = commands.add_parser("prepare-mastra-read", help="Exporter les entrées candidat sans annotations.")
    for command in (mastra_validate, mastra_prepare):
        command.add_argument("--dataset", help="Corpus Mastra review/v0 alternatif.")
    mastra_prepare.add_argument("--output", required=True, help="Nouveau répertoire de préparation.")
    mastra_check = commands.add_parser("check-mastra-read", help="Vrais wrappers MCPs sur backends simulés ; aucun modèle.")
    mastra_check.add_argument("--mcps-root", required=True)
    mastra_check.add_argument("--revision", required=True, help="Commit complet des sources, sans exécuter le WIP local.")
    mastra_check.add_argument("--output", required=True, help="Nouvelle archive de contrôles techniques.")
    mastra_capture = commands.add_parser("capture-mastra-planner", help="Capturer le planner natif avec fournisseur simulé, sans modèle réel.")
    mastra_capture.add_argument("--mcps-root", required=True)
    mastra_capture.add_argument("--revision", required=True)
    mastra_capture.add_argument("--output", required=True)
    mastra_observe = commands.add_parser("observe-mastra-read", help="Observation d'un candidat ; local par défaut, références non approuvées.")
    mastra_observe.add_argument("--dataset")
    mastra_observe.add_argument("--profile", required=True)
    mastra_observe.add_argument("--output", required=True)
    mastra_observe.add_argument("--stack-root")
    mastra_observe.add_argument("--max-seconds", type=int, default=300)
    mastra_observe.add_argument("--allow-remote", action="store_true",
                               help="Autoriser explicitement Jev API sur les 24 cas synthétiques, avec son budget durable.")
    lengths = commands.add_parser("build-lengths", help="Générer les longueurs avec le tokenizer local, sans inférence.")
    lengths.add_argument("--dataset", required=True)
    lengths.add_argument("--profile", required=True)
    lengths.add_argument("--output", required=True)
    lengths.add_argument("--targets", nargs="+", type=int, default=[100, 250, 500, 1000, 2000, 4000, 8000])
    lengths.add_argument("--positions", nargs="+", choices=("start", "middle", "end"), default=["middle"])
    lengths.add_argument("--orders", nargs="+", choices=("original", "reversed"), default=["original"])
    analysis = commands.add_parser("analyze-context", help="Analyser une archive par domaine et longueur, sans inférence.")
    analysis.add_argument("--archive", required=True)
    analysis.add_argument("--output", required=True)
    timing = commands.add_parser("benchmark-timing", help="Mesures explicites répétées; candidats chargés séquentiellement.")
    timing.add_argument("--dataset", required=True)
    timing.add_argument("--profile", required=True, action="append", dest="profiles")
    timing.add_argument("--output", required=True)
    timing.add_argument("--stack-root")
    timing.add_argument("--launches", type=int, default=3)
    timing.add_argument("--warmup", type=int, default=5)
    timing.add_argument("--passes", type=int, default=10)
    run = commands.add_parser("run", help="Exécuter une campagne explicite dans une nouvelle archive.")
    run.add_argument("--dataset", help="Corpus JSONL; défaut : decisions-v1.")
    run.add_argument("--profile", required=True, help="Profil candidat JSON.")
    run.add_argument("--stack-root", help="Stack locale pour le bridge MCPs.")
    run.add_argument("--max-new-cases", type=int, help="Arrêt contrôlé après N nouveaux résultats.")
    resume = commands.add_parser("resume", help="Compléter les cas sans trace dans une archive dérivée.")
    resume.add_argument("--archive", required=True)
    resume.add_argument("--stack-root")
    resume.add_argument("--max-new-cases", type=int)
    rescore = commands.add_parser("rescore", help="Rescorer une archive sans appeler de candidat.")
    rescore.add_argument("--archive", required=True)
    compare = commands.add_parser("compare", help="Comparer deux archives sans nouvelle inférence.")
    compare.add_argument("--baseline", required=True, help="Archive d'un replay de composant ou d'un modèle isolé.")
    compare.add_argument("--candidate", required=True, help="Archive du modèle isolé.")
    for command in (run, resume, rescore, compare):
        command.add_argument("--output", required=True, help="Nouveau répertoire d'archive.")
        command.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        if args.command == "measure-graph-proposals":
            from .graph_measurement import measure_graph_proposals
            observations = {}
            for item in args.observation:
                label, separator, path = item.partition("=")
                if not separator or not label.strip() or not path.strip() or label in observations:
                    raise ValueError("graph measurement: use distinct LABEL=PATH observations")
                observations[label] = path
            summary = measure_graph_proposals(args.archive, observations, args.output)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0
        if args.command == "prepare-graph-evidence-review":
            from .graph_evidence import prepare_graph_evidence_review
            summary = prepare_graph_evidence_review(args.archive, args.observation, args.output, arm=args.arm)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            # A prepared review is not a documentary accuracy qualification.
            return 0
        if args.command == "observe-graph-documents":
            from .graph_document import observe_graph_documents
            summary = observe_graph_documents(args.mcps_root, args.archive, args.plan, args.output,
                                               repetitions=args.repetitions, max_seconds=args.max_seconds,
                                               candidate_revision=args.candidate_revision)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            # Only completion of observations, never an accuracy PASS.
            return 0 if (summary["completion_status"] == "complete" and summary["observed_executions"] > 0
                         and all(a["transport_statuses"].get("ok", 0) == a["expected"] for a in summary["arms"].values())) else 1
        if args.command == "audit-graph-snapshot":
            from .graph_snapshot import audit_graph_snapshot
            report = audit_graph_snapshot(args.archive)
            print(json.dumps(report["public_summary"], ensure_ascii=False, indent=2))
            return 0 if report["status"] == "archive_consistent" else 1
        if args.command in {"validate-graph-review", "prepare-graph-review"}:
            from .graph_review import TEMPLATES, load_graph_templates, materialize_graph_review
            if args.command == "prepare-graph-review":
                summary = materialize_graph_review(args.packet, args.output, args.dataset or TEMPLATES)
            else:
                rows, digest = load_graph_templates(args.dataset or TEMPLATES)
                summary = {"structure_status": "valid", "cases_total": len(rows),
                           "families_total": len({row["family_id"] for row in rows}),
                           "template_sha256": digest, "references_resolved": 0, "cases_scored": 0,
                           "corpus_qualified": False, "evaluation_status": "not_run"}
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            # Exit success means a valid preparation, never a qualification PASS.
            return 0
        if args.command == "compare-graph-contracts":
            from .graph_comparison import AFTER, BEFORE, compare_graph_contracts
            summary = compare_graph_contracts(args.mcps_root, args.output, before=args.before or BEFORE,
                                              after=args.after or AFTER, repetitions=args.repetitions,
                                              max_seconds=args.max_seconds)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0 if (summary["completion_status"] == "complete" and summary["observed_executions"] > 0
                         and all(arm["contract_checks_passed"] == arm["expected"] for arm in summary["arms"].values())) else 1
        if args.command == "observe-mastra-read":
            from .mastra_observation import observe_local
            from .mastra_pilot import DATASET
            summary = observe_local(args.dataset or DATASET, args.profile, args.output,
                                    stack_root=args.stack_root, max_seconds=args.max_seconds,
                                    allow_remote=args.allow_remote)
            print(json.dumps({key: summary[key] for key in ("completion_status", "stop_reason", "metrics")},
                             ensure_ascii=False, indent=2))
            # Completion describes the pass; at least one valid decision is
            # needed for technical success, independently of agreement.
            return 0 if (summary["completion_status"] == "complete"
                         and summary["metrics"]["coverage"]["valid_decisions"] > 0) else 1
        if args.command in {"validate-mastra-read", "prepare-mastra-read", "check-mastra-read", "capture-mastra-planner"}:
            from .mastra_pilot import DATASET, prepare_review, review_summary, run_native_controls
            if args.command == "validate-mastra-read":
                summary = review_summary(args.dataset or DATASET)
            elif args.command == "prepare-mastra-read":
                summary = prepare_review(args.dataset or DATASET, args.output)
            else:
                summary = run_native_controls(args.mcps_root, args.revision, args.output,
                                              planner=args.command == "capture-mastra-planner")
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 1 if summary.get("contract_status") == "failed" else 0
        if private_catalog and args.command in {"validate-decisions", "decision-catalog"}:
            from .decisions import check_sources, decision_summary, load_decisions, render_catalog
            value, digest = load_decisions(args.decisions, stack_registry_path=args.registry)
            if args.command == "decision-catalog":
                print(render_catalog(value), end="")
                return 0
            summary = decision_summary(value, digest)
            external_roots = {}
            for item in args.external_root:
                key, separator, path = item.partition("=")
                if not separator or not key or not path or key in external_roots:
                    raise RegistryError("external root: expected unique ID=PATH")
                external_roots[key] = Path(path)
            if external_roots and not args.stack_root:
                raise RegistryError("external root requires --stack-root")
            if args.stack_root:
                summary["source_check"] = check_sources(value, args.stack_root, external_roots=external_roots)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0 if not args.stack_root or summary["source_check"]["status"] == "matched" else 1
        if args.command == "build-lengths":
            from .lengths import build_lengths
            result = build_lengths(args.dataset, args.profile, args.output, targets=args.targets,
                                   positions=args.positions, orders=args.orders)
            print(json.dumps({key: result[key] for key in
                              ("case_count", "eligible_cases", "families", "targets", "evaluation_status")}, indent=2))
            return 0
        if args.command == "analyze-context":
            from .context_analysis import analyze_context
            analyze_context(args.archive, args.output)
            print(json.dumps({"report": str(Path(args.output) / "report.md")}, indent=2))
            return 0
        if args.command == "benchmark-timing":
            from .timing import benchmark_timing
            summary = benchmark_timing(args.dataset, args.profiles, args.output, stack_root=args.stack_root,
                                       launches=args.launches, warmup=args.warmup, passes=args.passes)
            print(json.dumps({"report": str(Path(args.output) / "report.md"),
                              "completion_status": summary["completion_status"]}, indent=2))
            return 130 if summary["completion_status"] == "interrupted" else 0 if summary["completion_status"] == "complete" else 1
        if args.command == "validate-registry":
            registry, digest = load_registry(args.registry)
            print(json.dumps({"schema_version": registry["schema_version"], "status": "valid",
                              "components": len(registry["components"]),
                              "contracts": sum(len(c["contracts"]) for c in registry["components"]),
                              "sha256": digest, "evaluation_status": "not_run"}, indent=2))
            return 0
        if args.command == "compare":
            from .comparison import compare_campaigns
            summary = compare_campaigns(args.baseline, args.candidate, args.output)
            print(json.dumps(summary if args.format == "json" else {
                "comparison_status": summary["comparison_status"], "counts": summary["counts"],
                "report": str(Path(args.output) / "report.md"),
            }, ensure_ascii=False, indent=2))
            return 0 if summary["counts"]["paired_scored_cases"] else 2
        if args.command in {"validate-cases", "run", "resume", "rescore"}:
            from .cases import DEFAULT_DATASET, load_cases
            from .campaigns import render_report, rescore_campaign, resume_campaign, run_campaign
            if args.command == "validate-cases":
                dataset, digest = load_cases(args.dataset)
                print(json.dumps({"status": "valid", "cases": len(dataset), "sha256": digest,
                                  "packs": sorted({case["pack"] for case in dataset}),
                                  "languages": sorted({case["language"] for case in dataset}),
                                  "evaluation_status": "not_run"}, indent=2))
                return 0
            if args.command == "run":
                summary = run_campaign(args.dataset or DEFAULT_DATASET, args.profile, args.output,
                                       stack_root=args.stack_root, max_new_cases=args.max_new_cases)
            elif args.command == "resume":
                summary = resume_campaign(args.archive, args.output, stack_root=args.stack_root,
                                          max_new_cases=args.max_new_cases)
            else:
                summary = rescore_campaign(args.archive, args.output)
            print(json.dumps(summary, ensure_ascii=False, indent=2) if args.format == "json"
                  else render_report(summary), end="\n")
            if summary["completion_status"] == "interrupted":
                return 130
            verdict = summary["metrics"]["verdict"]
            return 2 if verdict == "invalid" else 0 if verdict == "pass" and summary["completion_status"] == "complete" else 1
        manifest = build_preflight(args.stack_root, registry_path=args.registry,
                                   selected_components=args.components)
        if args.output:
            write_manifest(manifest, args.output)
        if args.format == "json":
            print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(render_summary(manifest), end="")
        return 2 if manifest["status"] == "invalid" or (args.strict and manifest["status"] != "ok") else 0
    except FileExistsError:
        print("error: output already exists; choose a new archive path", file=sys.stderr)
    except (RegistryError, InventoryError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
    except OSError:
        print("error: unable to read or write a local file", file=sys.stderr)
    return 2
