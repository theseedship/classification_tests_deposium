# Comparaison des modèles de choix de contexte

Cas corrects / scorés / total ; les erreurs et absences restent dans le total.
Références agent à revoir humainement ; mesures exploratoires sur modèles isolés, pas parcours produit.

## Classement des bases

| Modèle | Corrects / scorés / total | Statuts (ok, unsupported, missing, error, timeout, abstain) | Médiane / p95 adaptateur ok (ms) | Premier appel (ms) | RSS max observé (MiB) |
|---|---:|---|---:|---:|---:|
| Vela03Macos | 65/132/132 | 132/0/0/0/0/0 | 154.0 / 195.8 (132) | 183.4 | 1204.6 (132/132 rapportés) |

Le temps adaptateur exclut l'initialisation ; premier appel distingué. P95 descriptif par rang le plus proche.

## Domaines

| Groupe | Vela03Macos |
|---|---|
| chemistry | 9/28/28 |
| documentary | 52/76/76 |
| mathematics | 4/28/28 |

## Langues

| Groupe | Vela03Macos |
|---|---|
| en | 32/66/66 |
| fr | 33/66/66 |

## Domaines × langues

| Groupe | Vela03Macos |
|---|---|
| chemistry / en | 4/14/14 |
| chemistry / fr | 5/14/14 |
| documentary / en | 26/38/38 |
| documentary / fr | 26/38/38 |
| mathematics / en | 2/14/14 |
| mathematics / fr | 2/14/14 |

## Domaines × split

| Groupe | Vela03Macos |
|---|---|
| chemistry / calibration | 3/8/8 |
| chemistry / test | 4/14/14 |
| chemistry / train | 2/6/6 |
| documentary / calibration | 8/14/14 |
| documentary / test | 29/38/38 |
| documentary / train | 15/24/24 |
| mathematics / calibration | 0/8/8 |
| mathematics / test | 4/14/14 |
| mathematics / train | 0/6/6 |

## Difficulté

| Groupe | Vela03Macos |
|---|---|
| D1 | 21/40/40 |
| D2 | 19/40/40 |
| D3 | 25/52/52 |

## Split

| Groupe | Vela03Macos |
|---|---|
| calibration | 11/30/30 |
| test | 37/66/66 |
| train | 17/36/36 |

## Types de tâche, tous domaines

| Groupe | Vela03Macos |
|---|---|
| aliquot-and-mix | 2/2/2 |
| ambiguous-selection | 0/2/2 |
| atoms-and-charge | 0/2/2 |
| cancel-keep-domain | 0/2/2 |
| catalog-active-inventory | 2/2/2 |
| catalog-catalog-not-source-count | 2/2/2 |
| catalog-corrected-request | 1/2/2 |
| catalog-count-and-names | 0/2/2 |
| catalog-distinct-identities | 2/2/2 |
| catalog-metadata-owners | 2/2/2 |
| catalog-metadata-table-language | 2/2/2 |
| catalog-negative-summary | 0/2/2 |
| catalog-quoted-summary-command | 0/2/2 |
| catalog-scope-after-interlude | 1/2/2 |
| catalog-selected-titles | 1/2/2 |
| catalog-selection-reuse | 0/2/2 |
| chain-derivative | 0/2/2 |
| combustion-balance | 0/2/2 |
| conditional-probability | 0/2/2 |
| conserved-dilution | 2/2/2 |
| extraneous-equation-root | 0/2/2 |
| formula-not-structure | 0/2/2 |
| fraction-addition | 0/2/2 |
| function-types | 0/2/2 |
| group-atom-count | 0/2/2 |
| hydrate-water-fraction | 2/2/2 |
| ionic-neutrality | 0/2/2 |
| limiting-reactant | 2/2/2 |
| matrix-product | 0/2/2 |
| missing-final-volume | 0/2/2 |
| molar-concentration | 0/2/2 |
| nested-complex-count | 0/2/2 |
| polynomial-remainder | 0/2/2 |
| precipitate-mass | 0/2/2 |
| principal-root | 0/2/2 |
| quantity-dimension | 2/2/2 |
| retrieve_answer-content-date | 0/2/2 |
| retrieve_answer-content-exact-clause | 2/2/2 |
| retrieve_answer-content-explanation | 2/2/2 |
| retrieve_answer-content-filtered-list | 1/2/2 |
| retrieve_answer-content-not-summary | 0/2/2 |
| retrieve_answer-content-refutation | 2/2/2 |
| retrieve_answer-content-total-unit | 2/2/2 |
| retrieve_answer-distant-report-reference | 2/2/2 |
| retrieve_answer-followup-cause | 1/2/2 |
| retrieve_answer-quoted-instruction-content | 1/2/2 |
| retrieve_answer-relations-mermaid | 2/2/2 |
| retrieve_answer-stale-summary-check | 2/2/2 |
| square-expansion | 0/2/2 |
| stored_summaries-cached-descriptions | 2/2/2 |
| stored_summaries-do-not-reread | 2/2/2 |
| stored_summaries-existing-per-file | 1/2/2 |
| stored_summaries-inherit-summary-constraint | 0/2/2 |
| stored_summaries-language-followup | 2/2/2 |
| stored_summaries-quotation-not-budget-question | 2/2/2 |
| stored_summaries-remaining-summaries | 2/2/2 |
| stored_summaries-resume-after-content | 2/2/2 |
| stored_summaries-summary-bundle | 2/2/2 |
| stored_summaries-summary-count-title | 2/2/2 |
| stored_summaries-translate-summary-table | 2/2/2 |
| stored_summaries-validated-abstracts | 2/2/2 |
| transpose-chain | 0/2/2 |
| unanchored-language | 1/2/2 |
| underdetermined-linear | 0/2/2 |
| unknown-function-values | 2/2/2 |
| water-balance | 1/2/2 |

## Tâches documentaires

| Groupe | Vela03Macos |
|---|---|
| ambiguous-selection | 0/2/2 |
| catalog-active-inventory | 2/2/2 |
| catalog-catalog-not-source-count | 2/2/2 |
| catalog-corrected-request | 1/2/2 |
| catalog-count-and-names | 0/2/2 |
| catalog-distinct-identities | 2/2/2 |
| catalog-metadata-owners | 2/2/2 |
| catalog-metadata-table-language | 2/2/2 |
| catalog-negative-summary | 0/2/2 |
| catalog-quoted-summary-command | 0/2/2 |
| catalog-scope-after-interlude | 1/2/2 |
| catalog-selected-titles | 1/2/2 |
| catalog-selection-reuse | 0/2/2 |
| retrieve_answer-content-date | 0/2/2 |
| retrieve_answer-content-exact-clause | 2/2/2 |
| retrieve_answer-content-explanation | 2/2/2 |
| retrieve_answer-content-filtered-list | 1/2/2 |
| retrieve_answer-content-not-summary | 0/2/2 |
| retrieve_answer-content-refutation | 2/2/2 |
| retrieve_answer-content-total-unit | 2/2/2 |
| retrieve_answer-distant-report-reference | 2/2/2 |
| retrieve_answer-followup-cause | 1/2/2 |
| retrieve_answer-quoted-instruction-content | 1/2/2 |
| retrieve_answer-relations-mermaid | 2/2/2 |
| retrieve_answer-stale-summary-check | 2/2/2 |
| stored_summaries-cached-descriptions | 2/2/2 |
| stored_summaries-do-not-reread | 2/2/2 |
| stored_summaries-existing-per-file | 1/2/2 |
| stored_summaries-inherit-summary-constraint | 0/2/2 |
| stored_summaries-language-followup | 2/2/2 |
| stored_summaries-quotation-not-budget-question | 2/2/2 |
| stored_summaries-remaining-summaries | 2/2/2 |
| stored_summaries-resume-after-content | 2/2/2 |
| stored_summaries-summary-bundle | 2/2/2 |
| stored_summaries-summary-count-title | 2/2/2 |
| stored_summaries-translate-summary-table | 2/2/2 |
| stored_summaries-validated-abstracts | 2/2/2 |
| unanchored-language | 1/2/2 |

## Temps base (ms)

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Vela03Macos |
|---|---:|
| adapter_ms | 135.4 / 154.0 / 195.8 / 203.8 (132) |
| decision_ms | 51.5 / 61.8 / 79.1 / 88.5 (132) |
| http_ms | — (0) |
| inference_ms | 29.1 / 37.0 / 52.1 / 61.2 (132) |

## Phases et ressources base

