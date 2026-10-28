# Comparaison des modèles de choix de contexte

Cas corrects / scorés / total ; les erreurs et absences restent dans le total.
Références agent à revoir humainement ; mesures exploratoires sur modèles isolés, pas parcours produit.

## Classement des bases

| Modèle | Corrects / scorés / total | Statuts (ok, unsupported, missing, error, timeout, abstain) | Médiane / p95 adaptateur ok (ms) | Premier appel (ms) | RSS max observé (MiB) |
|---|---:|---|---:|---:|---:|
| D3Q4 | 128/132/132 | 132/0/0/0/0/0 | 613.7 / 629.7 (132) | 621.8 | non observé (0/132 rapportés) |
| D3FlashQ8 | 124/132/132 | 132/0/0/0/0/0 | 194.3 / 200.4 (132) | 205.4 | non observé (0/132 rapportés) |
| D3FlashQ4 | 122/132/132 | 132/0/0/0/0/0 | 197.9 / 203.8 (132) | 209.9 | non observé (0/132 rapportés) |
| EosQ8 | 77/132/132 | 132/0/0/0/0/0 | 28.5 / 37.1 (132) | 85.8 | non observé (0/132 rapportés) |

Le temps adaptateur exclut l'initialisation ; premier appel distingué. P95 descriptif par rang le plus proche.

## Domaines

| Groupe | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---|---|---|---|
| chemistry | 27/28/28 | 26/28/28 | 27/28/28 | 10/28/28 |
| documentary | 73/76/76 | 72/76/76 | 71/76/76 | 55/76/76 |
| mathematics | 28/28/28 | 26/28/28 | 24/28/28 | 12/28/28 |

## Langues

| Groupe | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---|---|---|---|
| en | 64/66/66 | 62/66/66 | 60/66/66 | 38/66/66 |
| fr | 64/66/66 | 62/66/66 | 62/66/66 | 39/66/66 |

## Domaines × langues

| Groupe | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---|---|---|---|
| chemistry / en | 13/14/14 | 13/14/14 | 13/14/14 | 4/14/14 |
| chemistry / fr | 14/14/14 | 13/14/14 | 14/14/14 | 6/14/14 |
| documentary / en | 37/38/38 | 36/38/38 | 35/38/38 | 28/38/38 |
| documentary / fr | 36/38/38 | 36/38/38 | 36/38/38 | 27/38/38 |
| mathematics / en | 14/14/14 | 13/14/14 | 12/14/14 | 6/14/14 |
| mathematics / fr | 14/14/14 | 13/14/14 | 12/14/14 | 6/14/14 |

## Domaines × split

| Groupe | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---|---|---|---|
| chemistry / calibration | 8/8/8 | 8/8/8 | 8/8/8 | 3/8/8 |
| chemistry / test | 13/14/14 | 12/14/14 | 13/14/14 | 5/14/14 |
| chemistry / train | 6/6/6 | 6/6/6 | 6/6/6 | 2/6/6 |
| documentary / calibration | 14/14/14 | 14/14/14 | 14/14/14 | 12/14/14 |
| documentary / test | 38/38/38 | 37/38/38 | 36/38/38 | 27/38/38 |
| documentary / train | 21/24/24 | 21/24/24 | 21/24/24 | 16/24/24 |
| mathematics / calibration | 8/8/8 | 8/8/8 | 8/8/8 | 2/8/8 |
| mathematics / test | 14/14/14 | 12/14/14 | 10/14/14 | 8/14/14 |
| mathematics / train | 6/6/6 | 6/6/6 | 6/6/6 | 2/6/6 |

## Difficulté

| Groupe | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---|---|---|---|
| D1 | 40/40/40 | 39/40/40 | 39/40/40 | 30/40/40 |
| D2 | 38/40/40 | 37/40/40 | 37/40/40 | 22/40/40 |
| D3 | 50/52/52 | 48/52/52 | 46/52/52 | 25/52/52 |

## Split

| Groupe | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---|---|---|---|
| calibration | 30/30/30 | 30/30/30 | 30/30/30 | 17/30/30 |
| test | 65/66/66 | 61/66/66 | 59/66/66 | 40/66/66 |
| train | 33/36/36 | 33/36/36 | 33/36/36 | 20/36/36 |

