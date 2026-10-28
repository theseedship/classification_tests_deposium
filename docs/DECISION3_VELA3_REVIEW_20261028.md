# Decision 3.0 et Vela 3.0 — revue du 28 octobre 2026

**D3 Ultra et D3 Turbo n'ont pas été évalués dans nos campagnes historiques.**
Le meilleur total local publié reste celui de **D3 classe 27B Q4 : 128/132
bases et 24/24 accords Mastra provisoires**, sur un checkpoint GGUF du
16 octobre. Ce résultat ne qualifie ni Ultra, ni Turbo, ni une nouvelle
révision du fichier D3. Les références restent à revoir humainement ; aucun
parcours produit n'est qualifié par ces scores.

Ultra mérite une comparaison sur les mêmes données. Sa version BF16 publiée
ne peut cependant pas être admise avec les ressources disponibles lors de
cette revue : **48,59 GiB de fichiers de poids**, avant le runtime et les
activations, contre **27,86 GiB de mémoire disponible estimée** sur le Mac.
Le premier palier lancé dans ce lot est **Vela 3 Fast, décisions seules,
CPU/F32**. Cette campagne est désormais terminée : **57/132 bases et 18/24
accords Mastra provisoires** ; voir les [résultats et limites](VELA3_FAST_RESULTS_20261028.md).
Le catalogue reste un relevé de sources, séparé des mesures.

Le [catalogue JSON](evidence/decision3-vela3-20261028/catalog.json) conserve les
12 identités complètes, les empreintes des métadonnées et sources inspectées,
les tailles et SHA256 LFS déclarés des poids, les dépendances externes et les
limites d'interprétation. Il décrit des sources, pas douze modèles exécutés.
Base du banc au début de la revue :
`26a26ffe57e5f98981b744a9673942797a8e8868`.

## Modèles recensés et coût de stockage

Les valeurs ci-dessous sont la somme des fichiers de poids présents dans
chaque dépôt, en GiB (`octets / 2^30`). **Ce ne sont pas des besoins de RAM.**
Les adaptateurs Vela ont des bases externes ; certains dépôts proposent
plusieurs têtes ou backbones alternatifs que l'on ne charge pas simultanément.
L'inventaire des métadonnées a été capturé à
`2026-10-28T20:39:56.022517+00:00`, sans télécharger ces douze ensembles de poids.

