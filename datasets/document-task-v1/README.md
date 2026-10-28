# Projection documentaire du pilote Julia

Les 14 cas proviennent de `decisions-v1`, sans changer leurs entrées, identités,
familles ou splits. Seule l'assertion originale `/task` est conservée. Le manifeste
enregistre les hashes et distingue le noyau de 12 cas des deux suivis avec contexte.
Cette sélection et les deux prompts sont figés avant la première inférence.

Le noyau contient quatre cas par classe : `catalog`, `stored_summaries`,
`retrieve_answer`. Les deux suivis attendent `stored_summaries`. Les traductions
FR/EN forment sept familles corrélées. Dans le noyau, les quatre cas du split
`test` ne couvrent que deux familles de `retrieve_answer`; les deux suivis
ajoutent une famille `stored_summaries` à ce split (six cas au total).
Il manque donc la classe `catalog` dans le test. Tous les splits sont explorés,
sans tuning ni conclusion de généralisation multiclasses.

La revue par agent est dans `docs/CORPUS_REVIEW.md`; aucune revue humaine
n'est revendiquée. Les sorties complètes de plan, formats, droits, sources,
consentements et parcours produit ne sont pas évalués par cette projection.
Le benchmark refuse le profil Julia sur les assertions de plan complet.

Les deux candidats reçoivent exactement le même objet `input`. Celui-ci contient
parfois une intention amont ou un historique : leur succès est conditionnel à ces
informations. Le modèle ne reçoit ni identifiant de cas, ni split, ni annotation.
Les descriptions fixes des tâches sont une configuration publique du candidat;
elles ne contiennent aucune réponse propre à un cas.
