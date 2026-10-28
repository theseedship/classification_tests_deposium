# Variantes jusqu'à 9B : inventaire et admission CPU

Lecture du 11 octobre 2026, après le pilote D3 mini/flash (`04c7785`).
Inventaire documentaire uniquement : aucun nouveau poids téléchargé, aucune
inférence, aucun service modifié. Toutes les variantes proposées ci-dessous
restent `not_run`, avec RSS et latence `unobserved`.

Les [19 résultats existants](evidence/model-comparison-d3-larger-overview-20261011/report.md)
et leurs qualifications sont conservés. Flash obtient 124/132 contre 123/132
pour Jev historique sur ce corpus exploratoire ; ce résultat ne démontre pas
l'état de l'art ni une avance robuste. Les 24 choix Mastra mesurent l'accord
aux propositions en attente de revue, sans exécution d'outil ni qualité de
réponse finale. La taille interne de Jev API demeure inconnue.

## Variantes des familles déjà mesurées

« Reportée » exige une trace dans les anciens documents. Une variante découverte
pendant cette veille n'est pas présentée comme un ancien refus pour manque de RAM.
Les tailles exactes viennent des métadonnées HF et des manifestes amont, sans
vérification locale des poids. Les nombres ronds des noms commerciaux peuvent
différer du nombre total d'éléments des checkpoints.

