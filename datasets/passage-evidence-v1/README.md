# Passage evidence v1 — jeu multilingue exploratoire

**1 536 cas, 24 familles synthétiques, six langues.** Les références et
traductions sont proposées par agent, **sans revue humaine**. Ce pack prépare
une comparaison de modèles ; il n'annonce aucun gagnant ni gain produit.
Son [protocole](../../docs/PASSAGE_EVIDENCE_DATASET.md) distingue classement,
pertinence, soutien d'affirmations et possibilité de répondre.
Les cas portent 2 304 affirmations candidates et 9 216 jugements d'appui par passage.

## Couverture

| Axe | Contenu |
| --- | --- |
| Langues | FR, EN, DE, ES, IT, PT |
| Question → passages | Les six paires monolingues, FR→EN et EN→FR |
| Scénarios | Pièce/relation voisine ; variante ; unité/condition ; négation/exception ; preuves réparties ; preuve absente ; conflit ; preuve coupée |
| Familles / splits | 24 familles, huit par split train/calibration/test ; traductions et documents d'une famille restent ensemble |
| Ordre | Quatre rotations de quatre passages : chaque passage occupe chaque position |
| Texte visible | `full` ou `head_384`, préfixe de 384 caractères Unicode, avec références adaptées à la vue |
| Référence de pertinence | 3 directe ou réfutant le fait demandé ; 2 partielle ; 1 thématique ; 0 sans preuve utile |
| Soutien d'affirmation | `supports`, `refutes`, `insufficient`, spans exacts dans le texte visible |
| Réponse possible | `answerable`, `insufficient_visible_evidence`, `conflicting_visible_evidence` |

Les affirmations comprennent des contrôles où seul le nombre, l'unité ou la
négation change. Le chiffre présent dans une autre rubrique ne vaut pas appui.
Un passage réfutant une affirmation peut être très pertinent pour la question.
La conjonction distribuée nécessite deux passages ; aucun ne soutient à lui
seul l'affirmation entière.

La taille se décompose en **24 familles × 8 directions × 4 ordres × 2 vues**.
Ces dérivés ne constituent pas 1 536 faits indépendants. Des vues sont
identiques ; leur nombre est déclaré dans le manifeste. Les modèles doivent
être comparés sur les mêmes variantes et les incertitudes groupées par famille.
Les gabarits d'opération sont partagés entre splits : aucune généralisation
à des structures entièrement nouvelles n'est démontrée.

## Valider sans modèle

Python 3.11+ et la bibliothèque standard suffisent, depuis la racine du dépôt :

```bash
python3 -B -m deposium_bench.passage_corpus --check
python3 -B -m deposium_bench.passage_dataset validate
python3 -B -m unittest tests.test_passage_dataset -q
```

`--check` compare les octets régénérés aux fichiers versionnés, sans écrire.
Le validateur contrôle notamment les empreintes, identités, splits, références,
spans visibles et cohérence des annotations de textes identiques. Il ne remplace
pas une revue humaine du sens ou des traductions. La génération initiale refuse
l'écrasement ; `--overwrite` doit être demandé explicitement, avec justification
et revue d'un changement de référence.

## Exporter les entrées d'un essai borné

Exemple de premier lot : split calibration, texte complet, question anglaise,
passages français. Les fichiers de résultats sont ignorés par Git :

```bash
python3 -B -m deposium_bench.passage_dataset export \
  --projection ranking --split calibration --view full \
  --question-language en --passage-language fr \
  --output results/passage-pilot-001/ranking-inputs.jsonl

python3 -B -m deposium_bench.passage_dataset export \
  --projection support --split calibration --view full \
  --question-language en --passage-language fr \
  --output results/passage-pilot-001/support-inputs.jsonl
```

Chaque export affiche le nombre exact de requêtes, les filtres et le hash du
dataset. Il **n'appelle aucun modèle**. Il refuse par défaut d'écraser un fichier.
Les filtres peuvent être répétés pour sélectionner plusieurs langues ou splits.

- `ranking` : une requête par cas ; contrat `bench.passage-rerank`, entrée
  `{query, passages:[{id,text}]}`. Le futur adaptateur du cross-encoder doit
  restituer les quatre IDs classés.
