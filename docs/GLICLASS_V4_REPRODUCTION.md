# Reprendre GLiClass v4 9B depuis un autre poste

Ce guide complète le [protocole gelé](GLICLASS_V4_PILOT.md) sans le modifier.
Les [résultats du 17 octobre](GLICLASS_V4_RESULTS_20261017.md) sont déjà mesurés :
117/132 bases, dont 63/66 test, et 20/24 accords Mastra provisoires ; zéro cas
Mastra sémantiquement qualifié. Les commandes ci-dessous préparent **une nouvelle
exécution**, avec ses propres captures. Elles n'ont pas été rejouées pour rédiger
ce guide ; options et chemins ont été contrôlés dans le code et les aides CLI.

## Ce que fournit Git

Un clone contient les données synthétiques et références, le moteur commun
CLI/notebook, les scorers, l'adaptateur et le worker, les profils et inventaires
SHA, le fingerprint du runtime et les preuves agrégées publiques. Il permet de
lire les résultats et de valider le banc sans poids ni service externe :

```bash
python3 -m deposium_bench validate-registry
python3 -m unittest discover -s tests -v
```

Le socle demande Python 3.11+ ; ces commandes ordinaires ne téléchargent ni ne
chargent de modèle. Les limitations de la suite Mac historique restent indiquées
dans les rapports ; un registre valide n'est pas une campagne réussie.

`models/` et tout `results/` sont ignorés par Git. **Un pull ne transfère ni les
poids, ni les sorties brutes, ni les environnements, ni les archives scellées.**
Le [comparatif public](evidence/gliclass-model-comparison-20261017/report.md)
compare cinq exécutions natives. Les autres campagnes et protocoles gardent leurs
rapports propres ; cela ne constitue pas un classement unique de tous les usages.

Pour auditer ou rescorer les observations originales sur un autre poste,
transférer séparément, par un canal adapté, les dossiers complets suivants :

- `results/gliclass-smoke-20261017-001/` ;
- `results/gliclass-native-pilot-20261017-001/`, avec `bases/`, ses sources et
  l'enveloppe initiale conservée `completed:false` ;
- `results/mastra-read-gliclass-20261017-001/` ;
- `results/gliclass-consolidated-20261017-001/`, contenant les observations,
  l'exporteur `export.py`, l'orchestrateur `run-campaigns.py`, les stderr et leur sceau.

Pour reconstruire les comparaisons avec Eos/D3, il faut aussi leurs quatre
archives `eos-native-pilot-20261016-001/`,
`d3-flash-native-pilot-20261016-001/`,
`d3-flash-q4-native-pilot-20261016-001/` et
`d3-27b-q4-native-pilot-20261016-001/`, ainsi que les analyses appariées conservées.
L'exporteur de session est dans l'archive privée ; il n'est pas installé par Git.
Les empreintes publiées dans
[gliclass-session.json](evidence/gliclass-model-comparison-20261017/gliclass-session.json)
permettent de relier les captures. Vérifier les sceaux après transfert ; conserver
les octets originaux, y compris les chemins de provenance du poste d'origine.
Un rescore doit écrire dans un dossier neuf, sans modifier son archive source.
Les poids et le runtime ne sont pas nécessaires à ce rescore hors inférence :

```bash
python3 -m deposium_bench rescore \
  --archive results/gliclass-native-pilot-20261017-001/bases \
  --output results/gliclass-rescore-autre-poste-001
```

La suite du guide sert à **refaire l'inférence**. Elle exige de préparer ou
transférer les huit fichiers modèle et le snapshot officiel vérifié. Recréer
l'environnement local plutôt que copier un venv entre machines.

## Code courant ou code historique

La capture originale exécutait **`427e4d13a7d4e19179b5d2fb62246426a75a1331`**.
La consolidation ultérieure intègre d'autres travaux, dont la PR #8 : les helpers
communs et leurs empreintes peuvent donc différer même si les poids, paramètres
et sources GLiClass sont conservés. Les commandes ci-dessous utilisent le code
courant ; elles ne rejouent pas automatiquement le wrapper historique à l'identique.

