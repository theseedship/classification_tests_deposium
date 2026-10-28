# Comparaison des modèles de choix de contexte

Cas corrects / scorés / total ; les erreurs et absences restent dans le total.
Références agent à revoir humainement ; mesures exploratoires sur modèles isolés, pas parcours produit.

## Classement des bases

| Modèle | Corrects / scorés / total | Statuts (ok, unsupported, missing, error, timeout, abstain) | Médiane / p95 adaptateur ok (ms) | Premier appel (ms) | RSS max observé (MiB) |
|---|---:|---|---:|---:|---:|
| Vela4 | 106/132/132 | 132/0/0/0/0/0 | 7948.5 / 9042.8 (132) | 8569.6 | 18420.9 (132/132 rapportés) |
| Nox | 103/132/132 | 132/0/0/0/0/0 | 5919.6 / 7373.8 (132) | 5944.1 | 21151.2 (132/132 rapportés) |
| Liquid3 | 101/132/132 | 132/0/0/0/0/0 | 8079.9 / 10717.1 (132) | 8070.4 | 18227.9 (132/132 rapportés) |

Le temps adaptateur exclut l'initialisation ; premier appel distingué. P95 descriptif par rang le plus proche.

## Domaines

| Groupe | Vela4 | Nox | Liquid3 |
|---|---|---|---|
| chemistry | 22/28/28 | 24/28/28 | 20/28/28 |
| documentary | 64/76/76 | 54/76/76 | 60/76/76 |
| mathematics | 20/28/28 | 25/28/28 | 21/28/28 |

## Langues

| Groupe | Vela4 | Nox | Liquid3 |
|---|---|---|---|
| en | 54/66/66 | 53/66/66 | 51/66/66 |
| fr | 52/66/66 | 50/66/66 | 50/66/66 |

## Domaines × langues

| Groupe | Vela4 | Nox | Liquid3 |
|---|---|---|---|
| chemistry / en | 11/14/14 | 12/14/14 | 10/14/14 |
| chemistry / fr | 11/14/14 | 12/14/14 | 10/14/14 |
| documentary / en | 33/38/38 | 28/38/38 | 30/38/38 |
| documentary / fr | 31/38/38 | 26/38/38 | 30/38/38 |
| mathematics / en | 10/14/14 | 13/14/14 | 11/14/14 |
| mathematics / fr | 10/14/14 | 12/14/14 | 10/14/14 |

## Domaines × split

| Groupe | Vela4 | Nox | Liquid3 |
|---|---|---|---|
| chemistry / calibration | 5/8/8 | 6/8/8 | 4/8/8 |
| chemistry / test | 12/14/14 | 12/14/14 | 10/14/14 |
| chemistry / train | 5/6/6 | 6/6/6 | 6/6/6 |
| documentary / calibration | 12/14/14 | 9/14/14 | 10/14/14 |
| documentary / test | 34/38/38 | 31/38/38 | 35/38/38 |
| documentary / train | 18/24/24 | 14/24/24 | 15/24/24 |
| mathematics / calibration | 6/8/8 | 7/8/8 | 8/8/8 |
| mathematics / test | 10/14/14 | 12/14/14 | 10/14/14 |
| mathematics / train | 4/6/6 | 6/6/6 | 3/6/6 |

## Difficulté

| Groupe | Vela4 | Nox | Liquid3 |
|---|---|---|---|
| D1 | 38/40/40 | 32/40/40 | 29/40/40 |
| D2 | 33/40/40 | 31/40/40 | 30/40/40 |
| D3 | 35/52/52 | 40/52/52 | 42/52/52 |

## Split

| Groupe | Vela4 | Nox | Liquid3 |
|---|---|---|---|
| calibration | 23/30/30 | 22/30/30 | 22/30/30 |
| test | 56/66/66 | 55/66/66 | 55/66/66 |
| train | 27/36/36 | 26/36/36 | 24/36/36 |

## Types de tâche, tous domaines

