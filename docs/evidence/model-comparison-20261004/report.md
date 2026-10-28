# Comparaison des modèles de choix de contexte

Cas corrects / scorés / total ; les erreurs et absences restent dans le total.
Références agent à revoir humainement ; mesures exploratoires sur modèles isolés, pas parcours produit.

## Classement des bases

| Modèle | Corrects / scorés / total | Statuts (ok, unsupported, missing, error, timeout, abstain) | Médiane / p95 adaptateur ok (ms) | Premier appel (ms) | RSS max observé (MiB) |
|---|---:|---|---:|---:|---:|
| Jev | 123/132/132 | 132/0/0/0/0/0 | 280.5 / 323.3 (132) | 303.7 | non observé (0/132 rapportés) |
| Noma | 98/132/132 | 132/0/0/0/0/0 | 4206.3 / 5157.5 (132) | 3794.0 | 4938.7 (132/132 rapportés) |
| Eos | 77/132/132 | 132/0/0/0/0/0 | 1122.6 / 1379.7 (132) | 1053.2 | 3524.8 (132/132 rapportés) |
| GLiNER | 59/132/132 | 132/0/0/0/0/0 | 234.9 / 401.0 (132) | 263.6 | 2891.9 (132/132 rapportés) |
| Laya | 56/132/132 | 132/0/0/0/0/0 | 168.9 / 219.7 (132) | 193.7 | 2324.9 (132/132 rapportés) |
| Julia | 52/132/132 | 132/0/0/0/0/0 | 59.0 / 83.2 (132) | 77.0 | 992.4 (132/132 rapportés) |
| Indecis | 44/132/132 | 132/0/0/0/0/0 | 34.8 / 43.0 (132) | 56.4 | 1121.3 (132/132 rapportés) |

Le temps adaptateur exclut l'initialisation ; premier appel distingué. P95 descriptif par rang le plus proche.

## Domaines

| Groupe | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---|---|---|---|---|---|---|
| chemistry | 28/28/28 | 20/28/28 | 10/28/28 | 13/28/28 | 6/28/28 | 12/28/28 | 10/28/28 |
| documentary | 67/76/76 | 53/76/76 | 55/76/76 | 41/76/76 | 42/76/76 | 32/76/76 | 32/76/76 |
| mathematics | 28/28/28 | 25/28/28 | 12/28/28 | 5/28/28 | 8/28/28 | 8/28/28 | 2/28/28 |

## Langues

| Groupe | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---|---|---|---|---|---|---|
| en | 61/66/66 | 52/66/66 | 38/66/66 | 31/66/66 | 24/66/66 | 27/66/66 | 23/66/66 |
| fr | 62/66/66 | 46/66/66 | 39/66/66 | 28/66/66 | 32/66/66 | 25/66/66 | 21/66/66 |

## Domaines × langues

| Groupe | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---|---|---|---|---|---|---|
| chemistry / en | 14/14/14 | 10/14/14 | 4/14/14 | 6/14/14 | 3/14/14 | 7/14/14 | 5/14/14 |
| chemistry / fr | 14/14/14 | 10/14/14 | 6/14/14 | 7/14/14 | 3/14/14 | 5/14/14 | 5/14/14 |
| documentary / en | 33/38/38 | 29/38/38 | 28/38/38 | 22/38/38 | 18/38/38 | 17/38/38 | 17/38/38 |
| documentary / fr | 34/38/38 | 24/38/38 | 27/38/38 | 19/38/38 | 24/38/38 | 15/38/38 | 15/38/38 |
| mathematics / en | 14/14/14 | 13/14/14 | 6/14/14 | 3/14/14 | 3/14/14 | 3/14/14 | 1/14/14 |
| mathematics / fr | 14/14/14 | 12/14/14 | 6/14/14 | 2/14/14 | 5/14/14 | 5/14/14 | 1/14/14 |

## Difficulté

| Groupe | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---|---|---|---|---|---|---|
| D1 | 36/40/40 | 35/40/40 | 30/40/40 | 17/40/40 | 17/40/40 | 18/40/40 | 12/40/40 |
| D2 | 38/40/40 | 26/40/40 | 22/40/40 | 19/40/40 | 13/40/40 | 11/40/40 | 11/40/40 |
| D3 | 49/52/52 | 37/52/52 | 25/52/52 | 23/52/52 | 26/52/52 | 23/52/52 | 21/52/52 |

## Split

| Groupe | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---|---|---|---|---|---|---|
| calibration | 29/30/30 | 20/30/30 | 17/30/30 | 6/30/30 | 12/30/30 | 14/30/30 | 10/30/30 |
| test | 62/66/66 | 51/66/66 | 40/66/66 | 38/66/66 | 30/66/66 | 26/66/66 | 22/66/66 |
| train | 32/36/36 | 27/36/36 | 20/36/36 | 15/36/36 | 14/36/36 | 12/36/36 | 12/36/36 |

