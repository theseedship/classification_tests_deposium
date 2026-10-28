# Contrôle d'ordre équilibré : passages multilingues

512 cas synthétiques du split test, huit familles et quatre rotations de poids égal.
La rotation 0 est conservée comme observation historique ; le tableau principal couvre les quatre ordres.
Références et traductions non revues humainement ; aucun parcours produit mesuré.

## Classement, quatre rotations

Valeurs pénalisant erreurs et absences sur cas éligibles ; parenthèses : définis / éligibles / total.

| Méthode | nDCG@1 | nDCG@3 | MRR@4 | Rappel@1 | Rappel@3 |
|---|---:|---:|---:|---:|---:|
| Ordre d'entrée | 0.442 (480/480/512) | 0.635 (480/480/512) | 0.579 (416/416/512) | 0.250 (416/416/512) | 0.750 (416/416/512) |
| Ordre inversé | 0.442 (480/480/512) | 0.635 (480/480/512) | 0.579 (416/416/512) | 0.250 (416/416/512) | 0.750 (416/416/512) |
| BGE CPU | 0.922 (480/480/512) | 0.934 (480/480/512) | 0.926 (416/416/512) | 0.779 (416/416/512) | 0.923 (416/416/512) |
| D3-lite classes | 0.701 (480/480/512) | 0.808 (480/480/512) | 0.766 (416/416/512) | 0.510 (416/416/512) | 0.892 (416/416/512) |
| D3-lite + BGE (égalités) | 0.922 (480/480/512) | 0.935 (480/480/512) | 0.926 (416/416/512) | 0.779 (416/416/512) | 0.923 (416/416/512) |

## nDCG@1 par rotation

| Rotation | Ordre d'entrée | Ordre inversé | BGE | D3-lite | Complément |
|---|---:|---:|---:|---:|---:|
| 0 | 1.000 (120/120/128) | 0.000 (120/120/128) | 0.922 (120/120/128) | 0.989 (120/120/128) | 0.922 (120/120/128) |
| 1 | 0.486 (120/120/128) | 1.000 (120/120/128) | 0.922 (120/120/128) | 0.544 (120/120/128) | 0.922 (120/120/128) |
| 2 | 0.283 (120/120/128) | 0.486 (120/120/128) | 0.922 (120/120/128) | 0.547 (120/120/128) | 0.922 (120/120/128) |
| 3 | 0.000 (120/120/128) | 0.283 (120/120/128) | 0.922 (120/120/128) | 0.725 (120/120/128) | 0.922 (120/120/128) |

## nDCG@1 par language_direction

| Groupe | Ordre d'entrée | Ordre inversé | BGE | D3-lite | Complément |
|---|---:|---:|---:|---:|---:|
| de->de | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.808 (60/60/64) | 0.911 (60/60/64) |
| en->en | 0.442 (60/60/64) | 0.442 (60/60/64) | 1.000 (60/60/64) | 0.841 (60/60/64) | 1.000 (60/60/64) |
| en->fr | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.605 (60/60/64) | 0.911 (60/60/64) |
| es->es | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.610 (60/60/64) | 0.911 (60/60/64) |
| fr->en | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.610 (60/60/64) | 0.911 (60/60/64) |
| fr->fr | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.739 (60/60/64) | 0.911 (60/60/64) |
| it->it | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.740 (60/60/64) | 0.911 (60/60/64) |
| pt->pt | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.656 (60/60/64) | 0.911 (60/60/64) |

## nDCG@1 par scenario_id

