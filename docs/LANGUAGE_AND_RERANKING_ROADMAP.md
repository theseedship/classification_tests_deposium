# Historical language and reranking proposals

**Historical design note — 3 October 2026.** The French text below records the
proposal at that date, before later passage campaigns. Its future-tense tasks
and publisher/runtime descriptions are not the current execution status. Use
[Campaign status](CAMPAIGN_STATUS.md) for issue dependencies and next steps,
[Results and coverage](RESULTS.md#coverage-overview) for observations and gaps,
and the [protocol](PROTOCOL.md) for evaluation boundaries. No language-policy
qualification or application integration follows from this note.

État au 3 octobre 2026 : **cadrage pour un lot ultérieur**. Aucun modèle,
entraînement, téléchargement ou appel applicatif n'a été lancé pour cette fiche.
Les mesures du [local-only material, not distributed](PROTOCOL.md) portent surtout sur un choix
fermé FR/EN ; elles ne mesurent ni une politique de langue de réponse ni le
classement de passages. Les trois axes ci-dessous ont des références et des
consommateurs distincts. Le [local-only material, not distributed](PROTOCOL.md) recense déjà
`mcps.text-profile-language` (repli `en` pour texte court/inconnu/autre),
`solid.chat-request-modes`, `mcps.document-task-plan.output_language`,
`mcps.passage-reranking` et `turbov3.embedding-rerank-profile`. Ces fiches
datées sont des points de raccordement à revérifier dans les sources et le
runtime, pas une preuve qu'un détecteur par message ou un reranker précis est
actif aujourd'hui. Les [local-only material, not distributed](PROTOCOL.md) distinguent
également recherche MCPs et service de reranking Turbo.

## Trois sorties de langue par message

| Axe | Entrée et sortie proposées | Exemple et frontière |
|---|---|---|
| Langue du **message entrant** | Texte exact du dernier message → `fr`, `en`, `mixed`, `unknown`, avec confiance et segments si nécessaire | « Peux-tu explain this? » est mixte ; `x = 2` ou « OK » peut rester inconnu. |
| Langue **attendue de la réponse** | Consigne de l'utilisateur, préférence persistée, conversation et message → code langue ou `unknown`, plus `basis` | « Réponds en français » prévaut sur une requête anglaise et sur un document anglais. |
| Langue(s) des **documents/passages** | Chaque source/segment autorisé → ensemble de langues, `mixed` ou `unknown`, avec provenance | Une question FR peut être servie par un passage EN ; cela n'impose pas une réponse EN. |

Une convention à soumettre à revue : la **dernière consigne explicite** sur la
langue de sortie prime, puis la préférence utilisateur stable, puis le contexte
conversationnel, et enfin seulement la langue détectée du message. Conserver
la source et la portée de cette décision. Une consigne ponctuelle n'efface pas
la préférence durable sans action explicite de l'utilisateur. Définir un repli
déterministe pour `unknown` ; le modèle de détection ne décide ni consentement,
ni droits, ni accès aux documents. Les extraits cités, code, identifiants et
formules gardent leur sens même si la prose de réponse change de langue.

Ne pas forcer un code langue sur les messages très courts, les URL, le code,
les formules ou une alternance FR/EN. Pour les documents, enregistrer le niveau
d'observation : métadonnée déclarée du fichier, détection sur extrait, ou
annotation revue. Un document hétérogène doit pouvoir produire plusieurs
étiquettes de passages. Ne pas déduire cette sortie de la langue de la requête.

## Données, annotations et mesures

Construire un corpus de **messages et épisodes** distinct des 132 choix de
contexte et des 24 choix Mastra. Chaque entrée conserve texte candidat visible,
contexte minimal nécessaire, préférence/consigne explicite lorsqu'elle existe,
langues des passages et références annotées séparément. Annotations proposées :
`input_language`, `input_segments`, `output_language`, `output_basis`,
`passage_languages`, preuve de chaque label, ambiguïté et alternatives acceptables.
Les annotations et références ne sont jamais transmises au modèle.

Inclure au moins : FR→FR, EN→EN, EN→FR sur demande ou préférence, FR→EN sur
demande, requête FR/document EN, requête EN/document FR, conversation changeant
de langue, préférence maintenue entre tours, préférence contredite explicitement,
message court, code/formule, bilingue et langue hors périmètre. Versionner
les cas, la politique de repli et la revue humaine. Grouper les splits par
**conversation, document et famille de traduction** : une traduction, paraphrase
ou autre tour du même épisode ne doit pas passer en test si sa source est en
calibration. Garder un test FR/EN équilibré et des cas inconnus hors réglage.

Rapporter **par axe** exactitude macro et par classe, matrice de confusion,
couverture et dénominateur des `unknown`/abstentions, calibration des confiances
sur les classes qui en ont une, et conformité de la langue de réponse constatée.
Mesurer séparément latence, temps de chargement, RAM/VRAM et coût de chaque
étape ; une prédiction correcte de langue d'entrée ne prouve pas la bonne
langue de sortie. Le seuil d'abstention se fixe sur calibration uniquement.
Ne pas calculer un PASS global si une famille n'a aucun cas scoré.

## Décider, puis classer les passages

Un sélecteur `Julia` ou [Strands](STRANDS_DECIDER_CANDIDATE.md) pourrait choisir
une **action** ou un **profil** de recherche à partir d'options fermées. Un
reranker reçoit ensuite une requête et les passages déjà récupérés, puis les
reclasse. Cette composition garde le choix d'outil, les filtres d'identité et
d'espace, la recherche initiale et le classement comme frontières observables.
Un reranker ne peut pas sauver un passage absent des candidats initiaux.
Comparer d'abord `retrieval seul` au même `retrieval + reranker`, à top-k
et corpus figés, sans remplacer la logique des services applicatifs dans le banc.

Une autre hypothèse serait un torse **multitâche partagé** avec lectures
spécialisées pour langue, routage et pertinence. Ce n'est pas un branchement
immédiat : [Strands](https://github.com/strands-labs/strands-decider/blob/main/docs/inference.md)
remplace la tête de génération de Qwen par une tête à pointeur et adapte le
torse par LoRA ; ses sorties typées `choice`/`noul`/`score` ne produisent pas
d'emblée un score de pertinence `requête × passage` calibré pour Deposium.
Changer les libellés candidats sans réentraîner est possible au niveau API,
mais la fiabilité d'un **nouveau domaine** demande corpus annoté, négatifs,
split sans fuite et calibration. Comparer coût mémoire/latence d'un torse partagé
aux petits modèles séparés avant d'envisager entraînement ou mutualisation.

## Deux rerankers publics à examiner plus tard

| Candidat et révision HF relevée | Taille/licence/portée publiées | Question ouverte |
|---|---|---|
| [cross-encoder/mmarco-mMiniLMv2-L12-H384-v1](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/tree/1427fd652930e4ba29e8149678df786c240d8825) `1427fd652930e4ba29e8149678df786c240d8825` | 117,6 M paramètres, Apache-2.0, `fr` et `en` listés ; entraîné sur mMARCO traduit. Référence multilingue compacte face à Strands, mais pas « minuscule ». | Classement croisé FR↔EN, passages techniques, troncature et CPU local. |
| [cross-encoder/ms-marco-TinyBERT-L2-v2](https://huggingface.co/cross-encoder/ms-marco-TinyBERT-L2-v2/tree/81d1926f67cb8eee2c2be17ca9f793c7c3bd20cc) `81d1926f67cb8eee2c2be17ca9f793c7c3bd20cc` | Environ **4,39 M paramètres**, Apache-2.0, fiche marquée **anglais**, longueur 512 dans la recette. Contrôle vraiment petit à combiner avec Julia ; qualité FR/EN non établie. | Mesurer le compromis pertinence/latence en EN, puis examiner séparément FR et paires croisées. |

Tailles et langues proviennent des [fiches officielles mMARCO](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1)
et [TinyBERT](https://huggingface.co/cross-encoder/ms-marco-TinyBERT-L2-v2),
non de mesures sur notre machine. Le corpus mMARCO est traduit ; son étiquette
multilingue ne prouve pas la qualité sur documents Deposium, paires de langues
croisées ni formules. Aucun reranker FR/EN véritablement minuscule n'est validé
par cette recherche documentaire ; ne pas forcer un choix sur ce critère.
Le tableau de vitesse TinyBERT utilise un V100 selon la fiche : aucune
projection de cette cadence sur notre machine ou sur une cascade Julia.

Un protocole futur fixe la révision des deux modèles, les candidats initiaux,
la fenêtre de tokens et les refus de troncature, les jugements de pertinence par
requête/passage, des négatifs difficiles et les groupes de documents traduits.
Mesurer rappel du premier étage, nDCG@k/MRR@k et taux de passage supportant
effectivement la réponse, par sens FR→FR, EN→EN, FR→EN et EN→FR, avec chaque
dénominateur. Ajouter temps par paire et par requête top-k, RSS/VRAM et coût.
Une amélioration de classement n'établit pas la fidélité de la réponse finale.
