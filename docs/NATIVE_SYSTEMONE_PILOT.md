# Pilote local GGUF via deposium-inference

Protocole du **16 octobre 2026**, avant les campagnes complètes Eos / D3 Flash.
Le CLI et le notebook partagent `campaigns.run_campaign`, les mêmes cas,
références et scorers. Le nouvel adaptateur `systemone_local` transmet seulement
le contexte, la question et les descriptions ordonnées à la vraie passerelle
`deposium-inference`. Il n'implémente aucun encodeur, tête ou routage applicatif.

## Entrées figées et qualification

- Bases : `datasets/context-choice-v1/cases.jsonl`, 132 cas, 66 familles FR/EN,
  SHA-256 `767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616`.
- Mastra : `datasets/mastra-read-pilot-v0/cases.jsonl`, 24 propositions,
  SHA-256 `d66ec51d9b8d89f46b87b90b80bcd0d45abf1570fa9857c24d9ce39117935497`.
  Le helper `candidate_request` et la projection commune restent inchangés.
- Les annotations, IDs sémantiques et réponses attendues restent hors requête.
  Les options portent `c0`, `c1`, etc. ; le banc remappe la réponse vers leur ID.
- Les références attendent leur revue humaine. Les bases conservent leurs
  oracles restreints ; Mastra reste un accord provisoire, zéro cas sémantiquement
  qualifié. Aucun outil, planner ou parcours produit n'est exécuté.

Poids et révisions sont dans `profiles/eos-q8-gguf-assets.json`,
`profiles/d3-flash-q8-assets.json` et `profiles/d3-27b-q8-assets.json`.
Ces manifestes ne téléchargent rien. Eos utilise le runtime Decision 2.0 déjà
validé ; D3 utilise un second pin officiel. Le GGUF Eos existant ne charge pas
avec ce pin D3 : ce refus technique reste archivé. Même API ne signifie pas
interchangeabilité des exports. Les scores PyTorch CPU historiques restent des
observations distinctes des nouveaux candidats Q8/Metal.

## Ressources et exécution explicite

Python 3.11+ et la bibliothèque standard suffisent au pilote, après compilation
explicite du service natif et téléchargement explicite d'un GGUF. Lire le
`docs/LOCAL_RUNTIME.md` du dépôt d'inférence pour compiler Metal, CPU ou CUDA.
Le code n'installe rien globalement et n'utilise aucun service Supabase.

```bash
python3 scripts/run-native-pilot.py \
  --service-root ../deposium_fullstack/deposium-inference \
  --stack-root ../deposium_fullstack \
  --model models/vllm-d3-flash-GGUF-3d53d13/vllm-d3-flash-Q8_0.gguf \
  --assets-manifest profiles/d3-flash-q8-assets.json \
  --model-id d3-flash-q8 --runtime d3 --backend metal \
  --max-rss-mb 20480 --min-free-mb 8192 --max-seconds 1200 \
  --output results/d3-flash-native-NOUVEAU
```

`--smoke-only` exécute les contrôles techniques sans campagne scorée. Sur WSL,
sélectionner `--backend cuda` ou `cpu` avec l'artefact construit sur cette
plateforme ; l'exécution CUDA n'est pas qualifiée par le seul build Mac.
Eos emploie son manifeste, `--runtime decision2` et une garde RSS de 8192 Mio.

Premier palier Flash : contexte 4096, batch physique/logique 4096, un slot,
une question et un appel à la fois. Garde RSS du groupe possédé 20480 Mio,
au moins 8192 Mio estimés disponibles pendant l'essai, 1200 s au total.
Le préflight exige RSS maximale + réserve disponibles avant de lancer le
service, avant de réchauffer le cache de fichiers par lecture des poids. Après
vérification des assets, la réserve seule est contrôlée : les pages déjà lues
appartiennent au budget de ce modèle. Le contrôle Mastra ne réserve pas à
nouveau tout le modèle déjà résident ; son superviseur conserve ses gardes.
Les appels ont un délai total de 30 s, sans reprise HTTP automatique.
Le palier 27B, conditionné au premier palier complet et aux ressources,
utilisera Q8, les mêmes corpus/contexte et une garde RSS de 32768 Mio avec la
même réserve de 8192 Mio. Aucune garde ne sera augmentée pour compléter un score.

Le superviseur démarre un groupe de processus neuf, le sonde toutes les
250 ms et arrête uniquement ce groupe à la limite ou à la fin. L'observation
RSS n'est pas un plafond instantané ni toute la mémoire GPU unifiée. Sur Mac,
la mémoire disponible est une estimation conservant les pages libres,
inactives et spéculatives, sans compter deux fois les pages purgeables ; ce
n'est pas la définition Linux de `MemAvailable`. Garder cette différence dans
les rapports. Les allocations Metal et l'offload proviennent des traces natives.

