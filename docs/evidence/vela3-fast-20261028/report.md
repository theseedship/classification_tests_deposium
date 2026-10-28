# Comparaison des modèles de choix de contexte

Cas corrects / scorés / total ; les erreurs et absences restent dans le total.
Références agent à revoir humainement ; mesures exploratoires sur modèles isolés, pas parcours produit.

## Classement des bases

| Modèle | Corrects / scorés / total | Statuts (ok, unsupported, missing, error, timeout, abstain) | Médiane / p95 adaptateur ok (ms) | Premier appel (ms) | RSS max observé (MiB) |
|---|---:|---|---:|---:|---:|
| D3Q4 | 128/132/132 | 132/0/0/0/0/0 | 613.7 / 629.7 (132) | 621.8 | non observé (0/132 rapportés) |
| D3FlashQ8 | 124/132/132 | 132/0/0/0/0/0 | 194.3 / 200.4 (132) | 205.4 | non observé (0/132 rapportés) |
| GLiClass9B | 117/132/132 | 132/0/0/0/0/0 | 326.5 / 615.5 (132) | 1714.3 | 1171.2 (132/132 rapportés) |
| Vela3Fast | 57/132/132 | 132/0/0/0/0/0 | 80.5 / 116.4 (132) | 105.8 | 3233.9 (132/132 rapportés) |

Le temps adaptateur exclut l'initialisation ; premier appel distingué. P95 descriptif par rang le plus proche.

## Domaines

| Groupe | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---|---|---|---|
| chemistry | 27/28/28 | 26/28/28 | 23/28/28 | 5/28/28 |
| documentary | 73/76/76 | 72/76/76 | 70/76/76 | 43/76/76 |
| mathematics | 28/28/28 | 26/28/28 | 24/28/28 | 9/28/28 |

## Langues

| Groupe | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---|---|---|---|
| en | 64/66/66 | 62/66/66 | 59/66/66 | 32/66/66 |
| fr | 64/66/66 | 62/66/66 | 58/66/66 | 25/66/66 |

## Domaines × langues

| Groupe | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---|---|---|---|
| chemistry / en | 13/14/14 | 13/14/14 | 12/14/14 | 3/14/14 |
| chemistry / fr | 14/14/14 | 13/14/14 | 11/14/14 | 2/14/14 |
| documentary / en | 37/38/38 | 36/38/38 | 35/38/38 | 23/38/38 |
| documentary / fr | 36/38/38 | 36/38/38 | 35/38/38 | 20/38/38 |
| mathematics / en | 14/14/14 | 13/14/14 | 12/14/14 | 6/14/14 |
| mathematics / fr | 14/14/14 | 13/14/14 | 12/14/14 | 3/14/14 |

## Domaines × split

| Groupe | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---|---|---|---|
| chemistry / calibration | 8/8/8 | 8/8/8 | 4/8/8 | 1/8/8 |
| chemistry / test | 13/14/14 | 12/14/14 | 14/14/14 | 2/14/14 |
| chemistry / train | 6/6/6 | 6/6/6 | 5/6/6 | 2/6/6 |
| documentary / calibration | 14/14/14 | 14/14/14 | 14/14/14 | 8/14/14 |
| documentary / test | 38/38/38 | 37/38/38 | 37/38/38 | 22/38/38 |
| documentary / train | 21/24/24 | 21/24/24 | 19/24/24 | 13/24/24 |
| mathematics / calibration | 8/8/8 | 8/8/8 | 8/8/8 | 2/8/8 |
| mathematics / test | 14/14/14 | 12/14/14 | 12/14/14 | 4/14/14 |
| mathematics / train | 6/6/6 | 6/6/6 | 4/6/6 | 3/6/6 |

## Difficulté

| Groupe | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---|---|---|---|
| D1 | 40/40/40 | 39/40/40 | 39/40/40 | 20/40/40 |
| D2 | 38/40/40 | 37/40/40 | 35/40/40 | 14/40/40 |
| D3 | 50/52/52 | 48/52/52 | 43/52/52 | 23/52/52 |

## Split

