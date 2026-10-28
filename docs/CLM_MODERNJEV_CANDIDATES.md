# CLM et ModernJEV : deux candidats à évaluer

**Mise à jour du 10 octobre 2026 :** ModernJEV est maintenant mesuré sur CPU : 42/132 bases et 8/24 accords Mastra provisoires. [local-only material, not distributed](PROTOCOL.md). CLM reste non exécuté. Le cadrage daté ci-dessous est conservé.

Lecture de sources et métadonnées du 2 octobre 2026. **Aucun poids téléchargé,
adaptateur implémenté, entraînement ou appel d'inférence.** Les deux candidats
restent `not_run` et ne rejoignent pas le tableau des quatre modèles mesurés.

## Identités et intérêt

| Candidat | Révision examinée | Mécanisme | Intérêt proposé pour Deposium |
|---|---|---|---|
| `Contrastive-LM/CLM-v0.1-8B` | HF `e939398d4556fcd9400c76fa8c5a513202f42b0a`; code `bb42c6c5bf914fd449bed2f6ca65be80602cb1f7` | Deux têtes contrastives sur Qwen3-8B gelé; état et actions encodés séparément | Comparer sélection ouverte, propositions documentaires et spécialisation de têtes |
| `MaziyarPanahi/ModernJEV-Decide-Preview` | HF `d5b398ed03de073a00bc4e53acf53afda409445e` | ModernBERT, 149 605 633 paramètres, score scalaire par candidat lu avec le contexte | Pilote local de sélection d'action/outil, puis mesure du transfert aux autres domaines |

