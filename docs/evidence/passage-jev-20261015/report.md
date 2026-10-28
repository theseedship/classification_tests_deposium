# JeV 1.14.0 : passages multilingues

512 cas synthétiques du split test, huit familles, quatre rotations de poids égal.
Références et traductions non revues humainement ; aucun parcours produit mesuré.

## Classement, quatre rotations

Valeurs pénalisant erreurs et absences ; parenthèses : définis / éligibles / total.

| Méthode | nDCG@1 | nDCG@3 | MRR@4 | Rappel@1 | Rappel@3 |
|---|---:|---:|---:|---:|---:|
| Ordre d'entrée | 0.442 (480/480/512) | 0.635 (480/480/512) | 0.579 (416/416/512) | 0.250 (416/416/512) | 0.750 (416/416/512) |
| Ordre inversé | 0.442 (480/480/512) | 0.635 (480/480/512) | 0.579 (416/416/512) | 0.250 (416/416/512) | 0.750 (416/416/512) |
| BGE CPU | 0.922 (480/480/512) | 0.934 (480/480/512) | 0.926 (416/416/512) | 0.779 (416/416/512) | 0.923 (416/416/512) |
| JeV 1.14.0 seul | 0.840 (480/480/512) | 0.878 (480/480/512) | 0.879 (416/416/512) | 0.663 (416/416/512) | 0.921 (416/416/512) |
| JeV 1.14.0 + BGE (égalités) | 0.911 (480/480/512) | 0.931 (480/480/512) | 0.917 (416/416/512) | 0.769 (416/416/512) | 0.923 (416/416/512) |

## nDCG@1 par rotation

| Rotation | Ordre d'entrée | Ordre inversé | BGE | JeV | Complément |
|---|---:|---:|---:|---:|---:|
| 0 | 1.000 (120/120/128) | 0.000 (120/120/128) | 0.922 (120/120/128) | 0.989 (120/120/128) | 0.911 (120/120/128) |
| 1 | 0.486 (120/120/128) | 1.000 (120/120/128) | 0.922 (120/120/128) | 0.661 (120/120/128) | 0.911 (120/120/128) |
| 2 | 0.283 (120/120/128) | 0.486 (120/120/128) | 0.922 (120/120/128) | 0.761 (120/120/128) | 0.911 (120/120/128) |
| 3 | 0.000 (120/120/128) | 0.283 (120/120/128) | 0.922 (120/120/128) | 0.947 (120/120/128) | 0.911 (120/120/128) |

## nDCG@1 par language_direction

| Groupe | Ordre d'entrée | Ordre inversé | BGE | JeV | Complément |
|---|---:|---:|---:|---:|---:|
| de->de | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.870 (60/60/64) | 0.911 (60/60/64) |
| en->en | 0.442 (60/60/64) | 0.442 (60/60/64) | 1.000 (60/60/64) | 0.825 (60/60/64) | 0.911 (60/60/64) |
| en->fr | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.837 (60/60/64) | 0.911 (60/60/64) |
| es->es | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.870 (60/60/64) | 0.911 (60/60/64) |
| fr->en | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.706 (60/60/64) | 0.911 (60/60/64) |
| fr->fr | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.870 (60/60/64) | 0.911 (60/60/64) |
| it->it | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.870 (60/60/64) | 0.911 (60/60/64) |
| pt->pt | 0.442 (60/60/64) | 0.442 (60/60/64) | 0.911 (60/60/64) | 0.870 (60/60/64) | 0.911 (60/60/64) |

## nDCG@1 par scenario_id

| Groupe | Ordre d'entrée | Ordre inversé | BGE | JeV | Complément |
|---|---:|---:|---:|---:|---:|
| component_relation_collision | 0.321 (64/64/64) | 0.321 (64/64/64) | 1.000 (64/64/64) | 0.946 (64/64/64) | 1.000 (64/64/64) |
| conflicting_evidence | 0.536 (64/64/64) | 0.536 (64/64/64) | 1.000 (64/64/64) | 0.973 (64/64/64) | 1.000 (64/64/64) |
| distributed_binding | 0.583 (64/64/64) | 0.583 (64/64/64) | 0.417 (64/64/64) | 0.562 (64/64/64) | 0.333 (64/64/64) |
| heading_value_truncation | 0.321 (32/32/64) | 0.321 (32/32/64) | 1.000 (32/32/64) | 0.915 (32/32/64) | 1.000 (32/32/64) |
| missing_evidence | 0.750 (64/64/64) | 0.750 (64/64/64) | 1.000 (64/64/64) | 1.000 (64/64/64) | 1.000 (64/64/64) |
| negation_exception | 0.321 (64/64/64) | 0.321 (64/64/64) | 1.000 (64/64/64) | 0.571 (64/64/64) | 1.000 (64/64/64) |
| unit_condition_collision | 0.321 (64/64/64) | 0.321 (64/64/64) | 1.000 (64/64/64) | 1.000 (64/64/64) | 1.000 (64/64/64) |
| variant_scope | 0.321 (64/64/64) | 0.321 (64/64/64) | 1.000 (64/64/64) | 0.786 (64/64/64) | 1.000 (64/64/64) |

