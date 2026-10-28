# Indecis ouvert : résultats du pilote CPU

Campagnes du 2 octobre 2026, branche `feat/indecis-open-pilot`, code et
[protocole](INDECIS_PILOT.md) gelés à `2f1875d` avant la première prédiction.
Le mode ouvert non entraîné est rapide sur les cas courts, mais obtient
**44/132 bonnes réponses**, moins que Julia, GLiNER et Jev sur ces mêmes bases.
Ce résultat ne mesure pas l'intérêt d'une spécialisation par entraînement.

Modèle isolé, preuve A, capacité `bench.context-choice`. Le préflight recense
les 15 composants et 29 contrats de la stack; aucun service, routage ou parcours
Deposium n'est exécuté ou remplacé. Les références restent `agent_only`.

## Qualité sur les bases

`results/context-base-indecis-001` contient **132/132 réponses `ok`**, dont
44 correctes (33,33 %). Aucun refus technique, erreur, timeout ou abstention.
Le corpus représente 66 familles traduites FR/EN; les traductions ne sont pas
des observations indépendantes. Aucun corpus, scorer ou prompt n'a été adapté
après lecture des résultats.

| Domaine | Indecis brut | Julia CPU | GLiNER CPU | Jev API |
|---|---:|---:|---:|---:|
| Documentaire | 32/76 | 32/76 | 41/76 | 67/76 |
| Mathématiques | 2/28 | 8/28 | 5/28 | 28/28 |
| Chimie | 10/28 | 12/28 | 13/28 | 28/28 |
| Ensemble | **44/132** | 52/132 | 59/132 | 123/132 |
| Split test uniquement | **22/66** | 26/66 | 38/66 | 62/66 |

Les comparateurs proviennent des campagnes antérieures :
[Julia](CONTEXT_RESULTS.md), [GLiNER](GLINER_RESULTS.md), [Jev](JEV_RESULTS.md).
Ils n'ont pas été relancés pour ce pilote.

Indecis : FR **21/66**, EN **23/66**; difficulté D1 **12/40**, D2 **11/40**,
D3 **21/52**. Train **12/36**, calibration **10/30**, test **22/66**. Le split
test comprend documentaire 15/38, maths 2/14 et chimie 5/14. Les noms des splits
décrivent le corpus : aucun entraînement n'a eu lieu.

Les **deux réussites mathématiques** sont les traductions FR/EN de la famille
`unknown-function-values`, où la réponse attendue est « information insuffisante ».
Les 24 questions mathématiques avec une réponse déterminée donnent **0/24**;
l'autre famille mathématique insuffisamment renseignée échoue également.
Ce pilote n'apporte donc aucune preuve de capacité de calcul ou d'assemblage
de formules. Sur les trois domaines, les cas d'information insuffisante donnent
5/12, dont 3/6 dans le test; choisir cette option reste une réponse sémantique,
distincte d'une abstention technique.

En documentaire : catalogue 11/24, résumés stockés 16/24, recherche de contenu
4/24, ambiguïté 1/4. Les petits effectifs et les conventions à revoir limitent
toute conclusion par domaine, langue ou difficulté.

## Longueur, position et couverture

`results/context-length-indecis-001` termine les 378 variantes prévues :
**81/300 bonnes réponses scorées** et **78 `unsupported`**. Les refus sont
24 cibles irréalisables à 100 tokens dans la garde commune et 54 dépassements
du budget natif à 8k. Aucun échec technique, timeout ou arrêt mémoire.

| Cible Julia | Correct / scoré / prévu | Plus longue séquence native, min–max | Décision médiane ms, cas exécutés |
|---:|---:|---:|---:|
| 100 | 14/30/54 | 33–68 | 30,8 |
| 250 | 15/54/54 | 177–215 | 63,7 |
| 500 | 14/54/54 | 429–466 | 114,5 |
| 1 000 | 13/54/54 | 928–971 | 254,1 |
| 2 000 | 16/54/54 | 1 933–1 971 | 350,0 |
| 4 000 | 9/54/54 | 3 931–3 972 | 944,1 |
| 8 000 | — / 0 / 54 | 7 925–7 968 | aucune inférence |

