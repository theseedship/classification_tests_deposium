# Passages multilingues : résultats CPU du 15 octobre 2026

**Conserver BGE pour le classement avec les profils mesurés.** Sur les quatre
rotations du split test, D3-lite seul classe moins bien les passages et coûte
beaucoup plus de temps CPU. La combinaison par grades D3 puis départage BGE
n'améliore ni le premier passage ni le rappel à trois passages. Ses décisions
de soutien et de réponse possible produisent trop de faux positifs pour servir
de validation automatique des preuves.

Ce constat concerne **D3-lite et cette projection de choix**, sans entraînement.
Il ne tranche pas pour tous les modèles de décision, un reranker entraîné à
cette tâche, ou une autre combinaison. Jev API n'a pas été appelé. Les 22
observations historiques et leurs classements restent conservés séparément.

## Classement : contrôle équilibré

Corpus source `7ed178d`, inchangé : 1 536 cas synthétiques, 24 familles. Ce pilote
utilise **les 512 cas du split test, soit huit familles**, les six langues
FR/EN/DE/ES/IT/PT, huit directions avec FR↔EN, deux vues et quatre rotations.
Les splits train et calibration ne sont pas utilisés pour adapter le candidat.
Les références et traductions n'ont pas encore été revues humainement.

Un pool contient quatre passages. Le remplacement choisit un grade 3/2/1/0
pour chaque paire question/passage, puis trie ces grades ; une égalité garde
l'ordre d'entrée. Le complément utilise BGE pour départager ces égalités.
Aucun passage n'est supprimé ; une réfutation reste une preuve pertinente.

| Méthode | nDCG@1 | nDCG@3 | Rappel@1 | Rappel@3 | Médiane CPU / pool | p95 |
|---|---:|---:|---:|---:|---:|---:|
| BGE v2-m3 INT8 natif CPU | **0,922** | 0,934 | **0,779** | **0,923** | **0,236 s** | 0,908 s |
| D3-lite, grades seuls | 0,701 | 0,808 | 0,510 | 0,892 | 4,411 s* | 8,446 s* |
| D3-lite + BGE pour les égalités | **0,922** | **0,935** | **0,779** | **0,923** | 4,654 s* | 9,354 s* |
| Contrôle : ordre d'entrée sans modèle | 0,442 | 0,635 | 0,250 | 0,750 | — | — |

nDCG : 480 cas éligibles sur 512, tous observés ; 32 cas sans gain idéal ont
une métrique non définie. Rappel : 416/512 éligibles, tous observés ; 96 sans
passage pertinent restent non définis. Ces métriques ne sont pas des taux de
réponses finales correctes. Le gain nDCG@3 du complément est faible et descriptif,
sans amélioration de la capture d'un ensemble suffisant à trois passages :
**288/352** cas répondables avec BGE comme avec le complément, **281/352** avec
D3 seul. Appui et réfutation sont conservés ensemble à trois passages dans
**64/64** conflits avec BGE et le complément, contre **60/64** avec D3 seul.

BGE a réellement évalué les 512 pools. Les 2 048 choix logiques de pertinence
D3 ont été réattribués depuis **264 entrées visibles strictement identiques**
déjà archivées : zéro nouvel appel D3 pour les rotations. Les temps marqués *
sont des sommes des temps physiques antérieurs, projetées par pool sans cache,
et ajoutées à BGE pour la combinaison ; aucun pipeline composé n'a été chronométré.
La médiane D3 de classement représente environ 19 fois celle de BGE dans ce
montage. BGE inclut HTTP local, `docker exec` et `curl`, pas seulement son forward.

D3 est derrière BGE dans chacune des huit directions. Les
[tableaux détaillés](evidence/passage-order-control-20261015/report.md)
donnent les langues, scénarios, vues, rotations et égalités. BGE est faible sur
`distributed_binding` (0,417 en nDCG@1) ; D3 seul atteint 0,479, mais le contrôle
sans modèle atteint 0,583 dans cette famille. Ce petit sous-ensemble justifie
une inspection des références et des preuves distribuées, pas une substitution.

## Pourquoi l'essai initial semblait meilleur

Le premier lot comportait 128 cas, uniquement la rotation 0. Son ordre auteur
était déjà parfait : **garder les passages dans l'ordre donnait nDCG@1 = 1 et
nDCG@3 = 1**. D3 seul y atteignait 0,989, contre 0,922 pour BGE. Ce résultat
ne pouvait pas être attribué au modèle. Nous avons donc conservé cet essai et
ajouté les quatre rotations existantes, sans changer les références, les prompts,
les règles de classement ou les seuils après observation.

