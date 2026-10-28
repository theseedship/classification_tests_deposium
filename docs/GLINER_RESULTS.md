# Résultats GLiNER2.5-multi-Decide : base, contextes longs et temps

Relevé local du 2 octobre 2026. Sur les 132 bases gelées FR/EN, GLiNER donne
132 réponses `ok`, dont **59 correctes (44,70 %)**. Julia en donne 52 correctes
sur les mêmes cas (39,39 %). Le gain global de sept réponses masque des
régressions : 32 cas deviennent corrects, 25 deviennent faux.

Ce sont des observations de modèles isolés, preuve A, sur un corpus synthétique.
Elles ne qualifient ni le routage Deposium, ni un seuil de recours à un LLM.
Le [protocole GLiNER](GLINER_PILOT.md) fixe les entrées, limites et campagnes
avant leur exécution. Sur les contextes longs, GLiNER réussit 72/192 cas
scorés sur 378 prévus; un arrêt mémoire réduit sa couverture. Sur la mesure
répétée des 18 sentinelles courtes, les deux candidats réussissent 6/18
à chaque passage, et Julia répond plus vite dans cette série locale.

## Méthode et identité des campagnes

Le modèle est `fastino/GLiNER2.5-multi-Decide`, révision
`a35a0cd3b7a0f00f2effc576f454cd48fa98aa5f`. Le runtime observé utilise
Python 3.12.3, `gliner2` 2.0.0, Torch 2.14.0+cpu, Transformers 4.57.6,
Tokenizers 0.22.2 et NumPy 2.5.3. Le modèle et le runtime sont locaux,
en mode hors ligne, CPU, deux threads, une requête et un modèle à la fois.

La campagne de base enregistre le commit **propre `83be31a`**. L'archive
historique Julia enregistre `52f1660` avec un checkout alors modifié : les
deux campagnes ne prétendent donc pas provenir du même état complet du banc.
La comparaison vérifie les mêmes bytes de corpus, les mêmes identités de cas,
le même protocole `context_choice` et le même scorer courant. Les deux
archives sources sont scellées et de preuve A.

| Élément figé | SHA-256 |
|---|---|
| Corpus des 132 bases | `767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616` |
| Scorer et dépendances de validation | `d10a8b962ae2722c83218771fdffb4e16925d263fcca7d780cd14d4cab5a7084` |
| Assets GLiNER vérifiés | `492b491f2da19dfdb7650fd2ac67bf9f16d36ae0e255021301994830418ec32f` |
| Lock du runtime GLiNER | `8af83e57f2f0dabed16483a26a4d2f64ec3fa14679e584f3f8fb1dce4fa3b4b8` |
| Sources Python installées de GLiNER | `afad097d6823940c489d2d1d0778587ed66181b715a8448c7a79223e720a56bc` |

Les manifests conservent aussi les profils, prompts, versions, sources de
l'adaptateur et du worker, et hashes individuels des assets. Le worker reçoit
uniquement le contexte, la question et les descriptions des choix. Les IDs
servent à mapper sa sortie; ni référence, ni oracle, ni difficulté, ni split
ne sont fournis au classifier. Le traitement officiel ajoute éventuellement
un point et met les mots en minuscules; ce comportement, y compris ses effets
possibles sur les formules chimiques, appartient au candidat évalué.

Le préflight du processeur officiel conserve l'entrée complète. Le budget
fixé est de **4 096 sous-tokens natifs**, question et options comprises. Un
hook vérifie les IDs et le masque effectivement envoyés à l'encodeur.
Un dépassement doit rester `unsupported/gliner_context_overflow`, avant
forward. Ce budget est celui du pilote, pas une limite universelle du modèle.

## Chargement : échec conservé puis contrôle réussi

`results/gliner-smoke-001`, exécutée depuis le commit propre `d3902da`,
échoue au chargement : protobuf manque au chemin de compatibilité du tokenizer
sous Transformers 4.x. Les deux demandes tentées sont archivées
`missing/gliner_assets_or_runtime_missing`, avec zéro cas scoré; les 130
autres cas n'ont pas été appelés. L'archive initiale est conservée.

Le commit `83be31a` ajoute protobuf au lock, avant la première prédiction
GLiNER réussie. Les cas, références, prompt, poids, adaptateur et worker
ne changent pas avec cette correction de dépendance. La nouvelle archive
`results/gliner-smoke-002` donne **2/2 demandes correctes**, une FR et une EN,
et laisse les 130 cas non appelés visibles dans le dénominateur total.
Ce contrôle de chargement n'est pas une campagne de 132 réussites.

## Résultats des 132 bases

Le [corpus](../datasets/context-choice-v1/README.md) contient 66 familles
traduites FR/EN : 76 cas documentaires, 28 mathématiques et 28 chimiques,
dont quatre cas d'information insuffisante par domaine. Les références sont
`agent_only`; la revue humaine indépendante reste à faire. Les oracles
scientifiques exacts sont restreints aux hypothèses des exercices.

Tous les appels ont répondu `ok`, sans erreur, timeout, abstention technique
ni refus. Le dénominateur apparié des appels réussis est donc lui aussi 132.
L'exactitude sur les cas scorés et celle sur tous les cas coïncident ici.

| Domaine | GLiNER : corrects / scorés / tous | Julia : corrects / scorés / tous |
|---|---:|---:|
| Documentaire | 41 / 76 / 76 | 32 / 76 / 76 |
| Mathématiques | 5 / 28 / 28 | 8 / 28 / 28 |
| Chimie | 13 / 28 / 28 | 12 / 28 / 28 |
| Ensemble | **59 / 132 / 132** | **52 / 132 / 132** |

| Split | GLiNER corrects / tous | Julia corrects / tous |
|---|---:|---:|
| Train | 15 / 36 | 12 / 36 |
| Calibration | 6 / 30 | 14 / 30 |
| Test | 38 / 66 | 26 / 66 |

Dans le test seul : documentaire **26/38 contre 15/38** pour Julia,
mathématiques **3/14 contre 4/14**, chimie **9/14 contre 7/14**. Les 66
cas de test représentent 33 familles traduites.

Les noms de splits décrivent le découpage gelé; aucun entraînement local sur
ces cas n'a été effectué. Le résultat global regroupe ces trois splits et
ne constitue pas un score de test seul.

| Langue ou difficulté déclarée | GLiNER corrects / tous | Julia corrects / tous |
|---|---:|---:|
| Français | 28 / 66 | 25 / 66 |
| Anglais | 31 / 66 | 27 / 66 |
| D1 | 17 / 40 | 18 / 40 |
| D2 | 19 / 40 | 11 / 40 |
| D3 | 23 / 52 | 23 / 52 |

Les niveaux D1/D2/D3 ont été définis avant les prédictions et décrivent la
construction des exercices. Les cas d'information insuffisante et les sujets
différents empêchent d'en déduire une échelle empirique monotone. Les seules
langues évaluées sont FR et EN; aucune performance Deposium n'est établie
ici pour les autres langues annoncées par le modèle.

La comparaison appariée compte **27 cas corrects pour les deux modèles,
48 faux pour les deux, 32 corrects seulement pour GLiNER et 25 corrects
seulement pour Julia**. GLiNER gagne neuf réponses documentaires et une en
chimie, mais en perd trois en mathématiques. Cela ne justifie pas une
supériorité générale, ni une cascade ajustée après examen de ces erreurs.

La reconnaissance de l'information insuffisante reste fragile : **3/12 pour
GLiNER contre 8/12 pour Julia** sur tous les splits. Sur les six cas de test
de ce sous-ensemble, chacun réussit 3/6. Le protocole demande toujours un
choix unique : « information insuffisante » est une réponse sémantique parmi
les options, distincte du statut technique `abstain`. Le top-1 forcé peut
donc sélectionner une réponse injustifiée malgré une confiance native.

