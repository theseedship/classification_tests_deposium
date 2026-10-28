# Usages DuckDB/XLSX avant tout benchmark prédictif

État au 2 octobre 2026. **Le besoin de prédiction tabulaire reste à établir.**
La lecture des sources confirme des parcours et des données disponibles, pas
leur fréquence d'utilisation ni une décision métier qui bénéficierait de Kumo.
Aucun flux utilisateur n'a été collecté ou annoté dans ce lot.

Cette étape T0 précède le [pilote tabulaire envisagé](KUMO_QWEN_CLEF_CANDIDATES.md).
Elle complète la revue humaine R1 et la préparation R2 de la [local-only material, not distributed](PROTOCOL.md).
Un résultat recevable de T0 est de ne retenir aucun besoin prédictif.

## Trois objets à annoter séparément

1. **Le flux technique** : entrée chat ou appel MCP direct, fichier/feuille ou
   table, schéma, outils réellement appelés, révisions, sortie et erreurs.
   DuckDB est un moteur et XLSX un format; aucun des deux ne désigne un besoin.
2. **La tâche utilisateur** : demande, contexte de suivi, résultat attendu,
   personne qui l'utilise et action qu'il permet. C'est l'unité de découverte :
   un épisode complet, pas chaque appel SQL compté comme un usage indépendant.
3. **La cible éventuelle du modèle** : route à proposer, catégorie sémantique,
   ou valeur inconnue à estimer. Cette annotation dépend du cas retenu et ne
   se déduit ni des noms de colonnes ni du modèle actuellement disponible.

Les labels de routage portent sur les demandes; les labels de prédiction
tabulaire portent sur les lignes et leur cible observée. Ce sont deux datasets.
La sortie du routeur actuel, le succès HTTP et un pouce positif restent des
observations : ils ne deviennent pas automatiquement la bonne réponse.

## Ce que les sources permettent déjà de repérer

Sources MCPs au HEAD `391be12078b1`, checkout propre lors de la lecture.
Chemins relatifs à `deposium_fullstack/deposium_MCPs`; aucun service observé.