Le meilleur grade D3 est partagé dans **436/512 pools** ; tous les pools
contiennent au moins une égalité. Le départage a donc un effet matériel :
avec les quatre ordres à poids égal, le score D3 seul tombe à 0,701. Les
[exports initiaux](evidence/passage-cpu-20261015/report.md) restent historiques ;
le contrôle équilibré constitue la comparaison principale.

## Soutien et possibilité de répondre : seulement 128 cas initiaux

Ces tâches sont distinctes du classement. Les décisions sur un pool complet
ne sont pas extrapolées aux pools réordonnés. Les dénominateurs incluent les
vues et traductions liées, pas autant de faits indépendants.

| Tâche D3-lite | Résultat | Risque observé |
|---|---:|---|
| Grade exact de pertinence | 229/512 choix, 44,7 % | Classes intermédiaires mal distinguées ; nombreuses égalités |
| Soutien / réfutation / insuffisant | 443/768 choix, 57,7 % | Seulement **102/215** appuis prédits sont de vrais appuis ; **80/290** réfutations prédites sont correctes |
| Répondable / insuffisant / contradictoire | 88/128 pools, 68,8 % | **36/88** pools répondables sont refusés, dont **34** fausses contradictions ; 4/24 pools insuffisants sont acceptés |

D3 retrouve 102/104 vrais appuis et 80/80 vraies réfutations, mais cela mesure
le rappel de ces classes, pas la fiabilité d'un appui prédit. Parmi les 584
paires insuffisantes, il invente 113 appuis et 210 réfutations. Il détecte les
16 vrais pools contradictoires, tout en déclarant un conflit dans 34 pools
répondables. Un filtre bloquant ferait donc perdre beaucoup de réponses valides.

Coûts CPU projetés sur les 128 pools : soutien de toutes les affirmations
**8,330 s** de médiane / **9,605 s** p95 ; décision de réponse possible
**1,476 s** / **5,203 s**. Ils s'ajoutent au classement si ces fonctions sont
activées. Aucun seuil de confiance n'a été calibré. Les matrices de confusion,
précisions/rappels et résultats par langue sont conservés dans le
[JSON du contrôle](evidence/passage-order-control-20261015/analysis.json),
section `original_rotation_zero` ; les tableaux initiaux donnent aussi les
comptages par direction. Pas d'acceptation automatique de preuve ni de garde
bloquante recommandée avec ce profil.

## Ressources et véritable chemin natif

| Candidat | Taille des poids | Mémoire observée | Exécution |
|---|---:|---:|---|
| BGE v2-m3 INT8 | 569 705 899 octets, 0,531 Gio ONNX | VmHWM processus **0,908 Gio** ; pic cgroup conteneur **0,884 Gio** | 2 CPU, ORT 2 threads, pool de sessions 1, plafond conteneur 4 Gio |
| D3-lite | 1 707 072 248 octets, 1,590 Gio safetensors | RSS worker maximal échantillonné **2,214 Gio** | Backbone 852 985 920 paramètres BF16, tête 261 120 FP32, 2 threads |

Les portées mémoire diffèrent : worker D3 échantillonné contre processus
serveur/conteneur BGE, avec runtime et initialisation. Les deux candidats ont
été exécutés successivement ; aucun pic RAM d'un pipeline simultané n'est mesuré.
Les poids, le RSS et le plafond de sécurité sont des mesures distinctes.
CPU hôte Core Ultra 5 235HX ; temps descriptifs sous pression hôte variable.

Le pilote appelle le **vrai serveur Rust TurboV3 et son reranker ONNX**, dans
un conteneur CPU temporaire isolé, avec les mêmes poids, tokenizer et ORT que
l'image locale. Le service actif CUDA n'est pas sollicité pour l'inférence ni
reconfiguré. Son binaire CUDA ne démarrait pas sans GPU : le préflight 001 est
archivé avec zéro cas scoré. Un exécutable natif CPU existant a été épinglé et
monté en lecture seule pour les essais 002/003. Son hash et le provider CPU
sont vérifiés avant les requêtes. **La révision source exacte de cet artefact
n'est pas établie** ; son hash fait foi, pas le HEAD local TurboV3. Voir le
[protocole et toutes les identités](PASSAGE_CPU_PILOT_20261015.md).

D3 utilise l'adaptateur existant, le helper et les poids natifs à la révision
`a8d25a91ef75552803f7009d25b7bd435991abd9`. 728 appels physiques complets
couvrent 1 408 choix logiques initiaux : 264 pertinence, 392 soutien et 72 réponse
possible après déduplication exacte. Aucun échec technique. Les plafonds mémoire,
délais et réserves hôte n'ont pas été relevés. La phase D3 a duré environ
17 min 23 s ; le contrôle BGE 512, 164,925 s initialisation/archivage compris.
Tous les conteneurs créés par ce pilote ont été supprimés avec leurs volumes
anonymes après capture des logs.

