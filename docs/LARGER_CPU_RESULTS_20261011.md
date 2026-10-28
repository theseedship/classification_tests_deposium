# Résultats CPU Nox 4B, Vela 4B et Liquid d1-3B — 11 octobre 2026

Les trois pilotes sont complets : **468 décisions valides** (3 × 132 bases +
3 × 24 propositions Mastra), sans erreur, timeout, abstention ou refus sur ces
entrées courtes. Les contrôles synthétiques séparés passent et ne contribuent
pas au score. Le [protocole gelé](LARGER_CPU_PILOT_20261011.md) utilise les
helpers natifs épinglés, CPU FP32, deux threads, un seul modèle à la fois.

## Comparaison des trois candidats

| Modèle | Bases /132 | Doc. /76 | Maths /28 | Chimie /28 | FR /66 | EN /66 | Routage /24 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Vela-2.0-4B | 106 | 64 | 20 | 22 | 52 | 54 | 18 |
| Decision-2.0-Nox-4B | 103 | 54 | 25 | 24 | 50 | 53 | 18 |
| LiquidAI/d1-3B | 101 | 60 | 21 | 20 | 50 | 51 | 16 |

Vela se distingue sur le documentaire de ce lot ; Nox sur les maths et la
chimie. Liquid est entre les deux en documentaire et en maths, mais ne les
dépasse pas sur les bases ou le routage. Nox et Vela reconnaissent les 8 demandes
de recherche et les 8 de statistiques, mais seulement 2 des 8 replis ; Liquid
obtient respectivement 6/8, 8/8 et 2/8. Le repli reste leur principale faiblesse.

Sur Mastra, FR/EN donnent 9/12 et 9/12 pour Nox et Vela ; 8/12 et
8/12 pour Liquid. Les deux traductions choisissent la même action dans
11/12 familles pour Nox, 9/12 pour Vela et 12/12 pour Liquid. La stabilité
linguistique peut donc être forte même lorsque le choix est faux.

## RAM, latences et taille des entrées

| Modèle | RSS bases max Gio | Bases médiane / p95 s | Mastra médiane / p95 s | Tokens natifs bases min / médiane / max |
|---|---:|---:|---:|---:|
| Vela-2.0-4B | 17.99 | 7.95 / 9.04 | 9.59 / 10.73 | 171 / 204.5 / 250 |
| Decision-2.0-Nox-4B | 20.66 | 5.92 / 7.37 | 7.56 / 8.37 | 131 / 164.5 / 210 |
| LiquidAI/d1-3B | 17.80 | 8.08 / 10.72 | 9.00 / 12.83 | 58 / 96 / 134 |

RSS worker échantillonné sur les 132 appels ; ce n’est ni le poids sur disque,
ni la RAM de toute la stack. Temps adaptateur observés sur une seule passe,
chargement séparé, Intel Core Ultra 5 235HX sous WSL. La pression des autres
processus varie ; ces mesures ne sont pas une garantie de latence ou de débit.
Les paramètres FP32 seuls sous-estiment nettement le RSS réel de Liquid.

L’initialisation adaptateur des bases dure 25,89 s pour Nox, 24,30 s
pour Vela et 12,65 s pour Liquid ; elle inclut le lancement et le chargement,
sans être ajoutée aux médianes par décision.

Les tokens incluent le gabarit et les choix propres au helper. Leurs nombres
ne sont pas comparables directement entre tokenizers. Le budget local est de
4096 tokens ; cette campagne courte ne mesure pas la qualité jusqu’à cette
limite. Les contrôles de dépassement vérifient un refus avant forward. Le
worker Liquid vérifie aussi les IDs effectivement reçus par le moteur natif.

## Classements complets et intégrité

- [22 modèles : général, routage, domaines, langues, difficultés, splits, RAM, temps et tokens](evidence/model-comparison-larger-cpu-overview-20261011/report.md).
- [Détails et croisements des trois nouveaux modèles](evidence/model-comparison-larger-cpu-20261011/report.md), avec [agrégat JSON](evidence/model-comparison-larger-cpu-20261011/analysis.json).
- [Producteur versionné](../scripts/compose-larger-cpu-comparison.py) et [manifeste de composition](evidence/model-comparison-larger-cpu-overview-20261011/manifest.json).

Sur les bases, Vela, Nox et Liquid occupent les rangs **5, 6 et 7**, derrière
D3 flash (124/132), Jev historique (123/132), D3 mini (119/132) et D3 nano
(117/132). Les 19 agrégats antérieurs sont copiés depuis les exports épinglés,
sans nouvelle inférence ni rescore. Aucun appel Jev dans ce lot. Le producteur
contrôle les six nouvelles archives, tous leurs fichiers scellés, leurs
identités, révisions et dénominateurs, ainsi que les hashes des exports anciens.