Les cibles sont définies par le tokenizer Julia de référence. Indecis encode
séparément le contexte et chaque choix; leur somme n'est pas une fenêtre de
cross-encoder. Les mêmes textes ont été utilisés, sans régénération.
Le plafond **4 096 tokens par séquence** est un budget choisi pour ce pilote,
pas une limite intrinsèque démontrée du modèle. Les 54 refus 8k portent
`forward_executed=false`, sans sortie native ni `inference_ms` : aucun score
de qualité ou temps d'inférence à 8k ne peut être déduit de ces traces.
Les 300 appels exécutés passent l'audit des IDs réellement encodés, sans troncature.

Par domaine : documentaire **36/99 scorés sur 126**, maths **19/99 sur 126**,
chimie **26/102 sur 126**. Par langue : FR **35/150 sur 189**, EN **46/150 sur
189**. Par position : début **31/100**, milieu **25/100**, fin **25/100**,
chacune sur 126 variantes prévues. Ces variantes ne représentent que **neuf
familles de calibration**; elles ne renforcent pas le nombre de cas indépendants
et ne constituent pas un nouveau test de généralisation.

Les comparaisons sur sorties `ok` communes donnent :

| Comparateur | Cas communs scorés | Indecis | Comparateur |
|---|---:|---:|---:|
| Julia | 300 | 81 | 114 |
| GLiNER | 192 | 56 | 72 |
| Jev | 300 | 81 | 261 |

Sur les 378 prévus, Julia avait 300 sorties scorées, GLiNER 192 et Jev 354.
Les arrêts mémoire de Julia/GLiNER et le refus préventif d'Indecis sont des
statuts distincts. Ces observations ne qualifient aucun seuil de bascule LLM.

## Temps répétés et ressources

`results/context-indecis-timing-001` termine **180/180 appels** : trois
lancements, un appel initial, cinq échauffements, puis trois passages des mêmes
18 bases à chaque lancement. Les **162 mesures** retenues donnent :

| Frontière mesurée | Médiane ms | p95 ms |
|---|---:|---:|
| Appel natif `DecideOpen`, options réencodées comprises | 25,93 | 35,30 |
| Décision du worker, préflight et audits compris | **25,99** | **35,39** |
| Appel complet de l'adaptateur Python | 34,12 | 44,32 |

Le chargement prend 1 168 ms médians sur trois lancements; le premier appel
prend 45,06 ms de décision médians. Chaque passage donne **6/18**, avec le même
choix sur les neuf répétitions de chacun des 18 cas. Cette stabilité observée
ne garantit pas une reproductibilité bit à bit sur toute machine.

Pour situer les résultats historiques sur ces mêmes 18 bases : Julia mesurait
**59,74 ms** de décision médiane et GLiNER **187,77 ms**, avec 6/18 à chaque
passage. Jev mesurait **272,20 ms HTTP**, réseau et nouvelle connexion TLS
compris, avec 157/162 bonnes réponses. Les sessions diffèrent; le temps HTTP
n'est pas le temps de calcul serveur. Ce sous-ensemble temporel ne remplace
pas la qualité sur les 132 bases.

Deux threads CPU, aucun GPU, garde RSS 3 072 MiB. RSS maximal observé du worker :
**1 121,28 MiB** sur la base, **1 241,19 MiB** sur les longueurs et **960,75 MiB**
sur les répétitions. La garde n'a pas été déclenchée. Ce sont des observations
de processus, pas la RAM totale de la machine. Le pilote utilise environ
235 MiB d'assets modèle sur disque; SDK et caches de compilation sont séparés.
Ces mesures ne décrivent pas un détecteur spécialisé à vocabulaire réduit.

## Provenance, archives et vérifications

