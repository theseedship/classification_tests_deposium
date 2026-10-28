# Résultats : domaines, longueurs et temps de décision

Campagnes locales de la nuit du 1er au 2 octobre 2026. Résultats exploratoires isolés; aucune
qualification de routage produit ni seuil de bascule vers un LLM.

## Configuration et références

- Julia-1 : `a85b127321d580d65176c89ced8273f305745d85`, poids et runtime déjà locaux.
- CPU : Intel Core Ultra 5 235HX, WSL2, 14 processeurs logiques; Julia limité à deux threads, batch 1, fp32, sans compilation.
- Runtime Julia : Python 3.12.3, Torch 2.14.0+cpu, Transformers 5.0.0, Tokenizers 0.22.2, NumPy 2.5.3.
- Profil scientifique : fenêtre 8 192, tête 512, timeout 30 s, garde RSS 3 072 MiB.
- Corpus figé au commit `52f1660` avant toute prédiction, SHA-256 `767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616`.
- Références par agent; oracles scientifiques exacts restreints. Revue humaine indépendante non effectuée.
- MCPs réel : HEAD `391be12078b1f3daa24a50c31c3a39eb72d7fb94`; fonction documentaire importée depuis la stack. Les autres composants sont inventoriés, sans campagne intégrée.

## Les 132 cas courts

66 familles traduites FR/EN, trois difficultés définies avant les prédictions.
Les entrées réellement encodées vont de 45 à 123 tokens, avec zéro troncature.
132 réponses scorées, 52 réussites; tous les appels ont répondu sans erreur
d’exécution. RSS maximal rapporté : 992,43 MiB.

| Domaine | Tous les splits : réussis / scorés | Test seul | Français | Anglais |
|---|---:|---:|---:|---:|
| Documentaire | 32/76 | 15/38 | 15/38 | 17/38 |
| Mathématiques | 8/28 | 4/14 | 5/14 | 3/14 |
| Chimie | 12/28 | 7/14 | 5/14 | 7/14 |

FR : 25/66; EN : 27/66. D1 : 18/40; D2 : 11/40; D3 : 23/52.
Ces niveaux décrivent la construction des exercices. Leurs différences de
contenu, dont les cas d’information insuffisante, empêchent d’y lire une
échelle empirique monotone de difficulté.

Les choix mathématiques/chimiques portent sur des calculs, types, dimensions,
atomes et charges sous hypothèses explicites. Ils ne mesurent pas la génération
libre d’une démonstration ni la faisabilité d’une réaction. Les cas documentaires
demandent un choix de tâche; ils ne rejouent pas le routage de l’application.

## Domaine × longueur

Grille gelée : neuf familles de calibration, FR/EN, trois positions du passage
utile, sept paliers, ordre original. 378 variantes; neuf familles de scénarios,
pas 378 observations indépendantes. Les mêmes faits, questions et choix sont
conservés; les annexes sont synthétiques et répétées suivant un protocole figé.

Chaque cellule indique **réussis / scorés / prévus**. Les temps sont les médianes
de `decision_ms` des appels `ok`, avec leur effectif, toutes langues et domaines
confondus. Le JSON et le CSV conservent les croisements complets.

| Tokens cibles totaux | Documentaire | Mathématiques | Chimie | Décision médiane | Appels chronométrés |
|---:|---:|---:|---:|---:|---:|
| 100 | 6/9/18 | 5/9/18 | 2/12/18 | 66.5 ms | 30 |
| 250 | 10/18/18 | 7/18/18 | 6/18/18 | 145.2 ms | 54 |
| 500 | 8/18/18 | 5/18/18 | 4/18/18 | 297.7 ms | 54 |
| 1 000 | 9/18/18 | 3/18/18 | 5/18/18 | 690.6 ms | 54 |
| 2 000 | 10/18/18 | 7/18/18 | 5/18/18 | 1851.1 ms | 54 |
| 4 000 | 10/18/18 | 7/18/18 | 5/18/18 | 5773.6 ms | 54 |
| 8 000 | 0/0/18 | 0/0/18 | 0/0/18 | non mesurée | 0 |

Bilan : **114 réussites sur 300 cas scorés, 378 prévus**. Les 24 cas hors
cible à 100 tokens restent `unsupported/input_length_target_unattainable`.
Pour les 300 inférences abouties, le compte natif correspond exactement au
compte du générateur; aucune troncature n’est observée.

Au palier 8 000, le premier cas compte 7 996 tokens, 8 000 après padding.
Il déclenche `julia_rss_limit` après environ 19,43 s. Le worker est fermé;
les 53 demandes suivantes reçoivent l’erreur mémorisée sans nouveau forward.
Il y a donc **un dépassement observé, puis 53 cas non exécutés par le moteur**,
archivés en erreur. Leur faible durée de retour n’est pas une mesure de vitesse
à 8k. Aucun score de connaissance n’est disponible pour ce palier.

