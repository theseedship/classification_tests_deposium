# Comparaison des modèles de choix de contexte

Cas corrects / scorés / total ; les erreurs et absences restent dans le total.
Références agent à revoir humainement ; mesures exploratoires sur modèles isolés, pas parcours produit.

## Classement des bases

| Modèle | Corrects / scorés / total | Statuts (ok, unsupported, missing, error, timeout, abstain) | Médiane / p95 adaptateur ok (ms) | Premier appel (ms) | RSS max observé (MiB) |
|---|---:|---|---:|---:|---:|
| D3liteMacos | 94/132/132 | 132/0/0/0/0/0 | 3195.5 / 3887.9 (132) | 3442.6 | 1591.9 (132/132 rapportés) |

Le temps adaptateur exclut l'initialisation ; premier appel distingué. P95 descriptif par rang le plus proche.

## Domaines

| Groupe | D3liteMacos |
|---|---|
| chemistry | 16/28/28 |
| documentary | 63/76/76 |
| mathematics | 15/28/28 |

## Langues

| Groupe | D3liteMacos |
|---|---|
| en | 49/66/66 |
| fr | 45/66/66 |

## Domaines × langues

| Groupe | D3liteMacos |
|---|---|
| chemistry / en | 8/14/14 |
| chemistry / fr | 8/14/14 |
| documentary / en | 33/38/38 |
| documentary / fr | 30/38/38 |
| mathematics / en | 8/14/14 |
| mathematics / fr | 7/14/14 |

## Domaines × split

| Groupe | D3liteMacos |
|---|---|
| chemistry / calibration | 2/8/8 |
| chemistry / test | 10/14/14 |
| chemistry / train | 4/6/6 |
| documentary / calibration | 14/14/14 |
| documentary / test | 33/38/38 |
| documentary / train | 16/24/24 |
| mathematics / calibration | 6/8/8 |
| mathematics / test | 6/14/14 |
| mathematics / train | 3/6/6 |

## Difficulté

| Groupe | D3liteMacos |
|---|---|
| D1 | 32/40/40 |
| D2 | 31/40/40 |
| D3 | 31/52/52 |

## Split

| Groupe | D3liteMacos |
|---|---|
| calibration | 22/30/30 |
| test | 49/66/66 |
| train | 23/36/36 |

## Types de tâche, tous domaines

| Groupe | D3liteMacos |
|---|---|
| aliquot-and-mix | 0/2/2 |
| ambiguous-selection | 1/2/2 |
| atoms-and-charge | 2/2/2 |
| cancel-keep-domain | 0/2/2 |
| catalog-active-inventory | 2/2/2 |
| catalog-catalog-not-source-count | 2/2/2 |
| catalog-corrected-request | 1/2/2 |
| catalog-count-and-names | 2/2/2 |
| catalog-distinct-identities | 2/2/2 |
| catalog-metadata-owners | 2/2/2 |
| catalog-metadata-table-language | 2/2/2 |
| catalog-negative-summary | 2/2/2 |
| catalog-quoted-summary-command | 2/2/2 |
| catalog-scope-after-interlude | 2/2/2 |
| catalog-selected-titles | 2/2/2 |
| catalog-selection-reuse | 0/2/2 |
| chain-derivative | 2/2/2 |
| combustion-balance | 0/2/2 |
| conditional-probability | 0/2/2 |
| conserved-dilution | 2/2/2 |
| extraneous-equation-root | 0/2/2 |
| formula-not-structure | 2/2/2 |
| fraction-addition | 1/2/2 |
| function-types | 2/2/2 |
| group-atom-count | 2/2/2 |
| hydrate-water-fraction | 0/2/2 |
| ionic-neutrality | 2/2/2 |
| limiting-reactant | 1/2/2 |
| matrix-product | 0/2/2 |
| missing-final-volume | 2/2/2 |
| molar-concentration | 2/2/2 |
| nested-complex-count | 1/2/2 |
| polynomial-remainder | 0/2/2 |
| precipitate-mass | 0/2/2 |
| principal-root | 2/2/2 |
| quantity-dimension | 2/2/2 |
| retrieve_answer-content-date | 0/2/2 |
| retrieve_answer-content-exact-clause | 2/2/2 |
| retrieve_answer-content-explanation | 2/2/2 |
| retrieve_answer-content-filtered-list | 2/2/2 |
| retrieve_answer-content-not-summary | 2/2/2 |
| retrieve_answer-content-refutation | 1/2/2 |
| retrieve_answer-content-total-unit | 0/2/2 |
| retrieve_answer-distant-report-reference | 2/2/2 |
| retrieve_answer-followup-cause | 2/2/2 |
| retrieve_answer-quoted-instruction-content | 1/2/2 |
| retrieve_answer-relations-mermaid | 2/2/2 |
| retrieve_answer-stale-summary-check | 1/2/2 |
| square-expansion | 2/2/2 |
| stored_summaries-cached-descriptions | 2/2/2 |
| stored_summaries-do-not-reread | 2/2/2 |
| stored_summaries-existing-per-file | 2/2/2 |
| stored_summaries-inherit-summary-constraint | 2/2/2 |
| stored_summaries-language-followup | 2/2/2 |
| stored_summaries-quotation-not-budget-question | 2/2/2 |
| stored_summaries-remaining-summaries | 2/2/2 |
| stored_summaries-resume-after-content | 2/2/2 |
| stored_summaries-summary-bundle | 2/2/2 |
| stored_summaries-summary-count-title | 0/2/2 |
| stored_summaries-translate-summary-table | 2/2/2 |
| stored_summaries-validated-abstracts | 2/2/2 |
| transpose-chain | 0/2/2 |
| unanchored-language | 2/2/2 |
| underdetermined-linear | 2/2/2 |
| unknown-function-values | 2/2/2 |
| water-balance | 0/2/2 |

