# Indecis : pilote ouvert et spécialisation future

La lecture initiale de sources au **2 octobre 2026** a été réalisée sans
installation, poids, entraînement ni inférence. Le pilote ouvert a ensuite été
exécuté avec la source du banc `2f1875d`, sans entraîner le backbone :
**44/132 bases FR/EN**, dont documentaire 32/76, mathématiques 2/28 et chimie
10/28. Sur les longueurs, 81/300 cas scorés sont corrects sur 378; 24 cibles
sont irréalisables et les 54 variantes 8k sont refusées avant forward au budget
natif de 4096 tokens par séquence. Le panel temporel répété de 18 bases de
calibration donne 25,989 ms de décision médiane et 35,389 ms au p95.
Voir le [rapport de résultats](INDECIS_RESULTS.md) et le
[protocole exécuté](INDECIS_PILOT.md).

R3 est donc réalisé à titre expérimental. Cette note conserve l'analyse
préalable et prépare la spécialisation R4, après revue des références R1 et
nouveaux cas indépendants R2 dans la [local-only material, not distributed](PROTOCOL.md). Aucun entraînement
ou fine-tuning n'a été mesuré; aucune intégration produit n'est qualifiée.
Les comparaisons réutilisent les archives historiques Julia, GLiNER et Jev,
sans nouvelle exécution de ces candidats.

## Révision et mécanisme