Trois exemples anglais du split test sont vérifiables dans les sorties brutes :

| Cas | Référence gelée | GLiNER | Julia |
|---|---|---|---|
| `ctx-mathematics-matrix-product-en` | `AB` est `2×4`, pour `A:2×3` et `B:3×4` | `2×3`, faux | `2×3`, faux |
| `ctx-chemistry-molar-concentration-en` | `0.10 mol/L`, unité de concentration | `0.10 mol`, faux | `0.10 mol/L`, correct |
| `ctx-documentary-ambiguous-selection-en` | Référent insuffisant, demander une clarification | Fichier B seul, faux | Nécessairement A et B, faux |

## Ressources et temps observés sur la base

Sur 132 appels uniques, l'analyse archive les observations suivantes :

| Frontière mesurée | Médiane | p95 | Effectif |
|---|---:|---:|---:|
| Appel adaptateur, transport et gardes inclus | 234,95 ms | 401,05 ms | 132 |
| Décision dans le worker, prétraitement et audit inclus | 226,94 ms | 391,29 ms | 132 |
| Appel natif `classify_text`, prétraitement interne inclus | 224,75 ms | 389,02 ms | 132 |

Le chargement natif rapporte 12,56 s; l'initialisation entière 13,10 s.
Les entrées encodées comptent de 54 à 152 tokens natifs, médiane 104,
sans troncature observée. Leur longueur native ne se confond pas avec les
tokens Julia des mêmes textes.

Le pic RSS rapporté est **2 891,91 Mio**, sous la garde configurée de
3 072 Mio (3 Gio). Il s'agit du maximum cumulé du processus worker,
pas d'une allocation par question ni de la mémoire totale du système.
La garde est une surveillance toutes les 50 ms avec arrêt du processus,
pas un plafond système dur. Les modèles sont exécutés séquentiellement;
cette observation ne valide pas leur chargement simultané.

Ces 132 durées proviennent d'un passage unique. Leur p95 est descriptif,
sans garantie de queue de latence, de charge service ni de cache disque froid.
Elles ne remplacent pas la mesure répétée prévue ci-dessous et ne permettent
pas d'attribuer un gain de vitesse sur les archives historiques Julia.

## Contextes longs : couverture limitée par la garde mémoire

La campagne scellée `results/context-length-gliner-001`, depuis le commit
propre `83be31a`, utilise les **378 textes existants**, neuf familles de calibration
FR/EN, trois positions et sept paliers de 100 à 8 000 tokens de référence
Julia. Le corpus de variantes reste
`f721aec7ff08b3b4be6a2e3dcb5dd88ae2b1c0bea3a7fcf6f9ab0aefd92e492a`.
Les textes n'ont pas été régénérés pour rapprocher les tokenizers. Les
378 variantes restent neuf familles, pas 378 observations indépendantes.

Bilan GLiNER : **72 corrects / 192 scorés / 378 prévus**. Il y a 192 appels
`ok`, 24 refus `input_length_target_unattainable` au palier 100, et 162
enveloppes `error/gliner_rss_limit`. Aucun timeout, aucune troncature ni
aucun `gliner_context_overflow` n'est observé.

| Cible Julia | GLiNER corrects / scorés / prévus | Julia corrects / scorés / prévus | Tokens natifs GLiNER observés | Décision GLiNER médiane / effectif |
|---:|---:|---:|---:|---:|
| 100 | 12 / 30 / 54 | 13 / 30 / 54 | 91–138 | 205,67 ms / 30 |
| 250 | 21 / 54 / 54 | 23 / 54 / 54 | 282–335 | 491,94 ms / 54 |
| 500 | 18 / 54 / 54 | 17 / 54 / 54 | 580–669 | 1 289,42 ms / 54 |
| 1 000 | 21 / 54 / 54 | 17 / 54 / 54 | 1 192–1 314 | 4 924,79 ms / 54 |
| 2 000 | 0 / 0 / 54 | 22 / 54 / 54 | non conservés | non mesurée / 0 |
| 4 000 | 0 / 0 / 54 | 22 / 54 / 54 | non mesurés | non mesurée / 0 |
| 8 000 | 0 / 0 / 54 | 0 / 0 / 54 | non mesurés | non mesurée / 0 |

