# Vela3-fast : premier palier mesuré — 28 octobre 2026

**Vela3-fast, backbone de décision seul, obtient 57/132 bases et 18/24 accords
Mastra provisoires sur le Mac.** Il ne remplace pas D3 Flash ou D3 27B pour ces
tâches. Les tâches spécialisées des adaptateurs Vela 3 restent non exécutées.
D3 Ultra et Turbo restent également `not_run` ; voir la
[revue des collections et des runtimes](DECISION3_VELA3_REVIEW_20261028.md).

## Résultats et couverture

Même corpus, références, splits et scorers que les campagnes précédentes :
132 bases = 66 familles FR/EN ; 24 observations Mastra = 12 familles.
Références encore proposées par agents, sans revue humaine. Les 156 décisions
sont valides, avec une passe native observée, sans troncature, erreur, timeout
ou repli de périphérique. **Aucun cas Mastra sémantiquement qualifié**, aucun
outil exécuté, aucun parcours produit testé.

| Mesure | Résultat |
|---|---:|
| Bases, tous splits | **57/132** (43,18 %) |
| Bases, split test uniquement | **28/66** |
| Bases EN | **32/66** |
| Bases FR, langue exploratoire | **25/66** |
| Documentaire / mathématiques / chimie | **43/76 ; 9/28 ; 5/28** |
| Mastra, accord avec les propositions | **18/24**, dont 14/18 test |
| Mastra EN / FR | **9/12 ; 9/12** |
| Mastra search / stats / fallback | **8/8 ; 8/8 ; 2/8** |
| Paires Mastra donnant la même action | **11/12** |
| Couverture bases / Mastra | **132/132 ; 24/24** |

Le faible score ne vient pas uniquement du français : l'anglais reste à
32/66 et la chimie à 5/28. L'accord Mastra masque aussi six désaccords sur les
huit propositions `fallback`. Ces observations ne qualifient pas le routeur
spécialisé Vela3Encoder, qui n'a pas été chargé dans ce pilote.

Le [comparatif hors inférence](evidence/vela3-fast-20261028/report.md) et son
[JSON](evidence/vela3-fast-20261028/analysis.json) vérifient les sceaux des
archives locales existantes avant agrégation :

| Observation | Bases /132 | Accord Mastra /24 |
|---|---:|---:|
| D3 historique classe 27B Q4, Metal | 128 | 24 |
| D3 Flash Q8, Metal | 124 | 20 |
| GLiClass v4 9B BF16, MPS | 117 | 20 |
| **Vela3-fast décision seule FP32, CPU** | **57** | **18** |

Vela **2.0** 0.3B, 0.8B et 4B avaient obtenu respectivement **65, 79 et
106/132**, avec **18, 14 et 18/24** accords provisoires. Ces lignes viennent
des [agrégats CPU publiés](evidence/model-comparison-larger-cpu-overview-20261011/report.md) ;
leurs archives brutes WSL ne sont pas présentes sur ce Mac et n'ont pas été
rescorrées ici. Différences de machines, précision, génération et architecture
conservées ; aucun avantage matériel contrôlé n'est déduit de cette table.

## Runtime, mémoire et limites

Le profil `profiles/vela3-fast-cpu.json` épingle
`vllm-sr/vela3-fast@9e338f39babc622f42e9bd8556398fe2d80d9f13`.
Poids : **1 521 771 272 octets**, **380 436 226 éléments F32**, scalaire
`log_tau` inclus. L'agrégat API de paramètres omet ce scalaire ; le header
borné, les octets et le compteur du modèle chargé sont vérifiés séparément.
Les huit helpers, config et tokenizer ont des SHA256 fixes ; les autres
fichiers retenus sont vérifiés contre les blobs Git/LFS publiés.

Le vrai `DecisionEncoder.load` / `predict` officiel s'exécute sans modification,
en **CPU FP32/SDPA**, deux threads, limite locale 4096 tokens, sous Python
3.12.12 / Torch 2.14.0 / Transformers 5.17.0. Le readout `lg.double().cpu()`
n'est pas directement utilisable sur MPS. Le code du banc ne le remplace pas
et ne reconstruit pas les probabilités. L'encodeur reçoit les IDs et masques
complets vérifiés au forward ; les identifiants externes et références ne sont
pas fournis au modèle. Les adaptateurs span/router/vision ne sont pas chargés.

RSS maximal observé : **3233,94 Mio sur les bases et 3234,89 Mio sur Mastra**,
soit environ **3,16 Gio**. Médiane adaptateur : **80,5 ms** sur les bases,
**156,9 ms** sur Mastra ; initialisations de l'ordre de 8,3–8,4 s. Ce sont
des passages uniques sur des entrées courtes (43–166 tokens natifs pour les
bases), avec une stack Docker déjà active et une validation Linux hors poids
en parallèle. Ni les 32K annoncés, ni une latence
de production, ni l'inférence WSL/CUDA/MPS ne sont qualifiés.