Pour examiner ou réexécuter les sources du code historique, préparer un checkout
séparé à cette révision, depuis le dépôt local :

```bash
git clone --no-checkout . ../deposium-gliclass-code-427e
git -C ../deposium-gliclass-code-427e checkout --detach \
  427e4d13a7d4e19179b5d2fb62246426a75a1331
git -C ../deposium-gliclass-code-427e rev-parse HEAD
```

Dans ce checkout séparé, reprendre les pins du modèle, du code officiel et du
runtime archivés. Les chemins du profil de 2026 dépendaient du worktree d'origine :
les reconfigurer dans **un nouveau profil local**, pour les assets vérifiés de ce
poste. Cette adaptation change l'empreinte du profil et doit être enregistrée ;
ne pas réécrire le profil archivé ni prétendre conserver l'identité complète de
l'ancienne capture. Les sources archivées et leurs sceaux restent l'autorité pour
l'audit de l'exécution originale. Le schéma de campagne de `427e4d13` avait une
lacune de déclaration GLiClass, corrigée ensuite hors inférence ; ne pas altérer
l'archive pour la corriger. Même avec ce code et ces pins, aucune égalité bit à bit
MPS entre deux machines n'est garantie.

## Préparer un environnement Mac isolé

Voie qualifiée par le lot : **macOS arm64, MPS, BF16, attention eager**.
L'inférence CPU/CUDA sous Linux/WSL n'est pas qualifiée par ces commandes.
Docker, Supabase et les services applicatifs n'ont pas à démarrer pour ce modèle
isolé. Si la stack source est disponible, son chemin sert au préflight Git,
sans lancer ses services. Aucune API payante n'est utilisée.

Prérequis explicites : Git, curl et un interpréteur **Python 3.12.12 arm64**
accessible sous le nom `python3.12`. Le mettre à disposition avant cette étape ;
le Python système du Mac peut être d'une autre version. Les commandes ne
l'installent pas globalement et refusent une autre version ou architecture.

Toutes les commandes partent de la racine du dépôt, dans un clone propre.
Utiliser une nouvelle session de terminal et arrêter au premier échec :

```bash
set -e
python3.12 - <<'PY'
import platform
import sys
from pathlib import Path
assert sys.version_info[:3] == (3, 12, 12), "Python 3.12.12 requis"
assert platform.system() == "Darwin" and platform.machine() == "arm64", "Mac arm64 requis"
assert not Path("results/.toolchains/gliclass-python").exists(), "venv déjà présent : vérifier ou utiliser un clone neuf"
Path("results/gliclass-reproduction-001").mkdir(parents=True, exist_ok=False)
PY
python3.12 -m venv results/.toolchains/gliclass-python
export PIP_CACHE_DIR="$PWD/results/gliclass-reproduction-001/pip-cache"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export HF_HOME="$PWD/results/.cache/hf-gliclass-reproduction"
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export HF_HUB_DISABLE_TELEMETRY=1
export HF_HUB_DISABLE_PROGRESS_BARS=1
```

`runtimes/gliclass/runtime.lock` est un **fingerprint**, pas un fichier pip brut :
43 identités, soit Python et 42 distributions. Python est traité séparément ;
`gliclass==0.1.21` sera construit depuis le commit officiel vérifié. Préparer les
41 autres pins pour pip, sans changer le lock suivi :

```bash
python3.12 - <<'PY'
from pathlib import Path
pins = {}
for line in Path("runtimes/gliclass/runtime.lock").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#"):
        name, version = line.split("==", 1)
        assert name not in pins
        pins[name] = version
assert len(pins) == 43 and pins["python"] == "3.12.12" and pins["gliclass"] == "0.1.21"
with Path("results/gliclass-reproduction-001/requirements.txt").open("x") as out:
    out.write("".join(f"{name}=={version}\n" for name, version in sorted(pins.items())
                      if name not in {"python", "gliclass"}))
PY
results/.toolchains/gliclass-python/bin/python -m pip install \
  --no-deps --only-binary=:all: \
  --requirement results/gliclass-reproduction-001/requirements.txt
```

