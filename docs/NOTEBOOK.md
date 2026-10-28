# Exécuter et vérifier le notebook de décisions

Le notebook [decision_bench.ipynb](../notebooks/decision_bench.ipynb) appelle le
même moteur `deposium_bench.campaigns` que la CLI. Les cellules ne définissent
ni candidat, ni routage, ni scorer. Le noyau du banc et les tests ordinaires
utilisent seulement la bibliothèque standard; Jupyter est un extra facultatif
verrouillé, requis pour la vérification explicite ci-dessous.

Depuis la racine du clone, avec Python 3.11+ et `uv` :

```bash
uv sync --locked --extra notebook
```

Un éditeur Jupyter peut sélectionner directement `.venv/bin/python`. Le notebook
trouve la racine des sources depuis le clone ou son dossier `notebooks`, dans
un kernel neuf, sans chemin WSL imposé. Aucun kernel utilisateur n'est requis.

## Parité reproductible depuis des kernels neufs

Le [script de vérification](../scripts/verify-notebook.py) lance exclusivement
le profil `profiles/fixture-control.json`. Il utilise NBClient avec le Python
de l'environnement courant, sans installer de kernel ni modifier le notebook
source. Depuis la racine :

```bash
.venv/bin/python scripts/verify-notebook.py
```

Depuis le dossier `notebooks`, la même vérification fonctionne :

```bash
../.venv/bin/python ../scripts/verify-notebook.py
```

Par défaut, huit kernels neufs couvrent deux dossiers de démarrage du kernel
(racine et `notebooks`) et quatre étapes : campagne complète, campagne limitée
à quatre résultats, reprise de cette campagne puis rescore de la reprise.
Chaque étape est également exécutée via la CLI, dans une archive indépendante.
Le script vérifie :

- L'égalité exacte des métriques, états d'achèvement et couvertures de stack.
- Pour chaque `case_id`, l'égalité des sorties normalisées, sorties brutes,
  états, erreurs, contrats et empreintes de requête. Seules la durée mesurée et
  l'identité d'exécution sont exclues de cette comparaison.
- L'égalité des résultats d'une reprise/rescore avec la campagne complète,
  la conservation octet pour octet de la trace brute lors du rescore et
  l'absence de modification des archives parentes ou du notebook source.

Les résultats restent dans un nouveau répertoire
`results/notebook-parity-<uuid>/`, hors Git : archives CLI/notebook, copies des
notebooks exécutés et bilan `verification.json`. `--output-dir` choisit un autre
répertoire neuf; une destination existante est refusée. `--kernel-cwd root` ou
`--kernel-cwd notebooks` limite le contrôle à quatre kernels. Un écart arrête
la vérification; les artefacts déjà écrits restent disponibles pour inspection.
Cette commande est volontairement distincte des tests ordinaires sans Jupyter.

Le profil de contrôle contient des erreurs intentionnelles et des états non
réussis : son verdict de campagne doit rester `fail`. Le `pass` du script indique
uniquement la parité et l'intégrité des archives; il ne qualifie aucun modèle.
Aucun téléchargement de poids, appel d'API ou service de stack n'est requis.

## Paramètres et limites

La cellule marquée `parameters` porte `dataset_path`, `profile_path`,
`output_dir`, `stack_root`, `run_mode`, `source_archive` et `max_new_cases`.
Modifier cette cellule ou injecter une cellule juste après, avant les calculs
dérivés. Le script utilise cette injection en mémoire; Papermill n'est pas requis.
Les chemins relatifs sont interprétés depuis la racine trouvée.
`output_dir=None` crée un nouveau nom `results/notebook-<uuid>`. Une destination
explicite existante est refusée par le moteur.

`run_mode='run'` appelle `run_campaign`. `resume` et `rescore` exigent
`source_archive` et créent une nouvelle archive. `max_new_cases` borne une
exécution/reprise; il ne change pas un rescore. Rapports et scores proviennent
du moteur commun. Le notebook source conserve sorties et compteurs vides.

Choisir explicitement un profil MCPs et `stack_root` pour un replay réel, avec
ses prérequis. Un replay de fonction ne qualifie ni la route HTTP, ni les droits,
ni le parcours produit. La parité sur fixtures ne démontre pas une amélioration
du chat. Les modèles restent à mesurer dans des campagnes documentées séparément.