## Types de tâche, tous domaines

| Groupe | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---|---|---|---|
| aliquot-and-mix | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| ambiguous-selection | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| atoms-and-charge | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| cancel-keep-domain | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-active-inventory | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-catalog-not-source-count | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| catalog-corrected-request | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-count-and-names | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-distinct-identities | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-metadata-owners | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-metadata-table-language | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-negative-summary | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| catalog-quoted-summary-command | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-scope-after-interlude | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| catalog-selected-titles | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-selection-reuse | 1/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| chain-derivative | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| combustion-balance | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| conditional-probability | 2/2/2 | 2/2/2 | 0/2/2 | 0/2/2 |
| conserved-dilution | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| extraneous-equation-root | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| formula-not-structure | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| fraction-addition | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| function-types | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| group-atom-count | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| hydrate-water-fraction | 1/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| ionic-neutrality | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| limiting-reactant | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| matrix-product | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| missing-final-volume | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| molar-concentration | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| nested-complex-count | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| polynomial-remainder | 2/2/2 | 0/2/2 | 0/2/2 | 0/2/2 |
| precipitate-mass | 2/2/2 | 0/2/2 | 1/2/2 | 1/2/2 |
| principal-root | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| quantity-dimension | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-date | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-exact-clause | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-explanation | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-filtered-list | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-not-summary | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-refutation | 2/2/2 | 1/2/2 | 1/2/2 | 2/2/2 |
| retrieve_answer-content-total-unit | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-distant-report-reference | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-followup-cause | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-quoted-instruction-content | 2/2/2 | 2/2/2 | 1/2/2 | 0/2/2 |
| retrieve_answer-relations-mermaid | 2/2/2 | 1/2/2 | 1/2/2 | 2/2/2 |
| retrieve_answer-stale-summary-check | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| square-expansion | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-cached-descriptions | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-do-not-reread | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-existing-per-file | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-inherit-summary-constraint | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-language-followup | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-quotation-not-budget-question | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-remaining-summaries | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-resume-after-content | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-summary-bundle | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-summary-count-title | 0/2/2 | 0/2/2 | 0/2/2 | 1/2/2 |
| stored_summaries-translate-summary-table | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-validated-abstracts | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| transpose-chain | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| unanchored-language | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| underdetermined-linear | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| unknown-function-values | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| water-balance | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |

## Tâches documentaires

| Groupe | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---|---|---|---|
| ambiguous-selection | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| catalog-active-inventory | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-catalog-not-source-count | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| catalog-corrected-request | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-count-and-names | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-distinct-identities | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-metadata-owners | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-metadata-table-language | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-negative-summary | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| catalog-quoted-summary-command | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-scope-after-interlude | 2/2/2 | 2/2/2 | 2/2/2 | 1/2/2 |
| catalog-selected-titles | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| catalog-selection-reuse | 1/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-date | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-exact-clause | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-explanation | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-content-filtered-list | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-not-summary | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-refutation | 2/2/2 | 1/2/2 | 1/2/2 | 2/2/2 |
| retrieve_answer-content-total-unit | 2/2/2 | 2/2/2 | 2/2/2 | 0/2/2 |
| retrieve_answer-distant-report-reference | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-followup-cause | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-quoted-instruction-content | 2/2/2 | 2/2/2 | 1/2/2 | 0/2/2 |
| retrieve_answer-relations-mermaid | 2/2/2 | 1/2/2 | 1/2/2 | 2/2/2 |
| retrieve_answer-stale-summary-check | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-cached-descriptions | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-do-not-reread | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-existing-per-file | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-inherit-summary-constraint | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-language-followup | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-quotation-not-budget-question | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-remaining-summaries | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-resume-after-content | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-summary-bundle | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-summary-count-title | 0/2/2 | 0/2/2 | 0/2/2 | 1/2/2 |
| stored_summaries-translate-summary-table | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-validated-abstracts | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| unanchored-language | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |

## Temps base (ms)

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| adapter_ms | 351.5 / 613.7 / 629.7 / 640.6 (132) | 126.8 / 194.3 / 200.4 / 205.4 (132) | 129.4 / 197.9 / 203.8 / 209.9 (132) | 26.8 / 28.5 / 37.1 / 85.8 (132) |
| decision_ms | — (0) | — (0) | — (0) | — (0) |
| http_ms | 351.3 / 613.5 / 629.5 / 640.4 (132) | 126.6 / 194.1 / 200.3 / 205.2 (132) | 129.3 / 197.7 / 203.7 / 209.6 (132) | 26.6 / 28.3 / 37.0 / 85.6 (132) |
| inference_ms | — (0) | — (0) | — (0) | — (0) |

## Phases et ressources base

Initialisation, premier appel, puis médiane / p95 des appels ok suivants ; mémoire RSS observée dans le worker et couverture sur tous les appels.

| Modèle | Init ms | Premier appel ms (statut) | Après premier ok ms (n) | RSS worker max MiB (n/total) | RSS chargement MiB |
|---|---:|---|---:|---:|---:|
| D3Q4 | — | 621.8 (ok) | 613.6 / 629.7 (131) | — (0/132) | — |
| D3FlashQ8 | — | 205.4 (ok) | 194.3 / 200.0 (131) | — (0/132) | — |
| D3FlashQ4 | — | 209.9 (ok) | 197.9 / 203.5 (131) | — (0/132) | — |
| EosQ8 | — | 85.8 (ok) | 28.5 / 37.1 (131) | — (0/132) | — |

## Temps base par statut (ms)

Médiane / p95 (n) ; temps adaptateur inclut les échecs enregistrés.

| Statut / mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| ok / adapter_ms | 613.7 / 629.7 (132) | 194.3 / 200.4 (132) | 197.9 / 203.8 (132) | 28.5 / 37.1 (132) |
| ok / inference_ms | — (0) | — (0) | — (0) | — (0) |
| ok / decision_ms | — (0) | — (0) | — (0) | — (0) |
| ok / http_ms | 613.5 / 629.5 (132) | 194.1 / 200.3 (132) | 197.7 / 203.7 (132) | 28.3 / 37.0 (132) |

## Tokens natifs base

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| encoded_tokens | — (0) | — (0) | — (0) | — (0) |
| indecis_max_sequence_tokens | — (0) | — (0) | — (0) | — (0) |
| indecis_sum_tokens | — (0) | — (0) | — (0) | — (0) |
| padded_tokens | — (0) | — (0) | — (0) | — (0) |

## Tokens déclarés par le fournisseur, base

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| input_tokens | 128.0 / 165.0 / 194.0 / 211.0 (132) | 128.0 / 165.0 / 194.0 / 211.0 (132) | 128.0 / 165.0 / 194.0 / 211.0 (132) | 131.0 / 164.5 / 193.0 / 210.0 (132) |
| output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (132) | 0.0 / 0.0 / 0.0 / 0.0 (132) | 0.0 / 0.0 / 0.0 / 0.0 (132) | 0.0 / 0.0 / 0.0 / 0.0 (132) |

## Tokens natifs base par domaine

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| chemistry | — (0) | — (0) | — (0) | — (0) |
| documentary | — (0) | — (0) | — (0) | — (0) |
| mathematics | — (0) | — (0) | — (0) | — (0) |

## Tokens natifs base par langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| en | — (0) | — (0) | — (0) | — (0) |
| fr | — (0) | — (0) | — (0) | — (0) |

## Tokens natifs base par domaine × langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| chemistry / en | — (0) | — (0) | — (0) | — (0) |
| chemistry / fr | — (0) | — (0) | — (0) | — (0) |
| documentary / en | — (0) | — (0) | — (0) | — (0) |
| documentary / fr | — (0) | — (0) | — (0) | — (0) |
| mathematics / en | — (0) | — (0) | — (0) | — (0) |
| mathematics / fr | — (0) | — (0) | — (0) | — (0) |