Initialisation, premier appel, puis médiane / p95 des appels ok suivants ; mémoire RSS observée dans le worker et couverture sur tous les appels.

| Modèle | Init ms | Premier appel ms (statut) | Après premier ok ms (n) | RSS worker max MiB (n/total) | RSS chargement MiB |
|---|---:|---|---:|---:|---:|
| Vela03Macos | 5922.9 | 183.4 (ok) | 153.9 / 195.8 (131) | 1204.6 (132/132) | 1119.4 |

## Temps base par statut (ms)

Médiane / p95 (n) ; temps adaptateur inclut les échecs enregistrés.

| Statut / mesure | Vela03Macos |
|---|---:|
| ok / adapter_ms | 154.0 / 195.8 (132) |
| ok / inference_ms | 37.0 / 52.1 (132) |
| ok / decision_ms | 61.8 / 79.1 (132) |
| ok / http_ms | — (0) |

## Tokens natifs base

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Vela03Macos |
|---|---:|
| encoded_tokens | 56.0 / 89.0 / 122.0 / 134.0 (132) |
| indecis_max_sequence_tokens | — (0) |
| indecis_sum_tokens | — (0) |
| padded_tokens | — (0) |

## Tokens déclarés par le fournisseur, base

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Vela03Macos |
|---|---:|
| input_tokens | — (0) |
| output_tokens | — (0) |

## Tokens natifs base par domaine

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | Vela03Macos |
|---|---:|
| chemistry | 109.0 / 133.0 (28) |
| documentary | 92.0 / 112.0 (76) |
| mathematics | 74.0 / 114.0 (28) |

## Tokens natifs base par langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | Vela03Macos |
|---|---:|
| en | 83.5 / 114.0 (66) |
| fr | 97.0 / 122.0 (66) |

## Tokens natifs base par domaine × langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | Vela03Macos |
|---|---:|
| chemistry / en | 99.0 / 128.0 (14) |
| chemistry / fr | 112.5 / 134.0 (14) |
| documentary / en | 84.5 / 99.0 (38) |
| documentary / fr | 98.0 / 116.0 (38) |
| mathematics / en | 72.5 / 114.0 (14) |
| mathematics / fr | 76.5 / 116.0 (14) |

## Tokens fournisseur base par domaine

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | Vela03Macos |
|---|---:|
| chemistry / input_tokens | — (0) |
| chemistry / output_tokens | — (0) |
| documentary / input_tokens | — (0) |
| documentary / output_tokens | — (0) |
| mathematics / input_tokens | — (0) |
| mathematics / output_tokens | — (0) |

## Tokens fournisseur base par langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | Vela03Macos |
|---|---:|
| en / input_tokens | — (0) |
| en / output_tokens | — (0) |
| fr / input_tokens | — (0) |
| fr / output_tokens | — (0) |

## Tokens fournisseur base par domaine × langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | Vela03Macos |
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

| Mesure | Vela03Macos |
|---|---:|
| characters | 85.0 / 304.0 / 404.0 / 441.0 (132) |
| words | 15.0 / 47.0 / 63.0 / 70.0 (132) |

Tokens natifs : encodage propre à chaque adaptateur ; `indecis_max_sequence_tokens` mesure la plus longue séquence, `indecis_sum_tokens` la somme des séquences. Tokens fournisseur : comptabilité postérieure à la requête, non comparable au tokenizer local. RSS : pics rapportés par worker, sans RAM serveur distant.

## Confusion des actions documentaires sur la base

| Attendu → prédit | Vela03Macos |
|---|---:|
| catalog → catalog | 13 |
| catalog → retrieve_answer | 8 |
| catalog → stored_summaries | 3 |
| insufficient_information → A_and_B | 2 |
| insufficient_information → insufficient_information | 1 |
| insufficient_information → retrieve_answer | 1 |
| retrieve_answer → catalog | 2 |
| retrieve_answer → insufficient_information | 3 |
| retrieve_answer → retrieve_answer | 17 |
| retrieve_answer → stored_summaries | 2 |
| stored_summaries → catalog | 1 |
| stored_summaries → retrieve_answer | 2 |
| stored_summaries → stored_summaries | 21 |

## Confusion documentaire base FR