## nDCG@1 par view

| Groupe | Ordre d'entrée | Ordre inversé | BGE | JeV | Complément |
|---|---:|---:|---:|---:|---:|
| full | 0.435 (256/256/256) | 0.435 (256/256/256) | 0.927 (256/256/256) | 0.844 (256/256/256) | 0.917 (256/256/256) |
| head_384 | 0.451 (224/224/256) | 0.451 (224/224/256) | 0.917 (224/224/256) | 0.834 (224/224/256) | 0.905 (224/224/256) |

## Conservation des preuves

| Méthode | Ensemble suffisant @3 | Appui et réfutation du même claim @3 |
|---|---:|---:|
| Ordre d'entrée | 248/352 | 32/64 |
| Ordre inversé | 248/352 | 32/64 |
| BGE CPU | 288/352 | 64/64 |
| JeV 1.14.0 seul | 287/352 | 64/64 |
| JeV 1.14.0 + BGE (égalités) | 288/352 | 64/64 |

Égalité du meilleur grade JeV : 356/512 pools.
Les diagnostics d'appui et de possibilité de répondre portent seulement sur les 128 cas initiaux.

| Axe JeV initial | Couverture OK | Exactitude sur tous les choix | Erreurs / manquants |
|---|---:|---:|---:|
| support | 514/768 | 0.513 (768 choix, manquants pénalisés) | 2 / 252 |
| answerability | 0/128 | — non mesuré | 0 / 128 |

## Temps et usage HTTP

BGE : durée mesurée d'un appel natif CPU par pool. JeV : durées client mesurées autour des appels HTTP physiques initiaux ; les quatre choix de pertinence par pool tourné sont une projection par réutilisation d'entrées identiques.
Aucun nouvel appel JeV pour les rotations. La somme BGE + JeV est une projection séquentielle, pas un pipeline intégré.
Le temps HTTP inclut réseau et serveur ; la mémoire et le temps d'inférence du modèle distant ne sont pas observés.

| Opération | Médiane s | p95 s | Pools |
|---|---:|---:|---:|
| bge_one_pool_actual | 0.236 | 0.908 | 512 |
| jev_four_relevance_choices_replayed_client_projection | 1.058 | 1.187 | 512 |
| complement_sequential_projection | 1.303 | 1.957 | 512 |

Campagne incomplete : 522/728 tentatives HTTP 200 distinctes, modèle natif `jev-1.14.0` ; 1 erreur de contrat conservée. Le classement dispose de tous les jugements nécessaires.
Origine : 104 appels hérités d'une archive scellée, 418 nouveaux appels HTTP ; 1 réponse initialement rejetée puis revalidée hors réseau.
Durée HTTP par tentative : médiane 0.252 s, p95 0.306 s.
Usage retourné : 212511 tokens d'entrée et 40680 tokens de sortie.
Estimation au tarif déclaré de 0,042 USD par million de tokens d'entrée, sorties gratuites : 0.008925 USD ; ce n'est pas une facture fournisseur.

## Portée

Le classement est complet sur 512 cas ; le soutien reste partiel sur les 128 cas initiaux et la réponse possible non mesurée. L’exactitude sur tous les choix inclut les manquants : zéro réponse observée ne signifie pas 0 % de qualité.
Le binaire CPU BGE est identifié par hash ; sa révision source exacte reste non établie.
Huit familles et des gabarits partagés limitent l'inférence ; les rotations ne sont pas indépendantes.
Les réponses rejetées conservent chacune leur réservation de 65 536 tokens dans le journal local ; ces réserves sont distinctes de l’estimation fondée sur les usages retournés.
Aucun verdict de remplacement produit, recherche initiale ou chat réel.
Corpus : `35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476` ; export ranking 512 : `06e3321ef8397ea231d189245256c4145aefb14f2aaf55d6190eff71b037c1b9`.
Producteur : `d50e16836f3fe04ac7b02d755a0e91758f10accd85c99ba087bd19d78a0d9510`.