## Tokens fournisseur base par domaine

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| chemistry / input_tokens | 147.0 / 180.5 / 208.0 / 211.0 (28) | 147.0 / 180.5 / 208.0 / 211.0 (28) | 147.0 / 180.5 / 208.0 / 211.0 (28) | 147.0 / 179.5 / 207.0 / 210.0 (28) |
| chemistry / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (28) | 0.0 / 0.0 / 0.0 / 0.0 (28) | 0.0 / 0.0 / 0.0 / 0.0 (28) | 0.0 / 0.0 / 0.0 / 0.0 (28) |
| documentary / input_tokens | 149.0 / 168.0 / 190.0 / 193.0 (76) | 149.0 / 168.0 / 190.0 / 193.0 (76) | 149.0 / 168.0 / 190.0 / 193.0 (76) | 148.0 / 167.0 / 190.0 / 193.0 (76) |
| documentary / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (76) | 0.0 / 0.0 / 0.0 / 0.0 (76) | 0.0 / 0.0 / 0.0 / 0.0 (76) | 0.0 / 0.0 / 0.0 / 0.0 (76) |
| mathematics / input_tokens | 128.0 / 148.5 / 177.0 / 179.0 (28) | 128.0 / 148.5 / 177.0 / 179.0 (28) | 128.0 / 148.5 / 177.0 / 179.0 (28) | 131.0 / 151.0 / 176.0 / 178.0 (28) |
| mathematics / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (28) | 0.0 / 0.0 / 0.0 / 0.0 (28) | 0.0 / 0.0 / 0.0 / 0.0 (28) | 0.0 / 0.0 / 0.0 / 0.0 (28) |

## Tokens fournisseur base par langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| en / input_tokens | 128.0 / 157.0 / 186.0 / 204.0 (66) | 128.0 / 157.0 / 186.0 / 204.0 (66) | 128.0 / 157.0 / 186.0 / 204.0 (66) | 131.0 / 156.0 / 189.0 / 203.0 (66) |
| en / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (66) | 0.0 / 0.0 / 0.0 / 0.0 (66) | 0.0 / 0.0 / 0.0 / 0.0 (66) | 0.0 / 0.0 / 0.0 / 0.0 (66) |
| fr / input_tokens | 132.0 / 173.5 / 198.0 / 211.0 (66) | 132.0 / 173.5 / 198.0 / 211.0 (66) | 132.0 / 173.5 / 198.0 / 211.0 (66) | 135.0 / 174.0 / 197.0 / 210.0 (66) |
| fr / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (66) | 0.0 / 0.0 / 0.0 / 0.0 (66) | 0.0 / 0.0 / 0.0 / 0.0 (66) | 0.0 / 0.0 / 0.0 / 0.0 (66) |

## Tokens fournisseur base par domaine × langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| chemistry / en / input_tokens | 147.0 / 172.5 / 204.0 / 204.0 (14) | 147.0 / 172.5 / 204.0 / 204.0 (14) | 147.0 / 172.5 / 204.0 / 204.0 (14) | 147.0 / 172.5 / 203.0 / 203.0 (14) |
| chemistry / en / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) |
| chemistry / fr / input_tokens | 152.0 / 186.5 / 211.0 / 211.0 (14) | 152.0 / 186.5 / 211.0 / 211.0 (14) | 152.0 / 186.5 / 211.0 / 211.0 (14) | 151.0 / 185.5 / 210.0 / 210.0 (14) |
| chemistry / fr / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) |
| documentary / en / input_tokens | 149.0 / 159.5 / 173.0 / 176.0 (38) | 149.0 / 159.5 / 173.0 / 176.0 (38) | 149.0 / 159.5 / 173.0 / 176.0 (38) | 148.0 / 158.5 / 172.0 / 175.0 (38) |
| documentary / en / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (38) | 0.0 / 0.0 / 0.0 / 0.0 (38) | 0.0 / 0.0 / 0.0 / 0.0 (38) | 0.0 / 0.0 / 0.0 / 0.0 (38) |
| documentary / fr / input_tokens | 160.0 / 175.5 / 192.0 / 193.0 (38) | 160.0 / 175.5 / 192.0 / 193.0 (38) | 160.0 / 175.5 / 192.0 / 193.0 (38) | 160.0 / 175.5 / 192.0 / 193.0 (38) |
| documentary / fr / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (38) | 0.0 / 0.0 / 0.0 / 0.0 (38) | 0.0 / 0.0 / 0.0 / 0.0 (38) | 0.0 / 0.0 / 0.0 / 0.0 (38) |
| mathematics / en / input_tokens | 128.0 / 147.0 / 177.0 / 177.0 (14) | 128.0 / 147.0 / 177.0 / 177.0 (14) | 128.0 / 147.0 / 177.0 / 177.0 (14) | 131.0 / 149.5 / 176.0 / 176.0 (14) |
| mathematics / en / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) |
| mathematics / fr / input_tokens | 132.0 / 151.0 / 179.0 / 179.0 (14) | 132.0 / 151.0 / 179.0 / 179.0 (14) | 132.0 / 151.0 / 179.0 / 179.0 (14) | 135.0 / 153.0 / 178.0 / 178.0 (14) |
| mathematics / fr / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) | 0.0 / 0.0 / 0.0 / 0.0 (14) |

