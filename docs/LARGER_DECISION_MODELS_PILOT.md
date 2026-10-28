# Montée en taille sur Mac 64 Go : candidats vérifiés

**Mise à jour du 16 octobre 2026 :** les campagnes Eos, D3 Flash 9B Q8/Q4 et
D3 27B Q4 sont maintenant terminées. Voir les
[résultats réels et leurs limites](NATIVE_DECISION_RESULTS_20261016.md) et le
[protocole natif](NATIVE_SYSTEMONE_PILOT.md). Le 27B Q8 reste non exécuté.
La veille ci-dessous conserve l'état et la sélection antérieurs aux campagnes.

Lecture des sources publiques au **15 octobre 2026**. Ce document prépare le
prochain lot ; aucun nouveau modèle téléchargé ni campagne exécutée par cette
veille. Les [local-only material, not distributed](PROTOCOL.md) restent
conservés. Eos/Kai mesurés appartiennent à Decision 2.0 ; **D3 n'a pas encore de
résultat Deposium**. Noma conserve le meilleur score local global historique,
98/132, et Eos 19/24 accords Mastra provisoires.

## Séries et progression

| Série déjà présente dans le banc | Variantes plus grandes ou plus récentes vérifiées | Priorité proposée |
| --- | --- | --- |
| Decision 2.0, Kai 0.6B / Eos 0.8B | Sol 2B, Nox 4B, Lux 9B, Vega 27B | Lux, puis Vega comme témoins de génération précédente |
| Decision 3.0, génération suivante | d3-edge, d3-lite, d3-nano, d3-mini, d3-flash classe 9B, d3 classe 27B | d3-flash, puis d3 ; nano/mini peuvent compléter une étude d'échelle |
| LiquidAI d1-omni-600M | d1-3B | Comparateur d'une autre architecture après D3 |
| Noma, environ 2.67B | Aucun checkpoint Noma plus grand identifié dans l'organisation officielle à cette date | Conserver le résultat historique comme référence ; pas de variante inventée |
| ModernJEV-Decide-Preview | Seul ce checkpoint retrouvé dans la recherche HF ModernJEV | Pas de montée 9B/27B identifiée dans cette série |
| Julia, Laya, GLiNER, Muose, Indecis | Le lot ne leur attribue aucune variante 9B/27B | Garder ces comparateurs ; un autre backbone/helper constitue un nouveau candidat à qualifier |
| Jev API historique | Identité du modèle serveur, poids et mémoire non observés localement | Conserver l'archive ; aucun nouvel appel API dans ce lot |