Les temps de cette table concernent seulement les appels `ok`, toutes
langues, positions et domaines confondus. Les tokens cibles sont ceux du
tokenizer de référence Julia; la colonne GLiNER montre le compte natif
complet réellement audité sur les appels aboutis.

Le premier cas du palier 2 000,
`ctx-documentary-catalog-active-inventory-fr--t02000--start--original`,
déclenche la garde RSS après **1 533,14 ms**. Le texte contient 2 007 tokens
de référence, 2 008 après padding Julia. Le worker est arrêté; **les 161
demandes suivantes reçoivent la même erreur mémorisée, sans nouvel appel
au worker ni forward**. Il s'agit donc d'**un dépassement mémoire observé**,
suivi de 161 retours d'échec, et non de 162 dépassements indépendants.

La sortie brute du premier appel arrêté est nulle : son compte natif, son
pic exact et le moment précis atteint dans le moteur ne sont pas conservés.
Les appels aboutis rapportent un maximum RSS cumulé de 2 885,47 Mio;
l'activation de la garde établit séparément le dépassement de 3 072 Mio.
Les réponses mémorisées très rapides ne mesurent pas la vitesse du modèle
sur les textes de 2k, 4k ou 8k.

**Aucun forward GLiNER n'a été exécuté aux paliers 4k et 8k.** La politique
de refus au-delà de 4 096 sous-tokens existe et est testée sans poids, mais
cette campagne n'en produit aucune observation native : l'arrêt mémoire
intervient avant ces paliers. Elle ne mesure ni leur qualité, ni leur durée
de décision, ni une frontière universelle de capacité. Entre le dernier
palier réussi et le premier appel arrêté, aucune recherche de frontière
fine n'a été menée.

La [local-only material, not distributed](PROTOCOL.md)
conserve le coût de la perte de couverture :

| Dénominateur | GLiNER | Julia |
|---|---:|---:|
| Corrects / tous les cas | 72 / 378 (19,05 %) | 114 / 378 (30,16 %) |
| Scorés / tous les cas | 192 / 378 (50,79 %) | 300 / 378 (79,37 %) |
| Corrects / scorés propres au candidat | 72 / 192 (37,50 %) | 114 / 300 (38,00 %) |
| Corrects / appels `ok` communs | **72 / 192 (37,50 %)** | **70 / 192 (36,46 %)** |

Sur ces 192 appels communs : 42 corrects pour les deux, 92 faux pour les
deux, 30 corrects seulement pour GLiNER et 28 seulement pour Julia. Les
scores propres aux candidats portent sur des sous-ensembles différents;
ils ne remplacent pas l'appariement. Les 186 autres cas restent non appariés.

| Domaine | GLiNER corrects / scorés / prévus | Julia corrects / scorés / prévus | GLiNER / Julia corrects sur appels communs |
|---|---:|---:|---:|
| Documentaire | 24 / 63 / 126 | 53 / 99 / 126 | 24 / 33 sur 63 |
| Mathématiques | 18 / 63 / 126 | 34 / 99 / 126 | 18 / 20 sur 63 |
| Chimie | 30 / 66 / 126 | 27 / 102 / 126 | 30 / 17 sur 66 |

La grille longue porte seulement sur des familles de calibration, avec
annexes synthétiques répétées. Elle ne permet pas d'extrapoler le résultat
des 132 bases ni de fixer un seuil LLM.

## Diagnostic séparé du refus de longueur native