| Groupe | Vela4 | Nox | Liquid3 |
|---|---|---|---|
| aliquot-and-mix | 1/2/2 | 0/2/2 | 0/2/2 |
| ambiguous-selection | 2/2/2 | 2/2/2 | 2/2/2 |
| atoms-and-charge | 2/2/2 | 2/2/2 | 2/2/2 |
| cancel-keep-domain | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-active-inventory | 2/2/2 | 0/2/2 | 0/2/2 |
| catalog-catalog-not-source-count | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-corrected-request | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-count-and-names | 1/2/2 | 0/2/2 | 0/2/2 |
| catalog-distinct-identities | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-metadata-owners | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-metadata-table-language | 2/2/2 | 1/2/2 | 1/2/2 |
| catalog-negative-summary | 2/2/2 | 1/2/2 | 0/2/2 |
| catalog-quoted-summary-command | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-scope-after-interlude | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-selected-titles | 2/2/2 | 0/2/2 | 0/2/2 |
| catalog-selection-reuse | 0/2/2 | 0/2/2 | 0/2/2 |
| chain-derivative | 2/2/2 | 2/2/2 | 2/2/2 |
| combustion-balance | 0/2/2 | 2/2/2 | 0/2/2 |
| conditional-probability | 0/2/2 | 0/2/2 | 2/2/2 |
| conserved-dilution | 2/2/2 | 2/2/2 | 2/2/2 |
| extraneous-equation-root | 0/2/2 | 2/2/2 | 0/2/2 |
| formula-not-structure | 2/2/2 | 2/2/2 | 2/2/2 |
| fraction-addition | 2/2/2 | 2/2/2 | 1/2/2 |
| function-types | 2/2/2 | 2/2/2 | 2/2/2 |
| group-atom-count | 2/2/2 | 2/2/2 | 2/2/2 |
| hydrate-water-fraction | 2/2/2 | 2/2/2 | 2/2/2 |
| ionic-neutrality | 2/2/2 | 2/2/2 | 0/2/2 |
| limiting-reactant | 1/2/2 | 2/2/2 | 2/2/2 |
| matrix-product | 2/2/2 | 2/2/2 | 0/2/2 |
| missing-final-volume | 2/2/2 | 2/2/2 | 2/2/2 |
| molar-concentration | 2/2/2 | 2/2/2 | 2/2/2 |
| nested-complex-count | 2/2/2 | 2/2/2 | 2/2/2 |
| polynomial-remainder | 0/2/2 | 2/2/2 | 0/2/2 |
| precipitate-mass | 0/2/2 | 0/2/2 | 0/2/2 |
| principal-root | 2/2/2 | 2/2/2 | 2/2/2 |
| quantity-dimension | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-date | 0/2/2 | 0/2/2 | 1/2/2 |
| retrieve_answer-content-exact-clause | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-explanation | 2/2/2 | 1/2/2 | 1/2/2 |
| retrieve_answer-content-filtered-list | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-not-summary | 1/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-refutation | 2/2/2 | 1/2/2 | 2/2/2 |
| retrieve_answer-content-total-unit | 1/2/2 | 0/2/2 | 2/2/2 |
| retrieve_answer-distant-report-reference | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-followup-cause | 2/2/2 | 1/2/2 | 2/2/2 |
| retrieve_answer-quoted-instruction-content | 0/2/2 | 0/2/2 | 2/2/2 |
| retrieve_answer-relations-mermaid | 2/2/2 | 1/2/2 | 1/2/2 |
| retrieve_answer-stale-summary-check | 2/2/2 | 2/2/2 | 2/2/2 |
| square-expansion | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-cached-descriptions | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-do-not-reread | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-existing-per-file | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-inherit-summary-constraint | 1/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-language-followup | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-quotation-not-budget-question | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-remaining-summaries | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-resume-after-content | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-summary-bundle | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-summary-count-title | 0/2/2 | 0/2/2 | 0/2/2 |
| stored_summaries-translate-summary-table | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-validated-abstracts | 2/2/2 | 2/2/2 | 2/2/2 |
| transpose-chain | 0/2/2 | 1/2/2 | 2/2/2 |
| unanchored-language | 2/2/2 | 2/2/2 | 2/2/2 |
| underdetermined-linear | 2/2/2 | 2/2/2 | 2/2/2 |
| unknown-function-values | 2/2/2 | 2/2/2 | 2/2/2 |
| water-balance | 2/2/2 | 2/2/2 | 2/2/2 |