## Longueur commune des entrées base

Somme des caractères Unicode ou mots séparés par espace dans le contexte, la question et les descriptions d'options visibles par tous ; exclut les identifiants et la sérialisation.

| Mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| characters | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) |
| words | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) |

Tokens natifs : encodage propre à chaque adaptateur ; `indecis_max_sequence_tokens` mesure la plus longue séquence, `indecis_sum_tokens` la somme des séquences. Tokens fournisseur : comptabilité postérieure à la requête, non comparable au tokenizer local. RSS : pics rapportés par worker, sans RAM serveur distant.

## Confusion des actions documentaires sur la base

| Attendu → prédit | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| catalog → catalog | 23 | 24 | 24 | 13 |
| catalog → insufficient_information | 0 | 0 | 0 | 3 |
| catalog → retrieve_answer | 1 | 0 | 0 | 4 |
| catalog → stored_summaries | 0 | 0 | 0 | 4 |
| insufficient_information → A_and_B | 0 | 0 | 0 | 1 |
| insufficient_information → insufficient_information | 4 | 4 | 4 | 3 |
| retrieve_answer → catalog | 0 | 0 | 1 | 0 |
| retrieve_answer → insufficient_information | 0 | 2 | 2 | 8 |
| retrieve_answer → retrieve_answer | 24 | 22 | 21 | 16 |
| stored_summaries → catalog | 2 | 2 | 2 | 1 |
| stored_summaries → stored_summaries | 22 | 22 | 22 | 23 |

## Confusion documentaire base FR

| Attendu → prédit | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| catalog → catalog | 11 | 12 | 12 | 5 |
| catalog → insufficient_information | 0 | 0 | 0 | 3 |
| catalog → retrieve_answer | 1 | 0 | 0 | 2 |
| catalog → stored_summaries | 0 | 0 | 0 | 2 |
| insufficient_information → insufficient_information | 2 | 2 | 2 | 2 |
| retrieve_answer → insufficient_information | 0 | 1 | 1 | 4 |
| retrieve_answer → retrieve_answer | 12 | 11 | 11 | 8 |
| stored_summaries → catalog | 1 | 1 | 1 | 0 |
| stored_summaries → stored_summaries | 11 | 11 | 11 | 12 |

## Confusion documentaire base EN

| Attendu → prédit | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| catalog → catalog | 12 | 12 | 12 | 8 |
| catalog → retrieve_answer | 0 | 0 | 0 | 2 |
| catalog → stored_summaries | 0 | 0 | 0 | 2 |
| insufficient_information → A_and_B | 0 | 0 | 0 | 1 |
| insufficient_information → insufficient_information | 2 | 2 | 2 | 1 |
| retrieve_answer → catalog | 0 | 0 | 1 | 0 |
| retrieve_answer → insufficient_information | 0 | 1 | 1 | 4 |
| retrieve_answer → retrieve_answer | 12 | 11 | 10 | 8 |
| stored_summaries → catalog | 1 | 1 | 1 | 1 |
| stored_summaries → stored_summaries | 11 | 11 | 11 | 11 |

## Cohérence des traductions documentaires FR/EN

| Modèle | Paires scorées / total | Même action | Deux correctes |
|---|---:|---:|---:|
| D3Q4 | 38/38 | 37/38 | 36/38 |
| D3FlashQ8 | 38/38 | 36/38 | 35/38 |
| D3FlashQ4 | 38/38 | 35/38 | 34/38 |
| EosQ8 | 38/38 | 31/38 | 25/38 |

## Provenance et limites des bases

Champs explicitement autorisés depuis les profils et les archives ; empreintes complètes dans analysis.json.

