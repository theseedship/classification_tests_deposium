# Pilote Jev par API

Protocole initial fixé le 2 octobre 2026 avant la première prédiction; amendement
de validation des arrondis décrit ci-dessous. Qualification :
modèle isolé, preuve A. Les composants de la stack restent reliés par le registre;
aucun service ni parcours produit n'est qualifié par ce pilote.

## Candidat et requête

Profil [jev-api-context.json](../profiles/jev-api-context.json) : version demandée
`jev-1.13.0`, vérifiée sur chaque réponse. Les alias mobiles ne sont pas utilisés.
L'identifiant publié ne donne pas accès aux poids ni à leur hash. Le client Python
standard appelle uniquement `POST https://api.typesafe.ai/v1/systemone`, en HTTPS
vérifié, sans redirection ni retry automatique. Aucun paquet externe nécessaire.

Le contexte devient `state`, la question devient `instructions` d'une unique
question `choice`, et chaque description de réponse devient une clé de `criteria`
avec valeur `null`. L'ordre des options est conservé. Les identifiants opaques,
références, annotations et splits ne sont jamais envoyés. La sortie native est
archivée et la description choisie est remappée vers l'identifiant du banc.

La clé vient uniquement de `TYPESAFE_API_KEY`. Le fichier local éventuel dans
`secrets/` est ignoré par Git; aucune clé n'entre dans les profils ou archives.
Seuls les textes synthétiques gelés sont transmis au fournisseur.

## Campagnes gelées

1. Deux premières bases pour vérifier le contrat, sans modifier les prompts.
2. Les 132 bases FR/EN, trois domaines, trois difficultés déclarées, mêmes splits.
   SHA-256 : `767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616`.
3. Les 378 variantes déjà utilisées pour Julia et GLiNER, dont 354 admissibles
   et 24 cibles de longueur irréalisables :
   `results/context-sentinels-001/lengths/cases.jsonl`, SHA-256
   `f721aec7ff08b3b4be6a2e3dcb5dd88ae2b1c0bea3a7fcf6f9ab0aefd92e492a`.
   Cibles de 100 à 8000 tokens du tokenizer de référence Julia, trois positions.
4. Temps répétés sur les 18 bases de calibration déjà sélectionnées :
   `results/context-sentinels-001/base.jsonl`, SHA-256
   `cc2e19abf97f777a762a4c685ab2a2660f02f3d158ee2dbb4fba4ef516fa7ddb`.
   Trois lancements, chacun un appel initial, cinq échauffements et trois passages
   de 18 cas : 180 appels prévus, dont 162 mesurés. Les répétitions ne créent pas
   de nouvelles familles indépendantes.

Les comparaisons utilisent les archives scellées et le scorer commun inchangé.
Rapporter exactitude, couverture, statuts et dénominateurs par domaine, langue,
difficulté, split et longueur. Il reste 66 familles pour les bases et neuf pour
les sentinelles. Ce corpus synthétique revu par agents ne fixe pas à lui seul un
seuil de bascule vers un LLM ni une décision de production.

## Ressources et observations

Le fournisseur annonce 64k tokens par requête et 32k pour l'état plus la question
la plus longue. Sans tokenizer natif ni indicateur de troncature exposé, le banc
envoie les textes complets, trace leurs hashes et conserve `usage` après l'appel;
il ne certifie pas le traitement intégral côté serveur. Les comptes Julia et
les tokens facturés par Jev restent des mesures distinctes.

`http_ms` mesure l'aller-retour client, TLS, transfert et attente compris.
Chaque appel ouvre une nouvelle connexion HTTPS; aucune réutilisation de connexion
n'est mesurée. L'échauffement ne garantit donc pas une connexion TLS chaude ni
un état particulier du serveur.
Le temps du banc inclut aussi les contrôles et la cadence. Ni le temps de calcul
serveur, ni la RAM/GPU du fournisseur ne sont observés. La campagne de temps
distante n'est pas simultanée à la campagne CPU Julia/GLiNER historique.