## Tâches documentaires

| Groupe | Vela4 | Nox | Liquid3 |
|---|---|---|---|
| ambiguous-selection | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-active-inventory | 2/2/2 | 0/2/2 | 0/2/2 |
| catalog-catalog-not-source-count | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-corrected-request | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-count-and-names | 1/2/2 | 0/2/2 | 0/2/2 |
| catalog-distinct-identities | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-metadata-owners | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-metadata-table-language | 2/2/2 | 1/2/2 | 1/2/2 |
| catalog-negative-summary | 2/2/2 | 1/2/2 | 0/2/2 |
| catalog-quoted-summary-command | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-scope-after-interlude | 2/2/2 | 2/2/2 | 2/2/2 |
| catalog-selected-titles | 2/2/2 | 0/2/2 | 0/2/2 |
| catalog-selection-reuse | 0/2/2 | 0/2/2 | 0/2/2 |
| retrieve_answer-content-date | 0/2/2 | 0/2/2 | 1/2/2 |
| retrieve_answer-content-exact-clause | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-explanation | 2/2/2 | 1/2/2 | 1/2/2 |
| retrieve_answer-content-filtered-list | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-not-summary | 1/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-content-refutation | 2/2/2 | 1/2/2 | 2/2/2 |
| retrieve_answer-content-total-unit | 1/2/2 | 0/2/2 | 2/2/2 |
| retrieve_answer-distant-report-reference | 2/2/2 | 2/2/2 | 2/2/2 |
| retrieve_answer-followup-cause | 2/2/2 | 1/2/2 | 2/2/2 |
| retrieve_answer-quoted-instruction-content | 0/2/2 | 0/2/2 | 2/2/2 |
| retrieve_answer-relations-mermaid | 2/2/2 | 1/2/2 | 1/2/2 |
| retrieve_answer-stale-summary-check | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-cached-descriptions | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-do-not-reread | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-existing-per-file | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-inherit-summary-constraint | 1/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-language-followup | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-quotation-not-budget-question | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-remaining-summaries | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-resume-after-content | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-summary-bundle | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-summary-count-title | 0/2/2 | 0/2/2 | 0/2/2 |
| stored_summaries-translate-summary-table | 2/2/2 | 2/2/2 | 2/2/2 |
| stored_summaries-validated-abstracts | 2/2/2 | 2/2/2 | 2/2/2 |
| unanchored-language | 2/2/2 | 2/2/2 | 2/2/2 |

## Temps base ok (ms)

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| adapter_ms | 6550.9 / 7948.5 / 9042.8 / 14308.9 (132) | 4848.5 / 5919.6 / 7373.8 / 9529.5 (132) | 3279.6 / 8079.9 / 10717.1 / 11644.7 (132) |
| decision_ms | 6544.4 / 7941.8 / 9036.3 / 14297.3 (132) | 4842.6 / 5913.2 / 7367.7 / 9521.8 (132) | 3276.0 / 8074.6 / 10713.9 / 11641.1 (132) |
| http_ms | — (0) | — (0) | — (0) |
| inference_ms | 6543.6 / 7940.7 / 9035.1 / 14295.9 (132) | 4841.5 / 5911.8 / 7366.5 / 9520.4 (132) | 3275.5 / 8073.4 / 10713.1 / 11640.3 (132) |

## Phases et ressources base

Initialisation, premier appel, puis médiane / p95 des appels ok suivants ; mémoire RSS observée dans le worker et couverture sur tous les appels.

| Modèle | Init ms | Premier appel ms (statut) | Après premier ok ms (n) | RSS worker max MiB (n/total) | RSS chargement MiB |
|---|---:|---|---:|---:|---:|
| Vela4 | 24298.6 | 8569.6 (ok) | 7948.4 / 9042.8 (131) | 18420.9 (132/132) | 18420.9 |
| Nox | 25886.0 | 5944.1 (ok) | 5895.1 / 7373.8 (131) | 21151.2 (132/132) | 21056.2 |
| Liquid3 | 12649.6 | 8070.4 (ok) | 8089.4 / 10717.1 (131) | 18227.9 (132/132) | 18227.9 |