| Groupe | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---|---|---|---|
| calibration | 30/30/30 | 30/30/30 | 26/30/30 | 11/30/30 |
| test | 65/66/66 | 61/66/66 | 63/66/66 | 28/66/66 |
| train | 33/36/36 | 33/36/36 | 28/36/36 | 18/36/36 |

## Types de tâche, tous domaines

| Groupe | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---|---|---|---|
| aliquot-and-mix | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 |
| ambiguous-selection | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| atoms-and-charge | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| cancel-keep-domain | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| catalog-active-inventory | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-catalog-not-source-count | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| catalog-corrected-request | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| catalog-count-and-names | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-distinct-identities | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-metadata-owners | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-metadata-table-language | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-negative-summary | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-quoted-summary-command | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-scope-after-interlude | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-selected-titles | 2/2/2 | 2/2/2 | 1/2/2 | 1/2/2 |
| catalog-selection-reuse | 1/2/2 | 2/2/2 | 0/2/2 | 0/2/2 |
| chain-derivative | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| combustion-balance | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 |
| conditional-probability | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| conserved-dilution | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| extraneous-equation-root | 2/2/2 | 2/2/2 | 0/2/2 | 1/2/2 |
| formula-not-structure | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| fraction-addition | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| function-types | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| group-atom-count | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| hydrate-water-fraction | 1/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| ionic-neutrality | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| limiting-reactant | 2/2/2 | 2/2/2 | 1/2/2 | 2/2/2 |
| matrix-product | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| missing-final-volume | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| molar-concentration | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| nested-complex-count | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| polynomial-remainder | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| precipitate-mass | 2/2/2 | 0/2/2 | 2/2/2 | 0/2/2 |
| principal-root | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| quantity-dimension | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-date | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-exact-clause | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-explanation | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-filtered-list | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| retrieve_answer-content-not-summary | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-refutation | 2/2/2 | 1/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-total-unit | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-distant-report-reference | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-followup-cause | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| retrieve_answer-quoted-instruction-content | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-relations-mermaid | 2/2/2 | 1/2/2 | 1/2/2 | 0/2/2 |
| retrieve_answer-stale-summary-check | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| square-expansion | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| stored_summaries-cached-descriptions | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-do-not-reread | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-existing-per-file | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-inherit-summary-constraint | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-language-followup | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-quotation-not-budget-question | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-remaining-summaries | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-resume-after-content | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| stored_summaries-summary-bundle | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| stored_summaries-summary-count-title | 0/2/2 | 0/2/2 | 0/2/2 | 2/2/2 |
| stored_summaries-translate-summary-table | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-validated-abstracts | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| transpose-chain | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| unanchored-language | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| underdetermined-linear | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| unknown-function-values | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| water-balance | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |

## Tâches documentaires

| Groupe | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---|---|---|---|
| ambiguous-selection | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-active-inventory | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-catalog-not-source-count | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| catalog-corrected-request | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| catalog-count-and-names | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-distinct-identities | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-metadata-owners | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-metadata-table-language | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-negative-summary | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-quoted-summary-command | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-scope-after-interlude | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-selected-titles | 2/2/2 | 2/2/2 | 1/2/2 | 1/2/2 |
| catalog-selection-reuse | 1/2/2 | 2/2/2 | 0/2/2 | 0/2/2 |
| retrieve_answer-content-date | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-exact-clause | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-explanation | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-filtered-list | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| retrieve_answer-content-not-summary | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-refutation | 2/2/2 | 1/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-total-unit | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-distant-report-reference | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-followup-cause | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| retrieve_answer-quoted-instruction-content | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-relations-mermaid | 2/2/2 | 1/2/2 | 1/2/2 | 0/2/2 |
| retrieve_answer-stale-summary-check | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| stored_summaries-cached-descriptions | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-do-not-reread | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-existing-per-file | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-inherit-summary-constraint | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-language-followup | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-quotation-not-budget-question | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-remaining-summaries | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-resume-after-content | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| stored_summaries-summary-bundle | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| stored_summaries-summary-count-title | 0/2/2 | 0/2/2 | 0/2/2 | 2/2/2 |
| stored_summaries-translate-summary-table | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-validated-abstracts | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| unanchored-language | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |

## Temps base (ms)

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| adapter_ms | 351.5 / 613.7 / 629.7 / 640.6 (132) | 126.8 / 194.3 / 200.4 / 205.4 (132) | 201.0 / 326.5 / 615.5 / 1714.3 (132) | 56.2 / 80.5 / 116.4 / 134.0 (132) |
| decision_ms | — (0) | — (0) | 198.0 / 319.9 / 612.3 / 1710.9 (132) | 55.1 / 74.7 / 109.8 / 120.1 (132) |
| http_ms | 351.3 / 613.5 / 629.5 / 640.4 (132) | 126.6 / 194.1 / 200.3 / 205.2 (132) | — (0) | — (0) |
| inference_ms | — (0) | — (0) | 195.4 / 317.3 / 609.7 / 1706.6 (132) | 54.4 / 73.9 / 109.0 / 119.3 (132) |

## Phases et ressources base

Initialisation, premier appel, puis médiane / p95 des appels ok suivants ; mémoire RSS observée dans le worker et couverture sur tous les appels.

| Modèle | Init ms | Premier appel ms (statut) | Après premier ok ms (n) | RSS worker max MiB (n/total) | RSS chargement MiB |
|---|---:|---|---:|---:|---:|
| D3Q4 | — | 621.8 (ok) | 613.6 / 629.7 (131) | — (0/132) | — |
| D3FlashQ8 | — | 205.4 (ok) | 194.3 / 200.0 (131) | — (0/132) | — |
| GLiClass9B | 13465.5 | 1714.3 (ok) | 326.5 / 491.6 (131) | 1171.2 (132/132) | 788.7 |
| Vela3Fast | 8339.1 | 105.8 (ok) | 80.5 / 116.4 (131) | 3233.9 (132/132) | 3233.9 |

## Temps base par statut (ms)

Médiane / p95 (n) ; temps adaptateur inclut les échecs enregistrés.

| Statut / mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| ok / adapter_ms | 613.7 / 629.7 (132) | 194.3 / 200.4 (132) | 326.5 / 615.5 (132) | 80.5 / 116.4 (132) |
| ok / inference_ms | — (0) | — (0) | 317.3 / 609.7 (132) | 73.9 / 109.0 (132) |
| ok / decision_ms | — (0) | — (0) | 319.9 / 612.3 (132) | 74.7 / 109.8 (132) |
| ok / http_ms | 613.5 / 629.5 (132) | 194.1 / 200.3 (132) | — (0) | — (0) |

## Tokens natifs base

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| encoded_tokens | — (0) | — (0) | 38.0 / 75.0 / 104.0 / 117.0 (132) | 43.0 / 81.0 / 141.0 / 166.0 (132) |
| indecis_max_sequence_tokens | — (0) | — (0) | — (0) | — (0) |
| indecis_sum_tokens | — (0) | — (0) | — (0) | — (0) |
| padded_tokens | — (0) | — (0) | — (0) | — (0) |

## Tokens déclarés par le fournisseur, base

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| input_tokens | 128.0 / 165.0 / 194.0 / 211.0 (132) | 128.0 / 165.0 / 194.0 / 211.0 (132) | — (0) | — (0) |
| output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (132) | 0.0 / 0.0 / 0.0 / 0.0 (132) | — (0) | — (0) |

## Tokens natifs base par domaine

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| chemistry | — (0) | — (0) | 86.5 / 114.0 (28) | 94.5 / 129.0 (28) |
| documentary | — (0) | — (0) | 78.0 / 101.0 (76) | 97.5 / 152.0 (76) |
| mathematics | — (0) | — (0) | 58.0 / 83.0 (28) | 70.0 / 101.0 (28) |

## Tokens natifs base par langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| en | — (0) | — (0) | 67.0 / 96.0 (66) | 70.5 / 100.0 (66) |
| fr | — (0) | — (0) | 83.5 / 104.0 (66) | 122.0 / 152.0 (66) |

