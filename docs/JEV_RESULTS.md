# Jev 1.13.0 : résultats du pilote API

Campagnes retenues du 2 octobre 2026, branche `feat/jev-api-pilot`, code gelé à
`c27581b`. [Protocole et amendement sur les arrondis](JEV_PILOT.md).
La version renvoyée est `jev-1.13.0` sur toutes les réponses acceptées.
Modèle isolé, preuve A : aucun service ou routage Deposium remplacé.

## Bases identiques aux pilotes CPU

Archive `results/context-base-jev-002` : **132/132 réponses `ok`, 123 correctes
(93,18 %)**. Les 132 cas représentent 66 familles FR/EN; les références sont
encore `agent_only`. Ni le corpus ni le scorer n'ont changé entre candidats.

| Domaine | Jev API | Julia CPU | GLiNER CPU |
|---|---:|---:|---:|
| Documentaire | 67/76 | 32/76 | 41/76 |
| Mathématiques | 28/28 | 8/28 | 5/28 |
| Chimie | 28/28 | 12/28 | 13/28 |
| Ensemble | **123/132** | 52/132 | 59/132 |
| Split test uniquement | **62/66** | 26/66 | 38/66 |

Jev : FR 62/66, EN 61/66; D1 36/40, D2 38/40, D3 49/52.
Train 32/36, calibration 29/30, test 62/66. Aucun apprentissage ou réglage de
prompt sur ces résultats. Sur les 132 cas appariés, Jev améliore 75 réponses
et en dégrade quatre face à Julia; 68 améliorations et quatre régressions face
à GLiNER. Ce gain n'est donc pas une domination sur chaque cas.

Les neuf erreurs concernent le documentaire : demandes composées
compte/titres/résumés, reprise du lot Audit après un échange intermédiaire,
ou clarification choisie au lieu d'aller lire le catalogue/contenu.
La question anglaise sur une date de mise en service échoue avec une confiance
native de 0,78 : ce champ ne suffit pas à garantir la justesse.
Une revue humaine doit notamment confirmer les formulations qui attendent le
choix d'une action alors que la question demande directement une information.

Les 28/28 scientifiques portent sur **14 familles par domaine**, avec réponses
proposées. Ils ne qualifient ni la génération libre de formules, ni un solveur
général, ni la fiabilité d'un calcul produit.

## Longueur et position

Archive `results/context-length-jev-001` : **305/354 correctes parmi les cas
scorés**, sur 378 variantes. Les 24 cibles irréalisables à 100 restent
`unsupported`, sans appel API. Zéro erreur, timeout ou retour mémorisé sur les
354 appels. Ces variantes ne représentent que neuf familles de calibration.

| Cible Julia | Correct / scoré / total | Entrée déclarée par Jev, min–max | HTTP médian ms | HTTP p95 ms |
|---:|---:|---:|---:|---:|
| 100 | 30/30/54 | 367–388 | 282,8 | 382,4 |
| 250 | 46/54/54 | 526–574 | 273,2 | 351,8 |
| 500 | 44/54/54 | 794–868 | 272,7 | 344,4 |
| 1 000 | 47/54/54 | 1 330–1 475 | 265,9 | 311,5 |
| 2 000 | 48/54/54 | 2 381–2 673 | 273,1 | 341,8 |
| 4 000 | 46/54/54 | 4 473–5 045 | 303,0 | 366,3 |
| 8 000 | 44/54/54 | 8 672–9 801 | 329,7 | 383,6 |

Les textes sont exactement ceux des autres pilotes. Les cibles Julia et les
tokens déclarés par l'API sont distincts; le banc ne dispose pas du tokenizer
Jev ni d'une preuve de non-troncature serveur.

Par domaine : documentaire 83/117 scorés sur 126, maths 117/117 sur 126,
chimie 105/120 sur 126. Par langue : FR 154/177 sur 189, EN 151/177 sur 189.
Par position : début 103/118, milieu 101/118, fin 101/118, chacun sur 126 prévus.
Pas de dégradation monotone suffisante pour fixer un seuil de bascule.
Les 49 erreurs viennent de deux familles seulement : inventaire actif
(34 variantes) et aliquote/mélange (15). Cela limite toute généralisation
par domaine à partir de cette petite sélection.
En chimie, les erreurs choisissent 0,250 mol/L au lieu de 0,175 mol/L :
la première valeur correspond à une moyenne non pondérée des concentrations.
Un calcul déterministe reste utile pour contrôler ce type de réponse.

