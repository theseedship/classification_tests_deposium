# Pilote Indecis ouvert, sans entraînement

Protocole fixé le 2 octobre 2026, avant les premières prédictions. Modèle
isolé, preuve A; aucun composant Deposium remplacé. Ce pilote mesure le
backbone brut avec les choix dynamiques d'Indecis. Il ne mesure pas une tête
spécialisée entraînée sur les décisions Deposium.

## Identités et limites

- Indecis : `339e191405ac9be90f6857f810f478b3312b7f35`, sources officielles
  compilées localement avec Go 1.27.1, `GOEXPERIMENT=simd`, CGO désactivé.
  Le calcul utilise le chemin flottant officiel, sans `WithInt8`, et sans
  cache d'embeddings entre requêtes. Les options sont réencodées à chaque appel.
  Archive officielle `go1.27.1.linux-amd64.tar.gz` vérifiée : SHA-256
  `63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445`.
- Backbone : `hotchpotch/bekko-embedding-v1-a8m`, révision
  `c721113d59a1d91b447450324f51c4b3332c924a`; seuls `config.json`,
  `model.safetensors` et `tokenizer.json` sont téléchargés (246 317 545 octets).
- Empreintes modèle dans [indecis-assets.json](../profiles/indecis-assets.json),
  sources, compilateur et binaire dans les manifests du runtime. Le worker
  charge uniquement des fichiers locaux. Aucun téléchargement sur import,
  test ordinaire, initialisation du candidat ou inférence.
- Deux threads, un worker et une requête à la fois; garde RSS 3 072 Mio,
  initialisation 120 s, requête 30 s. La surveillance RSS reste une garde
  périodique avec arrêt du worker, pas une réservation mémoire système.
- Budget d'entrée : 4 096 tokens natifs par séquence encodée. Ce plafond
  expérimental ne qualifie ni une fenêtre universelle ni la qualité à 4k.
  Le défaut upstream de 256 tokens est explicitement remplacé.
- Aucun entraînement, appel Jev/LLM, génération de corpus, réduction de
  vocabulaire ou ajustement après lecture des scores dans ce pilote.

L'installation est locale au banc : runtime Go sous `.cache/`, poids sous
`models/`, tous hors Git. Les assets modèle restent sous 1 Gio. Le SDK Go et
ses caches de compilation sont comptés séparément de ce budget de poids.

## Entrée figée et absence de troncature

Le vrai `DecideOpen` reçoit le contexte comme texte à encoder. Chaque choix
utilise sa description comme `Candidate.Name`, avec `Candidate.Description`
vide; la question devient `Instructions`. Le code officiel construit alors
le texte candidat `description + "\n" + question`. Aucun exemple de réponse
n'est ajouté. Les identifiants servent au transport et au remapping; ni
référence, split, difficulté, domaine, ni identifiant de cas ne sont encodés.

Le worker compte les tokens complets du contexte et de chaque texte candidat,
puis compare ces IDs à ceux du chemin `TokenIDs` effectivement employé par
Indecis. Tout dépassement devient `unsupported/indecis_context_overflow`
ou `unsupported/indecis_option_overflow`, avant l'inférence, sans raccourcir
le texte ni déplacer sa preuve. Les
séquences candidates et contexte sont comptées séparément, sans assimiler
leur somme à une fenêtre de cross-encoder. Les mêmes octets sont utilisés
pour les autres candidats du banc; leurs tokenizers ne sont pas interchangeables.

La sortie native, les distributions, les temps et les observations mémoire
sont archivés. Les probabilités issues de similarités ne sont pas calibrées
par ce pilote. L'option sémantique « information insuffisante » est distincte
du statut technique d'abstention. `missing`, `unsupported`, `error` et `timeout`
restent distincts. Une garde fatale ferme le worker; les demandes suivantes
ne déclenchent pas de nouvelle inférence et restent visibles dans la couverture.

## Campagnes et critères de poursuite

1. Contrôle de chargement : les deux premiers cas des bases figées, dans une
   archive séparée. Arrêter et corriger le runtime si le protocole échoue;
   conserver toute archive échouée.
2. Base : les 132 cas FR/EN de `datasets/context-choice-v1/cases.jsonl`, SHA-256
   `767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616`.
   Publier tous les splits et le test seul, langues, domaines et difficultés.
3. Longueurs : les 378 variantes déjà produites dans
   `results/context-sentinels-001/lengths/cases.jsonl`, SHA-256
   `f721aec7ff08b3b4be6a2e3dcb5dd88ae2b1c0bea3a7fcf6f9ab0aefd92e492a`.
   Les 24 cibles impossibles restent exclues par le garde commun. Paliers
   100–8 000 en tokens Julia de référence, positions début/milieu/fin. Aucun
   texte régénéré pour Indecis. Tout dépassement natif reste dans le dénominateur.