Cette dernière commande télécharge les dépendances dans le venv local. Si un pin
ou une roue arm64 est indisponible, arrêter et documenter l'écart ; ne pas le
remplacer silencieusement par une version récente ou une autre précision.

## Préparer les 27 fichiers de code officiel

Le profil attend `results/.sources/gliclass-runtime-6a00f80/`, contenant exactement
l'inventaire de `profiles/gliclass-source-assets.json`. Le checkout complet Git
sert seulement à extraire ces fichiers ; aucun notebook ni script d'entraînement
n'est exécuté.

```bash
git init results/gliclass-reproduction-001/GLiClass-upstream
git -C results/gliclass-reproduction-001/GLiClass-upstream remote add origin \
  https://github.com/Knowledgator/GLiClass.git
git -C results/gliclass-reproduction-001/GLiClass-upstream fetch --depth 1 origin \
  6a00f8067648f25aa0f4f477d167c5f391cb4165
git -C results/gliclass-reproduction-001/GLiClass-upstream checkout --detach FETCH_HEAD
python3.12 - <<'PY'
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
manifest = json.loads(Path("profiles/gliclass-source-assets.json").read_text())
revision = "6a00f8067648f25aa0f4f477d167c5f391cb4165"
upstream = Path("results/gliclass-reproduction-001/GLiClass-upstream")
target = Path("results/.sources/gliclass-runtime-6a00f80")
assert manifest["repo_id"] == "Knowledgator/GLiClass" and manifest["revision"] == revision
assert len(manifest["files"]) == 27
assert subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip() == revision
assert not target.exists(), "snapshot déjà présent : ne pas écraser"
for item in manifest["files"]:
    path = upstream / item["path"]
    assert path.is_file() and not path.is_symlink()
    data = path.read_bytes()
    assert len(data) == item["size"] and hashlib.sha256(data).hexdigest() == item["sha256"]
target.mkdir(parents=True, exist_ok=False)
for item in manifest["files"]:
    destination = target / item["path"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(upstream / item["path"], destination)
assert {str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()} == {
    item["path"] for item in manifest["files"]}
# Le packaging peut créer build/ et egg-info : le faire sur une autre copie.
shutil.copytree(target, "results/gliclass-reproduction-001/package-build")
print("27 fichiers officiels vérifiés")
PY
results/.toolchains/gliclass-python/bin/python -m pip install \
  --no-deps --no-build-isolation results/gliclass-reproduction-001/package-build
```

Ne pas installer depuis une branche mouvante ou modifier le snapshot utilisé par
le worker. Vérifier les 43 identités du runtime après installation, sans charger
les poids :

```bash
results/.toolchains/gliclass-python/bin/python - <<'PY'
import importlib.metadata
import sys
from pathlib import Path
for line in Path("runtimes/gliclass/runtime.lock").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    name, expected = line.split("==", 1)
    actual = sys.version.split()[0] if name == "python" else importlib.metadata.version(name)
    assert actual == expected, (name, actual, expected)
print("Runtime conforme au fingerprint")
PY
```

Le worker refait ce contrôle et importe le code de l'inventaire local, dont les
hashes sont contrôlés par l'adaptateur. L'installation de la distribution sert
aussi à exposer sa version ; elle ne remplace pas le snapshot épinglé.

## Télécharger et vérifier les huit fichiers modèle

Étape réseau explicite : environ **18 Go de poids**, hors allocations d'inférence.
Le modèle public ne demande pas de token dans ces commandes. Les deux variables
d'authentification usuelles sont retirées pour le téléchargement ; aucune clé
n'est placée dans des arguments, profils ou notebooks.

