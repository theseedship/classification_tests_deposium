# Choix Mastra : trois candidats locaux et la référence Jev

Comparaisons ultérieures sur les mêmes entrées : [local-only material, not distributed](PROTOCOL.md),
[local-only material, not distributed](PROTOCOL.md) et [Laya](LAYA_RESULTS.md). La
[local-only material, not distributed](PROTOCOL.md) et le
[rapport de routage détaillé](evidence/model-comparison-complete-20261004/report.md)
couvrent les sept modèles. Ce document conserve les quatre mesures du 2 octobre.

Le 2 octobre 2026, sur **les mêmes 24 demandes synthétiques**, Julia n'améliore
pas l'accord global d'Indecis ; GLiNER gagne un cas. Jev rejoint davantage de
propositions, mais le repli reste imparfait. L'objectif utilisateur demeure
un modèle local pour la production ; Jev sert ici de référence expérimentale.

Ces nombres sont des **accords avec des propositions à revoir**, pas une
précision validée humainement. Douze familles FR/EN, six cas de calibration
et dix-huit de test ; 24/24 choix valides pour chaque candidat. Aucun outil
MCP n'est exécuté à partir de ces décisions.

## Comparaison

| Candidat | Accord /24 | Recherche /8 | Statistiques /8 | Repli /8 | Médiane côté adaptateur | Pic RSS rapporté |
|---|---:|---:|---:|---:|---:|---:|
| Indecis ouvert, Bekko | 11 | 5 | 6 | 0 | 44,69 ms | 894,88 Mio |
| Julia-1 | 11 | 6 | 4 | 1 | 100,21 ms | 1 019,27 Mio |
| GLiNER2.5-multi-Decide | 12 | 8 | 4 | 0 | 391,88 ms | 2 886,23 Mio |
| Jev `1.13.0`, API | **20** | **8** | **8** | **4** | 288,02 ms | Non observable côté serveur |

Durées hors initialisation, première demande incluse. Pour Jev, elles incluent
réseau/TLS et gestion locale du budget. Pour les locaux, contrôles et transport
vers le worker résident sont inclus. C'est une passe descriptive, sans chauffe
ni répétition ; les mesures ne comparent pas des temps de calcul moteur égaux.
Les trois locaux utilisent deux threads CPU et une garde RSS de 3 072 Mio.
Les relevés hôte montrent un swap presque entièrement occupé.

| Candidat | FR /12 | EN /12 | Calibration /6 | Test /18 | Paires avec même action /12 |
|---|---:|---:|---:|---:|---:|
| Indecis | 5 | 6 | 4 | 7 | 10 |
| Julia | 5 | 6 | 4 | 7 | 5 |
| GLiNER | 8 | 4 | 3 | 9 | 5 |
| Jev | 9 | 11 | 4 | 16 | 9 |

Les paires peuvent être concordantes et toutes deux en désaccord avec la
proposition. Douze traductions ne font pas douze scénarios indépendants de
plus. Le contrôle constant d'action ou d'ID donne 8/24, puisque les positions
et actions sont équilibrées. Un écart d'un cas entre locaux ne suffit pas à
établir une supériorité généralisable.

## Ce que montrent les divergences

GLiNER retrouve les huit demandes de passages, mais aucun des huit replis.
Indecis ne choisit jamais le repli non plus. Julia le choisit quatre fois :
une seule correspond à une proposition de repli, trois détournent des demandes
de recherche/statistiques. La seule couverture du pool ne rend donc pas le
routeur utilisable.

Exemple français : « Ne compte pas les documents ni les entités. Retrouve
seulement les passages… ». La proposition est `search` ; Indecis choisit
`stats`, Julia `fallback`, GLiNER et Jev `search`. Les citations et négations
méritent des familles indépendantes dans le futur dataset de spécialisation.

Jev rejoint les 16 propositions de recherche/statistiques. Ses quatre
divergences se trouvent parmi les huit replis :

| Demande | Choix Jev | Proposition |
|---|---|---|
| « Regarde ce qui pose problème dans cet espace. » | Statistiques | Repli |
| Traduction anglaise de cette demande vague | Recherche | Repli |
| Compter, retrouver des passages, puis rédiger une recommandation — FR | Statistiques | Repli |
| Durée de cuisson du riz — FR | Recherche | Repli |

Cette liste ne rend pas automatiquement la référence correcte. La demande
composée illustre la convention à faire revoir : le pilote vise une décision
courte suffisante, alors qu'un planner peut commencer légitimement par compter
avant de poursuivre. Une demande hors domaine dépend aussi du périmètre connu
du corpus. La première étape utile consiste à expliciter ces conventions avec
des demandes réelles autorisées, avant entraînement ou changement de seuil.