## Tâches documentaires

| Groupe | D3liteMacos |
|---|---|
| ambiguous-selection | 1/2/2 |
| catalog-active-inventory | 2/2/2 |
| catalog-catalog-not-source-count | 2/2/2 |
| catalog-corrected-request | 1/2/2 |
| catalog-count-and-names | 2/2/2 |
| catalog-distinct-identities | 2/2/2 |
| catalog-metadata-owners | 2/2/2 |
| catalog-metadata-table-language | 2/2/2 |
| catalog-negative-summary | 2/2/2 |
| catalog-quoted-summary-command | 2/2/2 |
| catalog-scope-after-interlude | 2/2/2 |
| catalog-selected-titles | 2/2/2 |
| catalog-selection-reuse | 0/2/2 |
| retrieve_answer-content-date | 0/2/2 |
| retrieve_answer-content-exact-clause | 2/2/2 |
| retrieve_answer-content-explanation | 2/2/2 |
| retrieve_answer-content-filtered-list | 2/2/2 |
| retrieve_answer-content-not-summary | 2/2/2 |
| retrieve_answer-content-refutation | 1/2/2 |
| retrieve_answer-content-total-unit | 0/2/2 |
| retrieve_answer-distant-report-reference | 2/2/2 |
| retrieve_answer-followup-cause | 2/2/2 |
| retrieve_answer-quoted-instruction-content | 1/2/2 |
| retrieve_answer-relations-mermaid | 2/2/2 |
| retrieve_answer-stale-summary-check | 1/2/2 |
| stored_summaries-cached-descriptions | 2/2/2 |
| stored_summaries-do-not-reread | 2/2/2 |
| stored_summaries-existing-per-file | 2/2/2 |
| stored_summaries-inherit-summary-constraint | 2/2/2 |
| stored_summaries-language-followup | 2/2/2 |
| stored_summaries-quotation-not-budget-question | 2/2/2 |
| stored_summaries-remaining-summaries | 2/2/2 |
| stored_summaries-resume-after-content | 2/2/2 |
| stored_summaries-summary-bundle | 2/2/2 |
| stored_summaries-summary-count-title | 0/2/2 |
| stored_summaries-translate-summary-table | 2/2/2 |
| stored_summaries-validated-abstracts | 2/2/2 |
| unanchored-language | 2/2/2 |

## Temps base (ms)

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3liteMacos |
|---|---:|
| adapter_ms | 2568.7 / 3195.5 / 3887.9 / 4127.6 (132) |
| decision_ms | 2495.4 / 3121.3 / 3805.1 / 4037.4 (132) |
| http_ms | — (0) |
| inference_ms | 2476.4 / 3101.8 / 3782.0 / 4013.9 (132) |

## Phases et ressources base

Initialisation, premier appel, puis médiane / p95 des appels ok suivants ; mémoire RSS observée dans le worker et couverture sur tous les appels.

