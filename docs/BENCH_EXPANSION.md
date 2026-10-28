# Extension du banc : temps, langues, difficulté et domaines

Extension livrée le 1er octobre 2026 sur `feat/domain-context-bench`, corpus
figé au commit `52f1660` avant inférence. Le choix générique, les 132 bases
FR/EN, les oracles restreints, les variantes de longueur, le replay MCPs résident
et les chronomètres sont implémentés. Les corpus et archives du pilote v1 restent
inchangés. Voir [local-only material, not distributed](PROTOCOL.md) et
[les résultats](CONTEXT_RESULTS.md).

La base Julia scellée réussit 52/132 cas : documentaire 32/76, maths 8/28,
chimie 12/28. La campagne longue est scellée : 114/300 réussites scorées sur
378 variantes, 24 cibles infaisables et 54 erreurs de garde RAM à 8k; aucune réussite
globale ni qualité à 8k n'est annoncée. Références et traductions ne disposent
pas de revue humaine indépendante; aucun seuil LLM ni parcours produit n'est qualifié.

## Ce que le pilote permet déjà de voir

Relecture des archives `results/task-mcps-001`, `task-julia-001` et
`task-julia-reversed-001`, et du code des deux bridges :

| Mesure canonique | Médiane | Maximum | Ce qui est chronométré |
|---|---:|---:|---|
| MCPs, appel du banc | 142,98 ms | 167,11 ms | Validation, lancement Node à chaque cas, imports, fonction, transport et fermeture |
| Julia, appel du banc | 86,34 ms | 102,44 ms | Validation, transport vers le worker résident, décision et contrôles |
| Julia, `inference_ms` | 81,13 ms | 96,64 ms | Encodage/audit, moteur, validation des scores, softmax et choix |

Chaque ligne contient 14 observations, sans répétitions ni warm-up explicite.
La médiane est la moyenne des deux valeurs centrales. Le percentile au rang
`ceil(0,95*n)` serait ici le maximum, pas une estimation stable de la queue.
Julia archive aussi 10,193 s pour imports/chargement/relevé de versions : ce
temps exclut la vérification préalable des assets et le démarrage du processus.
La durée complète d'initialisation des deux adaptateurs n'est pas disponible.

Ces temps ne permettent pas de classer la vitesse de décision MCPs/Julia.
La référence MCPs appelle `normalizeChatDocumentRequest`, une fonction
déterministe; elle n'appelle aucun LLM. Un futur LLM doit être mesuré dans le
même protocole : sa latence dépendra notamment du runtime, du matériel, du
contexte et de la sortie demandée. Elle n'est pas connue avec ces archives.

Le pilote compte sept cas français et sept anglais, sept familles traduites,
avec des messages de 2 à 10 mots, médiane six. Deux cas seulement utilisent
l'historique (deux tours, en anglais); deux reçoivent déjà `intent=search_query`.
Il n'y a aucun corps de document dans ces 14 entrées. Les classes comptent
quatre `catalog`, six `stored_summaries`, quatre `retrieve_answer`; le split
test ne comporte aucun `catalog`.

La difficulté n'a pas été annotée avant ce pilote. Une description rétrospective
par structure distingue six demandes simples, six composées/avec contrainte de
présentation et deux suivis contextuels. Ce classement ne mesure pas une difficulté
universelle et ne transforme pas les échecs Julia en exemples « difficiles ».

## Temps comparables pour la suite

Le transport résident et les chronomètres suivants sont livrés, sans recopier
les fonctions applicatives; les mesures répétées ont leur propre campagne :

1. Worker MCPs résident et modules importés une fois, comme le worker Julia,
   avec contrôles d'identité et de dérive des fichiers.
2. Mesurer séparément l'initialisation complète, la première décision, la
   décision après échauffement et le temps complet vu par l'appelant.
3. Pour la frontière interne commune, partir de l'entrée JSON décodée et finir
   à la décision normalisée. Inclure formatage/tokenisation propres au candidat;
   exclure transport et vérification de provenance, mesurés séparément.
4. Annoncer échauffement, répétitions, ordre alterné des candidats et concurrence.
   Configuration initiale pour les candidats locaux : trois lancements de
   processus, cinq appels d'échauffement puis dix passages mesurés du corpus.
   Les répétitions temporelles ne créent pas de nouveaux exemples de qualité.
5. Publier effectif, médiane/p95, dispersion entre lancements, erreurs/timeouts,
   RAM/VRAM et débit à concurrence donnée. Les durées d'échec restent visibles;
   un timeout est une mesure censurée, pas une réponse rapide réussie.

Le « chargement à froid » signifie ici un processus neuf, sans prétendre vider
les caches du système. Archiver CPU/GPU, threads, runtime, quantification,
batch, longueur encodée réelle et budget. Aucun cache de réponses dans les temps
frais; les sorties reprises/rescorées ne constituent pas de nouvelles mesures.

Pour un LLM distant, le temps client inclut le réseau et le provider; son temps
interne reste inconnu sans télémétrie fournie. Rapporter temps jusqu'à la
**décision exploitable**, erreurs de format, retries et coût. Le premier token
peut être une mesure supplémentaire, mais ne vaut pas décision terminée.

