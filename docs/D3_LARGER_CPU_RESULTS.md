# D3 mini / flash : résultats CPU du 11 octobre 2026

**Flash obtient 124/132 bases, un cas de plus que Jev historique (123/132).**
C’est le meilleur total observé ici, sans preuve d’une avance robuste sur cet
échantillon exploratoire. Mini obtient 119/132, contre 117/132 pour Nano.
Les deux nouveaux candidats atteignent 20/24 accords Mastra provisoires,
comme Jev ; le nombre de replis retrouvés reste 4/8 pour chacun.

[Classements complets à 19 modèles](evidence/model-comparison-d3-larger-overview-20261011/report.md),
[agrégats détaillés à 18 modèles](evidence/model-comparison-d3-larger-20261011/report.md)
et [protocole fixé avant inférence](D3_LARGER_CPU_PILOT.md).
Le JSON détaillé contient thèmes/sous-tâches, langues, croisements, difficulté,
splits, couverture et statuts, matrice de routage, tokens, phases temporelles,
p95/max et empreintes. Sol conserve son export historique séparé.
Les classements général, routage, domaines et langues sont triés indépendamment.

## Bases : scores et ressources

| Modèle | Bases /132 | Documentaire /76 | Maths /28 | Chimie /28 | FR /66 | EN /66 | Médiane / p95 s | RSS worker max Gio |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D3flash | 124 | 72 | 26 | 26 | 62 | 62 | 10.08 / 15.01 | 13.75 |
| Jev | 123 | 67 | 28 | 28 | 62 | 61 | 0.28 / 0.32 | non mesuré (API) |
| D3mini | 119 | 71 | 24 | 24 | 60 | 59 | 5.97 / 8.29 | 7.55 |
| D3nano | 117 | 68 | 26 | 23 | 58 | 59 | 2.08 / 2.45 | 3.39 |

Flash gagne un cas documentaire et deux cas dans chacun des domaines scientifiques
par rapport à Mini. Il mène le documentaire à 72/76 ; Mini est à 71/76.
En maths, Flash et Nano sont à 26/28, derrière Jev à 28/28. Flash mène la
chimie locale à 26/28, derrière Jev à 28/28. Les tables par langue montrent
les différences FR/EN sans les masquer dans le total.

Le surcoût CPU est mesuré sur les mêmes entrées courtes : Flash prend environ
4,84 fois la médiane de Nano et 4,05 fois son pic RSS ; Mini environ 2,87 et
2,23 fois. Ces ratios décrivent ces captures, sans débit ni garantie de latence.
La médiane exclut le chargement ; le p95 est descriptif d’une seule passe.
Jev reste la référence distante historique, avec réseau et sans RAM serveur mesurée.
Aucun nouvel appel API Jev n’a été lancé.

## Routage : accord provisoire

| Modèle | Accord /24 | Recherche /8 | Statistiques /8 | Repli /8 | FR /12 | EN /12 | Médiane / p95 s | RSS worker max Gio |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D3mini | 20 | 8 | 8 | 4 | 10 | 10 | 7.33 / 8.24 | 7.36 |
| D3flash | 20 | 8 | 8 | 4 | 9 | 11 | 13.22 / 14.40 | 13.59 |

Même total et mêmes comptes par action, mais pas les mêmes résultats par langue :
Mini 10/12 dans chaque langue ; Flash 9/12 FR et 11/12 EN. Une taille supérieure
ne donne donc pas un meilleur accord sur toutes les sous-populations.
Ces accords ne sont pas une mesure de l’exécution des outils ou des réponses.

## Entrées, contrôles et limites

312 décisions valides : 132 bases + 24 propositions pour chacun des deux modèles.
Couverture 100 %, aucun `error`, `missing`, `unsupported`, `timeout` ou abstention
sur ces campagnes. Tous les forwards sont observés ; aucune troncature acceptée.
Deux contrôles synthétiques par modèle sont séparés : court valide à 108 tokens,
overflow à 20 098 tokens refusé avant forward, zéro cas scoré.

Tokens natifs min / médiane / max : bases **128 / 165 / 211**, Mastra
**201 / 227,5 / 264**. Le plafond local de 4 096 tokens est une garde,
pas une longueur utile démontrée. Longueurs, temps répétés, images/vidéo,
Noul/Score, permutations et GPU restent non mesurés pour ces nouveaux candidats.
Les anciens [résultats de longueurs](evidence/length-comparison-20261004/report.md)
et [temps répétés](evidence/timing-comparison-20261004/report.md) sont conservés.

Références bases `agent_only_pending_human`, Mastra `pending_human` : zéro
référence humaine qualifiée. Aucun outil exécuté, aucun corpus privé envoyé,
aucune récupération graphe ni qualité de réponse finale ou intégration CLI/chat
qualifiée. Le résultat devant Jev porte uniquement sur ces 132 bases.

