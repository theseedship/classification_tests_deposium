# Pilote Vela 2.0 — 11 octobre 2026

Ce protocole précède les prédictions. Il ajoute des modèles isolés au banc,
sans changer les corpus, références, prompts, scorers ou archives historiques.
Les résultats restent `not_run` tant qu'une campagne n'a pas été exécutée.

| Candidat | Révision HF épinglée | Paramètres du checkpoint principal selon HF | Paramètres seuls en FP32, estimation | Fenêtre annoncée |
|---|---|---:|---:|---:|
| [Vela 0.3B](https://huggingface.co/vllm-sr/Vela-2.0-0.3B) | `d6f03aa9baca4f9017fa8f8e9c2764d3bed3f409` | 309 114 369 | 1,15 Gio | 8 192 tokens |
| [Vela 0.8B](https://huggingface.co/vllm-sr/Vela-2.0-0.8B) | `326b01d81f61fff7fd4ae570e54b87a49119e490` | 754 565 953 | 2,81 Gio | 16 384 tokens |
| [Vela 4B](https://huggingface.co/vllm-sr/Vela-2.0-4B) | `d692394127f6f87fc581d8634c9558fe4776efce` | 4 211 182 081 | 15,69 Gio | 16 384 tokens |

Les estimations multiplient les paramètres par quatre octets ; elles excluent
les activations, allocations temporaires, tokenizer et runtime. La tête
d'extraction supplémentaire des décodeurs est un fichier distinct. Les chiffres
des cartes peuvent donc différer de l'inventaire du checkpoint principal.
Les métadonnées HF sont conservées localement, sans confondre taille sur disque
et RAM. Le 4B reste documentaire : les paramètres seuls dépassent les quelque
14 Gio disponibles observés au préflight. Aucun téléchargement de ses poids,
relèvement des gardes ou perturbation de la stack n'est prévu dans ce lot.

## Interface et périmètre

Les modèles publient `system_one` avec Choice, Noul, Score, Span et Set.
Le 0.3B est un encodeur ModernBERT ; les décodeurs sont fondés sur Qwen3.5.
Le premier pilote utilise exclusivement Choice, sur les mêmes **132 bases**
FR/EN (76 documentaires, 28 mathématiques, 28 chimiques) et les **24 propositions
Mastra** de recherche/statistiques/repli. Un contrôle synthétique précède les
campagnes et vérifie aussi le refus d'une entrée trop longue avant inférence.

Le contexte, la question et les descriptions restent complets ; les IDs des
options sont projetés en clés ordinales `c0`, `c1`, etc. Les annotations et IDs
sémantiques n'entrent pas dans le modèle. Le code natif épinglé assure l'encodage,
la décision et la calibration : ses algorithmes ne sont pas recopiés.
Une interface SystemOne similaire à Decision2 ne prouve pas une compatibilité
du loader ou du rendu natif ; ceux-ci sont contrôlés séparément.

Les références demeurent exploratoires et attendent une revue humaine.
Les accords Mastra conservent zéro cas qualifié, sans exécution des outils.
Ce lot ne mesure ni extraction de spans, multisélection, sécurité, récupération
documentaire, réponse finale, intégration CLI/chat, GPU, ONNX ou grandes longueurs.
Les capacités supplémentaires pourront faire l'objet de corpus dédiés.

## Ressources fixées avant résultats

Un seul worker CPU FP32 à la fois, deux threads, entrée locale limitée à
**4 096 tokens natifs complets**, schéma et options compris, sans troncature.
Le code natif pouvant raccourcir l'état, le bridge construit une séquence
complète avec les helpers amont puis contrôle les tenseurs réellement transmis.
Un dépassement donne `unsupported` avant le forward.

0.3B : garde RSS **4 096 Mio**, **6 144 Mio disponibles** avant worker,
**2 048 Mio** pendant l'exécution, initialisation **120 s**, choix **30 s**.
0.8B, sous réserve de compatibilité du code : garde RSS **6 144 Mio**,
**8 192 Mio disponibles** avant worker, mêmes autres limites.
Les campagnes Mastra ont un budget moteur **300 s** ; les bases sont bornées
par un délai externe SIGINT **900 s** conservant une archive interrompue.
Une garde atteinte reste un échec archivé, sans ajustement pour compléter le score.
La surveillance RSS par relevés ne garantit pas un plafond instantané.

Le runtime Decision2 existant est réutilisé sans mise à jour : Python 3.12.3,
Torch 2.14.0+cpu, Transformers 5.17.0, Tokenizers 0.23.2, Safetensors 0.8.0,
NumPy 2.5.3, avec `runtimes/small-models/runtime.lock`.
Imports ordinaires et tests hors ligne ne chargent aucun poids.

## Conservation et publication

Le téléchargement HF est explicite, révision épinglée, dans `models/` ignoré
par Git. Pour le 0.3B, les deux exports `onnx/*` sont exclus : seule la variante
Torch est évaluée. Le préparateur contrôle chaque fichier sélectionné contre
les métadonnées HF de cette révision, dont les blobs Git et SHA-256 LFS ; un
inventaire public est vérifié avant import du code éditeur.

Chaque campagne crée une archive neuve et conserve code, profils, empreintes,
runtime, stack et tous ses sous-modules, sorties natives, tokens, statuts,
couverture, latences, chargement et RSS. Aucun service Deposium n'est exécuté.
Les sorties brutes, profils absolus et corpus privés restent hors Git.
Les rapports ventilent domaine, langue, difficulté, split et tailles d'entrée.
Une passe courte ne détermine pas le seuil de bascule vers un LLM.

Les cartes déclarent Apache-2.0 pour les modèles ; le tokenizer du 0.3B est
également soumis aux conditions Gemma. Les notices et conditions de chaque
snapshot doivent être examinées avant exploitation, indépendamment du score.
Les comparaisons de sécurité publiées en amont ne sont pas une mesure sur
notre corpus et incluent des tâches présentes dans l'entraînement.

## Contrôle initial et variante de chargement

Le contrôle `vela2-control-03-20261011-001`, code `0769a12`, a atteint la
garde RSS de 4 096 Mio pendant le chargement autonome de l'encodeur, avant
toute décision. Ses deux entrées restent `error/vela2_rss_limit` ; zéro
cas comparatif a été exécuté. La trace initiale n'enregistre pas le pic exact.

Une variante est donc fixée avant les premières prédictions : le loader
Hugging Face `AutoModel.from_pretrained` publié par le même snapshot, en
FP32/CPU/SDPA, local uniquement, puis le moteur natif `Vela2` sur ce modèle.
Le loader autonome alloue le modèle avant de charger le state dict ; le
loader Transformers permet un chargement sans cette initialisation complète.
Les poids, dtype, paramètres, rendu et moteur de décision sont conservés,
mais aucune égalité bit-à-bit entre les deux chemins n'est revendiquée sans
mesure. Les gardes ne changent pas. Un contrôle successeur conserve sa propre
archive et ses empreintes ; l'échec initial n'est ni modifié ni rescorré.

Les contrôles suivants `vela2-control-03-20261011-002` et
`vela2-control-08-20261011-001`, code `4441f22`, ont refusé l'identité du
modèle avant disponibilité (pics échantillonnés : 905,6 et 5 169,8 Mio).
Le compteur Hub du checkpoint principal diffère des éléments réellement
présents dans les paramètres natifs et dans les headers safetensors :
**309 114 371** pour l'encodeur et **754 565 954** pour le décodeur principal,
plus **1 119 745** dans la tête broad du 0.8B. Les contrôles d'identité sont
corrigés à ces comptes exacts, avant toute campagne comparative.
Les trois échecs initiaux restent conservés séparément et ne reçoivent
aucun score de qualité. Les petites différences n'affectent pas les
estimations mémoire arrondies du tableau.

Les contrôles `vela2-control-03-20261011-003` et
`vela2-control-08-20261011-002`, code `724aa68`, ont également échoué avant
les décisions. Le diagnostic instrumenté privé du 0.3B a identifié une erreur
dans le nouveau bridge : le contrôle dtype lisait le tuple `(nom, paramètre)`
comme un tenseur. Le contrôle est corrigé et testé sur les deux variantes,
avec refus conservé des mauvais dtypes, devices et nombres de paramètres.
Les comptes exacts précédents restent vérifiés ; ils ne suffisaient pas à
résoudre cet autre défaut. Les archives d'échec sont conservées.

## Contrôles et campagnes achevés

Les contrôles synthétiques finaux, code `33d231b`, sont disponibles :
`vela2-control-03-20261011-004` et `vela2-control-08-20261011-003`.
Le choix court passe ; l’entrée trop longue est `unsupported` avant forward,
respectivement 10 028 et 20 120 tokens complets. Pics RSS relevés par le parent :
1 145,5 et 5 227,8 Mio. Ces contrôles ont **zéro cas scoré** ; les relevés
échantillonnés et les pics rapportés par le worker sont des mesures distinctes.

Les campagnes `context-base-vela{03,08}-20261011-001` et
`mastra-read-vela{03,08}-20261011-001` sont complètes et scellées :
**65/132, 18/24** pour .3B ; **79/132, 14/24** pour .8B.
Le [comparatif à quatorze modèles](MODEL_COMPARISON_VELA2_20261011.md)
réunit les ventilations, ressources et limites. Les anciennes qualifications
et captures restent conservées. Aucun modèle historique, service ou API
n’a été relancé. Les métriques de confiance ne sont pas interchangeables :
Vela Choice publie une marge top-2, tandis que Decision2 utilise son propre
score natif. Aucun seuil de routage commun n’est calibré ici.

Le 4B reste `not_run`. Le 0.3B et le 0.8B n’ont pas de mesure de qualité sur
longues entrées, de campagne temporelle répétée ni d’essai GPU.

## Rejouer explicitement un candidat

Les profils `profiles/vela2-{03,08}-cpu-context.json` décrivent les gardes et
les révisions. Leurs chemins sont relatifs au profil, pour un clone avec poids
sous `models/` et runtime sous `.cache/decision2-runtime/`. Un worktree peut
utiliser un profil absolu privé conservé sous `results/`, sans copier les poids.
Le préparateur `scripts/prepare-vela2-assets.py --help` vérifie hors ligne le
snapshot sélectionné contre les métadonnées Hub épinglées ; les manifests
publiés recensent les fichiers utilisés. L’installation et le téléchargement
sont des opérations explicites, jamais déclenchées par les tests ordinaires.

Après préparation et vérification du budget mémoire, utiliser des dossiers
neufs à chaque exécution, par exemple pour .3B :

```sh
python3 -B scripts/check-vela2-cpu.py --profile profiles/vela2-03-cpu-context.json --output results/vela2-control-03-new
python3 -B -m deposium_bench run --dataset datasets/context-choice-v1/cases.jsonl --profile profiles/vela2-03-cpu-context.json --stack-root /chemin/deposium_fullstack --output results/context-base-vela03-new
python3 -B -m deposium_bench observe-mastra-read --profile profiles/vela2-03-cpu-context.json --stack-root /chemin/deposium_fullstack --output results/mastra-read-vela03-new
```

Pour .8B, changer le profil et les dossiers de sortie ; conserver un seul
modèle actif. Un statut `missing`, `error` ou `unsupported` est archivé et ne
constitue pas une réponse correcte. Une campagne avec choix erronés peut
terminer avec un code retour non nul tout en conservant tous ses résultats.
``run`` ne remplace aucun composant de la stack.