## Tokens natifs base par domaine × langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| chemistry / en | — (0) | — (0) | 80.5 / 110.0 (14) | 85.0 / 115.0 (14) |
| chemistry / fr | — (0) | — (0) | 92.5 / 117.0 (14) | 104.0 / 136.0 (14) |
| documentary / en | — (0) | — (0) | 68.5 / 83.0 (38) | 72.0 / 87.0 (38) |
| documentary / fr | — (0) | — (0) | 86.0 / 103.0 (38) | 129.5 / 158.0 (38) |
| mathematics / en | — (0) | — (0) | 56.5 / 83.0 (14) | 61.0 / 97.0 (14) |
| mathematics / fr | — (0) | — (0) | 61.0 / 85.0 (14) | 78.0 / 103.0 (14) |

## Tokens fournisseur base par domaine

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| chemistry / input_tokens | 147.0 / 180.5 / 208.0 / 211.0 (28) | 147.0 / 180.5 / 208.0 / 211.0 (28) | — (0) | — (0) |
| chemistry / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (28) | 0.0 / 0.0 / 0.0 / 0.0 (28) | — (0) | — (0) |
| documentary / input_tokens | 149.0 / 168.0 / 190.0 / 193.0 (76) | 149.0 / 168.0 / 190.0 / 193.0 (76) | — (0) | — (0) |
| documentary / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (76) | 0.0 / 0.0 / 0.0 / 0.0 (76) | — (0) | — (0) |
| mathematics / input_tokens | 128.0 / 148.5 / 177.0 / 179.0 (28) | 128.0 / 148.5 / 177.0 / 179.0 (28) | — (0) | — (0) |
| mathematics / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (28) | 0.0 / 0.0 / 0.0 / 0.0 (28) | — (0) | — (0) |

## Tokens fournisseur base par langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| en / input_tokens | 128.0 / 157.0 / 186.0 / 204.0 (66) | 128.0 / 157.0 / 186.0 / 204.0 (66) | — (0) | — (0) |
| en / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (66) | 0.0 / 0.0 / 0.0 / 0.0 (66) | — (0) | — (0) |
| fr / input_tokens | 132.0 / 173.5 / 198.0 / 211.0 (66) | 132.0 / 173.5 / 198.0 / 211.0 (66) | — (0) | — (0) |
| fr / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (66) | 0.0 / 0.0 / 0.0 / 0.0 (66) | — (0) | — (0) |

## Tokens fournisseur base par domaine × langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| chemistry / en / input_tokens | 147.0 / 172.5 / 204.0 / 204.0 (14) | 147.0 / 172.5 / 204.0 / 204.0 (14) | — (0) | — (0) |
| chemistry / en / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) | — (0) | — (0) |
| chemistry / fr / input_tokens | 152.0 / 186.5 / 211.0 / 211.0 (14) | 152.0 / 186.5 / 211.0 / 211.0 (14) | — (0) | — (0) |
| chemistry / fr / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) | — (0) | — (0) |
| documentary / en / input_tokens | 149.0 / 159.5 / 173.0 / 176.0 (38) | 149.0 / 159.5 / 173.0 / 176.0 (38) | — (0) | — (0) |
| documentary / en / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (38) | 0.0 / 0.0 / 0.0 / 0.0 (38) | — (0) | — (0) |
| documentary / fr / input_tokens | 160.0 / 175.5 / 192.0 / 193.0 (38) | 160.0 / 175.5 / 192.0 / 193.0 (38) | — (0) | — (0) |
| documentary / fr / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (38) | 0.0 / 0.0 / 0.0 / 0.0 (38) | — (0) | — (0) |
| mathematics / en / input_tokens | 128.0 / 147.0 / 177.0 / 177.0 (14) | 128.0 / 147.0 / 177.0 / 177.0 (14) | — (0) | — (0) |
| mathematics / en / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) | — (0) | — (0) |
| mathematics / fr / input_tokens | 132.0 / 151.0 / 179.0 / 179.0 (14) | 132.0 / 151.0 / 179.0 / 179.0 (14) | — (0) | — (0) |
| mathematics / fr / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) | — (0) | — (0) |

## Longueur commune des entrées base

Somme des caractères Unicode ou mots séparés par espace dans le contexte, la question et les descriptions d'options visibles par tous ; exclut les identifiants et la sérialisation.

| Mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| characters | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) |
| words | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) |

Tokens natifs : encodage propre à chaque adaptateur ; `indecis_max_sequence_tokens` mesure la plus longue séquence, `indecis_sum_tokens` la somme des séquences. Tokens fournisseur : comptabilité postérieure à la requête, non comparable au tokenizer local. RSS : pics rapportés par worker, sans RAM serveur distant.

## Confusion des actions documentaires sur la base

| Attendu → prédit | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| catalog → catalog | 23 | 24 | 21 | 13 |
| catalog → insufficient_information | 0 | 0 | 2 | 1 |
| catalog → retrieve_answer | 1 | 0 | 1 | 2 |
| catalog → stored_summaries | 0 | 0 | 0 | 8 |
| insufficient_information → A | 0 | 0 | 0 | 1 |
| insufficient_information → A_and_B | 0 | 0 | 0 | 1 |
| insufficient_information → insufficient_information | 4 | 4 | 4 | 2 |
| retrieve_answer → catalog | 0 | 0 | 0 | 4 |
| retrieve_answer → insufficient_information | 0 | 2 | 1 | 8 |
| retrieve_answer → retrieve_answer | 24 | 22 | 23 | 7 |
| retrieve_answer → stored_summaries | 0 | 0 | 0 | 5 |
| stored_summaries → catalog | 2 | 2 | 2 | 2 |
| stored_summaries → retrieve_answer | 0 | 0 | 0 | 1 |
| stored_summaries → stored_summaries | 22 | 22 | 22 | 21 |

## Confusion documentaire base FR

| Attendu → prédit | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| catalog → catalog | 11 | 12 | 10 | 5 |
| catalog → insufficient_information | 0 | 0 | 1 | 1 |
| catalog → retrieve_answer | 1 | 0 | 1 | 2 |
| catalog → stored_summaries | 0 | 0 | 0 | 4 |
| insufficient_information → A | 0 | 0 | 0 | 1 |
| insufficient_information → insufficient_information | 2 | 2 | 2 | 1 |
| retrieve_answer → catalog | 0 | 0 | 0 | 1 |
| retrieve_answer → insufficient_information | 0 | 1 | 0 | 5 |
| retrieve_answer → retrieve_answer | 12 | 11 | 12 | 3 |
| retrieve_answer → stored_summaries | 0 | 0 | 0 | 3 |
| stored_summaries → catalog | 1 | 1 | 1 | 0 |
| stored_summaries → retrieve_answer | 0 | 0 | 0 | 1 |
| stored_summaries → stored_summaries | 11 | 11 | 11 | 11 |

## Confusion documentaire base EN

| Attendu → prédit | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| catalog → catalog | 12 | 12 | 11 | 8 |
| catalog → insufficient_information | 0 | 0 | 1 | 0 |
| catalog → stored_summaries | 0 | 0 | 0 | 4 |
| insufficient_information → A_and_B | 0 | 0 | 0 | 1 |
| insufficient_information → insufficient_information | 2 | 2 | 2 | 1 |
| retrieve_answer → catalog | 0 | 0 | 0 | 3 |
| retrieve_answer → insufficient_information | 0 | 1 | 1 | 3 |
| retrieve_answer → retrieve_answer | 12 | 11 | 11 | 4 |
| retrieve_answer → stored_summaries | 0 | 0 | 0 | 2 |
| stored_summaries → catalog | 1 | 1 | 1 | 2 |
| stored_summaries → stored_summaries | 11 | 11 | 11 | 10 |

## Cohérence des traductions documentaires FR/EN

| Modèle | Paires scorées / total | Même action | Deux correctes |
|---|---:|---:|---:|
| D3Q4 | 38/38 | 37/38 | 36/38 |
| D3FlashQ8 | 38/38 | 36/38 | 35/38 |
| GLiClass9B | 38/38 | 36/38 | 34/38 |
| Vela3Fast | 38/38 | 23/38 | 17/38 |

## Provenance et limites des bases

Champs explicitement autorisés depuis les profils et les archives ; empreintes complètes dans analysis.json.