| Dépôt et révision inspectée | Poids du dépôt (GiB) | Interprétation |
|---|---:|---|
| [d3-ultra · 52ba9e7a](https://huggingface.co/vllm-sr/d3-ultra/tree/52ba9e7a00402f9560c7fba8c039608e7ddee7fb) | 48,593 | Nouveau candidat dense, BF16 ; non admis en mémoire |
| [d3-turbo · a0f3e9e5](https://huggingface.co/vllm-sr/d3-turbo/tree/a0f3e9e59ebd1202fe1d4de1c4c0f9a986758cbb) | 48,593 | Nouveau candidat dense ; pas une variante MoE de petite mémoire |
| [d3 · 20f37b9a](https://huggingface.co/vllm-sr/d3/tree/20f37b9a892acc13d4b07a4f3c4f11b2518c615c) | 48,593 | Source courante, distincte de notre ancien GGUF mesuré |
| [d3-flash · 13dc1cc8](https://huggingface.co/vllm-sr/d3-flash/tree/13dc1cc8ef23caefa765907e1d764751e5629f7d) | 15,637 | Classe 9B ; anciennes campagnes à leurs propres pins |
| [d3-mini · bd0090dd](https://huggingface.co/vllm-sr/d3-mini/tree/bd0090dd758d32ba59ef5c749910a8e87fc4391f) | 8,458 | Classe 4B ; ne pas substituer ce pin aux bases Vela |
| [d3-lite · 03560c26](https://huggingface.co/vllm-sr/d3-lite/tree/03560c26f5199c3c04129a2ccb38960c913635e0) | 1,590 | Classe 0,8B ; base Vela Lite différente |
| [vela3-fast · 9e338f39](https://huggingface.co/vllm-sr/vela3-fast/tree/9e338f39babc622f42e9bd8556398fe2d80d9f13) | 6,138 | Tous adaptateurs inclus ; backbone de décision seul : 1 521 771 272 octets, soit 1,417 GiB |
| [vela3-fast-vision · 1e13154c](https://huggingface.co/vllm-sr/vela3-fast-vision/tree/1e13154c1c2137654c79c4a08b912f0085bf9fe8) | 5,322 | Preview visuelle ; contient plusieurs backbones et adaptateurs |
| [vela3-lite · 2ac29e42](https://huggingface.co/vllm-sr/vela3-lite/tree/2ac29e42ecec3d067c4cb991bb5e6a933ea21fb1) | 0,207 | Adaptateurs/têtes ; ajouter la base D3 Lite épinglée |
| [vela3-mini · 5227b8a0](https://huggingface.co/vllm-sr/vela3-mini/tree/5227b8a0f2e86df53035b98dc45b21ecd8a8bc00) | 1,064 | Adaptateurs/têtes ; ajouter la base D3 Mini épinglée |
| [vela3-flash · 47c6eaae](https://huggingface.co/vllm-sr/vela3-flash/tree/47c6eaaef64e87a06a95767920e8357e5f5036f9) | 3,754 | Adaptateurs/têtes ; ajouter la base D3 Flash épinglée |
| [vela3-turbo · 575ec6f8](https://huggingface.co/vllm-sr/vela3-turbo/tree/575ec6f89afc8b7b0f3f1f7b12bccfc8d292ddb6) | 5,737 | Adaptateurs/têtes ; ajouter une base de classe 27B |

Les chiffres API de paramètres peuvent ne décrire que le fichier principal.
Pour Ultra, le [manifeste éditeur](https://huggingface.co/vllm-sr/d3-ultra/blob/52ba9e7a00402f9560c7fba8c039608e7ddee7fb/MODEL_MANIFEST.json)
détaille **25 624 600 064 paramètres texte, 460 730 096 vision et
1 305 600 readout**, soit **26 086 635 760 chargés**. La
[configuration](https://huggingface.co/vllm-sr/d3-ultra/blob/52ba9e7a00402f9560c7fba8c039608e7ddee7fb/config.json)
décrit un modèle dense Qwen3.5 à 64 couches, sans configuration d'experts.
D3, Turbo et Ultra ont les mêmes dimensions d'architecture dans les sources
inspectées. « Turbo » n'implique donc pas quelques milliards de paramètres
actifs dans un MoE. L'étiquette de famille des cartes ne remplace pas cette
lecture des configurations.

## Ce qui était déjà testé

Les campagnes CPU historiques ont mesuré D3 Edge, Lite, Nano, Mini et Flash,
ainsi que Vela 2.0 0,3B, 0,8B et 4B. Les résultats Vela sont respectivement
**65/132, 79/132 et 106/132 bases**, avec **18/24, 14/24 et 18/24 accords
Mastra provisoires**. Ces modèles Vela 2.0 ne sont pas Vela 3.0 : voir
l'[index consolidé](RESULTS_INDEX.md), les
[résultats Vela 2](MODEL_COMPARISON_VELA2_20261011.md) et le
[lot CPU 4B](LARGER_CPU_RESULTS_20261011.md).

La [campagne Metal du 16 octobre](NATIVE_DECISION_RESULTS_20261016.md) mesurait
Flash Q8 à 124/132, Flash Q4 à 122/132 et D3 27B Q4 à 128/132. Le dernier
avait un pic RSS de groupe de processus de 18,81 GiB. Ce RSS historique
n'est pas une prédiction du BF16 Ultra ni d'une autre longueur de contexte.

Le témoin D3 Q4 historique est
`ggml-org/vllm-d3-GGUF@de9670136f5ddd83e677c89ce041d5b9bb3b0dcb`,
fichier de **19 403 686 112 octets**, SHA256
`a5a341e8611dc5d916c8f4c693dbef4a68e57eb17d37914fd56dcb5a9221eb2d`.
Le [dépôt GGUF courant](https://huggingface.co/ggml-org/vllm-d3-GGUF/tree/992fe43f6e2f6e623f9c0c10ab9667c0ea56ed47)
est à `992fe43f6e2f6e623f9c0c10ab9667c0ea56ed47` : son Q4 fait
**19 403 686 208 octets**, SHA256
`2b6823fe1f1e2866f313b21922304d3a8037cceb1d68274ca258292832505009`.
Les empreintes et tailles diffèrent ; ces 96 octets seuls ne permettent pas
de conclure que les tenseurs ont changé. Le nouveau fichier reste `not_run`.

## Ultra : publications prometteuses, protocoles différents

La [carte Ultra épinglée](https://huggingface.co/vllm-sr/d3-ultra/blob/52ba9e7a00402f9560c7fba8c039608e7ddee7fb/README.md)
publie **87,2 sur SR-Text**, contre 83,1 pour Turbo et 81,4 pour D3.
SR-Text est une évaluation privée de l'éditeur : 10 411 requêtes,
73 495 questions et une moyenne de six domaines corrigée du hasard.
Elle ne permet pas de prévoir combien des 132 cas de notre corpus Ultra
réussira.

Sur le **Decision Index public** consulté le 28 octobre, Ultra obtient
**70,18**, contre 67,31 pour Turbo et 67,15 pour D3 v3.1.0. Mais l'entrée
Ultra a été évaluée à
`37fee01926f3de396620e794201b074fb427ac2d`, tandis que le checkpoint inspecté
ici est `52ba9e7a00402f9560c7fba8c039608e7ddee7fb`. Il faut conserver cette
différence d'identité, les versions de protocole et les dénominateurs.
Source : [données officielles du classement](https://huggingface.co/datasets/multimodalart/decision-index-leaderboard).

Ultra n'est pas supérieur dans toutes les tâches publiées. Sur **SR-Box**,
également privé, le score moyen sur dix domaines est **58,2 pour Ultra et
60,0 pour Turbo**, sur 5 678 questions et 4 984 images, avec succès défini
par IoU ≥ 0,5. Notre banc textuel actuel n'évalue ni les boîtes, ni le suivi
vidéo, ni les performances publiées sur GPU AMD MI325X.

## Vela 3 : nouvelles tâches et dépendances à respecter

Vela 3 Fast est un encodeur UltraBERT de 380M paramètres, avec son propre
backbone de décision distillé. Sa carte annonce anglais et 32K tokens ;
notre première campagne garde **les cas FR/EN existants et un budget de
4 096 tokens**, afin de rendre visible la performance hors de la langue
annoncée. Les décisions seules n'évaluent pas les routeurs spécialisés, les
entités, les relations, les spans d'appui ou les affirmations non soutenues.
Source : [carte Vela 3 Fast](https://huggingface.co/vllm-sr/vela3-fast/blob/9e338f39babc622f42e9bd8556398fe2d80d9f13/README.md).

Les variantes Lite/Mini/Flash/Turbo attachent des adaptateurs et têtes à un
D3 gelé. Leur petit volume de fichiers ne représente pas le modèle complet.
Le chargeur lit les bases suivantes dans **`vela3_config.json`** :

| Variante | Base externe effectivement épinglée par sa configuration |
|---|---|
| [Lite](https://huggingface.co/vllm-sr/vela3-lite/blob/2ac29e42ecec3d067c4cb991bb5e6a933ea21fb1/vela3_config.json) | `vllm-sr/d3-lite@9c10703193afc7c7d28c88201c0364bfbbf58320` |
| [Mini](https://huggingface.co/vllm-sr/vela3-mini/blob/5227b8a0f2e86df53035b98dc45b21ecd8a8bc00/vela3_config.json) | `vllm-sr/d3-mini@566da0ea398e27184472add700499245ed09af35` |
| [Flash](https://huggingface.co/vllm-sr/vela3-flash/blob/47c6eaaef64e87a06a95767920e8357e5f5036f9/vela3_config.json) | `vllm-sr/d3-flash@8b35c853b90e777595ec36bacae820fe08ea077a` |
| [Turbo](https://huggingface.co/vllm-sr/vela3-turbo/blob/575ec6f89afc8b7b0f3f1f7b12bccfc8d292ddb6/vela3_config.json) | `vllm-sr/d3-turbo@da17b5d0c860f7e5be6e2afebe67228b4bd24d0c` |

Ces quatre pins diffèrent tous des sources D3 courantes recensées plus haut.
La configuration Mini précise que le D3 Mini courant a des poids et un readout
différents. La configuration Turbo distingue aussi un pin interne absent du
Hub du snapshot public retenu. Le catalogue reprend le pin public demandé par
le chargeur ; aucune substitution par `main` n'est admise implicitement.

La [variante Fast Vision](https://huggingface.co/vllm-sr/vela3-fast-vision/blob/1e13154c1c2137654c79c4a08b912f0085bf9fe8/config.json)
est une preview distincte ; sa configuration cite
`athrael-soju/UltraVBERT@014dd536e8bb22fcd946e40ec8112f66efffcc53`.
Elle demande un corpus visuel et ne peut pas être déclarée testée à partir
de la campagne de choix textuels.

## Mémoire et compatibilité Mac / WSL

Le précontrôle initial donne **65 536 MiB de mémoire totale** et
**28 529,89 MiB disponibles estimés**, soit **27,86 GiB**. La méthode macOS
additionne les pages libres, inactives et spéculatives : ce n'est ni une
mesure d'allocation GPU, ni le `MemAvailable` de Linux. Ultra BF16 comprend
52 176 025 120 octets de poids, soit 48,59 GiB, avant activations, buffers,
conversions éventuelles, runtime et mémoire du système. Le téléchargement
et le chargement de ce candidat n'ont donc pas été engagés dans cette revue.

Son [runtime natif](https://huggingface.co/vllm-sr/d3-ultra/blob/52ba9e7a00402f9560c7fba8c039608e7ddee7fb/d3_runtime.py)
et son [wrapper](https://huggingface.co/vllm-sr/d3-ultra/blob/52ba9e7a00402f9560c7fba8c039608e7ddee7fb/modeling_d3.py)
utilisent un backbone BF16, un readout FP32 et SDPA. Les dépendances publiées
incluent `torch>=2.8` et `transformers==5.17.0`. Le device par défaut est CUDA
si disponible, sinon CPU ; MPS doit être demandé explicitement. L'acceptation
d'un device MPS par le code ne constitue pas une qualification sur notre Mac.
La synchronisation interne observée ne couvre que CUDA : des mesures MPS
devront synchroniser explicitement le GPU.

Ultra/Turbo conservent les points d'entrée `prepare`, `run`, `respond` et
`system_one`, avec un mode **`prefix_bidir` / `header-v1`** et un état encodé
une fois pour plusieurs questions. Les types textuels inspectés sont
**`choice`, `noul` et `score`** ; aucun type `nand` n'a été trouvé. Les types
visuels `box` et `track` exigent une couverture distincte. Un seul choix par
cas, comme dans notre premier protocole, ne mesure pas le gain promis pour
de nombreuses questions partageant le même état.

La voie GGUF/llama.cpp historique reste utile pour Mac/Metal et Linux/WSL,
mais aucune exportation officielle **Ultra GGUF ou MLX** n'a été trouvée dans
la recherche publique effectuée le 28 octobre. Cela décrit cette recherche,
pas une preuve d'absence universelle. Mettre simplement llama.cpp à jour ne
convertit pas les poids ni le nouveau protocole de readout Ultra.

Une [quantification communautaire Ultra W4A16 GPTQ](https://huggingface.co/evanrodgers/d3-ultra-W4A16-GPTQ/blob/239d3979a72632ea78596c0a34a09bb06305181e/README.md)
existe à `239d3979a72632ea78596c0a34a09bb06305181e` :
**16 065 797 408 octets**, soit **14,96 GiB de fichiers**. Sa carte décrit un
chemin NVIDIA avec un chargeur compact `d3q` qui n'est pas inclus dans ce
dépôt. Un chargement direct par Transformers déquantifie en BF16 et retrouve
le coût des poids complets. MPS/MLX/GGUF ne sont pas démontrés ; ce n'est pas
un raccourci Mac prêt à utiliser. L'accord top-1 publié sur 256 exemples est
une mesure de fidélité de quantification, pas notre exactitude. Les variantes
officielles [Turbo INT4](https://huggingface.co/vllm-sr/d3-turbo-INT4/tree/00ef9f546f920ad9b8d208c42c2664aa96b0cfc6),
[NVFP4](https://huggingface.co/vllm-sr/d3-turbo-NVFP4/tree/669cb9b1b3f6f9073640449e65d20678bbb0e226)
et [FP8](https://huggingface.co/vllm-sr/d3-turbo-FP8/tree/bdcda581c944e484c08b77dff1339b3ec1ad2cbf)
concernent Turbo et ne qualifient pas Ultra ou Metal.

## Ordre des essais et reproduction

1. Premier palier terminé : **Vela 3 Fast CPU/F32, décisions seules**, avec les profils
   `profiles/vela3-fast-cpu.json` et `profiles/vela3-fast-assets.json`, le
   runtime isolé et les mêmes cas figés. Conserver les erreurs, la couverture,
   les sorties brutes, les mesures et les archives avant toute synthèse.
2. Comparer Vela 3 Fast à Vela 2.0 et D3 sur les mêmes splits, en séparant FR
   et EN. N'étendre les adaptateurs de spans, de routage et d'appui qu'avec
   leurs propres cas et scorers ; les décisions seules ne les valident pas.
3. Essayer **Vela 3 Lite, puis Mini**, après vérification du stockage et de la
   mémoire de leurs bases exactes et du chargement des adaptateurs. Garder un
   seul modèle chargé ; relever CPU puis MPS/CUDA comme qualifications séparées.
4. Pour le palier 27B, conserver l'ancien D3 Q4 comme témoin, puis qualifier
   la nouvelle révision GGUF avant comparaison. Garder Ultra et Turbo
   `not_run` jusqu'à disposer d'un runtime et d'un format effectivement admis
   sur la machine choisie. Sur WSL/CUDA, revalider également les contraintes
   mémoire et les kernels ; la disponibilité d'une quantification n'est pas
   une campagne exécutée.

Le catalogue contient des URL `resolve/<revision>/...` et les SHA256 des
sources inspectées. Pour reproduire l'audit, lire ces fichiers aux révisions
complètes, vérifier leurs empreintes, puis traiter séparément chaque base
externe. Ne pas télécharger toute une collection pour une comparaison de
décisions seules. Les poids et archives brutes restent hors Git.

Ce lot est une évaluation de **modèles isolés**. Les tâches de compréhension,
sources, portée documentaire et choix d'outil renvoient aux contrats MCPs ;
l'exécution native historique renvoie à `deposium-inference`. Les variantes
spans/claims pourraient ensuite alimenter les packs de recherche/preuves.
Voir [local-only material, not distributed](PROTOCOL.md) et
[local-only material, not distributed](PROTOCOL.md). La liste courante des
sous-modules est découverte dans `.gitmodules` ; les composants Solid,
Desktop, CLI, Edge, recherche, ingestion et stockage ne sont pas qualifiés
par cette revue de modèles. Aucun service de la stack, base Supabase ou
déploiement Railway n'est requis pour ce premier palier ; aucun changement
de ces services n'est revendiqué ici.