## Langues et construction de la difficulté

Conserver FR/EN pour amorcer les nouveaux domaines, puis DE/ES/IT/PT, les quatre
autres langues déjà prévues au protocole. Ce sont des cibles du banc, pas une
qualification linguistique de Julia ou du produit. Le nouveau schéma de cas v2
accepte les six langues; le corpus livré contient FR/EN. Les cas v1 historiques
gardent leur contrat FR/EN. DE/ES/IT/PT exigent encore des traductions revues.

Annoter séparément langue de la consigne, des sources/historiques et de la sortie
demandée; ajouter du mélange de langues. Les traductions et paraphrases d'un
même problème restent dans un seul split et comptent comme une seule famille
pour l'indépendance statistique. Revue linguistique distincte de la vérification
du calcul; sans revue, les exemples restent exploratoires.

| Niveau cible | Construction annoncée avant les prédictions | Variantes |
|---|---|---|
| D1 | Une règle ou une demande explicite, contexte suffisant | Formulation directe puis paraphrase |
| D2 | Plusieurs contraintes ou deux transformations à combiner | Unités, type, signe, format, négation |
| D3 | Chaîne de dépendances ou hypothèse à retrouver dans le contexte | Référent distant, condition de domaine, distracteur proche |

La longueur est un axe distinct : une formule courte peut être difficile.
Ajouter séparément typos, accents absents, variables renommées, notations
ASCII/Unicode/LaTeX et instructions citées. La longueur doit être mesurée
avec le tokenizer de chaque candidat; un dépassement explicite n'est ni une
troncature silencieuse ni une mauvaise réponse sémantique.

Le [protocole domaine × longueur](CONTEXT_LENGTH_PROTOCOL.md) précise les paliers
100 à 8 000 tokens, leur prolongement selon les candidats, le comptage total,
les variantes appariées et la calibration d'une éventuelle bascule vers un LLM.
Les 132 cas livrés plus bas sont les bases de ces variantes; aucun seuil
de bascule n'est encore mesuré ou qualifié.

Les cas ambigus, contradictoires ou insuffisamment spécifiés forment une strate
propre avec attente explicite de clarification/abstention. Plusieurs solutions
valides doivent être acceptées; une préférence subjective ne devient pas un
QCM à réponse unique. Les références restent hors de l'entrée du candidat.
Une option correctement choisie « information insuffisante » est une décision
sémantique, distincte d'une absence de réponse, d'une erreur technique ou d'une
abstention du candidat; le contrat `bench.context-choice` et le scorer conservent
cette distinction via une réponse `choice_id` ordinaire.

## Mathématiques : préciser ce que signifie « assembler »

Quatre capacités séparées : choisir un complément parmi des options; vérifier
qu'une transformation est valide sous ses hypothèses; choisir une étape utile
pour atteindre un but; classer plusieurs compléments pertinents. Une composition
correctement typée n'est pas nécessairement utile, et une expression familière
n'est pas nécessairement vraie. Le but et les hypothèses font partie de l'entrée.

| Exemple présent dans les bases | Réponse ou propriété attendue | Vérification indépendante |
|---|---|---|
| Compléter `(x+1)^2` pour tout réel `x` | `x^2 + 2*x + 1` | Coefficients du polynôme développé |
| Pour `f:R^2→R^3`, `g:R^3→R`, composer à partir de `x∈R^2` | `g(f(x))` | Compatibilité des domaines/codomaines |
| `A` de taille 2×3, `B` de taille 3×4 : forme de `AB` | 2×4; `BA` non défini avec ces tailles | Règles de dimensions |
| Compléter `sqrt(x^2)` pour tout réel `x` | `abs(x)`; accepter `x` exige `x≥0` | Hypothèses et contre-exemple `x=-1` pour le distracteur |
| `f(x)=x^2`, `g(x)=x+1` : dérivée de `f(g(x))` | `2*(x+1)` | Dérivation exacte et règle de chaîne |
| Simplifier `(x^2-4)/(x-2)` en conservant la même fonction et son domaine | `x+2` avec `x≠2` | Factorisation et domaine vérifiés séparément |
| `n` en mol, `V` en litre : concentration molaire | `c=n/V`, en mol/L | Calcul dimensionnel; il ne prouve pas seul la loi physique |

Créer des paires où une seule hypothèse, dimension, parenthèse ou négation change
la validité. Donner les règles nécessaires dans une première série; les retirer
dans une série distincte pour séparer application de règles et connaissances
préalables. Le second protocole n'est pas directement comparable au premier.