| Variante non mesurée | Taille relevée, milliards | Trace antérieure | CPU et mémoire des paramètres seuls | Intérêt de comparaison |
|---|---:|---|---|---|
| [Decision-2.0-Nox-4B](https://huggingface.co/vllm-sr/Decision-2.0-Nox-4B) | 4,208 | Mentionnée dans [local-only material, not distributed](PROTOCOL.md), sans décision explicite de report | Runtime natif FP32 : 15,68 Gio ; préflight accessible à préparer | Compléter Kai/Eos/Sol ; comparer au texte de D3 mini |
| [Vela-2.0-4B](https://huggingface.co/vllm-sr/Vela-2.0-4B) | 4,211 | Reportée dans [Vela](VELA2_PILOT.md) : ~14 Gio disponibles au préflight initial, contre 15,69 Gio de paramètres FP32 | CPU FP32 documenté : 15,69 Gio ; nouveau budget et worker à qualifier | Mise à l'échelle de Vela 0.3/0.8B ; choix, puis extraction de spans séparément |
| [Decision-2.0-Lux-9B](https://huggingface.co/vllm-sr/Decision-2.0-Lux-9B) | 7,941 | Ajout de cette veille, absent de notre liste de campagnes | Runtime natif CPU FP32 : 29,58 Gio ; trop pour la RAM disponible relevée pendant cette veille | Comparaison de taille proche de D3 flash, modèle texte |
| [Vela-2.0-9B](https://huggingface.co/vllm-sr/Vela-2.0-9B) | 7,945 | Ajout de cette veille | CPU FP32 documenté : 29,60 Gio ; même restriction de RAM disponible | Compléter la courbe Vela et comparer le choix à D3 flash |
| [LiquidAI/d1-3B](https://huggingface.co/LiquidAI/d1-3B) | 3,123 | À préparer séparément après Omni, si les ressources le permettent, dans [le cadrage](LIQUID_D1_CANDIDATES.md) | Estimation FP32 : 11,64 Gio ; chemin CPU à vérifier avec le helper natif | Même fournisseur que Omni 600M, mais architecture texte/images différente |
| [GLiNER2.5-Decide-1B](https://huggingface.co/fastino/GLiNER2.5-Decide-1B) | 1,189 | Ajout de cette veille | Checkpoint FP32 : 4,43 Gio ; contrôles d'identité et d'encodage à adapter | Comparaison avec multi-Decide ; anglais annoncé, FR exploratoire |
| [GLiNER2.5-Decide](https://huggingface.co/fastino/GLiNER2.5-Decide) | 0,486 | Ajout de cette veille | Checkpoint FP32 : 1,81 Gio ; adapter le profil et les gardes | Variante annoncée « 340M », plus grande que multi-Decide ; anglais |
| [laya](https://huggingface.co/convaiinnovations/laya) | 0,421 | Écartée du lot multilingue dans [local-only material, not distributed](PROTOCOL.md) | Estimation FP32 : 1,57 Gio ; nouveau profil à qualifier | Anglais généraliste, contexte annoncé 512 ; FR séparé |
| [laya-typed-decisions](https://huggingface.co/convaiinnovations/laya-typed-decisions) | 0,421 | Écartée du lot multilingue dans [local-only material, not distributed](PROTOCOL.md) | Estimation FP32 : 1,57 Gio ; projection native à vérifier | Quatre workflows synthétiques anglais ; intérêt spécialisé, pas une simple version plus grande |
| [Muose-100M-Decision](https://huggingface.co/muose/Muose-100M-Decision) | 0,118 | Ajout de cette veille | Checkpoint FP32 : 0,44 Gio ; nouveau profil à qualifier | Compléter le 50M mesuré, contexte 512 ; licence non commerciale |

On retrouve donc **quatre variantes déjà documentées comme non exécutées ou à préparer**, une
variante déjà mentionnée (Nox), et **cinq ajouts vérifiés** dans les mêmes familles.
Les variantes anglaises ne deviennent pas multilingues par leur taille.

Les cinq variantes publiques D3 sous 9B (edge, lite, nano, mini, flash) sont déjà
mesurées : [collection amont](https://huggingface.co/collections/vllm-sr/decision-30).
Le 4B de Decision 2.0 se nomme **Nox**, pas Sol ; aucun `Sol-4B` public n'a été
retrouvé dans [la collection officielle](https://huggingface.co/collections/vllm-sr/decision-20).
Une nouvelle variante <=9B n'a pas été établie pour Noma, Julia ou ModernJEV
pendant cette recherche. Julia-1-ONNX est un autre format/runtime, pas un
checkpoint plus grand. Jev/GLiDE sont des services : ne pas leur inventer une taille.
Indecis et ses spécialisations ne forment pas une gamme publiée comparable ici.

## CPU : faisable n'est pas déjà prêt dans le banc

Le relevé ponctuel local donne **43,11 Gio de RAM totale, environ 24,62 Gio
disponibles**, avec la stack active. Ce n'est pas une réservation. Le swap ne
sert pas de budget d'admission. Les minima ci-dessus utilisent `N × 4 / 2^30`
en FP32 ; ils excluent activations, pic de chargement, tokenizer et runtime.
Ils ne sont ni des RSS mesurés ni des exigences GPU.

Les [sources Decision 2.0](https://huggingface.co/vllm-sr/Decision-2.0-Nox-4B/blob/ae269ecf34a0b3a89026bc1afd9c995279212fad/decision2/qwen.py)
chargent le CPU en FP32. Les [instructions Vela](https://huggingface.co/vllm-sr/Vela-2.0-9B/blob/068425bb145c05884a98b870c219047da22d9aea/USAGE.md)
documentent également CPU FP32. Leur stockage mixte BF16/FP32 ne prouve pas une
résidence CPU BF16. En comparaison, [D3 flash](D3_LARGER_CPU_RESULTS.md) a été
mesuré en BF16/readout FP32, à 13,75 Gio de RSS. On ne peut pas transposer son
RSS aux autres modèles.

Lux et Vela 9B dépassent donc déjà la RAM disponible avec leurs seuls paramètres
FP32. Leur essai CPU demanderait une autre situation mémoire ou un chemin de
précision réduite explicitement pris en charge et vérifié. Un GPU dédié serait
une autre configuration, avec ses mesures propres. Les
[GGUF Decision 2.0](https://huggingface.co/vllm-sr/Decision-2.0-Lux-9B-GGUF)
demandent une branche spécifique de llama.cpp et l'interface SystemOne :
ce n'est pas un remplacement automatique du runtime évalué.

Les adaptateurs locaux actuels acceptent Kai/Eos et Vela 0.3/0.8B, pas Nox/Lux
ou Vela 4/9B. Leurs plafonds RSS d'environ 6 Gio ne conviennent pas à ce nouveau
lot. Sol conserve son export historique depuis une branche distincte.
Ajouter seulement un nom de modèle dans un JSON ne suffit pas : il faudra
épingler les actifs, vérifier le code natif, adapter le bridge et fixer les
gardes mémoire/délais avant les premières prédictions. Aucun de ces changements
d'exécution n'est fait par cet inventaire.

## Autres candidats déjà envisagés, familles encore non mesurées

Ils complètent éventuellement le panel 8/9B, mais ne sont pas des variantes
de nos familles ayant déjà des scores.

| Candidat | Taille et limite d'interprétation | Préparation nécessaire |
|---|---|---|
| [CLM-v0.1-8B](https://huggingface.co/Contrastive-LM/CLM-v0.1-8B) | Qwen3-8B vérifié à 8,191B, plus deux têtes ; fichier des têtes seulement ~75,6 Mo | Encodeur externe à épingler, pooling natif dernier token, garde de longueur et séparation cache froid/actions réutilisées ; [cadrage](CLM_MODERNJEV_CANDIDATES.md) |
| [Qwen3-4B via SemIf](https://huggingface.co/Qwen/Qwen3-4B) | LLM utilisé pour un choix en un forward | Réutiliser le vrai helper jevworks, sans génération ; [cadrage](KUMO_QWEN_CLEF_CANDIDATES.md) |
| [Imajev 4B](https://huggingface.co/mohit67890/imajev-4b) / [9B](https://huggingface.co/mohit67890/imajev-9b) | Adaptateurs LoRA + readout, backbone Qwen3.5 externe ; le nom « 9B » ne vérifie pas le plafond strict du total effectivement chargé | Native PyTorch à prévoler sur CPU, compte complet des tenseurs, head et abstention à respecter ; texte avant images. Le 9B est une variante de cette famille encore non mesurée ; [cadrage](IMAJEV_CANDIDATE.md) |
| [Clef-flash « 9B »](https://huggingface.co/Cloudflare/clef-flash) | API HF actuelle : **9,410B** éléments, donc au-delà de 9B stricts | Candidat voisin si le plafond vise les noms « 9B » ; tête jointe obligatoire, refus de troncature et CPU BF16 à prévoler ; [cadrage](KUMO_QWEN_CLEF_CANDIDATES.md) |
| [Strands Decider 2B v19](https://huggingface.co/StrandsAgents/strands-decider-2B-hobson-v19) | Tentative de chargement reportée sous garde RSS ; aucun score dans les 19 modèles | Reprendre le chargement et son budget séparément ; [résumé de la tentative](MODEL_COMPARISON_VELA2_20261011.md), [protocole](STRANDS_DECIDER_CANDIDATE.md) |

La [liste publique Strands](https://huggingface.co/api/models?author=StrandsAgents&limit=100)
contient aussi les variantes non mesurées suivantes. Elles sont enregistrées
séparément dans la preuve JSON ; elles ne portent pas le nombre de familles
mesurées à plus de 19.

| Variante Strands | Taille du backbone externe | Limite avant campagne |
|---|---:|---|
| [2B Hobson v21](https://huggingface.co/StrandsAgents/strands-decider-2B-hobson-v21) | Qwen3.5-2B-Base | Nouvelle révision après le v19 tenté ; adapter/readout et poids de base à figer |
| [2B Qwen3.5 v1-2610](https://huggingface.co/StrandsAgents/strands-decider-2B-qwen3.5-v1-2610) | Qwen3.5-2B-Base | Nouveau checkpoint ; ne pas lui attribuer la tentative v19 |
| [E2B Gemma4 v1-2610](https://huggingface.co/StrandsAgents/strands-decider-E2B-gemma4-v1-2610) | Gemma-4-E2B-it : **5,123B** éléments BF16 | ~9,54 Gio de paramètres BF16 du backbone, avant adapter/readout et activations ; total chargé et CPU à vérifier |
| [E4B Gemma4 v1-2610](https://huggingface.co/StrandsAgents/strands-decider-E4B-gemma4-v1-2610) | Gemma-4-E4B-it : **7,996B** éléments BF16 | ~14,89 Gio de paramètres BF16 du backbone, avant adapter/readout et activations ; total chargé et CPU à vérifier |

Les étiquettes Gemma **E2B/E4B ne sont pas les comptes totaux des checkpoints**.
La taille de l'adaptateur seul ne suffit pas non plus. Les versions Strands
12B et 26B-A4B sortent du périmètre en taille totale, même si une partie
seulement des paramètres est activée par token.

La [fiche E4B épinglée](https://huggingface.co/StrandsAgents/strands-decider-E4B-gemma4-v1-2610/blob/1344d44397c457f3be34b8ff15c593b41248c6bf/README.md)
documente un mode CPU. Elle demande toutefois le code GitHub actuel pour le
support Gemma 4, absent de la version PyPI décrite, et télécharge le backbone
au premier usage. Le futur pilote devra épingler un commit et vérifier les
actifs avant exécution ; l'exemple amont ne mesure pas notre machine.

## Ordre proposé et conditions de comparaison

1. **Nox 4B et Vela 4B**, un worker à la fois : prolonger les familles déjà
   mesurées et les comparer à D3 mini. **d1-3B** peut suivre en texte, avec son
   API native et des contrôles CPU séparés.
2. **Lux 9B et Vela 9B** : principaux équivalents de taille pour D3 flash,
   après admission mémoire ou qualification d'un autre runtime. La
   [carte Flash épinglée](https://huggingface.co/vllm-sr/d3-flash/blob/521525effa79469d899a570726547dd7f00da3af/README.md)
   compte environ 0,46B de vision dans les 8,39B. Lux comporte 7,937B de backbone
   texte selon [son manifeste épinglé](https://huggingface.co/vllm-sr/Decision-2.0-Lux-9B/blob/1dcd1e7f240eab37ac09a6d0b0f77654b59411f9/MODEL_MANIFEST.json).
   Publier texte/vision/têtes et précision séparément.
3. **GLiNER anglais, Laya anglais/typé et Muose 100M** : compléter le compromis
   qualité/RAM/latence, sans attendre des scores équivalents parce qu'ils sont
   plus grands que les checkpoints précédents.
4. **CLM et autres familles** : protocole distinct si leur intérêt produit
   justifie l'adaptateur ; les caches CLM et les images ne doivent pas fausser
   les temps du panel textuel.

Réutiliser les mêmes 132 bases FR/EN et 24 propositions Mastra, sans modifier
leurs références ni les archives précédentes. Conserver les classements général,
domaines, langues et routage, ainsi que tokens complets natifs, couverture,
statuts d'échec, chargement, médiane/p95 et RSS. Des tailles comparables aident
à interpréter les résultats ; elles n'effacent pas les différences d'entraînement,
d'architecture et de précision. Les grandes longueurs, les temps répétés et la
qualité des réponses finales restent des expériences séparées.

## Révisions et preuves de cette veille

Les [métadonnées publiques relevées](evidence/variants-up-to-9b-20261011.json)
conservent révisions, sources et comptes. Ce sont des déclarations amont, pas
des poids localement vérifiés ou un manifeste de campagne.
Les SHA Nox et d1-3B relevés aujourd'hui diffèrent de leurs anciennes mentions :
`25e8f67d…` et `da1fe36a…`. Les observations historiques restent liées à ces
anciens SHA ; les nouveaux candidats devront figer leur propre révision.

| Modèle | Révision HF consultée |
|---|---|
| Nox 4B | `ae269ecf34a0b3a89026bc1afd9c995279212fad` |
| Lux 9B | `1dcd1e7f240eab37ac09a6d0b0f77654b59411f9` |
| Vela 4B | `d692394127f6f87fc581d8634c9558fe4776efce` |
| Vela 9B | `068425bb145c05884a98b870c219047da22d9aea` |
| d1-3B | `051bcc464b01b9f92942b364d9586b0ef5912432` |
| GLiNER Decide 1B | `67af949e17bebd20f05fe020a971079889e7a462` |
| GLiNER Decide | `9d1bfb848cd16d93ee56ccbc59cd92bf0f284d90` |
| Laya anglais | `7b928d828b7b0e022f929d9bd2e44165aa270148` |
| Laya typé | `e929ae5cf69bc34259cd2f95c9e91145b818b1f0` |
| Muose 100M | `244f2f3b614b9732843c01a0ee8134e7fa1da278` |

Pour Vela, les manifestes affichent chacun un élément de plus que le total
safetensors publié par l'API HF. L'écart est conservé dans la preuve JSON,
sans résoudre arbitrairement l'identité du futur modèle chargé. Les futurs
contrôles devront compter les tenseurs effectivement chargés, comme le lot précédent.

## Vérification locale ultérieure du même jour

Le pilote CPU vérifie les headers Vela4 : 4 211 182 082 éléments dans les
shards principaux, dont le biais scalaire `set_bias`, et 2 798 593 dans la tête
broad. Les métadonnées HF historiques ci-dessus omettent ce scalaire ; leur
export est conservé tel que relevé. Le worker vérifie aussi chaque nom et forme
des paramètres chargés. Voir [le protocole CPU](LARGER_CPU_PILOT_20261011.md).