| Modèle | Adaptateur / modèle | Révision modèle / source | Device / dtype / threads | Limite entrée / RSS / timeout | Runtimes sélectionnés |
|---|---|---|---|---|---|
| D3Q4 | systemone_local / ggml-org/vllm-d3-GGUF | de9670136f5ddd83e677c89ce041d5b9bb3b0dcb / efe3626b119ff81033e309c3ba07a770bef2c546 | metal/Q4_K_M/— | 4096/24576/30 | — |
| D3FlashQ8 | systemone_local / ggml-org/vllm-d3-flash-GGUF | 3d53d13778bf8035e6e1e534ce489ed052ee5663 / efe3626b119ff81033e309c3ba07a770bef2c546 | metal/Q8_0/— | 4096/20480/30 | — |
| GLiClass9B | gliclass / knowledgator/gliclass-v4-9b | 14d11a92b5e0bab4a166e1fce4cc0777cac27182 / 6a00f8067648f25aa0f4f477d167c5f391cb4165 | mps/bfloat16/2 | 4096/32768/30 | python=3.12.12, torch=2.14.0, transformers=5.19.0 |
| Vela3Fast | vela3_fast / vllm-sr/vela3-fast | 9e338f39babc622f42e9bd8556398fe2d80d9f13 / — | cpu/float32/2 | 4096/8192/30 | python=3.12.12, torch=2.14.0, transformers=5.17.0 |

## Troncature observée, base

Vrai / faux / inconnu sur tous les appels ; le compteur Laya indique état tronqué positif / zéro / inconnu.

| Modèle | État | Options | Préfixe Noma | Usage natif | État Laya réduit |
|---|---:|---:|---:|---:|---:|
| D3Q4 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 |
| D3FlashQ8 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 |
| GLiClass9B | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 |
| Vela3Fast | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 |

## Observation Mastra

Accord avec propositions d'agent ; références pending_human, aucun score sémantique final.

| Modèle | Accord / valides / total | Statuts | Médiane / p95 adaptateur ok (ms) | RSS max observé (MiB) |
|---|---:|---|---:|---:|
| D3Q4 | 24/24/24 | 24/0/0/0/0/0 | 650.8 / 675.7 | non observé (0/24 rapportés) |
| D3FlashQ8 | 20/24/24 | 24/0/0/0/0/0 | 206.5 / 219.9 | non observé (0/24 rapportés) |
| GLiClass9B | 20/24/24 | 24/0/0/0/0/0 | 444.0 / 719.1 | 995.4 (24/24 rapportés) |
| Vela3Fast | 18/24/24 | 24/0/0/0/0/0 | 156.9 / 205.8 | 3234.9 (24/24 rapportés) |

## Mastra par action proposée

Accords / décisions valides / total. Une proposition en attente de revue humaine ne vaut pas une référence validée.

| Action | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| search | 8/8/8 | 8/8/8 | 8/8/8 | 8/8/8 |
| stats | 8/8/8 | 8/8/8 | 8/8/8 | 8/8/8 |
| fallback | 8/8/8 | 4/8/8 | 4/8/8 | 2/8/8 |

## Mastra par action proposée et langue

Accords / décisions valides / total.

| Action / langue | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| search / fr | 4/4/4 | 4/4/4 | 4/4/4 | 4/4/4 |
| search / en | 4/4/4 | 4/4/4 | 4/4/4 | 4/4/4 |
| stats / fr | 4/4/4 | 4/4/4 | 4/4/4 | 4/4/4 |
| stats / en | 4/4/4 | 4/4/4 | 4/4/4 | 4/4/4 |
| fallback / fr | 4/4/4 | 1/4/4 | 2/4/4 | 1/4/4 |
| fallback / en | 4/4/4 | 3/4/4 | 2/4/4 | 1/4/4 |

## Mastra : action proposée → action prédite

| Attendu → prédit | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| fallback → fallback | 8 | 4 | 4 | 2 |
| fallback → search | 0 | 3 | 2 | 5 |
| fallback → stats | 0 | 1 | 2 | 1 |
| search → search | 8 | 8 | 8 | 8 |
| stats → stats | 8 | 8 | 8 | 8 |