| Parcours présent dans le code | Usage à rechercher dans les épisodes | Référence |
|---|---|---|
| `tabular.describe`, `preview`, `query` | Lire une feuille, sélectionner des colonnes, filtrer, trier; résultat exact attendu | `src/tools/tabular.ts:372` |
| Bridge tabulaire conditionnel du chat RAG | Répondre à partir du schéma et d'échantillons d'un fichier; vérifier si l'échantillon suffit réellement | `src/routes/chat-handlers/rag.ts:6398` |
| Handlers DuckDB natifs | Requête exacte, dont agrégation/jointure si autorisées par le handler concerné; relever le transport réel | `src/mcp-server.ts:293` |
| Routage DSPy | Choisir intention/moteur/template, puis contrôler séparément la requête produite et son résultat | Fiche `mcps.dspy-structured-routing`, [local-only material, not distributed](PROTOCOL.md) |
| Tables climat/NDVI GeoAI | Chercher un consommateur et une décision temporelle avant de définir une cible future | [Audit des points de raccordement](KUMO_QWEN_CLEF_CANDIDATES.md#raccordement-aux-sources-deposium) |

Le bridge RAG ne démontre pas un parcours général question libre → SQL exact.
`tabular.query` expose des filtres structurés; il n'expose pas lui-même un
langage complet d'agrégation/jointure. L'outil DuckDB natif et le dispatcher
TypeScript ne sont pas des chemins interchangeables. Aucune prédiction
statistique de colonne n'a été identifiée dans les parcours examinés.

Le [local-only material, not distributed](PROTOCOL.md) conserve ses contrats et
vocabulaires propres. Cette fiche d'usage ne crée pas une taxonomie commune
destinée à remplacer les enums applicatifs ou les contrôles d'accès.
Rattacher les épisodes, selon le chemin parcouru, à `mcps.intent-cascade`,
`mcps.context-source-dispatch`, `mcps.semantic-source-route`,
`mcps.dspy-structured-routing` et `mcps.final-handler-routing`.
`worker.tabular-admission` reste déterministe. Aucune de ces fiches ne couvre
à elle seule toute la tâche utilisateur sur une feuille.

Les manifestes [decisions-v1](../datasets/decisions-v1/manifest.json) et
[context-choice-v1](../datasets/context-choice-v1/manifest.json) décrivent des
cas synthétiques sans revue humaine achevée. Ils servent aux régressions et
comparaisons exploratoires, pas à prouver des usages XLSX réels.

## Trier les besoins avant de sélectionner un modèle

Exemples de catégories d'annotation, **pas de demandes réelles déjà observées** :

| Tâche attendue | Référence à préparer | Famille d'expérience possible |
|---|---|---|
| Lire, filtrer, compter, sommer, joindre, appliquer une formule connue | Résultat exact sur un snapshot; requête/calcul vérifiés | Tests déterministes; compréhension de demande évaluée séparément |
| Choisir feuille, colonne, source, outil ou présentation | Sélection attendue revue dans le contexte et alternatives acceptables | Routage/choix sémantique, si une difficulté réelle est observée |
| Attribuer une catégorie à un libellé libre | Définitions métier et exemples annotés par un humain | Classification sémantique |
| Estimer une valeur ou classe indisponible au moment d'agir | Cible mesurée ensuite ou dans des lignes indépendantes, avec date de disponibilité | Prédiction tabulaire, si le résultat change une action |
| Demande ambiguë, résultat inutilisable ou aucun consommateur identifié | Information manquante et motif | Clarifier, corriger le parcours ou ne pas lancer de modèle |

Plusieurs catégories peuvent coexister dans un épisode : sélectionner une
colonne demande parfois de la compréhension, puis sa somme reste exacte.
Une valeur absente ne constitue pas à elle seule une raison de l'imputer.

## Fiche minimale à remplir sur chaque épisode

| Champ | Contenu attendu |
|---|---|
| Preuve | ID local de l'épisode, provenance autorisée, date, statut : capacité repérée / usage observé / besoin confirmé |
| Demande | Formulation réelle et contexte de suivi suffisant, rôle de l'utilisateur, domaine |
| Table | Référence/version du fichier et feuille ou table; une ligne représente quoi, colonnes/types/unités pertinents, ordre de grandeur, données manquantes |
| Résultat attendu | Sortie souhaitée et **action ou décision permise**; responsable capable de confirmer son utilité |
| Parcours observé | Contrats/outils, paramètres nécessaires, version des sources, résultat/erreur/abandon, durée si disponible |
| Diagnostic humain | Calcul exact possible ? Ambiguïté de sens ? Information réellement inconnue ? Ce qui a échoué, correction attendue, alternatives acceptables |
| Valeur | Récurrence observée et taille de l'échantillon, temps perdu ou enjeu, coût d'une mauvaise réponse; inconnus explicités |
| Cible, seulement si pertinente | Variable et unité/classe, grain, origine/horizon, disponibilité des entrées et de la vérité, décision différente selon la prédiction |
| Revue | Auteur, justification, désaccords, statut à revoir/accepté/rejeté, groupe document/entité/conversation et traductions |

Conserver les références aux données autorisées hors Git; une vue expurgée
peut suffire à la découverte. Un replay scientifique demandera ensuite un
snapshot reproductible, et non seulement un hash de message ou un aperçu.
Les annotations attendues restent séparées des entrées du futur candidat.

## Réutiliser les traces, compléter seulement ce qui manque

Les sources offrent des points de départ, dont la disponibilité effective
devra être vérifiée sur l'échantillon choisi :

- `src/routes/chat-stream.ts:275` construit des journaux de runs avec intention,
  outils, étapes, durée et état terminal. Ils décrivent le parcours exécuté;
  ils ne contiennent pas nécessairement le besoin métier ni la réponse attendue.
- `src/http-server/tools-call-handler.ts:310` journalise les appels MCP directs,
  avec un message `[MCP] outil` et `step_details: null`. Cette trace seule ne
  reconstitue pas la demande utilisateur ou les filtres de la table.
- `src/routes/feedback.ts:230` accepte un retour positif/négatif/partiel et du
  contexte de route/datasets. Relier ce signal à une revue humaine; distinguer
  les problèmes de calcul, routage, couverture et présentation.
- `src/services/query-history.ts:221` propose un historique de requêtes;
  son branchement systématique sur `tabular.query` n'est pas établi ici.

Aucun export global ni nouvelle instrumentation n'est activé. Si les traces
disponibles ne suffisent pas, commencer par une observation manuelle accompagnée;
spécifier ensuite uniquement les champs manquants à un point d'entrée précis.

## Sortie de T0 et passage au banc

Commencer par un petit lot de lecture, par exemple 20–30 épisodes autorisés si
disponibles, incluant réussites, corrections, échecs et abandons. Ce nombre
borne l'effort de découverte; il ne prouve aucune représentativité statistique.
Dédupliquer les reprises et documenter les utilisateurs, périodes et flux
absents avant de parler de fréquence. Des exemples synthétiques peuvent tester
la grille, mais ne prouvent jamais une demande produit.

Pour chaque famille, produire : besoins confirmés, fréquence connue/inconnue,
action consommatrice, mécanisme exact de référence, difficulté résiduelle,
données/cibles disponibles et décision **corriger l'existant / préparer un
benchmark ciblé / différer**. Une fréquence élevée n'est pas obligatoire si
l'usage est critique et confirmé; une démonstration technique ne suffit pas.

Un pilote prédictif ne commence qu'avec un consommateur, une cible mesurable,
des entrées disponibles au moment d'agir, une baseline simple, des splits
indépendants et un critère d'utilité fixé avant les essais. Sans cela, Kumo
reste dans la veille. La Phase 5 GeoAI demeure différée et aucun adaptateur
du banc n'est ajouté par T0.
