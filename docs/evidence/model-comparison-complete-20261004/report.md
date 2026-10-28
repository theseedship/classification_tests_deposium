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

## Domaines × split

| Groupe | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---|---|---|---|---|---|---|
| chemistry / calibration | 8/8/8 | 4/8/8 | 3/8/8 | 0/8/8 | 3/8/8 | 3/8/8 | 3/8/8 |
| chemistry / test | 14/14/14 | 12/14/14 | 5/14/14 | 9/14/14 | 3/14/14 | 7/14/14 | 5/14/14 |
| chemistry / train | 6/6/6 | 4/6/6 | 2/6/6 | 4/6/6 | 0/6/6 | 2/6/6 | 2/6/6 |
| documentary / calibration | 13/14/14 | 8/14/14 | 12/14/14 | 4/14/14 | 8/14/14 | 8/14/14 | 7/14/14 |
| documentary / test | 34/38/38 | 28/38/38 | 27/38/38 | 26/38/38 | 22/38/38 | 15/38/38 | 15/38/38 |
| documentary / train | 20/24/24 | 17/24/24 | 16/24/24 | 11/24/24 | 12/24/24 | 9/24/24 | 10/24/24 |
| mathematics / calibration | 8/8/8 | 8/8/8 | 2/8/8 | 2/8/8 | 1/8/8 | 3/8/8 | 0/8/8 |
| mathematics / test | 14/14/14 | 11/14/14 | 8/14/14 | 3/14/14 | 5/14/14 | 4/14/14 | 2/14/14 |
| mathematics / train | 6/6/6 | 6/6/6 | 2/6/6 | 0/6/6 | 2/6/6 | 1/6/6 | 0/6/6 |

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

## Types de tâche, tous domaines

| Groupe | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---|---|---|---|---|---|---|
| aliquot-and-mix | 2/2/2 | 0/2/2 | 1/2/2 | 0/2/2 | 1/2/2 | 0/2/2 | 0/2/2 |
| ambiguous-selection | 2/2/2 | 2/2/2 | 1/2/2 | 0/2/2 | 2/2/2 | 0/2/2 | 0/2/2 |
| atoms-and-charge | 2/2/2 | 2/2/2 | 1/2/2 | 2/2/2 | 1/2/2 | 2/2/2 | 2/2/2 |
| cancel-keep-domain | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
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
| chain-derivative | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| combustion-balance | 2/2/2 | 0/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 1/2/2 |
| conditional-probability | 2/2/2 | 2/2/2 | 0/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 |
| conserved-dilution | 2/2/2 | 2/2/2 | 1/2/2 | 2/2/2 | 0/2/2 | 2/2/2 | 2/2/2 |
| extraneous-equation-root | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 2/2/2 | 1/2/2 | 0/2/2 |
| formula-not-structure | 2/2/2 | 2/2/2 | 0/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 1/2/2 |
| fraction-addition | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| function-types | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| group-atom-count | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| hydrate-water-fraction | 2/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 1/2/2 | 0/2/2 | 0/2/2 |
| ionic-neutrality | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 1/2/2 | 0/2/2 | 0/2/2 |
| limiting-reactant | 2/2/2 | 0/2/2 | 0/2/2 | 2/2/2 | 0/2/2 | 2/2/2 | 2/2/2 |
| matrix-product | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| missing-final-volume | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 2/2/2 | 1/2/2 |
| molar-concentration | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 2/2/2 | 0/2/2 |
| nested-complex-count | 2/2/2 | 2/2/2 | 0/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| polynomial-remainder | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| precipitate-mass | 2/2/2 | 0/2/2 | 1/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| principal-root | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| quantity-dimension | 2/2/2 | 1/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 2/2/2 | 0/2/2 |
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
| square-expansion | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 1/2/2 | 0/2/2 |
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
| transpose-chain | 2/2/2 | 2/2/2 | 0/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 0/2/2 |
| unanchored-language | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 | 1/2/2 | 2/2/2 | 1/2/2 |
| underdetermined-linear | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 1/2/2 | 1/2/2 | 0/2/2 |
| unknown-function-values | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| water-balance | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 | 2/2/2 | 1/2/2 | 1/2/2 |

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

