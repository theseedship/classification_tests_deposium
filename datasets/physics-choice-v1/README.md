# Physique : choix élémentaires FR/EN, v1

48 cas synthétiques, 24 familles FR/EN, distincts des 132 bases historiques.
Les lois et hypothèses sont données dans les entrées : ce lot mesure leur
application et le choix d’une réponse, pas une connaissance générale de la
physique ni la rédaction de démonstrations. Aucune référence humaine approuvée.

Mécanique : mouvement uniforme/accéléré, forces opposées, énergies cinétique,
potentielle et élastique, rendement, collision parfaitement inélastique.
Électricité : résistances série/parallèle, puissance, effet Joule, condensateur.
Ondes/optique : célérité, période, temps aller-retour d’un écho, lentille mince.
Thermique et fluides : gaz idéal isobare, chaleur, mélange calorimétrique,
surpression hydrostatique. Deux familles exigent de reconnaître une information
insuffisante (masse ou capacité thermique inconnue), avec contre-exemples exacts.

16 cas par difficulté déclarée D1/D2/D3 ; 12 calibration, 36 test. Les variantes
FR/EN d’une famille partagent leur split et leur ordre sémantique. Chaque langue
a six réponses par position a/b/c/d. Ces niveaux sont construits avant les
prédictions et ne constituent pas une échelle externe de difficulté.

Le module `deposium_bench.physics_corpus` calcule les cibles avec `Fraction`,
sans lire les options ni une prédiction. Les nombres/rationnels proposés sont
fixés séparément, puis l’unique correspondance exacte désigne l’option attendue.
`validate_oracle` refuse toute modification des faits, lois, options, référence,
split, langue ou métadonnées de la définition figée. Les annotations, oracles,
références et IDs descriptifs ne sont pas fournis au modèle.

Les contrôles hors ligne vérifient 24 résultats exacts indépendamment inscrits
dans les tests, les contre-exemples insuffisants, les mutations, le rejet de
réponses vides/fausses et la conservation du hash des 132 cas historiques.
La rédaction et les traductions restent `agent_only`, sans revue scientifique
ou linguistique humaine. Ce lot fini ne couvre ni physique expérimentale,
incertitudes de mesure, simulation, problèmes avancés ou documents réels longs.
La première [campagne Flash Q8/Metal du 29 octobre 2026](../../docs/PHYSICS_FLASH_RESULTS_20261029.md)
atteint **39/48**, dont **32/36 test**, avec une couverture scorée complète.
La campagne distincte [Clef Flash Q8/Metal](../../docs/CLEF_FLASH_RESULTS_20261029.md)
atteint **41/48**, dont **31/36 test**. Son gain sur le total vient de la
calibration ; il ne dépasse pas D3 Flash sur le sous-ensemble test.

La [variante directe du protocole Flash Q8](../../docs/PHYSICS_FLASH_UPSTREAM_PROTOCOL_20261029.md)
a été exécutée avec une ancre de contexte séparée, sans dépendance à l’API Turbo
ni passerelle applicative. Le manifeste conserve son état `not_run` de création
du dataset ; la campagne et ses résultats ont leurs archives séparées.

Le contrat est `bench.context-choice`, niveau A. Les liens à
`mcps.evidence-attribution` et `turbov3.rerank` indiquent les capacités concernées,
sans exécution de ces composants. Les longueurs de physique ne sont pas
implémentées ; les paliers historiques portent sur documentaire/maths/chimie.

```bash
python3 -m deposium_bench validate-cases --dataset datasets/physics-choice-v1/cases.jsonl
python3 -m unittest discover -s tests -p 'test_physics_corpus.py' -v
python3 -m deposium_bench run --dataset datasets/physics-choice-v1/cases.jsonl \
  --profile profiles/decision3-turbo-api-robustness.json \
  --output results/physics-NOUVELLE-ARCHIVE
```

Le profil distant nécessite une clé d’environnement et un budget disponible.
L’import et les tests ordinaires n’appellent aucun service. Les références sont
figées avant toute inférence ; elles ne sont pas ajustées aux sorties du candidat.
