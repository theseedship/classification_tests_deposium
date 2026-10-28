# Choix courts Mastra : première observation Indecis

Le 2 octobre 2026, Indecis ouvert non entraîné produit 24 décisions valides,
dont **11/24 en accord avec les propositions synthétiques**. Il ne choisit
jamais le repli. Ce résultat ne qualifie pas un routeur : les 24 références
attendent une revue humaine, et aucune décision ne déclenche d'outil métier.
Il renseigne le candidat isolé, pas une spécialisation entraînée.

Le [protocole](MASTRA_INDECIS_OBSERVATION_PROTOCOL.md) et le moteur ont été
committés à `fc5de1f` avant toute prédiction ; le runtime reconstruit et la
correction de statut CLI à `8495293` avant la passe effective. Corpus,
descriptions, projection v1 et adaptateur Indecis n'ont pas changé entre les
deux lancements. Aucun téléchargement, entraînement ou appel API.

## Décisions observées

| Proposition du corpus | Accord / cas | Prédictions recherche | Prédictions statistiques | Prédictions repli |
|---|---:|---:|---:|---:|
| Recherche de passages | 5/8 | 5 | 3 | 0 |
| Statistiques du corpus | 6/8 | 2 | 6 | 0 |
| Repli vers le planner | 0/8 | 5 | 3 | 0 |
| Total | **11/24 (45,8 %)** | 12 | 12 | 0 |

Couverture : 24/24 choix dans le pool, 24 forwards réels ; aucune erreur,
abstention technique, réponse manquante, limite de contexte ou timeout.
L'absence de choix `fallback` ne signifie pas que ces demandes sont prises
en charge. Le modèle a sélectionné une lecture pour les huit demandes dont
la proposition était de revenir au planner complet.

| Axe | Accord / décisions valides et cas prévus |
|---|---:|
| Français | 5/12 |
| Anglais | 6/12 |
| Calibration | 4/6 |
| Test | 7/18 |

Dix des douze paires FR/EN obtiennent la même action, y compris lorsque les
deux réponses divergent de la proposition. Les traductions ne constituent
pas 24 scénarios indépendants. Un choix constant d'action ou d'ID donne
arithmétiquement 8/24 ; l'écart observé de trois accords ne démontre pas une
supériorité généralisable sur ce petit corpus.

Les sorties détaillées montrent notamment :

- « Ne compte pas les documents ni les entités. Retrouve seulement les
  passages… » déclenche `stats`, en français comme en anglais.
- La citation « retrouve les passages », suivie d'une demande effective de
  comptage, déclenche `search` dans les deux langues.
- Les deux demandes interdisant recherche et statistiques choisissent quand
  même l'une de ces actions ; la demande de cuisson du riz choisit `search`.
- Les demandes simples d'extraits et de comptage sont reconnues dans les
  deux langues, ainsi que la faute « passges ».

Ces observations orientent la revue des cas négatifs, des citations et du
repli. Elles ne justifient pas de changer les prompts ou les références pour
améliorer ce résultat. Les cas composites et les demandes vagues exigent
particulièrement une convention humaine : le pilote demande une décision
terminale courte, tandis qu'un planner complet peut choisir une première
étape légitime dans un parcours plus long.

## Temps et ressources de cette passe

CPU, deux threads, même worker résident ; aucune chauffe ni répétition.
La durée côté adaptateur comprend contrôles d'intégrité et transport local.
La mesure native « inférence » inclut l'appel `DecideOpen` et ses opérations
de tokenisation, embeddings, comparaison et normalisation.

| Mesure | Effectif | Médiane | p95 descriptif |
|---|---:|---:|---:|
| Appel côté adaptateur, initialisation exclue | 24 | 44,69 ms | 57,00 ms |
| Décision native | 24 | 36,50 ms | 48,38 ms |
| Inférence native | 24 | 36,31 ms | 48,16 ms |
| Adaptateur, après le premier appel | 23 | 44,62 ms | 54,28 ms |

Premier appel : 68,01 ms côté adaptateur. Initialisation : 1 215,81 ms,
dont chargement natif 1 078,57 ms. Phase modèle totale : 2 433,91 ms.
Pic RSS rapporté : **894,88 Mio**, sous la garde 3 072 Mio. Les p95 utilisent
le rang supérieur `ceil(n × 0,95)`, sans intervalle de confiance.

Les séquences de contexte vont de 66 à 117 tokens natifs ; les totaux contexte
plus options de 148 à 211. Ce sont des séquences encodées séparément : leur
somme n'est pas une fenêtre jointe. Aucune troncature observée. Cette passe
ne teste pas encore les prompts longs ni la charge concurrente. Au départ,
12 733,83 Mio de RAM étaient disponibles, mais seulement 3,40 Mio de swap
libres sur 16 Gio : les temps décrivent cet hôte à cet instant.

## Archives, incident et contrôles natifs

`results/mastra-read-indecis-001` reste scellé : initialisation refusée,
24 erreurs mises en cache, zéro forward. Les temps de cette archive ne sont
pas des mesures d'inférence. Le décalage source/manifeste et la reconstruction
hors réseau sont détaillés dans le protocole. La CLI rend désormais un code
d'échec si aucun choix valide n'est obtenu.

`results/mastra-read-indecis-002` est la passe effective, au commit propre
`84952938103e6c8f83b45c177033456490e244ed`. Les deux sceaux et tous leurs
fichiers ont été revérifiés. Les archives locales conservent entrées, profil,
sorties natives, provenance du runtime, préflight de stack et compteurs. La
[preuve compacte versionnée](evidence/mastra-indecis-observation-20261002.json)
contient les empreintes, les mesures et les décisions cas par cas ; les bruts
restent dans `results/`, hors Git. Les 15 composants sont recensés par le
préflight, avec `model_isolated_only` ; aucun n'est exercé par ces prédictions.

En parallèle, `capture-mastra-planner` exerce le vrai `Agent.generate` sur les
sources MCPs `391be12` avec un fournisseur entièrement simulé : **3/3 contrôles**
capturent le corps de requête, le pool natif et les appels ordonnés du premier
tour. Les [local-only material, not distributed](PROTOCOL.md) distinguent bien
les six outils natifs des trois labels du candidat. Un arrêt texte simulé
n'est pas un repli au planner. Aucun temps LLM ni gain de parcours n'est mesuré.
Cette archive de capture n'a pas de sceau global ; ses fichiers sont hachés
dans la preuve compacte dédiée.

## Prochaine étape utile

Faire revoir les douze familles et définir précisément quand la décision
courte suffit, puis annoter des demandes réelles autorisées. Les familles de
cette observation, désormais consultées, restent un diagnostic gelé ; créer
un test indépendant pour une future spécialisation. Un fine-tuning aurait
besoin d'exemples de repli, négations, citations et demandes composites.

Pour mesurer un gain utile, il reste à comparer un LLM sur les mêmes trois
labels et entrées, puis à mesurer le parcours natif complet séparément.
La capture simulée prépare son instrumentation ; elle ne fournit pas cette
baseline. L'intégration reste conditionnée à une politique de repli validée,
aux contrôles déterministes et à une recette sur le service réel.
