# ImaJEV-4B : piste pour les décisions avec images

Veille du 5 octobre 2026. **Non exécuté dans Deposium** : aucun téléchargement
de poids, adaptateur du banc, service ou nouveau corpus dans ce lot.
Cette note complète le [registre des candidats](NEXT_CANDIDATES.md), sans
modifier le [local-only material, not distributed](PROTOCOL.md).

## Identités à conserver séparément

| Élément | Révision observée |
|---|---|
| [Dépôt HF ImaJEV-4B](https://huggingface.co/mohit67890/imajev-4b/tree/f8d8234cebc6c99065c07731e59716dc0a6e27ab) | `f8d8234cebc6c99065c07731e59716dc0a6e27ab` |
| [Code natif](https://github.com/mohit67890/imajev/tree/ccf586d43d2a580319b6535c893668904d909eb9) | `ccf586d43d2a580319b6535c893668904d909eb9` |
| Base Qwen/Qwen3.5-4B déclarée dans l'adaptateur | `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` |

Le [config PEFT](https://huggingface.co/mohit67890/imajev-4b/blob/f8d8234cebc6c99065c07731e59716dc0a6e27ab/adapter_config.json)
contient un chemin de cache propre à l'auteur. Le futur chargement devra résoudre
la base locale à sa révision, sans dépendre de ce chemin, et archiver les hashes
de la base, du LoRA, de la tête, du processeur et de la calibration utilisés.
Licence annoncée : Apache-2.0 ; conserver aussi celle de la base et les droits
des images choisies.

## Ce que fournit le modèle

La [fiche HF épinglée](https://huggingface.co/mohit67890/imajev-4b/blob/f8d8234cebc6c99065c07731e59716dc0a6e27ab/README.md)
décrit des décisions `choice`, `noul` et `score` à partir de texte, d'une image
ou de deux images. L'API locale reprend `/v1/systemone` et ajoute des informations
d'abstention. Il s'agit d'un projet distinct de TypeSafe Jev.

La [spécification de release](https://huggingface.co/mohit67890/imajev-4b/blob/f8d8234cebc6c99065c07731e59716dc0a6e27ab/RELEASE-SPEC.md)
décrit un LoRA de rang 64 et une tête de 256 codes, dont `unknown`, sur la base
Qwen3.5-4B. Le dépôt HF contient l'adaptateur et la tête, **pas la base complète**.
Le futur pilote doit appeler le backend natif et son scoring, sans remplacer
la tête par `generate()` ni recopier les algorithmes du serveur.

Le [contrat API](https://github.com/mohit67890/imajev/blob/ccf586d43d2a580319b6535c893668904d909eb9/src/vision_decision/jev_api.py)
renormalise les probabilités `choice` sur les choix connus, en excluant la masse
`unknown`. Il conserve un meilleur choix connu **même lorsque `abstained=true`**.
L'adaptateur devra donc lire l'abstention explicite avant de scorer ou proposer
une action. Dans le [scorer](https://github.com/mohit67890/imajev/blob/ccf586d43d2a580319b6535c893668904d909eb9/src/vision_decision/scoring.py),
`unknown` gagnant déclenche l'abstention ; ce n'est pas un seuil de confiance.

## Limites et ressources à vérifier avant exécution

La fiche annonce l'anglais, jusqu'à deux images redimensionnées à 400 000 pixels,
32 KB de state, 1–8 questions et un budget de service de 4 096 tokens. Ce sont
des limites distinctes : octets, tokens et pixels ne sont pas interchangeables.
Archiver les images avant/après préparation, la taille du prompt complet et le
budget effectivement appliqué. Une réduction de résolution peut rendre une
formule ou une légende illisible ; elle doit rester visible dans les résultats.

La release distingue le service ordinaire d'une campagne DecisionBench avec
une limite portée à 64k. **Ne pas qualifier une fenêtre de 64k à partir de ce
résultat.** Le README GitHub et la release HF décrivent aussi des générations
d'adaptateurs différentes ; vérifier le contrat effectif du code et des fichiers
retenus avant d'annoncer le nombre maximal de choix ou une compatibilité.

Le [serveur épinglé](https://github.com/mohit67890/imajev/blob/ccf586d43d2a580319b6535c893668904d909eb9/scripts/playground/server.py)
fixe par défaut 4 096 tokens, un ordre de choix et aucune calibration.
Le chemin PyTorch direct effectue un forward par question et rotation ; les
quatre rotations de certains résultats publics augmentent donc le travail.
Le backend MLX peut partager la préparation du préfixe. Archiver ces réglages
avant de comparer leurs durées.

La base 4B en BF16 représente un ordre de grandeur de 8 Go de paramètres,
avant LoRA, vision, activations et runtime. Cette estimation ne constitue ni
une mesure de RAM/RSS ni une preuve que la configuration tient sur le GPU local.
Le serveur PyTorch choisit FP32 sur CPU, soit un ordre de grandeur de 16 Go de
paramètres de base avant surcoûts ; il charge toujours le modèle complet.
PyTorch et MLX sont des configurations à conserver séparément. Aucun temps
CPU/GPU, mémoire ou besoin de quantification n'est mesuré ici.

L'abstention apprise et une température de calibration ne garantissent pas
la justesse sur nos données. La release déclare un contrôle `unknown-gold`
non satisfait et une dérogation de publication. Vérifier les rapports bruts
avant de reprendre ses comptes ; ne pas transformer une confiance en référence.
Les classements et scores publics restent des résultats externes, sans
reproduction ni qualification Deposium dans ce lot.

## Hypothèses de cas d'usage, à confirmer

| Famille proposée | Question courte avec choix explicites | Référence à préparer |
|---|---|---|
| Page documentaire et graphique | Le graphique soutient-il la conclusion proposée ? | Page/version, axes, unités et annotations relues |
| Formule ou schéma mathématique | Quel complément est cohérent avec les contraintes visibles ? | Solution justifiée, image lisible ; complexité identifiée |
| Figure ou schéma chimique | Quel libellé correspond à la figure fournie ? | Annotation spécialisée ; ambiguïtés et informations absentes explicites |
| Capture ou tableau | L'image contredit-elle un champ structuré donné ? | Champ exact et preuve visuelle vérifiés |
| Deux images | Quelle différence vérifiable distingue référence et cible ? | Paire liée, annotation et cas réellement indécidables |

Ces propositions n'établissent aucun besoin produit déjà confirmé. Pour les
cas documentaires, réutiliser les vrais services MCPs de lecture et de provenance
afin d'obtenir les pages autorisées ; ne pas reconstituer leurs algorithmes.
Rattacher chaque futur cas aux composants concernés et aux sources/images
effectivement exécutées selon [local-only material, not distributed](PROTOCOL.md).

## Pilote futur et critères de comparaison

1. Figer un petit panel EN relu avant toute inférence, avec choix d'action
   courts, cas répondables et cas sans preuve suffisante. Ajouter FR comme
   exploration séparée ; garder les familles de traduction ensemble au split.
2. Séparer images synthétiques contrôlées et vraies pages documentaires privées.
   Grouper les splits par document, paire et scénario ; aucune annotation de
   référence, nom de fichier révélateur ou réponse attendue dans l'entrée.
3. Comparer ImaJEV au Qwen de base sur les mêmes images, et à une chaîne
   OCR/extraction puis décision textuelle lorsque cela a du sens. Jev ou Eos
   recevant l'extraction constituent une chaîne différente, à mesurer comme telle.
4. Tester l'image correcte, absente et remplacée pour vérifier si le modèle
   utilise la preuve visuelle. Mesurer séparément un ordre de choix et quatre
   rotations, calibration désactivée/figée, sans ajustement sur le test.
5. Publier précision et couverture avec dénominateurs, erreurs, dépassements,
   abstentions justifiées et fausses abstentions. Vérifier que les scorers
   rejettent les réponses vides et fausses ; `unknown` n'est pas un PASS générique.
6. Relever chargement, préparation d'image, tokens texte/vision observables,
   forward, rotations, durée totale, médiane/p95, RSS et VRAM. Fixer les gardes
   avant campagne, un modèle à la fois ; garder les mesures absentes `unobserved`.

Poids, images, corpus, annotations et sorties brutes restent hors Git ; publier
uniquement des agrégats et manifestes sans données privées. Un score de modèle
isolé ne qualifie ni le routage intégré ni la qualité des réponses finales du
CLI/chat. L'intégration produit et toute campagne API constituent des étapes
ultérieures distinctes.