La fenêtre MCPs de 384 caractères n'est pas exécutée ici : `head_384` est une
vue synthétique du pack. Toutes les 2 048 paires BGE du contrôle ont au plus
245 tokens, sous son plafond 512. Recherche initiale, sélection de fenêtres,
outils MCPs, routage intégré, citations, CLI/chat et réponses finales restent
non mesurés. L'inspection des appels MCPs a aussi repéré un nom de reranker
par défaut trompeur dans les métriques ; le pilote vérifie les artefacts et
le provider effectifs, sans modifier l'application.

## Conservation et reproduction

Sources gelées : `551edba` pour D3, `8d8ccba` pour BGE 128 et `ccb1b99` pour
BGE 512. Le correctif ultérieur du rendu Markdown stabilise seulement l'ordre
des lignes du nouveau rapport ; aucune mesure ni référence n'est changée.
Les sources gelées sont aussi conservées séparément des champs automatiques
`source_archive: not_captured`, qui restent inchangés.

Captures locales scellées et ignorées par Git, dans le checkout principal :

- `results/passage-d3-lite-cpu-20261015-001` : requêtes physiques/logiques, sorties et scores initiaux ;
- `results/passage-bge-cpu-20261015-001` : échec préalable, zéro cas scoré ;
- `results/passage-bge-cpu-20261015-002` et `...-003` : 128 puis 512 classements CPU natifs ;
- `results/passage-comparison-20261015-001` : analyse dérivée initiale ;
- `results/passage-rerank-preflight-20261015` : profils absolus, reçus, sources gelées, artefact CPU, logs et validations.

Le producteur versionné vérifie les sceaux, les identités natives, l'export,
les permutations et la correspondance exacte entre chaque choix D3 et son
entrée visible. Les agrégats publics excluent secrets, chemins privés et poids.
Les anciens JSON sont reproduisibles byte à byte ; leur ancien rendu Markdown
varie dans l'ordre des lignes après relecture du JSON trié, sans changement de
valeur. Le nouveau producteur corrige cet ordre ; JSON **et** Markdown du
contrôle sont régénérables à l'identique depuis les agrégats publics, sans modèle :

```bash
python3 -B scripts/analyze-passage-order-control.py \
  --render-json docs/evidence/passage-order-control-20261015/analysis.json \
  --output results/passage-order-report-reproduced
```

Pour recalculer les agrégats depuis les trois captures privées, utiliser
`--choice-archive`, `--original-baseline-archive` et `--balanced-baseline-archive`
à la place de `--render-json`, avec un dossier de sortie neuf. Les hashes des
sceaux et producteurs figurent dans le JSON. Les deux poids D3 retéléchargés
pour ce lot sont supprimés après contrôle de leurs hashes et des sceaux ;
configs/tokenizers, runtime, artefact CPU et toutes les captures restent conservés.
Un nouveau forward D3 nécessite de retélécharger la révision épinglée.

## Vérifications

Depuis un clone Git propre à `ccb1b993`, sans poids ni service externe :
**637 tests exécutés, 7 ignorés, zéro échec** ; registre valide, pack régénéré
à l'identique et dataset valide avec 1 536 cas / 24 familles. Dépendance de
validation isolée : `jsonschema==4.26.0`. Après le seul correctif de stabilité
du rendu à `7365ab62`, **six tests ciblés** passent dans ce clone, dont la
régression de relecture JSON trié ; la suite entière n'a pas été répétée.
Les sorties publiques finales du contrôle sont reproduites byte à byte depuis
leur JSON et depuis les captures scellées, sans nouvelle inférence. Les cinq
archives et les 31 fichiers D3 ont été vérifiés avant suppression des seuls
deux poids du lot : **1 707 072 248 octets** libérés. Logs et reçus hors Git.

## Suite utile

Faire relire les références de ces huit familles, puis constituer des cas issus
de documents réels avec provenance des passages et preuves suffisantes attendues.
Pour BGE, examiner d'abord les preuves réparties entre plusieurs passages. Pour
un modèle de décision, tester sur les mêmes cas un candidat plus robuste ou un
classement pair-à-pair pourrait être une nouvelle expérience ; il faudra en
mesurer le coût, les égalités et les faux appuis. Aucun fine-tuning ni ajout au
chat n'est justifié par les seuls résultats présents.