## Temps base par statut (ms)

Médiane / p95 (n) ; réponses ok uniquement.

| Statut / mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| ok / adapter_ms | 7948.5 / 9042.8 (132) | 5919.6 / 7373.8 (132) | 8079.9 / 10717.1 (132) |
| ok / inference_ms | 7940.7 / 9035.1 (132) | 5911.8 / 7366.5 (132) | 8073.4 / 10713.1 (132) |
| ok / decision_ms | 7941.8 / 9036.3 (132) | 5913.2 / 7367.7 (132) | 8074.6 / 10713.9 (132) |
| ok / http_ms | — (0) | — (0) | — (0) |

## Tokens natifs base

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| encoded_tokens | 171.0 / 204.5 / 233.0 / 250.0 (132) | 131.0 / 164.5 / 193.0 / 210.0 (132) | — (0) |
| full_input_tokens | — (0) | — (0) | 58.0 / 96.0 / 123.0 / 134.0 (132) |
| max_sequence_tokens | 171.0 / 204.5 / 233.0 / 250.0 (132) | 131.0 / 164.5 / 193.0 / 210.0 (132) | 58.0 / 96.0 / 123.0 / 134.0 (132) |
| padded_batch_tokens | — (0) | — (0) | — (0) |
| padded_tokens | — (0) | — (0) | — (0) |
| sum_sequence_tokens | 171.0 / 204.5 / 233.0 / 250.0 (132) | 131.0 / 164.5 / 193.0 / 210.0 (132) | 58.0 / 96.0 / 123.0 / 134.0 (132) |

## Tokens déclarés par le fournisseur, base

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| input_tokens | — (0) | — (0) | — (0) |
| output_tokens | — (0) | — (0) | — (0) |

## Tokens natifs base par domaine

Tokens natifs plus longue séquence native : médiane / p95 (n mesuré).

| Groupe | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| chemistry | 219.5 / 247.0 (28) | 179.5 / 207.0 (28) | 104.5 / 129.0 (28) |
| documentary | 207.0 / 230.0 (76) | 167.0 / 190.0 (76) | 98.0 / 121.0 (76) |
| mathematics | 191.0 / 216.0 (28) | 151.0 / 176.0 (28) | 79.5 / 102.0 (28) |

## Tokens natifs base par langue

Tokens natifs plus longue séquence native : médiane / p95 (n mesuré).

| Groupe | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| en | 196.0 / 229.0 (66) | 156.0 / 189.0 (66) | 88.0 / 113.0 (66) |
| fr | 214.0 / 237.0 (66) | 174.0 / 197.0 (66) | 105.0 / 125.0 (66) |

## Tokens natifs base par domaine × langue

Tokens natifs plus longue séquence native : médiane / p95 (n mesuré).

| Groupe | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| chemistry / en | 212.5 / 243.0 (14) | 172.5 / 203.0 (14) | 100.0 / 129.0 (14) |
| chemistry / fr | 225.5 / 250.0 (14) | 185.5 / 210.0 (14) | 109.5 / 134.0 (14) |
| documentary / en | 198.5 / 212.0 (38) | 158.5 / 172.0 (38) | 88.5 / 105.0 (38) |
| documentary / fr | 215.5 / 232.0 (38) | 175.5 / 192.0 (38) | 107.0 / 125.0 (38) |
| mathematics / en | 189.5 / 216.0 (14) | 149.5 / 176.0 (14) | 77.0 / 102.0 (14) |
| mathematics / fr | 193.0 / 218.0 (14) | 153.0 / 178.0 (14) | 80.0 / 105.0 (14) |

## Tokens fournisseur base par domaine

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| chemistry / input_tokens | — (0) | — (0) | — (0) |
| chemistry / output_tokens | — (0) | — (0) | — (0) |
| documentary / input_tokens | — (0) | — (0) | — (0) |
| documentary / output_tokens | — (0) | — (0) | — (0) |
| mathematics / input_tokens | — (0) | — (0) | — (0) |
| mathematics / output_tokens | — (0) | — (0) | — (0) |