## Temps base (ms)

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| adapter_ms | 243.3 / 280.5 / 323.3 / 363.1 (132) | 3292.1 / 4206.3 / 5157.5 / 5848.9 (132) | 927.8 / 1122.6 / 1379.7 / 1536.4 (132) | 167.3 / 234.9 / 401.0 / 519.8 (132) | 116.0 / 168.9 / 219.7 / 276.2 (132) | 41.4 / 59.0 / 83.2 / 104.9 (132) | 24.7 / 34.8 / 43.0 / 56.4 (132) |
| decision_ms | — (0) | 3287.3 / 4201.6 / 5152.5 / 5843.3 (132) | 924.2 / 1119.2 / 1376.2 / 1533.0 (132) | 159.0 / 226.9 / 391.3 / 501.1 (132) | 82.5 / 135.9 / 185.4 / 243.2 (132) | 36.8 / 54.7 / 78.6 / 100.6 (132) | 16.6 / 26.3 / 34.5 / 48.3 (132) |
| http_ms | 226.4 / 268.8 / 315.2 / 356.5 (132) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| inference_ms | — (0) | 1833.3 / 2609.8 / 3271.8 / 3560.2 (132) | 923.0 / 1117.7 / 1374.9 / 1531.3 (132) | 157.1 / 224.7 / 389.0 / 495.6 (132) | 81.3 / 134.1 / 183.8 / 241.7 (132) | 36.7 / 54.6 / 78.5 / 100.5 (132) | 16.5 / 26.1 / 34.4 / 48.0 (132) |

## Phases et ressources base

Initialisation, premier appel, puis médiane / p95 des appels ok suivants ; mémoire RSS observée dans le worker et couverture sur tous les appels.

| Modèle | Init ms | Premier appel ms (statut) | Après premier ok ms (n) | RSS worker max MiB (n/total) | RSS chargement MiB |
|---|---:|---|---:|---:|---:|
| Jev | — | 303.7 (ok) | 280.3 / 323.3 (131) | — (0/132) | — |
| Noma | 12309.9 | 3794.0 (ok) | 4209.6 / 5157.5 (131) | 4938.7 (132/132) | 704.3 |
| Eos | 13056.8 | 1053.2 (ok) | 1123.6 / 1379.7 (131) | 3524.8 (132/132) | 3467.2 |
| GLiNER | 13096.7 | 263.6 (ok) | 234.9 / 401.0 (131) | 2891.9 (132/132) | 2891.9 |
| Laya | 11186.0 | 193.7 (ok) | 168.9 / 219.7 (131) | 2324.9 (132/132) | 2324.9 |
| Julia | 14164.9 | 77.0 (ok) | 59.0 / 83.2 (131) | 992.4 (132/132) | 926.0 |
| Indecis | 1160.5 | 56.4 (ok) | 34.8 / 43.0 (131) | 1121.3 (132/132) | 789.5 |

## Temps base par statut (ms)

Médiane / p95 (n) ; temps adaptateur inclut les échecs enregistrés.

| Statut / mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| ok / adapter_ms | 280.5 / 323.3 (132) | 4206.3 / 5157.5 (132) | 1122.6 / 1379.7 (132) | 234.9 / 401.0 (132) | 168.9 / 219.7 (132) | 59.0 / 83.2 (132) | 34.8 / 43.0 (132) |
| ok / inference_ms | — (0) | 2609.8 / 3271.8 (132) | 1117.7 / 1374.9 (132) | 224.7 / 389.0 (132) | 134.1 / 183.8 (132) | 54.6 / 78.5 (132) | 26.1 / 34.4 (132) |
| ok / decision_ms | — (0) | 4201.6 / 5152.5 (132) | 1119.2 / 1376.2 (132) | 226.9 / 391.3 (132) | 135.9 / 185.4 (132) | 54.7 / 78.6 (132) | 26.3 / 34.5 (132) |
| ok / http_ms | 268.8 / 315.2 (132) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |

## Tokens natifs base

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| encoded_tokens | — (0) | 79.0 / 116.0 / 145.0 / 161.0 (132) | 131.0 / 164.5 / 193.0 / 210.0 (132) | 54.0 / 104.0 / 138.0 / 152.0 (132) | 45.0 / 78.0 / 111.0 / 123.0 (132) | 45.0 / 78.0 / 111.0 / 123.0 (132) | 18.0 / 29.0 / 59.0 / 75.0 (132) |
| indecis_max_sequence_tokens | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) | 18.0 / 29.0 / 59.0 / 75.0 (132) |
| indecis_sum_tokens | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) | 72.0 / 113.5 / 152.0 / 168.0 (132) |
| padded_tokens | — (0) | — (0) | — (0) | 54.0 / 104.0 / 138.0 / 152.0 (132) | — (0) | 48.0 / 80.0 / 112.0 / 128.0 (132) | — (0) |

## Tokens déclarés par le fournisseur, base

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| input_tokens | 324.0 / 363.0 / 397.0 / 406.0 (132) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| output_tokens | 50.0 / 85.0 / 107.0 / 115.0 (132) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |

## Tokens natifs base par domaine

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| chemistry | — (0) | 131.5 / 159.0 (28) | 179.5 / 207.0 (28) | 98.5 / 136.0 (28) | 98.0 / 122.0 (28) | 98.0 / 122.0 (28) | 38.0 / 70.0 (28) |
| documentary | — (0) | 119.0 / 140.0 (76) | 167.0 / 190.0 (76) | 113.0 / 143.0 (76) | 81.0 / 101.0 (76) | 81.0 / 101.0 (76) | 28.0 / 38.0 (76) |
| mathematics | — (0) | 99.5 / 128.0 (28) | 151.0 / 176.0 (28) | 81.0 / 137.0 (28) | 63.0 / 103.0 (28) | 63.0 / 103.0 (28) | 31.5 / 70.0 (28) |

