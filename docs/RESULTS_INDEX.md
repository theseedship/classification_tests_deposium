# Résultats consolidés entre postes — 28 octobre 2026

La PR #8, fusionnée dans `main` à `796ba198`, apporte les campagnes CPU/API
et les essais sur les passages. La PR #9 apporte les quatre campagnes natives
Metal. La PR #10 ajoute GLiClass v4 9B sur MPS/BF16 ; le lot du 28 octobre ajoute
Vela3-fast, backbone de décision CPU FP32. Cet index relie ces
résultats en conservant leurs machines, précisions et protocoles respectifs.
Il ne crée ni nouvelle inférence ni classement de latence entre matériels.

## Décisions courtes : modèles isolés

Ces quatre panneaux utilisent les 132 bases FR/EN (66 familles) et les
24 propositions Mastra (12 familles), avec références encore proposées par
agents. Mastra conserve zéro cas sémantiquement qualifié ; aucun outil exécuté.

| Panneau | Exécutions et matériel | Synthèse | Preuves publiques |
| --- | --- | --- | --- |
| Historique CPU/API consolidé | 22 observations, dont Jev distant ; campagnes WSL/CPU, précisions propres à chaque modèle | [Nox, Vela, Liquid et classement complet](LARGER_CPU_RESULTS_20261011.md), [D3 mini/flash](D3_LARGER_CPU_RESULTS.md) | [22 modèles](evidence/model-comparison-larger-cpu-overview-20261011/report.md), [manifeste](evidence/model-comparison-larger-cpu-overview-20261011/manifest.json) |
| Natif Mac / Metal | Eos Q8, Flash Q8/Q4, D3 27B Q4 ; llama.cpp et passerelle locale | [Scores, RAM et pins](NATIVE_DECISION_RESULTS_20261016.md) | [Comparatif](evidence/native-model-comparison-20261016/report.md), [identités](evidence/native-model-comparison-20261016/native-sessions.json) |
| GLiClass Mac / MPS | GLiClass v4 9B BF16 ; pipeline officiel PyTorch | [Résultats et limites](GLICLASS_V4_RESULTS_20261017.md), [reproduction et transfert](GLICLASS_V4_REPRODUCTION.md) | [Comparatif avec les quatre campagnes Metal](evidence/gliclass-model-comparison-20261017/report.md), [provenance MPS](evidence/gliclass-model-comparison-20261017/gliclass-session.json) |
| Vela 3 Fast Mac / CPU | Backbone de décision seul FP32/SDPA officiel ; 57/132 bases, 18/24 accords provisoires, ~3,16 Gio RSS | [Résultats et reproduction](VELA3_FAST_RESULTS_20261028.md), [audit Ultra/Vela 3](DECISION3_VELA3_REVIEW_20261028.md) | [Comparatif](evidence/vela3-fast-20261028/report.md), [identité et sceaux](evidence/vela3-fast-20261028/vela3-fast-session.json) |

Les totaux 22 + 4 + 1 + 1 désignent des observations, **pas 28 modèles distincts**.
Eos et D3 Flash apparaissent sur plusieurs runtimes ; Flash Q8/Q4 sont deux
quantifications. Les agrégats historiques ne sont pas réécrits pour supprimer
ces distinctions. Les sous-tableaux datés « onze modèles » ou « dix-neuf
modèles » restent des instantanés historiques.

Sur Mac, D3 Flash Q8 reste le choix par défaut proposé hors 27B : **124/132**,
72/76 documentaire, environ 9,39 Gio de RSS observé sur les entrées courtes.
Flash Q4 : **122/132**, 6,66 Gio RSS. GLiClass : **117/132**, mais **63/66 test**
contre 61/66 pour Flash Q8 ; son allocation GPU observée est de 16,75 Gio,
distincte du RSS. Le corpus limité et ses références provisoires ne prouvent
pas une avance générale. La même valeur totale sur CPU et Metal ne démontre
pas une identité des prédictions ou une parité numérique.

**D3 mini et Liquid d1-3B sont déjà mesurés sur CPU** : respectivement 119/132
et 101/132. Leurs chemins natifs Mac restent à qualifier. Leur proposer un
premier pilote CPU serait donc une répétition ; l’[inventaire courant](NEXT_CANDIDATES.md)
sépare checkpoint nouveau et runtime encore non exécuté.

## Autres protocoles, conservés séparément

| Évaluation | Résultat observable et limites | Rapports |
| --- | --- | --- |
| Passages et reranking multilingues | Split test : 512 cas, huit familles, quatre rotations ; BGE nDCG@1 0,922, D3-lite 0,701, Jev 1.14 0,840. Pas de gain démontré à remplacer BGE par ces projections de décisions | [BGE/D3](PASSAGE_CPU_RESULTS_20261015.md), [Jev et couverture partielle](PASSAGE_JEV_RESULTS_20261015.md), [rotations](evidence/passage-order-control-20261015/report.md), [corpus](PASSAGE_EVIDENCE_DATASET.md) |
| Grandes longueurs et temps répétés historiques | Campagnes distinctes des nouvelles entrées courtes ; aucun résultat GLiClass long ou temporel répété | [Longueurs](evidence/length-comparison-20261004/report.md), [temps répétés](evidence/timing-comparison-20261004/report.md) |
| Frontières d'intégration RAG | Modèle isolé, proposition après contrôles déterministes et parcours complet restent des niveaux de preuve distincts | [Protocole public](PROTOCOL.md) |

Jev 1.13 historique et Jev 1.14 sur les passages restent distincts. La campagne
Jev 1.14 est incomplète à 522/728 appels : pertinence complète pour le classement,
soutien partiel, réponse possible non mesurée. Aucun nouveau coût API ni outil
applicatif n’est engagé par cette consolidation.

## Ce qui est partagé et ce qui reste local

**Git partage** code, profils relatifs, manifestes SHA, corpus synthétiques,
références versionnées, rapports et JSON agrégés. Une fois la branche publiée,
un autre poste peut les récupérer. GLiClass est fusionné via la PR #10 ;
Vela3-fast est disponible sur la branche publiée de ce nouveau lot avant sa fusion.

**Git ne partage pas** les poids, environnements installés, profils absolus,
sorties brutes, archives scellées, snapshots de sources et journaux sous
`models/` ou `results/`. Un pull n’est pas une sauvegarde ni un transfert de ces
preuves privées. Les archives CPU restent sur le poste qui les a produites ;
les archives Metal et GLiClass restent sur le Mac. Leur présence sur l’autre
poste n’a pas été vérifiée par ce lot.

Lire les agrégats publics et exécuter les tests hors poids ne nécessite pas
ces captures privées. Refaire un rescore ou un audit des sorties brutes les
nécessite ; réexécuter l’inférence demande en plus les actifs et le runtime
épinglés. Les historiques et sceaux initiaux sont conservés, y compris
l’enveloppe GLiClass `completed:false` avant reprise Mastra séparée.

Cette consolidation ne déploie rien sur Railway, ne met pas à jour le gitlink
de la stack et ne publie pas le correctif local voisin de `deposium-inference`.
Ce dernier reste un lot séparé, comme documenté dans le rapport natif.