## Mastra : action proposée → prédite FR

| Attendu → prédit | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| fallback → fallback | 4 | 1 | 2 | 1 |
| fallback → search | 0 | 2 | 1 | 3 |
| fallback → stats | 0 | 1 | 1 | 0 |
| search → search | 4 | 4 | 4 | 4 |
| stats → stats | 4 | 4 | 4 | 4 |

## Mastra : action proposée → prédite EN

| Attendu → prédit | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| fallback → fallback | 4 | 3 | 2 | 1 |
| fallback → search | 0 | 1 | 1 | 2 |
| fallback → stats | 0 | 0 | 1 | 1 |
| search → search | 4 | 4 | 4 | 4 |
| stats → stats | 4 | 4 | 4 | 4 |

## Mastra par langue et split

Accords / décisions valides / total.

| Groupe | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| by_language / en | 12/12/12 | 11/12/12 | 10/12/12 | 9/12/12 |
| by_language / fr | 12/12/12 | 9/12/12 | 10/12/12 | 9/12/12 |
| by_split / calibration | 6/6/6 | 4/6/6 | 4/6/6 | 4/6/6 |
| by_split / test | 18/18/18 | 16/18/18 | 16/18/18 | 14/18/18 |

## Temps Mastra (ms)

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| adapter_ms | 633.4 / 650.8 / 675.7 / 911.5 (24) | 201.9 / 206.5 / 219.9 / 277.8 (24) | 312.5 / 444.0 / 719.1 / 1001.7 (24) | 120.3 / 156.9 / 205.8 / 209.2 (24) |
| decision_ms | — (0) | — (0) | 309.1 / 438.4 / 706.3 / 998.3 (24) | 118.8 / 155.0 / 193.4 / 202.0 (24) |
| http_ms | 633.0 / 650.5 / 675.4 / 911.2 (24) | 201.6 / 206.1 / 219.5 / 277.3 (24) | — (0) | — (0) |
| inference_ms | — (0) | — (0) | 306.2 / 435.8 / 703.5 / 995.2 (24) | 117.9 / 154.0 / 192.4 / 200.7 (24) |

## Phases et ressources Mastra

Initialisation, premier appel, puis médiane / p95 des appels ok suivants ; mémoire RSS observée dans le worker et couverture sur tous les appels.

| Modèle | Init ms | Premier appel ms (statut) | Après premier ok ms (n) | RSS worker max MiB (n/total) | RSS chargement MiB |
|---|---:|---|---:|---:|---:|
| D3Q4 | — | 671.0 (ok) | 649.3 / 675.7 (23) | — (0/24) | — |
| D3FlashQ8 | — | 219.9 (ok) | 205.6 / 212.1 (23) | — (0/24) | — |
| GLiClass9B | 12935.5 | 1001.7 (ok) | 443.4 / 661.2 (23) | 995.4 (24/24) | 789.0 |
| Vela3Fast | 8398.5 | 209.2 (ok) | 149.0 / 204.1 (23) | 3234.9 (24/24) | 3234.9 |

## Temps Mastra par statut (ms)

Médiane / p95 (n) ; temps adaptateur inclut les échecs enregistrés.

| Statut / mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| ok / adapter_ms | 650.8 / 675.7 (24) | 206.5 / 219.9 (24) | 444.0 / 719.1 (24) | 156.9 / 205.8 (24) |
| ok / inference_ms | — (0) | — (0) | 435.8 / 703.5 (24) | 154.0 / 192.4 (24) |
| ok / decision_ms | — (0) | — (0) | 438.4 / 706.3 (24) | 155.0 / 193.4 (24) |
| ok / http_ms | 650.5 / 675.4 (24) | 206.1 / 219.5 (24) | — (0) | — (0) |

## Tokens natifs Mastra

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| encoded_tokens | — (0) | — (0) | 116.0 / 143.0 / 168.0 / 180.0 (24) | 129.0 / 177.0 / 233.0 / 245.0 (24) |
| indecis_max_sequence_tokens | — (0) | — (0) | — (0) | — (0) |
| indecis_sum_tokens | — (0) | — (0) | — (0) | — (0) |
| padded_tokens | — (0) | — (0) | — (0) | — (0) |