| Modèle | Init ms | Premier appel ms (statut) | Après premier ok ms (n) | RSS worker max MiB (n/total) | RSS chargement MiB |
|---|---:|---|---:|---:|---:|
| D3liteMacos | 6597.5 | 3442.6 (ok) | 3195.3 / 3887.9 (131) | 1591.9 (132/132) | 717.2 |

## Temps base par statut (ms)

Médiane / p95 (n) ; temps adaptateur inclut les échecs enregistrés.

| Statut / mesure | D3liteMacos |
|---|---:|
| ok / adapter_ms | 3195.5 / 3887.9 (132) |
| ok / inference_ms | 3101.8 / 3782.0 (132) |
| ok / decision_ms | 3121.3 / 3805.1 (132) |
| ok / http_ms | — (0) |

## Tokens natifs base

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3liteMacos |
|---|---:|
| encoded_tokens | 128.0 / 165.0 / 194.0 / 211.0 (132) |
| indecis_max_sequence_tokens | — (0) |
| indecis_sum_tokens | — (0) |
| padded_tokens | — (0) |

## Tokens déclarés par le fournisseur, base

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3liteMacos |
|---|---:|
| input_tokens | — (0) |
| output_tokens | — (0) |

## Tokens natifs base par domaine

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | D3liteMacos |
|---|---:|
| chemistry | 180.5 / 208.0 (28) |
| documentary | 168.0 / 190.0 (76) |
| mathematics | 148.5 / 177.0 (28) |

## Tokens natifs base par langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | D3liteMacos |
|---|---:|
| en | 157.0 / 186.0 (66) |
| fr | 173.5 / 198.0 (66) |

## Tokens natifs base par domaine × langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | D3liteMacos |
|---|---:|
| chemistry / en | 172.5 / 204.0 (14) |
| chemistry / fr | 186.5 / 211.0 (14) |
| documentary / en | 159.5 / 173.0 (38) |
| documentary / fr | 175.5 / 192.0 (38) |
| mathematics / en | 147.0 / 177.0 (14) |
| mathematics / fr | 151.0 / 179.0 (14) |

## Tokens fournisseur base par domaine

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | D3liteMacos |
|---|---:|
| chemistry / input_tokens | — (0) |
| chemistry / output_tokens | — (0) |
| documentary / input_tokens | — (0) |
| documentary / output_tokens | — (0) |
| mathematics / input_tokens | — (0) |
| mathematics / output_tokens | — (0) |

## Tokens fournisseur base par langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | D3liteMacos |
|---|---:|
| en / input_tokens | — (0) |
| en / output_tokens | — (0) |
| fr / input_tokens | — (0) |
| fr / output_tokens | — (0) |

## Tokens fournisseur base par domaine × langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | D3liteMacos |
|---|---:|
| chemistry / en / input_tokens | — (0) |
| chemistry / en / output_tokens | — (0) |
| chemistry / fr / input_tokens | — (0) |
| chemistry / fr / output_tokens | — (0) |
| documentary / en / input_tokens | — (0) |
| documentary / en / output_tokens | — (0) |
| documentary / fr / input_tokens | — (0) |
| documentary / fr / output_tokens | — (0) |
| mathematics / en / input_tokens | — (0) |
| mathematics / en / output_tokens | — (0) |
| mathematics / fr / input_tokens | — (0) |
| mathematics / fr / output_tokens | — (0) |

## Longueur commune des entrées base

Somme des caractères Unicode ou mots séparés par espace dans le contexte, la question et les descriptions d'options visibles par tous ; exclut les identifiants et la sérialisation.

| Mesure | D3liteMacos |
|---|---:|
| characters | 85.0 / 304.0 / 404.0 / 441.0 (132) |
| words | 15.0 / 47.0 / 63.0 / 70.0 (132) |

Tokens natifs : encodage propre à chaque adaptateur ; `indecis_max_sequence_tokens` mesure la plus longue séquence, `indecis_sum_tokens` la somme des séquences. Tokens fournisseur : comptabilité postérieure à la requête, non comparable au tokenizer local. RSS : pics rapportés par worker, sans RAM serveur distant.

## Confusion des actions documentaires sur la base