## Tokens natifs base par langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| en | — (0) | 108.0 / 137.0 (66) | 156.0 / 189.0 (66) | 95.5 / 122.0 (66) | 72.5 / 103.0 (66) | 72.5 / 103.0 (66) | 26.0 / 58.0 (66) |
| fr | — (0) | 123.5 / 149.0 (66) | 174.0 / 197.0 (66) | 114.0 / 143.0 (66) | 86.0 / 111.0 (66) | 86.0 / 111.0 (66) | 32.0 / 63.0 (66) |

## Tokens natifs base par domaine × langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| chemistry / en | — (0) | 123.5 / 155.0 (14) | 172.5 / 203.0 (14) | 93.5 / 127.0 (14) | 88.0 / 117.0 (14) | 88.0 / 117.0 (14) | 35.5 / 70.0 (14) |
| chemistry / fr | — (0) | 137.0 / 161.0 (14) | 185.5 / 210.0 (14) | 103.0 / 137.0 (14) | 101.5 / 123.0 (14) | 101.5 / 123.0 (14) | 41.0 / 75.0 (14) |
| documentary / en | — (0) | 110.0 / 124.0 (38) | 158.5 / 172.0 (38) | 98.5 / 122.0 (38) | 73.5 / 88.0 (38) | 73.5 / 88.0 (38) | 25.0 / 36.0 (38) |
| documentary / fr | — (0) | 126.5 / 142.0 (38) | 175.5 / 192.0 (38) | 121.5 / 147.0 (38) | 87.0 / 105.0 (38) | 87.0 / 105.0 (38) | 31.0 / 44.0 (38) |
| mathematics / en | — (0) | 98.0 / 128.0 (14) | 149.5 / 176.0 (14) | 74.0 / 137.0 (14) | 61.5 / 103.0 (14) | 61.5 / 103.0 (14) | 29.0 / 70.0 (14) |
| mathematics / fr | — (0) | 102.0 / 130.0 (14) | 153.0 / 178.0 (14) | 86.0 / 140.0 (14) | 65.5 / 105.0 (14) | 65.5 / 105.0 (14) | 33.0 / 71.0 (14) |

## Tokens fournisseur base par domaine

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| chemistry / input_tokens | 338.0 / 371.5 / 401.0 / 403.0 (28) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| chemistry / output_tokens | 50.0 / 72.0 / 115.0 / 115.0 (28) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| documentary / input_tokens | 344.0 / 368.5 / 397.0 / 406.0 (76) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| documentary / output_tokens | 80.0 / 87.0 / 107.0 / 107.0 (76) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| mathematics / input_tokens | 324.0 / 343.0 / 370.0 / 370.0 (28) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| mathematics / output_tokens | 50.0 / 55.0 / 84.0 / 84.0 (28) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |

## Tokens fournisseur base par langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| en / input_tokens | 324.0 / 352.5 / 381.0 / 394.0 (66) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| en / output_tokens | 50.0 / 82.0 / 87.0 / 115.0 (66) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| fr / input_tokens | 327.0 / 379.0 / 399.0 / 406.0 (66) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| fr / output_tokens | 50.0 / 102.0 / 107.0 / 115.0 (66) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |

## Tokens fournisseur base par domaine × langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| chemistry / en / input_tokens | 338.0 / 365.0 / 394.0 / 394.0 (14) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| chemistry / en / output_tokens | 50.0 / 72.0 / 115.0 / 115.0 (14) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| chemistry / fr / input_tokens | 341.0 / 380.5 / 403.0 / 403.0 (14) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| chemistry / fr / output_tokens | 50.0 / 72.0 / 115.0 / 115.0 (14) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| documentary / en / input_tokens | 344.0 / 355.0 / 368.0 / 371.0 (38) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| documentary / en / output_tokens | 80.0 / 85.0 / 87.0 / 87.0 (38) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| documentary / fr / input_tokens | 365.0 / 383.0 / 399.0 / 406.0 (38) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| documentary / fr / output_tokens | 83.0 / 105.0 / 107.0 / 107.0 (38) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| mathematics / en / input_tokens | 324.0 / 341.5 / 367.0 / 367.0 (14) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| mathematics / en / output_tokens | 50.0 / 55.0 / 84.0 / 84.0 (14) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| mathematics / fr / input_tokens | 327.0 / 345.5 / 370.0 / 370.0 (14) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| mathematics / fr / output_tokens | 50.0 / 55.0 / 84.0 / 84.0 (14) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |

## Longueur commune des entrées base

Somme des caractères Unicode ou mots séparés par espace dans le contexte, la question et les descriptions d'options visibles par tous ; exclut les identifiants et la sérialisation.

| Mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| characters | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) |
| words | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) |

Tokens natifs : encodage propre à chaque adaptateur ; `indecis_max_sequence_tokens` mesure la plus longue séquence, `indecis_sum_tokens` la somme des séquences. Tokens fournisseur : comptabilité postérieure à la requête, non comparable au tokenizer local. RSS : pics rapportés par worker, sans RAM serveur distant.

## Confusion des actions documentaires sur la base

| Attendu → prédit | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| catalog → catalog | 20 | 14 | 13 | 8 | 10 | 5 | 11 |
| catalog → insufficient_information | 2 | 5 | 3 | 0 | 1 | 5 | 7 |
| catalog → retrieve_answer | 1 | 0 | 4 | 1 | 3 | 12 | 2 |
| catalog → stored_summaries | 1 | 5 | 4 | 15 | 10 | 2 | 4 |
| insufficient_information → A | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| insufficient_information → A_and_B | 0 | 0 | 1 | 1 | 0 | 1 | 2 |
| insufficient_information → B | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| insufficient_information → insufficient_information | 4 | 4 | 3 | 0 | 3 | 2 | 1 |
| insufficient_information → retrieve_answer | 0 | 0 | 0 | 2 | 0 | 0 | 1 |
| insufficient_information → stored_summaries | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| retrieve_answer → catalog | 0 | 0 | 0 | 2 | 5 | 0 | 12 |
| retrieve_answer → insufficient_information | 3 | 9 | 8 | 1 | 6 | 4 | 1 |
| retrieve_answer → retrieve_answer | 21 | 13 | 16 | 11 | 7 | 16 | 4 |
| retrieve_answer → stored_summaries | 0 | 2 | 0 | 10 | 6 | 4 | 7 |
| stored_summaries → catalog | 2 | 1 | 1 | 2 | 1 | 1 | 4 |
| stored_summaries → insufficient_information | 0 | 0 | 0 | 0 | 0 | 2 | 3 |
| stored_summaries → retrieve_answer | 0 | 1 | 0 | 0 | 1 | 12 | 1 |
| stored_summaries → stored_summaries | 22 | 22 | 23 | 22 | 22 | 9 | 16 |

## Confusion documentaire base FR

| Attendu → prédit | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| catalog → catalog | 11 | 7 | 5 | 4 | 5 | 3 | 5 |
| catalog → insufficient_information | 0 | 2 | 3 | 0 | 1 | 2 | 3 |
| catalog → retrieve_answer | 1 | 0 | 2 | 0 | 2 | 6 | 2 |
| catalog → stored_summaries | 0 | 3 | 2 | 8 | 4 | 1 | 2 |
| insufficient_information → A | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| insufficient_information → A_and_B | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| insufficient_information → insufficient_information | 2 | 2 | 2 | 0 | 1 | 1 | 0 |
| insufficient_information → retrieve_answer | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| insufficient_information → stored_summaries | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| retrieve_answer → catalog | 0 | 0 | 0 | 1 | 3 | 0 | 5 |
| retrieve_answer → insufficient_information | 2 | 5 | 4 | 0 | 2 | 0 | 1 |
| retrieve_answer → retrieve_answer | 10 | 5 | 8 | 4 | 6 | 10 | 2 |
| retrieve_answer → stored_summaries | 0 | 2 | 0 | 7 | 1 | 2 | 4 |
| stored_summaries → catalog | 1 | 1 | 0 | 1 | 0 | 0 | 3 |
| stored_summaries → insufficient_information | 0 | 0 | 0 | 0 | 0 | 1 | 1 |
| stored_summaries → retrieve_answer | 0 | 1 | 0 | 0 | 0 | 10 | 0 |
| stored_summaries → stored_summaries | 11 | 10 | 12 | 11 | 12 | 1 | 8 |

## Confusion documentaire base EN

| Attendu → prédit | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| catalog → catalog | 9 | 7 | 8 | 4 | 5 | 2 | 6 |
| catalog → insufficient_information | 2 | 3 | 0 | 0 | 0 | 3 | 4 |
| catalog → retrieve_answer | 0 | 0 | 2 | 1 | 1 | 6 | 0 |
| catalog → stored_summaries | 1 | 2 | 2 | 7 | 6 | 1 | 2 |
| insufficient_information → A_and_B | 0 | 0 | 1 | 0 | 0 | 1 | 1 |
| insufficient_information → B | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| insufficient_information → insufficient_information | 2 | 2 | 1 | 0 | 2 | 1 | 1 |
| insufficient_information → retrieve_answer | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| retrieve_answer → catalog | 0 | 0 | 0 | 1 | 2 | 0 | 7 |
| retrieve_answer → insufficient_information | 1 | 4 | 4 | 1 | 4 | 4 | 0 |
| retrieve_answer → retrieve_answer | 11 | 8 | 8 | 7 | 1 | 6 | 2 |
| retrieve_answer → stored_summaries | 0 | 0 | 0 | 3 | 5 | 2 | 3 |
| stored_summaries → catalog | 1 | 0 | 1 | 1 | 1 | 1 | 1 |
| stored_summaries → insufficient_information | 0 | 0 | 0 | 0 | 0 | 1 | 2 |
| stored_summaries → retrieve_answer | 0 | 0 | 0 | 0 | 1 | 2 | 1 |
| stored_summaries → stored_summaries | 11 | 12 | 11 | 11 | 10 | 8 | 8 |