| Modèle | Adaptateur / modèle | Révision modèle / source | Device / dtype / threads | Limite entrée / RSS / timeout | Runtimes sélectionnés |
|---|---|---|---|---|---|
| D3Q4 | systemone_local / ggml-org/vllm-d3-GGUF | de9670136f5ddd83e677c89ce041d5b9bb3b0dcb / efe3626b119ff81033e309c3ba07a770bef2c546 | metal/Q4_K_M/— | 4096/24576/30 | — |
| D3FlashQ8 | systemone_local / ggml-org/vllm-d3-flash-GGUF | 3d53d13778bf8035e6e1e534ce489ed052ee5663 / efe3626b119ff81033e309c3ba07a770bef2c546 | metal/Q8_0/— | 4096/20480/30 | — |
| D3FlashQ4 | systemone_local / ggml-org/vllm-d3-flash-GGUF | 3d53d13778bf8035e6e1e534ce489ed052ee5663 / efe3626b119ff81033e309c3ba07a770bef2c546 | metal/Q4_K_M/— | 4096/14336/30 | — |
| EosQ8 | systemone_local / vllm-sr/Decision-2.0-Eos-0.8B-GGUF | a02a4cc6a4d637003ceede6f8b3b0bb0125b2d66 / 3c64a581d4f95bb2de409d383741fa5b18d84345 | metal/Q8_0/— | 4096/8192/30 | — |

## Troncature observée, base

Vrai / faux / inconnu sur tous les appels ; le compteur Laya indique état tronqué positif / zéro / inconnu.

| Modèle | État | Options | Préfixe Noma | Usage natif | État Laya réduit |
|---|---:|---:|---:|---:|---:|
| D3Q4 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 |
| D3FlashQ8 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 |
| D3FlashQ4 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 |
| EosQ8 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 |

## Observation Mastra

Accord avec propositions d'agent ; références pending_human, aucun score sémantique final.

| Modèle | Accord / valides / total | Statuts | Médiane / p95 adaptateur ok (ms) | RSS max observé (MiB) |
|---|---:|---|---:|---:|
| D3Q4 | 24/24/24 | 24/0/0/0/0/0 | 650.8 / 675.7 | non observé (0/24 rapportés) |
| D3FlashQ8 | 20/24/24 | 24/0/0/0/0/0 | 206.5 / 219.9 | non observé (0/24 rapportés) |
| D3FlashQ4 | 21/24/24 | 24/0/0/0/0/0 | 211.7 / 226.2 | non observé (0/24 rapportés) |
| EosQ8 | 19/24/24 | 24/0/0/0/0/0 | 31.5 / 44.3 | non observé (0/24 rapportés) |

## Mastra par action proposée

Accords / décisions valides / total. Une proposition en attente de revue humaine ne vaut pas une référence validée.

| Action | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| search | 8/8/8 | 8/8/8 | 8/8/8 | 7/8/8 |
| stats | 8/8/8 | 8/8/8 | 8/8/8 | 8/8/8 |
| fallback | 8/8/8 | 4/8/8 | 5/8/8 | 4/8/8 |

## Mastra par action proposée et langue

Accords / décisions valides / total.

| Action / langue | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| search / fr | 4/4/4 | 4/4/4 | 4/4/4 | 4/4/4 |
| search / en | 4/4/4 | 4/4/4 | 4/4/4 | 3/4/4 |
| stats / fr | 4/4/4 | 4/4/4 | 4/4/4 | 4/4/4 |
| stats / en | 4/4/4 | 4/4/4 | 4/4/4 | 4/4/4 |
| fallback / fr | 4/4/4 | 1/4/4 | 2/4/4 | 2/4/4 |
| fallback / en | 4/4/4 | 3/4/4 | 3/4/4 | 2/4/4 |

## Mastra : action proposée → action prédite

| Attendu → prédit | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| fallback → fallback | 8 | 4 | 5 | 4 |
| fallback → search | 0 | 3 | 3 | 2 |
| fallback → stats | 0 | 1 | 0 | 2 |
| search → search | 8 | 8 | 8 | 7 |
| search → stats | 0 | 0 | 0 | 1 |
| stats → stats | 8 | 8 | 8 | 8 |

## Mastra : action proposée → prédite FR