Sur les **300 cas exécutés par Jev et Julia**, Jev réussit 261 contre 114.
Sur les **192 communs à Jev et GLiNER**, Jev réussit 167 contre 72. Les arrêts
mémoire des candidats CPU restent dans leurs dénominateurs complets; le gain
de couverture de l'API ne renseigne pas sa consommation de RAM/GPU distante.

## Temps répétés et variabilité

`results/context-jev-timing-001` termine **180/180 appels** : trois lancements,
un appel initial, cinq échauffements puis trois passages des mêmes 18 bases.
Les 162 mesures retenues donnent **272,20 ms HTTP médians, p95 311,95 ms**;
le temps complet de l'adaptateur est 290,56 ms, p95 332,01 ms.

Chaque appel utilise une nouvelle connexion HTTPS. Ces temps comprennent
TLS, réseau et attente; le calcul serveur est inconnu. Pour situer les ordres
de grandeur, la campagne CPU historique sur ces mêmes 18 bases mesurait
59,74 ms de décision pour Julia et 187,77 ms pour GLiNER. Les frontières de
mesure et les dates d'exécution diffèrent : aucun ratio de vitesse intrinsèque
n'est déduit de cette comparaison.

Jev donne 17/18 sur cinq passages et 18/18 sur quatre, soit 157/162 réponses
correctes. Trois cas changent de choix entre répétitions : inventaire actif EN
(six réponses correctes sur neuf), aliquote/mélange FR et EN (huit sur neuf
chacun). Julia et GLiNER donnaient chacun 6/18 sur leurs neuf passages.
Une version API épinglée ne garantit donc pas des sorties identiques.

## Budget, archives et vérifications

Le journal partagé conserve **735 tentatives**, dont 733 avec usage validé :
1 183 333 tokens d'entrée et 58 430 de sortie déclarés. Deux appels rejetés
avant correction restent réservés à 65 536 tokens chacun, soit une consommation
conservatrice de **1 314 405 / 2 000 000 tokens** et 735/800 appels.
Au tarif publié, l'usage validé représente environ **0,04970 USD**;
en comptant entièrement les réserves, environ **0,05521 USD**. Ce sont des
estimations, pas un relevé de facture. Les sorties sont annoncées gratuites.

Les premières traces sont conservées : `jev-smoke-001` (deux réponses),
`context-base-jev-001` (65 réponses valides, un rejet puis 66 retours sans appel),
`jev-response-diagnostic-001.json` (reproduction du problème d'arrondi).
La correction ne change aucun prompt, choix, référence ou score antérieur.

| Preuve locale | Résultat |
|---|---|
| `jev-tests-003.json` | 248 tests, 244 réussis, quatre skips MCPs |
| `jev-clean-stdlib-002.json` | Copie propre `c27581b`, Python `-S` : 248 tests, 233 réussis, 15 skips optionnels |
| `jev-notebook-proof-001.json` | Kernel neuf, rescore de 132 cas, mêmes scores et raw; source inchangée, aucune inférence |
| `jev-archive-validation-001.json` | Archives scellées, schémas et rescore exacts; 486 appels uniques dans les deux campagnes Jev retenues |
| `jev-timing-validation-001.json` | Neuf fichiers du scellement temporel vérifiés |
| `jev-budget-validation-001.json` | 735 tentatives uniques rapprochées du journal partagé; recherche de la clé négative dans les fichiers à publier et les archives |

Archives, clé et journal de budget restent hors Git. Les rapports agrégés sont
versionnés; aucun poids local supplémentaire n'a été téléchargé.

SHA-256 des fichiers `seal.json` : base
`b6d3c1a3d401e45b06af4022f455c930aaa2d04cf14328e75fd5fae3f6aede84`,
longueurs `f7be4b0a2663e388f05469e713d56eb6f5364582eab19a2f6c73a09a220889cf`.
Empreinte agrégée du scellement temporel :
`2e2ed8a4bf37d45adf5ac325fbbf97dd71de45381023961dd01dab2a971de7fe`.
Scorer inchangé : `d10a8b962ae2722c83218771fdffb4e16925d263fcca7d780cd14d4cab5a7084`.

Jev devient une référence mesurée pour la suite du banc. Il reste à revoir
humainement les références, introduire des documents réels autorisés et une
baseline LLM avant de qualifier une politique de bascule. La piste
[Indecis](INDECIS_CANDIDATE.md) prépare séparément un mode ouvert puis une
spécialisation documentaire, avec de nouvelles familles d'entraînement et test.