Correctifs de revue après les campagnes du 16 octobre : le répertoire de
sortie est résolu et refusé dans la stack ou le dépôt du service avant toute
création, y compris en mode smoke. Les champs d'identité du manifeste (dépôt,
commit, fichier, taille et hash) sont validés avant la lecture des poids ;
l'empreinte effective du fichier est vérifiée avant le démarrage.
Le suivi des ressources doit avoir fermé son fichier avant le scellement.
Pour Mastra natif, l'exception de réservation du modèle déjà résident exige
le scope de supervision vivant du pilote : profil/session liés, processus et
watcher actifs, groupe possédé, limites respectées et observation récente.
Un appel direct avec un profil sauvegardé est refusé ; une perte de supervision
interrompt la passe et conserve les cas restants comme manquants.
Les archives et versions de code des campagnes antérieures restent inchangées.

## Contrôles, sorties et reprise

Avant une campagne : vérifier tailles/hashes des poids et des exécutables,
faire un choix synthétique, observer les rejets d'authentification/de modèle/de
route, puis envoyer un contexte dépassant la capacité. Le pin D3 renvoie 500
avec un message explicite de dépassement du batch complet : seul ce refus
strictement reconnu devient `unsupported`. Les autres 500 restent `error`.
Aucune réponse partielle ou tronquée ne devient un choix scoré.

La passerelle ne reçoit aucun identifiant fournisseur. Une clé locale aléatoire
est transmise par environnement, jamais dans le profil ou les logs. Le client
accepte uniquement `http://127.0.0.1:<port>/v1/systemone`, sans proxy, redirection
ou DNS, et vérifie l'identité du modèle et les domaines de probabilité.
Les fichiers épinglés sont revérifiés par métadonnées avant/après chaque appel.

Chaque dossier neuf contient session/profil/catalogue, snapshots du code du
banc et du service, contrôles synthétiques, ressources, traces du vrai moteur,
campagnes `bases/` et `mastra/`, puis un sceau. Les archives de campagnes
conservent leur format et leur propre sceau. Les archives initiales ne sont
jamais réécrites. Le snapshot de code du superviseur complète séparément les
manifestes du moteur qui gardent leur champ historique `source_archive`.

Le contrôle synthétique échauffe le modèle avant les campagnes. Les latences
observées incluent le HTTP local ; elles ne sont ni une comparaison CPU/GPU
contrôlée ni un p95 produit. La présence d'une réponse ne prouve pas à elle
seule qu'un nouveau forward physique a eu lieu : le champ demeure inconnu
quand le moteur n'en fournit pas la preuve.

Un rescore se fait hors inférence dans un nouveau dossier avec le moteur
commun. Relancer le pilote crée une nouvelle session et une nouvelle archive ;
les anciens profils liés à une session arrêtée ne redémarrent aucun service.
Les défauts du socle historique observés sur Mac restent distincts des contrôles
du nouvel adaptateur et des régressions Linux. Aucun résultat historique ou
référence n'est régénéré pour faire passer les vérifications.

## Suite Q4 fixée avant ses prédictions

Après les campagnes Eos Q8 et Flash Q8 (`87259b1`), Flash Q8 a 132/132 sorties
valides, 124/132 choix corrects et 20/24 accords Mastra provisoires. Le palier
27B Q8 n'est pas admis par la réserve prévue de 40960 Mio : après Flash, les
observations disponibles sont entre environ 30 et 38 Gio, malgré les 64 Gio
physiques de la machine. Cela ne prouve pas une impossibilité du Q8 sur 64 Gio.

La suite conserve tous les cas/références et les mêmes limites de contexte :

| Variante, choisie avant toute inférence Q4 | Manifeste | RSS maximale / réserve |
| --- | --- | --- |
| Flash 9B Q4_K_M | `profiles/d3-flash-q4-assets.json` | 14336 / 8192 Mio |
| d3 27B Q4_K_M | `profiles/d3-27b-q4-assets.json` | 24576 / 8192 Mio |

Mesurer d'abord Flash Q4 face à Flash Q8 pour observer l'effet de quantification,
puis le 27B Q4. Les quantifications et pins restent explicites ; les décisions
natives et les distributions sont conservées. Le palier Q8 27B demeure `not_run`.
Les corrections de préflight évitent de compter deux fois les pages du même
modèle ; elles n'augmentent ni le plafond RSS, ni le contexte, et ne diminuent
pas la réserve de 8192 Mio du superviseur.
