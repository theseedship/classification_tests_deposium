# Domaine × longueur : limites utiles et politique de bascule

Cadrage actualisé le 1er octobre 2026. La génération et l'analyse sont livrées
sur `feat/domain-context-bench`; corpus figé à `52f1660`. Complément de
[BENCH_EXPANSION.md](BENCH_EXPANSION.md), commandes dans
[local-only material, not distributed](PROTOCOL.md), observations dans
[CONTEXT_RESULTS.md](CONTEXT_RESULTS.md).
La base de 132 cas et la campagne longue sont scellées : 378 variantes,
300 réponses scorées, 24 cibles de 100 tokens inatteignables et 54 erreurs
au palier 8k après activation de la garde RAM sur le premier cas.
Ni qualité longue, ni seuil de bascule LLM, ni routage produit n'est qualifié.

## Question mesurée

Pour chaque **candidat × capacité × domaine × langue**, déterminer les zones où
la qualité, le temps de réponse et les ressources satisfont les objectifs fixés.
La longueur et la difficulté sont deux axes séparés. Un problème court peut
déjà nécessiter un autre outil; un long contexte explicite peut rester facile.
Une fenêtre de contexte annoncée ne constitue pas une garantie de qualité.

Le résultat attendu est une carte de fonctionnement : mesures et effectifs par
palier, zones qualifiées, zones incertaines, limites techniques et motifs de
bascule. Ne pas réduire cette carte à un seul nombre de tokens pour tout le modèle.

## Ce qui est connu pour Julia-1

Révision `a85b127321d580d65176c89ced8273f305745d85`, fichiers locaux vérifiés :

| Limite ou observation | Valeur | Portée |
|---|---:|---|
| Longueur effectivement encodée dans le pilote | 126 à 157 tokens | 14 cas canoniques, mêmes longueurs pour l'ordre inversé |
| Plafond du profil CPU du pilote | 1 024 | Configuration; aucune mesure de qualité à 1 024 tokens |
| Plafond accepté par l'adaptateur et le schéma du banc | 8 192 | Garde locale étendue et testée; profil historique inchangé |
| Plafond du nouveau profil de choix générique | 8 192 | `julia-1-cpu-context.json`, tête 512, deux threads, garde RSS 3 072 MiB |
| Longueur native de la nouvelle base scellée | 45 à 123 tokens | 132 cas FR/EN; 52/132 réussites |
| Grille longue exécutée | Paliers 100 à 4 000 | 114/300 réussites scorées; références exploratoires |
| Premier essai au palier 8 000 | 7 996 natifs, 8 000 après padding | Arrêt par la garde RSS 3 072 MiB; qualité non évaluée |
| Fenêtre du checkpoint annoncée par l'auteur | 8 192 | Entrée combinée; configuration encodeur cohérente |
| Budget question/choix du profil | 512 | Contrainte distincte du contexte global |
| Limite d'une option du runtime | 48 tokens | Un long choix peut dépasser cette limite même si le total tient |