```bash
curl --disable --fail --location --silent --show-error \
  'https://huggingface.co/api/models/knowledgator/gliclass-v4-9b/revision/14d11a92b5e0bab4a166e1fce4cc0777cac27182?blobs=true' \
  --output results/gliclass-reproduction-001/model-9b-blobs.json
env -u HF_TOKEN -u HUGGING_FACE_HUB_TOKEN \
  results/.toolchains/gliclass-python/bin/hf download \
  knowledgator/gliclass-v4-9b \
  README.md calibration_report.json chat_template.jinja config.json \
  model.safetensors processor_config.json tokenizer.json tokenizer_config.json \
  --revision 14d11a92b5e0bab4a166e1fce4cc0777cac27182 \
  --local-dir models/gliclass-v4-9b-14d11a9 --max-workers 1
results/.toolchains/gliclass-python/bin/python scripts/prepare-gliclass-assets.py \
  --model-dir models/gliclass-v4-9b-14d11a9 \
  --metadata results/gliclass-reproduction-001/model-9b-blobs.json \
  --output results/gliclass-reproduction-001/verified-model-assets.json
results/.toolchains/gliclass-python/bin/python - <<'PY'
import json
from pathlib import Path
expected = json.loads(Path("profiles/gliclass-v4-9b-assets.json").read_text())
observed = json.loads(Path("results/gliclass-reproduction-001/verified-model-assets.json").read_text())
assert observed == expected, "Inventaire différent du profil suivi ; arrêter"
print("8 fichiers modèle conformes aux métadonnées HF et au profil suivi")
PY
```

Le préparateur contrôle l'identité et la révision des métadonnées HF, les tailles,
les SHA-256 LFS et les identités Git des petits fichiers. Son résultat va dans
un fichier **neuf** sous `results/`, puis est comparé au manifeste suivi ; ne pas
utiliser `--output profiles/gliclass-v4-9b-assets.json`, qui existe déjà dans Git.
Le profil conserve le manifeste suivi. Le cache `.cache/` créé par HF reste hors
inventaire ; aucun autre fichier modèle supplémentaire n'est accepté.

## Nouvelle inférence : smoke, bases puis Mastra

Les étapes ci-dessous **chargent réellement le modèle**. Le profil reste MPS,
BF16/eager, contexte 4096, deux threads, initialisation 300 s, appels 30 s.
Admission avant hash : 40960 Mio disponibles, soit budget RSS 32768 et réserve
hôte 8192. RSS et compteur GPU rapporté ont chacun le plafond numérique 32768 ;
ils ne sont pas additionnés. Le profil ne mesure pas un pic absolu de toute la
mémoire unifiée. Aucun seuil ne doit être relevé pour compléter un score.

Avant le premier chargement, conserver les sources suivies effectivement
exécutées et leurs identités dans le nouveau dossier de préparation :

```bash
python3.12 - <<'PY'
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
assert not subprocess.check_output(["git", "status", "--porcelain"], text=True).strip(), "Checkout suivi non propre"
folder = Path("results/gliclass-reproduction-001")
with (folder / "bench-commit.txt").open("x") as out:
    out.write(subprocess.check_output(["git", "rev-parse", "HEAD"], text=True))
assert not (folder / "bench-source.tar").exists()
subprocess.run(["git", "archive", "--format=tar", "--output", str(folder / "bench-source.tar"), "HEAD"], check=True)
source = Path("results/.sources/gliclass-runtime-6a00f80")
manifest = json.loads(Path("profiles/gliclass-source-assets.json").read_text())
with tarfile.open(folder / "official-source.tar", "x") as archive:
    for item in manifest["files"]:
        archive.add(source / item["path"], arcname=item["path"], recursive=False)
for name in ("gliclass-v4-9b-mps.json", "gliclass-v4-9b-assets.json", "gliclass-source-assets.json"):
    assert not (folder / name).exists()
    shutil.copyfile(Path("profiles") / name, folder / name)
assert not (folder / "runtime.lock").exists()
shutil.copyfile("runtimes/gliclass/runtime.lock", folder / "runtime.lock")
PY
```

