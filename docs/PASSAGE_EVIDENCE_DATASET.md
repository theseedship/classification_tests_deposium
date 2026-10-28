# Passages multilingues : classement et appui des affirmations

Lot du 15 octobre 2026. Jeu de données **synthétique exploratoire**, références
proposées par agent et revue humaine/linguistique non effectuée. Aucun modèle
n'est téléchargé ou appelé par sa génération, sa validation ou son export.
Ce lot ne modifie aucun service MCPs, TurboV3 ou inference.

## Questions à mesurer séparément

| Usage envisagé | Entrée identique entre candidats | Sortie à mesurer |
| --- | --- | --- |
| Remplacer le reranker | Question et pool ordonné de passages visibles | Classement complet, nDCG, rappel des preuves et rang de la première preuve |
| Compléter le reranker | Même question et un passage du pool | Pertinence directe/partielle/thématique/nulle, sans éliminer les contradictions utiles |
| Vérifier la réponse | Affirmation candidate et passage réellement visible | Appui, réfutation ou information insuffisante ; présence du même chiffre seule insuffisante |
| Décider de répondre | Question et ensemble des passages visibles | Réponse possible, preuves insuffisantes ou preuves contradictoires |

Un modèle à choix de type JEV et un cross-encoder n'ont pas nécessairement la
même sortie. Le premier peut classifier chaque paire ou sélectionner une action ;
le second peut noter puis classer les passages. Le corpus est commun, les
projections et les métriques demeurent explicites. Une bonne classification de
passage ne démontre pas une meilleure réponse finale.

## Contenu et langues

Le pack [passage-evidence-v1](../datasets/passage-evidence-v1/README.md) couvre
FR, EN, DE, ES, IT et PT. Il contient les six directions monolingues et les deux
directions croisées FR→EN / EN→FR. Il ne couvre donc pas toutes les paires entre
ces six langues, ni les pools mélangeant plusieurs langues.

Les incidents de recette motivent des propriétés, sans recopier leurs documents :
même valeur attribuée à une autre pièce ; même objet mais autre réglage ; variante
de produit voisine ; unité, condition, négation et exception ; preuves réparties ;
absence dans les seuls extraits visibles ; désaccord entre sources. Les entités,
documents et valeurs sont inventés. Aucun PDF privé, identifiant de fichier réel,
tenant, capture de production ou secret n'entre dans ce pack.

Chaque famille conserve ses traductions, variantes d'ordre et fenêtres dans un
seul split. Quatre rotations du pool placent chaque passage aux quatre positions.
Elles servent à mesurer la sensibilité à l'ordre, pas à multiplier le nombre de
faits indépendants. Les opérations et certains gabarits sont partagés entre
familles : ce pack n'est pas un test de généralisation à tout domaine nouveau.

Les vues `full` et `head_384` doivent être comparées séparément. La seconde
contient exactement le début du passage, au plus 384 caractères Unicode Python.
Ce n'est **ni une fenêtre de tokens, ni le sélecteur de fenêtre MCPs**. Elle
permet de mesurer la perte de preuve par troncature sans importer son annotation
dans le texte visible. Les labels sont établis sur la vue réellement transmise.

## Références et export sans annotations

Les cas canoniques séparent passages et `annotations` : pertinence graduée,
état de réponse, ensembles de preuves suffisants et appui d'affirmations.
Une réfutation peut avoir une pertinence élevée. Une preuve partielle peut
nécessiter une autre source. Un manque dans le pool ne devient jamais une
assertion d'absence dans le corpus complet.

L'export vers le modèle utilise une liste de champs autorisés. Les annotations,
justifications, spans de référence, splits, noms de scénarios, familles et grades
ne sont pas fournis au candidat. Les identifiants des passages sont opaques.
La vérification des spans contrôle le texte exact et les bornes dans la vue
visible ; elle ne constitue pas une revue sémantique ou linguistique humaine.

Les projections de choix réutilisent `deposium_bench.choice_protocol`. Elles
conservent le contrat candidat `bench.context-choice` et restent exploitables
par ses adaptateurs. Elles ne sont **pas** de nouveaux cas du corpus v2 figé :
son oracle connaît explicitement les 132 bases historiques. Le nouveau pack a
son propre schéma et son validateur additionnel ; les campagnes, corpus et
oracles historiques restent inchangés.

## Protocole de comparaison proposé

1. Valider et figer le corpus, son hash et les projections avant toute mesure.
   Faire revoir les références et les traductions ; conserver les désaccords.
2. Fixer les profils des candidats : révision, tokenizer, quantification, runtime,
   device effectif, paramètres, prompt et politique de dépassement de longueur.
3. Comparer le reranker actuel et le candidat sur les **mêmes textes visibles**,
   même pool et mêmes fenêtres. Ne pas attribuer un gain de traduction ou de
   rappel initial au seul modèle de classement.
4. Mesurer séparément le complément : classement actuel seul, puis même
   classement avec classification des passages. Fixer la composition et les
   seuils sur train/calibration ; conserver le test hors réglage. Ne pas
   supprimer automatiquement une contradiction parce qu'elle réfute une réponse.