| Attendu → prédit | D3liteMacos |
|---|---:|
| catalog → catalog | 21 |
| catalog → retrieve_answer | 1 |
| catalog → stored_summaries | 2 |
| insufficient_information → A | 1 |
| insufficient_information → insufficient_information | 3 |
| retrieve_answer → insufficient_information | 6 |
| retrieve_answer → retrieve_answer | 17 |
| retrieve_answer → stored_summaries | 1 |
| stored_summaries → catalog | 2 |
| stored_summaries → stored_summaries | 22 |

## Confusion documentaire base FR

| Attendu → prédit | D3liteMacos |
|---|---:|
| catalog → catalog | 10 |
| catalog → retrieve_answer | 1 |
| catalog → stored_summaries | 1 |
| insufficient_information → A | 1 |
| insufficient_information → insufficient_information | 1 |
| retrieve_answer → insufficient_information | 4 |
| retrieve_answer → retrieve_answer | 8 |
| stored_summaries → catalog | 1 |
| stored_summaries → stored_summaries | 11 |

## Confusion documentaire base EN

| Attendu → prédit | D3liteMacos |
|---|---:|
| catalog → catalog | 11 |
| catalog → stored_summaries | 1 |
| insufficient_information → insufficient_information | 2 |
| retrieve_answer → insufficient_information | 2 |
| retrieve_answer → retrieve_answer | 9 |
| retrieve_answer → stored_summaries | 1 |
| stored_summaries → catalog | 1 |
| stored_summaries → stored_summaries | 11 |

## Cohérence des traductions documentaires FR/EN

| Modèle | Paires scorées / total | Même action | Deux correctes |
|---|---:|---:|---:|
| D3liteMacos | 38/38 | 32/38 | 29/38 |

## Provenance et limites des bases

Champs explicitement autorisés depuis les profils et les archives ; empreintes complètes dans analysis.json.

| Modèle | Adaptateur / modèle | Révision modèle / source | Device / dtype / threads | Limite entrée / RSS / timeout | Runtimes sélectionnés |
|---|---|---|---|---|---|
| D3liteMacos | d3 / vllm-sr/d3-lite | a8d25a91ef75552803f7009d25b7bd435991abd9 / — | cpu/bfloat16+float32(readout)/2 | 4096/6144/60 | python=3.12.16, torch=2.14.0, transformers=5.17.0 |

## Troncature observée, base

Vrai / faux / inconnu sur tous les appels ; le compteur Laya indique état tronqué positif / zéro / inconnu.

| Modèle | État | Options | Préfixe Noma | Usage natif | État Laya réduit |
|---|---:|---:|---:|---:|---:|
| D3liteMacos | 0/132/0 | 0/132/0 | 0/0/132 | 0/0/132 | 0/0/132 |

## Observation Mastra

Accord avec propositions d'agent ; références pending_human, aucun score sémantique final.

| Modèle | Accord / valides / total | Statuts | Médiane / p95 adaptateur ok (ms) | RSS max observé (MiB) |
|---|---:|---|---:|---:|
| D3liteMacos | 19/24/24 | 24/0/0/0/0/0 | 4364.3 / 5095.4 | 1630.5 (24/24 rapportés) |

## Mastra par action proposée

Accords / décisions valides / total. Une proposition en attente de revue humaine ne vaut pas une référence validée.

| Action | D3liteMacos |
|---|---:|
| search | 8/8/8 |
| stats | 8/8/8 |
| fallback | 3/8/8 |

## Mastra par action proposée et langue

Accords / décisions valides / total.

| Action / langue | D3liteMacos |
|---|---:|
| search / fr | 4/4/4 |
| search / en | 4/4/4 |
| stats / fr | 4/4/4 |
| stats / en | 4/4/4 |
| fallback / fr | 1/4/4 |
| fallback / en | 2/4/4 |

## Mastra : action proposée → action prédite

| Attendu → prédit | D3liteMacos |
|---|---:|
| fallback → fallback | 3 |
| fallback → search | 3 |
| fallback → stats | 2 |
| search → search | 8 |
| stats → stats | 8 |

## Mastra : action proposée → prédite FR

| Attendu → prédit | D3liteMacos |
|---|---:|
| fallback → fallback | 1 |
| fallback → search | 3 |
| search → search | 4 |
| stats → stats | 4 |

## Mastra : action proposée → prédite EN

| Attendu → prédit | D3liteMacos |
|---|---:|
| fallback → fallback | 2 |
| fallback → stats | 2 |
| search → search | 4 |
| stats → stats | 4 |

