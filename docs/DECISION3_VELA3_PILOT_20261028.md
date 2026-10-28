# Decision 3.0 et Vela 3.0 — protocole du 28 octobre 2026

Protocole fixé avant les nouvelles prédictions. Les archives et références
historiques restent conservées. L'ancien D3 classe 27B Q4 (128/132) n'est pas
D3 Ultra ; les Vela 0.3B, 0.8B et 4B mesurés sont de génération 2.0.

## Première campagne : Vela3-fast, backbone de décision seul

- Dépôt `vllm-sr/vela3-fast`, révision
  `9e338f39babc622f42e9bd8556398fe2d80d9f13`.
- `model.safetensors` : 1 521 771 272 octets, FP32, SHA256
  `2294745881d9a01b7d049133b57e5fed2aec6ae1d34ef1ab9fa16f047fc35c8e`.
  Les adaptateurs span, evidence, relation et router ne sont pas téléchargés.
- Vrai `DecisionEncoder.load` puis `predict` de la source officielle, sans
  réécriture du rendu, du readout ou de la calibration. Ce loader est aussi
  celui du moteur Decision Index livré par l'éditeur. Pas de routage natif
  Vela3Encoder revendiqué : le profil est explicitement limité à la décision.
- Mac M5 Pro 64 Gio, **CPU FP32 / SDPA**, deux threads, une requête et un modèle
  à la fois. Python 3.12.12, Torch 2.14.0, Transformers 5.17.0 et fingerprint
  complet dans `runtimes/vela3-fast/runtime.lock`, environnement local séparé.
  Le readout officiel fait `lg.double().cpu()` : Metal ne prend pas en charge
  ce FP64 sur GPU. Aucun patch amont ni repli implicite de périphérique.
- Limite locale 4096 tokens, plafond RSS du groupe 8192 Mio, réserve disponible
  estimée 8192 Mio ; admission **16384 Mio avant hash des poids**, puis réserve
  seule pendant le chargement et l'inférence. Initialisation 300 s, appel 30 s,
  budget d'observation Mastra 300 s. Gardes inchangées pendant ce lot.

Les entrées sont les mêmes **132 cas / 66 familles FR-EN** du pack
`context-choice-v1`, puis **24 observations / 12 familles** `mastra-read-pilot-v0`.
Mêmes splits, références et scorers, sans annotations dans les entrées du modèle.
Vela3-fast est annoncé anglais : présenter FR et EN séparément, le FR étant
exploratoire. Les références sont synthétiques et attendent une revue humaine ;
l'accord Mastra ne qualifie ni la sémantique ni un parcours produit.

Le contexte devient `state`, la question `instructions` et les descriptions
ordonnées les critères natifs. Les identifiants externes restent hors modèle.
L'adaptateur conserve les probabilités et le choix natifs, vérifie l'argmax,
l'ordre, la normalisation et la correspondance aux identifiants externes.
Le tokenizer et `encode` natifs donnent l'entrée sans troncature ; une sonde de
pré-forward contrôle les IDs et masques effectivement reçus par l'encodeur.
Dépassement et marqueurs réservés sont refusés avant forward. Les réponses vides,
NaN, erreurs, refus, absences et timeouts restent distincts du succès et gardent
leur dénominateur. Un chargement raté ne donne aucun score.

Avant campagne : vérification des fichiers aux hashes publiés, tests hors ligne,
puis smoke synthétique via l'adaptateur commun avec une décision et un refus
trop long, zéro cas scoré. Réseau bloqué dans le worker et imports sans poids.
CLI et notebook partagent le même moteur. Chaque exécution crée une archive
neuve avec sources, pins, entrées, sorties, métriques et sceau ; un correctif
technique ou une reprise ne remplace jamais une archive antérieure.

## Autres variantes : qualification progressive

D3 Ultra et D3 Turbo, ainsi que Vela3-lite, mini, flash, turbo et fast-vision,
restent `not_run` à l'ouverture de ce lot. Une capacité ou un résultat éditeur
n'est pas un score Deposium. Les tâches span, NER, PII, evidence et vision
nécessitent des corpus et scorers appropriés avant toute qualification.

Ultra natif représente **52 176 025 120 octets (~48,59 Gio) de poids** seuls,
avant activations et marge. Le relevé préalable du Mac estimait 28 529,9 Mio
disponibles : aucun téléchargement de ses poids n'est autorisé par ce protocole.
Une voie quantifiée doit établir son checkpoint, son readout et son runtime
réels ; l'ancien export `ggml-org/vllm-d3-GGUF` ne prouve pas le support Ultra.

## Stack et reproductibilité

La découverte courante du parent `deposium_fullstack/.gitmodules` compte
**14 sous-modules**, contre 15 dans l'instantané du 1er octobre (MindsDB absent).
Le rattachement historique des cas reste celui du registre ; l'inventaire Git
de chaque campagne distingue gitlinks et checkouts. Aucun service de ces
composants n'est nécessaire à ce test de modèle isolé.

Le service voisin `deposium-inference`, ses modifications locales, Railway,
le gitlink parent, les secrets et la stack complète ne sont pas modifiés.
Le runtime Python commun fonctionne sur CPU ; **l'inférence WSL/Linux de ce
nouveau checkpoint reste à observer**, indépendamment des tests hors ligne.
Les poids et archives privées restent hors Git ; code, profils et rapports
publics suffisent à suivre ce qui a été exécuté et ce qui ne l'a pas été.