CLM fournit un classement parmi des candidats; ModernJEV est un prototype
indépendant inspiré du format de décisions Jev. Ni l'un ni l'autre ne génère
les arguments des outils ou une démonstration. Un choix correct ne qualifie
pas son exécution par la stack. Sources :
[CLM](https://huggingface.co/Contrastive-LM/CLM-v0.1-8B/tree/e939398d4556fcd9400c76fa8c5a513202f42b0a),
[ModernJEV](https://huggingface.co/MaziyarPanahi/ModernJEV-Decide-Preview/blob/d5b398ed03de073a00bc4e53acf53afda409445e/README.md).

## CLM : encodeur, cache et longueur à qualifier

Les quelque 75,6 Mo du checkpoint HF contiennent les têtes, pas Qwen3-8B.
Le [config](https://huggingface.co/Contrastive-LM/CLM-v0.1-8B/blob/e939398d4556fcd9400c76fa8c5a513202f42b0a/config.json)
exige des embeddings de dimension 4 096 avec pooling du dernier token.
Changer d'encodeur, de pooling ou de quantification constitue une variante
à qualifier séparément. Sa révision, son tokenizer et ses octets devront être
épinglés avant le pilote; le nom `qwen3-8b` d'un endpoint ne suffit pas.

Le [moteur](https://github.com/Contrastive-LM/CLM/blob/bb42c6c5bf914fd449bed2f6ca65be80602cb1f7/src/clm/engine.py)
associe contexte et question côté état, et les descriptions seules côté
actions. Il peut mettre les deux côtés en cache. Pour des actions fixes,
réutiliser leurs vecteurs est une hypothèse intéressante de gain; répéter
exactement un état déjà caché mesurerait un autre régime.

Le [wrapper d'embeddings](https://github.com/Contrastive-LM/CLM/blob/bb42c6c5bf914fd449bed2f6ca65be80602cb1f7/src/clm/embedder.py)
demande par défaut une troncature à 2 048 tokens, y compris pour les actions.
Son compteur d'usage compte les tokens des cache misses, pas les séquences
complètes. Le pilote devra refuser les dépassements avant appel et publier
les comptes natifs complets. Une hausse de fenêtre exige des limites cohérentes
dans ce wrapper et le serveur encodeur, plus une mesure mémoire.

Il existe un LRU d'embeddings distinct du cache de projections. Désactiver
`action_cache` ne supprime pas ce LRU. Son défaut de 200 000 vecteurs FP32
de dimension 4 096 représente une capacité théorique d'environ 3,05 Gio,
hors chaînes et overhead Python, pas une allocation observée. Borne mémoire,
reset de caches et identité du serveur devront être explicites.

Les performances publiées face à Jev dépendent des tâches et du cache;
les résultats de vérification de code utilisent des têtes spécialisées.
Ils ne mesurent pas ce checkpoint sur notre corpus. Les métadonnées HF
déclarent l'anglais; le français reste à tester.
[Conditions annoncées](https://github.com/Contrastive-LM/CLM/tree/bb42c6c5bf914fd449bed2f6ca65be80602cb1f7#results).

## ModernJEV : spécialisation et transfert

La fiche distingue le checkpoint entraîné sur **60 000 décisions** d'une
démonstration d'automatisation d'entraînement sur **6 000 décisions**. Les
coûts et durées de ces deux expériences ne prédisent pas ceux de Deposium.

| Résultat de l'auteur, pas une mesure Deposium | Exactitude |
|---|---:|
| Choix de l'action suivante | 850/1 158 — 73,40 % |
| Choix de l'outil | 337/542 — 62,18 % |
| When2Call, famille non entraînée | 1 256/3 652 — 34,39 %, contre 35,46 % pour la référence majoritaire |

La possibilité de fournir de nouveaux labels n'établit donc pas une bonne
généralisation. Les noms des labels participent à l'entrée et peuvent changer
le choix. La limite annoncée de 4 096 tokens inclut la paire et ses tokens
spéciaux. Les 23,6 ms annoncées concernent un forward GPU pour **un candidat**,
hors tokenisation, pas une décision complète. Anglais déclaré; français,
maths/chimie et latence CPU Deposium restent non mesurés.
[Fiche et évaluations publiées](https://huggingface.co/MaziyarPanahi/ModernJEV-Decide-Preview/blob/d5b398ed03de073a00bc4e53acf53afda409445e/README.md).

Le [helper publié](https://huggingface.co/MaziyarPanahi/ModernJEV-Decide-Preview/blob/d5b398ed03de073a00bc4e53acf53afda409445e/predict.py)
sérialise l'état comme JSON conversation/outils, puis encode une paire avec
`label: description`. Son interface liste de descriptions permet de garder
les IDs techniques du banc hors du modèle; elle répète alors la description
comme label. Cette projection devra être figée et conservée dans l'archive,
sans inventer des outils ou politiques absents du cas. Le helper tronque
automatiquement `only_first` à 4 096 avant de signaler `truncated` : il faut
donc contrôler chaque paire avant son appel. Son modèle par défaut pointe
vers `OpenMed/...`; passer explicitement le chemin local vérifié du checkpoint
`MaziyarPanahi/...`. Ne pas confondre compatibilité d'interface et même entrée.

## Ressources et proposition de pilote

Le relevé ponctuel local indique une RTX 5060 de 8 151 Mio, dont 725 Mio libres,
et 13 766 Mio de RAM disponible. Ce n'est pas une réservation. Par estimation,
8 milliards de paramètres en 16 bits représentent environ 16 Go de poids,
avant allocations de service. Le chemin CLM de référence ne tient donc pas
entièrement sur cette carte en 16 bits. L'exemple amont a été réduit à 2k pour
une carte de 24 Go; cela ne garantit pas 8k sur cette capacité.
[Modification amont](https://huggingface.co/Contrastive-LM/CLM-v0.1-8B/commit/e939398d4556fcd9400c76fa8c5a513202f42b0a).

ModernJEV est beaucoup plus petit : les métadonnées safetensors annoncent
149 605 633 paramètres FP32, soit environ 598 Mo de tenseurs par calcul,
hors runtime/activations. Un pilote CPU borné paraît plus accessible;
aucune consommation réelle n'est encore mesurée.
[Métadonnées HF](https://huggingface.co/api/models/MaziyarPanahi/ModernJEV-Decide-Preview/revision/d5b398ed03de073a00bc4e53acf53afda409445e).

Proposition, à figer avant les premières prédictions :

1. Commencer sans entraînement par les 132 cas historiques identiques, avec
   `bench.context-choice`, le moteur/scorer commun et les quatre archives
   existantes. Garder leur statut exploratoire et leurs références à revoir.
2. Épingler toutes les sources, poids, tokenizer, sérialisation et backend;
   contrôler chaque séquence complète, sans accepter de troncature silencieuse.
   ModernJEV requiert ce contrôle pour chaque paire contexte/candidat.
3. Mesurer premier appel, décision complète, RSS/VRAM et temps d'encodage.
   Pour CLM, séparer caches vides, actions réutilisées avec états nouveaux,
   et répétitions exactes. Dénominateurs et nombres de candidats restent visibles.
4. Reprendre progressivement les longueurs communes seulement après admission
   mémoire; ne pas attribuer les temps de cache ou de refus à une inférence.
5. Relier une spécialisation ultérieure au [local-only material, not distributed](PROTOCOL.md) :
   `mcps.document-task-plan`, `mcps.intent-cascade`, puis sélection de source.
   Garder les droits, disponibilités, choix explicites et budgets déterministes.
   Maths/chimie demandent des oracles indépendants; le ranking ne prouve pas le calcul.

Le pilote CLM attend un backend adapté et vérifiable. Aucun service n'a été
arrêté ou créé, aucun calcul distant acheté. ModernJEV reste une piste pour
la suite. La revue humaine R1 et les familles indépendantes R2 de la
[local-only material, not distributed](PROTOCOL.md) restent nécessaires avant toute spécialisation.
