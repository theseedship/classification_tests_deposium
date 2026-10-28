# Pilote Noma CPU sur les corpus communs

Protocole du 3 octobre 2026, fixé après le smoke et avant les campagnes complètes.
Le [local-only material, not distributed](PROTOCOL.md) conserve ses deux mesures. La base de
développement inclut le merge de la PR #4, `bbe8eb68c888ef5442f723ee56de494d982d55a5`.
Les campagnes sont terminées ; leurs [local-only material, not distributed](PROTOCOL.md) restent
séparés du protocole fixé avant exécution.

## Périmètre et budgets

Une passe séquentielle des **24 cas Mastra**, puis des **132 cas de base**,
avec le même moteur, les mêmes projections et références que les comparateurs
historiques. Aucun apprentissage, changement d'ordre, sélection après lecture
des résultats, API distante ou appel à un outil MCPs.

- Mastra : corpus SHA-256
  `d66ec51d9b8d89f46b87b90b80bcd0d45abf1570fa9857c24d9ce39117935497`,
  requêtes communes SHA-256
  `c076aedc2810c758d830c59bb21d404dcbad41df353f7df218950935381f7752`.
  Références `pending_human` : accord provisoire, zéro cas sémantiquement qualifié.
  Budget 300 s, initialisation incluse, vérifié entre appels comme pour Eos.
- Bases : corpus SHA-256
  `767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616`,
  76 cas documentaires, 28 mathématiques, 28 chimiques, FR/EN ; mêmes oracles
  restreints. Budget externe 900 s avec interruption du runner commun et
  conservation des lignes terminées.
- Un worker CPU, deux threads, BF16 pour le backbone et FP32 pour les têtes,
  comme dans le chargeur officiel. Garde RSS 8 192 Mio ; au moins 10 240 Mio
  disponibles avant chargement et 2 048 Mio pendant les échanges, sondage
  toutes les 50 ms. 120 s d'initialisation et 30 s par appel. Une garde
  atteinte arrête le worker ; aucun relèvement automatique du budget.

Plafond : **1 024 tokens natifs complets**, distinct des 4 096 annoncés pour
le préfixe seul. Aucun contexte long ou seuil de bascule LLM n'est qualifié.

## Modèle et adaptation

Poids `BlackdromeAILabs/noma` à `fac0429688a137ce451a27ad34d05e9fd47fb624`,
code `blackdromeai-labs/noma` à `8cfda260d8af88c18b1de1852e13dcbe9958042f`.
Le clone LF correspond aux octets des blobs Git publiés. Le clone CRLF du
smoke reste conservé avec ses empreintes. Les manifestes [modèle](../profiles/noma-assets.json)
et [sources](../profiles/noma-source-assets.json) sont vérifiés avant chargement,
avec inventaire exact, refus des liens et surveillance des mutations.

Le [profil](../profiles/noma-cpu-context.json) réutilise le runtime Eos verrouillé
sans installation. Les vrais `Noma.from_pretrained`, Serializer et `Noma.decide`
sont appelés ; leurs algorithmes ne sont pas recopiés. `context` devient l'état,
`question` l'instruction. Les descriptions d'options restent identiques et
ordonnées ; leurs IDs deviennent `c0`, `c1`, etc., puis sont remappés en sortie.
Aucune référence ou annotation de langue/difficulté/domaine n'est transmise.

Paramètres : `fork=False`, aucun bucket/graphe CUDA, `use_facts=True`,
`facts-0.2`, `reference_time="2026-10-03T00:00:00Z"`. Le canal déterministe
de faits fait partie du candidat ; ses règles principalement anglaises et
chaque fait dérivé restent explicites dans les sorties brutes.

Le précontrôle compare le préfixe officiel à celui du même Serializer à cap
élevé, refuse troncature/dépassement avant forward, puis contrôle les IDs de
l'unique appel `hidden`. Environnement enfant sans identifiants, Hub hors
ligne et connexions Python bloquées. Un préfixe de cache neuf avec `-B`
contourne les `.pyc` existants et assure l'utilisation des sources contrôlées.

Le choix comparé est **l'argmax des probabilités**, première option en cas
d'égalité. Le signal natif `abstain` et l'incertitude sont archivés séparément :
aucun seuil choisi sur le test, aucune assimilation au « retour au planner ».
Ce lot ne qualifie donc pas de politique d'abstention.

## Commandes et conservation

Depuis un clone avec poids/runtime aux chemins du profil :

```bash
python3 scripts/prepare-noma-assets.py \
  --source-dir .cache/noma-source-8cfda260-lf \
  --model-dir models/noma-fac0429 --output-dir results/noma-assets-check-NOUVEAU
python3 -m deposium_bench observe-mastra-read \
  --profile profiles/noma-cpu-context.json \
  --stack-root ../deposium_fullstack --output results/mastra-read-noma-NOUVEAU
timeout --signal=INT --kill-after=10s 900s python3 -m deposium_bench run \
  --dataset datasets/context-choice-v1/cases.jsonl \
  --profile profiles/noma-cpu-context.json \
  --stack-root ../deposium_fullstack --output results/context-base-noma-NOUVEAU
python3 scripts/analyze-noma-pilot.py \
  --mastra results/mastra-read-noma-NOUVEAU \
  --base results/context-base-noma-NOUVEAU \
  --output results/noma-analysis-NOUVEAU.json
```

Le préparateur ne télécharge rien et refuse de remplacer un manifeste. Comparer
ses sorties aux manifestes commités ; un écart doit être expliqué. Pour un
worktree réutilisant les assets du checkout principal, créer un profil privé
sous `results/` avec chemins absolus, sans modifier les anciens profils.

L'analyse versionnée relit les archives scellées sans inférence. Séparer
initialisation, première décision, durées par statut, tokens et RSS. Une passe
sans échauffement donne des temps descriptifs incluant la pression de l'hôte.
Le push ne sauvegarde ni poids, ni runtime, ni `results/`. `rescore` écrit une
archive distincte ; les anciennes qualifications restent intactes. L'inventaire
relève les 15 sous-modules sans qualifier leur exécution. Modèle isolé,
preuve documentaire et qualité des réponses CLI/chat restent distincts.