5. Publier les scores par direction de langue, scénario, vue et split, avec
   couverture, erreurs, délais et non-supportés. Les groupes sans preuve utile
   ont des métriques de classement non définies ; ils demandent les décisions
   d'insuffisance ou de conflit plutôt qu'un faux score parfait.
6. Mesurer à part chargement, latence par paire et pool, RAM/VRAM, coût et qualité
   de la réponse finale. Les répétitions/traductions appartiennent à leur famille
   pour toute estimation d'incertitude. Ne pas additionner les variantes comme
   des observations indépendantes.

L'essai à quatre passages historiques exécuté côté MCPs le 15 octobre est un
signal de défaut, pas le gold de ce pack. La séparation question originale /
expansion lexicale n'a pas démontré de gain anglais sur cet essai CPU. Ce jeu
ne doit pas être ajusté après coup pour faire gagner cette modification.

## Raccordement à Deposium

Décisions du registre concernées : `mcps.passage-reranking` et
`turbov3.embedding-rerank-profile`, ainsi que le contrat de stack
`mcps.evidence-attribution` pour l'appui d'affirmations. Le préflight existant
continue de recenser toute la stack ; ces liens ne qualifient pas ses autres
composants. Les sources de référence doivent être réévaluées avant une campagne
d'intégration.

Chemin relu dans la branche MCPs `a6f893021683f4ab5442e49c80be339511e14ec1` :
`src/tools/search.ts` choisit les fenêtres, puis appelle
`src/services/turbov2-resilient.ts::rerankDocuments`, qui envoie `/api/rerank` au
service Turbo configuré. Le nom historique `TurboV2` du client ne constitue pas
une autre implémentation de modèle dans MCPs. Le classement de passages et la
génération de texte demeurent des contrats distincts.

Les niveaux restent ceux du [local-only material, not distributed](PROTOCOL.md) :
ce pack prépare le niveau A. Le niveau B exigera un adaptateur vers le vrai
composant et ses guards ; le niveau C exigera une réponse finale et des citations
observées. Aucun remplacement applicatif ou entraînement n'est décidé par ce lot.

## Vérifications de livraison

Base du banc : `origin/main` à `e7fddcb`, dans un worktree isolé. Le checkout
canonique JEV et les branches des campagnes précédentes sont conservés. Les
sources et données applicatives ne font pas partie du diff.

Référence gelée : 1 536 cas / 24 familles / 2 304 affirmations / 9 216 jugements
de soutien, SHA-256
`35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476`.
La régénération retrouve les mêmes octets. Relecture indépendante : aucune
référence divergente pour une même entrée candidat, aucun document ni famille
à cheval sur les splits, 96 contrôles tronqués sans preuve ni pertinence
héritée des faits cachés. Ce sont des contrôles de cohérence, pas une revue humaine.

Les 15 tests ciblés passent avec le Python hôte. Les contrôles volontairement
faux montrent le rouge : classement inversé, nDCG@1 de 1 à 0 ; choix de soutien
erronés, taux de réussite de 1 à 0 ; prédictions absentes, couverture 0. Ils
utilisent les références synthétiques et ne représentent aucun score de modèle.
L'exemple calibration EN→FR exporte 32 requêtes de classement et 192 requêtes
de soutien sans inférence. Les registres de stack et de décisions restent valides.

```text
python3 -B -m unittest tests.test_passage_dataset -q
Ran 15 tests — OK

python3 -S -B -m unittest discover -s tests -q
Ran 531 tests — OK (skipped=35)
```

La deuxième commande vérifie le socle sans paquets de site : 496 succès et
35 contrôles optionnels omis. Avant ce lot, la même suite comptait 516 tests
et les mêmes 35 omissions. Avec les paquets hôte, la baseline présentait déjà
19 erreurs de résolution de schéma avec `jsonschema 4.10.3` (identifiants URI
`deposium.*`), plus six skips. Ces erreurs historiques ne sont pas corrigées ni
comptées comme des succès par le lot. Aucun paquet global n'a été modifié.

GitNexus ne dispose pas d'index pour ce dépôt du banc : `detect_changes` a
signalé le dépôt inconnu. Aucun résultat d'impact de l'index MCPs n'est présenté
comme preuve sur JEV. Le diff ajoute deux modules du banc, leur schéma et leurs
tests, les données et cette documentation ; il ne modifie aucun symbole applicatif
ni les oracles/corpus historiques. La suite et la revue de diff bornent ce périmètre.

## Message de reprise pour un agent de campagne

> Lis AGENTS.md, docs/PASSAGE_EVIDENCE_DATASET.md et
> datasets/passage-evidence-v1/README.md. Valide le pack sans modèle. Vérifie le
> hash du corpus et conserve les anciennes archives. Prépare une campagne bornée
> comparant le reranker de référence à un candidat explicitement choisi, puis
> séparément à une composition avec un modèle à choix. Déclare les profils,
> projections, ressources et métriques avant inférence. Ne modifie ni les labels
> pour améliorer un score, ni les services actifs. Les appels externes et l'envoi
> de données privées ne sont pas autorisés par la seule présence d'un profil.
> Conserve missing/error/timeout/unsupported, les métriques non définies et les
> limites de revue. Rapporte un résultat par tâche et par groupe de langue, sans
> verdict de qualité produit avant les essais B/C.