## Tokens fournisseur base par langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| en / input_tokens | — (0) | — (0) | — (0) |
| en / output_tokens | — (0) | — (0) | — (0) |
| fr / input_tokens | — (0) | — (0) | — (0) |
| fr / output_tokens | — (0) | — (0) | — (0) |

## Tokens fournisseur base par domaine × langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| chemistry / en / input_tokens | — (0) | — (0) | — (0) |
| chemistry / en / output_tokens | — (0) | — (0) | — (0) |
| chemistry / fr / input_tokens | — (0) | — (0) | — (0) |
| chemistry / fr / output_tokens | — (0) | — (0) | — (0) |
| documentary / en / input_tokens | — (0) | — (0) | — (0) |
| documentary / en / output_tokens | — (0) | — (0) | — (0) |
| documentary / fr / input_tokens | — (0) | — (0) | — (0) |
| documentary / fr / output_tokens | — (0) | — (0) | — (0) |
| mathematics / en / input_tokens | — (0) | — (0) | — (0) |
| mathematics / en / output_tokens | — (0) | — (0) | — (0) |
| mathematics / fr / input_tokens | — (0) | — (0) | — (0) |
| mathematics / fr / output_tokens | — (0) | — (0) | — (0) |

## Longueur commune des entrées base

Somme des caractères Unicode ou mots séparés par espace dans le contexte, la question et les descriptions d'options visibles par tous ; exclut les identifiants et la sérialisation.

| Mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| characters | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) | 85.0 / 304.0 / 404.0 / 441.0 (132) |
| words | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) | 15.0 / 47.0 / 63.0 / 70.0 (132) |

Tokens natifs : `max_sequence_tokens` est la plus longue séquence par décision, `sum_sequence_tokens` additionne ses séquences et `padded_batch_tokens` relève séparément les positions allouées. Les refus pré-forward restent comptés quand le tokenizer natif a mesuré l'entrée complète. Les temps agrégés ci-dessus concernent uniquement les réponses ok. Tokens fournisseur : comptabilité postérieure à la requête, non comparable au tokenizer local. RSS : pics rapportés par worker, sans RAM serveur distant.

## Confusion des actions documentaires sur la base

| Attendu → prédit | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| catalog → catalog | 21 | 14 | 13 |
| catalog → insufficient_information | 0 | 7 | 5 |
| catalog → retrieve_answer | 2 | 2 | 4 |
| catalog → stored_summaries | 1 | 1 | 2 |
| insufficient_information → insufficient_information | 4 | 4 | 4 |
| retrieve_answer → catalog | 3 | 0 | 1 |
| retrieve_answer → insufficient_information | 2 | 10 | 2 |
| retrieve_answer → retrieve_answer | 18 | 14 | 21 |
| retrieve_answer → stored_summaries | 1 | 0 | 0 |
| stored_summaries → catalog | 2 | 0 | 1 |
| stored_summaries → insufficient_information | 0 | 2 | 1 |
| stored_summaries → retrieve_answer | 1 | 0 | 0 |
| stored_summaries → stored_summaries | 21 | 22 | 22 |

## Confusion documentaire base FR

| Attendu → prédit | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| catalog → catalog | 11 | 7 | 7 |
| catalog → insufficient_information | 0 | 3 | 2 |
| catalog → retrieve_answer | 1 | 2 | 2 |
| catalog → stored_summaries | 0 | 0 | 1 |
| insufficient_information → insufficient_information | 2 | 2 | 2 |
| retrieve_answer → catalog | 2 | 0 | 1 |
| retrieve_answer → insufficient_information | 1 | 6 | 1 |
| retrieve_answer → retrieve_answer | 8 | 6 | 10 |
| retrieve_answer → stored_summaries | 1 | 0 | 0 |
| stored_summaries → catalog | 1 | 0 | 0 |
| stored_summaries → insufficient_information | 0 | 1 | 1 |
| stored_summaries → retrieve_answer | 1 | 0 | 0 |
| stored_summaries → stored_summaries | 10 | 11 | 11 |

## Confusion documentaire base EN