| Attendu → prédit | Vela03Macos |
|---|---:|
| catalog → catalog | 6 |
| catalog → retrieve_answer | 3 |
| catalog → stored_summaries | 3 |
| insufficient_information → A_and_B | 1 |
| insufficient_information → retrieve_answer | 1 |
| retrieve_answer → catalog | 1 |
| retrieve_answer → retrieve_answer | 10 |
| retrieve_answer → stored_summaries | 1 |
| stored_summaries → catalog | 1 |
| stored_summaries → retrieve_answer | 1 |
| stored_summaries → stored_summaries | 10 |

## Confusion documentaire base EN

| Attendu → prédit | Vela03Macos |
|---|---:|
| catalog → catalog | 7 |
| catalog → retrieve_answer | 5 |
| insufficient_information → A_and_B | 1 |
| insufficient_information → insufficient_information | 1 |
| retrieve_answer → catalog | 1 |
| retrieve_answer → insufficient_information | 3 |
| retrieve_answer → retrieve_answer | 7 |
| retrieve_answer → stored_summaries | 1 |
| stored_summaries → retrieve_answer | 1 |
| stored_summaries → stored_summaries | 11 |

## Cohérence des traductions documentaires FR/EN

| Modèle | Paires scorées / total | Même action | Deux correctes |
|---|---:|---:|---:|
| Vela03Macos | 38/38 | 27/38 | 22/38 |

## Provenance et limites des bases

Champs explicitement autorisés depuis les profils et les archives ; empreintes complètes dans analysis.json.

| Modèle | Adaptateur / modèle | Révision modèle / source | Device / dtype / threads | Limite entrée / RSS / timeout | Runtimes sélectionnés |
|---|---|---|---|---|---|
| Vela03Macos | vela2 / vllm-sr/Vela-2.0-0.3B | d6f03aa9baca4f9017fa8f8e9c2764d3bed3f409 / — | cpu/float32/2 | 4096/4096/30 | python=3.12.16, torch=2.14.0, transformers=5.17.0 |

## Troncature observée, base

Vrai / faux / inconnu sur tous les appels ; le compteur Laya indique état tronqué positif / zéro / inconnu.

| Modèle | État | Options | Préfixe Noma | Usage natif | État Laya réduit |
|---|---:|---:|---:|---:|---:|
| Vela03Macos | 0/132/0 | 0/132/0 | 0/0/132 | 0/0/132 | 0/0/132 |

## Observation Mastra

Accord avec propositions d'agent ; références pending_human, aucun score sémantique final.

| Modèle | Accord / valides / total | Statuts | Médiane / p95 adaptateur ok (ms) | RSS max observé (MiB) |
|---|---:|---|---:|---:|
| Vela03Macos | 18/24/24 | 24/0/0/0/0/0 | 155.9 / 183.2 | 1211.8 (24/24 rapportés) |

## Mastra par action proposée

Accords / décisions valides / total. Une proposition en attente de revue humaine ne vaut pas une référence validée.

| Action | Vela03Macos |
|---|---:|
| search | 8/8/8 |
| stats | 7/8/8 |
| fallback | 3/8/8 |

## Mastra par action proposée et langue

Accords / décisions valides / total.

| Action / langue | Vela03Macos |
|---|---:|
| search / fr | 4/4/4 |
| search / en | 4/4/4 |
| stats / fr | 4/4/4 |
| stats / en | 3/4/4 |
| fallback / fr | 3/4/4 |
| fallback / en | 0/4/4 |

## Mastra : action proposée → action prédite

| Attendu → prédit | Vela03Macos |
|---|---:|
| fallback → fallback | 3 |
| fallback → search | 5 |
| search → search | 8 |
| stats → search | 1 |
| stats → stats | 7 |

## Mastra : action proposée → prédite FR

| Attendu → prédit | Vela03Macos |
|---|---:|
| fallback → fallback | 3 |
| fallback → search | 1 |
| search → search | 4 |
| stats → stats | 4 |

## Mastra : action proposée → prédite EN

| Attendu → prédit | Vela03Macos |
|---|---:|
| fallback → search | 4 |
| search → search | 4 |
| stats → search | 1 |
| stats → stats | 3 |

## Mastra par langue et split

Accords / décisions valides / total.

| Groupe | Vela03Macos |
|---|---:|
| by_language / en | 7/12/12 |
| by_language / fr | 11/12/12 |
| by_split / calibration | 5/6/6 |
| by_split / test | 13/18/18 |