Le [protocole fixé avant les prédictions](DECISION3_VELA3_PILOT_20261028.md)
prévoit admission à 16 Gio avant hash, plafond RSS 8 Gio et réserve 8 Gio,
initialisation 300 s, appel 30 s et Mastra 300 s. Ces seuils ont été conservés.
Le smoke a vérifié chargement, choix et refus trop long avant forward, zéro cas
scoré. Le refus synthétique ne constitue pas une campagne de longues entrées.

## Conservation et reproduction

Code et protocole des prédictions :
`cbd25a7b3f445d70ce221658de5a859d138d015f`.
Le relevé Git des campagnes indique deux documents de revue non suivis ; le
code exécuté et le protocole étaient committés et leurs empreintes sont
enregistrées. Les [identités et sceaux publics](evidence/vela3-fast-20261028/vela3-fast-session.json)
relient les résultats à l'archive privée
`results/vela3-fast-pilot-20261028-001/` : smoke, bases, Mastra, sources,
runtime, stderr et sceau parent de 35 fichiers. Les archives historiques sont
inchangées. Aucun poids ni journal privé n'est publié dans Git.

Créer un environnement **Python 3.12.12** isolé, puis installer les pins de
`runtimes/vela3-fast/runtime.lock` en excluant sa ligne `python==...` (c'est un
fingerprint, pas un paquet pip). Télécharger uniquement les noms de fichiers du
manifeste versionné, à la révision complète :

```python
import json
from huggingface_hub import snapshot_download
assets = json.load(open("profiles/vela3-fast-assets.json"))
snapshot_download(assets["repo_id"], revision=assets["revision"],
                  local_dir="models/vela3-fast-9e338f3",
                  allow_patterns=[f["path"] for f in assets["files"]])
```

Archiver les métadonnées du Hub avec `?blobs=true`, puis vérifier le snapshot
sans chargement. Le dossier de sortie du préparateur doit être neuf :

```bash
python3 scripts/prepare-vela3-fast-assets.py \
  --model-dir models/vela3-fast-9e338f3 \
  --metadata results/vela3-fast-publisher-blobs.json \
  --output results/vela3-fast-verified-assets.json
```

Comparer ce manifeste au fichier versionné ; adapter les chemins du profil si
nécessaire. Les tests ordinaires et le registre n'ont besoin d'aucun poids.
Les exécutions explicites utilisent le même moteur commun :

```bash
python3 scripts/run-vela3-fast-smoke.py \
  --profile profiles/vela3-fast-cpu.json --stack-root ../deposium_fullstack \
  --output results/vela3-fast-reproduction-001/smoke
python3 -m deposium_bench run \
  --dataset datasets/context-choice-v1/cases.jsonl \
  --profile profiles/vela3-fast-cpu.json --stack-root ../deposium_fullstack \
  --output results/vela3-fast-reproduction-001/bases
python3 -m deposium_bench observe-mastra-read \
  --dataset datasets/mastra-read-pilot-v0/cases.jsonl \
  --profile profiles/vela3-fast-cpu.json --stack-root ../deposium_fullstack \
  --max-seconds 300 --output results/vela3-fast-reproduction-001/mastra
```

Un verdict de qualité négatif sur les bases peut retourner un code non nul
avec `completion_status:complete` et couverture 132/132 : lire la synthèse,
sans transformer ce score en erreur d'inférence. Attendre la libération du
worker entre phases ; ne pas relever les gardes pour terminer une campagne.
Les profils et interfaces CPU sont communs à macOS et Linux/WSL, mais seul
le forward macOS a été observé dans ce lot.

L'inventaire actuel de la stack est archivé avec les campagnes : 14
sous-modules déclarés contre 15 dans le registre historique. Ni le service
`deposium-inference` voisin, ni ses travaux locaux, ni Railway, ni les gitlinks
ne sont modifiés. Aucun service de la stack n'a été relancé pour ces tests.

## Validation du lot

- **Mac : 47/47 tests Vela hors poids réussis**, jsonschema actif.
- **Linux amd64 : 767 tests, 735 réussis / 32 skips optionnels**, zéro échec,
  Python 3.12.12, Git et jsonschema 4.26.0, réseau coupé, 2 CPU / 4 Gio.
  Les skips concernent notamment Node/DuckDB et des intégrations optionnelles ;
  ce contrôle ne constitue pas une inférence Linux/WSL du modèle.
- Registre historique valide : **15 composants / 29 contrats**.
- **274 validations de schémas** sur les vrais artefacts, **156 audits natifs**,
  synthèses reproduites à l'identique et **35 fichiers scellés revérifiés**.
  Liens locaux et `git diff --check` valides ; aucun worker Vela3-fast restant.

Journaux privés : `results/decision3-vela3-review-20261028-001/`.
La première image Python ne contenait pas Git ; la deuxième n'exposait Python
que dans `/usr/local/bin`, hors du PATH nettoyé des workers factices Indecis.
La troisième exécution ajoute un alias Python dans le conteneur et passe toute
la suite. Les essais antérieurs restent conservés ; aucun code applicatif ni
référence n'a été modifié pour résoudre ces prérequis de validation.
