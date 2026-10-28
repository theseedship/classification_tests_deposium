# Revue indépendante du corpus decisions-v1

Date : 1er octobre 2026. Revue par un agent, à partir des entrées et références,
sans consulter de prédictions de candidat. **La revue humaine et linguistique
reste `not_performed`.** Cette note ne modifie ni les cas ni leurs références.

Le corpus permet un premier pilote de classification de tâche documentaire.
Ses 36 lignes ne constituent pas 36 situations indépendantes : elles représentent
18 familles FR/EN, dont trois FOLLOWUP ont des entrées exactement identiques.
Un classifieur de texte ne peut pas être évalué équitablement sur tous les champs
des cinq packs avec une seule taxonomie.

## Sources et intégrité

Documents lus : `README.md`, `HANDOFF.md`, `docs/LOT1_VALIDATION.md`, protocole,
synthèse de l'audit et `docs/STACK_INTEGRATION.md`; puis manifeste, README et
36 cas de `datasets/decisions-v1`. La liste des 15 sous-modules a été retrouvée
dans `.gitmodules` du parent. Pour comprendre les champs litigieux, lecture
de `bridges/mcps-decisions.mjs`, `deposium_bench/cases.py` et des sources MCPs
`src/services/chat-document-request-plan.ts` et
`src/routes/chat-handlers/document-read.ts`.

Le HEAD MCPs lu est `391be12078b1f3daa24a50c31c3a39eb72d7fb94`.
Cette lecture ne prouve aucun service actif, image exécutée ou parcours produit.
Le SHA-256 recalculé de `cases.jsonl` correspond au manifeste :
`88c728ee18d91647a6c3ee1a8ecfc65e808c916d82dba5ad70925dc4be3b3ab6`.

| Axe | Lignes / familles |
|---|---:|
| DOC | 8 / 4 |
| FOLLOWUP | 6 / 3 |
| PRESENTATION | 6 / 3 |
| SOURCES | 8 / 4 |
| EVIDENCE | 8 / 4 |
| train | 6 / 3 |
| calibration | 8 / 4 |
| test | 22 / 11 |

Les scénarios, documents synthétiques et familles de traduction restent dans
un seul split. Cependant, les exemples de bibliothèque se ressemblent entre
calibration et test malgré leurs IDs distincts : séparer les IDs ne garantit
pas une séparation de thèmes. Aucun entraînement ou choix de seuil sur le
test ne doit être ajouté à ce pilote.

## Lecture des 18 familles

Chaque famille ci-dessous comprend deux cas, suffixés `-fr` et `-en`.
Les réserves portent sur l'intention utilisateur et la portée des assertions,
même lorsque le normaliseur actuel produit exactement la référence.