Source examinée : [Bornholm/indecis](https://github.com/Bornholm/indecis/tree/339e191405ac9be90f6857f810f478b3312b7f35),
commit `339e191405ac9be90f6857f810f478b3312b7f35`, licence MIT. Le README
annonce une bibliothèque expérimentale, avec API susceptible de changer.
Le cœur est en Go 1.27, sans dépendance externe à la bibliothèque standard;
les modules serveur et annotation `teacher` sont séparés. L'encodeur ModernBERT
peut être entièrement ajusté par entraînement : forward/backward et optimiseur
implémentés en Go, avec mise à jour sparse de la table d'embeddings.
Sources : [README](https://github.com/Bornholm/indecis/blob/339e191405ac9be90f6857f810f478b3312b7f35/README.md),
[architecture](https://github.com/Bornholm/indecis/blob/339e191405ac9be90f6857f810f478b3312b7f35/docs/architecture.md).

| Voie | Ce qui est appris et fourni à l'appel | Conséquence pour le banc |
|---|---|---|
| `Fit` → `Decide` | Encodeur + têtes `noul`, `choice`, `score`; questions et classes fixes | Adapté à une taxonomie récurrente. Ajouter une classe impose un nouvel entraînement. Les `Instructions` du schéma ne sont pas lues par le modèle. |
| `FitEmbeddings` → `DecideOpen`/`ChooseIn` | Encodeur contrastif; options décrites au moment de l'appel | Choix dynamiques possibles, y compris avec le backbone brut comme référence sans entraînement. Comparaison d'embeddings, sans génération de texte ni preuve de calcul. |

En mode ouvert, l'instruction est associée à chaque description; le pilote
sérialise chaque option sous la forme `description + '\n' + question`,
avec le contexte encodé séparément. Le prototype
d'une option combine nom, description et exemples. Les distributions sont un
softmax de cosinus, dont la calibration n'est pas acquise. En mode fixe,
`Calibrate` ajuste des températures sur un jeu réservé; vérifier ensuite
Brier/NLL/ECE et erreurs par classe. Sources :
[schema.go](https://github.com/Bornholm/indecis/blob/339e191405ac9be90f6857f810f478b3312b7f35/schema.go#L50),
[mode ouvert](https://github.com/Bornholm/indecis/blob/339e191405ac9be90f6857f810f478b3312b7f35/decide_open.go),
[prototypes et choix](https://github.com/Bornholm/indecis/blob/339e191405ac9be90f6857f810f478b3312b7f35/fit_embed.go#L295).

Le serveur accepte `/v1/systemone`, mais le nom d'une question correspondant
à une tête apprise sélectionne cette tête, indépendamment des nouvelles
instructions. Le même contrat HTTP que Jev n'implique donc pas le même
comportement. [Contrat serveur](https://github.com/Bornholm/indecis/blob/339e191405ac9be90f6857f810f478b3312b7f35/docs/serving.md).

## Ressources, langues et longueur

Le backbone conseillé est `hotchpotch/bekko-embedding-v1-a8m`, révision
`c721113d59a1d91b447450324f51c4b3332c924a` : MIT, quatre couches, dimension
384, couverture de plus de 100 langues annoncée. « 7,7 M » exclut la table
d'embeddings : les métadonnées HF comptent **105 975 168 paramètres BF16**.
Les trois fichiers nécessaires totalisent **246 317 545 octets** :
`config.json` 1 207, `model.safetensors` 211 952 896 et
`tokenizer.json` 34 363 442. Le pilote épingle ces fichiers et leurs SHA-256;
les exemples de téléchargement de l'auteur utilisent `main`.
[Backbone épinglé](https://huggingface.co/hotchpotch/bekko-embedding-v1-a8m/tree/c721113d59a1d91b447450324f51c4b3332c924a),
[guide de chargement](https://github.com/Bornholm/indecis/blob/339e191405ac9be90f6857f810f478b3312b7f35/docs/creating-a-model.md).

L'auteur mesure environ **30 minutes pour 20 000 exemples sur deux epochs**,
sur Core Ultra 7 265U, tous cœurs. Son détecteur spécialisé atteint 1,5 ms
à 15 tokens et 23 ms à 256 tokens sur un cœur, avec int8/SIMD; mémoire prête
30 MB et pic 82 MB dans ce benchmark. Ce ne sont pas des mesures Deposium,
ni une estimation garantie de l'entraînement complet. Son guide synthétique
900 exemples/24 tests obtient seulement 75 % pour le sujet et 58,3 % pour
l'urgence : volume synthétique et vitesse ne suffisent pas à qualifier la
généralisation. Sources : architecture ci-dessus,
[mesures d'inférence](https://github.com/Bornholm/indecis/blob/339e191405ac9be90f6857f810f478b3312b7f35/docs/inference.md),
guide ci-dessus. Le pilote local mesure désormais FR/EN et les familles
scientifiques du corpus historique. Langues mélangées, autres langues et
spécialisation scientifique restent à évaluer; ne pas assimiler couverture
annoncée et qualité qualifiée.

**Risque bloquant pour un adaptateur : troncature silencieuse.** `WithMaxLen`
vaut 256 par défaut. `EncodeMax` coupe à droite; `EncodePair` répartit le
budget entre contexte et texte, puis coupe les deux. Avant tout forward,
compter l'encodage complet avec ses tokens spéciaux, pour le texte et chacune
des options/exemples; comparer les identifiants complets à ceux réellement
consommés. Un dépassement devient `unsupported`, sans découpage automatique.
Le compte natif Bekko et le palier de référence Julia restent distincts,
sur les mêmes octets de cas. La qualité au-delà de 256 tokens n'est pas
mesurée par l'auteur malgré des chronométrages longs.
[Tokenizer](https://github.com/Bornholm/indecis/blob/339e191405ac9be90f6857f810f478b3312b7f35/tokenizer/tokenizer.go#L350),
[protocole local](CONTEXT_LENGTH_PROTOCOL.md).

Le pilote met en œuvre ce contrôle pour le contexte et chaque option, avec
un budget de 4096 tokens natifs par séquence. Les 54 variantes 8k sont
`unsupported`, sans forward; elles n'apportent aucune mesure de qualité à ce
palier. Les résultats sur les paliers admissibles restent exploratoires.

## Décisions Deposium pertinentes

Lecture locale : parent fullstack `25dbf06d8e90cea5675a498959e9d9db1fb7a3e0`,
HEAD MCPs `391be12078b1f3daa24a50c31c3a39eb72d7fb94`, différent du gitlink
parent `acb41319e00bed5452da6a6fce9eee36ad2a87f0`. Ce sont des états source,
sans preuve de service actif. `.gitmodules` et
[registre](../deposium_bench/data/stack-registry.json) recensent 15 composants
et 29 contrats. Les quatre entrées du
[bridge MCP](../bridges/mcps-decisions.mjs) appellent les fonctions réelles.

| Besoin | Candidat plausible | Frontière déterministe à conserver |
|---|---|---|
| `document-plan` : `catalog`, `stored_summaries`, `retrieve_answer` | Tête fixe entraînée sur demandes/historiques revus | Contraintes de sélection, accès et disponibilité documentaire |
| `document-followup` : reconnaître un suivi ou une demande ambiguë | Classification d'intention/clarification | Résolution des IDs, chat/espace et sélection complète |
| `scope-dispatch`, `semantic-source-route` | Proposition de type de source; mode ouvert pour choix disponibles dynamiques | Priorité des sélections explicites, connecteurs autorisés/disponibles et limites de ressources |
| Mathématiques/chimie | Type de problème, outil à appeler, formule candidate, information insuffisante | Calcul, unités, domaine de définition, dimensions, équivalence et bilan atomique/charge vérifiés par un oracle adapté |

Sources applicatives sous `deposium_fullstack/deposium_MCPs/src` :
`services/chat-document-request-plan.ts`, `services/chat-document-selection.ts`,
`services/scope-dispatcher.ts`, `services/source-route-resolver.ts`. Les IDs documentaires et
connecteurs d'un utilisateur ne constituent pas une taxonomie fixe à apprendre.
Les oracles du [corpus scientifique](../deposium_bench/research_corpus.py)
couvrent des familles finies; ils ne constituent pas un vérificateur général
de mathématiques. Aucun contrat actuel ne qualifie ici un calculateur produit.

## Protocole de spécialisation proposé

1. **Séparer deux expériences.** Le mode ouvert sans entraînement est désormais
   mesuré sur le choix générique avec sérialisation figée question/contexte/options.
   La prochaine expérience serait une tête documentaire spécialisée entraînée
   sur un corpus distinct,
   comparée au vrai harness MCP. Comparer un modèle spécialisé à Jev sur cette
   tâche précise, sans présenter ce résultat comme une décision agnostique.
2. **Acquérir des références revues.** La base actuelle contient 132 cas,
   66 familles FR/EN, tous `agent_only` : 18 familles train, 15 calibration,
   33 test. Ne pas recycler le test déjà observé pour entraîner ou choisir les
   hyperparamètres. Constituer des familles nouvelles à partir de situations
   autorisées et anonymisées, avec classe rare, négation, suivi, ambiguïté,
   hors domaine et langues mélangées. Déterminer le volume nécessaire par
   courbe d'apprentissage et incertitude par classe, sans promettre qu'un petit
   nombre d'exemples suffira.
3. **Figer les splits avant entraînement.** Grouper document/scénario,
   traduction, paraphrase, variantes longues et template générateur dans la
   même famille; réserver calibration et test indépendant, si possible
   temporel. Indecis fournit `Family`/`HoldOut`, mais sans `Family` il sépare
   par texte : renseigner explicitement cette identité.
   [Implémentation](https://github.com/Bornholm/indecis/blob/339e191405ac9be90f6857f810f478b3312b7f35/dataset/dataset.go#L112).
4. **Conserver inconnus et abstention.** Ajouter des inconnus réalistes et
   des négatifs proches. Régler une éventuelle abstention uniquement sur
   calibration, puis figer la règle et rapporter risque/couverture. Une option
   « information insuffisante » n'est pas le statut d'abstention; `unsupported`,
   `error` et `timeout` restent séparés. Aucun seuil softmax arbitraire ni
   seuil de bascule LLM ne serait qualifié par cette seule expérience.
5. **Faire un pilote borné et archivé.** Budget futur proposé : CPU deux
   threads, un processus, plafond 1 GiB d'artefacts et 3 GiB RSS; arrêt sur
   dépassement, durée d'entraînement plafonnée et annoncée avant lancement.
   Épingler modèle/code/Go, données, schema, tokenizer, paramètres et scorers.
   Publier qualité par famille/langue/classe, couverture, erreurs, coût de
   préparation des options, décision froide/chaude et RSS. Le cache d'options
   réduit leur réencodage; il ne rend pas le coût indépendant de leur nombre.
   Aucun cache de réponses ni échantillon du test dans l'entraînement,
   la calibration ou la réduction du vocabulaire.

La prochaine décision utile est de choisir une taxonomie et d'obtenir des
familles revues. Le pilote ouvert fournit une référence sans entraînement;
cette note n'engage aucun nouvel entraînement, téléchargement ou remplacement
de composant applicatif.
