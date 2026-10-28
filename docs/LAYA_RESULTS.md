# Résultats Laya multilingue — 4 octobre 2026

Le pilote utilise `convaiinnovations/laya-multilingual` (322 M paramètres),
révision `1720e3e3357cfe1e281542e223f8273b0890ca34`, via le SDK officiel
0.3.26 à `2e4d9c87e8b1621deb344eac7de5c7258f32f849`. Le
[local-only material, not distributed](PROTOCOL.md) explique le choix parmi les trois checkpoints,
la préparation du tokenizer, la projection native et les gardes mémoire.
Les variantes anglaise et `typed-decisions` n'ont pas été exécutées.

## Bases FR/EN

**56/132 corrects (42,4 %), 132/132 réponses valides**, sans erreur, timeout,
abstention ni troncature. Les 132 cas représentent 66 familles traduites,
avec des références proposées par agent encore à revoir humainement.
La même version du corpus et du scorer est utilisée pour les sept modèles du
[comparatif détaillé](evidence/model-comparison-20261004/report.md).

| Domaine | FR | EN | Total |
|---|---:|---:|---:|
| Documentaire | 24/38 | 18/38 | 42/76 |
| Mathématiques | 5/14 | 3/14 | 8/28 |
| Chimie | 3/14 | 3/14 | 6/28 |
| Ensemble | 32/66 | 24/66 | 56/132 |

| Difficulté annotée | Corrects |
|---|---:|
| D1 | 17/40 |
| D2 | 13/40 |
| D3 | 26/52 |

| Split gelé | Corrects |
|---|---:|
| Train | 14/36 |
| Calibration | 12/30 |
| Test | 30/66 |

Le score global se place entre GLiNER (59/132) et Julia (52/132).
Laya obtient plus de bonnes décisions documentaires que ces deux modèles
(42 contre 41 et 32), mais seulement 6/28 en chimie. Le meilleur résultat FR
que EN sur ce lot ne qualifie pas toutes les langues annoncées par sa carte.
Les 38 sous-thèmes documentaires restent visibles séparément dans le rapport ;
deux traductions d'un scénario ne constituent pas deux observations indépendantes.
Les difficultés regroupent des tâches différentes : D3 supérieur à D2 ne
démontre pas une meilleure capacité intrinsèque sur les questions difficiles.

## Observation de routage Mastra

**10/24 accords provisoires**, 24/24 choix valides ; FR 5/12, EN 5/12.
Les douze paires traduites produisent toutes la même action. Laya propose
`search` dans 22 cas, `fallback` dans deux, et jamais `stats` :

| Action proposée par la référence | Accords | Action choisie par Laya |
|---|---:|---|
| Recherche | 8/8 | Recherche dans les huit cas |
| Statistiques | 0/8 | Recherche dans les huit cas |
| Repli | 2/8 | Recherche dans six cas, repli dans deux |

Ce biais vers la recherche rend le checkpoint brut peu convaincant pour ce
premier routage. Aucun seuil n'a été réglé après mesure. Les références sont
`pending_human`, **zéro cas sémantiquement qualifié** ; aucun véritable appel
MCPs, enchaînement d'outils ou réponse finale n'est évalué par ces 24 décisions.
Le protocole d'intégration avec les vrais wrappers reste distinct.

## Ressources mesurées

CPU FP32, backend eager, batch 1, deux threads ; un seul worker à la fois.

| Mesure | Bases, 132 appels | Mastra, 24 appels |
|---|---:|---:|
| Médiane adaptateur | 168,9 ms | 267,4 ms |
| P95 adaptateur | 219,7 ms | 375,1 ms |
| Premier appel | 193,7 ms | 405,8 ms |
| Médiane inférence native | 134,1 ms | 229,8 ms |
| Initialisation du worker | 11,19 s | 11,72 s |
| Pic RSS observé | 2 324,9 Mio / 2,27 Gio | 2 323,1 Mio / 2,27 Gio |
| Tokens natifs effectivement encodés | 45–123 | Maximum 182 |

Les temps adaptateur excluent l'initialisation et comprennent le transport et
les contrôles. Un seul passage, sans panel temporel répété : ils décrivent
ces campagnes, pas un SLA. RSS couvre le processus worker et ses bibliothèques,
pas toute la RAM de la stack ni un poids disque. Le checkpoint pèse 643 835 514
octets ; son empreinte mémoire FP32 est différente. Aucune mesure GPU ou de
contexte proche de la limite 1 024 tokens n'a été réalisée.

## Archives et validation

Le code exécuté est figé au commit **`73076927531ee978667f05eb13aea2ec4336b58a`**.
Les archives privées du checkout principal sont conservées séparément :

- `results/context-base-laya-001/` et `results/mastra-read-laya-001/` : campagnes
  complètes scellées, profils, provenance, sorties natives et audits du forward.
- `results/context-base-laya-rescore-001/` : rescore hors inférence, mêmes
  56/132, fichiers de cas et sorties brutes identiques à l'archive initiale.
- `results/context-base-laya-smoke-001/` : deux erreurs d'encodage avant forward
  dues à un mauvais nom d'argument du wrapper, corrigé avant le gel.
- `results/context-base-laya-smoke-002/` : deux contrôles FR/EN valides, séparés
  des dénominateurs des campagnes complètes.
- `results/laya-code-7307692.tar.gz` : archive du code figé, SHA-256
  `b63316c1590a633e597b70cbfe82fe911e755bcec90719d9de38b9508e7f9654`.

L'archive externe du code complète la conservation des preuves ; elle ne
change pas le champ historique `source_archive=not_captured` des manifests.
Poids, SDK local, profils absolus et archives restent hors Git ; les anciennes
qualifications Jev, Eos, Noma, GLiNER, Julia et Indecis sont intactes.

Vérifications locales : clones LF propres à `7307692` puis `6991e85`, sans
poids ni service, **450 tests,
444 réussis et six skips optionnels** ; registre valide (15 composants,
29 contrats). Les schémas des manifests/provenances réels passent. Une seconde
lecture vérifie les sceaux, les 156 projections et forwards, leurs empreintes
et l'absence de pertes de tokens ou de référence dans l'entrée modèle.

L'audit a aussi trouvé un ordre de colonnes non reproductible lors du rechargement
du JSON agrégé. Le correctif `6991e85` impose `base_ranking` au rendu Markdown ;
son test échoue avant correction et passe après. Le rapport a été recalculé
hors inférence, sans toucher aux sorties ou aux scores des modèles.

Prochaine campagne : références humaines et familles indépendantes, puis
longueurs et temps répétés ; une spécialisation éventuelle reste un autre lot.
Le pilote ne justifie aucune activation dans le CLI ou le chat.
