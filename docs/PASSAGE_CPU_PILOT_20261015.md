# Pilote CPU passages multilingues — protocole du 15 octobre 2026

Protocole initial préparé avant toute prédiction sur le nouveau corpus. Le
préflight BGE 001, sans cas scoré, a ensuite nécessité le binaire CPU décrit
ci-dessous ; code et réglages de D3 restent ceux du gel initial. Ce lot mesure
le modèle seul sur des passages synthétiques ; il ne remplace aucun composant
applicatif et ne modifie aucun service actif. Aucun appel API Jev, document
privé ou entraînement. Les références et traductions restent proposées par
agent, sans revue humaine. Les classements historiques à 132 bases sont conservés.

## Corpus et sélection figés

Source : commit `7ed178d`, intégré sans changement des données à la branche
`feat/passage-rerank-cpu-20261015`, avec les 22 observations précédentes.
Corpus complet : 1 536 cas, 24 familles, SHA-256
`35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476`.
Régénération et validation hors modèle réussies.

Premier lot : **128 cas du split test**, `position_rotation=0`, huit familles
et huit scénarios ; les six directions monolingues FR, EN, DE, ES, IT, PT et
les croisements FR→EN / EN→FR, chacun en `full` et `head_384`.
Chaque direction/vue comporte huit cas. Aucun réglage sur train, calibration
ou test ; règles de composition déclarées ci-dessous avant mesure.
Empreinte des IDs triés, séparés et terminés par LF :
`e79262de0cad7b920be3d3ad8f3d6e247170a8d7025385087bf044ab7ab475a7`.
Export ranking JSONL préparé :
`44c91f74862e2588e643a0d1202df635f5cf91d22313a88611ccafca0cc174df`.

Les deux vues sont souvent identiques. Les doublons ne sont ni des faits
indépendants, ni de nouveaux appels : les requêtes de choix strictement
identiques, par contrat et entrée canonique, sont dédupliquées ; leurs résultats
sont réattribués aux identités logiques. Les échecs sont conservés aussi et
ne sont pas réessayés. Les temps physiques, logiques sans cache et avec cache
sont distingués. L'ordre des quatre passages n'est pas varié dans ce premier lot.

## Candidats et ressources

| Candidat | Identité | Paramètres / format | Exécution |
|---|---|---|---|
| Reranker de référence | BGE v2-m3 INT8, poids de l'image locale TurboV3, binaire natif CPU épinglé | ONNX INT8, hash du graphe ci-dessous | Processus Docker temporaire, CPU, sans GPU ni réseau externe ; aucun appel au service actif CUDA |
| Modèle à choix | `vllm-sr/d3-lite` à `a8d25a91ef75552803f7009d25b7bd435991abd9` | Backbone 852 985 920 paramètres BF16, tête 261 120 FP32 | Adaptateur D3 existant et helper natif, deux threads, plafond 4096 tokens sans coupe acceptée |

Image de référence :
`sha256:4c5c2098b21735baf7d3b05206c59c5da69fd4a604194ed258802200f4bcb7d2`.
ONNX BGE :
`dd1b7800bdfde4afd4aab79ea75752250e11fa043ddc397cbf8e8a1c9a809b44`.
Tokenizer :
`8bf8afbfd11306bd872018c53bfdf2e160a56f8edbcf49933324404791c148d3`.
Le premier préflight isolé `passage-bge-cpu-20261015-001` n’a scoré aucun cas :
le binaire CUDA de cette image échoue au préchargement sans GPU. Son archive
et ses logs sont conservés, son conteneur supprimé.

Pour le nouvel essai CPU, un exécutable natif déjà compilé est copié depuis
le dépôt Turbo, puis monté en lecture seule dans le conteneur isolé : SHA-256
`0cca8fc00aeb5dfb15fe2c737ecd23433daed99437b7ebe037a34793176d1759`.
Son fichier Cargo fingerprint `features=["default"]`, sans CUDA, est épinglé à
`fe8554f54474197cbe3039759d550ef83ac449699add3733a921ce231d1d68bf`.
Le binaire CPU effectif est revérifié après démarrage, avec une preuve de
provider `cpu` avant toute requête du corpus. Le binaire de l’image reste
identifié séparément. Les poids, le tokenizer et la bibliothèque ORT sont les
mêmes ; l’exécutable diffère du service actif. Le commit source exact de ces
binaires n’est pas établi : leurs hashes sont l’identité des artefacts. Le HEAD
local du dépôt Turbo ne constitue pas leur provenance source.

Le reranker natif reçoit la question originale et les quatre textes visibles,
sans expansion ni sélecteur de fenêtre MCPs. Son plafond de 512 tokens par paire
sera contrôlé avec le tokenizer correspondant avant inférence ; un dépassement
non maîtrisé reste un refus, pas une troncature silencieuse. Le conteneur doit
prouver son provider CPU, rester sous 4 Gio, utiliser deux CPU et être supprimé
après archivage. Une indisponibilité de ce chemin laisse la référence `not_run`,
sans substitution par le fallback lexical MCPs ou par un modèle différent.

D3 conserve ses gardes : 8 Gio de mémoire disponible avant worker, plafond RSS
6 Gio, réserve hôte de 4 Gio entre appels, délai 60 s par décision, budget
2 400 s et au plus 1 200 appels physiques. L'initialisation, les erreurs et les
arrêts sont archivés. Aucun seuil ne sera relevé après une prédiction. Les
candidats sont exécutés séquentiellement ; aucune purge ou modification de la
stack pour leur faire de la place. Poids retéléchargés dans `models/`, hors Git.

