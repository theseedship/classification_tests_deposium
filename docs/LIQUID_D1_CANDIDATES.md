# LiquidAI d1 : deux candidats pour les décisions locales

**Mise à jour du 10 octobre 2026 :** Le pilote texte d1-omni-600M est exécuté : 51/132 bases et 16/24 accords Mastra provisoires. [local-only material, not distributed](PROTOCOL.md). d1-3B, images et audio restent non mesurés. Le cadrage daté ci-dessous est conservé.

Veille du 7 octobre 2026. **Aucune inférence Deposium exécutée** : lecture des
fiches, configurations et helpers publics uniquement. Aucun poids téléchargé,
service lancé ou corpus privé transmis. Ce lot ajoute des pistes au
[registre](NEXT_CANDIDATES.md), sans modifier les résultats historiques du
[local-only material, not distributed](PROTOCOL.md).

## Révisions observées et ressources

| Candidat | Révision HF inspectée | Paramètres et fichier de poids |
|---|---|---|
| [LiquidAI/d1-3B](https://huggingface.co/LiquidAI/d1-3B/tree/da1fe36a861f24690f27f622dca1d8688503d113) | `da1fe36a861f24690f27f622dca1d8688503d113` | 3 123 483 888 paramètres BF16 ; `model.safetensors` : 6 247 065 504 octets |
| [LiquidAI/d1-omni-600M](https://huggingface.co/LiquidAI/d1-omni-600M/tree/414f8d6438174f5b2133a9c21a478fc42625e308) | `414f8d6438174f5b2133a9c21a478fc42625e308` | 587 161 089 paramètres FP32 ; `model.safetensors` : 2 348 774 500 octets |

Les métadonnées et tailles viennent des API HF à ces révisions. Les valeurs
`usedStorage` du dépôt incluent d'autres artefacts/versions : ne pas les employer
comme taille d'un modèle chargé. Les hashes des poids restent à vérifier au
téléchargement ; aucun hash de fichier local exécuté n'existe pour cette veille.

| Configuration proposée | Poids seuls, estimation | Mesures Deposium |
|---|---|---|
| d1-3B CPU FP32 | 12,49 Go, soit 11,64 GiB | RSS, latence et capacité : `unobserved` |
| d1-3B accélérateur BF16 | 6,25 Go, soit 5,82 GiB | VRAM et latence : `unobserved` |
| d1-omni CPU FP32 | 2,35 Go, soit 2,19 GiB | RSS, latence et capacité : `unobserved` |
| d1-omni accélérateur FP16 | 1,17 Go, soit 1,09 GiB | VRAM, parité et latence : `unobserved` |

Calculs : nombre de paramètres × octets par dtype, hors activations, images,
audio, tokenizer et runtime. Ils ne prouvent pas qu'une campagne ou un contexte
maximal tient dans la mémoire disponible. La fiche Omni conseille FP16 plutôt
que BF16 sur accélérateur ; vérifier la parité sur nos cas avant comparaison.

## Interfaces et périmètres

Les deux modèles exposent `system_one(state, questions, ...)` : `noul` donne
P(oui), `choice` choisit une option nommée et `score` renvoie l'espérance d'un
niveau ordinal de 2 à 10 niveaux. Ils ne génèrent pas les réponses finales d'un
chat. Appeler leur API et leurs scorers natifs, avec un mapping d'IDs explicite,
sans recopier le routage MCPs.

Le [d1-3B](https://huggingface.co/LiquidAI/d1-3B/blob/da1fe36a861f24690f27f622dca1d8688503d113/README.md)
est dérivé de LFM2.5-VL-3B et accepte texte et images. Le
[d1-omni](https://huggingface.co/LiquidAI/d1-omni-600M/blob/414f8d6438174f5b2133a9c21a478fc42625e308/README.md)
combine un encodeur textuel avec vision et audio. Il accepte images **ou** audio
dans une demande, pas les deux simultanément. Les fiches listent FR/EN pour
le texte, sans résultat Deposium ni ventilation française publiée ; l'audio
Omni est entraîné sur des interactions anglophones.

Les helpers de choix renvoient toujours un meilleur candidat. Aucun champ natif
`abstained` comparable à [ImaJEV](IMAJEV_CANDIDATE.md) n'est fourni. Leur
`confidence` est la probabilité maximale parmi les options proposées, distincte
de la métrique de concentration d'autres APIs. Elle ne prouve pas la justesse.
Pour les cas indécidables, conserver les choix du corpus ; une option
supplémentaire d'abstention demanderait un protocole séparé commun aux candidats.
Omni applique des températures stockées au texte, mais pas à l'image/audio.
Tout seuil de repli futur demande une calibration tenue hors du split de test.

## Longueurs : précontrôle obligatoire

| Chemin | Limite déclarée | Risque vérifié dans le helper |
|---|---|---|
| d1-3B texte/images | 32 768 positions | Le budget de lot par défaut de 65 536 n'est pas une garde de contexte par cas |
| Omni texte | 16 384 positions | State, instruction et descriptions peuvent être coupés silencieusement |
| Omni avec images | 16 384 positions totales ; texte limité à 896 | Plusieurs coupes sont possibles avant le forward |
| Omni avec audio | Clip mono 16 kHz, 30 s maximum | Le clip trop long est coupé ; la place textuelle dépend du préfixe audio |

Le [prompt Omni](https://huggingface.co/LiquidAI/d1-omni-600M/blob/414f8d6438174f5b2133a9c21a478fc42625e308/prompt.py)
réserve un budget aux options, coupe instructions/descriptions puis la fin du
state. `usage.input_tokens` décrit l'entrée après préparation ; ce nombre seul
ne certifie pas l'absence de perte. Mesurer aussi les instructions et critères,
même pour un state court. Refuser les cas altérés avant inférence au lieu de
les comparer au texte complet reçu par les autres candidats. Cette vérification
doit utiliser les véritables helpers épinglés, sans leur substituer un encodeur.

Le [runner 3B](https://huggingface.co/LiquidAI/d1-3B/blob/da1fe36a861f24690f27f622dca1d8688503d113/runner.py)
peut admettre un cas isolé dépassant son budget de lot. Compter le rendu complet,
questions/options et positions visuelles incluses, puis appliquer la limite
par cas avant appel. La réduction des images et leur découpage doivent être
archivés ; une formule ou un axe devenu illisible ne constitue pas une entrée
équivalente à la page originale.

## Résultats externes : indications, pas classement Deposium

Liquid AI rapporte **48,57** pour d1-3B et **15,95** pour Omni sur Decision Index
0.2.1, avec le scorer officiel mais sans soumission au classement. Sur Fast
Decisions **dev**, les fiches annoncent respectivement **69,3** et **76,9**.
Ces deux protocoles ne donnent donc pas le même ordre : garder scores, domaines
et splits ensemble. Ils ne justifient aucune position dans notre tableau mesuré.

Les temps GPU/Mac publiés pour le 3B ne décrivent pas notre CPU ou notre GPU.
La fiche Omni ne publie aucune latence. Ne pas lui attribuer les temps du 3B,
ni confondre ces checkpoints ouverts avec le modèle d1 de l'API hébergée.

## Chargement et licence

Prévoir un environnement isolé : Transformers >=5.14 pour 3B, >=5.15 pour Omni,
PyTorch, torchvision et Pillow ; soundfile pour le chemin audio. Le chargement
utilise du code personnalisé (`trust_remote_code=True`) : inspecter et épingler
les fichiers réellement exécutés avant de charger les poids. Le
[modèle 3B](https://huggingface.co/LiquidAI/d1-3B/blob/da1fe36a861f24690f27f622dca1d8688503d113/modeling_d1.py)
recharge tokenizer/processeur depuis `name_or_path` sans révision explicite ;
une révision passée au premier appel ne suffit pas à prouver leur identité.
Un snapshot local vérifié doit contenir tous les artefacts nécessaires.
Utiliser l'API du checkpoint d1 chargé : le constructeur `SystemOne` isolé
prend par défaut la base `LiquidAI/LFM2.5-VL-3B`, qui serait un autre candidat.

Les deux dépôts utilisent la **LFM Open License v1.0**, pas Apache-2.0.
La [licence épinglée](https://huggingface.co/LiquidAI/d1-omni-600M/blob/414f8d6438174f5b2133a9c21a478fc42625e308/LICENSE)
définit un seuil de chiffre d'affaires annuel de 10 M$ et exclut l'usage
commercial par une entité dépassant ce seuil. Conserver le texte et les
conditions de redistribution lors du futur téléchargement ; ne pas déduire
les droits commerciaux du seul statut « open weights ».

## Pilote proposé

1. Préparer d'abord Omni en texte seul : empreinte plus accessible pour vérifier
   le mapping, les gardes et la non-troncature. Son score global externe faible
   invite à une campagne bornée ; il ne prédit pas son résultat de routage.
2. Reprendre les 132 bases FR/EN et les 24 choix Mastra existants, mêmes choix,
   ordre, références et statut de revue. Publier domaines, langues, difficulté,
   taille du prompt, couverture et dénominateurs ; les accords Mastra restent
   provisoires et ne mesurent pas l'exécution d'outils ou les réponses finales.
3. Préparer d1-3B séparément si les ressources le permettent : candidat plus
   prometteur en décision générale selon ce protocole externe, plus coûteux en
   poids. Un modèle à la fois, gardes de mémoire et durée figées avant lancement.
4. Étendre aux longueurs sans perte d'entrée, puis aux images avec le panel
   distinct proposé pour ImaJEV. Séparer contrôles synthétiques et pages privées
   relues ; tester image absente/remplacée et grouper les splits par document,
   scénario et famille de traduction. L'audio reste un pilote ultérieur autonome.
5. Relever chargement, préparation/tokenisation, forward, temps client complet,
   médiane/p95, RSS/VRAM et cas refusés. Comparer la confiance/calibration sur
   des références relues, sans assimiler un score de probabilité à la vérité.

Les scorers doivent rejeter les réponses vides/fausses ; `unsupported`, erreur,
timeout et abstention restent distincts. Garder corpus, annotations, images,
poids et sorties brutes hors Git, publier uniquement les agrégats reproductibles.
Tout raccordement intégré doit réutiliser les vrais services de la stack et
leur provenance selon [local-only material, not distributed](PROTOCOL.md). Aucun contrôle
d'accès ou de ressources ne dépend d'une prédiction ; une qualification CLI/chat
demande ensuite une mesure du parcours produit.