## Runtime et ressources

Le vrai runtime `D3.prepare/run/respond` est réutilisé, sans moteur recopié.
CPU, deux threads, batch d’une question, backbone natif BF16, tête FP32, SDPA,
sans permutation. Même runtime isolé et verrouillé que le premier lot D3.
Tous les fichiers HF sont vérifiés ; les headers comptent tous les shards,
puis le worker vérifie les paramètres réellement chargés et les formes de tête.

| Candidat | Fichiers de poids Gio | Paramètres backbone BF16 | Head FP32 | Initialisation bases / Mastra s |
|---|---:|---:|---:|---:|
| D3mini | 8.46 | 4,539,265,536 | 255 × 2560 | 16.47 / 16.02 |
| D3flash | 15.64 | 8,392,695,024 | 255 × 4096 | 24.47 / 23.94 |

L’initialisation ci-dessus est le temps adaptateur, vérification des assets et
worker compris ; elle diffère du seul chargement natif, également archivé.
Poids sur disque et RSS résident sont des grandeurs différentes.
Gardes inchangées : Mini RSS 14 Gio / démarrage disponible 18 Gio ; Flash
18 Gio / 22 Gio ; réserve courante 4 Gio. Un seul worker modèle à la fois.

WSL dispose de 43,11 Gio au total. Flash avait environ 24 Gio disponibles après
Mini avant téléchargement, puis environ 24,8 Gio avant son contrôle. La stack
reste active ; caches, autres services et swap peuvent influencer ces mesures.
Le swap n’est pas utilisé comme budget de qualification. Il n’est pas vide
(environ 3,34 Gio utilisés au relevé final), sans attribuer cette évolution à
un seul processus. Aucune purge, aucun service/volume modifié. D3 26B reste
`not_run`, sans poids téléchargés, hors du budget natif BF16 retenu pour WSL.

## Conservation et reproduction

Code et protocole Mini figés propres à `09abf162441393e3bec5606355e4c09bd0891e46`.
Flash utilise le même code avec le seul manifeste d’assets ajouté à `4d0974f`.
Les gardes et les budgets sont fixés avant leurs premières prédictions.
Archives source privées : `09abf16-source.tar`, SHA-256
`bf98a845bec5743bb9ef7bd6101854aec1948268df95c16ef7f609502aee78bc`,
et `flash-source.tar`, SHA-256
`5f190dc01be3d3b8b67c1716d8ddee2a1770d4430abb18d681ffa027e6720cf4`.
Ce gel supplémentaire est distinct de `source_archive:not_captured` dans la
provenance automatique. Les captures identifient les commits propres exécutés.

Nouveaux dossiers privés du checkout principal :

- `results/context-base-d3-{mini,flash}-20261011-001/` ;
- `results/mastra-read-d3-{mini,flash}-20261011-001/` ;
- `results/d3-control-{mini,flash}-20261011-001/` ;
- `results/d3-mini-flash-preflight-20261011/` : profils absolus, sources,
  métadonnées HF, receipts, logs et vérifications.

Poids et corpus privé hors Git. Aucun sceau ou export historique réécrit.
Les 36 archives traitées par l’analyse sont vérifiées ; les deux sceaux de Sol
et leurs hashes publiés sont revérifiés séparément sans rescore. La composition
refuse toute modification des 16 agrégats D3 historiques, des 13 agrégats Vela
et des métriques communes à l’export Sol. Les préflights recensent tous les
sous-modules déclarés, séparément des composants enregistrés et services observés.

Reproduire la synthèse publique sans poids, captures privées ou service :

```bash
python3 -B scripts/compose-d3-comparison.py --bench-root . \
  --current-json docs/evidence/model-comparison-d3-larger-20261011/analysis.json \
  --vela-json docs/evidence/model-comparison-vela2-20261011/analysis.json \
  --sol-json docs/evidence/model-comparison-complete-20261010-sol/analysis.json \
  --d3-json docs/evidence/model-comparison-d3-20261011/analysis.json \
  --output-dir results/d3-larger-overview-replay-001
```

L’analyse détaillée se régénère depuis les archives locales scellées via
`scripts/analyze-model-comparison.py` ; arguments exacts conservés hors Git dans
`results/d3-mini-flash-preflight-20261011/analysis-args.json`.
Validation avant inférence : **560 tests, 7 ignorés**, registre valide avec
`jsonschema==4.26.0`. Validation finale à `79dc522` depuis un clone Git propre sous `/tmp`, sans
poids ni runtime modèle : **560 tests, 7 ignorés**, registre valide, rapport
et manifeste à 19 modèles reproduits byte-à-byte depuis les quatre JSON
publics. Log privé `results/d3-mini-flash-preflight-20261011/tests-clean-clone.log`.
Les tests ordinaires ne chargent aucun poids.