| Attendu → prédit | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| fallback → fallback | 4 | 1 | 2 | 2 |
| fallback → search | 0 | 2 | 2 | 2 |
| fallback → stats | 0 | 1 | 0 | 0 |
| search → search | 4 | 4 | 4 | 4 |
| stats → stats | 4 | 4 | 4 | 4 |

## Mastra : action proposée → prédite EN

| Attendu → prédit | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| fallback → fallback | 4 | 3 | 3 | 2 |
| fallback → search | 0 | 1 | 1 | 0 |
| fallback → stats | 0 | 0 | 0 | 2 |
| search → search | 4 | 4 | 4 | 3 |
| search → stats | 0 | 0 | 0 | 1 |
| stats → stats | 4 | 4 | 4 | 4 |

## Mastra par langue et split

Accords / décisions valides / total.

| Groupe | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| by_language / en | 12/12/12 | 11/12/12 | 11/12/12 | 9/12/12 |
| by_language / fr | 12/12/12 | 9/12/12 | 10/12/12 | 10/12/12 |
| by_split / calibration | 6/6/6 | 4/6/6 | 4/6/6 | 4/6/6 |
| by_split / test | 18/18/18 | 16/18/18 | 17/18/18 | 15/18/18 |

## Temps Mastra (ms)

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| adapter_ms | 633.4 / 650.8 / 675.7 / 911.5 (24) | 201.9 / 206.5 / 219.9 / 277.8 (24) | 205.8 / 211.7 / 226.2 / 285.5 (24) | 29.8 / 31.5 / 44.3 / 53.6 (24) |
| decision_ms | — (0) | — (0) | — (0) | — (0) |
| http_ms | 633.0 / 650.5 / 675.4 / 911.2 (24) | 201.6 / 206.1 / 219.5 / 277.3 (24) | 205.4 / 211.4 / 225.8 / 285.1 (24) | 29.5 / 31.2 / 44.0 / 53.3 (24) |
| inference_ms | — (0) | — (0) | — (0) | — (0) |

## Phases et ressources Mastra

Initialisation, premier appel, puis médiane / p95 des appels ok suivants ; mémoire RSS observée dans le worker et couverture sur tous les appels.

| Modèle | Init ms | Premier appel ms (statut) | Après premier ok ms (n) | RSS worker max MiB (n/total) | RSS chargement MiB |
|---|---:|---|---:|---:|---:|
| D3Q4 | — | 671.0 (ok) | 649.3 / 675.7 (23) | — (0/24) | — |
| D3FlashQ8 | — | 219.9 (ok) | 205.6 / 212.1 (23) | — (0/24) | — |
| D3FlashQ4 | — | 226.2 (ok) | 211.2 / 218.2 (23) | — (0/24) | — |
| EosQ8 | — | 53.6 (ok) | 31.3 / 32.9 (23) | — (0/24) | — |

## Temps Mastra par statut (ms)

Médiane / p95 (n) ; temps adaptateur inclut les échecs enregistrés.

| Statut / mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| ok / adapter_ms | 650.8 / 675.7 (24) | 206.5 / 219.9 (24) | 211.7 / 226.2 (24) | 31.5 / 44.3 (24) |
| ok / inference_ms | — (0) | — (0) | — (0) | — (0) |
| ok / decision_ms | — (0) | — (0) | — (0) | — (0) |
| ok / http_ms | 650.5 / 675.4 (24) | 206.1 / 219.5 (24) | 211.4 / 225.8 (24) | 31.2 / 44.0 (24) |

## Tokens natifs Mastra

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| encoded_tokens | — (0) | — (0) | — (0) | — (0) |
| indecis_max_sequence_tokens | — (0) | — (0) | — (0) | — (0) |
| indecis_sum_tokens | — (0) | — (0) | — (0) | — (0) |
| padded_tokens | — (0) | — (0) | — (0) | — (0) |

## Tokens déclarés par le fournisseur, Mastra

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| input_tokens | 201.0 / 227.5 / 252.0 / 264.0 (24) | 201.0 / 227.5 / 252.0 / 264.0 (24) | 201.0 / 227.5 / 252.0 / 264.0 (24) | 190.0 / 217.0 / 242.0 / 254.0 (24) |
| output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (24) | 0.0 / 0.0 / 0.0 / 0.0 (24) | 0.0 / 0.0 / 0.0 / 0.0 (24) | 0.0 / 0.0 / 0.0 / 0.0 (24) |