## Tokens déclarés par le fournisseur, Mastra

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| input_tokens | 201.0 / 227.5 / 252.0 / 264.0 (24) | 201.0 / 227.5 / 252.0 / 264.0 (24) | — (0) | — (0) |
| output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (24) | 0.0 / 0.0 / 0.0 / 0.0 (24) | — (0) | — (0) |

## Tokens natifs Mastra par langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| en | — (0) | — (0) | 123.0 / 140.0 (12) | 136.0 / 156.0 (12) |
| fr | — (0) | — (0) | 157.0 / 180.0 (12) | 213.5 / 245.0 (12) |

## Tokens fournisseur Mastra par langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| en / input_tokens | 201.0 / 208.0 / 225.0 / 225.0 (12) | 201.0 / 208.0 / 225.0 / 225.0 (12) | — (0) | — (0) |
| en / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (12) | 0.0 / 0.0 / 0.0 / 0.0 (12) | — (0) | — (0) |
| fr / input_tokens | 230.0 / 241.0 / 264.0 / 264.0 (12) | 230.0 / 241.0 / 264.0 / 264.0 (12) | — (0) | — (0) |
| fr / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (12) | 0.0 / 0.0 / 0.0 / 0.0 (12) | — (0) | — (0) |

## Longueur commune des entrées Mastra

Somme des caractères Unicode ou mots séparés par espace dans le contexte, la question et les descriptions d'options visibles par tous ; exclut les identifiants et la sérialisation.

| Mesure | D3Q4 | D3FlashQ8 | GLiClass9B | Vela3Fast |
|---|---:|---:|---:|---:|
| characters | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) |
| words | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) |

## Troncature observée, Mastra

Vrai / faux / inconnu sur tous les appels ; le compteur Laya indique état tronqué positif / zéro / inconnu.

| Modèle | État | Options | Préfixe Noma | Usage natif | État Laya réduit |
|---|---:|---:|---:|---:|---:|
| D3Q4 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 |
| D3FlashQ8 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 |
| GLiClass9B | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 |
| Vela3Fast | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 |

## Cohérence Mastra FR/EN

| Modèle | Paires valides / total | Même action |
|---|---:|---:|
| D3Q4 | 12/12 | 12/12 |
| D3FlashQ8 | 12/12 | 10/12 |
| GLiClass9B | 12/12 | 12/12 |
| Vela3Fast | 12/12 | 11/12 |

## Provenance et limites Mastra

Champs explicitement autorisés depuis les profils et les archives ; empreintes complètes dans analysis.json.

| Modèle | Adaptateur / modèle | Révision modèle / source | Device / dtype / threads | Limite entrée / RSS / timeout | Runtimes sélectionnés |
|---|---|---|---|---|---|
| D3Q4 | systemone_local / ggml-org/vllm-d3-GGUF | de9670136f5ddd83e677c89ce041d5b9bb3b0dcb / efe3626b119ff81033e309c3ba07a770bef2c546 | metal/Q4_K_M/— | 4096/24576/30 | — |
| D3FlashQ8 | systemone_local / ggml-org/vllm-d3-flash-GGUF | 3d53d13778bf8035e6e1e534ce489ed052ee5663 / efe3626b119ff81033e309c3ba07a770bef2c546 | metal/Q8_0/— | 4096/20480/30 | — |
| GLiClass9B | gliclass / knowledgator/gliclass-v4-9b | 14d11a92b5e0bab4a166e1fce4cc0777cac27182 / 6a00f8067648f25aa0f4f477d167c5f391cb4165 | mps/bfloat16/2 | 4096/32768/30 | python=3.12.12, torch=2.14.0, transformers=5.19.0 |
| Vela3Fast | vela3_fast / vllm-sr/vela3-fast | 9e338f39babc622f42e9bd8556398fe2d80d9f13 / — | cpu/float32/2 | 4096/8192/30 | python=3.12.12, torch=2.14.0, transformers=5.17.0 |

Sources, révisions et empreintes : voir analysis.json. Aucune sortie de cas ni contexte privé publié.
