# Pilote Decision 3.0 CPU — 11 octobre 2026

Protocole fixé avant les premières prédictions à `b8d01be`. Ces trois candidats ne changent
ni les références, ni les 132 bases FR/EN, ni les 24 propositions Mastra.
Leur état initial était `not_run` ; les résultats ci-dessous datent du lot exécuté
le 11 octobre. Aucun score amont n'est transposé.

| Modèle | Révision HF | Paramètres backbone BF16 | Poids backbone, octets | Readout FP32, éléments |
|---|---|---:|---:|---:|
| [d3-edge](https://huggingface.co/vllm-sr/d3-edge) | `18d61df78684675463af9ae732872478845c5a79` | 594 321 600 | 1 188 677 968 | 261 120 |
| [d3-lite](https://huggingface.co/vllm-sr/d3-lite) | `a8d25a91ef75552803f7009d25b7bd435991abd9` | 852 985 920 | 1 706 027 688 | 261 120 |
| [d3-nano](https://huggingface.co/vllm-sr/d3-nano) | `3aeb1c22a5632aac72353c36b3d0111c40e7dbf4` | 2 213 241 664 | 4 426 555 160 | 522 240 |

Les nombres viennent des métadonnées HF et sont contrôlés contre les headers
safetensors. Le backbone comprend le module de vision (annoncé environ
0,10B pour edge/lite et 0,33B pour nano), même lors des choix textuels.
Le readout est distinct : 1 044 560 / 1 044 560 / 2 089 040 octets.
Poids sur disque, RAM RSS du processus et réservation GPU sont des mesures
différentes. Les snapshots déclarent Apache-2.0.

## Interface et périmètre

La famille expose Choice, Noul et Score sans génération de texte, avec entrée
texte/JSON et capacités image/vidéo déclarées. Ce lot utilise **uniquement
Choice textuel** : 76 cas documentaires, 28 mathématiques, 28 chimiques,
66 familles FR/EN, puis 24 propositions recherche/statistiques/repli.
Les descriptions et le contexte restent complets, les IDs deviennent c0…
puis sont remappés ; annotations et justifications restent hors entrée.

Le bridge appelle le vrai runtime `D3.from_pretrained` puis ses méthodes
`prepare`, `run`, `respond` comme l'engine éditeur. Il ne recopie ni le prompt,
ni les logits, ni la calibration. Le backbone CPU natif est **BF16**, le
readout et le softmax **FP32**, attention SDPA et kernels PyTorch de référence.
Le loader amont refuse FP32 pour le backbone. Ce choix est conservé et sera
visible dans les archives ; les mesures historiques FP32 restent inchangées.
L'averaging par permutation est désactivé, batch d'une seule question.

Les références des bases sont `agent_only_pending_human` ; celles de Mastra
`pending_human`, avec zéro cas humainement qualifié et aucun outil exécuté.
Il s'agit de modèles isolés, sans intégration CLI/chat, récupération du corpus
privé ni qualité des réponses finales. Images, vidéos, Noul/Score, permutations,
GPU, grandes longueurs et temps répétés restent hors de cette première passe.

## Ressources et refus fixés avant résultats

Un seul processus modèle à la fois, CPU, deux threads, entrée maximale
**4 096 tokens natifs complets**. Les checkpoints déclarent `max_length:null` ;
le bridge impose donc ce plafond local. Le rendu/tokenizer natif prépare la
séquence complète avant le forward, sans troncature. Le bridge vérifie les
IDs et le masque réellement transmis ; une séquence trop longue reste
`unsupported` avant forward. Un contrôle synthétique court et long précède
chaque candidat et score zéro cas.

| Candidat | RSS max Mio | RAM disponible avant worker Mio | Initialisation max s | Choix max s |
|---|---:|---:|---:|---:|
| edge | 6 144 | 8 192 | 180 | 60 |
| lite | 6 144 | 8 192 | 180 | 60 |
| nano | 12 288 | 16 384 | 240 | 60 |

Chaque worker exige aussi 4 096 Mio disponibles pendant son exécution.
Le relevé RSS ne garantit pas un plafond instantané. Mastra est borné à
600 secondes ; chaque campagne de bases à 1 800 secondes externes (SIGINT,
puis arrêt forcé après 30 secondes). Les limites restent fixes après les
premiers résultats ; un dépassement est archivé et n'est pas corrigé en
augmentant la garde. Le préflight initial observe environ 27 Gio disponibles
sur les 43 Gio de WSL, swap non utilisé.

## Runtime et conservation

Runtime séparé `.cache/d3-runtime`, sans modifier celui de Decision2/Vela.
Les pins historiques sont conservés : Python 3.12.3, Torch 2.14.0+cpu,
Transformers 5.17.0, NumPy 2.5.3, Tokenizers 0.23.2, Safetensors 0.8.0 et Hub
1.33.0. Ajouts explicites : Accelerate 1.15.0, Einops 0.8.2, Pillow 12.3.0,
Psutil 7.2.2. Pas de kernels GPU FLA/causal-conv1d, ni installation globale.
`runtimes/d3/requirements.lock` installe les packages avec hashes ;
`runtime.lock` ajoute l'identité Python à vérifier, sans la traiter comme
un package installable. Le préparateur `scripts/prepare-d3-assets.py`
contrôle tous les fichiers sélectionnés contre les blobs/LFS HF épinglés.
Les tests ordinaires ne téléchargent et ne chargent aucun poids.

Poids sous `models/`, sources copiées, profils absolus, receipts et logs sous
`results/d3-preflight-20261011/`, tous ignorés par Git. Les manifests publics
ne contiennent que noms de fichiers, tailles et hashes. Chaque contrôle et
campagne utilise un dossier neuf ; les échecs sont conservés. Chaque préflight
recense la stack configurable et tous ses sous-modules, en distinguant les
sources locales/gitlinks des services observés. Aucun service n'est modifié.
Les résultats publiés ne contiendront que des agrégats, avec dénominateurs,
statuts, domaines, langues, tailles, latences, chargement et RAM observée.


## Lot observé après gel

Les [local-only material, not distributed](PROTOCOL.md) et [classements à 17 modèles](evidence/model-comparison-d3-overview-20261011/report.md)
conservent les résultats initiaux et les références. Edge : 74/132 et 18/24 ;
lite : 95/132 et 19/24 ; nano : 117/132 et 18/24. Six captures scellées,
468 décisions valides, sans erreur, timeout, refus ou troncature acceptée.
Les trois contrôles synthétiques courts sont valides et les trois entrées de
20 098 tokens refusées avant forward ; zéro cas scoré par ces contrôles.

Archives du checkout principal, toutes nouvelles :

- `results/d3-control-{edge,lite,nano}-20261011-001` ;
- `results/context-base-d3-{edge,lite,nano}-20261011-001` ;
- `results/mastra-read-d3-{edge,lite,nano}-20261011-001`.

Un runtime modèle à la fois, sans modifier les gardes. RAM disponible avant
les contrôles environ 25 Gio ; swap utilisé environ 4 Mio. Pic worker des
bases : 1 350 / 1 845 / 3 474 Mio, distinct du RSS échantillonné par le parent
et du RSS pendant le seul chargement. Aucun budget GPU n'est déduit.

Le code des campagnes était propre à
`b8d01be831263f2883c2b687e1ebfe838d0fe5af` : archive privée
`results/d3-preflight-20261011/b8d01be-source.tar`, SHA-256
`7875529eb105567c883dcfd416c297b84dc0042fe3159525fe3044baaade9da7`.
Cette copie est une conservation supplémentaire : les manifests automatiques
ne prétendent pas avoir capturé une archive source.

Les préflights recensent les 14 sous-modules actuellement déclarés ; le
registre historique de 15 composants et 29 contrats reste inchangé.
`attention` signale les divergences/dirty states de la stack et le composant
historique absent, sans modifier les dépôts concernés. Un relevé de source
ne prouve pas l'activité d'un service ; ces modèles n'appellent aucun service.

Validation avant inférence : 543 tests, 7 ignorés pour prérequis optionnels,
avec `jsonschema==4.26.0`, puis registre valide. Le jsonschema système 4.10.3
rencontre des erreurs de résolution de `$id` aussi dans des tests historiques ;
le runtime modèle séparé n'a pas été utilisé pour masquer ce défaut de l'outil
de validation. Les huit tests de composition ajoutés après les campagnes
vérifient notamment les corpus, identités, métriques historiques et ex aequo,
sans poids ni service. Les archives et qualifications anciennes sont conservées.

Validation finale à `4cb1d47` dans un clone Git local propre sous `/tmp`, sans
poids ni captures privées : **551 tests, 7 ignorés**, registre valide, puis
reproduction byte-à-byte du rapport à 17 modèles et de son manifeste depuis
les trois seuls JSON publics. Le log est conservé hors Git dans
`results/d3-preflight-20261011/tests-clean-clone.log`.
