# Pilote GLiNER2.5-multi-Decide

Protocole fixé le 2 octobre 2026 avant les premières prédictions du candidat.
Qualification : modèle isolé, preuve A. Aucun routage Deposium remplacé.

## Candidat et runtime

- Modèle : `fastino/GLiNER2.5-multi-Decide`, révision
  `a35a0cd3b7a0f00f2effc576f454cd48fa98aa5f`.
- Paquet officiel `gliner2[local]==2.0.0`, `AutoExtractor` architecture boundary,
  Python 3.12, Torch CPU. Dépendances et hashes :
  [requirements.lock](../runtimes/gliner/requirements.lock).
- Chargement depuis le répertoire local uniquement, Hub et Transformers hors
  ligne pendant l'inférence. Pas de téléchargement d'un second encodeur.
- Deux threads, une requête et un modèle à la fois, RSS maximum 3072 Mio,
  délai d'initialisation 120 s et délai par requête 30 s. Le surveillant relève
  la RSS toutes les 50 ms et arrête son processus en cas de dépassement.

Le `max_len=4096` du checkpoint est un réglage de traitement des mots qui
n'est pas appliqué automatiquement par `classify_text(max_len=None)`.
Le **budget du pilote** est donc fixé séparément à 4096 sous-tokens natifs,
schéma, question et choix inclus. Ce budget ne prouve ni une limite native
du modèle, ni une qualité acceptable à cette longueur.

## Entrées et contrôle de longueur

Les cas et références restent ceux du [local-only material, not distributed](PROTOCOL.md).
`context` devient le texte de `classify_text`, `question` son prompt et les
descriptions des choix ses labels, dans l'ordre fourni. Les identifiants
restent hors modèle et servent uniquement à mapper la réponse. Aucun exemple
de bonne réponse ni annotation n'entre dans la requête.

Le traitement officiel ajoute un point si le texte ne finit pas par `.`, `!`
ou `?`, puis utilise les mots en minuscules. Ces transformations sont tracées
et peuvent notamment affecter la casse des formules : elles appartiennent au
candidat testé. Le banc n'en corrige pas les sorties. Le préflight utilise le
processeur officiel sans troncature; un hook vérifie que les IDs et le masque
effectivement reçus par l'encodeur correspondent exactement au préflight.

Un dépassement du budget retourne `unsupported/gliner_context_overflow`
avant tout forward. Les refus de cible de longueur irréalisable, les erreurs
d'exécution, les timeouts et les réponses fausses demeurent séparés.
La sortie native et sa confiance sont archivées; aucune distribution complète
de probabilités ni aucun logit ne sont reconstruits à partir de cette confiance.

## Campagnes prévues

1. Chargement et quelques cas de contrôle, sous garde mémoire.
2. Les 132 bases FR/EN inchangées : documentaire, mathématiques, chimie;
   résultats séparés par split, domaine, langue et difficulté déclarée.
3. Les 378 textes déjà produits dans
   `results/context-sentinels-001/lengths/cases.jsonl`, hash
   `f721aec7ff08b3b4be6a2e3dcb5dd88ae2b1c0bea3a7fcf6f9ab0aefd92e492a`.
   Les cibles 100 à 8000 sont mesurées avec le tokenizer de référence Julia;
   les tokens natifs GLiNER sont une observation distincte. Pas de régénération
   de textes pour faire coïncider les nombres de tokens entre candidats.
4. Comparaison d'archives scellées avec les mêmes bytes de corpus et le même
   scorer. Montrer les cas appariés réussis et les dénominateurs complets.

Mesure répétée des temps fixée avant son exécution : les 18 bases de la sélection
de sentinelles (`results/context-sentinels-001/base.jsonl`), les profils
contextuels Julia et GLiNER, trois lancements par candidat, un appel initial,
cinq échauffements puis trois passages. Soit 360 appels prévus, dont 162 appels
mesurés par candidat. Les processus sont séquentiels et l'ordre des candidats
alterne entre lancements. Les neuf familles de calibration restent neuf familles;
ces répétitions ne constituent pas un nouveau test de généralisation.

Le nombre de familles indépendantes reste 66 pour les bases et 9 pour les
sentinelles. Les résultats ne fixent pas un seuil de bascule vers un LLM :
il manque encore une baseline LLM, une revue humaine et des documents réels.

## Reproduction

```bash
uv venv --python 3.12 .cache/gliner-runtime
uv pip sync --python .cache/gliner-runtime/bin/python runtimes/gliner/requirements.lock --require-hashes
hf download fastino/GLiNER2.5-multi-Decide README.md config.json encoder_config/config.json model.safetensors tokenizer.json tokenizer_config.json --revision a35a0cd3b7a0f00f2effc576f454cd48fa98aa5f --local-dir models/GLiNER2.5-multi-Decide-a35a0cd --max-workers 1
python3 -m deposium_bench run --dataset datasets/context-choice-v1/cases.jsonl --profile profiles/gliner-multi-cpu-context.json --output results/context-base-gliner-NEW --stack-root ../deposium_fullstack
```

Le manifeste vérifie les assets, versions installées et sources Python de
GLiNER. Les autres bibliothèques sont installées avec les hashes du lock et
leurs versions sont vérifiées; leurs fichiers installés ne sont pas tous
rehashés à chaque campagne. Les mesures CPU sont locales, hors services et LLM.

Sources primaires : [checkpoint](https://huggingface.co/fastino/GLiNER2.5-multi-Decide/tree/a35a0cd3b7a0f00f2effc576f454cd48fa98aa5f),
[paquet 2.0.0](https://pypi.org/project/gliner2/2.0.0/),
[loader officiel](https://github.com/fastino-ai/GLiNER2/blob/55656fbfa01d3d4a77485e1a1eeeaf682990ccdf/gliner2/auto.py).
