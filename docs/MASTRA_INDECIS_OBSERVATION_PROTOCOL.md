# Observation Indecis sur les choix Mastra — protocole avant inférence

Conservation du 3 octobre : le binaire CRLF historique a été retrouvé puis
copié, sans exécution, dans `results/indecis-historical-binary-979bb28b/` du
checkout principal. SHA-256 vérifié :
`979bb28b26bd81834ec8bd203617fb9bef99e90ad326c6310671a70e0815bff6`.
Cette copie privée préserve la preuve après disparition du scratchpad ;
elle ne remplace pas le runtime LF courant et n'est pas sauvegardée par Git.

Fixé le 2 octobre 2026 avant les premières prédictions de cette tâche.
Une seule passe locale, modèle isolé ; pas de fine-tuning, ni appel payant,
ni exécution d'outil MCP, ni modification du service.

- Corpus : 24 cas de `datasets/mastra-read-pilot-v0/cases.jsonl`, SHA-256
  `d66ec51d9b8d89f46b87b90b80bcd0d45abf1570fa9857c24d9ce39117935497`.
  Douze familles FR/EN ; calibration 6, test 18. Les références restent toutes
  `pending_human`, sans changements après lecture des sorties.
- Candidat : profil `profiles/indecis-open-cpu-context.json`, mode ouvert non
  entraîné. Source Indecis `339e191405ac9be90f6857f810f478b3312b7f35`, backbone
  `hotchpotch/bekko-embedding-v1-a8m` à
  `c721113d59a1d91b447450324f51c4b3332c924a`. Le profil et les manifests
  existants contrôlent poids, binaire, sources, tokenizer et runtime.
- Budget : 24 appels maximum, un worker, deux threads CPU, garde RSS 3 072 Mio,
  4 096 tokens natifs, 30 s par demande et 300 s pour la phase modèle.
  Le budget de durée est contrôlé entre les appels : un appel déjà lancé
  peut finir après ce délai. Pas d'échauffement, répétition ou nouvelle tentative.
- Aucun téléchargement : poids et worker sont déjà présents. Le lancement
  exige une mémoire disponible supérieure au budget RSS + 1 Gio ; arrêt des
  nouveaux appels sous 1 Gio disponible. Avant cette série, environ 13 Gio
  étaient disponibles, mais presque tout le swap de 16 Gio était occupé.
  L'archive enregistre les relevés effectifs avant et après.

## Projection commune v1, fixée avant les résultats

La préparation v0 plaçait la demande dans `question`, et seulement le cadrage
dans `context`. Or Indecis compare l'embedding du contexte aux options, dont
le texte contient la question. Pour cette tâche de classification, la demande
doit se trouver du côté du texte à classifier. La **projection commune v1**
est donc fixée avant la première inférence, pour tous les futurs candidats :

```text
context = "Demande utilisateur / User request:\n" + message
        + "\n\nPérimètre / Scope:\n" + contexte_du_pilote
question = "Quelle action choisir pour cette demande ? / Which action fits this request?"
options = les descriptions et IDs déjà figés
```

Ces marqueurs bilingues sont identiques pour tous les cas ; aucune annotation
de langue, difficulté ou référence ne choisit le prompt. Les IDs servent au
remapping, sans entrer dans les embeddings. Les anciennes préparations v0
restent intactes, identifiées par leur version et leurs hashes. Les campagnes
historiques des autres tâches ne sont pas rejouées ou modifiées.

## Mesures et interprétation prévues

- Conformité au pool et couverture : choix valides/24, statuts distincts,
  nombre de forwards réels. Un choix `fallback` reste un choix valide.
- **Accord aux propositions synthétiques** : accords/choix valides et accords/24,
  puis par action, langue et split. Matrice d'actions et concordance FR/EN.
  Aucun score de vérité humaine, PASS produit ou seuil de routage qualifié.