Sources primaires : [Decision 2.0 / Lux](https://huggingface.co/vllm-sr/Decision-2.0-Lux-9B),
[Vega](https://huggingface.co/vllm-sr/Decision-2.0-Vega-27B),
[collection D3](https://huggingface.co/collections/vllm-sr/decision-30),
[d3-flash](https://huggingface.co/vllm-sr/d3-flash),
[d3](https://huggingface.co/vllm-sr/d3),
[d1-3B](https://huggingface.co/LiquidAI/d1-3B),
[organisation Noma](https://huggingface.co/BlackdromeAILabs),
[ModernJEV](https://huggingface.co/MaziyarPanahi/ModernJEV-Decide-Preview).

Les classes 9B/27B sont les noms de gamme. Les fiches D3 courantes indiquent
respectivement 8.39B et 26.09B paramètres, encodeur vision inclus. Leurs résultats
publics servent à sélectionner les candidats ; ils ne prédisent pas nos scores
FR/EN ou ceux des GGUF épinglés ci-dessous.

## Fichiers Q8 texte sélectionnés, non téléchargés

| Candidat | Dépôt GGUF et révision | Fichier | Octets / Go décimaux |
| --- | --- | --- | --- |
| d3-flash | `ggml-org/vllm-d3-flash-GGUF` à `3d53d13778bf8035e6e1e534ce489ed052ee5663` | `vllm-d3-flash-Q8_0.gguf` | 9 527 503 296 / 9.53 |
| d3 | `ggml-org/vllm-d3-GGUF` à `de9670136f5ddd83e677c89ce041d5b9bb3b0dcb` | `vllm-d3-Q8_0.gguf` | 28 595 765 472 / 28.60 |

SHA-256 attendus, publiés dans les métadonnées LFS à ces révisions :

- d3-flash : `7352edf6be85d93ab8806a17e1b3d0a7e71ee3685af3212ddbe679b742c2221b`.
- d3 : `82130d83cb6f31d43a742a08f737a78c087e408776115b6f28e5d3bc27617805`.

Sources : [fichiers Flash épinglés](https://huggingface.co/ggml-org/vllm-d3-flash-GGUF/tree/3d53d13778bf8035e6e1e534ce489ed052ee5663)
et [fichiers d3 épinglés](https://huggingface.co/ggml-org/vllm-d3-GGUF/tree/de9670136f5ddd83e677c89ce041d5b9bb3b0dcb).
Le `.src_sha` Flash indique le modèle source `f6075bff3c0f7d5704e353d0fb2ebf94888d1691` ;
il diffère du HEAD HF courant `8b35c853b90e777595ec36bacae820fe08ea077a`.
Ne pas assimiler une nouvelle fiche à une identité de poids vérifiée.

Ces volumes rendent des essais séquentiels Q8 plausibles avec 64 Go unifiés ;
ils ne mesurent ni le pic mémoire ni la longueur tenable. Commencer en texte
seul, contexte 4096, sans projecteur vision et un modèle à la fois. Le Q4 est
une variante ultérieure dont la perte de qualité doit être mesurée séparément.

## Prérequis d'exécution et ordre du lot

Le support D3 a été fusionné dans llama.cpp officiel le 12 octobre :
[PR #30383](https://github.com/ggml-org/llama.cpp/pull/30383), commit de fusion
`efe3626b119ff81033e309c3ba07a770bef2c546`. Le pin local Decision 2.0 testé
`3c64a581d4f95bb2de409d383741fa5b18d84345` n'est pas une qualification D3.
Conserver cet artefact et sélectionner explicitement une seconde révision
officielle couvrant D3, avec build Metal et voie Linux CPU/CUDA commune. Aucun
changement du runtime Docker/Railway dans ce lot de préparation.

1. Qualifier ce second runtime sur un contrôle synthétique D3, avec preuve
   d'identité, absence de troncature et traces Metal. Conserver un seul appel
   et une question par forward pour ce premier lot ; vérifier notamment les
   contraintes de batch complet de la tête native. Ne pas déduire le support
   D3 d'une réponse `/health` ou du seul nom d'un tag llama.cpp.
2. Raccorder `/v1/systemone` au moteur CLI/notebook commun du banc, sans copie
   du routage ni du scorer natif du modèle. Mapper les choix ordinaux, garder
   annotations et références hors requête, vérifier les refus et sorties vides.
3. Refaire une baseline Eos GGUF, puis d3-flash Q8 sur les mêmes 132 bases et
   24 propositions Mastra. Versions, quantification et changement de runtime
   restent explicites face aux campagnes historiques PyTorch CPU.
4. Passer à d3 27B Q8 si le chargement et la garde mémoire du premier palier
   sont satisfaisants. Exécuter Lux/Vega pour isoler l'intérêt de la génération
   D3 ; ajouter d1-3B comme comparateur indépendant.

Les corpus, oracles, split et familles FR/EN restent ceux du
[local-only material, not distributed](PROTOCOL.md). Archiver sorties natives,
empreintes, couverture/statuts, domaine/langue, chargement et temps des appels.
Les latences CPU WSL et Metal Mac ne mesurent pas à elles seules un effet de
taille. Les contextes longs, répétitions, médias et parcours produit demandent
des lots distincts. Jusqu'à exécution : modèles proposés `not_run`, mémoire et
qualité `not_observed`, zéro cas scoré par ce lot.