| Groupe | Ordre d'entrée | Ordre inversé | BGE | D3-lite | Complément |
|---|---:|---:|---:|---:|---:|
| component_relation_collision | 0.321 (64/64/64) | 0.321 (64/64/64) | 1.000 (64/64/64) | 0.647 (64/64/64) | 1.000 (64/64/64) |
| conflicting_evidence | 0.536 (64/64/64) | 0.536 (64/64/64) | 1.000 (64/64/64) | 0.915 (64/64/64) | 1.000 (64/64/64) |
| distributed_binding | 0.583 (64/64/64) | 0.583 (64/64/64) | 0.417 (64/64/64) | 0.479 (64/64/64) | 0.417 (64/64/64) |
| heading_value_truncation | 0.321 (32/32/64) | 0.321 (32/32/64) | 1.000 (32/32/64) | 0.746 (32/32/64) | 1.000 (32/32/64) |
| missing_evidence | 0.750 (64/64/64) | 0.750 (64/64/64) | 1.000 (64/64/64) | 0.938 (64/64/64) | 1.000 (64/64/64) |
| negation_exception | 0.321 (64/64/64) | 0.321 (64/64/64) | 1.000 (64/64/64) | 0.571 (64/64/64) | 1.000 (64/64/64) |
| unit_condition_collision | 0.321 (64/64/64) | 0.321 (64/64/64) | 1.000 (64/64/64) | 0.920 (64/64/64) | 1.000 (64/64/64) |
| variant_scope | 0.321 (64/64/64) | 0.321 (64/64/64) | 1.000 (64/64/64) | 0.415 (64/64/64) | 1.000 (64/64/64) |

## nDCG@1 par view

| Groupe | Ordre d'entrée | Ordre inversé | BGE | D3-lite | Complément |
|---|---:|---:|---:|---:|---:|
| full | 0.435 (256/256/256) | 0.435 (256/256/256) | 0.927 (256/256/256) | 0.704 (256/256/256) | 0.927 (256/256/256) |
| head_384 | 0.451 (224/224/256) | 0.451 (224/224/256) | 0.917 (224/224/256) | 0.698 (224/224/256) | 0.917 (224/224/256) |

## Preuves et égalités

| Méthode | Ensemble suffisant @3 | Appui et réfutation du même claim @3 |
|---|---:|---:|
| Ordre d'entrée | 248/352 | 32/64 |
| Ordre inversé | 248/352 | 32/64 |
| BGE CPU | 288/352 | 64/64 |
| D3-lite classes | 281/352 | 60/64 |
| D3-lite + BGE (égalités) | 288/352 | 64/64 |

Égalité du meilleur grade D3 : 436/512 pools ; une égalité quelconque : 512/512.
Comptages par rotation, direction, scénario et vue : analysis.json.

## Coûts CPU

BGE : un appel natif mesuré par pool. D3 : somme projetée de quatre temps de choix physiques préexistants par pool ; aucun nouvel appel D3 pour les rotations.
La projection D3 n'est pas une mesure d'un rejeu sans cache. Soutien et possibilité de répondre ne font pas partie du coût de classement.

| Opération | Médiane s | p95 s | Pools |
|---|---:|---:|---:|
| bge_one_pool_actual | 0.236 | 0.908 | 512 |
| d3_four_relevance_choices_replayed_projection | 4.411 | 8.446 | 512 |
| complement_sequential_projection | 4.654 | 9.354 | 512 |

## Portée

Les scores de soutien et de possibilité de répondre concernent seulement les 128 cas de rotation 0 ; leurs archives et scores figurent dans analysis.json.
Les choix D3 de pertinence sont rejoués par entrée visible identique, sans nouvelle inférence. Aucun choix de réponse n'est imputé aux pools tournés.
Le binaire CPU BGE est identifié par hash ; sa révision source exacte reste non établie.
Huit familles et gabarits partagés limitent l'inférence ; aucun intervalle ne traite les rotations comme indépendantes.
Aucun verdict de remplacement produit, de recherche initiale ou de chat réel.
Corpus : `35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476` ; export ranking 512 : `06e3321ef8397ea231d189245256c4145aefb14f2aaf55d6190eff71b037c1b9`.
Producteur : `16356e6350ba73cb1a6ef181e60b8a4bc7cb3572a68091df1ac2ea14ca8610b4`.