## Mastra par langue et split

Accords / décisions valides / total.

| Groupe | D3liteMacos |
|---|---:|
| by_language / en | 10/12/12 |
| by_language / fr | 9/12/12 |
| by_split / calibration | 4/6/6 |
| by_split / test | 15/18/18 |

## Temps Mastra (ms)

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3liteMacos |
|---|---:|
| adapter_ms | 3719.7 / 4364.3 / 5095.4 / 5566.7 (24) |
| decision_ms | 3649.1 / 4289.0 / 4992.1 / 5472.4 (24) |
| http_ms | — (0) |
| inference_ms | 3628.7 / 4266.4 / 4968.4 / 5447.9 (24) |

## Phases et ressources Mastra

Initialisation, premier appel, puis médiane / p95 des appels ok suivants ; mémoire RSS observée dans le worker et couverture sur tous les appels.

| Modèle | Init ms | Premier appel ms (statut) | Après premier ok ms (n) | RSS worker max MiB (n/total) | RSS chargement MiB |
|---|---:|---|---:|---:|---:|
| D3liteMacos | 6714.2 | 4476.1 (ok) | 4358.2 / 5095.4 (23) | 1630.5 (24/24) | 709.4 |

## Temps Mastra par statut (ms)

Médiane / p95 (n) ; temps adaptateur inclut les échecs enregistrés.

| Statut / mesure | D3liteMacos |
|---|---:|
| ok / adapter_ms | 4364.3 / 5095.4 (24) |
| ok / inference_ms | 4266.4 / 4968.4 (24) |
| ok / decision_ms | 4289.0 / 4992.1 (24) |
| ok / http_ms | — (0) |

## Tokens natifs Mastra

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3liteMacos |
|---|---:|
| encoded_tokens | 201.0 / 227.5 / 252.0 / 264.0 (24) |
| indecis_max_sequence_tokens | — (0) |
| indecis_sum_tokens | — (0) |
| padded_tokens | — (0) |

## Tokens déclarés par le fournisseur, Mastra

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | D3liteMacos |
|---|---:|
| input_tokens | — (0) |
| output_tokens | — (0) |

## Tokens natifs Mastra par langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | D3liteMacos |
|---|---:|
| en | 208.0 / 225.0 (12) |
| fr | 241.0 / 264.0 (12) |

## Tokens fournisseur Mastra par langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | D3liteMacos |
|---|---:|
| en / input_tokens | — (0) |
| en / output_tokens | — (0) |
| fr / input_tokens | — (0) |
| fr / output_tokens | — (0) |

## Longueur commune des entrées Mastra

Somme des caractères Unicode ou mots séparés par espace dans le contexte, la question et les descriptions d'options visibles par tous ; exclut les identifiants et la sérialisation.

| Mesure | D3liteMacos |
|---|---:|
| characters | 585.0 / 658.5 / 724.0 / 781.0 (24) |
| words | 91.0 / 103.0 / 117.0 / 125.0 (24) |

## Troncature observée, Mastra

Vrai / faux / inconnu sur tous les appels ; le compteur Laya indique état tronqué positif / zéro / inconnu.

| Modèle | État | Options | Préfixe Noma | Usage natif | État Laya réduit |
|---|---:|---:|---:|---:|---:|
| D3liteMacos | 0/24/0 | 0/24/0 | 0/0/24 | 0/0/24 | 0/0/24 |

## Cohérence Mastra FR/EN

| Modèle | Paires valides / total | Même action |
|---|---:|---:|
| D3liteMacos | 12/12 | 9/12 |

## Provenance et limites Mastra

Champs explicitement autorisés depuis les profils et les archives ; empreintes complètes dans analysis.json.

| Modèle | Adaptateur / modèle | Révision modèle / source | Device / dtype / threads | Limite entrée / RSS / timeout | Runtimes sélectionnés |
|---|---|---|---|---|---|
| D3liteMacos | d3 / vllm-sr/d3-lite | a8d25a91ef75552803f7009d25b7bd435991abd9 / — | cpu/bfloat16+float32(readout)/2 | 4096/6144/60 | python=3.12.16, torch=2.14.0, transformers=5.17.0 |

Sources, révisions et empreintes : voir analysis.json. Aucune sortie de cas ni contexte privé publié.