Choisir le chemin configurable de la stack source si elle est présente ; aucun
service n'est lancé par ce paramètre. Les métadonnées Git constatées peuvent
différer de celles du Mac d'origine et doivent rester archivées telles quelles.
Les sorties doivent rester en dehors de cette stack :

```bash
GLICLASS_STACK_ROOT="../deposium_fullstack"
results/.toolchains/gliclass-python/bin/python scripts/run-gliclass-smoke.py \
  --profile profiles/gliclass-v4-9b-mps.json \
  --stack-root "$GLICLASS_STACK_ROOT" \
  --output results/gliclass-reproduction-001/smoke
```

Lire `smoke/smoke.json`, `choice.json`, `overflow.json` et le stderr privé.
Exiger `completed:true`, un choix valide et le refus trop long avant forward.
Ce smoke score zéro cas. Un chargement raté, un repli CPU, une troncature ou un
arrêt mémoire reste un résultat technique archivé ; ne pas poursuivre comme
s'il s'agissait d'une mesure de qualité.

Après fermeture du smoke, lancer une seule campagne à la fois :

```bash
results/.toolchains/gliclass-python/bin/python -m deposium_bench run \
  --dataset datasets/context-choice-v1/cases.jsonl \
  --profile profiles/gliclass-v4-9b-mps.json \
  --stack-root "$GLICLASS_STACK_ROOT" \
  --output results/gliclass-reproduction-001/bases
results/.toolchains/gliclass-python/bin/python -m deposium_bench observe-mastra-read \
  --dataset datasets/mastra-read-pilot-v0/cases.jsonl \
  --profile profiles/gliclass-v4-9b-mps.json \
  --stack-root "$GLICLASS_STACK_ROOT" --max-seconds 300 \
  --output results/gliclass-reproduction-001/mastra
```

Chaque commande crée son propre worker, le ferme et attend sa terminaison.
La CLI `run` applique les délais par appel et gardes du profil ; elle n'a pas
d'option `--max-seconds`. Mastra garde son budget de 300 s. Les dossiers de
sortie doivent être absents avant chaque lancement. Si la mémoire n'est pas
revenue naturellement au seuil d'admission entre phases, conserver le refus
et attendre ; ne pas arrêter des applications tierces ni changer les gardes
pour obtenir une campagne complète. Le smoke et les phases antérieures peuvent
réchauffer les caches : ces passages ne garantissent pas un démarrage à froid.

Examiner couverture, statuts, sorties brutes, provenance et sceaux. Ne pas confondre
`completion_status:complete`, 132 cas effectivement scorés, exactitude et simple
accord Mastra. Conserver références et dénominateurs, y compris lors d'un échec.
Le profil et le code du nouvel essai sont archivés avec leur propre révision :
ne pas les présenter comme une nouvelle exécution de `427e4d13` à l'identique.

## Conserver les preuves de la nouvelle exécution

Les CLI produisent les sous-archives scellées, mais ne reconstruisent pas
l'enveloppe historique, ses tar de sources ou son exporteur privé. Avant de
partager une nouvelle campagne, conserver aussi un snapshot du banc effectivement
exécuté et du code GLiClass vérifié, le lock, les profils, inventaires, logs
privés et commandes employées. La fermeture des workers doit précéder le dernier
scellement. Ne pas remplacer ni réécrire les archives de 2026 pour publier un score.

Le partage Git vise les rapports, preuves agrégées, protocoles et code. Le transfert
des archives privées est une opération séparée ; les poids peuvent être retéléchargés
à la même révision. Une seed ou des versions identiques ne garantissent pas des
prédictions ou temps identiques entre machines. CPU/CUDA, grandes longueurs,
routage intégré et parcours produit exigent leurs propres qualifications.
