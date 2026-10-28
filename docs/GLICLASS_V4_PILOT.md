# Pilote GLiClass v4 9B — 17 octobre 2026

Protocole fixé avant les premières prédictions. Modèle isolé, mêmes 132 bases
FR/EN (66 familles) et 24 propositions Mastra (12 familles), mêmes références,
splits et scorers que les campagnes précédentes. Références à revoir humainement,
zéro cas Mastra sémantiquement qualifié. Aucun outil ni parcours produit exécuté.

## Identités et ressources

- Modèle `knowledgator/gliclass-v4-9b`, commit
  `14d11a92b5e0bab4a166e1fce4cc0777cac27182` ; poids d'environ 17,97 Go,
  SHA-256 `c457f1e8f9c01b5d233eba5858f9985341e49492144982deab3b10e416b961e4`.
- Code officiel `Knowledgator/GLiClass`, commit
  `6a00f8067648f25aa0f4f477d167c5f391cb4165`, version 0.1.21.
- Python 3.12.12, Torch 2.14.0, Transformers 5.19.0 ; environnement isolé
  audité dans `runtimes/gliclass/runtime.lock`. Ce fingerprint contient Python
  et ne constitue pas directement une commande pip. Pas d'installation globale.
- M5 Pro 64 Gio, PyTorch MPS BF16, attention `eager`, deux threads CPU pour
  l'orchestration, un modèle et une requête à la fois. Contexte local 4096.
- Garde RSS du groupe de processus 32768 Mio, réserve estimée 8192 Mio ;
  admission 40960 Mio avant hash des poids, puis réserve seule pendant le
  chargement et l'inférence. Initialisation 300 s, appel 30 s, passe Mastra 300 s.
  Les gardes ne seront pas relevées pour compléter un score.

Une sonde matricielle MPS/BF16 a réussi ; elle ne qualifie pas le forward du 9B.
Un smoke synthétique doit vérifier le chargement, une sortie valide et le refus
d'une entrée trop longue avant les campagnes. Un échec reste archivé, sans score.
Le premier transfert Xet a échoué sur une résolution DNS ; une reprise HTTP a
conservé la même révision et les mêmes fichiers. Aucun 27B téléchargé.

## Projection et intégrité

L'adaptateur stdlib appelle un worker isolé, sans chargement à l'import. Le
worker appelle `GLiClassModel` et `ZeroShotClassificationPipeline` officiels :
`context` devient le texte, `question` le prompt et les descriptions ordonnées
deviennent les labels. Les IDs, annotations et réponses attendues ne sont pas
fournis au modèle. `single-label` avec `return_hierarchical=True` expose les
probabilités natives ; le banc ne reconstruit pas de confiance artificielle.
Calibrateur et récurrence restent ceux du checkpoint.

Le pipeline officiel peut tronquer le contexte pour réserver les labels. Le
worker construit donc l'entrée avec les vrais helpers/tokenizer sans troncature,
refuse les dépassements et marqueurs réservés, compare les IDs préparés et
vérifie les IDs/masques réellement reçus par le décodeur au forward. Une altération
ne devient pas une réponse scorée. Probabilités, ordre des labels et argmax
sont contrôlés ; vide, NaN, erreur, timeout et refus restent distincts.

Le périphérique est un objet `torch.device('mps')` : le code épinglé ferait
retomber une simple chaîne `"mps"` sur CPU. Les paramètres et le périphérique
effectifs sont contrôlés, avec repli MPS vers CPU désactivé. Tokenization et
audit des sorties utilisent le CPU ; cela ne signifie pas repli du forward.
Réseau bloqué dans le worker, snapshot local vérifié, aucun téléchargement à
l'import, dans les tests ordinaires ou pendant l'inférence.

Le suivi mémoire ne mesure pas un pic absolu de toute la mémoire unifiée.
RSS du groupe et allocations PyTorch échantillonnées restent séparés ; ne pas
les additionner. Les durées synchronisent MPS, mais les passages uniques restent
des observations descriptives, sans p95 produit ni comparaison matérielle contrôlée.

## Périmètre et reproduction

Les poids et fichiers privés restent dans `models/` et `results/`, hors Git.
Le préparateur vérifie les tailles et hashes publiés à la révision épinglée :

```bash
python3 scripts/prepare-gliclass-assets.py \
  --model-dir models/gliclass-v4-9b-14d11a9 \
  --metadata results/model-9b-blobs.json \
  --output profiles/gliclass-v4-9b-assets.json
```

Les CLI `run` et `observe-mastra-read` utilisent le même adaptateur et moteur
que le notebook ; pas de seconde implémentation de campagne. Chaque lancement
a un dossier neuf, des sorties brutes et un sceau. Sources du banc, du worker,
du modèle et du runtime sont identifiées avant les campagnes ; une correction
technique ultérieure crée une nouvelle archive sans écraser la première.

Cette première voie GLiClass qualifie seulement Mac/MPS si le smoke et les
campagnes réussissent. Linux/WSL et CUDA restent à qualifier séparément ;
l'API du banc et les données restent communes. Ce checkpoint possède une tête
decoder-KV GLiClass ; notre llama.cpp D3 n'en est pas un backend établi.
Le service `deposium-inference`, son catalogue, Railway et les gitlinks restent
inchangés ; aucune stack complète ou BDD n'est nécessaire à ce lot.

La [fiche épinglée](https://huggingface.co/knowledgator/gliclass-v4-9b/blob/14d11a92b5e0bab4a166e1fce4cc0777cac27182/README.md)
annonce des résultats sur d'autres protocoles et du matériel NVIDIA. Elle ne
mesure pas notre split FR/EN ni une victoire sur D3. Le résultat du banc reste
`not_run` jusqu'aux captures réelles, indépendamment des scores publiés.
