# Julia-1 CPU — résultats du 1er octobre 2026

**Aucun gain observé sur ce pilote** : la fonction documentaire MCPs réussit
14/14 cas, Julia 10/14 et Julia avec choix inversés 9/14. L'inversion change
5/14 décisions. Ces résultats portent uniquement sur le champ `/task` d'un
petit corpus exploratoire; ils ne justifient pas de remplacement dans Deposium.

## Mesures et couverture

| Périmètre | MCPs | Julia canonique | Julia choix inversés |
|---|---:|---:|---:|
| Tous les cas, sept familles FR/EN | 14/14 | 10/14 | 9/14 |
| Noyau, six familles | 12/12 | 8/12 | 7/12 |
| Suivis avec contexte, une famille | 2/2 | 2/2 | 2/2 |
| Français | 7/7 | 5/7 | 4/7 |
| Anglais | 7/7 | 5/7 | 5/7 |
| Split train, deux familles | 4/4 | 2/4 | 4/4 |
| Split calibration, deux familles | 4/4 | 2/4 | 2/4 |
| Split test, trois familles | 6/6 | 6/6 | 3/6 |

Chaque cellule indique réussis/total, avec une couverture scorée de 100 %.
Les 42 sorties des trois campagnes ont le statut `ok`; aucune abstention,
erreur, absence, limitation de capacité ou expiration. `ok` signifie une réponse
valide, pas une assertion réussie. Les 28 encodages Julia n'ont aucune troncature.

Les cas FR/EN d'une famille sont corrélés. Le noyau du split test contient
quatre cas `retrieve_answer`; les deux suivis ajoutent `stored_summaries`.
Ce split ne contient aucun `catalog`. Les noms des splits sont hérités du
corpus; aucun entraînement ou calibrage n'a eu lieu dans ce pilote.

## Échecs et ordre des choix

Julia canonique renvoie `retrieve_answer` pour les deux demandes de comptage
(`catalog` attendu), puis `catalog` pour les deux demandes combinant comptage
et résumés (`stored_summaries` attendu).

L'ordre inversé corrige les deux comptages, conserve les deux erreurs sur les
demandes combinées, et introduit trois erreurs vers `catalog` : question sur
le contenu en français, Mermaid en français et en anglais. Cinq décisions
changent donc, avec deux corrections et trois régressions. Les descriptions
des options sont identiques; seule leur position change.

Le corpus original, ses annotations et ses fixtures n'ont pas été modifiés.
La [projection](../datasets/document-task-v1/manifest.json), les prompts et
le [local-only material, not distributed](PROTOCOL.md) ont été fixés avant les prédictions, commit
`b63dddb`. Aucun ajustement de prompt après lecture des scores.

La [revue par agent](CORPUS_REVIEW.md) identifie des ambiguïtés et des règles
de politique produit dans ces références. La revue humaine reste à faire.
Certaines entrées incluent une intention amont ou un historique de plan :
les scores sont conditionnels à ces mêmes informations fournies aux deux candidats.

## Exécution réellement observée

- Julia : révision `a85b127321d580d65176c89ced8273f305745d85`, moteur officiel
  PyTorch CPU, deux threads, batch 1, encodage strict 1 024/512 tokens.
- Runtime : Python 3.12.3, Torch 2.14.0+cpu, Transformers 5.0.0,
  Tokenizers 0.22.2, NumPy 2.5.3. Le lock est archivé; les versions installées
  sont observées, sans empreinte complète des fichiers des dépendances installées.
- Chargement : 10,19 s canonique, 10,47 s inversé. RSS maximal observé :
  999,28 et 999,02 Mio, sous le seuil surveillé de 3 072 Mio.
- Médiane de l'appel moteur Julia : 81,13 et 78,88 ms/cas, chargement exclu.
  Mesures locales descriptives; aucune comparaison de vitesse avec MCPs,
  dont le bridge mesure une frontière d'exécution différente.
