# D3 mini, flash et 26B — précontrôle CPU du 11 octobre 2026

**Mini paraît accessible sur la machine actuelle ; flash mérite un pilote
séquentiel avec davantage de marge mémoire. Le 26B BF16 est hors du budget
retenu pour cette instance WSL.** État initial des trois candidats au précontrôle : `not_run`,
zéro prédiction et zéro cas scoré. Seuls métadonnées et petits fichiers
source ont été lus ; aucun de leurs poids n'a été téléchargé.

Mise à jour après essais : [Mini et Flash sont mesurés](D3_LARGER_CPU_RESULTS.md).
Le présent relevé reste le précontrôle initial ; D3 26B reste reporté.

## Snapshots et poids

| Candidat | Révision HF | Paramètres backbone BF16 | Fichiers de poids, octets | Fichiers de poids, Gio |
|---|---|---:|---:|---:|
| [d3-mini](https://huggingface.co/vllm-sr/d3-mini/tree/a475367de0d8133a3c1a2a0dc12303d89cfa2ab4) | `a475367de0d8133a3c1a2a0dc12303d89cfa2ab4` | 4 539 265 536 | 9 081 227 360 | 8,46 |
| [d3-flash](https://huggingface.co/vllm-sr/d3-flash/tree/521525effa79469d899a570726547dd7f00da3af) | `521525effa79469d899a570726547dd7f00da3af` | 8 392 695 024 | 16 789 656 976 | 15,64 |
| [d3](https://huggingface.co/vllm-sr/d3/tree/cbff3a3cb0b074b6585fe9f747b9f9f5557a0e75) | `cbff3a3cb0b074b6585fe9f747b9f9f5557a0e75` | 26 085 330 160 | 52 176 025 120 | 48,59 |

Sommes des fichiers safetensors backbone et readout, headers inclus, relevées
via l'API HF `?blobs=true`. Les comptes de paramètres concordent entre API et
`MODEL_MANIFEST.json` ; les headers des poids restent à vérifier avant essai.
Le readout est FP32, de forme 255 × 2 560 / 4 096 / 5 120, séparé du backbone.
Les configurations sont denses Qwen3.5, sans experts MoE déclarés. Le backbone
inclut aussi la vision, chargée pour le pilote textuel.

Poids sur disque et stockage théorique des tenseurs ne mesurent pas le pic
RSS : runtime, activations, chargement et pages réellement résidentes diffèrent.
**Au moment de ce précontrôle, aucune RAM RSS ni latence d'inférence de ces
candidats n'avait été mesurée.** Voir les [mesures suivantes](D3_LARGER_CPU_RESULTS.md).

## CPU natif et adaptation nécessaire

Les trois snapshots publient le même `d3_runtime.py`, `modeling_d3.py` et
`requirements.txt`. Le [loader natif](https://huggingface.co/vllm-sr/d3/blob/cbff3a3cb0b074b6585fe9f747b9f9f5557a0e75/d3_runtime.py#L1110-L1138)
accepte `device="cpu"`, charge le backbone BF16 avec SDPA et le readout FP32.
Il refuse les kernels GPU FLA/causal-conv lorsqu'ils sont liés dans le runtime
CPU ; le runtime séparé du [premier pilote](D3_CPU_PILOT.md) utilise le repli
PyTorch sans ces kernels. Au moment du précontrôle, le support déclaré restait à confirmer par chargement
et forward des nouveaux snapshots ; le pilote suivant l’a observé pour Mini/Flash.

Au moment du précontrôle, le bridge autorisait seulement edge/lite/nano.
Il fallait étendre les révisions, comptes de paramètres, formes de tête et
manifests, puis fixer les gardes avant la première prédiction. Ce travail
est effectué dans le [pilote progressif](D3_LARGER_CPU_PILOT.md). L'intégration
continuera d'appeler le vrai `D3.prepare/run/respond`, sans recopier son moteur.
Les manifests/configurations inspectés ne montrent pas de snapshot quantifié ;
le loader fixe BF16 et aucune voie native de quantification CPU n'est établie.

## Ressources relevées au précontrôle et ordre proposé

Relevé local : **43,11 Gio de RAM totale WSL, 23,44 Gio disponibles**,
16 Gio de swap dont environ 0,04 Gio utilisés. Cet instantané varie avec
les autres services. Le swap ne sert pas de budget pour qualifier un modèle.

1. Mini en premier : garder un seul worker CPU, deux threads et les mêmes
   132 bases FR/EN et 24 propositions Mastra, après contrôles courts/overflow.
2. Flash ensuite : mesurer d'abord le chargement et un choix court, avec
   une réserve pour la stack et les activations ; la faisabilité est plausible,
   sans garantie fondée uniquement sur ses 15,64 Gio de fichiers.
3. D3 26B : reporter l'essai natif sur cette configuration. Les seuls tenseurs
   BF16 représentent environ 48,59 Gio, davantage que toute la RAM WSL,
   avant les autres allocations et services. Une machine disposant de plus
   de RAM disponible, ou une voie quantifiée distincte et validée, permettrait
   de reconsidérer le pilote. Aucun loader quantifié ou offload n'est improvisé.

Chaque campagne future aura de nouveaux dossiers, gardes/budgets et provenance.
Un score supérieur à nano n'est pas déduit de la taille : nano reste à 18/24
sur le routage, contre 19/24 pour lite. Les [local-only material, not distributed](PROTOCOL.md),
archives antérieures, références provisoires et qualifications ne changent pas.
Ce précontrôle ne valide aucune intégration CLI/chat ni réponse finale.
