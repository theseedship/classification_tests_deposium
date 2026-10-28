# Pilote progressif D3 mini / flash CPU — 11 octobre 2026

Protocole fixé avant la première prédiction. Les deux candidats sont initialement
`not_run`, zéro cas scoré. Mini est testé en premier ; Flash est lancé uniquement
si ses gardes de démarrage sont satisfaites après fermeture du worker Mini.
D3 26B reste reporté, sans poids téléchargés ni ajout à l’allowlist.
Les qualifications et archives historiques ne changent pas.

## Sources et interface

| Candidat | Révision HF | Paramètres backbone BF16 | Readout FP32 | Fichiers de poids, Gio |
|---|---|---:|---:|---:|
| [Mini](https://huggingface.co/vllm-sr/d3-mini/tree/a475367de0d8133a3c1a2a0dc12303d89cfa2ab4) | `a475367de0d8133a3c1a2a0dc12303d89cfa2ab4` | 4 539 265 536 | 255 × 2 560 | 8,46 |
| [Flash](https://huggingface.co/vllm-sr/d3-flash/tree/521525effa79469d899a570726547dd7f00da3af) | `521525effa79469d899a570726547dd7f00da3af` | 8 392 695 024 | 255 × 4 096 | 15,64 |

Ces tailles sur disque ne sont pas des mesures RSS. Le préparateur vérifie
l’inventaire complet et chaque blob/LFS contre les métadonnées HF épinglées,
puis les comptes et dtypes sur tous les shards et la tête. Le worker contrôle
également les paramètres réellement chargés et la forme du readout.

Même runtime isolé que le [premier pilote D3](D3_CPU_PILOT.md), mêmes pins,
backbone natif CPU BF16, readout FP32, SDPA et kernels PyTorch, deux threads,
batch d’une question, sans averaging par permutation. Le bridge appelle les
vrais `D3.from_pretrained`, `prepare`, `run`, `respond` ; aucune recopie du
moteur. Le fichier `d3_runtime.py` publié est identique à celui de Nano (SHA-256
`6c049aa7d3da8da3738602a2812572879d0a47b03c28c3e33f36d7300257de89`).

## Corpus et mesure

132 bases FR/EN : documentaire 76, mathématiques 28, chimie 28 ; 66 familles
de traduction, 66 cas par langue. Corpus SHA-256
`767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616`,
références `agent_only_pending_human`.

Puis les mêmes 24 propositions Mastra FR/EN, recherche/statistiques/repli,
SHA-256 `d66ec51d9b8d89f46b87b90b80bcd0d45abf1570fa9857c24d9ce39117935497`.
L’accord à ces propositions est provisoire : zéro cas humainement qualifié,
aucun outil exécuté. Annotations et justifications restent hors entrée.

Avant chaque candidat : contrôle synthétique court et overflow, zéro cas scoré.
La séquence native complète est préparée avant le forward, plafond local
4 096 tokens, sans troncature acceptée ; IDs et masque transmis sont vérifiés.
Les erreurs, refus, timeouts et couvertures demeurent distincts.
Les bases sont une passe exploratoire, sans réplication temporelle ni grandes
longueurs. Ni graphe documentaire réel, ni corpus privé, ni qualité des réponses
finales, ni intégration CLI/chat ne sont qualifiés par ces mesures.

## Gardes fixes avant résultats

| Candidat | RSS max Mio | RAM disponible avant worker Mio | Initialisation max s | Choix max s |
|---|---:|---:|---:|---:|
| Mini | 14 336 | 18 432 | 300 | 60 |
| Flash | 18 432 | 22 528 | 360 | 60 |

Un seul worker modèle à la fois. Réserve pendant l’exécution : 4 096 Mio
MemAvailable. Ces seuils sont des conditions d’arrêt prédéclarées, pas des
estimations du pic réel. Le RSS est échantillonné, sans garantie de plafond
instantané. Le swap ne compte pas dans le budget de qualification.

Chaque campagne de bases est bornée à 2 400 secondes externes (SIGINT puis
arrêt forcé après 30 secondes). Mastra conserve sa limite de 600 secondes.
Un échec ou dépassement est conservé ; les gardes ne sont pas relevées après
premières prédictions. Si Flash manque de marge au précontrôle, son état reste
`not_run`, sans déduire un mauvais score. Aucune purge de services, volumes ou
archives, ni modification de la stack, n’est nécessaire pour forcer un essai.

## Conservation et publication

Nouveaux dossiers dans le checkout principal :

- `results/d3-mini-flash-preflight-20261011/` : métadonnées, receipts,
  profils absolus, sources figées et logs ;
- `results/d3-control-{mini,flash}-20261011-001/` ;
- `results/context-base-d3-{mini,flash}-20261011-001/` ;
- `results/mastra-read-d3-{mini,flash}-20261011-001/`.

Poids sous `models/`, runtime sous `.cache/`, données privées et secrets restent
hors Git. Les manifests publics ne publient que chemins relatifs, tailles et
hashes. Sources et gardes sont commitées avant inférence ; une archive source
privée conserve ce gel, distinct de la provenance automatique des captures.
Tous les sous-modules déclarés sont recensés au préflight ; gitlinks, HEAD
locaux et services réellement observés restent séparés.

Les tableaux utilisent des agrégats scellés : scores/dénominateurs, thèmes,
langues, difficulté, splits, tokens natifs, latence, chargement et RSS. Classements
général, routage, domaines et langues sont indépendants ; RAM et latence sont
des axes séparés. Les exports historiques, dont Sol sur sa branche distincte,
sont vérifiés sans recharger les modèles ni réécrire leurs captures.