## Cohérence des traductions documentaires FR/EN

| Modèle | Paires scorées / total | Même action | Deux correctes |
|---|---:|---:|---:|
| Jev | 38/38 | 34/38 | 32/38 |
| Noma | 38/38 | 28/38 | 22/38 |
| Eos | 38/38 | 31/38 | 25/38 |
| GLiNER | 38/38 | 32/38 | 19/38 |
| Laya | 38/38 | 23/38 | 15/38 |
| Julia | 38/38 | 16/38 | 8/38 |
| Indecis | 38/38 | 25/38 | 13/38 |

## Provenance et limites des bases

Champs explicitement autorisés depuis les profils et les archives ; empreintes complètes dans analysis.json.

| Modèle | Adaptateur / modèle | Révision modèle / source | Device / dtype / threads | Limite entrée / RSS / timeout | Runtimes sélectionnés |
|---|---|---|---|---|---|
| Jev | jev_http / jev-1.13.0 | — / — | —/—/— | —/—/30 | python=3.14.2 |
| Noma | noma / BlackdromeAILabs/noma | fac0429688a137ce451a27ad34d05e9fd47fb624 / 8cfda260d8af88c18b1de1852e13dcbe9958042f | cpu/bfloat16/2 | 1024/8192/30 | python=3.12.3, torch=2.14.0+cpu, transformers=5.17.0, noma-source=1.0.1 |
| Eos | decision2 / vllm-sr/Decision-2.0-Eos-0.8B | 3594047d69f476f1d01cf84c593e213fc3a4dfe0 / — | cpu/float32/2 | 4096/6144/30 | python=3.12.3, torch=2.14.0+cpu, transformers=5.17.0 |
| GLiNER | gliner / fastino/GLiNER2.5-multi-Decide | a35a0cd3b7a0f00f2effc576f454cd48fa98aa5f / — | cpu/—/2 | 4096/3072/30 | python=3.12.3, torch=2.14.0+cpu, transformers=4.57.6, gliner2=2.0.0 |
| Laya | laya / convaiinnovations/laya-multilingual | 1720e3e3357cfe1e281542e223f8273b0890ca34 / 2e4d9c87e8b1621deb344eac7de5c7258f32f849 | cpu/float32/2 | 1024/3072/30 | python=3.12.3, torch=2.14.0+cpu, transformers=5.17.0, laya=0.3.26 |
| Julia | julia / SupersonicLabs/Julia-1 | a85b127321d580d65176c89ced8273f305745d85 / — | cpu/—/2 | 8192/3072/30 | python=3.12.3, torch=2.14.0+cpu, transformers=5.0.0 |
| Indecis | indecis / hotchpotch/bekko-embedding-v1-a8m | c721113d59a1d91b447450324f51c4b3332c924a / 339e191405ac9be90f6857f810f478b3312b7f35 | —/—/2 | 4096/3072/30 | parent_python=3.14.2, go=go1.27.1-X:simd |

## Troncature observée, base

Vrai / faux / inconnu sur tous les appels ; le compteur Laya indique état tronqué positif / zéro / inconnu.

| Modèle | État | Options | Préfixe Noma | Usage natif | État Laya réduit |
|---|---:|---:|---:|---:|---:|
| Jev | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 |
| Noma | 0/0/132 | 0/0/132 | 0/132/0 | 0/0/132 | 0/0/132 |
| Eos | 0/132/0 | 0/132/0 | 0/0/132 | 0/0/132 | 0/0/132 |
| GLiNER | 0/132/0 | 0/132/0 | 0/0/132 | 0/0/132 | 0/0/132 |
| Laya | 0/0/132 | 0/0/132 | 0/0/132 | 0/132/0 | 0/132/0 |
| Julia | 0/132/0 | 0/132/0 | 0/0/132 | 0/0/132 | 0/0/132 |
| Indecis | 0/132/0 | 0/132/0 | 0/0/132 | 0/0/132 | 0/0/132 |

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

## Mastra par action proposée

Accords / décisions valides / total. Une proposition en attente de revue humaine ne vaut pas une référence validée.

