# Lot 1 — preuves locales du 1er octobre 2026

Ce relevé précède le pilote de modèle. Lire [JULIA_RESULTS.md](JULIA_RESULTS.md)
pour la comparaison réelle ajoutée ensuite et les contrôles actuels du banc.

Branche de reprise : `feat/decision-bench-lot1`, issue du checkpoint `08c5708`.
Le noyau est utilisable avec contrôles figés et replay de quatre fonctions MCPs.
Le lot 1 complet reste ouvert : revue humaine du corpus, choix d'un candidat
réel et comparaison appariée. Aucun modèle, service de stack, API payante ou
parcours produit n'a été lancé; les checkouts applicatifs sont restés intacts.

## Résultats vérifiés

| Vérification | Résultat et portée |
|---|---|
| Suite locale `python3 -m unittest discover -s tests -q` | 103 tests découverts, 99 réussis, 4 replays réels omis par défaut |
| Copie isolée, Python 3.12 `-S`, sans Node/Jupyter/jsonschema/stack | 103 découverts, 84 réussis, 19 contrôles optionnels omis; noyau autonome |
| `validate-registry` | 15 composants, 29 contrats, 4 bridges `available`, 25 `planned`; évaluation `not_run` |
| `validate-cases` | 36 cas valides, 18 familles FR/EN, cinq packs; évaluation `not_run` |
| Tests MCPs réels avec racine explicitement fournie | 4 tests réussis sur les fonctions du checkout épinglé |
| Campagne de contrôle figée | 36 traces, 28 scorés, 21 réussis, 7 échoués; `fail` attendu |
| Campagne réelle de fonctions MCPs | 36 traces, 28 scorés et réussis, 8 EVIDENCE `unsupported`; `fail` global pour couverture incomplète |
| Notebook/CLI | Parité typée de tous les scores, états et sorties, huit kernels neufs |
| Reprise/rescore MCPs | Deux résultats conservés puis un nouvel appel; rescore complet sans adaptateur ni nouvelle inspection de stack |
| Schémas sur les archives produites | Manifestes, résumés, traces et seals conformes avec jsonschema déjà installé |
| Nettoyage | `git diff --check` réussi; notebook source sans sortie ni compteur d'exécution |

La copie isolée utilise Git et ses utilitaires shell usuels, sans dépendance
Python externe. Une première tentative de PATH limité au seul binaire Git
privait `git submodule` de ses utilitaires; elle a été corrigée dans le montage
de vérification, sans modification du code pour masquer l'échec.

Le profil de contrôle conserve les six états : 26 `ok`, 2 `abstain`,
2 `error`, 2 `timeout`, 2 `missing`, 2 `unsupported`. Ses scores servent
uniquement à vérifier le mécanisme. La campagne MCPs comporte 28 `ok` et
8 `unsupported`, sans erreur, absence ni timeout. Les dénominateurs ne changent
pas pour masquer les cas non supportés : couverture 28/36, succès 28/36,
succès parmi les cas scorés 28/28.

## Provenance du replay réel

- Parent stack : `25dbf06d8e90cea5675a498959e9d9db1fb7a3e0`.
- MCPs réellement importé : `391be12078b1f3daa24a50c31c3a39eb72d7fb94`, checkout propre.
- Gitlink MCPs du parent : `acb41319e00bed5452da6a6fce9eee36ad2a87f0`, distinct du HEAD exécuté.
- Runtime : Node `v24.19.0`, tsx `4.23.12`, zod `4.4.3`, esbuild et
  `@esbuild/linux-x64` `0.28.1`. Les 270 fichiers runtime sélectionnés représentent
  139 704 259 octets lus et hashés, sans copie de binaires ni installation.
- Inventaire : 15 composants découverts; préflight `attention`. Les HEAD locaux,
  gitlinks et états sales sont archivés, sans réinitialisation de la stack.
- Le bridge importe la fermeture de sources revue et les quatre exports;
  les racines réellement résolues des packages sont épinglées. Les changements
  de sources, fichiers runtime ou cibles de symlinks sont refusés autour des appels.
- Le banc a été exécuté avec les changements de ce lot encore non commités;
  les sources et schémas sont identifiés par leurs hashes dans les manifestes.
  Empreinte du noyau de ces deux campagnes :
  `4cc2a73d144ca30bff2a8eb0a78ca4198e17c232b9f60757e7209f27e24e3846`.

Le corpus et les références n'ont pas été modifiés pour obtenir ces scores.
SHA-256 de `cases.jsonl` :
`88c728ee18d91647a6c3ee1a8ecfc65e808c916d82dba5ad70925dc4be3b3ab6`.
FOLLOWUP reçoit une éligibilité et une sélection structurées déjà établies;
ses paires FR/EN ne prouvent pas une compréhension linguistique autonome.
Les assertions ne couvrent que les champs déclarés. Les splits sont tous
rejoués pour cette recette exploratoire, sans revendication de généralisation.

## Archives locales conservées hors Git

| Dossier sous `results/` | Identité / rôle |
|---|---|
| `control-lot1-20261001` | Run `3f746352-5416-4e74-9522-6280a9414b6a` |
| `mcps-lot1-20261001` | Run `6a0ccdd4-4586-4978-99c4-7d2f38f49fe7` |
| `mcps-lot1-rescore-20261001` | Même trace, mêmes métriques, aucun appel de candidat |
| `mcps-lot1-partial-20261001`, `mcps-lot1-resumed-20261001` | Reprise réelle 2 → 3 résultats, archives originales conservées |
| `notebook-parity-3e2205682bef4f588bee924b247c0fe0` | `verification.json`, huit notebooks exécutés et archives CLI/notebook |

SHA-256 des traces complètes :

- Contrôle : `9a9fd85b1ee11843071862126cfaa46e83796c5e0b307887ef7e856609016c8f`.
- MCPs : `88e9f651be26cfe50514a89bf5e3a3d25782a0349c23fe7c6e6d6ec3417909ff`.

La parité couvre chaque interface depuis la racine puis depuis `notebooks/`,
en modes run complet, run partiel, resume et rescore. La comparaison JSON
distingue notamment booléens/nombres; seules les métadonnées temporelles
variables sont exclues. Sorties brutes du rescore et archives parentes sont
inchangées. Le notebook source garde son hash
`8b737ee531c1184ee87b7fd134b72b345ffd372efcdb6e96ad711fbbaaf1b5fe`.

## Corrections d'intégrité et prochaine étape

Les tests ont conduit à rejeter les références/sorties récursivement vides,
les identités incohérentes, les doublons JSON, les valeurs non finies et les
traces tronquées. Ils vérifient les splits par scénario/document/traduction,
la séparation des annotations, les assertions typées et l'absence de PASS
quand aucun cas n'est scoré. U+2028/U+2029 restent du contenu JSON valide.

Une campagne exécute les mêmes octets de fixtures qu'elle archive. Reprise et
rescore réutilisent un snapshot des octets validés pour éviter qu'une édition
concurrente ne dissocie scores et sorties copiées. Les archives dérivées restent
séparées, avec lien de provenance. Les seals détectent les modifications; ils
ne sont pas des signatures d'authenticité face à un éditeur malveillant.

Prochaine étape : faire revoir les 18 familles et figer le protocole d'un
premier candidat (capacité, révision, runtime, budget disque/RAM, split et
contexte identiques à sa référence). La couverture EVIDENCE, le branchement
B et les parcours C restent des lots distincts. Les 28 réussites du composant
ne qualifient ni accès, recherche, génération, compte/liste canoniques,
rendu ni persistance du produit.