| Attendu → prédit | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| catalog → catalog | 10 | 7 | 6 |
| catalog → insufficient_information | 0 | 4 | 3 |
| catalog → retrieve_answer | 1 | 0 | 2 |
| catalog → stored_summaries | 1 | 1 | 1 |
| insufficient_information → insufficient_information | 2 | 2 | 2 |
| retrieve_answer → catalog | 1 | 0 | 0 |
| retrieve_answer → insufficient_information | 1 | 4 | 1 |
| retrieve_answer → retrieve_answer | 10 | 8 | 11 |
| stored_summaries → catalog | 1 | 0 | 1 |
| stored_summaries → insufficient_information | 0 | 1 | 0 |
| stored_summaries → stored_summaries | 11 | 11 | 11 |

## Cohérence des traductions documentaires FR/EN

| Modèle | Paires scorées / total | Même action | Deux correctes |
|---|---:|---:|---:|
| Vela4 | 38/38 | 34/38 | 30/38 |
| Nox | 38/38 | 30/38 | 24/38 |
| Liquid3 | 38/38 | 30/38 | 28/38 |

## Provenance et limites des bases

Champs explicitement autorisés depuis les profils et les archives ; empreintes complètes dans analysis.json.

| Modèle | Adaptateur / modèle | Révision modèle / source | Device / dtype / threads | Limite entrée / RSS / timeout | Runtimes sélectionnés |
|---|---|---|---|---|---|
| Vela4 | vela2 / vllm-sr/Vela-2.0-4B | d692394127f6f87fc581d8634c9558fe4776efce / — | cpu/float32/2 | 4096/22528/60 | python=3.12.3, torch=2.14.0+cpu, transformers=5.17.0 |
| Nox | decision2 / vllm-sr/Decision-2.0-Nox-4B | ae269ecf34a0b3a89026bc1afd9c995279212fad / — | cpu/float32/2 | 4096/22528/60 | python=3.12.3, torch=2.14.0+cpu, transformers=5.17.0 |
| Liquid3 | small_model / LiquidAI/d1-3B | 051bcc464b01b9f92942b364d9586b0ef5912432 / — | cpu/float32/2 | 4096/18432/60 | python=3.12.3, torch=2.14.0+cpu, transformers=5.17.0 |

## Troncature observée, base

Vrai / faux / inconnu sur tous les appels ; le compteur Laya indique état tronqué positif / zéro / inconnu.

| Modèle | État | Options | Préfixe Noma | Usage natif | État Laya réduit |
|---|---:|---:|---:|---:|---:|
| Vela4 | 0/132/0 | 0/132/0 | 0/0/132 | 0/0/132 | 0/0/132 |
| Nox | 0/132/0 | 0/132/0 | 0/0/132 | 0/0/132 | 0/0/132 |
| Liquid3 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 | 0/0/132 |

## Observation Mastra

Accord avec propositions d'agent ; références pending_human, aucun score sémantique final.

| Modèle | Accord / valides / total | Statuts | Médiane / p95 adaptateur ok (ms) | RSS max observé (MiB) |
|---|---:|---|---:|---:|
| Vela4 | 18/24/24 | 24/0/0/0/0/0 | 9587.6 / 10725.1 | 18382.0 (24/24 rapportés) |
| Nox | 18/24/24 | 24/0/0/0/0/0 | 7559.9 / 8371.8 | 21117.4 (24/24 rapportés) |
| Liquid3 | 16/24/24 | 24/0/0/0/0/0 | 8996.5 / 12825.3 | 18227.9 (24/24 rapportés) |

## Mastra par action proposée

Accords / décisions valides / total. Une proposition en attente de revue humaine ne vaut pas une référence validée.

| Action | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| search | 8/8/8 | 8/8/8 | 6/8/8 |
| stats | 8/8/8 | 8/8/8 | 8/8/8 |
| fallback | 2/8/8 | 2/8/8 | 2/8/8 |

## Mastra par action proposée et langue

Accords / décisions valides / total.

| Action / langue | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| search / fr | 4/4/4 | 4/4/4 | 3/4/4 |
| search / en | 4/4/4 | 4/4/4 | 3/4/4 |
| stats / fr | 4/4/4 | 4/4/4 | 4/4/4 |
| stats / en | 4/4/4 | 4/4/4 | 4/4/4 |
| fallback / fr | 1/4/4 | 1/4/4 | 1/4/4 |
| fallback / en | 1/4/4 | 1/4/4 | 1/4/4 |