## Tokens natifs Mastra par langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| en | — (0) | — (0) | — (0) | — (0) |
| fr | — (0) | — (0) | — (0) | — (0) |

## Tokens fournisseur Mastra par langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| en / input_tokens | 201.0 / 208.0 / 225.0 / 225.0 (12) | 201.0 / 208.0 / 225.0 / 225.0 (12) | 201.0 / 208.0 / 225.0 / 225.0 (12) | 190.0 / 197.0 / 214.0 / 214.0 (12) |
| en / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (12) | 0.0 / 0.0 / 0.0 / 0.0 (12) | 0.0 / 0.0 / 0.0 / 0.0 (12) | 0.0 / 0.0 / 0.0 / 0.0 (12) |
| fr / input_tokens | 230.0 / 241.0 / 264.0 / 264.0 (12) | 230.0 / 241.0 / 264.0 / 264.0 (12) | 230.0 / 241.0 / 264.0 / 264.0 (12) | 220.0 / 231.0 / 254.0 / 254.0 (12) |
| fr / output_tokens | 0.0 / 0.0 / 0.0 / 0.0 (12) | 0.0 / 0.0 / 0.0 / 0.0 (12) | 0.0 / 0.0 / 0.0 / 0.0 (12) | 0.0 / 0.0 / 0.0 / 0.0 (12) |

## Longueur commune des entrées Mastra

Somme des caractères Unicode ou mots séparés par espace dans le contexte, la question et les descriptions d'options visibles par tous ; exclut les identifiants et la sérialisation.

| Mesure | D3Q4 | D3FlashQ8 | D3FlashQ4 | EosQ8 |
|---|---:|---:|---:|---:|
| characters | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) |
| words | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) |

## Troncature observée, Mastra

Vrai / faux / inconnu sur tous les appels ; le compteur Laya indique état tronqué positif / zéro / inconnu.

| Modèle | État | Options | Préfixe Noma | Usage natif | État Laya réduit |
|---|---:|---:|---:|---:|---:|
| D3Q4 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 |
| D3FlashQ8 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 |
| D3FlashQ4 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 |
| EosQ8 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 |

## Cohérence Mastra FR/EN

| Modèle | Paires valides / total | Même action |
|---|---:|---:|
| D3Q4 | 12/12 | 12/12 |
| D3FlashQ8 | 12/12 | 10/12 |
| D3FlashQ4 | 12/12 | 11/12 |
| EosQ8 | 12/12 | 9/12 |

## Provenance et limites Mastra

Champs explicitement autorisés depuis les profils et les archives ; empreintes complètes dans analysis.json.

| Modèle | Adaptateur / modèle | Révision modèle / source | Device / dtype / threads | Limite entrée / RSS / timeout | Runtimes sélectionnés |
|---|---|---|---|---|---|
| D3Q4 | systemone_local / ggml-org/vllm-d3-GGUF | de9670136f5ddd83e677c89ce041d5b9bb3b0dcb / efe3626b119ff81033e309c3ba07a770bef2c546 | metal/Q4_K_M/— | 4096/24576/30 | — |
| D3FlashQ8 | systemone_local / ggml-org/vllm-d3-flash-GGUF | 3d53d13778bf8035e6e1e534ce489ed052ee5663 / efe3626b119ff81033e309c3ba07a770bef2c546 | metal/Q8_0/— | 4096/20480/30 | — |
| D3FlashQ4 | systemone_local / ggml-org/vllm-d3-flash-GGUF | 3d53d13778bf8035e6e1e534ce489ed052ee5663 / efe3626b119ff81033e309c3ba07a770bef2c546 | metal/Q4_K_M/— | 4096/14336/30 | — |
| EosQ8 | systemone_local / vllm-sr/Decision-2.0-Eos-0.8B-GGUF | a02a4cc6a4d637003ceede6f8b3b0bb0125b2d66 / 3c64a581d4f95bb2de409d383741fa5b18d84345 | metal/Q8_0/— | 4096/8192/30 | — |

Sources, révisions et empreintes : voir analysis.json. Aucune sortie de cas ni contexte privé publié.