Le RSS maximal des appels réussis atteint 1 765,32 MiB à 4k. Ce relevé est le
maximum cumulé du processus, pas une allocation propre à chaque question.
Le pic exact de l’appel arrêté à 8k n’est pas conservé : seule l’activation
de la garde 3 072 MiB est établie. Cette limite concerne ce profil et ce runtime,
pas toute exécution possible de Julia. La frontière précise entre 4k et 8k
n’a pas été recherchée et le contrôle exact 8 192/8 193 reste à reproduire.

La qualité ne décroît pas régulièrement avec la longueur dans cette petite
grille. Les positions début/milieu/fin donnent 37/100, 35/100 et 42/100 cas
scorés réussis, respectivement; elles restent corrélées au sein des familles.
Ces résultats ne permettent pas de définir un seuil fiable de bascule.

## Mesure répétée des 14 cas documentaires historiques

Trois lancements par candidat, un premier appel, cinq échauffements et dix
passages complets. Candidats séquentiels, ordre alterné entre lancements.
**876/876 appels aboutis**, dont 420 appels mesurés après échauffement par
candidat. Les 30 répétitions conservent les sept familles initiales.

| Candidat | Score sur chaque passage | Décision médiane | Décision p95 | Appel adaptateur médian | Initialisation médiane |
|---|---:|---:|---:|---:|---:|
| Fonction MCPs résidente | 14/14 | 0.085 ms | 0.260 ms | 9.645 ms | 0.565 s |
| Julia, profil historique 1 024 | 10/14 | 78.647 ms | 107.963 ms | 82.958 ms | 10.817 s |

La fonction déterministe MCPs est plus juste et plus rapide sur ces quatorze
cas. Le temps ancien d’environ 143 ms incluait un nouveau processus Node
à chaque cas; il ne mesurait pas seulement cette fonction.

Le temps adaptateur inclut transport et vérifications de provenance.
`decision_ms` est mesuré après décodage JSON, jusqu’à la décision normalisée;
Julia y ajoute formatage, tokenisation et audit. Le RSS MCPs n’est pas mesuré.
Un processus neuf ne signifie pas un cache disque froid. Les p95 décrivent
cette série locale; elles ne garantissent pas les latences d’un service chargé.
Aucun LLM distant n’a été appelé; son gain et son coût restent à mesurer.

## Archives et reprise

Validation du banc : 188 tests, 184 réussis et quatre replays MCPs réels omis
dans la suite ordinaire. Une copie sans poids, stack, cache, dépendance installée
ni environnement virtuel valide aussi le socle sous Python `-S`; les contrôles
JSON Schema y sont optionnels. Les trois archives base/longue/notebook satisfont
1 293 validations de schéma; leurs seals et les quatorze fichiers scellés du
benchmark temporel sont vérifiés. Le notebook source reste sans sorties.

Les grandes traces restent dans `results/`, hors Git; le présent relevé et les
corpus/scripts sont versionnés. Sur un clone neuf, utiliser les commandes du
[local-only material, not distributed](PROTOCOL.md); télécharger les poids demeure une étape
explicite distincte. La validation stdlib et les contrôles figés restent offline.

| Archive locale | Preuve |
|---|---|
| `results/context-base-julia-001` | 132 cas, sorties et manifeste scellés |
| `results/context-base-analysis-001` | Analyse JSON, Markdown et CSV |
| `results/context-sentinels-001` | Sélection avant prédiction et 378 variantes, 354 éligibles |
| `results/context-length-julia-001` | 300 réponses, 24 cibles infaisables, 54 erreurs mémoire |
| `results/context-length-analysis-001` | Détail domaine/langue/difficulté/longueur/position/split |
| `results/task-timing-001` | 876 appels, initialisations et résultats de chaque passage |
| `results/context-notebook-rescore-001` | Rescore dans un kernel neuf sans inférence |
| `results/context-notebook-proof-001.json` | Scores et raw identiques, source et archive intactes |

Identités des seals :

- Base : `dfdc3e220fe788bfd48f2b086130f74b265c4c2ecdd7b3f843994532d06d401a`.
- Longueurs : `88d0fdcbc30e5305df8952803fc56e32948983ad50532ea5e04620527ab8bbe5`.
- Temps : `38a37d984c938ebed9d807c3d79547084f2a5341cca4faa597c2ce65e847b647`.

Suite exécutée le 2 octobre : [pilote GLiNER2.5-multi-Decide](GLINER_RESULTS.md)
sur ces mêmes cas gelés. Les présents résultats Julia sont conservés comme
référence historique; la comparaison figure dans le rapport GLiNER.
Les références humaines, vrais documents longs, langues additionnelles et
comparaisons LLM/cascade restent les étapes de qualification suivantes.
