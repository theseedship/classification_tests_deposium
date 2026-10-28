# Decisions v1 — corpus exploratoire

36 cas synthétiques FR/EN, regroupés en 18 scénarios et familles de traduction.
Aucune donnée privée, aucun poids et aucun service ne sont requis pour valider
le corpus. Les annotations sont rédigées par un agent; **la revue humaine et
linguistique n’a pas été effectuée**. Le corpus sert à explorer les décisions,
pas à certifier la fiabilité de Deposium.

`manifest.json` fixe la version, le hash exact de `cases.jsonl`, la provenance,
les splits et les limites. Scénarios, documents et traductions restent dans le
même split. Les références ont été établies à partir des exigences et des
contrats natifs avant tout replay de composant; une mauvaise sortie réelle ne
justifie pas leur réécriture pour obtenir un score vert.

Les opérations DOC et PRESENTATION appellent le contrat du planner MCPs;
FOLLOWUP utilise la sélection native, et SOURCES le dispatch ou la résolution
sémantique. Le resolver FOLLOWUP reçoit une éligibilité déjà déterminée et un
contexte structuré identique en FR/EN: ces paires ne testent pas sa compréhension
linguistique. La langue reste un axe de provenance du scénario.

Les identités d’inventaire décrivent des exigences de qualité. Aucun de ces
appels ne lit les documents canoniques, ne valide les droits d’accès, ni ne
prouve le compte/liste/résumés dans une réponse produit. Un choix `passthrough`
ne prouve pas l’existence d’un connecteur ni l’exécution de la recherche.

EVIDENCE fournit seulement une requête et un pool figé de passages. La sortie
candidate attendue porte `evidence_ids`, `contradiction_ids` et `insufficient`.
Une contradiction utile appartient aussi aux preuves. Ce protocole de décision
est distinct de `searchHub`; le bridge du lot 1 renvoie `unsupported` pour
`mcps.search`. Il n’exécute ni recherche ni rerank et ne copie pas ces règles.
L’abstention est permise uniquement pour la famille `evidence-insufficient`.

Les références restent exclusivement dans `reference`. `candidate_request`
transmet seulement `case_id`, `contract_id` et une copie de `input`. Les scores
exacts portent sur les champs affirmés: ils ne jugent pas la vérité d’un texte
généré ni les champs laissés hors assertions.

```bash
python3 -m unittest tests.test_cases tests.test_scoring -v
```