| Action | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| search | 8/8/8 | 8/8/8 | 7/8/8 | 8/8/8 | 8/8/8 | 6/8/8 | 5/8/8 |
| stats | 8/8/8 | 8/8/8 | 8/8/8 | 4/8/8 | 0/8/8 | 4/8/8 | 6/8/8 |
| fallback | 4/8/8 | 2/8/8 | 4/8/8 | 0/8/8 | 2/8/8 | 1/8/8 | 0/8/8 |

## Mastra par action proposée et langue

Accords / décisions valides / total.

| Action / langue | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| search / fr | 4/4/4 | 4/4/4 | 4/4/4 | 4/4/4 | 4/4/4 | 2/4/4 | 2/4/4 |
| search / en | 4/4/4 | 4/4/4 | 3/4/4 | 4/4/4 | 4/4/4 | 4/4/4 | 3/4/4 |
| stats / fr | 4/4/4 | 4/4/4 | 4/4/4 | 4/4/4 | 0/4/4 | 2/4/4 | 3/4/4 |
| stats / en | 4/4/4 | 4/4/4 | 4/4/4 | 0/4/4 | 0/4/4 | 2/4/4 | 3/4/4 |
| fallback / fr | 1/4/4 | 1/4/4 | 2/4/4 | 0/4/4 | 1/4/4 | 1/4/4 | 0/4/4 |
| fallback / en | 3/4/4 | 1/4/4 | 2/4/4 | 0/4/4 | 1/4/4 | 0/4/4 | 0/4/4 |

## Mastra : action proposée → action prédite

| Attendu → prédit | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| fallback → fallback | 4 | 2 | 4 | 0 | 2 | 1 | 0 |
| fallback → search | 2 | 3 | 2 | 5 | 6 | 6 | 5 |
| fallback → stats | 2 | 3 | 2 | 3 | 0 | 1 | 3 |
| search → fallback | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| search → search | 8 | 8 | 7 | 8 | 8 | 6 | 5 |
| search → stats | 0 | 0 | 1 | 0 | 0 | 1 | 3 |
| stats → fallback | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| stats → search | 0 | 0 | 0 | 4 | 8 | 2 | 2 |
| stats → stats | 8 | 8 | 8 | 4 | 0 | 4 | 6 |

## Mastra : action proposée → prédite FR

| Attendu → prédit | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| fallback → fallback | 1 | 1 | 2 | 0 | 1 | 1 | 0 |
| fallback → search | 1 | 1 | 2 | 1 | 3 | 3 | 2 |
| fallback → stats | 2 | 2 | 0 | 3 | 0 | 0 | 2 |
| search → fallback | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| search → search | 4 | 4 | 4 | 4 | 4 | 2 | 2 |
| search → stats | 0 | 0 | 0 | 0 | 0 | 1 | 2 |
| stats → fallback | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| stats → search | 0 | 0 | 0 | 0 | 4 | 0 | 1 |
| stats → stats | 4 | 4 | 4 | 4 | 0 | 2 | 3 |

## Mastra : action proposée → prédite EN

| Attendu → prédit | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| fallback → fallback | 3 | 1 | 2 | 0 | 1 | 0 | 0 |
| fallback → search | 1 | 2 | 0 | 4 | 3 | 3 | 3 |
| fallback → stats | 0 | 1 | 2 | 0 | 0 | 1 | 1 |
| search → search | 4 | 4 | 3 | 4 | 4 | 4 | 3 |
| search → stats | 0 | 0 | 1 | 0 | 0 | 0 | 1 |
| stats → search | 0 | 0 | 0 | 4 | 4 | 2 | 1 |
| stats → stats | 4 | 4 | 4 | 0 | 0 | 2 | 3 |

## Mastra par langue et split

Accords / décisions valides / total.

| Groupe | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| by_language / en | 11/12/12 | 9/12/12 | 9/12/12 | 4/12/12 | 5/12/12 | 6/12/12 | 6/12/12 |
| by_language / fr | 9/12/12 | 9/12/12 | 10/12/12 | 8/12/12 | 5/12/12 | 5/12/12 | 5/12/12 |
| by_split / calibration | 4/6/6 | 4/6/6 | 4/6/6 | 3/6/6 | 2/6/6 | 4/6/6 | 4/6/6 |
| by_split / test | 16/18/18 | 14/18/18 | 15/18/18 | 9/18/18 | 8/18/18 | 7/18/18 | 7/18/18 |