- Assets sélectionnés : 611 721 780 octets. Dossiers locaux environ 584 Mio
  pour les assets, 909 Mio pour le runtime et 24 Mio de cache additionnel
  observés par `du`; ces fichiers sont exclus de Git.
- MCPs : HEAD propre `391be12078b1f3daa24a50c31c3a39eb72d7fb94`, différent
  du gitlink parent `acb41319e00bed5452da6a6fce9eee36ad2a87f0`.
  Parent stack `25dbf06d8e90cea5675a498959e9d9db1fb7a3e0`.
  Node v24.19.0, tsx 4.23.12, zod 4.4.3.

Le banc conserve l'inventaire des 15 composants. Seule la baseline appelle
la fonction MCPs; les campagnes Julia déclarent `model_isolated_only` pour
les composants. Les traces liées au contrat MCPs dans une campagne Julia
ne sont pas des appels au composant. Aucun service, image ou parcours produit
n'a été lancé ou qualifié par cette expérience.

## Archives et contrôles

Les archives complètes restent locales sous `results/`, hors Git. Le
[relevé versionné](evidence/julia-document-task-20261001.json) conserve leurs
hashes, dénominateurs, choix, logits, ordre des options et observations d'encodage.
Il ne remplace pas les archives complètes nécessaires à `resume` et `rescore`.

| Archive | Résultat |
|---|---|
| `task-mcps-001` | Replay MCPs, 14/14 |
| `task-julia-001` | Julia canonique, 10/14 |
| `task-julia-reversed-001` | Julia inversé, 9/14 |
| `task-comparison-001` | 14 paires, quatre régressions, zéro amélioration |
| `task-comparison-reversed-001` | 14 paires, cinq régressions, zéro amélioration |
| `task-julia-partial-001` | Arrêt contrôlé après deux cas, 12 `missing` |
| `task-julia-resumed-001` | 14 cas, 10 réussis; premières traces conservées |
| `task-julia-rescored-001` | Même trace brute octet pour octet, mêmes scores |
| `task-julia-notebook-001` | Kernel neuf depuis `notebooks/`, même résultat que CLI |

Les sources Python archivées par hash pour les campagnes Julia canonique et
inversée correspondent au commit `685eb6f`. La première conserve honnêtement
`b63dddb` avec checkout sale : un contrôle du type de numéro de séquence et ses
tests avaient été ajoutés avant son exécution, puis commités. Ces changements
n'affectent ni entrée, prompt, poids, choix ni scorer. Les hashes de l'adaptateur
et du worker sont identiques entre les deux campagnes; aucun manifeste réécrit.

Validation effectuée :

- 137 tests découverts : 133 réussis, quatre replays MCPs opt-in omis; le replay
  réel des 14 cas ci-dessus est une exécution séparée.
- Copie des fichiers suivis seule, sans cache/poids, Python `-S` : 127 réussis,
  dix omis (six validations JSON Schema optionnelles et quatre replays opt-in).
- Trois archives principales : schémas manifestes/profils/résumés/seals et
  42 traces validés; empreintes vérifiées par le lecteur d'archives.
- Reprise : sorties, logits et encodages identiques à la campagne complète;
  rescore sans adapter, trace brute et métriques conservées.
- Notebook : sorties, logits, encodages et métriques identiques à la CLI,
  hors durée et RSS; notebook source inchangé, sans sorties. Le lancement
  dans le sandbox bloquait le kernel; contrôle réussi avec sockets locaux
  autorisés, processus de vérification initial arrêté.

## Reprise du chantier

Branche `feat/julia-document-task-pilot`. Revoir humainement les références,
puis créer davantage de familles indépendantes, avec toutes les classes dans
le split test. Comparer ensuite d'autres candidats sur un protocole annoncé.
Les résultats de ce pilote restent une référence négative conservée. Le routage
intégré, les autres capacités et la qualification produit restent à faire.