## Temps Mastra (ms)

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Vela03Macos |
|---|---:|
| adapter_ms | 143.7 / 155.9 / 183.2 / 184.4 (24) |
| decision_ms | 64.0 / 70.0 / 81.5 / 101.3 (24) |
| http_ms | — (0) |
| inference_ms | 39.4 / 45.9 / 58.1 / 75.5 (24) |

## Phases et ressources Mastra

Initialisation, premier appel, puis médiane / p95 des appels ok suivants ; mémoire RSS observée dans le worker et couverture sur tous les appels.

| Modèle | Init ms | Premier appel ms (statut) | Après premier ok ms (n) | RSS worker max MiB (n/total) | RSS chargement MiB |
|---|---:|---|---:|---:|---:|
| Vela03Macos | 5983.0 | 184.4 (ok) | 155.1 / 182.0 (23) | 1211.8 (24/24) | 1115.4 |

## Temps Mastra par statut (ms)

Médiane / p95 (n) ; temps adaptateur inclut les échecs enregistrés.

| Statut / mesure | Vela03Macos |
|---|---:|
| ok / adapter_ms | 155.9 / 183.2 (24) |
| ok / inference_ms | 45.9 / 58.1 (24) |
| ok / decision_ms | 70.0 / 81.5 (24) |
| ok / http_ms | — (0) |

## Tokens natifs Mastra

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Vela03Macos |
|---|---:|
| encoded_tokens | 127.0 / 154.5 / 180.0 / 190.0 (24) |
| indecis_max_sequence_tokens | — (0) |
| indecis_sum_tokens | — (0) |
| padded_tokens | — (0) |

## Tokens déclarés par le fournisseur, Mastra

Min / médiane / p95 / max (n observé) ; — indique aucune mesure.

| Mesure | Vela03Macos |
|---|---:|
| input_tokens | — (0) |
| output_tokens | — (0) |

## Tokens natifs Mastra par langue

Tokens natifs encodés : médiane / p95 (n mesuré).

| Groupe | Vela03Macos |
|---|---:|
| en | 134.0 / 152.0 (12) |
| fr | 168.0 / 190.0 (12) |

## Tokens fournisseur Mastra par langue

Déclaration du fournisseur après requête ; min / médiane / p95 / max (n observé). Mesure distincte des tokens natifs locaux.

| Groupe / mesure | Vela03Macos |
|---|---:|
| en / input_tokens | — (0) |
| en / output_tokens | — (0) |
| fr / input_tokens | — (0) |
| fr / output_tokens | — (0) |

## Longueur commune des entrées Mastra

Somme des caractères Unicode ou mots séparés par espace dans le contexte, la question et les descriptions d'options visibles par tous ; exclut les identifiants et la sérialisation.

| Mesure | Vela03Macos |
|---|---:|
| characters | 585.0 / 658.5 / 724.0 / 781.0 (24) |
| words | 91.0 / 103.0 / 117.0 / 125.0 (24) |

## Troncature observée, Mastra

Vrai / faux / inconnu sur tous les appels ; le compteur Laya indique état tronqué positif / zéro / inconnu.

| Modèle | État | Options | Préfixe Noma | Usage natif | État Laya réduit |
|---|---:|---:|---:|---:|---:|
| Vela03Macos | 0/24/0 | 0/24/0 | 0/0/24 | 0/0/24 | 0/0/24 |

## Cohérence Mastra FR/EN

| Modèle | Paires valides / total | Même action |
|---|---:|---:|
| Vela03Macos | 12/12 | 8/12 |

## Provenance et limites Mastra

Champs explicitement autorisés depuis les profils et les archives ; empreintes complètes dans analysis.json.

| Modèle | Adaptateur / modèle | Révision modèle / source | Device / dtype / threads | Limite entrée / RSS / timeout | Runtimes sélectionnés |
|---|---|---|---|---|---|
| Vela03Macos | vela2 / vllm-sr/Vela-2.0-0.3B | d6f03aa9baca4f9017fa8f8e9c2764d3bed3f409 / — | cpu/float32/2 | 4096/4096/30 | python=3.12.16, torch=2.14.0, transformers=5.17.0 |

Sources, révisions et empreintes : voir analysis.json. Aucune sortie de cas ni contexte privé publié.