| Famille / split | Intention et qualité de la référence | Applicabilité au premier classifieur |
|---|---|---|
| `doc-count` / train | Compter le catalogue est clair. `catalog` et `count_only=true` sont cohérents. `all` suppose le catalogue autorisé disponible; les deux IDs ne sont pas un inventaire lu. | Oui pour `/task`; compter réellement et distinguer la page du total restent hors mesure. |
| `doc-list` / train | Lister les documents est clair. `catalog` convient. Aucun nom/ID n'est fourni ou vérifié dans la sortie. | Oui pour `/task`; lexicalement très direct. |
| `doc-compound` / calibration | Trois demandes explicites : nombre, noms, résumés. `stored_summaries` est une projection plausible du contrat, mais une seule tâche ne prouve ni composition ni ordre ni même inventaire. `include_connector_count=true` reprend une politique MCPs : l'utilisateur ne demande pas explicitement les connecteurs. | Oui pour `/task` avec cette perte annoncée. Revue humaine requise pour le champ connecteur et la préférence entre résumés stockés et génération. |
| `doc-content` / test | Trouver les documents où le budget est gelé exige une recherche de contenu. `retrieve_answer` est cohérent. L'entrée fournit déjà `intent=search_query`; `basis=classified` décrit la mécanique du contrat. | Oui pour `/task`, conditionnellement à cette intention amont identique chez les deux candidats. Ne mesure pas la découverte autonome de l'intention. |
| `follow-resolved` / train | Contexte complet, même chat/espace et fichiers dans un autre ordre : résolution cohérente. Aucun énoncé utilisateur n'est transmis; `eligible=true` est acquis. | Exclu. Test déterministe d'identité/sélection, aucune compréhension FR/EN. |
| `follow-space-changed` / test | L'espace a changé : clarification prudente et cohérente. Aucune ACL n'est testée. | Exclu. Guard déterministe, pas une prédiction sémantique. |
| `follow-incomplete` / test | L'ancre incomplète ne permet pas d'appliquer le suivi à tout le set : clarification cohérente. | Exclu. Guard déterministe; autres causes d'ambiguïté absentes. |
| `presentation-table` / calibration | Résumés, français et tableau sont explicites dans les deux langues. `stored_summaries` est cohérent avec la politique documentaire, mais le texte utilisateur ne dit pas « stockés ». | Oui pour `/task`. `format` et `output_language` demandent des tâches séparées; aucune traduction n'est jugée. |
| `presentation-mermaid` / test | Diagramme des relations est une demande de contenu, pas un catalogue. `retrieve_answer` et `mermaid` sont cohérents. `focused` n'est pas entièrement déterminé par « ces documents » : le set référent n'est pas matérialisé dans l'entrée. | Oui pour `/task`; ne pas prendre `coverage` comme vérité utilisateur incontestable. |
| `presentation-language-followup` / test | L'historique immédiat donne une tâche et un tableau; « en français » peut raisonnablement conserver les deux. L'assistant ne porte aucun véritable tableau ni ancre fonctionnelle. | Hors pilote initial. Expérience contextuelle séparée possible avec le même historique chez les deux candidats. Message seul insuffisant. |
| `sources-pinned-documents` / test | Le clic `selectedValue=documents` domine une proposition géographique. La référence préserve correctement le choix. | Exclu. Priorité de choix déterministe; le texte ne doit pas gouverner ce guard. |
| `sources-explicit-web` / test | Choix Web explicite; `passthrough` décrit la délégation à un autre routeur, pas la réalisation de l'intention Web. | Exclu. Ne pas apprendre `passthrough` comme classe métier ou succès de recherche. |
| `sources-disabled-geo` / test | Géographie proposée mais aucun connecteur/doc : `none` conserve la limite de capacité. `intent` et confiance sont déjà fournis. | Exclu. Guard de disponibilité indépendant du modèle. |
| `sources-scope-documents` / calibration | « Analyse les documents » avec documents présents soutient le scope documentaire. La référence est plausible; pas de concurrent artifact ni choix ambigu. | Autre pilote possible pour la source, avec plusieurs classes et témoins; une seule famille positive ne suffit pas. |
| `evidence-useful-vs-topic` / calibration | La date répond; le toit bleu ne répond pas. Référence claire, distracteur facile. EN « When does the library open? » peut aussi désigner les horaires quotidiens; ici le pool favorise la date d'ouverture. | Exclu. Tâche requête–passage dédiée; formulation EN à revoir humainement. |
| `evidence-contradiction` / test | « fermée tous les lundis » répond utilement « non ». Toutefois la question ouverte « est-elle ouverte ? » n'affirme pas qu'elle l'est. `contradiction_ids` suppose que le contrat traite l'hypothèse interrogée comme prémisse. | Exclu. Clarifier humainement cette convention avant de qualifier un juge de contradiction. |
| `evidence-multiple` / test | Deux jours demandés, deux preuves utiles; distracteur de couleur sans utilité. Référence claire. | Exclu. Multi-preuves et sufficience ne se réduisent pas à un label de requête. |
| `evidence-insufficient` / test | Date d'examen et montant 2030 ne déterminent pas le montant 2031. Abstention/insuffisance cohérentes. | Exclu. Bonne exigence négative pour un futur juge; baseline MCPs actuelle non supportée. |

## Fuites et omissions

`candidate_request` retire bien `reference`, assertions et justification, mais
conserve `case_id` et `contract_id` dans son enveloppe de transport. Des IDs
comme `doc-count-fr`, `evidence-insufficient-en` ou
`presentation-mermaid-fr` révèlent la cible. **L'adaptateur modèle doit construire
son texte exclusivement à partir de `input`, jamais de l'enveloppe entière.**
Ne pas lui transmettre pack, scénario, split, langue de métadonnée, document IDs
de provenance ou justification. L'ID reste utilisable pour corréler les archives.
Une taxonomie fixe issue du contrat est légitime; des descriptions de labels
construites par cas ou depuis sa référence constituent une fuite.

L'intention amont dans `doc-content` et SOURCES est une entrée du composant
actuel, pas une annotation cachée. Elle donne toutefois une grande partie de
la solution. Un protocole retirant ce champ aux deux candidats serait une
autre expérience : le normaliseur courant dépend précisément de ce champ
pour accepter beaucoup de demandes de contenu.

