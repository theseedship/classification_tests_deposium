# Comparatif des quatorze modèles — 11 octobre 2026

**Vela 0.8B obtient 79/132 (59,8 %) sur les bases, contre 77/132 pour Eos.** Ce faible écart ne suffit pas à établir un avantage stable. Il reste derrière Jev, Noma et Sol, et son accord de routage est inférieur à Eos : **14/24 contre 19/24**. Vela 0.3B obtient **65/132, 18/24**, avec une médiane de 171 ms sur les bases et 1,17 Gio de RSS observé. Les maths restent son point faible : 4/28.

Les mêmes 132 cas contiennent **66 familles de scénarios FR/EN**, dont 76 cas documentaires, 28 mathématiques et 28 chimiques. Les références sont `agent_only_pending_human`. Les 24 propositions Mastra restent `pending_human` : **zéro cas humainement qualifié**, aucun outil exécuté. Il ne s’agit ni de récupération documentaire sur le corpus privé ni de qualité des réponses finales.

Le [rapport recalculé à treize modèles](evidence/model-comparison-vela2-20261011/report.md) et son [JSON agrégé](evidence/model-comparison-vela2-20261011/analysis.json) vérifient 26 archives scellées. **Sol reste sur sa branche distincte** : ses chiffres proviennent du [rapport historique à douze modèles](evidence/model-comparison-complete-20261010-sol/report.md) et du [JSON conservé à l’identique](evidence/model-comparison-complete-20261010-sol/analysis.json), commit `2f64e1931652fe9faad784ffc6c54abc12b988b5`. Les deux archives Sol ont été revérifiées contre ces empreintes et les hashes des corpus correspondent. Son code n’est pas intégré à ce lot. Ces tableaux réunissent donc quatorze modèles sans relancer les douze candidats historiques.

## Choix sur les bases

132/132 réponses valides et scorées par modèle. Classement par nombre de choix corrects ; les assertions synthétiques ne sont pas une qualification produit.

| Modèle | Corrects /132 | % | Documentaire /76 | Maths /28 | Chimie /28 | FR /66 | EN /66 | Test /66 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Jev | 123 | 93,2 | 67 | 28 | 28 | 62 | 61 | 62 |
| Noma | 98 | 74,2 | 53 | 25 | 20 | 46 | 52 | 51 |
| Sol | 93 | 70,5 | 62 | 19 | 12 | 46 | 47 | 47 |
| Vela 0.8B | 79 | 59,8 | 56 | 11 | 12 | 38 | 41 | 45 |
| Eos | 77 | 58,3 | 55 | 12 | 10 | 39 | 38 | 40 |
| Kai | 70 | 53,0 | 56 | 7 | 7 | 34 | 36 | 36 |
| Vela 0.3B | 65 | 49,2 | 52 | 4 | 9 | 33 | 32 | 37 |
| GLiNER | 59 | 44,7 | 41 | 5 | 13 | 28 | 31 | 38 |
| Laya | 56 | 42,4 | 42 | 8 | 6 | 32 | 24 | 30 |
| Julia | 52 | 39,4 | 32 | 8 | 12 | 25 | 27 | 26 |
| Omni | 51 | 38,6 | 39 | 4 | 8 | 19 | 32 | 26 |
| Indecis | 44 | 33,3 | 32 | 2 | 10 | 21 | 23 | 22 |
| ModernJEV | 42 | 31,8 | 23 | 13 | 6 | 24 | 18 | 23 |
| Muose | 41 | 31,1 | 30 | 6 | 5 | 19 | 22 | 21 |

## Routage : accords provisoires

Ordre distinct, par accord sur 24. Chaque action proposée compte huit cas ; les langues comptent douze cas chacune. Le repli est une sélection d’option, sans preuve d’abstention ni d’exécution des gardes produit.

| Modèle | Accord /24 | Recherche /8 | Statistiques /8 | Repli /8 | FR /12 | EN /12 |
|---|---:|---:|---:|---:|---:|---:|
| Jev | 20 | 8 | 8 | 4 | 9 | 11 |
| Eos | 19 | 7 | 8 | 4 | 10 | 9 |
| Sol | 19 | 7 | 8 | 4 | 10 | 9 |
| Noma | 18 | 8 | 8 | 2 | 9 | 9 |
| Vela 0.3B | 18 | 8 | 7 | 3 | 11 | 7 |
| Kai | 16 | 6 | 8 | 2 | 8 | 8 |
| Omni | 16 | 7 | 8 | 1 | 7 | 9 |
| Vela 0.8B | 14 | 7 | 7 | 0 | 7 | 7 |
| GLiNER | 12 | 8 | 4 | 0 | 8 | 4 |
| Indecis | 11 | 5 | 6 | 0 | 5 | 6 |
| Julia | 11 | 6 | 4 | 1 | 5 | 6 |
| Laya | 10 | 8 | 0 | 2 | 5 | 5 |
| Muose | 10 | 6 | 4 | 0 | 5 | 5 |
| ModernJEV | 8 | 4 | 4 | 0 | 4 | 4 |