Un seul appel à la fois, au moins 100 ms entre départs, délai réseau nominal 30 s, corps envoyé
limité à 128 Kio. Budget partagé et durable entre campagnes, reprises et
lancements : au plus 800 tentatives et 2 000 000 tokens d'entrée réservés.
Chaque tentative réserve 65 536 tokens avant envoi; seule une réponse validée
permet de remplacer cette réserve par son usage observé. Une interruption ou
erreur ambiguë conserve la réserve complète. Le journal n'est jamais remis à
zéro par un nouveau lancement. Les erreurs fatales arrêtent les appels suivants
du candidat; les cas suivants portent des erreurs mises en cache identifiables.

Le watchdog interrompt la socket connectée et interdit l'envoi après expiration.
La résolution DNS du système, avant que cette socket soit disponible, peut
dépasser le délai nominal : le client standard ne fournit pas ici un plafond
dur de temps total en cas de panne du résolveur.

Au tarif publié de 0,042 USD par million de tokens d'entrée, ce plafond équivaut
à 0,084 USD. Il s'agit d'une garde locale selon la comptabilité documentée,
pas d'un plafond de facturation imposé au compte fournisseur. Aucun crédit gratuit
ni solde n'est supposé. Les sorties sont annoncées gratuites.

## Reproduction

Après avoir fourni la clé dans l'environnement, lancer explicitement :

```bash
python3 -m deposium_bench run --dataset datasets/context-choice-v1/cases.jsonl --profile profiles/jev-api-context.json --output results/context-base-jev-NEW --stack-root ../deposium_fullstack
```

Ne pas supprimer le journal pour poursuivre une campagne qui a épuisé son budget.
Les tests ordinaires utilisent des transports simulés et n'appellent aucun service.

Sources consultées : [API](https://docs.typesafe.ai/api),
[modèles et tarifs](https://docs.typesafe.ai/models),
[choix](https://docs.typesafe.ai/primitives/choice),
[données](https://docs.typesafe.ai/legal).

## Amendement après le premier passage

La campagne `context-base-jev-001` a reçu 65 réponses valides, puis une réponse
HTTP 200 rejetée par le client : 66 cas suivants n'ont plus appelé l'API.
Cette archive conserve 59 réussites sur 65 cas scorés, sur 132 prévus. Le corps
rejeté initial n'avait pas été retenu, uniquement son hash. Un appel diagnostique
distinct, compté dans le même budget, a reproduit un rejet avec une somme de
probabilités de 0,99. Le [SDK officiel](https://github.com/typesafe-ai/typesafe-sdk-python/blob/main/src/typesafe_sdk/_schemas/models.py)
décrit une somme approximative; le [provider Vercel épinglé](https://github.com/vercel/ai/blob/5b8e63bad8209a8e86c1de8d352daaf3c14e2671/packages/typesafe-ai/src/typesafe-ai-evaluation-model.ts)
documente les probabilités affichées à deux décimales. Sa
[documentation](https://ai-sdk.dev/providers/ai-sdk-providers/typesafe-ai#rounded-values-and-confidence)
précise explicitement que leur somme peut différer de 1.

Le contrôle initial à `1e-5` était donc trop strict. Lorsqu'elles sont toutes
sur la grille du centième, le client accepte désormais l'erreur cumulée
d'arrondi `0,005 × nombre d'options`, avec epsilon numérique. Il conserve
les probabilités natives sans renormalisation, leur somme, la tolérance et
l'hypothèse d'arrondi. Hors de cette grille, la tolérance reste `1e-5`.
Valeurs non finies, hors [0,1], options manquantes et choix hors argmax restent
refusés. Les corps JSON valides et sans secret sont désormais conservés même
lorsque la validation de leur contrat échoue.

Le prompt, les corpus, les choix et le scorer ne changent pas. La campagne
complète suivante utilise une nouvelle archive `context-base-jev-002`; aucune
ancienne trace n'est réécrite ou réparée. Les deux tentatives non réglées dans
le journal conservent chacune leur réserve de 65 536 tokens.
