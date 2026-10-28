# Context choice v1 — bases exploratoires FR/EN

132 cas synthétiques, 66 familles de traduction, aucun modèle ni service requis.
Les cas utilisent `deposium.case/v2`, le contrat isolé `bench.context-choice` et
le pack `RESEARCH`. Ils ne rejouent pas le normaliseur documentaire MCPs.

| Strate | Familles | Cas |
|---|---:|---:|
| Tâches documentaires déterminées | 36 | 72 |
| Mathématiques déterminées | 12 | 24 |
| Chimie déterminée | 12 | 24 |
| Information insuffisante, deux familles par domaine | 6 | 12 |

Les trois tâches documentaires (`catalog`, `stored_summaries`, `retrieve_answer`)
comptent chacune 12 familles : quatre D1, quatre D2 et quatre D3. Les sciences
comptent chacune quatre familles par niveau. D1 signifie une règle/demande
explicite; D2 combine contraintes ou transformations; D3 combine dépendances,
conditions ou référent contextuel. L'insuffisance forme une strate distincte,
étiquetée D3; elle n'est pas mélangée silencieusement aux 120 cas déterminés.
Ces niveaux ont été définis avant toute prédiction du nouveau corpus.

FR/EN comptent chacun 66 cas. Les traductions partagent leur ordre sémantique
d'options et leur split; par langue, les bonnes positions comptent a:17,
b:17, c:16, d:16. Cette construction a été corrigée avant la première inférence
pour éviter de confondre langue et position. Les réponses sémantiques n'ont
pas changé. Les totaux sont train:36, calibration:30, test:66. Chaque tâche
documentaire a quatre familles train, deux calibration et six test; chaque
science a trois/trois/six familles déterminées. Pour chaque domaine, une famille
d'insuffisance est en calibration et l'autre en test. Les documents synthétiques,
traductions et futures variantes restent dans leur split d'origine.

`input` contient exactement `context`, `question`, et quatre options `id`/`description`.
Tous les faits et règles nécessaires sont visibles dans ces champs. L'option
« information insuffisante » est une réponse sémantique explicite. Une abstention
technique, un timeout, une erreur ou une sortie vide ne la remplacent pas.
Les annotations `evaluation` et `reference` restent hors de l'entrée modèle.
L'enveloppe de transport contient encore l'identité du cas : l'adaptateur doit
envoyer uniquement `input` au candidat, jamais les identifiants descriptifs.

`deposium_bench.research_corpus` expose `build_cases()`, `validate_oracle(case)`
et `write_dataset(output)`. Le dernier refuse toute destination déjà existante.
Le manifeste fixe le hash exact de `cases.jsonl`; le test compare les octets
publiés aux cas reconstruits. Les références v1 et archives historiques sont
inchangées. Les oracles ne consultent aucune prédiction.

Les références documentaires sont des jugements d'agent selon les besoins et
conditions explicites. **Toute la revue reste `agent_only`; aucune revue humaine
ou linguistique n'est revendiquée.** Les problèmes scientifiques ont des oracles
restreints indépendants de la lettre correcte : arithmétique rationnelle,
coefficients polynomiaux, domaines/dimensions, comptage d'atomes, charges et
conservation. Les cas insuffisants scientifiques exhibent deux valeurs ou
structures compatibles qui donnent des réponses différentes. Les options sont
liées à une représentation sémantique, puis la valeur calculée désigne la lettre;
la lettre n'est pas une entrée du calcul.

L'oracle vérifie aussi question, association ID/texte des options, scénario et
documents. Une base garde exactement son entrée et son identité. Pour une
variante de longueur, le contexte de base doit apparaître une seule fois, le
hash d'entrée de base doit correspondre et l'ordre annoncé doit être conservé.
Cela vérifie la conservation des faits initiaux, sans prouver automatiquement
qu'un nouveau distracteur en langage naturel est dépourvu de contradiction.
La revue des variantes reste nécessaire. `evaluation.length` vaut `null` ici.

Ces oracles ne sont pas des solveurs symboliques généraux. Équilibrer une réaction
ne prouve ni sa faisabilité, ni la stabilité d'un composé. Les masses atomiques
des fixtures sont des valeurs exactes explicitement fournies pour l'exercice.
Plusieurs familles partagent une opération de raisonnement; 66 familles de
scénario ne signifient pas 66 algorithmes indépendants. Aucun parcours produit,
droit d'accès effectif, recherche réelle ou score de modèle n'est qualifié.

Les liens à `mcps.document-plan`, `mcps.document-followup`,
`mcps.canonical-document-read`, `mcps.evidence-attribution` et `turbov3.rerank`
désignent des contrats de stack concernés par ces capacités. Ils ne signifient
pas que leurs composants sont exécutés par ces QCM isolés.

```bash
python3 -m unittest tests.test_research_corpus -v
python3 -m deposium_bench validate-cases --dataset datasets/context-choice-v1/cases.jsonl
```

Les extensions DE/ES/IT/PT, longueurs, notations et paraphrases sont des séries
distinctes à revoir, pas des cas déjà inclus dans ces 132 bases.
