# Jev 1.14 face au reranker — 15 octobre 2026

**BGE reste le meilleur des profils mesurés pour classer ces passages.** Jev 1.14
surpasse D3-lite, mais ne remplace pas BGE avantageusement avec notre projection
par grades ; le complément Jev puis BGE dégrade légèrement le classement de BGE.
Ce résultat ne qualifie pas toutes les façons d'utiliser Jev comme reranker.

## Classement complet, campagne API partielle

Même corpus `7ed178d`, inchangé : les **512 cas du split test, huit familles,
huit directions, deux vues et quatre rotations**. Les références sont
synthétiques et sans revue humaine. Les 264 jugements de pertinence physiques
ont tous une réponse valide. Ils couvrent exactement les 2 048 choix logiques
nécessaires aux quatre rotations, sans nouvel appel API pour ces rotations.
Les anciennes observations à 132 bases restent distinctes ; Jev 1.13 historique
n'est pas réévalué ni fusionné avec Jev 1.14.

| Méthode | nDCG@1 | nDCG@3 | Rappel@3 | Médiane / pool | p95 |
|---|---:|---:|---:|---:|---:|
| BGE v2-m3 INT8 CPU | **0,922** | 0,934 | **0,923** | **0,236 s** | 0,908 s |
| Jev 1.14 API seul | 0,840 | 0,878 | 0,921 | 1,058 s* | 1,187 s* |
| Jev 1.14 + BGE pour les égalités | 0,911 | 0,931 | **0,923** | 1,303 s* | 1,957 s* |
| D3-lite CPU seul, essai précédent | 0,701 | 0,808 | 0,892 | 4,411 s* | 8,446 s* |

nDCG : 480/512 cas éligibles ; rappel : 416/512. Couverture complète des
classements, cas sans référence définie conservés séparément. Les temps * sont
les sommes projetées de quatre choix par pool, sans cache, depuis les appels
physiques réellement mesurés. La combinaison additionne ces temps à BGE ; elle
n'est pas un pipeline intégré chronométré. Jev inclut HTTP/TLS/réseau/attente et
serveur ; la RAM et le temps de calcul serveur ne sont pas observés. BGE reprend
les 512 appels natifs CPU déjà archivés, sans solliciter le service actif.

Jev partage son meilleur grade dans 356/512 pools. À trois passages, il conserve
un ensemble suffisant dans **287/352** cas répondables, contre **288/352** pour
BGE et le complément. Les 64/64 conflits conservent appui et réfutation ensemble
avec les trois méthodes. Les tableaux par langue/scénario/vue/rotation sont dans
le [rapport généré](evidence/passage-jev-20261015/report.md) et le
[JSON public](evidence/passage-jev-20261015/analysis.json).

## Pourquoi la campagne API s'est arrêtée

522 tentatives HTTP uniques sur les 728 prévues, toutes HTTP 200 et modèle
natif `jev-1.14.0`. Le transport et son budget ont arrêté les appels suivants
sur les rejets de contrat ; aucun retry automatique ni relèvement du budget.

- Archive 001 : 103 choix valides, puis une égalité stricte rejetant
  `0.45999999999999996` face à `0.46`. Le client est corrigé avec quatre ULP de
  tolérance, testé sans accepter un écart réel de `1e-10` ou `0.01`.
- Archive 002 : les 104 réponses sont revalidées hors réseau, avec leur filiation
  et leurs temps originaux conservés ; 418 nouveaux appels sont faits. Le dernier
  choisit « Il ne suffit pas pour trancher. » à **0,47**, alors que la distribution
  donne **0,48** à « Il étaye l'affirmation. ». Le rejet `jev_response_invalid`
  est conservé. Ce désaccord ne relève pas de la précision machine ; le client
  n'a pas été relâché davantage.

