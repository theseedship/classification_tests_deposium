# Mastra : propositions de première lecture — v0

Ce dossier contient **24 cas synthétiques, 12 familles FR/EN** pour proposer un
premier choix dans le périmètre du [local-only material, not distributed](../../docs/PROTOCOL.md).
Tous les cas restent `pending_human` : **zéro référence approuvée humainement**,
aucun usage observé, modèle, planner, service ou lecture métier exécuté.
Les propositions ne constituent pas un corpus de fine-tuning validé ni un PASS.

## Entrée et frontière

Chaque ligne utilise `deposium.mastra-read-review/v0`. Seul `candidate_input`
est destiné au candidat : `message`, `context` textuel et trois options
`{id,label,action}`. Les actions disponibles sont identiques dans chaque cas :

| Action | Consommateur envisagé | Limite |
|---|---|---|
| `search` | Wrapper Mastra in-process `deposium_search` | Passages bruts, arguments de recherche préparés hors candidat |
| `stats` | Wrapper Mastra in-process `deposium_analyze` | Comptes de documents et d’entités, un seul espace |
| `fallback` | Reprise par le planner, selon le protocole du banc | Aucun wrapper métier lancé par ce premier choix ; ni pseudo-HITL ni abstention produit prouvée |

Les champs `action` décrivent **toutes** les options, pas celle attendue. Les
références, justifications, splits, identifiants de famille et `execution`
restent hors de l’entrée du candidat. Aucun tenant, ID d’espace, secret ou
assertion de droits n’y est fourni. Le contexte décrit le périmètre du pilote ;
il ne remplace pas une authentification ou une vérification d’accès.

Les trois positions `a/b/c` tournent entre familles ; les deux traductions
gardent le même ordre sémantique. Les labels sont fixes dans chaque langue.
La recherche locale attend notamment `query_text`, tandis que la macro HTTP
homonyme attend `query` : ces propositions ne supposent pas leur équivalence.

## Familles, splits et revue

Il y a quatre familles par action proposée, soit huit cas par action. La
première famille de chaque action est en calibration, les trois autres en test :

| Split | Cas | Familles | Par action | Par position proposée |
|---|---:|---:|---:|---:|
| Calibration | 6 | 3 | 2 | 2 |
| Test | 18 | 9 | 6 | 6 |

Chaque langue compte 12 cas ; chacune a quatre propositions par position.
Les familles couvrent une demande directe, la négation, les instructions
citées, une faute de frappe, un renvoi contextuel, l’ambiguïté, une demande
composée et un comptage extérieur au corpus. Ce sont des épisodes rédigés
indépendamment, pas douze variantes numériques d’une même consigne, ni douze
utilisateurs observés. Les labels et le cadrage commun limitent leur diversité.

`reference.acceptable_choices` contient un ID proposé et sa justification ;
`reference.review` vaut toujours `pending_human`. La revue doit consigner auteur,
date, accords/désaccords, alternatives acceptables et arbitrage. La référence
n’a été fixée ni à partir d’une prédiction ni à partir du routeur actuel.
Les cas de test ne doivent pas servir à régler descriptions, règles ou seuils.

## Recette d’exécution distincte

Tous les cas désignent `execution.fixture_id="synthetic-corpus-a"`, conformément
au choix d’une petite recette synthétique commune. Ce locator n’est pas
candidat-visible. Ce dossier **ne matérialise pas** cette recette et ne prouve
ni ses droits ni son état runtime. Le runner devra disposer séparément du
tenant et de l’unique espace autorisés, des arguments fixés, de comptes connus
et de preuves de recherche vérifiables.

Les demandes de passages mentionnent exclusions de garantie, procédures de
verrouillage, un titre formulé comme un comptage et fermeture provisoire des
accès. La qualification de la recette doit préciser si ces éléments existent
dans ses documents. Le choix d’outil proposé ne fournit pas, à lui seul, un
oracle d’IDs, d’extraits ou de résultats métier. Un résultat vide légitime doit
rester distinct d’une erreur et d’une extraction utile manquante.

La recette commune n’est pas un corpus documentaire tenu à l’écart entre
calibration et test : les splits séparent ici les **familles de demandes**.
Une généralisation à de nouveaux documents/espaces exige une autre partition.
Aucun contrôle « liste les espaces » ou graphe bloqué n’est introduit dans ce
pool de deux wrappers : ces opérations ont des frontières distinctes.

## Intégrité et validation

[manifest.json](manifest.json) conserve le SHA-256 exact des lignes de
[cases.jsonl](cases.jsonl), les comptes, la politique de split et la source MCPs
`391be12078b1f3daa24a50c31c3a39eb72d7fb94`. Les hashes de deux fichiers
applicatifs identifient les octets lus ; ils ne scellent pas un runtime complet.

Ce format de revue est distinct de `deposium.case/v1` et `/v2` et de
`bench.context-choice`. Ne pas le passer implicitement à un ancien runner.
Une validation structurelle, une exécution de fixture ou un score contre ces
propositions ne vaut pas approbation humaine ni preuve du gain de latence.

Commandes livrées : `python3 -m deposium_bench validate-mastra-read`, puis
`prepare-mastra-read --output results/mastra-read-prepared-NNN` pour exporter
la projection au protocole de choix existant. Cette projection ne fournit
au modèle que contexte/question/descriptions des options ; les IDs permettent
le mapping du résultat et `action` reste dans le protocole d'exécution.
`check-mastra-read` qualifie séparément les wrappers sur réponses backend
simulées : il ne joue pas les 24 demandes contre un index documentaire.
Voir [local-only material, not distributed](../../docs/PROTOCOL.md).
