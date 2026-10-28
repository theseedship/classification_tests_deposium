# Sorties de contrôle du banc

`control-responses.jsonl` contient des prédictions synthétiques écrites à la main,
indépendamment des annotations du corpus. Ce fichier n'est ni un export d'un
modèle, ni une référence de vérité. Il permet d'exécuter le banc sans stack ou
inférence et de comparer CLI/notebook sur les mêmes sorties figées.

Il inclut volontairement des plans incorrects, une réponse vide et les états
`error`, `timeout`, `unsupported`, `missing` et `abstain`. La campagne de contrôle
doit donc produire un verdict d'échec avec une couverture partielle. Ne pas
modifier ces sorties pour afficher un score entièrement vert.

Les références et justifications sont dans `datasets/decisions-v1/cases.jsonl`.
L'adaptateur ne les reçoit jamais : il cherche uniquement l'identifiant demandé
dans ce fichier indépendant. Ce mécanisme ne mesure aucune capacité prédictive.