- Initialisation séparée ; premier appel identifié ; durées adapter,
  décision et inférence, RSS observée. Médiane et p95 descriptifs, avec leurs
  effectifs et une méthode de percentile explicite. Une passe de 24 cas ne
  mesure pas une latence de production, particulièrement sous pression du swap.
- Un choix constant d'action ou d'ID donne 8 accords/24 sur ces propositions
  équilibrées. C'est un contrôle arithmétique, pas une baseline sémantique.
- Références, profils, entrées exactes, provenance complète de l'adaptateur,
  sorties brutes, compteurs et hashes sont archivés puis scellés. Erreurs et
  cas non exécutés restent visibles. Le worker est fermé en fin de traitement.

## Exécution

```bash
python3 -m deposium_bench observe-mastra-read \
  --profile profiles/indecis-open-cpu-context.json \
  --stack-root ../deposium_fullstack \
  --output results/mastra-read-indecis-001
```

Le moteur refuse les adaptateurs distants, dont Jev HTTP. L'archive appartient
au format d'observation Mastra ; elle n'est pas une ancienne campagne `case/v2`.
La comparaison au planner n'est pas incluse : son pool natif de six outils et
son arrêt texte ne sont pas équivalents aux trois labels de cette tâche.
Les captures avec fournisseur simulé qualifient uniquement le contrat et
l'ordre des appels. Aucun temps issu de ces mocks ne sera comparé au candidat.

## Incident d'initialisation, avant toute prédiction

Le lancement `mastra-read-indecis-001` est conservé, scellé : 24 enveloppes
d'erreur mises en cache, zéro forward et zéro décision valide. Le contrôle
`indecis_build_invalid` a refusé le worker : son manifeste enregistrait
`worker_source_sha256=10f8a19c10ed0eee9b92bb9c153219718deedfe2e4ff405672b9f4233eac18bd`,
alors que les trois fichiers du bridge déjà committés donnent
`9db9bd2a8f6602925cac91a5be4337c0b085ef9dea5e7549b26377b9656fe53b`.
Le binaire et les sources amont correspondaient bien à leurs empreintes
enregistrées ; la cause historique du décalage du bridge n'est pas établie.
Ces erreurs ne mesurent ni qualité ni vitesse du modèle.

Le 2 octobre, `python3 runtimes/indecis/build_worker.py --test` reconstruit
hors réseau à partir des sources présentes et vérifie les neuf tests Go.
Aucun source du bridge, poids, prompt ou référence n'est changé. Le nouveau
binaire est `979bb28b26bd81834ec8bd203617fb9bef99e90ad326c6310671a70e0815bff6`,
contre `b0cc2d933b985a535b4d4b6852289c97b0f4375896a92915b03ba329694842b0`
auparavant. Le manifeste de build est renouvelé pour cette reconstruction,
sans relâcher les contrôles d'identité. Les anciens résultats restent intacts.

**Cause établie le 3 octobre :** le décalage venait des fins de ligne. Le
manifeste initial pinait les octets LF du bridge ; le checkout WSL, converti en
CRLF par `core.autocrlf`, donnait `9db9bd2a…`, et la reconstruction du 2 octobre
a épinglé ce digest CRLF ainsi que le binaire `979bb28b…`. Avec `eol=lf` imposé
par `.gitattributes`, `build_worker.py` redonne, deux fois de suite, exactement
`worker_source_sha256=10f8a19c…` et le binaire `b0cc2d93…` du manifeste
d'origine. Le manifeste est donc revenu à ces valeurs. L'observation
`mastra-indecis-observation-20261002` a été produite avec le binaire CRLF
`979bb28b…` et garde ses empreintes ; elle n'a pas été rejouée avec le binaire
LF (poids requis), et son équivalence de comportement n'est pas démontrée.

La CLI renvoie désormais un échec technique si le passage ne produit aucun
choix valide. La première passe d'inférence est relancée dans une nouvelle
archive `results/mastra-read-indecis-002`, avec le même protocole et le budget
de 24 forwards initialement prévu ; aucun résultat de prédiction n'a encore
été observé au moment de cet ajout.