## Temps Mastra (ms)

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| adapter_ms | 255.6 / 288.0 / 355.3 / 918.1 (24) | 4513.6 / 5259.6 / 6117.8 / 6203.1 (24) | 1206.5 / 1419.9 / 1754.2 / 1785.1 (24) | 275.3 / 391.9 / 582.6 / 670.4 (24) | 219.1 / 267.4 / 375.1 / 405.8 (24) | 77.3 / 100.2 / 146.6 / 164.4 (24) | 36.8 / 44.7 / 57.0 / 68.0 (24) |
| decision_ms | — (0) | 4508.7 / 5254.6 / 6111.9 / 6198.4 (24) | 1203.2 / 1416.5 / 1750.9 / 1781.5 (24) | 267.8 / 383.8 / 573.0 / 652.6 (24) | 185.6 / 232.6 / 326.3 / 353.3 (24) | 73.1 / 95.9 / 141.2 / 160.1 (24) | 29.0 / 36.5 / 48.4 / 60.6 (24) |
| http_ms | 241.3 / 264.1 / 333.5 / 902.2 (24) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| inference_ms | — (0) | 3107.5 / 3662.8 / 4360.8 / 4450.6 (24) | 1202.0 / 1415.1 / 1749.5 / 1779.9 (24) | 265.8 / 381.2 / 570.6 / 649.6 (24) | 183.8 / 229.8 / 324.0 / 349.7 (24) | 73.0 / 95.8 / 141.1 / 160.0 (24) | 28.9 / 36.3 / 48.2 / 60.1 (24) |

## Phases et ressources Mastra

Initialisation, premier appel, puis médiane / p95 des appels ok suivants ; mémoire RSS observée dans le worker et couverture sur tous les appels.

| Modèle | Init ms | Premier appel ms (statut) | Après premier ok ms (n) | RSS worker max MiB (n/total) | RSS chargement MiB |
|---|---:|---|---:|---:|---:|
| Jev | — | 355.3 (ok) | 286.6 / 347.9 (23) | — (0/24) | — |
| Noma | 13961.6 | 5083.3 (ok) | 5270.4 / 6117.8 (23) | 4734.0 (24/24) | 705.8 |
| Eos | 15227.2 | 1605.9 (ok) | 1417.1 / 1754.2 (23) | 3470.6 (24/24) | 3466.0 |
| GLiNER | 13069.2 | 424.5 (ok) | 385.9 / 582.6 (23) | 2886.2 (24/24) | 2886.2 |
| Laya | 11716.9 | 405.8 (ok) | 267.1 / 326.3 (23) | 2323.1 (24/24) | 2323.1 |
| Julia | 14637.9 | 164.4 (ok) | 99.5 / 114.8 (23) | 1019.3 (24/24) | 922.0 |
| Indecis | 1215.8 | 68.0 (ok) | 44.6 / 54.3 (23) | 894.9 (24/24) | 790.0 |

## Temps Mastra par statut (ms)

Médiane / p95 (n) ; temps adaptateur inclut les échecs enregistrés.

| Statut / mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| ok / adapter_ms | 288.0 / 355.3 (24) | 5259.6 / 6117.8 (24) | 1419.9 / 1754.2 (24) | 391.9 / 582.6 (24) | 267.4 / 375.1 (24) | 100.2 / 146.6 (24) | 44.7 / 57.0 (24) |
| ok / inference_ms | — (0) | 3662.8 / 4360.8 (24) | 1415.1 / 1749.5 (24) | 381.2 / 570.6 (24) | 229.8 / 324.0 (24) | 95.8 / 141.1 (24) | 36.3 / 48.2 (24) |
| ok / decision_ms | — (0) | 5254.6 / 6111.9 (24) | 1416.5 / 1750.9 (24) | 383.8 / 573.0 (24) | 232.6 / 326.3 (24) | 95.9 / 141.2 (24) | 36.5 / 48.4 (24) |
| ok / http_ms | 264.1 / 333.5 (24) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |

## Tokens natifs Mastra

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| encoded_tokens | — (0) | 153.0 / 183.0 / 204.0 / 216.0 (24) | 190.0 / 217.0 / 242.0 / 254.0 (24) | 159.0 / 199.0 / 233.0 / 245.0 (24) | 119.0 / 146.5 / 172.0 / 182.0 (24) | 119.0 / 146.5 / 172.0 / 182.0 (24) | 66.0 / 86.0 / 107.0 / 117.0 (24) |
| indecis_max_sequence_tokens | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) | 66.0 / 86.0 / 107.0 / 117.0 (24) |
| indecis_sum_tokens | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) | 148.0 / 175.5 / 201.0 / 211.0 (24) |
| padded_tokens | — (0) | — (0) | — (0) | 159.0 / 199.0 / 233.0 / 245.0 (24) | — (0) | 120.0 / 148.0 / 176.0 / 184.0 (24) | — (0) |

## Tokens déclarés par le fournisseur, Mastra

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| input_tokens | 396.0 / 429.0 / 462.0 / 475.0 (24) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| output_tokens | 73.0 / 86.5 / 98.0 / 98.0 (24) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |

## Tokens natifs Mastra par langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| en | — (0) | 160.5 / 184.0 (12) | 197.0 / 214.0 (12) | 169.0 / 199.0 (12) | 126.0 / 144.0 (12) | 126.0 / 144.0 (12) | 73.0 / 91.0 (12) |
| fr | — (0) | 193.0 / 216.0 (12) | 231.0 / 254.0 (12) | 212.5 / 245.0 (12) | 160.0 / 182.0 (12) | 160.0 / 182.0 (12) | 95.0 / 117.0 (12) |