Préférer des oracles exacts restreints (arithmétique rationnelle, polynômes,
dimensions) et, si nécessaire, un moteur symbolique épinglé. Un test numérique
peut réfuter une identité avec un contre-exemple, mais quelques points réussis
ne constituent pas une preuve. Une chaîne textuelle différente peut être
mathématiquement équivalente. Même un outil symbolique n'est pas un décideur
universel : conserver un état « non résolu par l'oracle » plutôt qu'un faux PASS.
Voir les [précisions officielles de SymPy sur l'égalité](https://docs.sympy.org/latest/tutorials/intro-tutorial/gotchas.html#equals-signs).

## Chimie : conservation, composition et information suffisante

| Exemple présent dans les bases | Réponse ou propriété attendue | Vérification indépendante |
|---|---|---|
| Compter les atomes dans `Ca(OH)2` | Ca:1, O:2, H:2 | Analyse de formule et multiplicateurs |
| Équilibrer `H2 + O2 → H2O` avec entiers positifs minimaux | Coefficients 2,1,2 | Conservation de chaque élément et PGCD |
| Combiner `Ca^2+` et `Cl^-` en proportion électriquement neutre minimale | 1:2 | Somme des charges et minimalité entière |
| `c1=0,20 mol/L`, `V1=50 mL`, volume final `V2=200 mL`, soluté conservé | `c2=0,050 mol/L` | `c1*V1=c2*V2`, conversion d'unités |
| La formule brute `C2H6O` suffit-elle à identifier une structure unique ? | Non; préciser les liaisons | Deux contre-exemples : éthanol et éther diméthylique |

Les tests de conservation vérifient une équation, pas la faisabilité réelle
d'une réaction. La formule brute ne détermine pas généralement la structure;
le respect des charges ne démontre pas la stabilité d'un composé. Les questions
sur les propriétés ou la plausibilité nécessitent des conditions et une référence
chimique distincte. Commencer par les oracles exacts ci-dessus, puis élargir.

## Place de Julia et lien à Deposium

La [fiche officielle Julia-1](https://huggingface.co/SupersonicLabs/Julia-1)
de la révision utilisée décrit un modèle qui compare des options fournies.
Elle indique que ses évaluations n'établissent pas la résolution d'équations
algébriques ou de longues chaînes de calcul. Les packs maths/chimie font désormais
l'objet de mesures exploratoires locales; leurs scores ne qualifient pas un
raisonnement général et ne sont pas ceux du pilote documentaire.
La génération libre de formules serait une capacité séparée des choix finis.

Le nouveau profil `profiles/julia-1-cpu-context.json` accepte uniquement
`bench.context-choice` avec contexte, question et choix fournis par cas.
Il fixe `max_length=8192`; les profils documentaires restent à 1024 et gardent
`mcps.document-plan`. Les métadonnées, IDs des cas et références ne font pas
partie du contenu encodé. Le lien aux contrats applicatifs reste une annotation
du banc, sans replay scientifique de la stack.

Les usages Deposium visés sont la sélection de passages/formules utiles et la
vérification d'affirmations documentaires : raccordement futur aux contrats
de preuve et de recherche, notamment `mcps.evidence-attribution` et
`turbov3.rerank`, dont les bridges restent planifiés. Un test abstrait d'algèbre
ne constitue pas un replay de ces composants. Le registre conserve les 15
composants et les motifs d'omission; aucune capacité scientifique active de la
stack n'est déduite de son inventaire.

## Premier périmètre livré avant d'autres modèles

| Pack | Familles indépendantes nouvelles | Cas FR/EN | Statut |
|---|---:|---:|---|
| Décision documentaire, classes et niveaux équilibrés | 36 | 72 | Livré; références par agent, revue humaine restante |
| Compléments/validité mathématiques, progression D1–D3 | 12 | 24 | Livré avec oracles exacts restreints |
| Composition/conservation chimiques, progression D1–D3 | 12 | 24 | Livré avec oracles exacts restreints |
| Ambiguïté/information insuffisante, réparties entre domaines | 6 | 12 | Livré; option sémantique, sans abstention technique |
| Total livré | 66 | 132 | Une campagne Julia de base scellée; 52/132 réussites |

Ce volume est un premier corpus, pas une puissance statistique garantie.
Réserver les familles de test avant écriture des variantes, couvrir chaque
classe documentaire dans chaque split et équilibrer la position des bonnes
réponses. Les rotations d'options sont des répétitions d'un même problème.
Présenter résultats par domaine, capacité, langue, niveau cible, longueur et
statut; pas de moyenne unique mélangeant catalogue, algèbre et chimie.

Les références, les splits et la position des choix ont été figés avant la
première inférence; les tests rejettent réponses fausses/vides et annotations
exposées au candidat. La grille longue initiale utilise neuf familles de
calibration, sept paliers et trois positions : 378 variantes, 354 éligibles,
24 cibles de 100 tokens inatteignables. Elle ne sélectionne pas de règle sur le test.

Les résultats, erreurs et mesures répétées sont publiés dans
[CONTEXT_RESULTS.md](CONTEXT_RESULTS.md). Depuis ce premier pilote, les
campagnes [GLiNER](GLINER_RESULTS.md) et [Jev](JEV_RESULTS.md) sont exécutées
sur les mêmes bases et textes longs. La [local-only material, not distributed](PROTOCOL.md) priorise désormais
la revue humaine bilingue et de nouvelles familles, puis les expériences Indecis.
Ajouter DE/ES/IT/PT après revue des premiers packs, sans lancer un produit
cartésien coûteux de toutes les variantes. Une comparaison avec un LLM et la
qualification d'une cascade restent des lots distincts.