## RAM et temps de réponse

RSS maximale rapportée par le worker, en Gio, avec 132/132 relevés sur les bases et 24/24 sur le routage pour chaque modèle local. Ce pic du processus peut inclure le chargement et n’est pas une mesure de RAM totale, une réservation minimale ou une mesure GPU. RAM distante Jev non observée. Latence adaptateur des réponses `ok`, hors initialisation ; Jev inclut HTTPS. Une passe par corpus, à des dates et avec des runtimes différents : médianes et p95 descriptifs, sans garantie de production.

| Modèle | RSS bases Gio | RSS routage Gio | Bases médiane / p95 ms | Routage médiane / p95 ms |
|---|---:|---:|---:|---:|
| Jev | Non observé | Non observé | 280,5 / 323,3 | 288,0 / 355,3 |
| Noma | 4,82 | 4,62 | 4206,3 / 5157,5 | 5259,6 / 6117,8 |
| Sol | 8,32 | 8,29 | 3471,9 / 6403,8 | 4658,7 / 6204,2 |
| Vela 0.8B | 5,13 | 5,13 | 1573,4 / 1849,3 | 1925,5 / 2061,8 |
| Eos | 3,44 | 3,39 | 1122,6 / 1379,7 | 1419,9 / 1754,2 |
| Kai | 3,01 | 2,96 | 1220,8 / 2227,8 | 1400,6 / 2101,0 |
| Vela 0.3B | 1,17 | 1,14 | 171,2 / 252,0 | 239,8 / 329,4 |
| GLiNER | 2,82 | 2,82 | 234,9 / 401,0 | 391,9 / 582,6 |
| Laya | 2,27 | 2,27 | 168,9 / 219,7 | 267,4 / 375,1 |
| Julia | 0,97 | 1,00 | 59,0 / 83,2 | 100,2 / 146,6 |
| Omni | 1,67 | 1,64 | 438,4 / 648,0 | 642,9 / 1219,9 |
| Indecis | 1,10 | 0,87 | 34,8 / 43,0 | 44,7 / 57,0 |
| ModernJEV | 0,86 | 0,83 | 668,1 / 1142,4 | 837,9 / 1040,0 |
| Muose | 0,61 | 0,61 | 308,0 / 748,1 | 469,1 / 675,9 |

Vela : CPU Intel Core Ultra 5 235HX, WSL2, FP32, deux threads, un seul worker à la fois. Chargement .3B via HF `AutoModel` local puis moteur natif ; .8B via le décodeur natif. Les modes sont conservés dans les JSON. Le [protocole](VELA2_PILOT.md) conserve les essais initiaux échoués et leurs corrections avant campagne.

## Taille des entrées

Min / médiane / max en tokens natifs. Les séquences complètes incluent instructions, contexte, options et schéma natif. Les tokenizers diffèrent : ces comptes ne définissent pas une longueur commune. La somme distingue les moteurs répétant le contexte par option. Le texte commun, padding et ventilations domaine × langue figurent dans les rapports détaillés.

