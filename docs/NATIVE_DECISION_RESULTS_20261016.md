# Eos, D3 Flash 9B et D3 27B sur Mac — 16 octobre 2026

Quatre campagnes locales réelles sont terminées sur le M5 Pro à 64 Gio unifiés,
via la passerelle Rust de `deposium-inference` et llama.cpp/Metal. **D3 27B Q4
obtient 128/132 sur les bases et 24/24 accords Mastra provisoires**, avec un pic
RSS du groupe de processus de 18,81 Gio. Ce résultat porte sur les modèles
isolés ; aucune intégration produit n'est qualifiée.

Le [protocole natif](NATIVE_SYSTEMONE_PILOT.md) fixe les entrées et les gardes.
Les [tables détaillées](evidence/native-model-comparison-20261016/report.md),
leur [JSON agrégé](evidence/native-model-comparison-20261016/analysis.json)
et les [identités des sessions](evidence/native-model-comparison-20261016/native-sessions.json)
sont calculés depuis les archives initiales, conservées hors Git.

## Résultats et couverture

| Modèle réellement exécuté | Poids, Go décimaux | Bases correctes / scorées / total | Accord Mastra / valide / total | Pic RSS du groupe, Gio |
| --- | ---: | ---: | ---: | ---: |
| Eos 0,8B Q8_0 | 0,82 | 77/132/132 (58,3 %) | 19/24/24 | 1,37 |
| D3 Flash classe 9B Q8_0 | 9,53 | 124/132/132 (93,9 %) | 20/24/24 | 9,39 |
| D3 Flash classe 9B Q4_K_M | 6,60 | 122/132/132 (92,4 %) | 21/24/24 | 6,66 |
| D3 classe 27B Q4_K_M | 19,40 | 128/132/132 (97,0 %) | 24/24/24 | 18,81 |

Chaque modèle a 132 sorties de base et 24 décisions Mastra valides :
`error`, `timeout`, `missing`, `unsupported` et `abstain` valent chacun zéro
dans ces campagnes. Les contrôles synthétiques de refus sont séparés des
156 décisions par modèle ; ils ne gonflent aucun dénominateur.
Les quatre passerelles ont été arrêtées avec un code de sortie nul.

Les 132 bases représentent **66 familles de traductions FR/EN**, pas 132
scénarios indépendants. Les références sont `agent_only`, en attente de revue
humaine. Mastra contient 24 propositions sur 12 familles ; son résultat mesure
un **accord provisoire**, avec **zéro cas sémantiquement qualifié et zéro
référence approuvée humainement**, y compris pour le 24/24. Aucun outil Mastra,
planner, accès documentaire réel ou parcours utilisateur n'est exécuté.

| Modèle | Documentaire /76 | Maths /28 | Chimie /28 | FR /66 | EN /66 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Eos Q8 | 55 | 12 | 10 | 39 | 38 |
| D3 Flash Q8 | 72 | 26 | 26 | 62 | 62 |
| D3 Flash Q4 | 71 | 24 | 27 | 62 | 60 |
| D3 27B Q4 | 73 | 28 | 27 | 64 | 64 |

Les comparaisons appariées utilisent le scorer commun, sur les mêmes cas :

- Eos Q8 → Flash Q8 : 51 améliorations, 4 régressions, gain net de 47/132.
- Flash Q8 → Flash Q4 : 1 amélioration, 3 régressions, perte nette de 2/132.
- Flash Q4 → 27B Q4 : 8 améliorations, 2 régressions, gain net de 6/132.

Le 27B Q4 est donc le meilleur de ces quatre candidats sur ce lot court.
Le 9B Q4 conserve un score proche du Q8 avec moins de RSS observée.
Ces observations uniques sur un corpus limité ne déterminent pas une politique
de routage ni un seuil de promotion ; les régressions restent conservées.
Eos retrouve ses totaux CPU historiques, sans preuve de prédictions identiques
ni de parité numérique CPU/Metal.

## Mémoire, temps et progression

Un modèle chargé à la fois, un slot, un appel et une question à la fois,
contexte de 4096 tokens, texte seul, sans projecteur vision. Les traces natives
montrent respectivement 25/25, 33/33, 33/33 et 65/65 couches déportées sur Metal.
Les réponses scorées ne présentent pas de troncature dans ces traces.
La matrice longue, les médias et le batching concurrent ne sont pas testés.

