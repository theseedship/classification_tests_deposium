"""Finite contextual-choice fixtures and exact, deliberately restricted oracles.

Importing this module performs no I/O and loads no model. Documentary judgments
are agent references, not automatic proofs. Science checks cover the explicit
rules in each fixture; conservation does not establish chemical feasibility.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
import hashlib
import json
from math import gcd, lcm
from pathlib import Path
import re


LETTERS = ("a", "b", "c", "d")
TASKS = ("catalog", "stored_summaries", "retrieve_answer", "insufficient_information")
SCIENCE_LINKS = ["mcps.evidence-attribution", "turbov3.rerank"]


def _fraction(value):
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("An exact rational must be an integer or fraction string.")
    return Fraction(value)


def _rational(expression):
    if not isinstance(expression, dict):
        return _fraction(expression)
    if set(expression) != {"op", "args"} or len(expression["args"]) != 2:
        raise ValueError("Unsupported rational expression.")
    left, right = map(_rational, expression["args"])
    op = expression["op"]
    if op == "add":
        return left + right
    if op == "sub":
        return left - right
    if op == "mul":
        return left * right
    if op == "div":
        return left / right
    raise ValueError("Unsupported rational operation.")


def _op(op, left, right):
    return {"op": op, "args": [left, right]}


def _trim(poly):
    result = [_fraction(x) for x in poly]
    while len(result) > 1 and result[-1] == 0:
        result.pop()
    return result or [Fraction(0)]


def _add(left, right):
    size = max(len(left), len(right))
    return _trim([(left[i] if i < len(left) else 0) +
                  (right[i] if i < len(right) else 0) for i in range(size)])


def _multiply(left, right):
    result = [Fraction(0)] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            result[i + j] += a * b
    return _trim(result)


def _compose(outer, inner):
    result = [Fraction(0)]
    for coefficient in reversed(outer):
        result = _add(_multiply(result, inner), [coefficient])
    return result


def _divide(numerator, denominator):
    numerator, denominator = _trim(numerator), _trim(denominator)
    if denominator == [0]:
        raise ValueError("Zero polynomial divisor.")
    quotient = [Fraction(0)] * max(1, len(numerator) - len(denominator) + 1)
    remainder = numerator[:]
    while remainder != [0] and len(remainder) >= len(denominator):
        offset = len(remainder) - len(denominator)
        factor = remainder[-1] / denominator[-1]
        quotient[offset] += factor
        remainder = _add(remainder, [0] * offset + [-factor * x for x in denominator])
    return _trim(quotient), _trim(remainder)


def _poly_value(poly, x):
    result = Fraction(0)
    for coefficient in reversed(_trim(poly)):
        result = result * x + coefficient
    return result


def _strings(poly):
    return [str(x) for x in _trim(poly)]


def parse_formula(formula):
    """Count elements in bounded ordinary formulas, nested groups and hydrates.

    Charges are separate data, not parsed from an ambiguous formula suffix.
    This parser does not identify structures, isotopes, radicals or stability.
    """
    if not isinstance(formula, str) or not formula or len(formula) > 200:
        raise ValueError("Invalid chemical formula.")
    total = Counter()
    for part in formula.split("·"):
        tokens = re.findall(r"[A-Z][a-z]?|[1-9][0-9]*|[()\[\]]", part)
        if not tokens or "".join(tokens) != part:
            raise ValueError("Unsupported chemical formula notation.")
        position = 0
        factor = 1
        if tokens[0].isdigit():
            factor = int(tokens[0])
            position = 1

        def group(close=None):
            nonlocal position
            counts = Counter()
            while position < len(tokens) and tokens[position] != close:
                token = tokens[position]
                position += 1
                if token in {"(", "["}:
                    current = group(")" if token == "(" else "]")
                elif re.fullmatch(r"[A-Z][a-z]?", token):
                    current = Counter({token: 1})
                else:
                    raise ValueError("Invalid chemical grouping.")
                multiplier = 1
                if position < len(tokens) and tokens[position].isdigit():
                    multiplier = int(tokens[position])
                    position += 1
                if multiplier > 10000:
                    raise ValueError("Formula multiplier is too large.")
                counts.update({element: count * multiplier for element, count in current.items()})
            if close is not None:
                if position >= len(tokens) or tokens[position] != close:
                    raise ValueError("Unclosed chemical group.")
                position += 1
            if not counts:
                raise ValueError("Empty chemical group.")
            return counts

        current = group()
        if position != len(tokens) or factor > 10000:
            raise ValueError("Invalid chemical formula suffix.")
        total.update({element: count * factor for element, count in current.items()})
    return dict(sorted(total.items()))


def _balance(params):
    """Unique one-dimensional nullspace, exact positive primitive coefficients."""
    species = params["reactants"] + params["products"]
    atoms = [parse_formula(item["formula"]) for item in species]
    elements = sorted({element for counts in atoms for element in counts})
    signs = [1] * len(params["reactants"]) + [-1] * len(params["products"])
    matrix = [[Fraction(counts.get(element, 0) * sign) for counts, sign in zip(atoms, signs)]
              for element in elements]
    if any(item["charge"] for item in species):
        matrix.append([Fraction(item["charge"] * sign) for item, sign in zip(species, signs)])
    row, pivots = 0, []
    for column in range(len(species)):
        found = next((i for i in range(row, len(matrix)) if matrix[i][column]), None)
        if found is None:
            continue
        matrix[row], matrix[found] = matrix[found], matrix[row]
        divisor = matrix[row][column]
        matrix[row] = [value / divisor for value in matrix[row]]
        for i in range(len(matrix)):
            if i != row:
                factor = matrix[i][column]
                matrix[i] = [a - factor * b for a, b in zip(matrix[i], matrix[row])]
        pivots.append(column)
        row += 1
        if row == len(matrix):
            break
    free = [i for i in range(len(species)) if i not in pivots]
    if len(free) != 1:
        raise ValueError("Oracle only supports unique balancing ratios.")
    vector = [Fraction(0)] * len(species)
    vector[free[0]] = 1
    for i, pivot in enumerate(pivots):
        vector[pivot] = -matrix[i][free[0]]
    multiple = lcm(*(item.denominator for item in vector))
    coefficients = [int(item * multiple) for item in vector]
    if all(item < 0 for item in coefficients):
        coefficients = [-item for item in coefficients]
    if not all(item > 0 for item in coefficients):
        raise ValueError("Reaction has no positive balancing ratio.")
    common = gcd(*coefficients)
    return [item // common for item in coefficients]


def _shape(expression, matrices):
    if isinstance(expression, str):
        return matrices[expression]
    if set(expression) == {"transpose"}:
        return list(reversed(_shape(expression["transpose"], matrices)))
    if set(expression) == {"product"}:
        factors = [_shape(item, matrices) for item in expression["product"]]
        if any(a[1] != b[0] for a, b in zip(factors, factors[1:])):
            raise ValueError("Undefined matrix composition.")
        return [factors[0][0], factors[-1][1]]
    raise ValueError("Unknown matrix expression.")


def _graph_formula(graph):
    elements = graph["elements"]
    hydrogens = graph["hydrogens"]
    if len(elements) != len(hydrogens) or any(type(x) is not int or x < 0 for x in hydrogens):
        raise ValueError("Invalid molecular graph.")
    valences = hydrogens[:]
    neighbours = [[] for _ in elements]
    edges = set()
    for a, b, order in graph["bonds"]:
        edge = tuple(sorted((a, b)))
        if a == b or edge in edges or not 0 <= a < len(elements) or not 0 <= b < len(elements) or order != 1:
            raise ValueError("Unsupported molecular bond.")
        edges.add(edge)
        valences[a] += order
        valences[b] += order
        neighbours[a].append(elements[b])
        neighbours[b].append(elements[a])
    for element, valence in zip(elements, valences):
        if element not in {"C", "O"} or valence != {"C": 4, "O": 2}[element]:
            raise ValueError("Molecular graph violates the supplied valence rule.")
    counts = Counter(elements)
    counts["H"] += sum(hydrogens)
    signature = sorted((element, hydrogen, tuple(sorted(adjacent)))
                       for element, hydrogen, adjacent in zip(elements, hydrogens, neighbours))
    return dict(sorted(counts.items())), signature


def _computed(kind, params):
    if kind == "human_reference":
        return params["task"]
    if kind == "rational_program":
        return str(_rational(params["expression"]))
    if kind == "quantity_program":
        return {"value": str(_rational(params["expression"])), "unit": params["unit"]}
    if kind == "polynomial_square":
        poly = _trim(params["polynomial"])
        return _strings(_multiply(poly, poly))
    if kind == "function_composition":
        f, g = params["functions"]["f"], params["functions"]["g"]
        if params["input_dimension"] != f[0] or f[1] != g[0]:
            raise ValueError("Function domains do not permit g after f.")
        return {"application_order": ["f", "g"], "output_dimension": g[1]}
    if kind == "matrix_shape":
        return _shape(params["expression"], params["matrices"])
    if kind == "absolute_square":
        if params != {"domain": "real", "root": "nonnegative_principal"}:
            raise ValueError("Unsupported square-root assumptions.")
        return "abs(x)"
    if kind == "chain_derivative":
        composition = _compose(_trim(params["outer"]), _trim(params["inner"]))
        return _strings([i * x for i, x in enumerate(composition)][1:])
    if kind in {"cancel_domain", "rational_equation"}:
        quotient, remainder = _divide(params["numerator"], params["denominator"])
        denominator = _trim(params["denominator"])
        if remainder != [0] or len(denominator) != 2:
            raise ValueError("Oracle requires exact division and a linear denominator.")
        excluded = -denominator[0] / denominator[1]
        if kind == "cancel_domain":
            return {"coefficients": _strings(quotient), "excluded": [str(excluded)]}
        equation = _add(quotient, [-_fraction(params["target"])])
        if len(equation) != 2 or equation[1] == 0:
            raise ValueError("Oracle requires a reduced linear equation.")
        root = -equation[0] / equation[1]
        return {"roots": [] if root == excluded else [str(root)]}
    if kind == "dimension_ratio":
        keys = set(params["numerator"]) | set(params["denominator"])
        return {key: value for key in sorted(keys)
                if (value := params["numerator"].get(key, 0) - params["denominator"].get(key, 0)) != 0}
    if kind == "polynomial_remainder":
        return _strings(_divide(params["numerator"], params["denominator"])[1])
    if kind == "formula_atoms":
        return parse_formula(params["formula"])
    if kind == "balance":
        return _balance(params)
    if kind == "neutral_ratio":
        positive, negative = params["charges"]
        if positive <= 0 or negative >= 0:
            raise ValueError("Neutral-ratio oracle requires opposite charges.")
        common = gcd(positive, -negative)
        return [-negative // common, positive // common]
    if kind == "limiting_reaction":
        coefficients = _balance(params)
        count = len(params["reactants"])
        extent = min(_fraction(n) / coefficient
                     for n, coefficient in zip(params["amounts"], coefficients[:count]))
        product = extent * coefficients[count + params["product_index"]]
        if params["output"] == "mass":
            product *= _fraction(params["molar_mass"])
        return {"value": str(product), "unit": params["unit"]}
    if kind == "hydrate_mass_fraction":
        hydrate = parse_formula(params["hydrate"])
        dry = parse_formula(params["anhydrous"])
        water = parse_formula("H2O")
        bound = {element: hydrate.get(element, 0) - dry.get(element, 0) for element in hydrate}
        if bound.get("H", 0) <= 0 or bound.get("H") != 2 * bound.get("O", 0) or any(
                amount for element, amount in bound.items() if element not in water):
            raise ValueError("Hydrate difference is not bound water.")
        mass = lambda counts: sum(_fraction(params["atomic_masses"][element]) * amount
                                  for element, amount in counts.items())
        return str(mass(bound) / mass(hydrate))
    if kind == "insufficient_linear":
        values = []
        for witness in params["witnesses"]:
            lhs = sum(_fraction(coefficient) * _fraction(witness[variable])
                      for variable, coefficient in params["coefficients"].items())
            if lhs != _fraction(params["rhs"]):
                raise ValueError("Invalid underdetermination witness.")
            values.append(_fraction(witness[params["query_variable"]]))
        if len(set(values)) < 2:
            raise ValueError("Witnesses do not establish underdetermination.")
        return "insufficient_information"
    if kind == "insufficient_functions":
        results = [_poly_value(w["g"], _poly_value(w["f"], _fraction(params["x"])))
                   for w in params["witnesses"]]
        if params["domain"] != "real_to_real" or len(set(results)) < 2:
            raise ValueError("Function witnesses do not establish underdetermination.")
        return "insufficient_information"
    if kind == "insufficient_volume":
        volumes = [_fraction(x) for x in params["witness_volumes"]]
        if any(x <= 0 for x in volumes) or len({_fraction(params["n"]) / x for x in volumes}) < 2:
            raise ValueError("Invalid volume witnesses.")
        return "insufficient_information"
    if kind == "insufficient_structure":
        expected = parse_formula(params["formula"])
        graphs = [_graph_formula(graph) for graph in params["witnesses"]]
        if any(formula != expected for formula, _ in graphs) or len({repr(signature) for _, signature in graphs}) < 2:
            raise ValueError("Graphs do not establish different structures.")
        return "insufficient_information"
    raise ValueError("Unsupported oracle kind.")


def _options(values, descriptions, correct_position):
    # Place the correct semantic value at a balanced position; no answer letter
    # enters the oracle computation. Translations share their semantic order.
    order = list(range(4))
    order = order[-correct_position:] + order[:-correct_position] if correct_position else order
    options = [{"id": letter, "description": descriptions[index]} for letter, index in zip(LETTERS, order)]
    semantics = {letter: deepcopy(values[index]) for letter, index in zip(LETTERS, order)}
    return options, semantics


DOC_CHOICES = {
    "fr": ["Lire le catalogue : compte, noms ou métadonnées.", "Présenter les résumés déjà stockés.",
           "Lire ou rechercher le contenu pour répondre.", "Demander une précision : le besoin reste indéterminé."],
    "en": ["Read the catalog: count, names or metadata.", "Present the summaries already stored.",
           "Read or search the document content to answer.", "Ask for clarification: the request remains undetermined."],
}


def _document_specs():
    # Each record changes the operation, constraints or discourse dependencies,
    # not just numbers in a repeated problem. Language review remains outstanding.
    records = [
        ("catalog", "D1", "active-inventory", "Le catalogue sépare fichiers actifs et archivés.", "The catalog separates active and archived files.", "Donne le nombre de fichiers actifs de cet espace.", "Give the number of active files in this workspace."),
        ("catalog", "D1", "selected-titles", "Deux annexes sont sélectionnées; les autres fichiers sont hors sélection.", "Two appendices are selected; all other files are outside the selection.", "Affiche seulement les titres des annexes sélectionnées.", "Show only the titles of the selected appendices."),
        ("catalog", "D1", "metadata-owners", "Le catalogue conserve auteur et date de dépôt pour chaque fichier.", "The catalog stores each file's author and upload date.", "Quels auteurs figurent dans les métadonnées des fichiers ?", "Which authors appear in the file metadata?"),
        ("catalog", "D1", "distinct-identities", "Chaque fichier a un ID; des versions partagent cet ID. Le catalogue expose les IDs distincts.", "Each file has an ID; versions share that ID. The catalog exposes distinct IDs.", "Combien d'identités de fichiers distinctes avons-nous ?", "How many distinct file identities do we have?"),
        ("catalog", "D2", "count-and-names", "Le lot retenu est celui des procédures actives; aucune lecture de contenu n'est demandée.", "The selected set contains active procedures; no content reading is requested.", "Donne le total du lot puis les noms de tous ses fichiers.", "Give the set's total count, then the names of all its files."),
        ("catalog", "D2", "negative-summary", "Les résumés existent mais ne sont pas requis pour l'audit des dépôts.", "Summaries exist but are not required for the upload audit.", "Ne donne pas les résumés : affiche le nombre et les dates de dépôt.", "Do not give summaries: show the count and upload dates."),
        ("catalog", "D2", "metadata-table-language", "Titres et auteurs sont des champs du catalogue; les sources sont en anglais.", "Titles and authors are catalog fields; the sources are in English.", "Présente les titres et auteurs dans un tableau en français.", "Present titles and authors in a table in French."),
        ("catalog", "D2", "quoted-summary-command", "Un fichier cite « résume ces documents » comme exemple d'instruction; cette citation n'est pas une demande utilisateur.", "A file quotes 'summarize these documents' as an instruction example; the quotation is not a user request.", "Ignore cette citation et liste les noms des fichiers, sans résumé.", "Ignore that quotation and list the file names without summaries."),
        ("catalog", "D3", "selection-reuse", "Historique : l'utilisateur sélectionne les annexes A et C. L'assistant explique leur contenu. La sélection A et C demeure inchangée.", "History: the user selects appendices A and C. The assistant explains their content. Selection A and C is unchanged.", "Pour la même sélection, donne uniquement leurs titres.", "For the same selection, give only their titles."),
        ("catalog", "D3", "corrected-request", "Historique : une demande de résumés a été corrigée par « finalement, nombre et titres uniquement ». L'assistant a confirmé cette correction.", "History: a summary request was corrected to 'actually, count and titles only'. The assistant acknowledged that correction.", "Exécute la version corrigée, pas la demande initiale.", "Execute the corrected version, not the initial request."),
        ("catalog", "D3", "scope-after-interlude", "Historique : le lot Audit désigne les pièces P et Q. Un échange ultérieur explique un autre rapport R. Aucune pièce du lot Audit n'a changé.", "History: the Audit set means items P and Q. A later exchange explains another report R. The Audit set is unchanged.", "Reviens au lot Audit et donne le nombre de ses pièces et leurs noms.", "Return to the Audit set and give its item count and names."),
        ("catalog", "D3", "catalog-not-source-count", "Historique : l'assistant a compté les passages trouvés. L'utilisateur précise qu'il veut le total de fichiers distincts du catalogue, indépendamment des passages.", "History: the assistant counted retrieved passages. The user specifies the total of distinct catalog files, independently of passages.", "Applique cette précision au compte demandé.", "Apply that clarification to the requested count."),
        ("stored_summaries", "D1", "validated-abstracts", "Chaque note dispose d'un résumé validé dans le catalogue.", "Each note has a validated summary in the catalog.", "Affiche les résumés validés des notes.", "Display the validated summaries of the notes."),
        ("stored_summaries", "D1", "cached-descriptions", "Les fiches contiennent déjà une description courte approuvée de chaque fichier.", "The records already contain an approved short description for each file.", "Récupère ces descriptions courtes déjà disponibles.", "Retrieve those short descriptions already available."),
        ("stored_summaries", "D1", "existing-per-file", "Un abstract a été enregistré pour chacun des articles sélectionnés.", "An abstract has been saved for each selected article.", "Montre l'abstract existant de chaque article sélectionné.", "Show the existing abstract for each selected article."),
        ("stored_summaries", "D1", "summary-bundle", "Le dossier Revue contient des fichiers et leurs résumés stockés séparément.", "The Review folder contains files and their separately stored summaries.", "Ouvre l'ensemble des résumés stockés du dossier Revue.", "Open the collection of stored summaries in the Review folder."),
        ("stored_summaries", "D2", "summary-count-title", "Le dossier annuel dispose d'un titre et d'un résumé validé pour chaque fichier.", "The annual folder has a title and validated summary for each file.", "Donne le nombre de fichiers, leurs titres puis leurs résumés validés.", "Give the file count, titles, then their validated summaries."),
        ("stored_summaries", "D2", "translate-summary-table", "Les résumés enregistrés sont en anglais; leur traduction est permise sans nouvelle synthèse du contenu.", "The saved summaries are in English; they may be translated without a new synthesis of the content.", "Traduis ces résumés en français et présente-les dans un tableau.", "Translate these summaries into French and present them in a table."),
        ("stored_summaries", "D2", "do-not-reread", "Des résumés approuvés sont disponibles et aucun fait nouveau n'est demandé.", "Approved summaries are available and no new facts are requested.", "Ne relis pas les fichiers complets; montre leurs résumés approuvés.", "Do not reread the full files; show their approved summaries."),
        ("stored_summaries", "D2", "quotation-not-budget-question", "Une ancienne réponse citait « quel budget ? ». La demande actuelle porte sur les fiches résumées déjà validées.", "An old answer quoted 'what budget?'. The current request concerns the already validated summary records.", "Présente les résumés validés, sans répondre à la question citée.", "Present the validated summaries without answering the quoted question."),
        ("stored_summaries", "D3", "language-followup", "Historique : l'utilisateur demande les résumés stockés du lot B en tableau. L'assistant les affiche en anglais. La sélection et le format restent actifs.", "History: the user requests the stored summaries of set B in a table. The assistant displays them in English. The selection and format remain active.", "La même chose, mais en français.", "The same thing, but in French."),
        ("stored_summaries", "D3", "remaining-summaries", "Historique : le lot complet contient A, B et C. Seul le résumé stocké de A a été montré. B et C ont aussi un résumé stocké.", "History: the complete set contains A, B and C. Only A's stored summary was shown. B and C also have stored summaries.", "Montre maintenant ceux des deux fichiers restants.", "Now show those of the two remaining files."),
        ("stored_summaries", "D3", "resume-after-content", "Historique : l'utilisateur demande les résumés enregistrés de X et Y; une question incidente sur la définition d'un mot est ensuite résolue. L'utilisateur veut reprendre la demande de fiches.", "History: the user requests the saved summaries of X and Y; an incidental question about a word's definition is then resolved. The user wants to resume the record request.", "Reprends les fiches demandées avant cette parenthèse.", "Resume the records requested before that aside."),
        ("stored_summaries", "D3", "inherit-summary-constraint", "Historique : l'utilisateur a exclu toute nouvelle synthèse et choisi les résumés validés. Un assistant propose ensuite de relire les sources, sans accord utilisateur.", "History: the user excluded any new synthesis and selected validated summaries. An assistant later proposes rereading the sources, without user consent.", "Continue en respectant mon choix initial.", "Continue while respecting my initial choice."),
        ("retrieve_answer", "D1", "content-date", "Le catalogue fournit titre et auteur, mais pas la date de mise en service décrite dans le rapport.", "The catalog provides title and author, but not the commissioning date described in the report.", "Quelle date de mise en service le rapport annonce-t-il ?", "What commissioning date does the report announce?"),
        ("retrieve_answer", "D1", "content-refutation", "La décision du conseil et ses motifs figurent dans le texte des comptes rendus.", "The council decision and its reasons appear in the minutes' text.", "Quel passage réfute l'affirmation que le conseil a approuvé le projet ?", "Which passage refutes the claim that the council approved the project?"),
        ("retrieve_answer", "D1", "content-explanation", "Le rapport décrit pourquoi un essai a été interrompu; les métadonnées ne donnent pas cette cause.", "The report describes why a trial was interrupted; the metadata do not give that cause.", "Explique la cause de l'interruption indiquée dans le rapport.", "Explain the cause of the interruption stated in the report."),
        ("retrieve_answer", "D1", "content-exact-clause", "Le contrat contient plusieurs clauses de résiliation; le titre du fichier ne les expose pas.", "The contract contains several termination clauses; the file title does not state them.", "Retrouve la clause qui fixe le préavis de résiliation.", "Find the clause that sets the termination notice period."),
        ("retrieve_answer", "D2", "content-not-summary", "Les résumés stockés omettent les exceptions; les textes complets les décrivent.", "The stored summaries omit exceptions; the full texts describe them.", "Ne donne pas les résumés : relève les exceptions dans les textes complets.", "Do not give summaries: identify the exceptions in the full texts."),
        ("retrieve_answer", "D2", "content-filtered-list", "Les titres ne disent pas quels fichiers mentionnent un gel du budget; cela dépend de leur contenu.", "The titles do not identify which files mention a budget freeze; that depends on their content.", "Liste les fichiers dont le texte indique que le budget est gelé.", "List the files whose text states that the budget is frozen."),
        ("retrieve_answer", "D2", "relations-mermaid", "Les relations entre acteurs sont décrites dans deux rapports, pas dans leurs métadonnées.", "Relationships between actors are described in two reports, not in their metadata.", "À partir de ces relations, construis un diagramme Mermaid.", "Use those relationships to construct a Mermaid diagram."),
        ("retrieve_answer", "D2", "content-total-unit", "Les coûts sont répartis entre plusieurs tableaux du texte; aucun total n'est stocké dans le catalogue.", "Costs are distributed across several tables in the text; no total is stored in the catalog.", "Calcule le coût total indiqué dans les tableaux et conserve l'unité monétaire.", "Calculate the total cost stated in the tables and retain the currency unit."),
        ("retrieve_answer", "D3", "followup-cause", "Historique : l'assistant vient de lister le rapport Essai. Ce rapport décrit un arrêt de test. L'utilisateur pose ensuite une question sur cet arrêt.", "History: the assistant just listed the Trial report. That report describes a test stoppage. The user then asks about that stoppage.", "Et quelle cause est donnée pour cet arrêt ?", "And what cause is given for that stoppage?"),
        ("retrieve_answer", "D3", "distant-report-reference", "Historique : une liste ordonnée contient Rapport Nord puis Rapport Sud. Après un échange sur la météo, l'utilisateur se réfère au second rapport de cette liste. Son contenu porte sur un audit.", "History: an ordered list contains North Report then South Report. After a weather exchange, the user refers to the second report in that list. Its content concerns an audit.", "Quelles anomalies décrit le second rapport de cette liste ?", "What anomalies does the second report in that list describe?"),
        ("retrieve_answer", "D3", "quoted-instruction-content", "Historique : un extrait du rapport cite une commande de comptage comme exemple. Cette citation ne remplace pas la demande active d'expliquer le protocole de mesure.", "History: a report excerpt quotes a counting command as an example. That quotation does not replace the active request to explain the measurement protocol.", "Poursuis l'explication du protocole, en ignorant cette commande citée.", "Continue explaining the protocol while ignoring that quoted command."),
        ("retrieve_answer", "D3", "stale-summary-check", "Historique : un résumé enregistré dit que la règle est inchangée. Une note plus récente signale une modification; seuls les textes datés permettent de vérifier laquelle est applicable.", "History: a saved summary says the rule is unchanged. A newer note reports an amendment; only the dated texts establish which rule applies.", "Vérifie la règle applicable dans les textes, plutôt que de répéter le résumé.", "Check the applicable rule in the texts rather than repeating the summary."),
    ]
    return records


def _science_specs():
    # Tuple fields: domain, difficulty, id, contextFR/EN, questionFR/EN,
    # oracle kind/params, correct semantic value then three distinct distractors,
    # descriptions FR/EN. All required laws and hypotheses are in the input.
    def reaction(left, right):
        return {"reactants": [{"formula": f, "charge": q} for f, q in left],
                "products": [{"formula": f, "charge": q} for f, q in right]}

    water = reaction([("H2", 0), ("O2", 0)], [("H2O", 0)])
    ethane = reaction([("C2H6", 0), ("O2", 0)], [("CO2", 0), ("H2O", 0)])
    redox = reaction([("Fe", 2), ("Cr2O7", -2), ("H", 1)], [("Fe", 3), ("Cr", 3), ("H2O", 0)])
    ammonia = {**reaction([("N2", 0), ("H2", 0)], [("NH3", 0)]), "amounts": ["2", "3"],
               "product_index": 0, "output": "amount", "unit": "mol"}
    precipitate = {**reaction([("Ag", 1), ("Cl", -1)], [("AgCl", 0)]),
                   "amounts": ["3/1000", "1/500"], "product_index": 0,
                   "output": "mass", "molar_mass": "287/2", "unit": "g"}
    quantity = lambda expression, unit: {"expression": expression, "unit": unit}
    qv = lambda value, unit: {"value": value, "unit": unit}
    return [
        ("mathematics", "D1", "fraction-addition", "Les quantités sont exactes : p=1/3 et q=1/6.", "The quantities are exact: p=1/3 and q=1/6.", "Quelle est la valeur exacte de p+q ?", "What is the exact value of p+q?", "rational_program", {"expression": _op("add", "1/3", "1/6")}, ["1/2", "2/9", "1/6", "2/3"], ["1/2", "2/9", "1/6", "2/3"], ["1/2", "2/9", "1/6", "2/3"]),
        ("mathematics", "D1", "square-expansion", "x est réel; le produit distributif définit le développement polynomial.", "x is real; the distributive law defines polynomial expansion.", "Quelle expression égale (x+1)^2 pour tout x ?", "Which expression equals (x+1)^2 for every x?", "polynomial_square", {"polynomial": [1, 1]}, [["1", "2", "1"], ["1", "0", "1"], ["1", "1", "1"], ["0", "2", "1"]], ["x^2+2x+1", "x^2+1", "x^2+x+1", "x^2+2x"], ["x^2+2x+1", "x^2+1", "x^2+x+1", "x^2+2x"]),
        ("mathematics", "D1", "function-types", "f:R^2→R^3 et g:R^3→R. x∈R^2; une composition doit respecter les domaines.", "f:R^2→R^3 and g:R^3→R. x∈R^2; composition must respect domains.", "Quelle composition utilise f et g et donne un réel ?", "Which composition uses f and g and yields a real number?", "function_composition", {"functions": {"f": [2, 3], "g": [3, 1]}, "input_dimension": 2}, [{"application_order": ["f", "g"], "output_dimension": 1}, {"application_order": ["g", "f"], "output_dimension": 1}, {"application_order": ["f"], "output_dimension": 3}, {"application_order": ["g"], "output_dimension": 1}], ["g(f(x))", "f(g(x))", "f(x)", "g(x)"], ["g(f(x))", "f(g(x))", "f(x)", "g(x)"]),
        ("mathematics", "D1", "matrix-product", "A est 2×3 et B est 3×4. Dans XY, les dimensions intérieures doivent coïncider.", "A is 2×3 and B is 3×4. In XY, the inner dimensions must agree.", "Quelle est la taille de AB ?", "What is the shape of AB?", "matrix_shape", {"matrices": {"A": [2, 3], "B": [3, 4]}, "expression": {"product": ["A", "B"]}}, [[2, 4], [3, 3], [4, 2], [2, 3]], ["2×4", "3×3", "4×2", "2×3"], ["2×4", "3×3", "4×2", "2×3"]),
        ("mathematics", "D2", "principal-root", "x est un réel quelconque. sqrt est la racine carrée principale non négative.", "x is any real number. sqrt is the nonnegative principal square root.", "Quelle identité vaut pour sqrt(x^2), sans supposer x≥0 ?", "Which identity holds for sqrt(x^2), without assuming x≥0?", "absolute_square", {"domain": "real", "root": "nonnegative_principal"}, ["abs(x)", "x", "-x", "x^2"], ["abs(x)", "x", "-x", "x^2"], ["abs(x)", "x", "-x", "x^2"]),
        ("mathematics", "D2", "chain-derivative", "f(t)=t^2 et g(x)=x+1 sur R. La dérivée de f∘g est (f'∘g)g'.", "f(t)=t^2 and g(x)=x+1 on R. The derivative of f∘g is (f'∘g)g'.", "Quelle est la dérivée de f(g(x)) ?", "What is the derivative of f(g(x))?", "chain_derivative", {"outer": [0, 0, 1], "inner": [1, 1]}, [["2", "2"], ["0", "2"], ["1", "2"], ["1", "0", "1"]], ["2x+2", "2x", "2x+1", "x^2+1"], ["2x+2", "2x", "2x+1", "x^2+1"]),
        ("mathematics", "D2", "cancel-keep-domain", "La fonction est (x^2-4)/(x-2), définie lorsque le dénominateur est non nul. Il faut conserver le domaine initial.", "The function is (x^2-4)/(x-2), defined when the denominator is nonzero. Preserve the original domain.", "Quelle simplification conserve expression et domaine ?", "Which simplification preserves both expression and domain?", "cancel_domain", {"numerator": [-4, 0, 1], "denominator": [-2, 1]}, [{"coefficients": ["2", "1"], "excluded": ["2"]}, {"coefficients": ["2", "1"], "excluded": []}, {"coefficients": ["-2", "1"], "excluded": ["2"]}, {"coefficients": ["2", "1"], "excluded": ["-2"]}], ["x+2, avec x≠2", "x+2, pour tout réel", "x-2, avec x≠2", "x+2, avec x≠-2"], ["x+2, with x≠2", "x+2, for every real", "x-2, with x≠2", "x+2, with x≠-2"]),
        ("mathematics", "D2", "quantity-dimension", "n a la dimension mol et V la dimension L. Une division soustrait les exposants des unités.", "n has dimension mol and V has dimension L. Division subtracts unit exponents.", "Quelle unité a n/V ?", "What unit does n/V have?", "dimension_ratio", {"numerator": {"mol": 1}, "denominator": {"L": 1}}, [{"L": -1, "mol": 1}, {"L": 1, "mol": 1}, {"L": 1, "mol": -1}, {"mol": 1}], ["mol/L", "mol·L", "L/mol", "mol"], ["mol/L", "mol·L", "L/mol", "mol"]),
        ("mathematics", "D3", "extraneous-equation-root", "Résoudre sur R : (x^2-1)/(x-1)=2. Le domaine initial exclut x=1; cette exclusion reste active après factorisation.", "Solve over R: (x^2-1)/(x-1)=2. The original domain excludes x=1; this exclusion remains after factorization.", "Quel ensemble de solutions respecte le domaine ?", "Which solution set respects the domain?", "rational_equation", {"numerator": [-1, 0, 1], "denominator": [-1, 1], "target": "2"}, [{"roots": []}, {"roots": ["1"]}, {"roots": ["-1"]}, {"roots": ["1", "-1"]}], ["Aucune solution", "{1}", "{-1}", "{-1,1}"], ["No solution", "{1}", "{-1}", "{-1,1}"]),
        ("mathematics", "D3", "transpose-chain", "A est 2×3, B est 4×3, C est 4×5. Transposer échange lignes et colonnes; les dimensions intérieures d'un produit doivent coïncider.", "A is 2×3, B is 4×3, C is 4×5. Transposition swaps rows and columns; product inner dimensions must agree.", "Quelle est la taille de A B^T C ?", "What is the shape of A B^T C?", "matrix_shape", {"matrices": {"A": [2, 3], "B": [4, 3], "C": [4, 5]}, "expression": {"product": ["A", {"transpose": "B"}, "C"]}}, [[2, 5], [3, 5], [2, 4], [5, 2]], ["2×5", "3×5", "2×4", "5×2"], ["2×5", "3×5", "2×4", "5×2"]),
        ("mathematics", "D3", "polynomial-remainder", "On divise x^4+x^3+2 par x^2-1 dans R[x]. Le reste doit avoir un degré strictement inférieur à 2.", "Divide x^4+x^3+2 by x^2-1 in R[x]. The remainder must have degree strictly below 2.", "Quel est le reste de cette division euclidienne ?", "What is the remainder of this polynomial division?", "polynomial_remainder", {"numerator": [2, 0, 0, 1, 1], "denominator": [-1, 0, 1]}, [["3", "1"], ["2", "1"], ["3"], ["2", "0", "1"]], ["x+3", "x+2", "3", "x^2+2"], ["x+3", "x+2", "3", "x^2+2"]),
        ("mathematics", "D3", "conditional-probability", "P(A)=1/3, P(B|A)=3/4, P(B|non A)=1/4. Utiliser P(A|B)=P(B|A)P(A)/(P(B|A)P(A)+P(B|non A)P(non A)).", "P(A)=1/3, P(B|A)=3/4, P(B|not A)=1/4. Use P(A|B)=P(B|A)P(A)/(P(B|A)P(A)+P(B|not A)P(not A)).", "Quelle est P(A|B) ?", "What is P(A|B)?", "rational_program", {"expression": _op("div", _op("mul", "3/4", "1/3"), _op("add", _op("mul", "3/4", "1/3"), _op("mul", "1/4", _op("sub", "1", "1/3"))))}, ["3/5", "3/4", "1/3", "1/4"], ["3/5", "3/4", "1/3", "1/4"], ["3/5", "3/4", "1/3", "1/4"]),
        ("chemistry", "D1", "group-atom-count", "Dans Ca(OH)2, le suffixe 2 multiplie tout le groupe OH.", "In Ca(OH)2, the suffix 2 multiplies the entire OH group.", "Quels nombres d'atomes décrit la formule ?", "Which atom counts does the formula describe?", "formula_atoms", {"formula": "Ca(OH)2"}, [{"Ca": 1, "H": 2, "O": 2}, {"Ca": 2, "H": 2, "O": 2}, {"Ca": 1, "H": 2, "O": 1}, {"Ca": 1, "H": 1, "O": 1}], ["Ca:1, O:2, H:2", "Ca:2, O:2, H:2", "Ca:1, O:1, H:2", "Ca:1, O:1, H:1"], ["Ca:1, O:2, H:2", "Ca:2, O:2, H:2", "Ca:1, O:1, H:2", "Ca:1, O:1, H:1"]),
        ("chemistry", "D1", "water-balance", "Équation formelle H2+O2→H2O. Conserver chaque élément; choisir les entiers positifs minimaux.", "Formal equation H2+O2→H2O. Conserve every element; choose minimal positive integers.", "Quels coefficients suivent l'ordre H2,O2,H2O ?", "Which coefficients follow the order H2,O2,H2O?", "balance", water, [[2, 1, 2], [1, 1, 1], [4, 2, 4], [2, 2, 1]], ["2,1,2", "1,1,1", "4,2,4", "2,2,1"], ["2,1,2", "1,1,1", "4,2,4", "2,2,1"]),
        ("chemistry", "D1", "ionic-neutrality", "Les charges formelles sont Ca^2+ et Cl^-. Demander uniquement un ratio neutre minimal, pas une preuve de stabilité.", "Formal charges are Ca^2+ and Cl^-. Ask only for a minimal neutral ratio, not proof of stability.", "Quel ratio Ca:Cl annule la charge totale ?", "What Ca:Cl ratio cancels the total charge?", "neutral_ratio", {"charges": [2, -1]}, [[1, 2], [1, 1], [2, 1], [2, 4]], ["1:2", "1:1", "2:1", "2:4"], ["1:2", "1:1", "2:1", "2:4"]),
        ("chemistry", "D1", "molar-concentration", "Une solution contient exactement n=1/5 mol dans V=2 L. La concentration molaire est c=n/V.", "A solution contains exactly n=1/5 mol in V=2 L. Molar concentration is c=n/V.", "Quelle concentration, avec unité, obtient-on ?", "What concentration, including its unit, results?", "quantity_program", quantity(_op("div", "1/5", "2"), "mol/L"), [qv("1/10", "mol/L"), qv("2/5", "mol/L"), qv("1/10", "mol"), qv("10", "mol/L")], ["0,10 mol/L", "0,40 mol/L", "0,10 mol", "10 mol/L"], ["0.10 mol/L", "0.40 mol/L", "0.10 mol", "10 mol/L"]),
        ("chemistry", "D2", "nested-complex-count", "Les multiplicateurs de K4[Fe(CN)6] s'appliquent à leur groupe complet, y compris les groupes emboîtés.", "Multipliers in K4[Fe(CN)6] apply to their entire group, including nested groups.", "Quels nombres d'atomes contient cette formule ?", "What atom counts does this formula contain?", "formula_atoms", {"formula": "K4[Fe(CN)6]"}, [{"C": 6, "Fe": 1, "K": 4, "N": 6}, {"C": 6, "Fe": 6, "K": 4, "N": 6}, {"C": 1, "Fe": 1, "K": 4, "N": 6}, {"C": 6, "Fe": 1, "K": 1, "N": 6}], ["K:4, Fe:1, C:6, N:6", "K:4, Fe:6, C:6, N:6", "K:4, Fe:1, C:1, N:6", "K:1, Fe:1, C:6, N:6"], ["K:4, Fe:1, C:6, N:6", "K:4, Fe:6, C:6, N:6", "K:4, Fe:1, C:1, N:6", "K:1, Fe:1, C:6, N:6"]),
        ("chemistry", "D2", "combustion-balance", "Équation formelle C2H6+O2→CO2+H2O. Conserver C,H,O et choisir les entiers positifs minimaux.", "Formal equation C2H6+O2→CO2+H2O. Conserve C,H,O and choose minimal positive integers.", "Quels coefficients suivent l'ordre C2H6,O2,CO2,H2O ?", "Which coefficients follow the order C2H6,O2,CO2,H2O?", "balance", ethane, [[2, 7, 4, 6], [1, 3, 2, 3], [4, 14, 8, 12], [2, 6, 4, 6]], ["2,7,4,6", "1,3,2,3", "4,14,8,12", "2,6,4,6"], ["2,7,4,6", "1,3,2,3", "4,14,8,12", "2,6,4,6"]),
        ("chemistry", "D2", "conserved-dilution", "c1=1/5 mol/L, V1=50 mL; le volume final est V2=200 mL. Le soluté est conservé : c1 V1=c2 V2; 1000 mL=1 L.", "c1=1/5 mol/L, V1=50 mL; final volume V2=200 mL. Solute is conserved: c1 V1=c2 V2; 1000 mL=1 L.", "Quelle est c2 avec son unité ?", "What is c2 with its unit?", "quantity_program", quantity(_op("div", _op("mul", "1/5", "1/20"), "1/5"), "mol/L"), [qv("1/20", "mol/L"), qv("4/5", "mol/L"), qv("1/5", "mol/L"), qv("1/20", "mol")], ["0,050 mol/L", "0,80 mol/L", "0,20 mol/L", "0,050 mol"], ["0.050 mol/L", "0.80 mol/L", "0.20 mol/L", "0.050 mol"]),
        ("chemistry", "D2", "atoms-and-charge", "Équation formelle Fe^2+ + Cr2O7^2- + H^+ → Fe^3+ + Cr^3+ + H2O. Conserver atomes et charge avec entiers positifs minimaux.", "Formal equation Fe^2+ + Cr2O7^2- + H^+ → Fe^3+ + Cr^3+ + H2O. Conserve atoms and charge with minimal positive integers.", "Quels coefficients suivent cet ordre des six espèces ?", "Which coefficients follow that order of the six species?", "balance", redox, [[6, 1, 14, 6, 2, 7], [1, 1, 14, 1, 2, 7], [6, 1, 7, 6, 2, 7], [12, 2, 28, 12, 4, 14]], ["6,1,14,6,2,7", "1,1,14,1,2,7", "6,1,7,6,2,7", "12,2,28,12,4,14"], ["6,1,14,6,2,7", "1,1,14,1,2,7", "6,1,7,6,2,7", "12,2,28,12,4,14"]),
        ("chemistry", "D3", "limiting-reactant", "N2+3H2→2NH3 est supposée complète. Au départ : 2 mol de N2 et 3 mol de H2. Le réactif limitant fixe l'avancement; aucun autre apport.", "N2+3H2→2NH3 is assumed complete. Initially: 2 mol N2 and 3 mol H2. The limiting reactant fixes the extent; no further input.", "Quelle quantité maximale de NH3 obtient-on ?", "What maximum amount of NH3 results?", "limiting_reaction", ammonia, [qv("2", "mol"), qv("4", "mol"), qv("6", "mol"), qv("1", "mol")], ["2 mol", "4 mol", "6 mol", "1 mol"], ["2 mol", "4 mol", "6 mol", "1 mol"]),
        ("chemistry", "D3", "aliquot-and-mix", "Une solution homogène de 50 mL est à 0,40 mol/L. On prélève 10 mL et les mélange avec 30 mL à 0,10 mol/L du même soluté. Volumes additifs, aucun soluté perdu; c=n/V.", "A homogeneous 50 mL solution is 0.40 mol/L. Take 10 mL and mix with 30 mL at 0.10 mol/L of the same solute. Volumes add, no solute is lost; c=n/V.", "Quelle est la concentration du mélange final ?", "What is the concentration of the final mixture?", "quantity_program", quantity(_op("div", _op("add", _op("mul", "2/5", "1/100"), _op("mul", "1/10", "3/100")), _op("add", "1/100", "3/100")), "mol/L"), [qv("7/40", "mol/L"), qv("1/4", "mol/L"), qv("2/5", "mol/L"), qv("23/80", "mol/L")], ["0,175 mol/L", "0,250 mol/L", "0,400 mol/L", "0,2875 mol/L"], ["0.175 mol/L", "0.250 mol/L", "0.400 mol/L", "0.2875 mol/L"]),
        ("chemistry", "D3", "precipitate-mass", "Ag^+ + Cl^- → AgCl est supposée quantitative. 30 mL à 0,10 mol/L de Ag^+ et 10 mL à 0,20 mol/L de Cl^- sont mélangés. M(AgCl)=143,5 g/mol; n=cV et m=nM.", "Ag^+ + Cl^- → AgCl is assumed quantitative. Mix 30 mL at 0.10 mol/L Ag^+ with 10 mL at 0.20 mol/L Cl^-. M(AgCl)=143.5 g/mol; n=cV and m=nM.", "Quelle masse de AgCl est formée ?", "What mass of AgCl is formed?", "limiting_reaction", precipitate, [qv("287/1000", "g"), qv("861/2000", "g"), qv("287/400", "g"), qv("1/500", "g")], ["0,287 g", "0,4305 g", "0,7175 g", "0,002 g"], ["0.287 g", "0.4305 g", "0.7175 g", "0.002 g"]),
        ("chemistry", "D3", "hydrate-water-fraction", "CuSO4·5H2O contient cinq eaux par unité CuSO4. Masses atomiques exactes utilisées : Cu=63,5, S=32, O=16, H=1 en g/mol. Fraction massique = masse d'eau / masse totale.", "CuSO4·5H2O contains five waters per CuSO4 unit. Exact atomic masses used: Cu=63.5, S=32, O=16, H=1 in g/mol. Mass fraction = water mass / total mass.", "Quelle est la fraction massique de l'eau liée ?", "What is the mass fraction of bound water?", "hydrate_mass_fraction", {"hydrate": "CuSO4·5H2O", "anhydrous": "CuSO4", "atomic_masses": {"Cu": "127/2", "S": "32", "O": "16", "H": "1"}}, ["180/499", "90/159", "5/6", "10/499"], ["180/499", "90/159", "5/6", "10/499"], ["180/499", "90/159", "5/6", "10/499"]),
    ]


def _insufficient_specs():
    return [
        ("documentary", "D3", "unanchored-language", "Aucune réponse précédente ni sélection documentaire n'est disponible. La demande pourrait modifier un texte, un résumé ou la langue du chat.", "No previous answer or document selection is available. The request could modify a text, a summary, or the chat language.", "Avec le seul message « en français », quelle opération documentaire précise peut-on choisir ?", "With only the message 'in French', which precise document operation can be chosen?", "human_reference", {"task": "insufficient_information"}, ["insufficient_information", "catalog", "stored_summaries", "retrieve_answer"], [DOC_CHOICES["fr"][3], *DOC_CHOICES["fr"][:3]], [DOC_CHOICES["en"][3], *DOC_CHOICES["en"][:3]]),
        ("documentary", "D3", "ambiguous-selection", "Deux fichiers A et B ont chacun un résumé enregistré. Aucun fichier n'est sélectionné et aucun référent antérieur n'existe.", "Files A and B each have a saved summary. No file is selected and no earlier referent exists.", "Le message « montre le résumé de celui-là » désigne quel fichier ?", "Which file does 'show the summary of that one' identify?", "human_reference", {"task": "insufficient_information"}, ["insufficient_information", "A", "B", "A_and_B"], ["Référent insuffisant : demander une précision.", "Le fichier A uniquement.", "Le fichier B uniquement.", "A et B nécessairement."], ["Insufficient referent: ask for clarification.", "File A only.", "File B only.", "Necessarily both A and B."]),
        ("mathematics", "D3", "underdetermined-linear", "x et y sont réels et la seule contrainte est x+y=10. Aucun signe ni autre équation n'est imposé.", "x and y are real and the only constraint is x+y=10. No sign or further equation is imposed.", "Quelle valeur unique de x découle des données ?", "What unique value of x follows from the data?", "insufficient_linear", {"coefficients": {"x": "1", "y": "1"}, "rhs": "10", "query_variable": "x", "witnesses": [{"x": "2", "y": "8"}, {"x": "7", "y": "3"}]}, ["insufficient_information", "5", "10", "0"], ["Information insuffisante", "5", "10", "0"], ["Insufficient information", "5", "10", "0"]),
        ("mathematics", "D3", "unknown-function-values", "On connaît seulement les types f:R→R et g:R→R; aucune formule ni valeur de f ou g n'est donnée.", "Only the types f:R→R and g:R→R are known; no formula or value of f or g is supplied.", "Quelle valeur numérique unique vaut g(f(1)) ?", "What unique numerical value is g(f(1))?", "insufficient_functions", {"domain": "real_to_real", "x": "1", "witnesses": [{"f": [0, 1], "g": [0, 1]}, {"f": [2], "g": [0, 1]}]}, ["insufficient_information", "1", "2", "0"], ["Information insuffisante", "1", "2", "0"], ["Insufficient information", "1", "2", "0"]),
        ("chemistry", "D3", "missing-final-volume", "La solution contient 1 mol de soluté. Son volume positif final n'est pas indiqué; c=n/V en mol/L.", "The solution contains 1 mol solute. Its positive final volume is unspecified; c=n/V in mol/L.", "Quelle concentration unique en mol/L peut-on déduire ?", "What unique concentration in mol/L can be deduced?", "insufficient_volume", {"n": "1", "witness_volumes": ["1", "2"]}, ["insufficient_information", "1", "1/2", "2"], ["Information insuffisante", "1 mol/L", "0,5 mol/L", "2 mol/L"], ["Insufficient information", "1 mol/L", "0.5 mol/L", "2 mol/L"]),
        ("chemistry", "D3", "formula-not-structure", "La seule donnée est la formule brute C2H6O. Les liaisons ne sont pas indiquées. Pour ce cas, C a valence 4, O valence 2 et H valence 1.", "The only datum is molecular formula C2H6O. Bonds are unspecified. For this case, C has valence 4, O valence 2 and H valence 1.", "Cette information détermine-t-elle une structure moléculaire unique ?", "Does this information determine a unique molecular structure?", "insufficient_structure", {"formula": "C2H6O", "witnesses": [{"elements": ["C", "C", "O"], "hydrogens": [3, 2, 1], "bonds": [[0, 1, 1], [1, 2, 1]]}, {"elements": ["C", "O", "C"], "hydrogens": [3, 0, 3], "bonds": [[0, 1, 1], [1, 2, 1]]}]}, ["insufficient_information", "ethanol_unique", "ether_unique", "no_structure"], ["Non : plusieurs structures sont compatibles.", "Oui : seulement l'éthanol.", "Oui : seulement l'éther diméthylique.", "Aucune structure n'est compatible."], ["No: several structures are compatible.", "Yes: ethanol only.", "Yes: dimethyl ether only.", "No structure is compatible."]),
    ]


def _assemble():
    cases = []
    specifications = []
    within_task = Counter()
    for task, difficulty, name, cfr, cen, qfr, qen in _document_specs():
        index = within_task[task]
        within_task[task] += 1
        calibration = {"catalog": {0, 4}, "stored_summaries": {0, 8}, "retrieve_answer": {4, 8}}[task]
        test = {2, 3, 6, 7, 10, 11}
        split = "test" if index in test else "calibration" if index in calibration else "train"
        values = [task] + [x for x in TASKS if x != task]
        descriptions = [[DOC_CHOICES[language][TASKS.index(x)] for x in values] for language in ("fr", "en")]
        specifications.append(("documentary", difficulty, f"{task}-{name}", cfr, cen, qfr, qen,
                               "human_reference", {"task": task}, values, *descriptions, split))
    sciences = Counter()
    for spec in _science_specs():
        index = sciences[spec[0]]
        sciences[spec[0]] += 1
        position = index % 4
        split = "train" if position == 0 else "calibration" if position == 1 else "test"
        specifications.append((*spec, split))
    insufficient = Counter()
    for spec in _insufficient_specs():
        index = insufficient[spec[0]]
        insufficient[spec[0]] += 1
        specifications.append((*spec, "calibration" if index == 0 else "test"))
    for family_index, spec in enumerate(specifications):
        domain, difficulty, name, cfr, cen, qfr, qen, kind, params, values, dfr, den, split = spec
        if _computed(kind, params) != values[0] or len({json.dumps(x, sort_keys=True) for x in values}) != 4:
            raise ValueError(f"Invalid oracle alternatives for {name}.")
        scenario = f"ctx-{domain}-{name}"
        related = (["mcps.document-plan", "mcps.canonical-document-read"] +
                   (["mcps.document-followup"] if difficulty == "D3" else [])) if domain == "documentary" else SCIENCE_LINKS[:]
        for language_index, (language, context, question, descriptions) in enumerate(
                (("fr", cfr, qfr, dfr), ("en", cen, qen, den))):
            options, semantics = _options(values, descriptions, family_index % 4)
            case_id = f"{scenario}-{language}"
            visible = {"context": context, "question": question, "options": options}
            correct = next(letter for letter, value in semantics.items() if value == _computed(kind, params))
            cases.append({"schema_version": "deposium.case/v2", "case_id": case_id,
                          "scenario_id": scenario, "translation_family": f"{scenario}-fr-en",
                          "document_ids": [f"synthetic:{scenario}:d1", f"synthetic:{scenario}:d2"] if domain == "documentary" else [],
                          "split": split, "language": language, "pack": "RESEARCH",
                          "contract_id": "bench.context-choice", "input": visible,
                          "reference": {"assertions": [{"path": "/choice_id", "op": "equals", "value": correct}],
                                        "abstention_allowed": False,
                                        "rationale": ("Référence documentaire par agent, selon la demande et les hypothèses explicites; revue humaine non effectuée."
                                                      if domain == "documentary" else
                                                      "Oracle exact restreint aux hypothèses fournies; aucune qualification du raisonnement général ou de la faisabilité chimique.")},
                          "evaluation": {"domain": domain, "difficulty": difficulty,
                                         "base_case_id": case_id, "related_contract_ids": related[:],
                                         "review": "agent_only", "task_type": name,
                                         "oracle": {"kind": kind, "params": deepcopy(params), "choices": semantics,
                                                    "base_input": deepcopy(visible)}, "length": None}})
    return cases


@lru_cache(maxsize=1)
def _base_index():
    return {case["case_id"]: case for case in _assemble()}


def validate_oracle(case):
    """Validate a built-in base or a length/order variant against its exact oracle.

    Base context must occur once inside a possibly longer context. Question and
    option ID/text association are fixed; presentation order may change. Unknown
    oracle families fail explicitly rather than claiming general symbolic proof.
    """
    if (isinstance(case, dict) and isinstance(case.get("evaluation"), dict)
            and case["evaluation"].get("domain") == "physics"):
        from .physics_corpus import validate_oracle as validate_physics_oracle
        return validate_physics_oracle(case)
    if (isinstance(case, dict) and isinstance(case.get("evaluation"), dict)
            and str(case["evaluation"].get("base_case_id", "")).startswith(("frv1-", "fra1-", "frc1-"))):
        from .facade_corpus import validate_oracle as validate_facade_oracle
        return validate_facade_oracle(case)
    try:
        evaluation = case["evaluation"]
        if evaluation["base_case_id"].startswith("ccv1-"):
            from .capability_corpus import canonical_case
            base = canonical_case(evaluation["base_case_id"])
            if evaluation["length"] is not None:
                raise ValueError("Capability catalogue variants are frozen bases, not token-length variants.")
        else:
            base = _base_index()[evaluation["base_case_id"]]
        oracle = evaluation["oracle"]
        if oracle != base["evaluation"]["oracle"]:
            raise ValueError("Oracle or base-input snapshot was modified.")
        for key in ("domain", "difficulty", "related_contract_ids", "review", "task_type"):
            if evaluation[key] != base["evaluation"][key]:
                raise ValueError("Base evaluation identity was modified.")
        visible, expected = case["input"], oracle["base_input"]
        if set(visible) != {"context", "question", "options"} or not isinstance(visible["context"], str):
            raise ValueError("Invalid contextual-choice input.")
        if visible["context"].count(expected["context"]) != 1 or visible["question"] != expected["question"]:
            raise ValueError("Base facts or question were altered, absent or duplicated.")
        if case["scenario_id"] != base["scenario_id"] or case["document_ids"] != base["document_ids"]:
            raise ValueError("Base scenario or document identity was modified.")
        length = evaluation["length"]
        if length is None:
            if case["case_id"] != base["case_id"] or visible != expected:
                raise ValueError("A base case must preserve its exact ID and input.")
        else:
            base_bytes = (json.dumps(expected, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode()
            if length["base_input_sha256"] != hashlib.sha256(base_bytes).hexdigest():
                raise ValueError("Length variant has a false base-input fingerprint.")
            order = length["order"]
            expected_order = expected["options"] if order == "original" else expected["options"][::-1]
            if order not in {"original", "reversed"} or visible["options"] != expected_order:
                raise ValueError("Length variant does not preserve its declared option order.")
        options = visible["options"]
        if (not isinstance(options, list) or len(options) != 4
                or any(not isinstance(x, dict) or set(x) != {"id", "description"} for x in options)
                or {x["id"]: x["description"] for x in options} !=
                   {x["id"]: x["description"] for x in expected["options"]}):
            raise ValueError("Option identity or content was modified.")
        answer = _computed(oracle["kind"], oracle["params"])
        matches = [letter for letter, value in oracle["choices"].items() if value == answer]
        if len(matches) != 1 or case["reference"]["assertions"] != [
                {"path": "/choice_id", "op": "equals", "value": matches[0]}]:
            raise ValueError("Oracle does not establish the unique reference choice.")
        if case["reference"]["abstention_allowed"] is not False:
            raise ValueError("Information-insufficient choices are semantic answers, not technical abstention.")
        if case["language"] != base["language"] or case["translation_family"] != base["translation_family"] or case["split"] != base["split"]:
            raise ValueError("Translation or split identity was modified.")
    except (KeyError, TypeError, ZeroDivisionError, IndexError) as error:
        raise ValueError("Malformed or unsupported exact-oracle case.") from error


def build_cases():
    """Return independent copies of the 132 bilingual base cases."""
    result = deepcopy(list(_base_index().values()))
    for case in result:
        validate_oracle(case)
    return result


def write_dataset(output):
    """Write a new dataset directory; never replace an existing destination."""
    destination = Path(output)
    if destination.exists():
        raise FileExistsError("Dataset output already exists.")
    cases = build_cases()
    payload = b"".join((json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
                       for case in cases)
    manifest = {"schema_version": "deposium.research-dataset/v1", "dataset_id": "context-choice-v1",
                "version": "1.0.0-exploratory", "case_schema": "deposium.case/v2",
                "cases_file": "cases.jsonl", "cases_sha256": hashlib.sha256(payload).hexdigest(),
                "case_count": len(cases), "family_count": len({c["translation_family"] for c in cases}),
                "languages": ["fr", "en"], "contract_id": "bench.context-choice",
                "review": "agent_only", "human_review": "not_performed",
                "provenance": "synthetic; base specifications fixed before candidate inference",
                "oracle_version": "deposium.research-oracles/v1",
                "construction_revision": "Before any candidate inference, bilingual choices were aligned to the same semantic order and position balancing was checked within each language. No semantic answer was changed.",
                "counts_by_domain": dict(Counter(c["evaluation"]["domain"] for c in cases)),
                "counts_by_difficulty": dict(Counter(c["evaluation"]["difficulty"] for c in cases)),
                "counts_by_split": dict(Counter(c["split"] for c in cases)),
                "counts_by_correct_position": dict(Counter(c["reference"]["assertions"][0]["value"] for c in cases)),
                "split_policy": "Keep translations, length/order variants and documents in one family split. Documentary tasks: 4 train/2 calibration/6 test families per class; sciences: 3/3/6; insufficiency: 1 calibration/1 test per domain.",
                "limitations": ["Documentary references are agent judgments, not human-reviewed ground truth.",
                                "Exact science oracles prove only the stated finite rational/polynomial/type/atom/charge tasks.",
                                "Conservation and charge balance do not prove reaction feasibility or compound stability.",
                                "Six insufficiency families choose an explicit semantic option; they do not abstain technically.",
                                "Families share reasoning operations; 66 scenario families are not 66 independent algorithms.",
                                "No model, integrated stack, service, latency or product qualification is claimed.",
                                "Length is null for these bases; longer variants require their separate provenance."]}
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "cases.jsonl").write_bytes(payload)
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest
