# Prochains candidats et rôle des classements publics

**Current complementary campaign plan — 29 October 2026:** the
[English staged plan](CAPABILITY_CAMPAIGN_PLAN.md) selects six known-size
historical class representatives plus GLiClass 9B as a family counterpoint for
the new 192-case capability pack. It records preparation gates, an exact
calibration canary, and separate 132/192 archives. Flash Q8 completed the first
campaign at 192/192 (test 96/96); six candidates remain `not_run`. The cohort
and order are unchanged. The [current priorities](BENCHMARK_PRIORITIES_20261029.md)
add a separate physics baseline; the dated candidate inventory below remains
historical context.

## Actualisation Decision 3 / Vela 3 — 28 octobre 2026

[Audit et catalogue épinglé](DECISION3_VELA3_REVIEW_20261028.md) : aucun Ultra ou
Turbo historique ; les Vela précédemment mesurés étaient de génération 2.
Le premier **Vela3-fast, décisions seules CPU FP32**, est maintenant mesuré :
**57/132 bases, 18/24 accords Mastra provisoires**, environ 3,16 Gio de RSS.
Voir [résultats et limites](VELA3_FAST_RESULTS_20261028.md). Il ne remplace pas
D3 Flash ou l'ancien D3 27B pour les tâches courtes de ce banc.

Priorités de cette nouvelle famille : **Vela3-lite puis mini**, en chargeant
leurs bases D3 exactes (pas `main`) et en préparant des cas/scorers pour les
spans, entités, appuis et routeurs spécialisés. Aucun de ces adaptateurs n'est
qualifié par le test du backbone Fast. Flash puis Turbo viennent après un
préflight de ressources. Fast Vision demande un corpus visuel distinct.

**D3 Ultra et Turbo restent `not_run`.** Ultra BF16 pèse 48,59 Gio avant runtime ;
le Mac disposait d'environ 27,86 Gio estimés à l'ouverture de la revue. Le GPTQ
communautaire ne fournit pas de chargeur Metal établi. Garder le 27B Q4
historique comme témoin ; qualifier séparément une nouvelle révision GGUF D3
ou un futur Ultra réellement compatible. Les anciennes priorités ci-dessous
restent des pistes distinctes de runtime et de génération.


## Complément mesuré — 17 octobre 2026

À la demande de l'utilisateur, **GLiClass v4 9B** a été mesuré séparément :
**117/132 bases, dont 63/66 test, et 20/24 accords Mastra provisoires**.
Voir les [résultats et preuves](GLICLASS_V4_RESULTS_20261017.md). Il reste derrière
D3 Flash Q8 au total, mais le dépasse sur ce petit split test ; D3 27B Q4 reste
devant dans les deux vues. Références en attente de revue, aucune qualification
produit. GLiClass 27B reste non téléchargé et non exécuté ; ses poids BF16
d'environ 54 Go imposeraient une étude de ressources avant tout essai sur 64 Gio.
Ce pilote MPS isolé ne qualifie pas CPU/CUDA et ne lance pas les pistes suivantes.

## Priorités natives après les campagnes Metal — 16 octobre 2026

Raccordement du 17 octobre : les priorités natives sont rapprochées ci-dessous
des mesures CPU importées par la PR #8, sans programmer de nouvelle campagne.

Les [quatre campagnes natives](NATIVE_DECISION_RESULTS_20261016.md) ajoutent
Eos Q8, D3 Flash 9B Q8/Q4 et D3 27B Q4 aux observations historiques.
Le 27B Q4 atteint 128/132 bases et 24/24 accords Mastra provisoires ; références
à revoir, zéro cas Mastra sémantiquement qualifié et aucun parcours produit.
Le 27B Q8 reste non exécuté, faute d'admission avec la réserve mémoire prévue.

La revue des sources officielles du 16 octobre conserve les pistes suivantes.
Les chemins natifs/GGUF ci-dessous restent **non exécutés**. Plusieurs
checkpoints ont déjà été mesurés sur CPU Python/BF16 ou FP32 dans le lot
consolidé par la PR #8 ; ce sont des variantes de runtime à qualifier, pas
des modèles entièrement nouveaux :

| Priorité proposée | Variante | Question à mesurer et voie technique |
| --- | --- | --- |
| 1 | [D3 mini, classe 4B](https://huggingface.co/vllm-sr/d3-mini) | Comparer la voie native au CPU BF16 déjà mesuré : 119/132 bases, 20/24 accords provisoires. [GGUF officiels](https://huggingface.co/ggml-org/vllm-d3-mini-GGUF/tree/main) Q8/Q4 disponibles ; chargement et compatibilité avec notre pin à vérifier par smoke avant campagne |
| 2 | [LiquidAI d1-3B](https://huggingface.co/LiquidAI/d1-3B) | CPU FP32 déjà mesuré : 101/132 bases, 16/24 accords provisoires. Une nouvelle voie Mac/MPS reste à qualifier avec le helper officiel, snapshot isolé et garde de non-troncature ; ne pas répéter ce pilote CPU comme une première mesure. Aucune compatibilité décisionnelle llama.cpp établie ici |
| 3 | [D3 nano, classe 2B](https://huggingface.co/vllm-sr/d3-nano) | Comparer la voie native au CPU BF16 déjà mesuré : 117/132 bases, 18/24 accords provisoires. [GGUF officiel](https://huggingface.co/ggml-org/vllm-d3-nano-GGUF/tree/main) Q8 disponible ; aucun Q4 listé lors de cette revue, qualification locale encore à faire |
| Témoins de génération | [Decision 2 Lux 9B](https://huggingface.co/vllm-sr/Decision-2.0-Lux-9B-GGUF), puis éventuellement [Vega 27B](https://huggingface.co/vllm-sr/Decision-2.0-Vega-27B-GGUF) | Comparer Decision 2 et D3 à taille voisine, avec quantification explicite. Les fiches GGUF demandent la branche Decision 2 ; conserver le runtime séparé déjà prévu. Commencer par Lux, décider de Vega selon l'information obtenue |

Premier petit lot proposé : **D3 mini puis d1-3B**. Nano vient ensuite si la
réduction de mémoire/latence est prioritaire. Sol 2B et Nox 4B de Decision 2
sont déjà mesurés sur CPU : respectivement 93/132 et 103/132 bases,
19/24 et 18/24 accords provisoires. Seules de nouvelles variantes natives
restent à qualifier pour ces modèles. La sélection ne programme aucune campagne ni téléchargement.
Les pins, quantifications et budgets devront être fixés avant les prédictions.

Les variantes anglaise et typée de Laya restent non testées, avec une priorité
moindre pour notre corpus FR/EN ; la [fiche officielle](https://huggingface.co/convaiinnovations/laya)
décrit les limites de spécialisation. CLM 8B et Clef Flash 9B restent des candidats documentés sans mesure
Deposium. Pour Strands Decider 2B, le v19 historique est déjà mesuré ; le
v1-2610 reste un candidat distinct à préparer (voir l’inventaire ci-dessous).
Aucun nouveau poids ni nouvelle inférence pendant cette revue documentaire.

## Inventaire CPU historique — 11 octobre 2026

État actualisé au 11 octobre 2026, conservé avec les résultats CPU. L'ordre de travail et les critères de fin sont dans
la [local-only material, not distributed](PROTOCOL.md). Les lignes suivantes distinguent observations et pistes;
elles ne constituent pas un classement de priorité ni une qualification produit.

[Inventaire des variantes jusqu'à 9B](VARIANTS_UP_TO_9B.md) : quatre variantes
déjà documentées comme non exécutées ou à préparer, Nox déjà mentionné et cinq autres versions repérées
dans les familles mesurées. Lux/Vela « 9B » constituent les prochains points
de comparaison de taille avec D3 flash ; leur CPU FP32 exige un autre budget
que le BF16 de Flash. L’inventaire initial est conservé ; Nox 4B, Vela 4B et Liquid d1-3B
sont maintenant [mesurés sur CPU](LARGER_CPU_RESULTS_20261011.md).

| Situation | Candidat | État et raison |
|---|---|---|
| Mesuré CPU FP32 | `vllm-sr/Decision-2.0-Nox-4B`, `vllm-sr/Vela-2.0-4B` | 103/132 et 106/132 ; chacun 18/24 accords provisoires. [Résultats](LARGER_CPU_RESULTS_20261011.md) |
| À préparer, CPU/FR à mesurer | `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` | Nouveau candidat distinct du v19 historique ; parité CPU/GPU annoncée sur 231 JevBench, pas de preuve Deposium/FR. Adaptateur `216d1cc…`, base `b1485b2…` conservée ; [suite](LARGER_CPU_RESULTS_20261011.md#nettoyage-et-suite) |
| À préparer, FR exploratoire | `muose/Muose-100M-Decision` | Étiqueté anglais, 512 tokens, licence non commerciale ; aucune mesure Deposium pour cette version |
| Mesuré CPU natif BF16 | `vllm-sr/d3-mini`, `vllm-sr/d3-flash` | Mini 119/132, Flash 124/132 ; chacun 20/24 accords provisoires. [Résultats/ressources](D3_LARGER_CPU_RESULTS.md). 26B reporté sans poids téléchargés |
| Mesuré CPU natif BF16 | `vllm-sr/d3-edge`, `vllm-sr/d3-lite`, `vllm-sr/d3-nano` | 74/132, 95/132, 117/132 ; routage 18/24, 19/24, 18/24. [local-only material, not distributed](PROTOCOL.md) |
| Mesuré CPU FP32 | `vllm-sr/Vela-2.0-0.3B`, `vllm-sr/Vela-2.0-0.8B` | 65/132 et 79/132 ; routage 18/24 et 14/24. [Résultats](MODEL_COMPARISON_VELA2_20261011.md). 4B maintenant mesuré dans un lot distinct |
| Export mesuré, branche distincte | `vllm-sr/Decision-2.0-Sol-2B` | 93/132 bases, 19/24 accords provisoires ; [synthèse conservant son export](D3_LARGER_CPU_RESULTS.md) |
| Mesuré | `convaiinnovations/laya-multilingual` | 56/132 bases FR/EN, 10/24 accords Mastra provisoires ; [résultats](LAYA_RESULTS.md). Variantes `laya` anglaise et `laya-typed-decisions` non exécutées |
| Mesuré | `BlackdromeAILabs/noma` | 98/132 bases, 18/24 accords Mastra provisoires ; [local-only material, not distributed](PROTOCOL.md) |
| Mesuré | `vllm-sr/Decision-2.0-Eos-0.8B` | 77/132 bases, 19/24 accords Mastra provisoires ; [local-only material, not distributed](PROTOCOL.md) |
| Mesuré | `vllm-sr/Decision-2.0-Kai-0.6B` | 70/132 bases, 16/24 accords Mastra provisoires ; [local-only material, not distributed](PROTOCOL.md). CPU FP32, plafond local 4k |
| Mesuré | `muose/Muose-50M-Decision` | 41/132 bases, 10/24 accords Mastra provisoires ; [local-only material, not distributed](PROTOCOL.md). Gabarit exploratoire figé, plafond 512 par option, licence non commerciale |
| Mesuré | Julia-1 | 52/132 bases FR/EN ; [résultats](JULIA_RESULTS.md) |
| Mesuré | `fastino/GLiNER2.5-multi-Decide` | Pilote local exécuté sur les 132 bases FR/EN : 59/132; voir [résultats](GLINER_RESULTS.md) |
| Mesuré | Jev `1.13.0` | [Pilote API exécuté](JEV_RESULTS.md) : 123/132 bases, 305/354 variantes scorées; référence mesurée pour la suite |
| Mesuré sans entraînement | Indecis ouvert | [Pilote exécuté](INDECIS_RESULTS.md) : 44/132 bases; la [spécialisation](INDECIS_CANDIDATE.md) reste à préparer avec des références revues |
| À préparer | GLiDE de Fastino | Raisonnement adaptatif via API; à évaluer après préparation de l'accès et du budget |
| À préparer, ressources à fixer | `Contrastive-LM/CLM-v0.1-8B` | Étiqueté anglais ; capacité FR de la tête non démontrée. Têtes contrastives sur Qwen3-8B; encodeur lourd, caches et troncature à contrôler. [Analyse et pilote proposé](CLM_MODERNJEV_CANDIDATES.md), aucune inférence effectuée |
| Mesuré | `MaziyarPanahi/ModernJEV-Decide-Preview` | 42/132 bases, 8/24 accords Mastra provisoires ; [local-only material, not distributed](PROTOCOL.md). Prototype distinct de Jev, helper officiel 4k sans coupe acceptée |
| À préparer | `Qwen/Qwen3-4B` via SemIf | LLM utilisé en un forward sur logits de choix, sans génération; wrapper 4k. [Analyse jevworks](KUMO_QWEN_CLEF_CANDIDATES.md), aucune inférence Deposium |
| À préparer, ressources à fixer | `Cloudflare/clef-flash` | Décisions typées multimodales, Qwen3.5-9B + tête jointe; helper à protéger contre la troncature. [Analyse](KUMO_QWEN_CLEF_CANDIDATES.md), aucun résultat Deposium |
| Piste multimodale, ressources à fixer | `mohit67890/imajev-4b` | Adaptateur Qwen3.5-4B + tête de décisions typées, 0–2 images ; [identités, limites et pilote proposé](IMAJEV_CANDIDATE.md). Aucun poids téléchargé ni résultat Deposium ; anglais annoncé, FR exploratoire |
| Mesuré en texte CPU FP32 | `LiquidAI/d1-3B` | 101/132 bases, 16/24 accords provisoires, RSS bases 17,80 Gio ; [résultats](LARGER_CPU_RESULTS_20261011.md). Images non mesurées |
| Mesuré en texte | `LiquidAI/d1-omni-600M` | 51/132 bases, 16/24 accords Mastra provisoires ; [local-only material, not distributed](PROTOCOL.md). Images/audio non mesurés ; budgets natifs contrôlés |
| Usages à qualifier d'abord | `nvidia/Kumo-Tabular` Small | [T0 : observer et annoter les tâches DuckDB/XLSX](TABULAR_USE_CASE_DISCOVERY.md) avant tout dataset prédictif. [Analyse technique](KUMO_QWEN_CLEF_CANDIDATES.md), aucun besoin prédictif confirmé ni pilote exécuté dans ce lot |

Le [classement complet des 22 modèles](evidence/model-comparison-larger-cpu-overview-20261011/report.md)
présente domaines, langues, mémoire et durées. Le
[rapport détaillé des 18 modèles hors Sol](evidence/model-comparison-d3-larger-20261011/report.md)
ajoute difficulté, splits et croisements ; Sol conserve son export historique. Il conserve les qualifications
historiques et sépare accord Mastra provisoire et qualité des réponses finales.

## GLiNER2.5-multi-Decide

Révision observée : `a35a0cd3b7a0f00f2effc576f454cd48fa98aa5f`.
La [fiche officielle](https://huggingface.co/fastino/GLiNER2.5-multi-Decide)
décrit 287 M paramètres, Apache-2.0, un classifieur multilingue pour décisions
opérationnelles sur CPU/GPU. Son benchmark publié est anglais et ne constitue
pas une mesure de ses autres langues. La fiche ne revendique pas de raisonnement
général.

Le [config épinglé](https://huggingface.co/fastino/GLiNER2.5-multi-Decide/blob/a35a0cd3b7a0f00f2effc576f454cd48fa98aa5f/config.json)
indique `max_len=4096`, encodeur `microsoft/mdeberta-v3-base`, architecture
`boundary`. L'inspection de GLiNER2 2.0.0 montre que ce réglage de mots n'est pas
appliqué automatiquement à `classify_text(max_len=None)`. Le pilote impose un
budget distinct de 4096 sous-tokens totaux avant forward. Ce budget n'est pas
une fenêtre native qualifiée. Ne pas lui attribuer le raisonnement de GLiDE.

Le [wrapper épinglé](GLINER_PILOT.md), le mapping vers le choix sémantique
du banc et le contrôle de non-troncature sont livrés. Le pilote réutilise les
mêmes textes FR/EN et la grille de longueurs de Julia. Élargir ensuite à
DE/ES/IT/PT avec revue des traductions. Mesurer
également la langue des descriptions des choix. Maths/chimie restent une
exploration des limites, séparée de la qualification du routage documentaire.

## Indecis ouvert

Le pilote du banc à la révision `2f1875d` mesure le backbone brut via
`DecideOpen`, sans entraînement : **44/132 bases FR/EN**, dont 32/76 en
documentaire, 2/28 en mathématiques et 10/28 en chimie. Sur les variantes
longues, 81/300 cas scorés sont corrects sur 378 cas au total; les 54 variantes
8k sont `unsupported` au budget natif de 4096 tokens par séquence, avant forward.
Les 24 autres cas non scorés ont une cible de longueur irréalisable.
Le panel temporel répété de 18 bases de calibration mesure une décision médiane
de 25,989 ms et un p95 de 35,389 ms; ce panel ne remplace pas le score des 132 bases.
Voir le [rapport](INDECIS_RESULTS.md) et le [protocole](INDECIS_PILOT.md).

Les comparaisons utilisent les archives historiques Julia, GLiNER et Jev;
ces candidats n'ont pas été rejoués pour ce lot. R3 est réalisé à titre
expérimental. La revue humaine R1 et les familles indépendantes R2 restent à
préparer avant une spécialisation R4. Aucune mesure d'entraînement ou de
fine-tuning n'est disponible ici, ni qualification produit.

## GLiDE

L'[annonce de Fastino](https://fastino.ai/blog/introducing-glide-the-first-thinking-decision-model)
rapporte 64,81 contre 57,91 pour Jev sur Decision Index 0.2.1, dans une exécution
réalisée par Fastino avec le scorer officiel, pas encore publiée au classement.
L'annonce indique une fenêtre partagée de 40k tokens, raisonnement inclus.
Pas de mesure locale de RAM/latence ni de comparaison Deposium disponible.
Prévoir temps client total, tokens d'entrée et de raisonnement, erreurs et coût.

## Complémentarité avec Decision Index

Le [Space communautaire](https://huggingface.co/spaces/multimodalart/jev-decision-index)
sert à présélectionner les candidats. Sa
[méthodologie](https://huggingface.co/spaces/multimodalart/jev-decision-index/blob/main/data/methodology.json)
sépare le scoring du panel temporel de 750 requêtes et 10 échauffements,
sur une RTX PRO 6000 de 96 Go pour les reproductions. Jev est mesuré via HTTPS;
ces temps ne se transposent pas directement à notre CPU ou au parcours Deposium.

Le banc Deposium conserve ses contrats applicatifs, cas métier, domaines, langues,
difficultés et budgets. Générer des annexes est simple; vérifier les références,
le réalisme et l'indépendance des familles reste nécessaire. Les variantes
synthétiques longues ne remplacent pas un corpus de vrais documents annotés.