| Modèle | Garde RSS, Mio | Réserve, Mio | Minimum disponible estimé, Mio | Médiane adaptateur bases / Mastra, ms |
| --- | ---: | ---: | ---: | ---: |
| Eos Q8 | 8192 | 8192 | 35931 | 28 / 31 |
| D3 Flash Q8 | 20480 | 8192 | 30425 | 194 / 206 |
| D3 Flash Q4 | 14336 | 8192 | 30088 | 198 / 212 |
| D3 27B Q4 | 24576 | 8192 | 21303 | 614 / 651 |

Le superviseur sonde le groupe qu'il a créé toutes les 250 ms, avec un budget
de 1200 secondes et arrêt automatique. Aucun arrêt de ressources n'a eu lieu.
Le RSS échantillonné n'est ni un plafond instantané ni une mesure de toute la
mémoire GPU unifiée. La mémoire disponible macOS est une estimation des pages
libres, inactives et spéculatives ; ne pas l'assimiler à `MemAvailable` Linux.

**Le 27B Q8 reste `not_run`.** Ses 28,60 Go de poids ne suffisent pas à prédire
son besoin total. La garde prévue de 32768 Mio plus 8192 Mio de réserve n'était
pas admise par la RAM disponible observée, malgré les 64 Gio physiques.
Après ce constat, les deux variantes Q4 et leurs budgets ont été fixés avant
leurs prédictions. Aucun plafond n'a été relevé pour compléter un score.
Le préflight vérifie l'admission avant le hash des poids, afin de ne pas compter
deux fois les pages du même modèle réchauffées par cette lecture.

Les temps sont descriptifs, après échauffement synthétique, sur un seul passage,
HTTP local inclus. Les 132 bases précèdent Mastra. Le champ générique Mastra
« Single pass without warm-up » des anciennes archives ne décrit donc pas
l'enveloppe native : il est conservé, et cette correction d'interprétation est
explicite. `first_call` signifie premier appel de l'adaptateur concerné, pas
démarrage à froid du moteur. Aucun p95 produit ni avantage CPU/GPU contrôlé
n'est établi. Un retour HTTP ne prouve pas à lui seul un nouveau forward
physique ; les indicateurs inconnus restent inconnus.

## Provenance et compatibilité

Les manifestes `profiles/*-assets.json` épinglent les fichiers et SHA-256.
Les quatre révisions de poids et de runtime sont reprises dans les exports :

| Série | Révision du dépôt GGUF | Runtime llama.cpp |
| --- | --- | --- |
| Eos | `a02a4cc6a4d637003ceede6f8b3b0bb0125b2d66` | fork Decision 2.0 `3c64a581d4f95bb2de409d383741fa5b18d84345` |
| D3 Flash Q8 et Q4 | `3d53d13778bf8035e6e1e534ce489ed052ee5663` | officiel `efe3626b119ff81033e309c3ba07a770bef2c546` |
| D3 27B Q4 | `de9670136f5ddd83e677c89ce041d5b9bb3b0dcb` | même pin officiel D3 |

Les deux campagnes Q8 utilisent le code du banc `87259b1`, les deux Q4
`96b102b`, dans un checkout propre pour chaque campagne. Corpus, assertions,
projection Mastra et scorer sont identiques ; leurs empreintes sont vérifiées
par l'analyse hors inférence. Les références ne sont jamais envoyées au modèle.
Les requêtes contiennent contexte, question et descriptions, avec choix ordinaux.

Le service exécuté vient du vrai dépôt `deposium-inference`, sur
`feat/local-decision-runtime`, HEAD `38b1c643a704b4f9462cdd0f74f9e2d267cc9328`
avec le correctif local non commité : ce HEAD seul ne décrit pas le code exécuté.
Les sessions épinglent séparément le lanceur, le gateway et le runtime ; chaque
enveloppe contient `bench-source.tar` et `service-source.tar` scellés. Le champ
historique `bench.source_archive: not_captured` des sous-manifestes ne recense
pas ces snapshots supplémentaires. Les archives d'origine restent inchangées.

La compatibilité repose sur **la même API `/v1/systemone`, le même lanceur,
les mêmes GGUF et le même banc**, avec un binaire Metal sur Mac et un build
CPU/CUDA sur Linux/WSL. L'export Eos existant échoue avec le pin officiel D3
(330 tenseurs attendus contre 320 chargés) : le fork Decision 2.0 est conservé
derrière cette API, avec sélection explicite du runtime. Le test négatif est
archivé. L'inférence D3 sous WSL/CUDA reste à exécuter sur la machine concernée ;
les tests Linux ne constituent pas cette qualification matérielle.

Les sept fichiers de production protégés (`Dockerfile`, `scripts/start.sh`,
`config/models.toml`, Cargo manifeste/lock, toolchain et compose) sont identiques
à la révision initiale du service. Le pin Docker/Railway `b9222` et le gitlink
du parent sont conservés. Aucun push, déploiement, accès au service Railway,
lecture de secrets `.env`, démarrage de Supabase ou de stack complète.
L'image de production et le matériel CUDA n'ont pas été requalifiés ici.

## Vérifications et conservation

Les quatre enveloppes et les huit sous-archives ont leurs sceaux vérifiés,
et leurs scores ont été recalculés hors inférence. Les exports n'incluent
aucune sortie privée, aucun poids ni chemin absolu utilisateur.
Les contrôles du client couvrent notamment réponses vides ou incohérentes,
identité, probabilités, erreurs, timeouts et refus de contexte. Le smoke vérifie
401 sans clé, 400 pour mauvaise route, 404 pour modèle inconnu et entrée trop
longue refusée. Un 500 D3 n'est classé comme dépassement que si son message
strictement reconnu prouve le dépassement du batch physique de 4096 ; les
autres 500 restent des erreurs. Les smokes échoués sont conservés.

Validation de l'inférence : 108 tests Rust sur Mac et Linux amd64, format et
Clippy Mac ; 10 tests du lanceur sur les deux systèmes. Le banc final a 40
tests ciblés réussis sur Mac et Linux. La vérification finale Linux amd64
réussit : **531 tests, 514 réussis et 17 skips optionnels**, registre valide
(15 composants déclarés, 29 contrats), puis les 10 tests du lanceur réussis.
Ces contrôles sont séparés des campagnes, sans poids ni service modèle.
Un composant déclaré dans le registre n'est pas un composant actif ou testé.
Journal : `results/d3-bench-linux-20261016-004.log`.

La suite historique Mac n'est pas entièrement verte : sur la baseline inchangée
516 tests donnent 51 échecs, 6 erreurs et 31 skips ; sur la première extension
524 tests donnent exactement les mêmes 57 signatures d'échec/erreur dans le
même ordre. Les défauts préexistants de fixtures/workers Mac ne sont pas
requalifiés en succès ; les nouveaux chemins natifs sont contrôlés séparément.

Les archives locales, ignorées par Git, sont :

- `results/eos-native-pilot-20261016-001/`
- `results/d3-flash-native-pilot-20261016-001/`
- `results/d3-flash-q4-native-pilot-20261016-001/`
- `results/d3-27b-q4-native-pilot-20261016-001/`
- `results/native-model-comparison-20261016-001/`
- `results/native-{eos-vs-flash,flash-q8-vs-q4,flash-vs-27b-q4}-20261016-001/`

Les poids restent sous `models/`, les preuves d'application dans
`results/inference-{update-20261015-001,d3-update-20261016-001}/`, et la
vérification finale de production dans
`results/inference-final-verification-20261016-001.json`.
Les [tables agrégées](evidence/native-model-comparison-20261016/report.md)
se reconstruisent avec `scripts/analyze-model-comparison.py`, quatre `--base`
et quatre `--mastra` vers ces archives, dans un nouveau `--output-dir`.
Aucun modèle n'est rappelé pour cette analyse.

## Revue de la PR #9 et point de pause

Les quatre remarques de la [PR #9](https://github.com/theseedship/deposium_jev_tests/pull/9)
sont légitimes et corrigées après les campagnes : fermeture effective du
watcher avant scellement, sortie canonique hors stack/service même en smoke,
validation préalable des identités de modèle et supervision vivante exigée
pour l'exception mémoire Mastra. Une perte de supervision arrête la passe,
conserve les réponses déjà observées et laisse les autres cas manquants.

Vérification hors inférence des correctifs : **52 tests ciblés Mac réussis** ;
**543 tests Linux amd64, 526 réussis et 17 skips**, registre valide, puis
**10 tests du lanceur réussis**. Les journaux sont
`results/pr9-review-mac-20261016-001.log` et
`results/pr9-review-linux-20261016-001.log`. Les quatre enveloppes initiales
et leurs empreintes publiées sont revérifiées et inchangées. Les versions de
code, résultats et qualifications de ces campagnes restent celles indiquées
plus haut ; aucune campagne ni référence n'est régénérée pour ces correctifs.

À la clôture de cette PR, le chantier est mis en pause à la demande de
l'utilisateur. La reprise commencera par D3 mini classe 4B, puis d1-3B,
selon [NEXT_CANDIDATES](NEXT_CANDIDATES.md). La publication séparée du correctif
local de `deposium-inference` reste à traiter. Aucune nouvelle inférence,
installation de poids ou modification de Railway pour cette clôture.