## Tâches documentaires

| Groupe | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---|---|---|---|---|---|---|
| ambiguous-selection | 2/2/2 | 2/2/2 | 1/2/2 | 0/2/2 | 2/2/2 | 0/2/2 | 0/2/2 |
| catalog-active-inventory | 1/2/2 | 1/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 | 2/2/2 |
| catalog-catalog-not-source-count | 2/2/2 | 2/2/2 | 1/2/2 | 0/2/2 | 2/2/2 | 1/2/2 | 2/2/2 |
| catalog-corrected-request | 2/2/2 | 1/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 0/2/2 | 1/2/2 |
| catalog-count-and-names | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| catalog-distinct-identities | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-metadata-owners | 1/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 | 2/2/2 |
| catalog-metadata-table-language | 2/2/2 | 1/2/2 | 2/2/2 | 2/2/2 | 1/2/2 | 0/2/2 | 2/2/2 |
| catalog-negative-summary | 2/2/2 | 1/2/2 | 1/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| catalog-quoted-summary-command | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| catalog-scope-after-interlude | 0/2/2 | 0/2/2 | 1/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| catalog-selected-titles | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| catalog-selection-reuse | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| retrieve_answer-content-date | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-exact-clause | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-explanation | 2/2/2 | 1/2/2 | 0/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 0/2/2 |
| retrieve_answer-content-filtered-list | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 1/2/2 | 0/2/2 |
| retrieve_answer-content-not-summary | 2/2/2 | 1/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 0/2/2 | 0/2/2 |
| retrieve_answer-content-refutation | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 | 1/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-total-unit | 2/2/2 | 1/2/2 | 0/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 0/2/2 |
| retrieve_answer-distant-report-reference | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 | 1/2/2 | 2/2/2 |
| retrieve_answer-followup-cause | 2/2/2 | 0/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-quoted-instruction-content | 1/2/2 | 0/2/2 | 0/2/2 | 1/2/2 | 1/2/2 | 1/2/2 | 0/2/2 |
| retrieve_answer-relations-mermaid | 2/2/2 | 0/2/2 | 2/2/2 | 1/2/2 | 0/2/2 | 1/2/2 | 0/2/2 |
| retrieve_answer-stale-summary-check | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 2/2/2 | 0/2/2 |
| stored_summaries-cached-descriptions | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 | 2/2/2 |
| stored_summaries-do-not-reread | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 | 0/2/2 |
| stored_summaries-existing-per-file | 2/2/2 | 1/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 2/2/2 |
| stored_summaries-inherit-summary-constraint | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 | 0/2/2 | 2/2/2 |
| stored_summaries-language-followup | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-quotation-not-budget-question | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 1/2/2 |
| stored_summaries-remaining-summaries | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 | 2/2/2 |
| stored_summaries-resume-after-content | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 | 1/2/2 |
| stored_summaries-summary-bundle | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 | 1/2/2 |
| stored_summaries-summary-count-title | 0/2/2 | 1/2/2 | 1/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 1/2/2 |
| stored_summaries-translate-summary-table | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 | 2/2/2 |
| stored_summaries-validated-abstracts | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 1/2/2 | 0/2/2 |
| unanchored-language | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 2/2/2 | 1/2/2 |

## Observation Mastra

Accord avec propositions d'agent ; références pending_human, aucun score sémantique final.

| Modèle | Accord / valides / total | Statuts | Médiane / p95 adaptateur ok (ms) | RSS max observé (MiB) |
|---|---:|---|---:|---:|
| Jev | 20/24/24 | 24/0/0/0/0/0 | 288.0 / 355.3 | non observé (0/24 rapportés) |
| Noma | 18/24/24 | 24/0/0/0/0/0 | 5259.6 / 6117.8 | 4734.0 (24/24 rapportés) |
| Eos | 19/24/24 | 24/0/0/0/0/0 | 1419.9 / 1754.2 | 3470.6 (24/24 rapportés) |
| GLiNER | 12/24/24 | 24/0/0/0/0/0 | 391.9 / 582.6 | 2886.2 (24/24 rapportés) |
| Laya | 10/24/24 | 24/0/0/0/0/0 | 267.4 / 375.1 | 2323.1 (24/24 rapportés) |
| Julia | 11/24/24 | 24/0/0/0/0/0 | 100.2 / 146.6 | 1019.3 (24/24 rapportés) |
| Indecis | 11/24/24 | 24/0/0/0/0/0 | 44.7 / 57.0 | 894.9 (24/24 rapportés) |

Sources, révisions et empreintes : voir analysis.json. Aucune sortie de cas ni contexte privé publié.