Les deux archives initiales restent scellées et inchangées. Les mêmes 104 appels
ne sont pas refacturés par une reprise réseau. L'archive 002 reste marquée
**incomplète**, même si la pertinence requise pour le classement est complète.
Le [protocole et son amendement](PASSAGE_JEV_PILOT_20261015.md) donnent les
entrées, gardes et modalités exactes. Les arrêts sont distincts de la qualité
sémantique des prédictions et ne sont pas transformés en campagnes réussies.

## Preuves : couverture partielle, réponse possible non mesurée

Sur les 768 choix logiques de soutien : **514 OK, 2 erreurs et 252 manquants**.
394 des 514 choix valides sont corrects ; le score commun incluant les
manquants est 394/768. Ce dernier ne doit pas être comparé directement à une
campagne complète comme celle de D3-lite.

Dans cette portion observée, **64/96** appuis prédits sont corrects et **48/136**
réfutations prédites sont correctes. Ces précisions ne suffisent pas à justifier
une validation automatique de preuves. Le préfixe observé n'est pas un échantillon
aléatoire ; langues et classes manquantes restent visibles dans le JSON.
La décision « peut-on répondre ? » a **0/128 cas observés** : elle est **non
mesurée**, sans conclusion sur la qualité de Jev pour cette tâche.

## Usage, sources et reproduction

Usage natif déclaré sur les 522 réponses reçues : **212 511 tokens d'entrée et
40 680 de sortie**, soit **0,008925462 USD estimés** au tarif publié de
[0,042 USD par million d'entrées](https://docs.typesafe.ai/models), sorties
gratuites. Ce calcul n'est pas une facture fournisseur. Les deux réponses
initialement rejetées conservent chacune 65 536 tokens de réserve dans le
journal : comptabilité conservatrice vérifiée à **342 809/2 000 000 tokens**,
**522/728 tentatives**, 520 règlements et deux réserves non réglées. Le budget
historique Jev 1.13 est conservé séparément.

Clé chargée en environnement depuis le fichier local ignoré par Git, sans
argument ni log secret. Seuls les textes publics synthétiques ont été envoyés.
Aucun document privé, modèle téléchargé, conteneur d'inférence créé ou service
applicatif reconfiguré dans cette campagne API.

Code collecteur gelé à `6e6e6dc` pour 001, puis `327f7f4` pour 002. Sources
archivées séparément dans `results/passage-jev-preflight-20261015`, avec profils
absolus, journaux, validation de budget et logs. Captures hors Git :
`results/passage-jev-api-20261015-{001,002}`. Le producteur versionné vérifie
sceaux, préfixes de requêtes, provenance héritée, modèle, usage, timings et
couverture de pertinence ; il recalcule les scores communs en conservant les
statuts manquants/erreurs. Les producteurs et captures D3 précédents sont intacts.

Reproduire les sorties publiques sans poids, secret ni API, dans un dossier neuf :

```bash
python3 -B scripts/analyze-passage-jev.py \
  --render-json docs/evidence/passage-jev-20261015/analysis.json \
  --output results/passage-jev-report-reproduced
```

Les JSON et Markdown ont été reproduits byte à byte ; la comptabilité dérivée
correspond au journal durable. Clone propre à `327f7f4` : **651 tests exécutés,
7 ignorés, zéro échec**, avec `jsonschema==4.26.0`, registre valide et corpus
régénéré/validé (1 536 cas, 24 familles). Après adaptation du seul producteur au
préfixe interrompu : **sept tests ciblés** passent, dont couverture de pertinence,
provenance et absence de score de réponse possible ; la suite entière n'est pas
répétée après ce dernier changement de rapport.

## Routage : une expérimentation distincte

L'[examen de Semantic Router](SEMANTIC_ROUTER_ASSESSMENT_20261015.md) propose un
pilote hors trafic contre la sélection intention × portée déjà présente dans
MCPs. Ce logiciel n'a pas été installé ni exécuté. Il serait pertinent pour
choisir les modèles selon la demande, après mesure des réponses et du coût
ajouté ; les résultats présents ne justifient pas un nouveau service.