Les références sont encore `agent_only_pending_human` / `pending_human`.
Les accords Mastra sont des propositions isolées, avec **zéro outil exécuté,
zéro référence humaine validée et aucune réponse finale qualifiée**. Le corpus
court comporte des familles FR/EN traduites : ce n’est pas une preuve de
généralisation indépendante ou de supériorité produit. Les mesures documentaires
du graphe privé restent séparées et inchangées.

## Sources figées et reprise

Le code initial est gelé à `042739b599eae0a3ed9af2238a91f07203288959` avant Nox.
Le contrôle Vela a détecté un total HF omettant un biais scalaire ; la correction
`21c829edbc5f4a46df460f3f05ad39e9295b825a` est figée avant les premières
prédictions Vela/Liquid. Le worker compare désormais les paramètres réellement
chargés aux headers des shards ; un test couvre ce scalaire. Aucun seuil mémoire
ou oracle n’a été relevé après une prédiction.

Les tarballs de ces sources et leurs reçus sont conservés hors Git. Le champ
automatique `source_archive: not_captured` des captures reste inchangé : les
archives de code sont des preuves séparées, sans réécriture des campagnes.

La provenance de stack distingue les **14 sous-modules actuellement déclarés**
des 15 composants du registre historique. Ces essais sont des modèles isolés ;
la présence de composants dans le préflight ne signifie pas qu’ils ont été
exécutés. Corpus privé, sorties brutes, logs, poids et profils absolus restent
hors Git. Les manifests publics permettent le téléchargement des mêmes révisions.

## Validation du banc

Clone Git propre à `56a35298bf720e3addf248cdb4698cb58e9038b6`, sans poids ni
runtime modèle : **592 tests, 7 ignorés**, aucun échec, registre valide.
Validation exécutée avec `jsonschema==4.26.0` pour ses références de schéma.
Les deux producteurs régénèrent les exports à l’identique sans inférence ;
le producteur du clone reproduit aussi le rapport 22 modèles et son manifeste
avec les six captures privées scellées disponibles. Un clone sans ces captures
peut lire les exports et tester les fixtures, mais ne peut pas revérifier leurs
payloads privés. Le journal complet reste hors Git.

## Nettoyage et suite

Après vérification des sceaux et des manifests épinglés, **31 fichiers de poids
antérieurs (51,855 Gio)**, puis **11 fichiers de poids de ce lot (23,897 Gio)**
ont été supprimés : **81 337 606 438 octets, soit 75,752 Gio** de fichiers au
total. Les reçus détaillés avant/après restent privés. Captures, configs,
tokenizers, sources et manifests sont conservés, ainsi que les bases Qwen/Strands
utiles à la suite. Un rejeu nécessite de retélécharger les poids épinglés.
La récupération de place physique Windows dépend ensuite de la compression WSL
habituelle ; aucune compression ni modification de service n’a été lancée ici.

Les versions Lux 9B et Vela 9B restent `not_run`. Leurs loaders CPU natifs
gardent les paramètres FP32 : environ **29,6 Gio pour les seuls paramètres**,
avant runtime, buffers et marge de stack. Après fermeture des workers, la RAM
disponible observée est de 27,07 Gio, déjà inférieure à ces seuls paramètres.
Le BF16 natif de D3 flash ne peut pas
leur être transposé sans qualification. Aucun poids 9B n’a été téléchargé.

CLM 8B est [étiqueté anglais](https://huggingface.co/Contrastive-LM/CLM-v0.1-8B).
Son encodeur Qwen3-8B et ses deux têtes contrastives n’ont pas de résultat FR
publié sur cette fiche ; le backbone ne suffit pas à qualifier la tête en
français. [Muose 100M](https://huggingface.co/muose/Muose-100M-Decision) est
aussi étiqueté anglais, avec une fenêtre de 512 tokens. Les deux seraient des
essais FR/EN exploratoires, pas des candidats multilingues déjà démontrés.

Pour Strands, la version [Qwen 2B v1](https://huggingface.co/StrandsAgents/strands-decider-2B-qwen3.5-v1-2610)
est préférable à l’ancien pilote v19 : l’éditeur annonce une parité de décisions
CPU/GPU sur ses 231 cas JevBench. Ce résultat n’est pas une mesure Deposium et
ne fournit pas de ventilation FR. Le futur profil devra épingler séparément
l’adaptateur `216d1ccb46a9e9b036eb9187b248db98480f77d4` et la base
`b1485b2fa6dfa1287294f269f5fb618e03d52d7c` déjà conservée. Voir
[les prochains candidats](NEXT_CANDIDATES.md) et [l’inventaire jusqu’à 9B](VARIANTS_UP_TO_9B.md).