Sources : `profiles/julia-1-cpu-task.json`, `deposium_bench/julia_adapter.py`,
`schemas/candidate-v1.schema.json`, `raw_output.encoding_info` des archives
`task-julia-001` et `task-julia-reversed-001`; `encoder/config.json` et README
du modèle téléchargé. La [fiche du modèle](https://huggingface.co/SupersonicLabs/Julia-1)
mentionne un smoke test CPU à 8 192 tokens, mais pas une qualification de qualité
à cette taille. Ce smoke test n'a pas été reproduit par ce banc.

L'extension de garde est livrée dans un profil distinct : encodage strict,
refus typés des dépassements contexte/tête/options avant forward, sans troncature
silencieuse. La campagne longue observe les paliers jusqu'à 4 000 tokens;
le premier essai à 8 000 déclenche la garde RAM, et les 53 demandes suivantes
n'exécutent plus le moteur. Cela ne qualifie pas la qualité à 8 192.
Les profils et archives historiques ne sont pas réécrits.

## Paliers et comptage

Grille initiale cible : **100, 250, 500, 1 000, 2 000, 4 000, 8 000 tokens**.
Pour les candidats qui les acceptent, prolonger à **16 000 puis 32 000**, et
au-delà seulement si le besoin produit et le budget le justifient. Arrêter
l'extension à la limite documentée/configurée de chaque candidat ou à la limite
de ressources; une longueur non supportée reste visible, sans score inventé.

Ajouter des contrôles de frontière séparés, juste sous, à et au-dessus de la
limite autorisée. Pour Julia, 8 192 est une frontière technique testée hors ligne,
distincte du palier 8 000. Le test au-dessus vérifie le refus explicite, sans
forcer une inférence hors limites ni le compter comme une erreur de connaissance.

La longueur de référence principale est l'**entrée totale réellement encodée** :
instructions, historique/documents, question, options, marqueurs/template et
tokens spéciaux. Publier aussi séparément le contenu variable et le surcoût du
format, ainsi que la longueur après padding et le batch pour les mesures de
temps/mémoire. Julia arrondit les batches au multiple de huit, dans la limite du
plafond; `encoding_info.tokens` décrit la séquence avant ce padding.
Pour un modèle génératif, réserver explicitement le budget de sortie
lorsque sa fenêtre est partagée entre entrée et génération.

Construire les paliers avec un tokenizer et un format de référence épinglés;
archiver leur révision, cible et compte réel. Comparer ensuite tous les candidats
sur les **mêmes textes, questions et choix sémantiques**, sans leur fabriquer
un contexte différent pour atteindre artificiellement le même compte natif.
Enregistrer en plus les tokens natifs et le template de chaque candidat.
Ainsi, un cas du palier « 1 000 de référence » peut consommer un autre nombre
de tokens sur un autre modèle; la comparaison reste appariée sur le même contenu.

La tolérance implémentée de ±5 % évite de couper un énoncé pour atteindre
un nombre exact; les essais de frontière, eux, doivent atteindre le compte exact.
Si instructions et choix dépassent déjà 100 tokens, marquer ce palier infaisable
avec ce format et publier le minimum réel. Ne pas raccourcir seulement ses labels.
Une série « 100 tokens de contenu + surcoût » reste possible, mais doit porter
cette désignation explicite et ne pas être confondue avec 100 tokens au total.
Dans le pilote documentaire historique, le tokenizer épinglé chargé seul mesure
**113 tokens de surcoût** pour le format canonique : question préfixée 23,
descriptions 82, quatre marqueurs et quatre tokens spéciaux.
Le palier 100 au total est donc impossible avec ce
format. Le profil 1 024 laisse 911 tokens au JSON de contenu, pas 1 024 tokens
au seul message utilisateur. Dans `bench.context-choice`, question et descriptions
varient par cas : ce surcoût est recalculé, et 100 tokens peut être atteignable
pour certaines familles, mais pas pour toutes.
La tête de 512 est un plafond, pas un remplissage systématique de 512 tokens;
le runtime exige en revanche `max_length > head_length + 4`. L'adaptateur
vérifie cette relation avant démarrage. Les budgets de chaque entrée sont
contrôlés par l'encodeur strict avant forward; la génération de variantes
mesure les tokens séparément, sans charger les poids.

Conserver un plafond de profil fixe et annoncé pendant la série. Augmenter la
longueur des entrées ne signifie pas changer `max_length` à chaque cas.
Un changement de fenêtre/runtime est une autre configuration expérimentale.

## Construire les longueurs dans chaque domaine

| Domaine | Contexte à faire croître | Signal à retrouver ou combiner |
|---|---|---|
| Documentaire | Extraits et tours d'historique plausibles, demandes citées | Tâche demandée, ancre et contraintes actives |
| Mathématiques | Définitions, hypothèses, lemmes et expressions voisines | Domaine, dimensions, conditions et objectif de transformation |
| Chimie | Données de composition, espèces, unités et conditions fournies | Éléments/charges, quantités, conditions pertinentes |

Pour une famille, garder **question, faits nécessaires et référence inchangés**
entre variantes de longueur. Ajouter des distracteurs plausibles du même domaine
sans nouvelle contradiction ou indice de réponse. Revoir ces variantes : une
phrase ajoutée peut modifier le problème. Éviter le simple remplissage répétitif,
qui mesure surtout la tolérance au bruit artificiel.

Déplacer le signal utile au début, au milieu et à la fin. Ajouter une série où
plusieurs éléments nécessaires sont éloignés les uns des autres. Conserver un
nombre de choix fixe dans une série; faire varier ce nombre séparément, car il
modifie aussi longueur et difficulté. Comparer notations et langues avec la
même prudence : les symboles mathématiques/chimiques peuvent se tokeniser autrement.

La série de raisonnement augmente séparément le nombre d'étapes ou d'hypothèses
à combiner à longueur comparable. Croiser ensuite quelques niveaux avec les
longueurs, pour distinguer perte du signal, difficulté de raisonnement et
interaction des deux. Chaque nouveau problème exige une référence vérifiée.

Toutes les variantes d'une famille — longueur, position, traduction, paraphrase,
notation et ordre des options — restent dans le même split. Elles sont corrélées
et n'augmentent pas le nombre de situations indépendantes.

## Mesures et seuils de bascule

Pour chaque cellule domaine/capacité/langue/longueur, publier : familles et cas,
couverture, exactitude parmi tous les cas et parmi les cas scorés, gravité des
erreurs, refus sémantiques, erreurs techniques, dépassements, troncatures,
latences médiane/p95 avec effectifs, RAM/VRAM et coût. Les échecs et cas hors
capacité ne disparaissent pas du dénominateur. Conserver les sorties brutes.

Définir avant calibration les objectifs de qualité, latence, coût et erreurs
inacceptables pour l'usage. Aucun seuil numérique de production n'est fixé ici.
Estimer l'incertitude au niveau des familles indépendantes, pas des milliers
de variantes d'une poignée de questions. Une cellule insuffisamment documentée
est **non qualifiée**, même si tous ses quelques exemples réussissent.

Apprendre la politique sur les familles de calibration, la figer, puis mesurer
sur des familles de test indépendantes. Évaluer côte à côte : petit modèle seul,
LLM seul, cascade et référence applicative pertinente. Le LLM de secours doit
être lui-même qualifié sur les cas escaladés; son gain ne se déduit pas de sa taille.

Deux formes de bascule sont à distinguer :

- **Avant le petit modèle** : entrée hors fenêtre/budget ou zone non qualifiée,
  destination choisie avec les métadonnées disponibles à l'exécution.
- **Après le petit modèle** : décision manquante/invalide, abstention ou critère
  d'incertitude réellement calibré, avec comptabilisation du premier appel.

La durée d'une cascade escaladée inclut les deux appels, le transport et les
chargements éventuels; son coût inclut les deux traitements. Conserver aussi
la proportion de bascules inutiles et les erreurs que la cascade laisse passer.
Un softmax élevé ne suffit pas à certifier la réponse. Le domaine ou la difficulté
annotés avec connaissance de la référence ne sont pas des informations accessibles
au routeur réel : utiliser des métadonnées autorisées ou qualifier leur estimation.

Ne pas supposer une dégradation monotone. Si les résultats sont irréguliers,
publier des zones et leurs incertitudes plutôt qu'un faux « jusqu'à N tokens ».
Un plafond conservateur peut être retenu seulement si les strates pertinentes
jusqu'à ce plafond satisfont les critères, puis si la politique complète tient
sur le test. Pour les tâches exactes, un outil symbolique ou une clarification
peut être une destination plus appropriée qu'un LLM. Les guards d'accès,
consentement et ressources restent déterministes, quelle que soit la destination.

## Exécution progressive et livrable

Les 132 cas livrés dans l'extension sont des cas de base, pas le volume final
après déclinaisons. Annoncer le nombre d'inférences avant chaque campagne : cas
éligibles × variantes effectivement retenues × configurations × répétitions.
Échantillonner les interactions selon une matrice de couverture versionnée;
ne pas multiplier mécaniquement toutes les langues, tailles, positions et modèles.

La première grille gelée retient neuf familles de calibration FR/EN, une par
domaine et difficulté, sept paliers de 100 à 8 000 et trois positions, ordre
original : 378 variantes. Les faits et choix restent inchangés; seules des
annexes synthétiques explicitement hors du problème actif sont autorisées.
Le validateur contrôle leur structure figée, l'ordre, le hash de base et l'ID.
Cette série ne mesure pas encore l'assemblage de plusieurs indices distants.
Les prolongements 16k/32k restent planifiés pour des candidats compatibles.

Commencer par les paliers courts et quelques familles sentinelles par domaine,
puis raffiner autour des premières dégradations et limites de ressources.
Cette exploration utilise les familles de développement/calibration; le test
final garde une grille gelée, y compris des paliers longs non favorables, pour
ne pas sélectionner seulement les zones où le candidat réussit.

Livrer des courbes qualité/latence/mémoire selon la longueur, séparées par domaine
et langue, ainsi qu'une table des règles de bascule candidates avec leur preuve.
Rester au niveau A pour les capacités isolées. La mise en service d'une cascade
Deposium exige ensuite son harness intégré et la vérification des invariants.
