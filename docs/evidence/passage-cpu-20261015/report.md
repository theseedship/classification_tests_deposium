# Passages multilingues : pilote CPU du 15 octobre 2026

128 cas synthétiques du split test, huit familles, huit directions de langue, deux vues, rotation 0.
Références et traductions non revues humainement. Aucun outil ni réponse finale évalué.

## Classement : référence, remplacement et complément

Valeur pénalisant absents/erreurs sur les cas éligibles ; entre parenthèses : définis / éligibles / total.

| Méthode | nDCG@1 | nDCG@3 | MRR@4 | Rappel@1 | Rappel@3 |
|---|---:|---:|---:|---:|---:|
| BGE v2-m3 INT8 CPU | 0.922 (120/120/128) | 0.934 (120/120/128) | 0.926 (104/104/128) | 0.779 (104/104/128) | 0.923 (104/104/128) |
| D3-lite classes seules | 0.989 (120/120/128) | 0.962 (120/120/128) | 0.987 (104/104/128) | 0.837 (104/104/128) | 0.942 (104/104/128) |
| D3-lite + BGE pour les égalités | 0.922 (120/120/128) | 0.935 (120/120/128) | 0.926 (104/104/128) | 0.779 (104/104/128) | 0.923 (104/104/128) |

## nDCG@1 par language_direction

| Groupe | BGE | D3-lite | Complément |
|---|---:|---:|---:|
| de->de | 0.911 (15/15/16) | 1.000 (15/15/16) | 0.911 (15/15/16) |
| en->en | 1.000 (15/15/16) | 1.000 (15/15/16) | 1.000 (15/15/16) |
| en->fr | 0.911 (15/15/16) | 0.911 (15/15/16) | 0.911 (15/15/16) |
| es->es | 0.911 (15/15/16) | 1.000 (15/15/16) | 0.911 (15/15/16) |
| fr->en | 0.911 (15/15/16) | 1.000 (15/15/16) | 0.911 (15/15/16) |
| fr->fr | 0.911 (15/15/16) | 1.000 (15/15/16) | 0.911 (15/15/16) |
| it->it | 0.911 (15/15/16) | 1.000 (15/15/16) | 0.911 (15/15/16) |
| pt->pt | 0.911 (15/15/16) | 1.000 (15/15/16) | 0.911 (15/15/16) |

## nDCG@1 par view

| Groupe | BGE | D3-lite | Complément |
|---|---:|---:|---:|
| full | 0.927 (64/64/64) | 0.990 (64/64/64) | 0.927 (64/64/64) |
| head_384 | 0.917 (56/56/64) | 0.988 (56/56/64) | 0.917 (56/56/64) |

## nDCG@1 par scenario_id

| Groupe | BGE | D3-lite | Complément |
|---|---:|---:|---:|
| component_relation_collision | 1.000 (16/16/16) | 1.000 (16/16/16) | 1.000 (16/16/16) |
| conflicting_evidence | 1.000 (16/16/16) | 1.000 (16/16/16) | 1.000 (16/16/16) |
| distributed_binding | 0.417 (16/16/16) | 0.917 (16/16/16) | 0.417 (16/16/16) |
| heading_value_truncation | 1.000 (8/8/16) | 1.000 (8/8/16) | 1.000 (8/8/16) |
| missing_evidence | 1.000 (16/16/16) | 1.000 (16/16/16) | 1.000 (16/16/16) |
| negation_exception | 1.000 (16/16/16) | 1.000 (16/16/16) | 1.000 (16/16/16) |
| unit_condition_collision | 1.000 (16/16/16) | 1.000 (16/16/16) | 1.000 (16/16/16) |
| variant_scope | 1.000 (16/16/16) | 1.000 (16/16/16) | 1.000 (16/16/16) |

## Décisions séparées

| Axe | Réussites / total | Couverture | Macro sur classes observées |
|---|---:|---:|---:|
| relevance | 229/512 | 512/512 | 0.496 |
| support | 443/768 | 768/768 | 0.809 |
| answerability | 88/128 | 128/128 | 0.808 |

### relevance : par classe

| Classe de référence | Réussites / total |
|---|---:|
| 3 | 102/104 |
| 2 | 8/32 |
| 1 | 14/224 |
| 0 | 105/152 |

### relevance : par direction

| Direction | Réussites / total |
|---|---:|
| de->de | 30/64 |
| en->en | 30/64 |
| en->fr | 28/64 |
| es->es | 27/64 |
| fr->en | 25/64 |
| fr->fr | 33/64 |
| it->it | 28/64 |
| pt->pt | 28/64 |

### support : par classe

| Classe de référence | Réussites / total |
|---|---:|
| supports | 102/104 |
| refutes | 80/80 |
| insufficient | 261/584 |

### support : par direction

| Direction | Réussites / total |
|---|---:|
| de->de | 44/96 |
| en->en | 72/96 |
| en->fr | 41/96 |
| es->es | 59/96 |
| fr->en | 47/96 |
| fr->fr | 70/96 |
| it->it | 51/96 |
| pt->pt | 59/96 |

### answerability : par classe

| Classe de référence | Réussites / total |
|---|---:|
| answerable | 52/88 |
| insufficient_visible_evidence | 20/24 |
| conflicting_visible_evidence | 16/16 |

### answerability : par direction

| Direction | Réussites / total |
|---|---:|
| de->de | 14/16 |
| en->en | 12/16 |
| en->fr | 11/16 |
| es->es | 12/16 |
| fr->en | 9/16 |
| fr->fr | 10/16 |
| it->it | 9/16 |
| pt->pt | 11/16 |

## Conservation des preuves

| Méthode | Ensemble suffisant @1 | Ensemble suffisant @3 | Appui + réfutation @3 |
|---|---:|---:|---:|
| BGE v2-m3 INT8 CPU | 72/88 | 72/88 | 16/16 |
| D3-lite classes seules | 72/88 | 76/88 | 16/16 |
| D3-lite + BGE pour les égalités | 72/88 | 72/88 | 16/16 |

## Coût CPU par pool de quatre passages

Reconstruction sans cache : somme des appels logiques mesurés. La composition additionne deux campagnes séquentielles, pas un pipeline intégré.
Support et possibilité de répondre sont des fonctions supplémentaires, séparées du classement.

| Opération | Médiane s | p95 s | Pools |
|---|---:|---:|---:|
| relevance | 4.411 | 8.446 | 128 |
| support | 8.330 | 9.605 | 128 |
| answerability | 1.476 | 5.203 | 128 |
| baseline_pool | 0.231 | 0.913 | 128 |
| complement_pool | 4.637 | 9.359 | 128 |
| complement_with_gate_pool | 6.140 | 14.751 | 128 |

D3 : 728 appels physiques pour 1408 choix logiques ; maximum RSS échantillonné 2267.473 Mio.
Les pics mémoire du processus BGE et de son conteneur sont consignés séparément dans le JSON ; ils ne représentent pas la même portée que le RSS du worker D3.
Les temps BGE incluent docker exec, curl et la boucle HTTP locale ; ils ne sont pas le seul temps du forward.

## Provenance et limites

Corpus : `35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476`.
Producteur : `scripts/analyze-passage-pilot.py`, SHA-256 `c10d018b963df12142f19ea519d900ad1e66d00aee89b2d3a1c105511d55b2f9`.
Les sceaux des deux campagnes et les identités des modèles figurent dans analysis.json.
Huit familles seulement, gabarits partagés, vues parfois identiques ; aucun intervalle traitant les variantes comme indépendantes.
Aucune qualification de remplacement produit, filtre automatique, recherche initiale, autre ordre ou chat réel.
