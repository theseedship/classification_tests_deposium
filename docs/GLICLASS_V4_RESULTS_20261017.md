# GLiClass v4 9B sur Mac — 17 octobre 2026

**GLiClass v4 9B obtient 117/132 bases (88,6 %) et 20/24 accords Mastra
provisoires**, sur le M5 Pro à 64 Gio unifiés. Les 156 décisions sont valides,
sans erreur, timeout, abstention ni troncature. Le modèle tourne réellement
sur MPS en BF16. D3 conserve le meilleur total dans ce comparatif.

Le détail du **split test** nuance ce total : GLiClass atteint **63/66**, contre
61/66 pour D3 Flash Q8 et 65/66 pour D3 27B Q4. Ces petits écarts sur des
familles corrélées ne démontrent pas une supériorité générale. Les références
restent proposées par agent, en attente de revue humaine.

Le [protocole](GLICLASS_V4_PILOT.md) a été commité avant les prédictions.
Les [tables détaillées](evidence/gliclass-model-comparison-20261017/report.md),
le [JSON agrégé](evidence/gliclass-model-comparison-20261017/analysis.json) et
les [observations MPS et comparaisons appariées](evidence/gliclass-model-comparison-20261017/gliclass-session.json)
proviennent des archives réelles, sans relancer les anciens modèles.

Après fusion de la PR #8 sur un autre poste, l’[index consolidé](RESULTS_INDEX.md)
relie aussi les 22 observations CPU/API et les campagnes de passages. Les cinq
exécutions ci-dessous restent leur panneau Mac distinct ; les exports initiaux
ne sont pas régénérés. Le [guide de reprise](GLICLASS_V4_REPRODUCTION.md) précise
les actifs et archives nécessaires sur un clone propre.

## Scores, couverture et références

| Modèle réellement exécuté | Bases correctes / scorées / total | Dont split test /66 | Accord Mastra / valide / total |
| --- | ---: | ---: | ---: |
| Eos 0,8B Q8_0 | 77/132/132 | 40 | 19/24/24 |
| D3 Flash classe 9B Q8_0 | 124/132/132 | 61 | 20/24/24 |
| D3 Flash classe 9B Q4_K_M | 122/132/132 | 59 | 21/24/24 |
| D3 classe 27B Q4_K_M | 128/132/132 | 65 | 24/24/24 |
| **GLiClass v4 9B BF16** | **117/132/132** | **63** | **20/24/24** |

Les quatre lignes Eos/D3 sont les [campagnes natives historiques](NATIVE_DECISION_RESULTS_20261016.md).
Ce lot ajoute uniquement GLiClass. Il compare des checkpoints, rendus et runtimes
différents, avec des précisions BF16/Q8/Q4 explicites. Il n'isole pas l'effet
de l'architecture, de la taille ou de la quantification.

Les 132 bases représentent **66 familles FR/EN** ; le split test contient
66 cas sur 33 familles. Aucun entraînement ou réglage sur les références de
ce lot n'a été réalisé. Les annotations restent séparées des entrées modèle.
Mastra contient 24 propositions sur 12 familles : **zéro cas sémantiquement
qualifié et zéro référence approuvée humainement**, même en cas d'accord.
Aucun outil, planner réel, routage intégré ou parcours utilisateur n'est exécuté.

| Candidat | Documentaire /76 | Maths /28 | Chimie /28 | FR /66 | EN /66 |
| --- | ---: | ---: | ---: | ---: | ---: |
| D3 Flash Q8 | 72 | 26 | 26 | 62 | 62 |
| D3 27B Q4 | 73 | 28 | 27 | 64 | 64 |
| GLiClass 9B BF16 | 70 | 24 | 23 | 58 | 59 |

Pour GLiClass : train **28/36**, calibration **26/30**, test **63/66**.
Sur Mastra : FR **10/12**, EN **10/12** ; les 12 paires choisissent la même
action. Les erreurs restent présentes dans les archives et dénominateurs.
`unsupported`, `missing`, `error`, `timeout` et `abstain` valent chacun zéro
dans les deux observations GLiClass ; le refus synthétique de longueur est séparé.

Les comparaisons appariées utilisent les mêmes cas, assertions et scorer :