## Mastra : action proposée → action prédite

| Attendu → prédit | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| fallback → fallback | 2 | 2 | 2 |
| fallback → search | 3 | 3 | 4 |
| fallback → stats | 3 | 3 | 2 |
| search → search | 8 | 8 | 6 |
| search → stats | 0 | 0 | 2 |
| stats → stats | 8 | 8 | 8 |

## Mastra : action proposée → prédite FR

| Attendu → prédit | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| fallback → fallback | 1 | 1 | 1 |
| fallback → search | 1 | 1 | 2 |
| fallback → stats | 2 | 2 | 1 |
| search → search | 4 | 4 | 3 |
| search → stats | 0 | 0 | 1 |
| stats → stats | 4 | 4 | 4 |

## Mastra : action proposée → prédite EN

| Attendu → prédit | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| fallback → fallback | 1 | 1 | 1 |
| fallback → search | 2 | 2 | 2 |
| fallback → stats | 1 | 1 | 1 |
| search → search | 4 | 4 | 3 |
| search → stats | 0 | 0 | 1 |
| stats → stats | 4 | 4 | 4 |

## Mastra par langue et split

Accords / décisions valides / total.

| Groupe | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| by_language / en | 9/12/12 | 9/12/12 | 8/12/12 |
| by_language / fr | 9/12/12 | 9/12/12 | 8/12/12 |
| by_split / calibration | 4/6/6 | 4/6/6 | 4/6/6 |
| by_split / test | 14/18/18 | 14/18/18 | 12/18/18 |

## Temps Mastra ok (ms)

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| adapter_ms | 8568.2 / 9587.6 / 10725.1 / 10939.4 (24) | 6572.1 / 7559.9 / 8371.8 / 8723.6 (24) | 5814.1 / 8996.5 / 12825.3 / 13344.0 (24) |
| decision_ms | 8562.0 / 9581.0 / 10718.8 / 10933.2 (24) | 6565.7 / 7553.6 / 8365.6 / 8717.4 (24) | 5810.4 / 8992.9 / 12821.9 / 13340.2 (24) |
| http_ms | — (0) | — (0) | — (0) |
| inference_ms | 8561.2 / 9579.8 / 10717.6 / 10929.4 (24) | 6564.5 / 7552.4 / 8364.3 / 8716.1 (24) | 5809.5 / 8992.0 / 12820.9 / 13339.1 (24) |

## Phases et ressources Mastra

Initialisation, premier appel, puis médiane / p95 des appels ok suivants ; mémoire RSS observée dans le worker et couverture sur tous les appels.

| Modèle | Init ms | Premier appel ms (statut) | Après premier ok ms (n) | RSS worker max MiB (n/total) | RSS chargement MiB |
|---|---:|---|---:|---:|---:|
| Vela4 | 30783.8 | 10939.4 (ok) | 9587.5 / 10324.7 (23) | 18382.0 (24/24) | 18382.0 |
| Nox | 27322.5 | 8306.3 (ok) | 7520.7 / 8371.8 (23) | 21117.4 (24/24) | 21056.3 |
| Liquid3 | 14483.5 | 8266.1 (ok) | 8998.2 / 12825.3 (23) | 18227.9 (24/24) | 18227.9 |

## Temps Mastra par statut (ms)

Médiane / p95 (n) ; réponses ok uniquement.

| Statut / mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| ok / adapter_ms | 9587.6 / 10725.1 (24) | 7559.9 / 8371.8 (24) | 8996.5 / 12825.3 (24) |
| ok / inference_ms | 9579.8 / 10717.6 (24) | 7552.4 / 8364.3 (24) | 8992.0 / 12820.9 (24) |
| ok / decision_ms | 9581.0 / 10718.8 (24) | 7553.6 / 8365.6 (24) | 8992.9 / 12821.9 (24) |
| ok / http_ms | — (0) | — (0) | — (0) |