4. Temps : les mêmes 18 bases de calibration de
   `results/context-sentinels-001/base.jsonl`, trois lancements successifs,
   un premier appel, cinq échauffements et trois passages complets par
   lancement : 180 appels, dont 162 mesures. Ne pas relancer les autres modèles;
   comparer aux mesures historiques en indiquant la différence de session.

Le fichier des 18 sentinelles porte le SHA-256
`cc2e19abf97f777a762a4c685ab2a2660f02f3d158ee2dbb4fba4ef516fa7ddb`.
Le scorer commun et ses dépendances conservent le SHA-256
`d10a8b962ae2722c83218771fdffb4e16925d263fcca7d780cd14d4cab5a7084`.
Le temps `inference_ms` couvre l'appel natif `DecideOpen`, préparation des
options comprise; `decision_ms` inclut aussi le préflight et les audits du
worker. `encoding_info.tokens` rapporte la plus longue séquence; la somme
des tokens réellement présentés au modèle est tracée séparément.

Budget maximal : 692 demandes prévues, dont au plus 668 appels candidats
après les 24 exclusions communes, contrôle de chargement compris. Arrêt
contrôlé si une campagne dépasse 15 minutes; conserver une archive partielle
et ses cas manquants. Les erreurs de qualité ne justifient aucun changement
de données, prompt, modèle ou scorer pendant cette série.

Les bases représentent 66 familles FR/EN, les longues et répétitions seulement
9 familles de calibration. Les références sont `agent_only`. Un score faible
du backbone brut ne réfute pas la spécialisation par entraînement; un score
élevé ne qualifie pas un calculateur, un routage intégré ou un seuil LLM.

## Lien avec Deposium et suite

Les contrats de stack et leurs propriétaires restent dans le registre commun,
actualisé par l'inventaire de campagne. La capacité isolée `bench.context-choice`
compare des décisions documentaires, mathématiques et chimiques; tous les
composants applicatifs restent omis avec motif `model_isolated_only`.
Les gitlinks du parent, HEAD des sous-modules et services réellement exécutés
restent distincts. Aucun service de la stack n'est démarré pour ce pilote.

Une spécialisation ultérieure utilisera de nouvelles familles revues, avec
train/calibration/test séparés. Elle sera comparée à GLiNER + LoRA et Jev sur
la même tâche explicite. Voir [la piste Indecis](INDECIS_CANDIDATE.md) et
[local-only material, not distributed](PROTOCOL.md).

## Exécution explicite

Après préparation du runtime et validation des manifests, depuis la racine
du banc (choisir de nouveaux noms d'archives à chaque exécution) :

```bash
timeout --signal=INT --kill-after=10s 900s python3 -m deposium_bench run \
  --dataset datasets/context-choice-v1/cases.jsonl \
  --profile profiles/indecis-open-cpu-context.json \
  --stack-root ../deposium_fullstack --max-new-cases 2 \
  --output results/indecis-smoke-NEW

timeout --signal=INT --kill-after=10s 900s python3 -m deposium_bench run \
  --dataset datasets/context-choice-v1/cases.jsonl \
  --profile profiles/indecis-open-cpu-context.json \
  --stack-root ../deposium_fullstack --output results/context-base-indecis-NEW

timeout --signal=INT --kill-after=10s 900s python3 -m deposium_bench run \
  --dataset results/context-sentinels-001/lengths/cases.jsonl \
  --profile profiles/indecis-open-cpu-context.json \
  --stack-root ../deposium_fullstack --output results/context-length-indecis-NEW

timeout --signal=INT --kill-after=10s 900s python3 -m deposium_bench benchmark-timing \
  --dataset results/context-sentinels-001/base.jsonl \
  --profile profiles/indecis-open-cpu-context.json \
  --stack-root ../deposium_fullstack --launches 3 --warmup 5 --passes 3 \
  --output results/context-indecis-timing-NEW

python3 -m deposium_bench analyze-context \
  --archive results/context-base-indecis-NEW --output results/indecis-analysis-NEW
```

Le code de sortie d'une campagne de qualité peut être 1 si des choix sont
faux ou non supportés : lire les statuts et le nombre de cas scorés dans
l'archive, sans assimiler ce verdict à un crash du worker.

Sources primaires : [Indecis épinglé](https://github.com/Bornholm/indecis/tree/339e191405ac9be90f6857f810f478b3312b7f35),
[backbone épinglé](https://huggingface.co/hotchpotch/bekko-embedding-v1-a8m/tree/c721113d59a1d91b447450324f51c4b3332c924a).