La plupart des requêtes sont courtes et contiennent exactement les mots de la
classe : compte, liste, résumés, tableau, Mermaid. Les passages utilisent des
distracteurs très éloignés, et les preuves utiles viennent toujours en tête.
Ces cas vérifient une capacité de base; ils ne distinguent guère règles
lexicales et compréhension robuste. Un bon score ne prouve aucune robustesse
aux paraphrases, typos, négations, instructions citées, permutations de labels,
historique intercalé ou texte long. Ces variantes restent à écrire dans une
nouvelle version après revue, sans déplacer ou réécrire les références v1.

Le protocole prévoit aussi zéro/deux/neuf documents, ACL/visibilité, pagination,
résumés absents, filtres, choix sans documents, sources concurrentes, faux
positifs d'injection et preuve à faible rang. Ils sont absents ici. Les documents
v1 sont des identités synthétiques; aucun manifeste de contenu canonique
ne permet de vérifier le compte/liste/résumés produit. Le petit corpus ne
contient pas assez de familles indépendantes pour qualifier une généralisation
multilingue ou une latence p95 fiable.

## Pilote recommandé : tâche seule, 12 cas

Projection proposée `document-task-pilot/v1`, niveau A exploratoire :
`mcps.document-plan`, assertion exacte sur **`/task` seulement**, taxonomie fixe
`catalog`, `stored_summaries`, `retrieve_answer`. La référence est la projection
de l'assertion v1 existante; ni une prédiction MCPs ni une sortie du modèle
ne servent à la reconstruire. Le scorer conserve les états invalides/absents
et doit rejeter vide, label inconnu et label volontairement erroné.

Sous-ensemble exact, dans l'ordre du corpus :

```text
doc-count-fr
doc-count-en
doc-list-fr
doc-list-en
doc-compound-fr
doc-compound-en
doc-content-fr
doc-content-en
presentation-table-fr
presentation-table-en
presentation-mermaid-fr
presentation-mermaid-en
```

Cela donne six familles, deux langues et quatre cas de chaque tâche. Les splits
originaux restent visibles : 4 train, 4 calibration, 4 test. **Le test contient
uniquement `retrieve_answer`**, deux familles; il ne qualifie pas les trois
classes sur un holdout équilibré. Exécuter tous les splits peut servir de
recette exploratoire, avec score séparé par split/classe/famille, sans annoncer
une accuracy de généralisation ni sélectionner prompt/seuil sur le test.
Les paires FR/EN sont regroupées pour toute analyse d'incertitude.

Le candidat et le témoin reçoivent les mêmes valeurs de `input`, y compris
`has_documents` et `intent` lorsqu'il existe. Le texte sérialisé destiné au
modèle, son formatage, l'ordre des labels et l'éventuelle troncature sont figés
et archivés; aucun contexte n'est ajouté. Le témoin appelle le vrai
`normalizeChatDocumentRequest` de la révision MCPs épinglée puis projette
`task`. La sortie candidate normalisée contient le seul champ prédit `task`.
Elle ne complète pas les autres champs depuis la référence ou des règles
copiées. Un `null`/échec du témoin reste visible.

Cette comparaison évalue la tâche principale retenue par le contrat. Elle ne
mesure pas `count_only`, composition count/list/summaries, source, coverage,
format, langue, basis ou connecteurs. Une campagne sur les références complètes
doit présenter le classifieur simple comme `unsupported` pour ces capacités,
ou utiliser une projection explicitement versionnée; ne pas imputer les champs
du témoin au candidat pour fabriquer un plan complet.

FOLLOWUP et les guards SOURCES restent des contrôles natifs déterministes.
EVIDENCE exige son propre adaptateur et un témoin applicable. Le suivi
linguistique peut former une extension contextualisée sur les deux cas
`presentation-language-followup`, annoncée distinctement du pilote initial.

## Revue humaine encore ouverte

Un relecteur humain doit valider les formulations FR/EN et la convention
utilisateur de tâche : résumés stockés plutôt que nouvelle synthèse, compte
incluant ou non les connecteurs, couverture des relations Mermaid, portée de
« contradiction » pour une question ouverte, et ambiguïté de l'ouverture EN.
Il doit également décider des variantes nécessaires pour un futur test
équilibré. En attendant, conserver `human_review=not_performed`, l'identité
`1.0.0-exploratory`, les références originales et cette revue agent indépendante.

Aucun modèle, téléchargement, appel de service, modification applicative ou
prediction de candidat n'a été utilisé pour cette revue.
