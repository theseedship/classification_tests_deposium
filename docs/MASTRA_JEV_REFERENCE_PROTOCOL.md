# Jev : référence API sur le corpus Mastra synthétique

Fixé le 2 octobre 2026, après les trois observations locales et avant les
réponses Jev de cette tâche. L'utilisateur autorise la comparaison avec Jev
sur **le même corpus**, tout en privilégiant un modèle local en production.
Cette passe établit une référence expérimentale ; elle ne propose aucune
intégration distante dans Deposium.

## Données et budget gelés

- Les mêmes 24 demandes synthétiques et trois options que dans les passes
  Indecis, Julia et GLiNER. Projection `mastra-read-choice/v1`, corpus
  `d66ec51d9b8d89f46b87b90b80bcd0d45abf1570fa9857c24d9ce39117935497`,
  requêtes `c076aedc2810c758d830c59bb21d404dcbad41df353f7df218950935381f7752`.
  Aucun texte privé ni annotation de référence n'est envoyé. Aucun changement
  de descriptions, prompts ou références à la lecture des résultats locaux.
- Profil existant `profiles/jev-api-context.json`, modèle demandé
  `jev-1.13.0`, endpoint/version/transport et budget contrôlés par
  l'[adaptateur existant](../deposium_bench/jev_http_adapter.py).
  Les identifiants de modèle ne constituent pas des hashes de poids distants.
- **24 tentatives maximum**, séquentielles, 30 s par requête et 300 s pour la
  passe, contrôle entre appels ; aucune répétition ou retry automatique.
  Les erreurs, réserves et requêtes non réalisées restent dans le bilan.
- Réutilisation obligatoire de `results/jev-pilot-budget-001.jsonl` : avant
  ce lot, **735/800 tentatives**, 733 règlements, deux réserves non réglées ;
  **1 314 405/2 000 000 tokens imputés**, réserves comprises.
  Reste : 65 tentatives et 685 595 tokens. Chaque tentative réserve 65 536
  tokens ; une réponse validée libère le surplus. Le budget peut donc arrêter
  la passe si des réserves restent pleines. Aucun nouveau journal, reset ou
  relèvement des plafonds.

Empreinte du journal avant la passe : 293 881 octets, SHA-256
`71178ad73edfdc67b17fe170c8f4374399dc5a2d380fc1b945a87ec46d1b14ea`.
Le bilan vérifiera que ce préfixe est conservé et rapprochera les nouvelles
réservations/règlements des tentatives réellement observées.

## Exécution et lecture

L'API exige `--allow-remote`, absent par défaut. La clé est chargée uniquement
dans `TYPESAFE_API_KEY` depuis le fichier local ignoré, sans valeur en argument,
sortie ou archive. Le corps transmis conserve contexte, question et descriptions
des trois options ; les IDs du banc sont remappés localement.

```bash
python3 -m deposium_bench observe-mastra-read \
  --allow-remote --profile profiles/jev-api-context.json \
  --stack-root ../deposium_fullstack --output results/mastra-read-jev-001
```

Le [protocole commun](MASTRA_INDECIS_OBSERVATION_PROTOCOL.md) décrit l'accord
aux propositions, couverture, splits et langues. Les références restent
`pending_human`, y compris si Jev les retrouve toutes. Jev n'est pas utilisé
comme annotateur de vérité. Les anciens scores Jev ne préjugent pas de cette
nouvelle observation.

Séparer durée côté adaptateur, durée HTTP mesurée (DNS/TLS/réseau/serveur) et
premier appel. Aucune durée interne d'inférence, RAM serveur, absence de
troncature ou exécution GPU n'est observable. Les tokens sont ceux déclarés
par le fournisseur, non comparables directement aux séquences des encodeurs
locaux. Conserver usage, modèle réellement déclaré, statuts, empreintes des
entrées/sorties et état du budget ; aucune estimation de gain produit.