Après la campagne longue, un processus neuf traite uniquement sa première
paire documentaire FR/EN au palier 8 000, position début, ordre original.
La sélection `results/gliner-overflow-selection-001/cases.jsonl` conserve
exactement ces deux entrées. Le diagnostic scellé
`results/gliner-overflow-probe-001` ne reprend ni ne modifie la campagne
de 378 cas. Son manifeste enregistre `7cf0d34` avec un checkout modifié;
les hashes du modèle, de l'adaptateur, du worker, du prompt et du runtime
correspondent à ceux de la base.

| Langue | Tokens natifs complets | Schéma / contenu | Mots du contexte | Statut |
|---|---:|---:|---:|---|
| FR | 9 432 | 86 / 9 346 | 5 819 | `unsupported/gliner_context_overflow` |
| EN | 9 215 | 70 / 9 145 | 6 221 | `unsupported/gliner_context_overflow` |

Les deux réponses gardent `stateTruncated=false`, `optionsTruncated=false`,
`forward_executed=false`, `inference_ms=null` et aucune sortie native.
Les comptes de mots supérieurs à 4 096 confirment l'absence de troncature
silencieuse à ce nombre de mots. Le budget du pilote demeure celui des
sous-tokens complets, schéma et contenu inclus.

La validation établit **la garde d'admission**, avec **zéro forward et
zéro cas scoré**; l'évaluation de qualité est `not_run`. Ces deux refus
ne constituent pas deux bonnes réponses. Ils ne remplacent pas les 162
enveloppes d'erreur de l'archive longue et ne valident aucun score à 8k.

## Mesure répétée Julia / GLiNER

Le protocole est fixé dans [GLINER_PILOT.md](GLINER_PILOT.md) et gelé au
commit `44bfd64`, avant sa première mesure. Il utilise les 18 bases des
neuf familles de sentinelles, trois lancements par candidat, un appel initial,
cinq échauffements et trois passages : **360/360 appels `ok`**, dont 162
mesurés après échauffement par candidat. Les six premiers appels et les
30 échauffements restent archivés, hors statistiques des passages mesurés.
Les processus sont séquentiels
et l'ordre des candidats alterne entre lancements.

La campagne `results/context-model-timing-001` est complète et scellée;
son manifeste enregistre le commit propre **`7cf0d34`**. Le CPU observé
est un Intel Core Ultra 5 235HX, sous WSL2, avec 14 processeurs logiques;
chaque candidat utilise deux threads. Les textes sont identiques,
SHA-256 `cc2e19abf97f777a762a4c685ab2a2660f02f3d158ee2dbb4fba4ef516fa7ddb`.

| Candidat | Corrects à chaque passage | Décision médiane / p95 | Adaptateur médian / p95 | Initialisation médiane | RSS maximum rapporté |
|---|---:|---:|---:|---:|---:|
| Julia, profil contextuel 8 192 / tête 512 | 6 / 18 | 59,745 / 84,272 ms | 64,273 / 89,093 ms | 11,748 s | 1 015,71 Mio |
| GLiNER, budget natif 4 096 | 6 / 18 | 187,771 / 243,106 ms | 194,885 / 251,455 ms | 10,917 s | 2 885,77 Mio |

Chaque distribution mesurée compte **162 appels par candidat**, répartis
sur neuf passages; l'initialisation compte trois lancements par candidat.
Les neuf passages conservent le score 6/18 et les mêmes choix normalisés
pour chaque cas. Un statut `ok` établit une exécution réussie, pas une
bonne réponse : les deux tiers des réponses restent faux sur cette sélection.
Ce 6/18 n'est pas le score des 132 bases.

Le rapport des médianes de `decision_ms`, GLiNER / Julia, vaut **3,143**
sur cette série locale. Ce temps inclut les prétraitements et audits propres
à chaque candidat; l'appel adaptateur ajoute transport et gardes de
provenance. Il ne s'agit ni d'un ratio de forward seul, ni d'une mesure de
service produit, ni d'un temps extrapolable aux textes longs. L'initialisation
et les budgets natifs des profils restent distincts.