## Tokens fournisseur Mastra par langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| en / input_tokens | 396.0 / 403.0 / 420.0 / 420.0 (12) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| en / output_tokens | 73.0 / 75.0 / 78.0 / 78.0 (12) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| fr / input_tokens | 438.0 / 451.0 / 475.0 / 475.0 (12) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |
| fr / output_tokens | 95.0 / 97.5 / 98.0 / 98.0 (12) | — (0) | — (0) | — (0) | — (0) | — (0) | — (0) |

## Longueur commune des entrées Mastra

Somme des caractères Unicode ou mots séparés par espace dans le contexte, la question et les descriptions d'options visibles par tous ; exclut les identifiants et la sérialisation.

| Mesure | Jev | Noma | Eos | GLiNER | Laya | Julia | Indecis |
|---|---:|---:|---:|---:|---:|---:|---:|
| characters | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) |
| words | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) |

## Troncature observée, Mastra

Vrai / faux / inconnu sur tous les appels ; le compteur Laya indique état tronqué positif / zéro / inconnu.

| Modèle | État | Options | Préfixe Noma | Usage natif | État Laya réduit |
|---|---:|---:|---:|---:|---:|
| Jev | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 |
| Noma | 0/0/24 | 0/0/24 | 0/24/0 | 0/0/24 | 0/0/24 |
| Eos | 0/24/0 | 0/24/0 | 0/0/24 | 0/0/24 | 0/0/24 |
| GLiNER | 0/24/0 | 0/24/0 | 0/0/24 | 0/0/24 | 0/0/24 |
| Laya | 0/0/24 | 0/0/24 | 0/0/24 | 0/24/0 | 0/24/0 |
| Julia | 0/24/0 | 0/24/0 | 0/0/24 | 0/0/24 | 0/0/24 |
| Indecis | 0/24/0 | 0/24/0 | 0/0/24 | 0/0/24 | 0/0/24 |

## Cohérence Mastra FR/EN

| Modèle | Paires valides / total | Même action |
|---|---:|---:|
| Jev | 12/12 | 9/12 |
| Noma | 12/12 | 11/12 |
| Eos | 12/12 | 9/12 |
| GLiNER | 12/12 | 5/12 |
| Laya | 12/12 | 12/12 |
| Julia | 12/12 | 5/12 |
| Indecis | 12/12 | 10/12 |

## Provenance et limites Mastra

Champs explicitement autorisés depuis les profils et les archives ; empreintes complètes dans analysis.json.

| Modèle | Adaptateur / modèle | Révision modèle / source | Device / dtype / threads | Limite entrée / RSS / timeout | Runtimes sélectionnés |
|---|---|---|---|---|---|
| Jev | jev_http / jev-1.13.0 | — / — | —/—/— | —/—/30 | python=3.14.2 |
| Noma | noma / BlackdromeAILabs/noma | fac0429688a137ce451a27ad34d05e9fd47fb624 / 8cfda260d8af88c18b1de1852e13dcbe9958042f | cpu/bfloat16/2 | 1024/8192/30 | python=3.12.3, torch=2.14.0+cpu, transformers=5.17.0, noma-source=1.0.1 |
| Eos | decision2 / vllm-sr/Decision-2.0-Eos-0.8B | 3594047d69f476f1d01cf84c593e213fc3a4dfe0 / — | cpu/float32/2 | 4096/6144/30 | python=3.12.3, torch=2.14.0+cpu, transformers=5.17.0 |
| GLiNER | gliner / fastino/GLiNER2.5-multi-Decide | a35a0cd3b7a0f00f2effc576f454cd48fa98aa5f / — | cpu/—/2 | 4096/3072/30 | python=3.12.3, torch=2.14.0+cpu, transformers=4.57.6, gliner2=2.0.0 |
| Laya | laya / convaiinnovations/laya-multilingual | 1720e3e3357cfe1e281542e223f8273b0890ca34 / 2e4d9c87e8b1621deb344eac7de5c7258f32f849 | cpu/float32/2 | 1024/3072/30 | python=3.12.3, torch=2.14.0+cpu, transformers=5.17.0, laya=0.3.26 |
| Julia | julia / SupersonicLabs/Julia-1 | a85b127321d580d65176c89ced8273f305745d85 / — | cpu/—/2 | 8192/3072/30 | python=3.12.3, torch=2.14.0+cpu, transformers=5.0.0 |
| Indecis | indecis / hotchpotch/bekko-embedding-v1-a8m | c721113d59a1d91b447450324f51c4b3332c924a / 339e191405ac9be90f6857f810f478b3312b7f35 | —/—/2 | 4096/3072/30 | parent_python=3.14.2, go=go1.27.1-X:simd |

Sources, révisions et empreintes : voir analysis.json. Aucune sortie de cas ni contexte privé publié.
