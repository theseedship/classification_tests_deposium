# Comparaison locale des choix Mastra : protocole complémentaire

Fixé le 2 octobre 2026, après observation des 24 choix Indecis, mais avant
toute prédiction Julia ou GLiNER sur cette tâche. La demande utilisateur
privilégie les candidats locaux pour préserver la confidentialité ; Jev
reste une comparaison ultérieure, éventuellement sur demandes synthétiques.
Aucun appel distant n'est inclus dans ce lot.

Le [protocole Indecis](MASTRA_INDECIS_OBSERVATION_PROTOCOL.md) s'applique au
corpus, à la projection commune v1, à l'interprétation provisoire et aux
mesures. Les requêtes doivent rester strictement identiques à celles de
`results/mastra-read-indecis-002` : SHA-256
`c076aedc2810c758d830c59bb21d404dcbad41df353f7df218950935381f7752`.
Aucun prompt, label ou cas n'est modifié à la lecture du résultat Indecis.

Deux passes supplémentaires, séquentielles, avec poids/runtimes déjà locaux :

| Candidat | Profil existant | Archive nouvelle | Budget |
|---|---|---|---|
| Julia-1 | `profiles/julia-1-cpu-context.json` | `results/mastra-read-julia-001` | 24 appels, 300 s |
| GLiNER2.5-multi-Decide | `profiles/gliner-multi-cpu-context.json` | `results/mastra-read-gliner-001` | 24 appels, 300 s |

Chaque passe utilise un worker, deux threads CPU et une garde RSS de
3 072 Mio ; délai de 30 s par demande, mémoire disponible minimale de
4 Gio avant initialisation, arrêt des nouveaux appels sous 1 Gio. Les
révisions, verrous runtime et manifests des profils historiques restent
exigés. Aucun téléchargement ou entraînement. Aucun échauffement, répétition
ou recherche d'hyperparamètres ; 48 nouvelles décisions au maximum.

Les sérialisations natives restent celles des adaptateurs existants : mêmes
textes de contexte/question/options, mais architecture et encodage propres à
chaque modèle. Les budgets natifs de 8 192 tokens pour Julia et 4 096 pour
GLiNER ne sont pas des longueurs éprouvées ici. Rapporter les tokens natifs
effectifs et les éventuelles limites, sans les rendre artificiellement égaux.

Rapporter tous les statuts et la couverture, l'accord aux propositions par
action/langue/split, le repli et les erreurs représentatives. Comparer les
temps côté adaptateur hors chargement, puis distinguer premier appel,
suivants, initialisation et RSS. Les temps internes n'ont pas nécessairement
le même périmètre entre modèles. Aucune extrapolation de gain LLM ou produit.
Si une garde intervient, conserver l'échec et les dénominateurs : aucun
relèvement de ressources pour compléter la comparaison.

```bash
python3 -m deposium_bench observe-mastra-read \
  --profile profiles/julia-1-cpu-context.json \
  --stack-root ../deposium_fullstack --output results/mastra-read-julia-001
python3 -m deposium_bench observe-mastra-read \
  --profile profiles/gliner-multi-cpu-context.json \
  --stack-root ../deposium_fullstack --output results/mastra-read-gliner-001
```

Les références sont toujours `pending_human`. Le meilleur accord de ce petit
lot ne suffit pas à choisir un modèle de production ni à valider un repli.
