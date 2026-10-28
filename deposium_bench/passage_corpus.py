"""Deterministic synthetic passage fixtures; importing performs no I/O.

All linguistic references are authored by an agent and await human review.
The generator encodes authored judgments, not a semantic annotation oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import unicodedata

LANGUAGES = ("fr", "en", "de", "es", "it", "pt")
DIRECTIONS = tuple((lang, lang) for lang in LANGUAGES) + (("fr", "en"), ("en", "fr"))
ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datasets" / "passage-evidence-v1"
SCENARIOS = (
    "component_relation_collision", "variant_scope", "unit_condition_collision",
    "negation_exception", "distributed_binding", "missing_evidence",
    "conflicting_evidence", "heading_value_truncation",
)
SPLITS = ("train", "calibration", "test")


def _six(*values: str) -> dict[str, str]:
    return dict(zip(LANGUAGES, values, strict=True))


# Six explicit semantic parallels per field. Labels are invented catalog fields,
# not actual document titles, private entities, file IDs or production passages.
FIELDS = (
    (_six("rebond avant", "front rebound", "Rückprall vorn", "rebote delantero", "rimbalzo anteriore", "retorno dianteiro"),
     _six("rebond arrière", "rear rebound", "Rückprall hinten", "rebote trasero", "rimbalzo posteriore", "retorno traseiro"),
     _six("compression avant", "front compression", "Kompression vorn", "compresión delantera", "compressione anteriore", "compressão dianteira")),
    (_six("réserve du quai nord", "north dock reserve", "Reserve am Nordkai", "reserva del muelle norte", "riserva del molo nord", "reserva do cais norte"),
     _six("réserve du quai sud", "south dock reserve", "Reserve am Südkai", "reserva del muelle sur", "riserva del molo sud", "reserva do cais sul"),
     _six("débit du quai nord", "north dock throughput", "Durchsatz am Nordkai", "caudal del muelle norte", "flusso del molo nord", "fluxo do cais norte")),
    (_six("plafond du fonds cuivre", "copper fund ceiling", "Obergrenze des Kupferfonds", "límite del fondo cobre", "massimale del fondo rame", "limite do fundo cobre"),
     _six("plafond du fonds étain", "tin fund ceiling", "Obergrenze des Zinnfonds", "límite del fondo estaño", "massimale del fondo stagno", "limite do fundo estanho"),
     _six("plancher du fonds cuivre", "copper fund floor", "Untergrenze des Kupferfonds", "mínimo del fondo cobre", "minimo del fondo rame", "mínimo do fundo cobre")),
)
GENERIC_FIELDS = (
    _six("seuil de contrôle", "inspection threshold", "Prüfschwelle", "umbral de inspección", "soglia di controllo", "limiar de inspeção"),
    _six("délai de livraison", "delivery interval", "Lieferfrist", "plazo de entrega", "intervallo di consegna", "prazo de entrega"),
    _six("réserve comptable", "accounting reserve", "Buchungsreserve", "reserva contable", "riserva contabile", "reserva contabilística"),
)
ALT_FIELDS = (
    _six("seuil de nettoyage", "cleaning threshold", "Reinigungsschwelle", "umbral de limpieza", "soglia di pulizia", "limiar de limpeza"),
    _six("délai de stockage", "storage interval", "Lagerfrist", "plazo de almacenamiento", "intervallo di stoccaggio", "prazo de armazenamento"),
    _six("réserve fiscale", "tax reserve", "Steuerrücklage", "reserva fiscal", "riserva fiscale", "reserva fiscal"),
)
UNITS = (
    _six("crans", "steps", "Stufen", "pasos", "scatti", "passos"),
    _six("caisses", "crates", "Kisten", "cajas", "casse", "caixas"),
    _six("jetons", "tokens", "Marken", "fichas", "gettoni", "fichas"),
)
NEUTRAL = _six(
    "Cette fiche fictive décrit un catalogue de travail. Les lignes de présentation indiquent uniquement comment lire les noms et les rubriques. Elles ne donnent aucun résultat de mesure, aucune exception et aucune valeur à retenir. ",
    "This fictional sheet describes a working catalog. Its introductory lines only explain how to read the names and sections. They provide no measurement result, exception, or value to retain. ",
    "Dieses fiktive Blatt beschreibt einen Arbeitskatalog. Die einleitenden Zeilen erklären nur, wie Namen und Rubriken zu lesen sind. Sie enthalten kein Messergebnis, keine Ausnahme und keinen maßgeblichen Wert. ",
    "Esta ficha ficticia describe un catálogo de trabajo. Las líneas introductorias solo explican cómo leer los nombres y las secciones. No aportan resultados de medición, excepciones ni valores que deban conservarse. ",
    "Questa scheda fittizia descrive un catalogo di lavoro. Le righe introduttive spiegano soltanto come leggere i nomi e le sezioni. Non forniscono risultati di misurazione, eccezioni o valori da conservare. ",
    "Esta ficha fictícia descreve um catálogo de trabalho. As linhas introdutórias apenas explicam como ler os nomes e as secções. Não apresentam resultados de medição, exceções ou valores a reter. ",
)


def _fact(lang: str, entity: str, field: str, value: int, unit: str, style: int) -> str:
    templates = (
        _six("La fiche de {e} indique pour « {f} » une valeur de {v} {u}.",
             "The sheet for {e} gives a value of {v} {u} for “{f}”.",
             "Das Blatt für {e} nennt für „{f}“ folgenden Wert: {v} {u}.",
             "La ficha de {e} indica un valor de {v} {u} para «{f}».",
             "La scheda di {e} indica un valore di {v} {u} per «{f}».",
             "A ficha de {e} indica um valor de {v} {u} para «{f}»."),
        _six("Pour {e}, la rubrique « {f} » est fixée à {v} {u}.",
             "For {e}, the “{f}” entry is set to {v} {u}.",
             "Für {e} ist der Eintrag „{f}“ auf {v} {u} festgelegt.",
             "Para {e}, la entrada «{f}» se fija en {v} {u}.",
             "Per {e}, la voce «{f}» è fissata a {v} {u}.",
             "Para {e}, a entrada «{f}» está fixada em {v} {u}."),
        _six("Dans le registre de {e}, {v} {u} correspond à « {f} ».",
             "In the register for {e}, {v} {u} corresponds to “{f}”.",
             "Im Register für {e} entsprechen {v} {u} dem Eintrag „{f}“.",
             "En el registro de {e}, {v} {u} corresponde a «{f}».",
             "Nel registro di {e}, {v} {u} corrisponde a «{f}».",
             "No registo de {e}, {v} {u} corresponde a «{f}»."),
    )
    return templates[style][lang].format(e=entity, f=field, v=value, u=unit)


def _question(lang: str, entity: str, field: str) -> str:
    return _six(
        "Quelle valeur est indiquée pour « {f} » dans la fiche de {e} ?",
        "What value is given for “{f}” in the sheet for {e}?",
        "Welcher Wert wird im Blatt für {e} für „{f}“ angegeben?",
        "¿Qué valor indica la ficha de {e} para «{f}»?",
        "Quale valore indica la scheda di {e} per «{f}»?",
        "Que valor indica a ficha de {e} para «{f}»?",
    )[lang].format(e=entity, f=field)


def _condition(lang: str, field: str, temperature: int) -> str:
    return _six("{f} à {t} °C", "{f} at {t} °C", "{f} bei {t} °C",
                "{f} a {t} °C", "{f} a {t} °C", "{f} a {t} °C")[lang].format(f=field, t=temperature)


def _exception(lang: str, entity: str, zone: str, applies: bool) -> str:
    templates = (
        _six("La règle de {e} s'applique dans la zone « {z} ».",
             "The rule for {e} applies in zone “{z}”.",
             "Die Regel für {e} gilt in der Zone „{z}“.",
             "La regla de {e} se aplica en la zona «{z}».",
             "La regola di {e} si applica nella zona «{z}».",
             "A regra de {e} aplica-se na zona «{z}»."),
        _six("La règle de {e} ne s'applique pas dans la zone « {z} » : cette zone constitue une exception explicite.",
             "The rule for {e} does not apply in zone “{z}”: this zone is an explicit exception.",
             "Die Regel für {e} gilt nicht in der Zone „{z}“: Diese Zone ist eine ausdrückliche Ausnahme.",
             "La regla de {e} no se aplica en la zona «{z}»: esta zona es una excepción explícita.",
             "La regola di {e} non si applica nella zona «{z}»: questa zona è un'eccezione esplicita.",
             "A regra de {e} não se aplica na zona «{z}»: esta zona é uma exceção explícita."),
    )
    return templates[0 if applies else 1][lang].format(e=entity, z=zone)


def _authored_world(scenario: int, world: int, lang: str) -> dict:
    """Construct one authored parallel, including its explicit annotation plan."""
    # Rotate lexical domains and sentence styles so neither is tied to a split.
    world = (world + scenario) % 3
    names = (("Neravel", "Orvila", "Tessuron"), ("Caldrin", "Vespara", "Molven"),
             ("Seldora", "Quenval", "Firavo"), ("Belnis", "Dovara", "Ilvane"),
             ("Merova", "Peldrin", "Zanora"), ("Ruvane", "Tilvora", "Selvique"),
             ("Avrelis", "Noldara", "Prenval"), ("Velcora", "Aldiven", "Corlune"))
    entity = names[scenario][world]
    value = 29 + scenario * 11 + world * 7
    other = value + 13
    field = GENERIC_FIELDS[world][lang]
    alt = ALT_FIELDS[world][lang]
    unit = UNITS[world][lang]
    if world == 1 and scenario != 0:
        unit = _six("jours", "days", "Tage", "días", "giorni", "dias")[lang]
    if scenario == 0:
        field, alt, relation = (part[lang] for part in FIELDS[world])
    else:
        relation = alt
    subject = entity + " R" if scenario == 1 else entity
    query = _question(lang, subject, field)
    claim = _fact(lang, subject, field, value, unit, world)
    texts = [claim, _fact(lang, subject, alt, value, unit, world),
             _fact(lang, subject, relation, other, unit, world),
             _fact(lang, entity + " Z", alt, other + 19, unit, world)]
    roles = ["direct", "wrong_component", "wrong_relation", "unrelated"]
    grades = [3, 1, 1, 0]
    judgments = ["supports", "insufficient", "insufficient", "insufficient"]
    sufficient = [[0]]
    status = "answerable"
    evidence = [claim, None, None, None]
    relevance_evidence = None
    if scenario == 1:
        texts[1] = _fact(lang, entity, field, value, unit, world)
        texts[2] = _fact(lang, entity + " S", field, other, unit, world)
        roles[1:3] = ["base_variant", "sibling_variant"]
    elif scenario == 2:
        field = _condition(lang, field, 16 + world)
        query = _question(lang, entity, field)
        unit = _six("secondes", "seconds", "Sekunden", "segundos", "secondi", "segundos")[lang]
        claim = _fact(lang, entity, field, value, unit, world)
        texts[0] = claim
        texts[1] = _fact(lang, entity, alt, value,
                         _six("minutes", "minutes", "Minuten", "minutos", "minuti", "minutos")[lang], world)
        texts[2] = _fact(lang, entity, _condition(lang, GENERIC_FIELDS[world][lang], 27 + world), value, unit, world)
        roles[1:3] = ["wrong_quantity_and_unit", "wrong_condition"]
        evidence[0] = claim
    elif scenario == 3:
        zone = ("Doria", "Lunet", "Sarva")[world]
        query = _six("La règle de {e} s'applique-t-elle dans la zone « {z} » ?",
                     "Does the rule for {e} apply in zone “{z}”?",
                     "Gilt die Regel für {e} in der Zone „{z}“?",
                     "¿Se aplica la regla de {e} en la zona «{z}»?",
                     "La regola di {e} si applica nella zona «{z}»?",
                     "A regra de {e} aplica-se na zona «{z}»?")[lang].format(e=entity, z=zone)
        claim = _exception(lang, entity, zone, False)
        texts = [claim, _exception(lang, entity, zone + "-Est", True),
                 _exception(lang, entity + " Z", zone, True), texts[3]]
        roles = ["explicit_exception", "other_zone", "other_rule", "unrelated"]
        evidence[0] = claim
    elif scenario == 4:
        batch = ("Lorim", "Talven", "Esvora")[world]
        binding = _six("Le lot {b} est affecté exclusivement à {e}.",
                       "Batch {b} is assigned exclusively to {e}.",
                       "Die Charge {b} ist ausschließlich {e} zugeordnet.",
                       "El lote {b} está asignado exclusivamente a {e}.",
                       "Il lotto {b} è assegnato esclusivamente a {e}.",
                       "O lote {b} está atribuído exclusivamente a {e}.")[lang].format(b=batch, e=entity)
        measurement = _fact(lang, batch, field, value, unit, world)
        query = _six("Quel lot est affecté à {e}, et quelle valeur indique sa rubrique « {f} » ?",
                     "Which batch is assigned to {e}, and what value does its “{f}” entry give?",
                     "Welche Charge ist {e} zugeordnet, und welchen Wert nennt ihr Eintrag „{f}“?",
                     "¿Qué lote está asignado a {e} y qué valor indica su entrada «{f}»?",
                     "Quale lotto è assegnato a {e} e quale valore indica la sua voce «{f}»?",
                     "Que lote está atribuído a {e} e que valor indica a sua entrada «{f}»?")[lang].format(e=entity, f=field)
        claim = binding + " " + measurement
        texts = [binding, measurement, _fact(lang, entity + " Z", field, value, unit, world), texts[3]]
        roles = ["binding_premise", "value_premise", "other_subject", "unrelated"]
        grades = [2, 2, 1, 0]
        judgments = ["insufficient"] * 4
        evidence = [None] * 4
        sufficient = [[0, 1]]
    elif scenario == 5:
        # The requested subject/field is absent. This licenses no global absence claim.
        texts[0] = _fact(lang, entity, alt, other, unit, world)
        texts[1] = _fact(lang, entity + " Z", field, value, unit, world)
        texts[2] = _fact(lang, entity + " S", field, other, unit, world)
        roles = ["other_field", "other_subject_same_number", "other_subject", "unrelated"]
        grades = [1, 1, 1, 0]
        judgments = ["insufficient"] * 4
        evidence = [None] * 4
        sufficient = []
        status = "insufficient_visible_evidence"
    elif scenario == 6:
        denial = _six("Pour {e}, la valeur de « {f} » n'est pas {v} {u}.",
                      "For {e}, the value of “{f}” is not {v} {u}.",
                      "Für {e} beträgt der Wert von „{f}“ nicht {v} {u}.",
                      "Para {e}, el valor de «{f}» no es {v} {u}.",
                      "Per {e}, il valore di «{f}» non è {v} {u}.",
                      "Para {e}, o valor de «{f}» não é {v} {u}.")[lang].format(e=entity, f=field, v=value, u=unit)
        texts[1] = _fact(lang, entity, field, other, unit, world) + " " + denial
        roles[1] = "explicit_conflict"
        grades[1] = 3
        judgments[1] = "refutes"
        evidence[1] = texts[1]
        sufficient = []
        status = "conflicting_visible_evidence"
    elif scenario == 7:
        heading = _six("Rubrique du registre", "Register entry", "Registereintrag",
                       "Entrada del registro", "Voce del registro", "Entrada do registo")[lang]
        # Fixed head projection, independent of gold; the first 384 code points
        # contain only neutral prose in every language.
        relevance_evidence = list(texts)
        texts = [NEUTRAL[lang] * 4 + "\n\n" + heading + ": " + text for text in texts]
        roles[0] = "evidence_after_neutral_prefix"
    # Curated counterclaims are independent support tasks, never ranking inputs.
    # Their subject and scope match the direct evidence; only the designated
    # value, unit or polarity changes. No semantic label is inferred from digits.
    extra_claims = []
    if scenario in (0, 2, 3, 6):
        if scenario == 0:
            counterclaim = _fact(lang, subject, field, other, unit, world)
        elif scenario == 2:
            minutes = _six("minutes", "minutes", "Minuten", "minutos", "minuti", "minutos")[lang]
            counterclaim = _fact(lang, entity, field, value, minutes, world)
        elif scenario == 3:
            counterclaim = _exception(lang, entity, zone, True)
        else:
            counterclaim = _fact(lang, entity, field, other, unit, world)
        counter_judgments = ["refutes", "insufficient", "insufficient", "insufficient"]
        counter_evidence = [texts[0], None, None, None]
        if scenario == 6:
            counter_judgments[1] = "supports"
            counter_evidence[1] = texts[1]
        extra_claims.append({"text": counterclaim, "judgments": counter_judgments,
                             "evidence": counter_evidence})
    return {"query": query, "claim": claim, "texts": texts, "grades": grades,
            "roles": roles, "judgments": judgments, "evidence": evidence,
            "relevance_evidence": relevance_evidence or list(texts),
            "extra_claims": extra_claims,
            "sufficient": sufficient, "status": status}


def _id(*parts: object) -> str:
    return hashlib.sha256("\x1f".join(map(str, parts)).encode("utf-8")).hexdigest()[:24]


def _normalized(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def build_cases() -> list[dict]:
    """Return 1536 fixtures from 24 authored worlds, without file or network I/O."""
    cases = []
    for scenario, scenario_name in enumerate(SCENARIOS):
        for world, split in enumerate(SPLITS):
            family = "family-" + _id("family", scenario, world)
            for question_language, passage_language in DIRECTIONS:
                q = _authored_world(scenario, world, question_language)
                p = _authored_world(scenario, world, passage_language)
                for position in range(4):
                    order = [(index + position) % 4 for index in range(4)]
                    for view in ("full", "head_384"):
                        passages, relevance, judgments = [], [], []
                        visible = {}
                        ids = {index: _id("passage", scenario, world, index) for index in range(4)}
                        for index in order:
                            text = _normalized(p["texts"][index])
                            if view == "head_384":
                                text = text[:384]
                            visible[index] = text
                            passages.append({"id": ids[index],
                                             "document_id": _id("document", scenario, world, index),
                                             "text": text, "language": passage_language,
                                             "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
                            evidence = _normalized(p["evidence"][index]) if p["evidence"][index] else None
                            evidence_visible = evidence is not None and evidence in text
                            label = p["judgments"][index] if evidence_visible else "insufficient"
                            spans = []
                            if label != "insufficient":
                                start = text.index(evidence)
                                spans = [{"start": start, "end": start + len(evidence), "text": evidence}]
                            grade = p["grades"][index]
                            role = p["roles"][index]
                            relevance_visible = _normalized(p["relevance_evidence"][index]) in text
                            if grade > 0 and not relevance_visible:
                                grade, role = 0, "evidence_outside_visible_projection"
                            relevance.append({"passage_id": ids[index], "grade": grade, "role": role})
                            judgments.append({"passage_id": ids[index], "label": label, "spans": spans})
                        # Recompute availability from the exact visible projection,
                        # using authored evidence requirements rather than hidden facts.
                        sufficient = []
                        for required in p["sufficient"]:
                            if all(_normalized(p["texts"][index]) in visible[index] for index in required):
                                sufficient.append([ids[index] for index in required])
                        status = p["status"]
                        if status == "answerable" and not sufficient:
                            status = "insufficient_visible_evidence"
                        claims = [{"id": _id("claim", scenario, world), "text": _normalized(q["claim"]),
                                   "judgments": judgments}]
                        for counter_index, counter in enumerate(p["extra_claims"]):
                            counter_judgments = []
                            for index in order:
                                evidence = counter["evidence"][index]
                                evidence = _normalized(evidence) if evidence else None
                                label = counter["judgments"][index]
                                spans = []
                                if evidence is not None and evidence in visible[index]:
                                    start = visible[index].index(evidence)
                                    spans = [{"start": start, "end": start + len(evidence), "text": evidence}]
                                else:
                                    label = "insufficient"
                                counter_judgments.append({"passage_id": ids[index], "label": label, "spans": spans})
                            claims.append({"id": _id("counterclaim", scenario, world, counter_index),
                                           "text": _normalized(q["extra_claims"][counter_index]["text"]),
                                           "judgments": counter_judgments})
                        case_id = _id("case", scenario, world, question_language, passage_language, position, view)
                        cases.append({
                            "schema_version": "deposium.passage-case/v1", "case_id": case_id,
                            "family_id": family, "scenario_id": scenario_name, "split": split,
                            "question_language": question_language, "passage_language": passage_language,
                            "view": view, "query": _normalized(q["query"]), "passages": passages,
                            "annotations": {"review": "agent_only_pending_human", "query_status": status,
                                "relevance": relevance,
                                "claims": claims,
                                "minimal_evidence_sets": sufficient,
                                "rationale": ("Authored synthetic judgment. Resolve subject, field, relation, variant, unit and scope from visible text only. "
                                              "A conjunction needs both authored premises; absent retrieved evidence does not establish global absence.")},
                            "provenance": {"kind": "synthetic_authored", "producer_version": 1,
                                "annotation_method": "agent_authored_parallel_references_pending_human",
                                "source": "invented_entities_fields_and_numbers_only",
                                "position_rotation": position,
                                "projection": "full_text" if view == "full" else "first_384_python_codepoints_after_NFC",
                                "projection_is_application_runtime": False},
                        })
    return cases


def encode_cases(cases: list[dict]) -> bytes:
    return ("".join(json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                    for case in cases)).encode("utf-8")


def build_manifest(cases: list[dict]) -> dict:
    """Describe authored coverage and dependent observations without inference."""
    from collections import Counter
    payloads = [json.dumps({"query": case["query"], "passages": case["passages"]},
                           ensure_ascii=False, sort_keys=True) for case in cases]
    return {
        "schema_version": "deposium.passage-manifest/v1", "dataset_id": "passage-evidence-v1",
        "case_count": len(cases), "cases_sha256": hashlib.sha256(encode_cases(cases)).hexdigest(),
        "claim_count": sum(len(case["annotations"]["claims"]) for case in cases),
        "claim_judgment_counts": dict(Counter(judgment["label"] for case in cases
            for claim in case["annotations"]["claims"] for judgment in claim["judgments"])),
        "counterclaim_scenarios": [SCENARIOS[index] for index in (0, 2, 3, 6)],
        "family_count": len({case["family_id"] for case in cases}), "risk_class_count": len(SCENARIOS),
        "domains": ["technical_settings", "logistics", "finance", "fictional_regulatory_exceptions", "instrument_conditions"],
        "languages": list(LANGUAGES), "directions": [list(pair) for pair in DIRECTIONS],
        "split_counts": dict(Counter(case["split"] for case in cases)),
        "families_per_split": {split: len({case["family_id"] for case in cases if case["split"] == split}) for split in SPLITS},
        "scenario_counts": dict(Counter(case["scenario_id"] for case in cases)),
        "scenario_families": {scenario: sorted({case["family_id"] for case in cases if case["scenario_id"] == scenario}) for scenario in SCENARIOS},
        "view_counts": dict(Counter(case["view"] for case in cases)),
        "query_status_counts": dict(Counter(case["annotations"]["query_status"] for case in cases)),
        "duplicate_visible_payload_count": len(payloads) - len(set(payloads)),
        "review": "agent_only_pending_human", "human_reviewed": 0,
        "provenance": {"source": "synthetic_invented_only", "generation": "deterministic_stdlib_no_inference",
                       "producer": "deposium_bench/passage_corpus.py", "producer_version": 1,
                       "translation": "six_agent_authored_semantic_parallels_not_human_validated",
                       "private_document_inputs": False, "model_calls": 0, "service_calls": 0},
        "relevance_scale": {"3": "direct evidence resolving or refuting the requested fact",
                            "2": "partial evidence requiring another passage", "1": "related without resolving evidence", "0": "irrelevant to visible answer evidence"},
        "claim_scale": ["supports", "refutes", "insufficient"],
        "limitations": [
            "1536 observations derive from 24 authored worlds in eight risk classes, not 1536 independent facts.",
            "World families are disjoint across train/calibration/test; shared operation templates and phrasing remain across splits, so this is not structural-template-disjoint generalization.",
            "Synthetic references and six-language parallels are agent-only and pending human semantic and translation review.",
            "Four cyclic orders and translated queries are dependent controls; repeated observations must not inflate statistical sample size.",
            "head_384 is a counterfactual prefix projection in Unicode code points, not the actual MCPs query-window selector or a model token budget.",
            "Most full/head views are exact visible duplicates; duplicate_visible_payload_count records duplicates including view and translated-query controls.",
            "Numeric presence is not a subject-relation proof; distributed conjunctions have no individually supporting passage.",
            "No retrieved-candidate absence licenses global source absence; no exhaustive corpus absence task is included.",
            "Annotations encode explicit authored scenarios and exact visible spans; they are not an automatic semantic truth oracle.",
            "No model, retrieval recall, application integration, resource cost or product behavior has been measured.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Compare regeneration to committed bytes without writing.")
    group.add_argument("--overwrite", action="store_true", help="Explicitly overwrite both generated dataset files.")
    args = parser.parse_args()
    cases = build_cases()
    outputs = {"cases.jsonl": encode_cases(cases),
               "manifest.json": (json.dumps(build_manifest(cases), ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")}
    if args.check:
        for filename, payload in outputs.items():
            path = DATASET / filename
            if not path.is_file() or path.read_bytes() != payload:
                parser.exit(1, f"Dataset regeneration differs: {filename}\n")
        print(f"Dataset regeneration matches: {len(cases)} cases.")
        return
    if not args.overwrite and any((DATASET / filename).exists() for filename in outputs):
        parser.exit(2, "Dataset already exists; use --check or explicit --overwrite.\n")
    DATASET.mkdir(parents=True, exist_ok=True)
    for filename, payload in outputs.items():
        (DATASET / filename).write_bytes(payload)
    print(f"Wrote {len(cases)} synthetic cases across 24 authored worlds.")


if __name__ == "__main__":
    main()