## Temps, taille et ressources

| Candidat | Initialisation locale | Premier appel | Médiane des 23 suivants | p95 des 24 appels |
|---|---:|---:|---:|---:|
| Indecis | 1 215,81 ms | 68,01 ms | 44,62 ms | 57,00 ms |
| Julia | 14 637,86 ms | 164,43 ms | 99,54 ms | 146,58 ms |
| GLiNER | 13 069,23 ms | 424,47 ms | 385,94 ms | 582,64 ms |
| Jev API | Pas de chargement serveur observé | 355,34 ms | 286,61 ms | 355,34 ms |

Temps côté adaptateur ; p95 au rang supérieur `ceil(n × 0,95)`. Pour Jev,
HTTP seul : médiane 264,07 ms, p95 333,48 ms, **maximum 902,22 ms**. Avec
24 mesures, le p95 ne montre pas cet appel le plus lent. Aucun temps interne
ni mémoire serveur n'est disponible. Aucune accélération de parcours produit
n'est démontrée : il manque encore un planner réel comparable et ses outils.

Les demandes sont courtes. Comptages natifs, de définitions différentes :

- Indecis : plus grande séquence indépendante de 66 à 117 tokens ; somme
  contexte/options de 148 à 211, sans fenêtre jointe.
- Julia : séquence assemblée de 119 à 182 tokens.
- GLiNER : schéma et contenu de 159 à 245 subwords.
- Jev : 10 274 tokens d'entrée et 2 067 de sortie déclarés au total par l'API ;
  pas de tokenizer natif ni de preuve de non-troncature accessible au banc.

Les locaux n'indiquent aucune troncature. Ce lot ne teste ni les longueurs
100/500/1k/… systématiques, ni des contextes longs, ni la concurrence.

## Protocole et preuves

Les quatre archives partagent strictement les mêmes octets pour le corpus
et les requêtes : corpus `d66ec51d…35497`, requêtes `c076aedc…f7752`.
Les hashes complets, révisions des modèles, environnements, empreintes des
archives, timings et décisions par cas figurent dans la
[preuve versionnée](evidence/mastra-model-comparison-20261002.json).
Protocoles : [Indecis et projection commune](MASTRA_INDECIS_OBSERVATION_PROTOCOL.md),
[comparateurs locaux](MASTRA_LOCAL_COMPARISON_PROTOCOL.md),
[référence Jev autorisée](MASTRA_JEV_REFERENCE_PROTOCOL.md).

| Archive locale | Code gelé avant prédictions | État |
|---|---|---|
| `results/mastra-read-indecis-001` | `fc5de1f` | Initialisation refusée, zéro forward, conservée |
| `results/mastra-read-indecis-002` | `8495293` | 24 choix valides |
| `results/mastra-read-julia-001` | `8e8cb02` | 24 choix valides |
| `results/mastra-read-gliner-001` | `8e8cb02` | 24 choix valides |
| `results/mastra-read-jev-001` | `b69ea8a` | 24 réponses API valides |

Les quatre archives effectives sont scellées et ont été vérifiées sans
nouvelle inférence. Aucun prompt, corpus ou référence n'a changé entre elles.
Une correction de compteurs distingue désormais un flag `forward_executed`
absent d'un zéro explicite : les 24 sorties Julia contiennent logits et temps
d'inférence, mais aucun tel flag. Son ancien résumé affichait donc un zéro
trompeur. La preuve comparative le présente comme inconnu ; les archives
initiales ne sont pas réécrites. Les forwards serveur de Jev restent inconnus.

Budget Jev : 24 nouvelles réservations et 24 règlements, chacun relié à une
sortie. Le journal conserve intégralement son ancien préfixe. Total désormais
**759/800 tentatives**, **1 324 679/2 000 000 tokens imputés** ; les deux
anciennes réserves non réglées restent comptabilisées. Aucun reset de budget,
retry, entraînement, donnée privée ou déploiement dans ce lot.

Les contrôles du [local-only material, not distributed](PROTOCOL.md) restent séparés :
10/10 contrôles natifs (dont 3 exécutions de wrappers) et 3/3 captures de planner avec fournisseur simulé.
Son pool de six outils et son arrêt texte ne sont pas équivalents aux trois
labels de ce comparatif. L'agent MCPs peut poursuivre les corrections graphe
indépendamment.

La suite utile est la revue des douze familles, puis des données réelles
autorisées et un test indépendant pour la spécialisation locale. Ce corpus
désormais consulté reste un diagnostic gelé. Jev constitue un comparateur,
pas un annotateur de vérité ni une dépendance de production retenue.