La médiane utilise la moyenne des deux valeurs centrales, le p95 le rang
`ceil(0,95 × n)`. Un processus neuf ne signifie pas un cache disque froid.
Les p95 décrivent cette série, sans garantie sous charge. Les répétitions
augmentent les observations temporelles, sans augmenter les neuf familles
indépendantes ni constituer un nouveau test de généralisation.

## Archives et limites de portée

| Archive locale | Contenu |
|---|---|
| `results/gliner-smoke-001` | Échec de chargement conservé, zéro prédiction scorée |
| `results/gliner-smoke-002` | Deux contrôles de chargement réussis |
| `results/context-base-gliner-001` | 132 sorties, référence, profil, provenance et seal |
| `results/context-base-gliner-analysis-001` | Analyse par domaine, split, langue et difficulté |
| `results/context-base-julia-gliner-001` | Comparaison appariée avec l'archive Julia de base |
| `results/context-length-gliner-001` | 192 réponses, 24 cibles infaisables et 162 enveloppes d'erreur mémoire |
| `results/context-length-gliner-analysis-001` | Détail domaine/langue/difficulté/longueur/position/split |
| `results/context-length-julia-gliner-001` | Comparaison sur tous les cas et les 192 appels réussis communs |
| `results/gliner-overflow-selection-001` | Première paire FR/EN à 8k conservée à l'identique |
| `results/gliner-overflow-probe-001` | Deux refus natifs avant forward, aucune évaluation de qualité |
| `results/gliner-overflow-validation-001.json` | Garde d'admission vérifiée, `quality_evaluation: not_run` |
| `results/context-model-timing-001` | 360 appels, six lancements et 162 mesures par candidat |
| `results/gliner-timing-validation-001.json` | Vérification des 15 fichiers scellés de la mesure répétée |
| `results/gliner-clean-stdlib-001.json` | Validation de la copie propre `83be31a`, sans poids ni runtime modèle |
| `results/gliner-notebook-proof-001.json` | Rescore notebook sans inférence, 132 sorties et métriques identiques |

Les archives sources de la base, de la longue et des deux contrôles de chargement ont été
relues par le validateur d'archive : leurs seals sont cohérents. Les grandes
traces restent dans `results/`, hors Git; ces chemins désignent les preuves
locales et ne rendent pas les archives disponibles dans un clone neuf.

La validation du banc sur l'environnement local annonce 221 tests, 217
réussis et quatre replays MCPs réels omis. La preuve de copie propre
`83be31a`, sous Python `-S`, archive **221 tests : 196 réussis, 25 omis,
zéro échec**. Les omissions sont explicites : dix contrôles JSON Schema
optionnels, onze fixtures nécessitant Node 24 et quatre replays MCPs réels.
Aucun modèle, poids, stack, téléchargement ni installation n'est requis
par cette validation. Le rescore dans un kernel neuf conserve les 132
sorties brutes et les métriques, sans nouvelle inférence; le notebook
source et l'archive initiale restent inchangés selon la preuve dédiée.

Les 15 fichiers du seal temporel ont été vérifiés; son identité est
`6d99a90a8aa1943811a265757a07af00b08c84a3dd8acff548d28e56ac9422c9`.

Les traductions et variantes d'une même famille sont corrélées : 132 bases
représentent 66 familles, les contextes longs neuf. Le documentaire teste
le choix de tâche; les sciences testent des choix sous hypothèses explicites,
sans preuve libre, document réel ni faisabilité chimique. Les annotations
documentaires restent des références par agent. Une confiance native n'est
pas une preuve de vérité ni une probabilité calibrée.

Les sources GLiNER sont vérifiées par contenu; les autres distributions
installées sont observées par versions et pins du lock, sans inventaire de
tous leurs fichiers. Aucun composant applicatif n'a été remplacé. Revue
humaine, autres langues, vrais documents longs, baseline LLM et cascade
gelée indépendante restent nécessaires avant toute qualification produit
ou seuil de recours à un LLM.