## Tâches séparées et composition sans apprentissage

- **Référence** : classement natif BGE des quatre passages, top-k=4.
- **Remplacement exploratoire** : quatre choix de pertinence D3, grades 3/2/1/0,
  classement décroissant ; égalités départagées par l'ordre d'entrée original.
  Il s'agit d'un classement dérivé de classes, pas d'un cross-encoder D3 natif.
- **Complément** : mêmes grades D3, égalités départagées par le classement BGE.
  Aucun passage n'est supprimé. Une réfutation directe conserve la classe haute.
- **Soutien d'affirmations** : `supports`, `refutes`, `insufficient`, séparé du
  classement. Une même valeur numérique n'est pas un critère suffisant d'appui.
- **Possibilité de répondre** : choix sur les quatre passages, preuves suffisantes,
  insuffisantes ou contradictoires. Cette décision est publiée séparément ; elle
  ne valide pas un pool réduit à top-1/top-3 ni une réponse générée.

Projections logiques : **128 classements, 512 choix de pertinence, 768 choix de
soutien et 128 choix de possibilité de répondre**. Déduplication des choix :
**728 appels physiques attendus**, tous axes confondus. Les labels, spans, grades,
familles, scénarios et splits ne franchissent jamais l'adaptateur.

## Mesures et limites de décision

Scorers communs du pack : nDCG@1/3/4, MRR@4, rappel@1/3/4 ; pour les choix,
réussites, classes, macro-moyenne et couverture. Montrer les dénominateurs
éligibles, observés et totaux ; erreurs/absents valent zéro uniquement quand
la métrique possède une référence définie. Sans preuve pertinente, MRR/rappel
restent non définis ; sans gain idéal, nDCG reste non défini. Le rappel@4 d'une
permutation complète n'est pas discriminant. Conserver les métriques par langue,
direction, scénario et vue. Huit familles indépendantes seulement dans ce lot.

Complément de lecture : capture d’un ensemble suffisant complet à top-1/top-3
sur les 88 cas répondables, et présence à top-3 d’appui et de réfutation
pour une même affirmation sur les 16 conflits. Un passage absent ou un
classement en échec vaut zéro au dénominateur éligible.

Mesurer séparément initialisation, latence physique par paire/choix/pool, coût
reconstruit sans cache, coût de la composition et RAM. La déduplication de vues
synthétiques ne doit pas devenir une promesse de cache en production. Les temps
CPU sont descriptifs, avec pression hôte variable. Le CPU du conteneur et ses
contraintes diffèrent de celles d'un processus hôte ; déclarer les deux.

Une progression sur ce pack autoriserait un essai sur un corpus documentaire
revu, puis les niveaux B/C avec le vrai point d'injection, les guards, les outils
et les citations. Aucune qualité de réponse finale, récupération initiale,
robustesse aux autres ordres, seuil de filtrage ou intégration CLI/chat n'est
qualifiée par ce lot. Les échecs et résultats négatifs sont publiés.

## Contrôle complémentaire des quatre ordres, avant son inférence BGE

Le premier essai à rotation 0 est conservé. Son contrôle hors modèle donne
nDCG@1 = 1 et nDCG@3 = 1 en conservant simplement l’ordre d’entrée : l’ordre
auteur favorise les preuves. Ce sous-ensemble ne permet donc pas d’attribuer
une avance de classement au modèle D3. Les labels et les cas ne sont pas modifiés.

Le contrôle complémentaire couvre **les 512 cas du split test**, huit familles,
huit directions, deux vues et **les quatre rotations prévues dans le pack**.
BGE sera réellement rejoué sur ces 512 pools, dans un nouveau conteneur CPU
avec les mêmes hashes, paramètres et gardes, toujours sous 1 200 s. Les sorties
et le préflight antérieurs restent archivés. Aucun réglage de la règle de
classement par grades, des prompts ou des seuils après observation.

Les jugements D3 de pertinence seront repris uniquement si le contrat et
l’entrée complète sont exactement identiques à ceux d’un appel physique scellé.
Le changement de position du passage n’est pas visible dans cette projection
par paire ; cette réattribution est un calcul hors inférence, sans nouveau
forward D3. Toute entrée absente du cache exact provoque un refus, sans prédiction
inventée. Les décisions de soutien et de réponse possible restent celles du
premier lot à 128 cas : aucune décision sur un pool réordonné n’est extrapolée.

Comparer les contrôles sans modèle « ordre initial » et « ordre inversé »,
les grades D3 seuls et les grades départagés par BGE, puis les scores par
rotation, direction, scénario et vue. Publier aussi les égalités de grades.
Les coûts D3 sont des reconstructions depuis les appels observés ; les coûts
BGE des 512 pools sont de nouvelles mesures. Les variantes restent liées à
huit familles seulement : cette extension corrige un biais d’ordre, pas le
manque de références humaines ni l’absence de corpus documentaire réel.

Export ranking du contrôle 512, SHA-256 :
`06e3321ef8397ea231d189245256c4145aefb14f2aaf55d6190eff71b037c1b9`.
IDs triés séparés/terminés LF :
`7ff58c3268c0469e886f9a7258ac430672d9cc3bb45c8628ddf1e1ff0d97bc38`.
Les 2 048 choix logiques de pertinence correspondent à **264 entrées D3 exactes**
déjà observées ; zéro nouvel appel D3 est nécessaire pour ce contrôle d’ordre.