- D3 Flash Q8 → GLiClass : **4 améliorations, 11 régressions**, 113 réussites
  communes et 4 échecs communs ; perte nette de 7/132.
- D3 27B Q4 → GLiClass : **1 amélioration, 12 régressions**, 116 réussites
  communes et 3 échecs communs ; perte nette de 11/132.

Le résultat publié par l'éditeur ne se transpose donc pas en victoire générale
sur notre corpus. La [fiche épinglée](https://huggingface.co/knowledgator/gliclass-v4-9b/blob/14d11a92b5e0bab4a166e1fce4cc0777cac27182/README.md)
décrit un autre protocole et du matériel NVIDIA. Aucun seuil de promotion
produit n'est déduit de ces scores exploratoires.

## Runtime, entrées et mémoire

Le worker appelle les vrais `GLiClassModel` et `ZeroShotClassificationPipeline`
du [code officiel épinglé](https://github.com/Knowledgator/GLiClass/tree/6a00f8067648f25aa0f4f477d167c5f391cb4165),
en `single-label`, avec calibrateur et récurrence du checkpoint. Le contexte
devient le texte, la question le prompt et les descriptions ordonnées les labels.
Le rendu decoder-KV officiel concatène question et contexte ; il est conservé,
sans modification après observation des résultats. IDs de cas, annotations
et actions attendues restent hors du modèle.

Tous les paramètres sont contrôlés sur MPS en BF16 ; les entrées réelles du
décodeur sont contrôlées sur MPS. Attention `eager`, deux threads CPU, un modèle
et un appel à la fois. Un objet
`torch.device('mps')` évite le repli CPU que ferait la chaîne `"mps"` dans ce
pipeline épinglé. Le repli automatique MPS vers CPU est désactivé. Les opérations
PyTorch de référence remplacent les kernels CUDA spécialisés absents sur Mac ;
tokenisation et audit des sorties passent par le CPU.

Les **156 forwards** ont une vérification des IDs et masques réellement reçus
par le décodeur, identiques aux entrées complètes préparées sans troncature.
Chaque appel réussi a un seul forward du backbone observé. Les bases comptent
38–117 tokens natifs complets ; Mastra 116–180. Probabilités natives, somme,
ordre et choix maximal sont contrôlés. Le smoke séparé réussit le choix
synthétique et refuse 6024 tokens avant forward, au plafond local de 4096 ;
**zéro cas scoré** pour ce smoke. Les grandes longueurs ne sont pas qualifiées.

| Observation GLiClass | Bases, 132 appels | Mastra, 24 appels |
| --- | ---: | ---: |
| Initialisation totale adaptateur, s | 13,47 | 12,94 |
| Premier appel adaptateur, ms | 1714 | 1002 |
| Médiane adaptateur, ms | 327 | 444 |
| Médiane pipeline natif synchronisé, ms | 317 | 436 |
| RSS maximal rapporté, Mio | 1171 | 995 |
| Allocation PyTorch GPU maximale échantillonnée, Mio | 17149 | 17149 |

**17149 Mio = environ 16,75 Gio d'allocations GPU observées**. Le RSS seul
sous-estime fortement la mémoire mobilisée ici. Ne pas additionner RSS et
allocation GPU, ni les comparer à un pic absolu de toute la mémoire unifiée.
Le tableau générique des preuves n'observe pas le RSS des campagnes D3 ; leur
suivi natif séparé figure dans le rapport historique.

La garde du groupe reste à **32768 Mio RSS et 8192 Mio de réserve hôte**,
admission de 40960 Mio avant hash des poids. Le code exécuté applique aussi
32768 Mio séparément au compteur d'allocations GPU rapporté, avec le même code
d'arrêt `gliclass_rss_limit` ; les deux compteurs ne sont pas additionnés.
La réserve macOS est une estimation
des pages libres, inactives et spéculatives, distincte de `MemAvailable` Linux.
Mastra conserve un minimum observé de 23583 Mio disponibles. Le manifeste Bases
contient un instantané d'initialisation ; son minimum mémoire ne décrit pas
les 132 appels. Les maxima Bases publiés ci-dessus viennent des sorties brutes.

Les phases ouvrent chacune un worker neuf. Le smoke et les phases précédentes
peuvent réchauffer les caches système/GPU ; ce ne sont pas des démarrages à froid
contrôlés. `inference_ms` inclut le pipeline natif et son audit/synchronisation,
pas uniquement les kernels GPU. Un passage ne qualifie ni latence de production,
ni p95 stable, ni avantage temporel contrôlé sur le serveur llama.cpp de D3.

## Archives, incident d'admission et provenance

Code des prédictions : **`427e4d13a7d4e19179b5d2fb62246426a75a1331`**, checkout
propre. Modèle : **`14d11a92b5e0bab4a166e1fce4cc0777cac27182`** ; code GLiClass :
**`6a00f8067648f25aa0f4f477d167c5f391cb4165`**. Les huit fichiers modèle et
27 fichiers source sont épinglés dans `profiles/gliclass-*-assets.json`.
Poids : 17968000418 octets, SHA-256
`c457f1e8f9c01b5d233eba5858f9985341e49492144982deab3b10e416b961e4`.
Python 3.12.12, Torch 2.14.0, Transformers 5.19.0 et dépendances effectives sont
identifiés dans `runtimes/gliclass/runtime.lock`. Poids et données privées hors Git.

Archives locales conservées sous `results/` :

- `gliclass-smoke-20261017-001/` : contrôle technique, source et stderr scellés.
- `gliclass-native-pilot-20261017-001/` : source complète du banc et de GLiClass,
  manifestes, runtime et sous-archive `bases/` complète, 132 cas scorés.
- `mastra-read-gliclass-20261017-001/` : observation complète séparée, même code
  et même profil ; 24 décisions, zéro cas sémantiquement scoré.
- `gliclass-consolidated-20261017-001/` : références aux sceaux, exporter local,
  orchestrateur et stderr des deux workers conservés après leur arrêt.
- `gliclass-model-comparison-20261017-001/` et `gliclass-paired-*-20261017-001/` :
  analyses hors inférence, sans modifier les archives sources.

L'enveloppe initiale conserve honnêtement **`completed:false`** : après les
132 bases réussies, les 32828 Mio disponibles observés étaient inférieurs à
l'admission de 40960 Mio pour le nouveau worker Mastra. Celui-ci n'a pas été
démarré et aucune archive Mastra n'a été créée dans cette enveloppe. Après arrêt
du worker Bases, l'absence de processus modèle restant et un swap nul ont été
vérifiés. La mémoire est revenue naturellement à environ 48263 Mio ; Mastra
a alors réussi dans un nouveau dossier, sans changer les seuils, poids,
références ou paramètres. L'enveloppe initiale et son sceau restent inchangés.

Le champ historique `bench.source_archive: not_captured` des sous-manifestes
ne décrit pas le `bench-source.tar` supplémentaire de l'enveloppe. Son SHA et
ceux des sceaux sont publiés dans `gliclass-session.json`. Les exports publics
ne contiennent ni sorties de cas, ni chemin absolu utilisateur, ni secret.

## Compatibilité et vérifications

Ce checkpoint nécessite sa tête decoder-KV GLiClass ; notre runtime llama.cpp
D3 n'est pas un backend établi pour celle-ci. L'adaptateur Python isolé
réutilise **le même moteur CLI/notebook, les mêmes données et scorers**.
Seul Mac/MPS est qualifié par cette inférence. Le profil actuel est explicitement
MPS ; la qualification CPU/CUDA sous Linux/WSL reste à faire. Les tests Linux
sans poids ne prouvent pas cette compatibilité matérielle.

La découverte réelle de `.gitmodules` trouve 14 sous-modules, distincts des
15 composants du registre historique. Les préflights archivés distinguent
gitlinks du parent et HEAD locaux. Aucun composant recensé n'est déclaré actif
par ce lot ; ni Supabase, ni stack complète nécessaires. Aucun changement dans
`deposium-inference`, le parent, son gitlink ou Railway, aucun déploiement.
GLiClass 27B est **non téléchargé et non exécuté**.

Vérifications initiales hors poids : 63 tests ciblés Mac réussis, dont 27 nouveaux
tests adaptateur/worker. La validation du vrai manifeste Bases a ensuite révélé
l'absence de sa nouvelle provenance dans le schéma de campagne ; ce schéma a
été complété strictement, avec trois tests de régression couvrant succès,
initialisation échouée et mutations invalides. Aucun runtime, résultat ou sceau
initial n'a changé. Le schéma archivé reste celui de `427e4d13` ; le schéma
corrigé valide maintenant ce manifeste et les profils réels.
Les sorties réelles, leurs sceaux,
entrées sans annotations et audits des 156 forwards ont été revérifiés hors
inférence. Le Markdown détaillé correspond au rendu de son JSON. La suite Mac
historique conserve ses limitations documentées ; aucun succès global Mac
n'est revendiqué.

Après ce correctif, les 30 tests GLiClass ciblés passent sur Mac. La suite
complète Linux amd64 sans poids réussit : **573 tests, dont 556
réussis et 17 skips optionnels**, registre valide (15 composants déclarés,
29 contrats, évaluation `not_run`), puis **10 tests du lanceur réussis**.
Le conteneur est jetable, dépôts montés en lecture seule ; aucune inférence
CPU/CUDA n'y est exécutée. Journaux privés conservés :
`results/gliclass-targeted-mac-20261017-001.log`,
`results/gliclass-schema-mac-20261017-001.log` et
`results/gliclass-linux-20261017-002.log`. Le premier passage Linux de 570 tests
est conservé dans `gliclass-linux-20261017-001.log`. Les workers des deux
observations ont été arrêtés ; leurs scores et captures restent inchangés.

### Raccordement avec la PR #8 — 17 octobre 2026

Le code réuni est figé à **`7aa5397b0f7f73d3ac7bfe25968ea65b1b745467`**, après
fusion du nouveau `main` `796ba198`. Les adaptateurs CPU de la PR #8 et la voie
native de la PR #9 sont conservés. **152 fichiers publics** de données, preuves,
profils et runtimes de cette base sont identiques à leurs objets Git ; les
**trois exports GLiClass** sont identiques à `b6241e9`. Les références ne changent
pas. Le rescore hors inférence retrouve 117/132 ; le rendu Markdown GLiClass
reste identique avec le producteur intégré. Les captures WSL privées ne sont
pas présentes ni réauditées sur ce Mac : seuls leurs fichiers publics sont
vérifiés ici.

Depuis ce code propre, Linux amd64 : **720 tests, 702 réussis, 18 omissions**,
zéro échec ; registre valide ; régénération des 1536 cas passages identique,
validation de leurs 24 familles ; puis **10 tests du lanceur réussis**.
Les omissions sont explicites : 11 tests Node24, deux DuckDB, quatre replays
MCPs soumis à opt-in et un contrôle NumPy. Journal :
`results/gliclass-pr8-integration-linux-20261017-001.log`.
Les observateurs CPU utilisant `/proc` sont vérifiés sur Linux ; cette suite
ne constitue pas une qualification globale de ces adaptateurs sur Mac.

Un **nouveau smoke MPS réel** a réussi avec ce code intégré dans
`results/gliclass-pr8-smoke-20261017-001/` : chargement du même snapshot,
choix synthétique valide et dépassement refusé avant forward, **zéro cas scoré**.
Sources et stderr sont scellés après fermeture du worker. Aucune campagne n'a
été rejouée ; les deux observations initiales restent celles de `427e4d13`.
Le commit de clôture suivant ne change que la documentation.

SHA-256 du sceau smoke :
`c22436bb3fab6ddfc96b4d7091060ca7a2ed43b72b405bc969d28c78f67045d8`.
SHA-256 du journal Linux :
`e0c9b7b252513b11976b4d24505c3bc9ef1a1211dddd281c2706e5db582e90ba`.

Un paquet privé de transfert des preuves initiales est préparé sous
`results/gliclass-transfer-20261017-001/` : 12 dossiers, 165 fichiers,
17 sceaux source vérifiés, environ 3,68 Mio compressés ; extraction sans
écrasement contrôlée. Il exclut poids et environnements. **Il n'a pas été
transféré sur l'autre poste** et reste hors Git, comme les archives d'origine.