| Modèle | Séquence max : bases | Séquence max : routage | Somme : bases | Somme : routage |
|---|---:|---:|---:|---:|
| Jev | Non observé | Non observé | Non observé | Non observé |
| Noma | 79 / 116 / 161 | 153 / 183 / 216 | 79 / 116 / 161 | 153 / 183 / 216 |
| Sol | 131 / 164,5 / 210 | 190 / 217 / 254 | 131 / 164,5 / 210 | 190 / 217 / 254 |
| Vela 0.8B | 171 / 204,5 / 250 | 230 / 257 / 294 | 171 / 204,5 / 250 | 230 / 257 / 294 |
| Eos | 131 / 164,5 / 210 | 190 / 217 / 254 | 131 / 164,5 / 210 | 190 / 217 / 254 |
| Kai | 118 / 154 / 201 | 177 / 214,5 / 262 | 118 / 154 / 201 | 177 / 214,5 / 262 |
| Vela 0.3B | 56 / 89 / 134 | 127 / 154,5 / 190 | 56 / 89 / 134 | 127 / 154,5 / 190 |
| GLiNER | 54 / 104 / 152 | 159 / 199 / 245 | 54 / 104 / 152 | 159 / 199 / 245 |
| Laya | 45 / 78 / 123 | 119 / 146,5 / 182 | 45 / 78 / 123 | 119 / 146,5 / 182 |
| Julia | 45 / 78 / 123 | 119 / 146,5 / 182 | 45 / 78 / 123 | 119 / 146,5 / 182 |
| Omni | 65 / 105 / 141 | 139 / 174,5 / 218 | 65 / 105 / 141 | 139 / 174,5 / 218 |
| Indecis | 18 / 29 / 75 | 66 / 86 / 117 | 72 / 113,5 / 168 | 148 / 175,5 / 211 |
| ModernJEV | 62 / 92,5 / 144 | 149 / 186 / 236 | 244 / 359,5 / 558 | 429 / 546 / 702 |
| Muose | 51 / 79 / 140 | 133 / 174,5 / 236 | 202 / 309,5 / 543 | 391 / 513 / 695 |

Pour Jev, les tokens déclarés par le fournisseur sont exposés séparément dans les rapports ; ils ne prouvent pas son encodage interne. Les 312 choix Vela ont tous été transmis complets et ont exécuté le forward, sans troncature acceptée ni erreur/timeout. Les contrôles synthétiques ont refusé 10 028 tokens pour .3B et 20 120 pour .8B avant forward. Ils vérifient une garde, **pas une qualité sur grandes longueurs**. Aucun seuil de bascule vers un LLM n’est établi.

## Difficulté et splits

Les niveaux D1/D2/D3 et les références restent à revoir humainement. Les splits désignent ceux du corpus commun, pas un entraînement de ces modèles par le banc.

| Modèle | D1 /40 | D2 /40 | D3 /52 | Train /36 | Calibration /30 | Test /66 |
|---|---:|---:|---:|---:|---:|---:|
| Jev | 36 | 38 | 49 | 32 | 29 | 62 |
| Noma | 35 | 26 | 37 | 27 | 20 | 51 |
| Sol | 32 | 28 | 33 | 26 | 20 | 47 |
| Vela 0.8B | 29 | 25 | 25 | 22 | 12 | 45 |
| Eos | 30 | 22 | 25 | 20 | 17 | 40 |
| Kai | 27 | 17 | 26 | 18 | 16 | 36 |
| Vela 0.3B | 21 | 19 | 25 | 17 | 11 | 37 |
| GLiNER | 17 | 19 | 23 | 15 | 6 | 38 |
| Laya | 17 | 13 | 26 | 14 | 12 | 30 |
| Julia | 18 | 11 | 23 | 12 | 14 | 26 |
| Omni | 13 | 15 | 23 | 16 | 9 | 26 |
| Indecis | 12 | 11 | 21 | 12 | 10 | 22 |
| ModernJEV | 14 | 15 | 13 | 10 | 9 | 23 |
| Muose | 14 | 13 | 14 | 12 | 8 | 21 |

## Suites possibles

- Vela 0.3B mérite un pilote documentaire/routage local pour son coût mesuré. Ses 3/8 replis et 4/28 maths interdisent une généralisation à tous les choix.
- Vela 0.8B ne remplace pas Eos sur la base de ces passages : deux bons choix supplémentaires sur 132, davantage de RAM et de temps, et 0/8 replis.
- **Vela 4B : `not_run`**, aucun poids téléchargé, aucun score à zéro. Environ 15,69 Gio pour les paramètres principaux seuls en FP32 ; le préflight initial observait environ 14 Gio disponibles. Budget et loader restent à valider avant essai.
- **Strands : aucun score comparatif disponible** ; ses contrôles initiaux sur la branche Sol/Strands ont échoué au chargement sous la garde RSS. Ce statut n’est pas un mauvais score de décision.
- Mesurer les entrées longues et temps répétés Vela, revoir les références humaines, puis substituer le candidat dans un vrai harness de routage avec gardes et repli. CLI/chat, corpus privé, réponses finales, GPU, Span/Score/Set et extraction restent non mesurés.

Les [mesures historiques de longueurs](evidence/length-comparison-20261004/report.md) et [temps répétés](evidence/timing-comparison-20261004/report.md) gardent leurs candidats et dénominateurs initiaux. Aucun résultat historique n’est réécrit.
