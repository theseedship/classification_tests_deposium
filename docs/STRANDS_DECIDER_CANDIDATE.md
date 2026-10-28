# Strands Decider v19 : candidat à mesurer

État au 3 octobre 2026 : **candidat documenté, aucune inférence Deposium exécutée**.
La proposition est de comparer le modèle local sur les décisions à choix fermé du
banc, puis, seulement si le résultat le justifie, d'étudier un raccordement au
vrai harness applicatif. Ni un score JevBench ni l'existence d'une API compatible
ne qualifient le routage Mastra ou le parcours produit.

## Pourquoi l'essayer, et ce que signifie « bat Jev »

[Strands Decider](https://github.com/strands-labs/strands-decider) publie un
classifieur de 1,9 milliard de paramètres : torse Qwen3.5-2B-Base, adaptation
LoRA de rang 16 et tête à pointeur. Il accepte `choice`, `noul` et `score`,
sans génération de texte. Le dépôt annonce **167/231** tâches publiques de
JevBench v1 à la fenêtre préenregistrée de 3 072 tokens, ou **168/231** à sa
fenêtre de service de 4 096 tokens. Son tableau comparatif place v19 devant
**Open-Jev 2B** (0,723 contre 0,645 sur les tâches publiques), mais au 50e rang
global des 89 systèmes de la version de tableau citée. Cela n'établit pas une
supériorité sur l'API `jev-1.13.0` employée ici : les tâches scellées, le score
composite, le matériel et la facture ne sont pas comparés. Les auteurs signalent
qu'un écart inférieur à environ dix tâches entre deux entraînements uniques
reste incertain. Leur médiane de 115 ms vient d'un RTX 3090 sous WSL2 ; aucune
latence Deposium ou sur notre matériel n'a été mesurée.

Sources primaires : [résultats JevBench et limites](https://github.com/strands-labs/strands-decider/blob/main/evaluation/jevbench.md),
[résultats de vitesse](https://github.com/strands-labs/strands-decider/blob/main/evaluation/results.md),
[architecture et inférence](https://github.com/strands-labs/strands-decider/blob/main/docs/inference.md).

## Identité des artefacts et coût matériel à vérifier

| Élément | Révision relevée | Ce qu'il faut archiver lors d'une campagne |
|---|---|---|
| [Code Strands](https://github.com/strands-labs/strands-decider/commit/890947e7ccd44c3de4115e26a7f46cc5c3147b44) | `890947e7ccd44c3de4115e26a7f46cc5c3147b44` | commit, lock Python, appareil et commande |
| [Checkpoint v19](https://huggingface.co/StrandsAgents/strands-decider-2B-hobson-v19/tree/bb282d786bc251fd4e3068de3ada9ddbb38127cd) | `bb282d786bc251fd4e3068de3ada9ddbb38127cd` | `MANIFEST.sha256`, empreintes des fichiers utilisés |
| [Torse Qwen](https://huggingface.co/Qwen/Qwen3.5-2B-Base/tree/b1485b2fa6dfa1287294f269f5fb618e03d52d7c) | `b1485b2fa6dfa1287294f269f5fb618e03d52d7c` | révision effective et empreintes des poids |

Le [fichier de provenance](https://huggingface.co/StrandsAgents/strands-decider-2B-hobson-v19/blob/bb282d786bc251fd4e3068de3ada9ddbb38127cd/provenance.json)
désigne cette révision Qwen comme **inférée depuis `main` au moment de
l'entraînement**, pas comme garantie de chargement : le loader Strands ne la
passe pas à Hugging Face. Pour une campagne, télécharger dans un cache local
ignoré de Git les deux snapshots à ces SHA, vérifier les manifestes, puis faire
charger des chemins locaux. Le checkpoint LoRA/tête fait environ **92 Mo** sur
le Hub ; les poids du torse, absents du checkpoint, ajoutent environ **4,5 Go**
selon la [documentation d'inférence](https://github.com/strands-labs/strands-decider/blob/main/docs/inference.md).
Ce sont des tailles disque annoncées, **pas une mesure de VRAM, RSS ni de
capacité sous la garde de 3 Gio** des anciens pilotes CPU. Aucun poids ou paquet
de calcul n'a été téléchargé pour cette fiche.

Le runtime amont demande Python >=3.10, PyTorch >=2.7, Transformers >=5.15 et
PEFT >=0.21 ; la [recette d'inférence](https://github.com/strands-labs/strands-decider/blob/main/docs/inference.md)
emploie notamment Torch 2.7.1, Transformers 5.17.0 et PEFT 0.21.0. Isoler ces
dépendances du socle Python standard du banc. La documentation prévient que la
version PyPI 0.1.0 n'a pas encore les extras `cuda`/`cpu`/`mps`/`mlx` décrits
pour la prochaine livraison : préparer un checkout épinglé et son environnement
dans une phase explicite. Préflight matériel avant tout téléchargement : RAM,
VRAM disponible, disque, CUDA/pilotes, et plafond de temps. CPU possible mais
annoncé bien plus lent. Le serveur local écoute `127.0.0.1` sans authentification ;
ne pas l'exposer au réseau ni lui transmettre de corpus privé sans autorisation.

## Ce que la recette d'entraînement publiée peut inspirer

La [recette v19](https://github.com/strands-labs/strands-decider/blob/main/training/README.md)
et sa [configuration](https://github.com/strands-labs/strands-decider/blob/main/configs/train.yaml)
sont publiques : `build`/`fetch`/`multistep`/`generated`/`adequacy`, étiquetage
par un Qwen3.5-4B figé, entraînement d'un parent, reprise de ses distributions
sur les cas multi-étapes, entraînement v19, calibration puis évaluation. Le
torse Qwen3.5-2B-Base reçoit un LoRA de rang 16 sur attention, MLP et couches
récurrentes ; la tête à pointeur est initialisée aléatoirement et entraînée
avec un taux distinct. `shuffle_options: true` contrôle l'ordre des choix ;
les distributions du parent apportent une cible de distillation, et
`kl_frozen_weight: 0.3` une régularisation KL vers la lecture gelée. Une
validation à 3 % figure au profil. Les options peuvent changer à l'inférence
sans réentraîner. Établir leur fiabilité sur une nouvelle décision demande
au moins des références annotées d'évaluation ; un nouvel entraînement ne
se justifie que si les mesures montrent ce besoin.

Les [sources et transformations](https://github.com/strands-labs/strands-decider/blob/main/data/README.md)
détaillent classification publique, ContractNLI équilibré par affirmation,
paires MuSiQue avec/sans réponse, BoardgameQA, questions documentaires générées,
et adéquation des réponses : notes humaines HelpSteer2 ramenées à deux classes
équilibrées, bande médiane écartée, plus exemples générés. HotpotQA sert à
l'évaluation seulement. Les exports synthétiques et cibles gelées sont
commités ; les corpus publics et poids sont téléchargés par la recette, sans
API payante lors de sa reproduction. Certains exports bruts ne se reconstruisent
pas octet pour octet aujourd'hui : les fichiers traités et `SHA256SUMS` font
foi. Les cibles gelées sont reliées **par position de ligne**, d'où le contrôle
strict des empreintes avant entraînement. Les auteurs annoncent environ 11 h
sur RTX 3090 24 Gio ou 1 h 10 sur 8 H100 ; ce n'est ni un budget local accordé
ni une preuve de reproduction ici.

Pour Deposium, retenir surtout le schéma de provenance, les permutations de
choix et la calibration après entraînement. Constituer d'abord des annotations
revues, négatifs plausibles et cas de repli par contrat, avec split groupé par
conversation/document/famille de traduction, puis mesurer séparément routage,
mathématiques et langues. Les références restent hors prompt et les gardes
d'accès déterministes. Ne pas transposer le `val_fraction` amont comme garantie
contre les fuites de variantes dans notre corpus ; aucune tête ni LoRA n'a été
entraînée pour Deposium.

## Contrat d'adaptation au banc

L'[API Strands](https://github.com/strands-labs/strands-decider/blob/main/src/strands_decider/schema.py)
accepte `POST /v1/systemone` avec `state`, `model`, et `questions` nommées.
Pour `bench.context-choice`, l'adaptateur commun doit envoyer une seule
question `choice` par cas, avec les **IDs d'options** comme clés de `criteria`
et leurs descriptions comme valeurs. Il conserve l'ordre reçu, sans tri par
libellé et sans inclure `reference`, split, famille, annotation ou action
attendue. Il archive le JSON de requête/réponse, `choice`, la distribution
`probabilities`, `confidence`, `usage.input_tokens`, `latency_ms`, temps côté
client et identité `/health`. Il vérifie que le choix et les clés de probabilité
correspondent exactement aux options et que les probabilités sont finies.
`confidence` est une concentration normalisée dérivée des probabilités ; elle
ne prouve ni justesse ni calibration sur Deposium. Un seuil d'abstention se règle
sur calibration uniquement et se juge sur test, avec couverture et dénominateur.

Le [serveur](https://github.com/strands-labs/strands-decider/blob/main/docs/inference.md#serve)
coupe silencieusement l'état au-delà de la fenêtre par défaut. L'essai doit
activer `--strict-window` et classer le refus HTTP 422 comme `unsupported`,
distinct de `error`, `timeout`, `missing` ou abstention. Vérifier sur un cas
volontairement trop long que l'option finale reste visible et qu'aucune réponse
tronquée n'est scorée. Tester séparément l'ordre des options et les traductions
FR/EN ; le score public ne qualifie ni ces langues, ni nos formulations, ni les
choix `search`/`stats`/`fallback`. Le serveur amont indique que la concurrence
n'est pas vérifiée : pilote séquentiel, un seul processus.

La forme HTTP ressemble à celle de JevBench, mais les auteurs précisent que la
compatibilité avec l'API Jev elle-même **n'est pas vérifiée**. Il faut donc un
adaptateur Strands explicite dans le moteur partagé CLI/notebook, avec profil,
schéma et tests de réponses invalides, sans réutiliser aveuglément l'adaptateur
`jev_http` ni recopier le routage Mastra. `search` et `stats` restent des choix
de premier niveau : droits, espaces, consentement et exécution des wrappers
demeurent déterministes dans la stack.

## Ordre de l'essai et critères de lecture

1. Préparer l'environnement isolé et la provenance ci-dessus, puis tester le
   contrat sur fixtures synthétiques, erreurs, refus de fenêtre, options
   permutées et réponses vides. `validate-registry` et les tests ordinaires
   doivent continuer de réussir sans poids ni service.
2. Rejouer les [24 demandes Mastra](../datasets/mastra-read-pilot-v0/README.md)
   FR/EN contre les **mêmes propositions `pending_human`**, avec les mêmes IDs,
   descriptions et splits (6 calibration, 18 test). Comparer par cas aux archives
   Jev, Julia, GLiNER et Indecis, dont [Jev 20/24](MASTRA_MODEL_COMPARISON.md).
   Rendre accords, régressions, repli `fallback` et taux de choix valides ; le
   résultat reste un accord exploratoire tant que les références ne sont pas
   revues et aucun outil n'est exécuté.
3. Rejouer les [local-only material, not distributed](PROTOCOL.md), ventilés par domaine,
   FR/EN et split, sans ajuster les prompts après lecture des tests. Comparer à
   l'archive [Jev 123/132](JEV_RESULTS.md) avec la même référence exploratoire.
   Faire ensuite un pilote de longueur borné sur les **300 variantes scorées
   par Julia** de la grille historique de 378, pour la comparaison appariée.
   Les 24 cibles infaisables restent exclues avant inférence. Examiner à part
   les 54 cas à 8k que la garde mémoire Julia avait arrêtés : enregistrer
   `unsupported` si leur encodage Strands dépasse 4 096 tokens. Ne pas annoncer
   d'avance le nombre de refus : il dépend du tokenizer et du prompt. Consigner
   longueur native, position de la preuve, refus et couverture à chaque palier.
4. Si le préflight ressources et les scores le justifient, reprendre le panel
   temporel des **18 mêmes bases**, avec échauffement documenté, temps de
   chargement séparé, médiane/p95 de décision et de bout en bout, RSS et VRAM
   mesurés, matériel et versions. Lire les archives Jev HTTP historiques ; ne
   pas engager de nouvelles requêtes payantes pour cette comparaison. Leurs
   272 ms médians incluent réseau et TLS, donc ils ne mesurent pas le temps de
   calcul serveur comparable au modèle local.

Chaque archive garde prompt, corpus, scorers, code/poids/torse, paramètres,
sorties brutes, erreurs et timings. Une reprise/rescore conserve l'archive
initiale. Rapport final : score et dénominateur par domaine/split/langue,
couverture `ok`/`unsupported`/`missing`/`error`/`timeout`/abstention,
calibration empirique sur nos cas si l'effectif le permet, et écarts appariés.
Les seuils de confiance, références et prompts ne changent pas pour obtenir un
résultat vert. Un éventuel essai de routage intégré appelle une révision précise
du vrai harness de `deposium_fullstack`, puis vérifie séparément les parcours
produit ; cette fiche ne les active pas.
