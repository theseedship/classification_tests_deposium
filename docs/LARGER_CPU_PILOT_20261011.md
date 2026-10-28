# Pilote CPU Nox 4B, Vela 4B et Liquid d1-3B — 11 octobre 2026

Protocole fixé avant la première prédiction. Les trois modèles commencent
`not_run`, zéro cas scoré ; exécution séquentielle, CPU natif FP32, deux threads,
batch d’une question. Aucun appel API payant, modification de service ou donnée privée.
Les anciennes qualifications et captures restent inchangées.

| Modèle | Révision HF | Paramètres chargés attendus | RSS max Mio | MemAvailable avant worker Mio | Initialisation max s |
|---|---|---:|---:|---:|---:|
| Nox 4B | `ae269ecf34a0b3a89026bc1afd9c995279212fad` | 4 208 383 488 | 22 528 | 24 576 | 300 |
| Vela 4B | `d692394127f6f87fc581d8634c9558fe4776efce` | 4 211 182 082 | 22 528 | 24 576 | 300 |
| Liquid d1-3B | `051bcc464b01b9f92942b364d9586b0ef5912432` | 3 123 483 888, embeddings liés | 18 432 | 22 528 | 300 |

Les paramètres ne sont pas une mesure RSS. Le total HF Vela omet le biais scalaire `set_bias` ;
les headers réels et le manifeste amont comptent 4 211 182 082 éléments : le worker vérifie indépendamment les headers
réels de ses shards et les tenseurs effectivement chargés. Liquid appelle le
vrai `D1Model.system_one` et son moteur natif ; Nox et Vela utilisent les helpers
amont. Aucun algorithme de prédiction n’est recopié.

Même corpus de 132 bases FR/EN que les campagnes précédentes : documentaire 76,
mathématiques 28, chimie 28, 66 cas par langue ; SHA-256
`767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616`.
Puis 24 propositions Mastra, recherche/statistiques/repli, 12 cas par langue ;
SHA-256 `d66ec51d9b8d89f46b87b90b80bcd0d45abf1570fa9857c24d9ce39117935497`.
Références `agent_only_pending_human`, aucun outil exécuté : cet accord est
provisoire et ne qualifie ni le routage produit ni les réponses finales.

Avant chaque campagne : contrôle synthétique court et overflow, zéro cas scoré.
Plafond local de 4096 tokens natifs sans troncature ; intégrité vérifiée jusqu’au
forward. Le choix court vérifie le contrat, sans servir de score de justesse.
Choix borné à 60 s, bases bornées à 2400 s externes (SIGINT puis arrêt forcé 30 s),
Mastra à 600 s. Réserve de 4096 Mio MemAvailable pendant exécution, swap exclu.
RSS échantillonné : le plafond n’est pas une garantie instantanée. Aucun seuil
n’est relevé après une prédiction ; échecs/timeout/refus demeurent conservés.
Un préflight refusé reste `not_run`, sans imputer de mauvais score.

Les snapshots complets sont vérifiés contre les blobs/LFS HF épinglés ; poids,
logs, profils absolus, reçus de nettoyage et archives brutes restent hors Git.
Le code et le protocole sont commités avant inférence, puis archivés séparément.
Chaque campagne recense les sous-modules déclarés de la stack configurable ;
gitlinks, HEAD locaux, images et comportement observé restent distincts.

Nettoyage autorisé : 31 fichiers de poids déjà mesurés, 55 678 920 586 octets,
51,855 Gio, après vérification de 17 archives scellées. Configurations, tokenizers,
sources, manifests et captures sont conservés. Les copies Qwen/Strands, Bekko,
Laya préparé et les nouveaux candidats sont exclus. Le rejeu des anciens modèles
nécessitera un téléchargement de leurs révisions épinglées ; leurs scores ne changent pas.

Vela4 annonce 17 langues, Liquid3 en annonce 16 dont le français ; ces déclarations
ne remplacent pas nos résultats FR/EN. CLM8B et Muose100 sont étiquetés anglais ;
ils restent exploratoires pour une exigence multilingue. Le backbone Qwen de
CLM ne prouve pas la qualité multilingue de sa tête de décision.
Sources : [Nox](https://huggingface.co/vllm-sr/Decision-2.0-Nox-4B),
[Vela4](https://huggingface.co/vllm-sr/Vela-2.0-4B),
[Liquid3](https://huggingface.co/LiquidAI/d1-3B),
[CLM8B](https://huggingface.co/Contrastive-LM/CLM-v0.1-8B),
[Muose100](https://huggingface.co/muose/Muose-100M-Decision).

Les variantes Lux 9 et Vela 9 demanderaient environ 29,6 Gio pour les seuls paramètres
FP32, au-delà de la marge actuellement disponible. Aucun poids 9B téléchargé :
les loaders natifs conservent leurs paramètres FP32 sur CPU, même avec
autocast. Une autre représentation ou machine devra être vérifiée avant admission.
Strands reste candidat séparé avec ses poids de base conservés. Voir
[les variantes jusqu’à 9B](VARIANTS_UP_TO_9B.md) pour leurs versions et limites.