- `relevance` : une requête de choix par passage ; quatre degrés de pertinence.
- `support` : une requête de choix par passage et affirmation candidate ; trois
  sorties de soutien. L'affirmation est bien une entrée de cette tâche ; son
  annotation reste cachée.
- `answerability` : une requête de choix sur le pool entier ; trois états de preuve.

Les trois projections de choix réutilisent `bench.context-choice` et le module
`choice_protocol` déjà employé par les adaptateurs du banc. Les instructions
suivent la langue de la question. Les champs `axis`, `passage_id`, `claim_id`
suivent les résultats comme identités, hors entrée du modèle. Le décodage des
options est dans `passage_dataset.CHOICE_LABELS` ; il ne contient pas les bonnes
réponses des cas. `candidate_row(request)` produit la ligne du protocole commun.

Ces exports sont compatibles avec la **frontière des adaptateurs de choix**,
pas avec les oracles des 132 cas historiques. Ne pas les passer comme de nouveaux
cas v2 à `validate-cases` ou à une ancienne campagne. Ce lot fournit données,
projections et scoring hors ligne ; il ne crée pas un second runner d'inférence.

## Scorer des sorties déjà enregistrées

Format d'une sortie de classement :

```json
{"case_id":"<ID du cas exporté>","status":"ok","ranking":["<ID1>","<ID2>","<ID3>","<ID4>"]}
```

Format d'un choix : conserver `case_id`, `axis`, `passage_id` et `claim_id`
lorsqu'ils figurent dans la requête, puis ajouter `status` et `choice_id` :

```json
{"case_id":"<ID du cas>","axis":"support","passage_id":"<ID passage>","claim_id":"<ID affirmation>","status":"ok","choice_id":"o3"}
```

Les états `error`, `timeout`, `unsupported` et `abstain` restent distincts.
Une ligne absente est comptée `missing` ; elle n'est pas supprimée du dénominateur.
Le choix sémantique « preuves insuffisantes » est un résultat `ok`, différent
d'une abstention technique de l'adaptateur. Les sorties `ok` vides, IDs inconnus,
doublons et permutations incomplètes sont refusés.

```bash
python3 -B -m deposium_bench.passage_dataset score \
  --projection ranking --split calibration --view full \
  --question-language en --passage-language fr \
  --predictions results/passage-pilot-001/ranking-predictions.jsonl \
  --output results/passage-pilot-001/ranking-scores.json
```

Utiliser les mêmes filtres qu'à l'export. Changer `--projection` pour scorer
`support`, `relevance` ou `answerability`. Les sorties restent dans une nouvelle
archive ; aucun rescore ne relance l'inférence ni n'écrase un score antérieur.

Le classement publie nDCG@1/3/4, MRR@4 et rappel@1/3/4, moyennes observées et
moyennes sur cas éligibles pénalisant les erreurs/absents. Sans gain idéal,
nDCG est `null` ; sans passage de grade ≥2, MRR et rappel sont `null`.
Un pool seulement thématique peut avoir un nDCG défini tout en étant insuffisant
pour répondre. Les choix publient couverture, taux de réussite global et par classe,
et moyenne macro. Les groupes sans résultat ne sont pas certifiés PASS.

## Lecture dans un notebook

Le notebook utilise les mêmes fonctions ; aucune logique dupliquée dans les cellules :

```python
from deposium_bench.passage_dataset import load_dataset, select_cases, export_requests

cases, dataset_sha256 = load_dataset()
pilot = select_cases(cases, split="calibration", view="full",
                     question_language="en", passage_language="fr")
requests = export_requests(pilot, projection="support")
print(dataset_sha256, len(pilot), len(requests))  # aucune inférence
```

Pour la campagne réelle, figer un profil candidat et ses ressources avant de
brancher l'adaptateur. Le nombre de requêtes de choix par paire peut dépasser
largement celui d'un reranking en lot : mesurer le coût de la composition.
Les quatre candidats sont déjà présents ; ce pack ne mesure pas le rappel
du premier étage de recherche ni le comportement du chat réel.