## Tokens natifs Mastra

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| encoded_tokens | 230.0 / 257.0 / 282.0 / 294.0 (24) | 190.0 / 217.0 / 242.0 / 254.0 (24) | — (0) |
| full_input_tokens | — (0) | — (0) | 134.0 / 164.5 / 193.0 / 204.0 (24) |
| max_sequence_tokens | 230.0 / 257.0 / 282.0 / 294.0 (24) | 190.0 / 217.0 / 242.0 / 254.0 (24) | 134.0 / 164.5 / 193.0 / 204.0 (24) |
| padded_batch_tokens | — (0) | — (0) | — (0) |
| padded_tokens | — (0) | — (0) | — (0) |
| sum_sequence_tokens | 230.0 / 257.0 / 282.0 / 294.0 (24) | 190.0 / 217.0 / 242.0 / 254.0 (24) | 134.0 / 164.5 / 193.0 / 204.0 (24) |

## Tokens déclarés par le fournisseur, Mastra

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| input_tokens | — (0) | — (0) | — (0) |
| output_tokens | — (0) | — (0) | — (0) |

## Tokens natifs Mastra par langue

Tokens natifs plus longue séquence native : médiane / p95 (n mesuré).

| Groupe | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| en | 237.0 / 254.0 (12) | 197.0 / 214.0 (12) | 142.0 / 159.0 (12) |
| fr | 271.0 / 294.0 (12) | 231.0 / 254.0 (12) | 182.0 / 204.0 (12) |

## Tokens fournisseur Mastra par langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| en / input_tokens | — (0) | — (0) | — (0) |
| en / output_tokens | — (0) | — (0) | — (0) |
| fr / input_tokens | — (0) | — (0) | — (0) |
| fr / output_tokens | — (0) | — (0) | — (0) |

## Longueur commune des entrées Mastra

Somme des caractères Unicode ou mots séparés par espace dans le contexte, la question et les descriptions d'options visibles par tous ; exclut les identifiants et la sérialisation.

| Mesure | Vela4 | Nox | Liquid3 |
|---|---:|---:|---:|
| characters | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) | 585.0 / 658.5 / 724.0 / 781.0 (24) |
| words | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) | 91.0 / 103.0 / 117.0 / 125.0 (24) |

## Troncature observée, Mastra

Vrai / faux / inconnu sur tous les appels ; le compteur Laya indique état tronqué positif / zéro / inconnu.

| Modèle | État | Options | Préfixe Noma | Usage natif | État Laya réduit |
|---|---:|---:|---:|---:|---:|
| Vela4 | 0/24/0 | 0/24/0 | 0/0/24 | 0/0/24 | 0/0/24 |
| Nox | 0/24/0 | 0/24/0 | 0/0/24 | 0/0/24 | 0/0/24 |
| Liquid3 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 |

## Cohérence Mastra FR/EN

| Modèle | Paires valides / total | Même action |
|---|---:|---:|
| Vela4 | 12/12 | 9/12 |
| Nox | 12/12 | 11/12 |
| Liquid3 | 12/12 | 12/12 |

## Provenance et limites Mastra

Champs explicitement autorisés depuis les profils et les archives ; empreintes complètes dans analysis.json.

| Modèle | Adaptateur / modèle | Révision modèle / source | Device / dtype / threads | Limite entrée / RSS / timeout | Runtimes sélectionnés |
|---|---|---|---|---|---|
| Vela4 | vela2 / vllm-sr/Vela-2.0-4B | d692394127f6f87fc581d8634c9558fe4776efce / — | cpu/float32/2 | 4096/22528/60 | python=3.12.3, torch=2.14.0+cpu, transformers=5.17.0 |
| Nox | decision2 / vllm-sr/Decision-2.0-Nox-4B | ae269ecf34a0b3a89026bc1afd9c995279212fad / — | cpu/float32/2 | 4096/22528/60 | python=3.12.3, torch=2.14.0+cpu, transformers=5.17.0 |
| Liquid3 | small_model / LiquidAI/d1-3B | 051bcc464b01b9f92942b364d9586b0ef5912432 / — | cpu/float32/2 | 4096/18432/60 | python=3.12.3, torch=2.14.0+cpu, transformers=5.17.0 |

Sources, révisions et empreintes : voir analysis.json. Aucune sortie de cas ni contexte privé publié.
