# Sélection d’outils — revue v0

Ce dossier amorce **16 cas synthétiques, 8 familles FR/EN** : 14 propositions de
choix à revoir humainement et 2 contrôles `contract_gap` bloqués. Aucun usage réel,
score, campagne ou dataset d’entraînement prêt. Les splits sont `unassigned`.

Les formats `deposium.tool-selection-review/v0` et
`deposium.tool-selection-review-manifest/v0` sont distincts des formats exécutables
du banc. **Ne pas passer ces fichiers au runner actuel.** Aucun adaptateur,
scorer ou harness de ces frontières n’est livré ici. Le manifeste contient le
hash des cas, le HEAD MCPs et les hashes de cinq sources; cela ne démontre pas
leur exécution runtime. Aucun code ou fixture applicatif n’a été modifié.

## Frontières et références

- Connecteurs : données publiques françaises, essais cliniques, négation des
  essais avec demande de population, traduction d’une phrase sans recherche.
  Pool Datagouv / ClinicalTrials / aucun. `none` signifie aucune sélection, pas
  un outil MCP. Le handler applique un choix au maximum; éligibilité, droits,
  disponibilité et ressources restent déterministes. Les fixtures bornent le
  périmètre, leurs golds de parité lexicale ne sont pas copiés comme golds
  sémantiques. Décisions existantes : `mcps.connector-orchestrator-selection`
  et `mcps.legacy-connector-keyword-choice`, sans contrat runner ajouté.
- Mastra **in-process** : passages, contrôle graphe, comptes du corpus, appel de
  réponse citée après une observation antérieure. Six noms réellement déclarés :
  `deposium_search`, `deposium_graph`, `deposium_analyze`, `deposium_answer`,
  `abstain_decision`, `escalate_decision`. Les deux derniers sont des pseudo-outils;
  interception HITL/fallback non prouvée et aucun choix attendu ne les désigne.
  `mcps.autonomous-agent-loop` désigne un autre executor : pas de couverture
  directe, pas d’ID de décision/contrat inventé pour ce bridge spécifique.

## Limites contractuelles

Le bridge graphe déclare `path` mais ne traite que `neighbors` et `search`, puis
retourne `not_implemented`. Il signale aussi un mauvais câblage d’arguments.
Les deux cas Alpha/Beta ont donc `acceptable_choices: []` et
`qualification: blocked_implementation`. Ne pas les scorer ni les entraîner,
ni fabriquer un gold `abstain`/`escalate`. Une correction requiert une nouvelle
revue explicite; le choix et l’exécution restent des preuves distinctes.

Le cas analyse attend des **comptes de documents et d’entités**, pas des thèmes.
Le cas réponse appelle le parcours cité, conformément à sa description, mais
`deposium_answer` relance `executeChat` et ne reçoit pas les blocs précédents.
L’observation de recherche est synthétique et antérieure au choix; ni sa
réutilisation, ni suppression d’une recherche, ni gain de chaîne ne sont promis.

## Préparer la revue, puis seulement une expérience

Seul `candidate_input` serait visible au futur candidat : message, observations
antérieures et options. IDs `c1`… opaques; ordre tournant entre familles et même
ordre de noms pour les deux langues d’une famille. Références, diagnostics,
provenance, qualification et justifications restent hors de l’entrée candidate.
Aucune prédiction ni sortie du routeur actuel n’a servi à fixer les propositions.

Consigner auteur/date, choix acceptables, justifications, désaccords et arbitrage.
Grouper familles/traductions/variantes avant de fixer des splits. Tous les cas
sont actuellement non scorables et non éligibles à l’entraînement. Un futur
scorer séparera sélection, arguments, dépendances, résultat et synthèse. Les
contrôles identité/ACL/consentement/ressources ne sont pas appris.

La baseline connecteur est déjà heuristique et rapide : viser un gain de qualité,
pas prétendre accélérer le routage. Mastra pourrait éviter un tour LLM de choix
seulement quand les arguments et le scope sont résolus; aucun gain mesuré ici.
Aucun modèle, test applicatif, service ou boucle agent exécuté par ce dossier.