Le worker appelle le vrai `DecideOpen` d'Indecis
`339e191405ac9be90f6857f810f478b3312b7f35`, compilé avec Go
`1.27.1-X:simd`. Backbone `hotchpotch/bekko-embedding-v1-a8m`, révision
`c721113d59a1d91b447450324f51c4b3332c924a`, chemin flottant officiel,
sans quantification INT8, cache interrequêtes, tête entraînée ou réduction
de vocabulaire. Le [runtime](../runtimes/indecis/README.md) et le
[profil](../profiles/indecis-open-cpu-context.json) décrivent la reproduction.

La question devient `Instructions`; chaque description de choix devient le
nom du candidat. Indecis encode ainsi `description + "\n" + question` face au
contexte. Les identifiants servent seulement au transport/remapping; annotations,
références, split, domaine et difficulté ne sont jamais fournis au modèle.
Les probabilités natives sont archivées mais ne sont pas calibrées.

| Vérification | Résultat |
|---|---|
| Copie Git propre `2f1875d`, Python `-S`, sans poids ni stack | 272 tests : 255 réussis, 17 skips optionnels |
| Adaptateur final et schémas, environnement local | 17 + 23 tests réussis |
| Worker Go, moteur factice | 9 tests réussis, sans poids |
| Préflight et registre | 15 composants, 29 contrats; services/images non observés |
| Archives base et longues | Scellements et schémas valides; rescore exact, mêmes corpus/scorer |
| Archive temporelle | Dix fichiers du scellement vérifiés, 180 appels archivés |
| Notebook, kernel neuf | Rescore 132 cas, 44 corrects, raw identique; aucune inférence, source inchangée |

Le contrôle initial `results/indecis-smoke-001` conserve 2/2 bonnes réponses,
avec 130 cas non exécutés : il reste une campagne partielle. Les analyses sont
dans `results/context-base-indecis-analysis-001` et
`results/context-length-indecis-analysis-001`. Six comparaisons sont archivées
sous `results/compare-{julia,gliner,jev}-indecis-{base,length}-001`.
Le rescore CLI est dans `results/context-base-indecis-rescore-001`; la preuve
notebook dans `results/indecis-notebook-check-001/verification.json`. Les logs
sont sous `results/indecis-pilot-logs/`. Les campagnes ont été exécutées
successivement; aucun appel Jev/LLM, entraînement ou changement de stack.
La preuve locale `results/indecis-pilot-verification-001.json` rassemble les
scellements vérifiés, le résultat de la copie propre et la preuve notebook.
Ces vérifications sont locales; aucune CI hébergée n'est configurée dans ce dépôt.

SHA-256 des fichiers `seal.json` :

- Base : `ed5291f2c094568cdb5869df36d04f66b876ded44630fbb3ab6167cfe3597bcf`.
- Longueurs : `c28c83dae2ae277e4f30d5da8104a9917150f7a6065ef0d6829765d9c5391b18`.
- Temps : `16e27e026fbe6699f6828df1b7661664d54036ed0552c4941868cb420fcd7b8f`.

Le [protocole](INDECIS_PILOT.md) fixe les hashes des trois corpus et du scorer.
SHA-256 du binaire exécuté :
`b0cc2d933b985a535b4d4b6852289c97b0f4375896a92915b03ba329694842b0`.
Les manifests versionnent également les assets et la fermeture des sources
upstream/worker. Les archives brutes, poids et SDK sont hors Git;
[leur conservation](EVIDENCE_PRESERVATION.md) reste distincte du push.

## Conséquence pour la suite

Le pilote R3 est terminé. Indecis brut fournit une baseline CPU rapide sur
les entrées courtes, avec une qualité insuffisante sur ce corpus. Pour décider
entre une spécialisation Indecis et GLiNER, il faut désormais revoir les
références, choisir une décision récurrente précise, puis constituer de
nouvelles familles train/calibration/test. Comparer ensuite les deux approches
sur le même test tenu à l'écart et les mêmes budgets, avec Jev comme référence
mesurée. Voir la [local-only material, not distributed](PROTOCOL.md); aucun entraînement n'est engagé ici.
