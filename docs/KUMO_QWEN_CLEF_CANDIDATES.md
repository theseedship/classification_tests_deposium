# Kumo, Qwen/SemIf et Clef-Flash : deux types d'expérience

État au 2 octobre 2026, après lecture du code public et des sources Deposium.
**Aucun de ces candidats n'a été exécuté dans le banc.** Aucun poids téléchargé,
service lancé, dataset privé exporté ni dépôt applicatif modifié.
Cette note complète la [liste des candidats](NEXT_CANDIDATES.md); elle ne crée
ni adaptateur ni capacité qualifiée et ne relance pas la Phase 5 GeoAI différée.
**Priorité précisée :** [identifier les usages réels DuckDB/XLSX](TABULAR_USE_CASE_DISCOVERY.md)
avant de construire un dataset prédictif. Les exemples ci-dessous sont des
hypothèses techniques, sans demande utilisateur ni utilité produit démontrées.

## Identités observées

| Source | Révision |
|---|---|
| [MagicLex/jevworks](https://github.com/MagicLex/jevworks) | `75e5b179c5cbe044684f71548e6db69115f1dae4` |
| [Qwen/Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B) | `1cfa9a7208912126459214e8b04321603b3df60c` |
| [Cloudflare/clef-flash](https://huggingface.co/Cloudflare/clef-flash) | `17f0b0ad64efb65d273590632833508766b2aae6` |
| [NVIDIA/structured-data-models](https://github.com/NVIDIA/structured-data-models) | `ce95710703a8be5744c756cd2f662ed79d3ee444` |
| [nvidia/Kumo-Tabular](https://huggingface.co/nvidia/Kumo-Tabular) | Page `main` : `3cfed70f0ea063751fc50eefc37e32ac8db1db8c`; tag de poids `v1.0.0` : `bd7fa122b516c7355583873ffcf38f5e79403ebd` |

Le chargeur SDM observé utilise **`v1.0.0`**, pas le HEAD de la fiche Kumo.
Le futur manifeste devra enregistrer les fichiers/hashes effectivement chargés.
La recette de déploiement [jevworks/kumo/requirements.txt](https://github.com/MagicLex/jevworks/blob/75e5b179c5cbe044684f71548e6db69115f1dae4/kumo/requirements.txt)
épingle SDM à `5d663369ff8ead4a78c910dbb8483d558e46627b`; `ce957107…`
est la révision plus récente inspectée séparément pour cette veille. Les détails
du constructeur et de la recette SDM ci-dessous concernent cette dernière.
Les licences annoncées sont MIT pour jevworks, Apache-2.0 pour Qwen/Clef et le
code SDM, OpenMDW 1.1 pour les poids Kumo; conserver ces identités séparément.

## Décisions textuelles : Qwen et Clef

**Qwen via SemIf** réutilise un LLM de 4 milliards de paramètres : un forward,
logits du dernier token restreints aux lettres A–P, puis softmax entre ces
options. Le thinking est désactivé; aucune génération ni chaîne de raisonnement
n'est produite. Le wrapper accepte 2–16 choix et rejette le prompt complet
au-delà de 4 096 tokens. Ce budget appartient au wrapper, pas à une qualification
de la fenêtre native Qwen. La confiance est conditionnelle aux choix proposés.
Source : [readout SemIf épinglé](https://github.com/MagicLex/jevworks/blob/75e5b179c5cbe044684f71548e6db69115f1dae4/jevworks/semif/direct.py#L13).

**Clef-Flash** est un modèle multimodal de 9 milliards de paramètres dérivé de
Qwen3.5-9B. Sa tête jointe score les options de plusieurs questions en un passage;
son interface `choice` / `noul` / `score` est compatible Jev/SystemOne.
Utiliser `joint_schema_model.py` et la tête fournie, pas un appel générique
`generate`. La fiche rapporte une exécution interne de Decision Index 0.2.1 :
CLadder 97,7 contre 72,6 pour Jev, mais GSM8K 67,3 contre 79,9 et RAGTruth
35,6 contre 76,5. Cela ne démontre aucune domination générale ni résultat
Deposium. Les 38,8 ms médians publiés ne sont pas une mesure sur notre machine.
Source : [fiche et résultats Clef](https://huggingface.co/Cloudflare/clef-flash/blob/17f0b0ad64efb65d273590632833508766b2aae6/README.md).

Le [helper Clef](https://huggingface.co/Cloudflare/clef-flash/blob/17f0b0ad64efb65d273590632833508766b2aae6/joint_schema_model.py#L106)
fixe `max_length=16384` par défaut, réserve le schéma puis **tronque le contexte
par la fin sans erreur**. Il encode les identifiants de questions/options et
trie les choix par identifiant. Un adaptateur du banc devra précompter l'entrée
complète, refuser les dépassements avant forward, fournir les instructions et
remapper les IDs internes vers des IDs neutres, avec ordre/permutations archivés.
Ne jamais envoyer les annotations, familles ou noms de références.

Ces deux candidats peuvent viser `bench.context-choice` à entrées comparables.
Conserver les budgets natifs, domaines, langues et options; la capacité
multimodale Clef demanderait une expérience distincte. Mesurer séparément
chargement, tokenisation, forward, temps client total et mémoire maximale.
La référence BF16 de Clef représente environ 18 Go de poids pour 9B paramètres,
avant activations : elle dépasse la VRAM totale de la RTX 5060 locale de 8 Go.
Quantification/offload éventuels seraient d'autres configurations à qualifier.

## Kumo : prédire une colonne à partir d'exemples

Kumo reçoit `x_context` (variables connues), `y_context` (cibles observées) et
`x_query` (lignes à prédire, sans cible). Classification et régression utilisent
des checkpoints distincts. L'adaptation en contexte évite un entraînement des
poids pour chaque table, mais **nécessite des exemples étiquetés**. Le modèle
n'interprète pas directement une demande en français ou un fichier Excel.
Source : [interface officielle](https://huggingface.co/nvidia/Kumo-Tabular/blob/3cfed70f0ea063751fc50eefc37e32ac8db1db8c/README.md).

Les tailles annoncées vont de 28 à 215 millions de paramètres
([présentation NVIDIA](https://huggingface.co/blog/nvidia/kumo-tabular)).
Pour un premier pilote borné, sélectionner explicitement `size="small"` et
une seule tâche; le [constructeur](https://github.com/NVIDIA/structured-data-models/blob/ce95710703a8be5744c756cd2f662ed79d3ee444/sdm/models/kumo/tabular/model.py)
choisit sinon `large` et toutes les tâches. RAM, temps et caches dépendent aussi
des lignes, colonnes et ensembles : aucun besoin mémoire réel mesuré ici.

La [recette SDM](https://github.com/NVIDIA/structured-data-models/blob/ce95710703a8be5744c756cd2f662ed79d3ee444/sdm/models/kumo/tabular/recipe.py)
traite les catégories avant conversion numérique, transforme les variables et
sélectionne **500 colonnes au maximum après mélange**. Documenter la sélection,
ou refuser une table trop large; aucune perte silencieuse dans le banc.
Dates, texte libre et jointures demandent un contrat de préparation explicite.
Les quantiles de régression ne constituent pas une preuve de calibration.

### Ce que montre réellement jevworks

Le [predictor du jeu](https://github.com/MagicLex/jevworks/blob/75e5b179c5cbe044684f71548e6db69115f1dae4/kumo/predictor.py#L50)
donne à Kumo cinq variables et un label produit par une règle connue. Par défaut,
78 situations sont déclinées à trois distances, soit **234 lignes de contexte**;
33 autres situations servent de validation. Des masques déterministes corrigent
les actions impossibles. Qwen, lui, reçoit une description textuelle et des règles.
Les parties et latences annoncées ne constituent donc pas un benchmark contrôlé
de nos cas d'usage. Le README laisse encore les résultats Clef du jeu à `[tbd]`.
Reprendre le principe d'adaptateur, pas les scores comme qualification Deposium.

## Raccordement aux sources Deposium

Sous-modules retrouvés dans `.gitmodules`, lus sans mutation. HEAD locaux :
GeoAI `7426dd00888a`, MCPs `391be12078b1`, worker `d41dd3a3d659`.
GeoAI et worker contiennent du travail local préservé. Ces références décrivent
les sources inspectées, pas les images/services réellement exécutés.
Chemins ci-dessous relatifs à la stack configurable décrite dans
[local-only material, not distributed](PROTOCOL.md).

| Besoin | Contrat existant | Expérience proposée |
|---|---|---|
| GeoAI | `deposium_geoai/src/tools/climate.py:1770` : `climate_enrich_ndvi` produit une table zone/date climat + NDVI | Prédire une observation NDVI future à horizon fixé, avec historique disponible à l'origine |
| XLSX | `deposium_rust_worker/src/tabular.rs:293` : conversion not_stirling vers Parquet par feuille et manifest | Construire une table de contexte et masquer une cible observée sur les lignes de test |
| Lecture des tables | `deposium_MCPs/src/tools/tabular.ts:30` : `describe`, `preview`, `query`, `index_card`; filtres structurés | Réutiliser types/provenance et extractions autorisées, sans détourner un échantillon RAG en dataset complet |

GeoAI dispose maintenant de so4gp enregistré dans `src/server.py`, avec
dépendance optionnelle `patterns`. Il recherche des associations; Kumo serait
un autre travail, la prédiction d'une cible. Le document GeoAI
`docs/research/phase-5-predictive-thin-layer.md` confirme que cette capacité
générique est **différée et non implémentée**. Le banc ne change pas ce statut.

Le join climat/NDVI utilise ±N jours : éviter qu'une observation postérieure à
l'origine de prédiction devienne une variable d'entrée. La CV actuelle des
patterns mesure leur récurrence entre zones; elle ne remplace pas un test
prédictif bloqué par temps et région. Un déclin NDVI ne prouve pas un stress
biologique sans référence terrain indépendante.

Côté XLSX, distinguer valeurs manquantes, dates, unités, nombres stockés en
texte et formules/caches : le manifest lu ne garantit pas un recalcul Excel.
Les filtres, sommes et formules calculables conservent un oracle exact.
Les contrôles tenant restent dans le dispatch MCP (`tools-call-handler.ts:970`);
un export de dataset devra aussi établir les droits sur les fichiers concernés.
Un modèle ne choisit ni les autorisations ni les chemins de stockage.

## Pilote tabulaire proposé, à cadrer avant exécution

1. Choisir une cible et un horizon, un consommateur, des données autorisées et
   un critère d'utilité. GeoAI : NDVI futur; XLSX : catégorie ou valeur réellement
   inconnue au moment d'agir. Séparer la prédiction de la simple copie d'une règle.
2. Figer les splits par entité/document, puis temps/région si pertinent. Retirer
   doublons, variables dérivées de la cible et informations connues trop tard.
   Ajuster toute préparation uniquement sur le contexte d'apprentissage.
3. Comparer Kumo Small et des références simples sur les mêmes lignes :
   majorité/médiane, modèle linéaire/arbres; pour NDVI, persistance et saisonnalité.
   Classification : macro-F1, métriques probabilistes et calibration; régression :
   MAE/RMSE. Publier couverture, abstentions et effectifs par groupe.
4. Remplacer l'axe « tokens » par lignes de contexte × colonnes × lignes requête,
   avec catégories/classes, valeurs manquantes et nombre d'ensembles. Une grille
   exploratoire 100/500/1k lignes et 10/30/100 colonnes n'est pas une limite native.
   Mesurer préparation/cache à froid puis requêtes à chaud, RAM/VRAM et p95.
5. Ajouter ultérieurement un contrat tabulaire au moteur commun, avec archives,
   modèles et données hachés, sorties brutes, tests négatifs et scorer propre.
   Les 132 QCM historiques ne suffisent pas à évaluer cette capacité.

Priorité pour cette piste : terminer T0, la [découverte des usages](TABULAR_USE_CASE_DISCOVERY.md).
Préparer un dataset Kumo Small seulement si une cible utile est confirmée.
Qwen/SemIf et Clef restent des comparateurs textuels
distincts, soumis aux références R1/R2 et au budget ressources de la [local-only material, not distributed](PROTOCOL.md).
