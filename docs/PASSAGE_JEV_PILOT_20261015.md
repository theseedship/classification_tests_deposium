# Passages multilingues — campagne Jev API du 15 octobre 2026

Protocole fixé avant tout appel de cette campagne. L'utilisateur demande un
nouvel essai API après le résultat D3-lite. Candidat : **`jev-1.14.0`**, publié
le 14 octobre selon la [documentation TypeSafe](https://docs.typesafe.ai/models)
consultée le 15 octobre. La référence historique `jev-1.13.0` reste inchangée ;
les scores de ces deux versions ne sont pas fusionnés.

## Entrées et comparaisons

Réutiliser le corpus `7ed178d` sans changer ses références : SHA-256
`35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476`.
Le plan physique est exactement celui de D3-lite : **128 cas test rotation 0,
huit familles, huit directions, deux vues ; 1 408 choix logiques et 728 appels
physiques uniques**, tous axes compris. Les labels, annotations, familles et
identifiants de passage/cas ne sont pas transmis dans le contenu d'inférence.
L'adaptateur HTTP existant projette uniquement le contexte, la question et les
descriptions d'options vers le contrat `choice` officiel ; aucun prompt modifié
pour Jev, aucune instruction tirée des réponses attendues.

Le classement principal sera calculé sur **les 512 cas test et les quatre
rotations à poids égal**, en réattribuant les 264 jugements de pertinence
strictement identiques à leurs entrées archivées, comme pour D3-lite. Aucun
nouvel appel sur les rotations. Soutien et réponse possible restent évalués
seulement sur les 128 cas initiaux. Comparer BGE CPU, D3-lite, Jev seul et Jev
puis BGE pour départager les grades. Garder aussi les contrôles sans modèle et
les dénominateurs non définis ; ne pas utiliser la rotation 0 seule pour conclure.

Réutiliser les captures BGE natives 002/003 et les producteurs/scorers communs,
sans nouvel appel au service actif ni copie d'algorithme. Références et
traductions synthétiques non revues humainement, huit familles test seulement.
Ce pilote ne qualifie ni documents réels ni réponses finales ou parcours chat.

## Transport, coûts et secrets

Profil public : [jev-api-passage-v114.json](../profiles/jev-api-passage-v114.json).
Transport existant HTTPS vérifié, endpoint `POST /v1/systemone`, version exacte
vérifiée à chaque réponse. Un appel à la fois, délai nominal 30 s, intervalle
minimum 100 ms, aucun retry ni redirection. Corps client limité à 128 Kio.
L'option `--allow-remote` doit être explicite. Les imports et tests ordinaires
n'appellent pas l'API.

Nouveau budget **de cette nouvelle version et campagne**, distinct du pilote
1.13 du 2 octobre : **728 tentatives et 2 000 000 tokens d'entrée**, journal
durable `results/jev-passage-budget-20261015-001.jsonl` dans le checkout
principal. Toutes reprises utilisent ce même chemin absolu, sans suppression,
réinitialisation ou changement de politique. Le journal historique reste intact :
759/800 tentatives utilisées, 1 324 679 tokens comptés avant ce lot ; ses
41 tentatives restantes ne sont pas présentées comme suffisantes pour ce plan.
Un profil d'exécution privé rebascule uniquement le chemin du journal vers ce
chemin absolu, afin d'éviter des budgets distincts entre worktrees.

Chaque tentative réserve 65 536 tokens avant envoi ; une réponse validée remplace
cette réserve par son usage déclaré. Un échec ambigu conserve sa réserve et
arrête la suite. Une campagne partielle reste scellée, avec manquants/erreurs
séparés, sans exporter un score de campagne complète.

Tarif publié : **0,042 USD / million de tokens d'entrée**, sorties gratuites.
Le plafond local de tokens représente **0,084 USD** à ce tarif. Il ne constitue
pas une limite de facturation du compte fournisseur. Rapporter usage déclaré,
réserves non réglées et coût calculé séparément ; aucun crédit disponible supposé.
La clé locale ignorée par Git n'entre que dans `TYPESAFE_API_KEY` du processus,
jamais dans les arguments, profils, archives ou logs. Seuls les textes synthétiques
publics du pack sont envoyés ; aucun document privé de Deposium.

## Mesures et arrêt

Conserver chaque réponse brute valide et sa filiation avec l'entrée, les temps
client, le modèle effectivement renvoyé, l'usage et les erreurs. Journaliser et
sceller aussi une indisponibilité de clé ou du modèle, sans retry automatique.
Le temps HTTP inclut réseau/TLS/file d'attente ; la RAM et le temps de calcul
serveur ne sont pas observés. Les sommes par pool sans cache sont des projections,
pas la mesure d'un pipeline Jev+BGE intégré. Limite murale 2 400 s ; réserve
mémoire hôte de 4 Gio, distincte de la RAM serveur inconnue. Aucun seuil relevé
après prédiction, aucune calibration sur les résultats test.

Exporter classement par rotation/langue/scénario/vue, capture des ensembles
suffisants, matrices de soutien et réponse possible, précision des appuis et
réfutations, faux conflits et cas insuffisants acceptés. Un gain sur les seules
classes ne prouve pas un gain sur les réponses finales.

Commande, après chargement privé de la clé et préparation du profil absolu :

```bash
python3 -B -m deposium_bench.passage_observation choice \
  --profile results/passage-jev-preflight-20261015/jev-local-profile.json \
  --output results/passage-jev-api-20261015-001 \
  --allow-remote --max-seconds 2400 \
  --stack-root ../deposium_fullstack
```

Lancer depuis le checkout de la branche portant ce protocole, avec chemins
absolus vers le répertoire `results/` principal si nécessaire. Le profil seul
ne lance rien ; un dossier de sortie doit être neuf. État initial : `not_run`,
zéro appel et zéro cas scoré pour Jev 1.14 sur ce corpus.

## Amendement du contrôle numérique et reprise, après 104 appels

L'archive `passage-jev-api-20261015-001` reste scellée et incomplète : 103
réponses valides, puis HTTP 200 rejeté par `jev_response_invalid`. La probabilité
du choix renvoyé vaut `0.45999999999999996`, pour un maximum publié `0.46`.
L'égalité stricte du client rejetait cet écart d'un ULP, sans désaccord sémantique
d'argmax. Le correctif accepte au plus **quatre ULP du maximum**, avec tolérance
relative nulle ; il ne reprend pas la tolérance d'arrondi au centième de la
somme des probabilités. Un test accepte ce cas et continue à rejeter un gagnant
inférieur de `1e-10` ou `0.01`. Aucune probabilité, option, référence, consigne,
limite de ressources ou politique de budget n'est changée.

Une reprise explicite crée une **nouvelle archive**, liée au sceau de la première.
Les 104 entrées reçues doivent correspondre exactement au préfixe du plan et au
même profil/version/journal. Le validateur de l'adaptateur revalide hors réseau
leur résultat natif conservé ; la trace d'origine reste intacte. La nouvelle
archive marque chaque héritage et conserve les IDs de tentative ainsi que leurs
temps d'origine. Aucun nouveau forward pour ces 104 entrées. Les **624 entrées
restantes seulement** sont envoyées, avec le même journal et le plafond total de
728 tentatives. L'erreur initiale n'est pas réessayée ; sa réponse reçue est
revalidée hors ligne dans une trace dérivée distincte.

La réserve de 65 536 tokens de la réponse initialement rejetée reste non réglée
dans le journal : ne pas modifier rétroactivement la comptabilité. Le rapport
sépare usage natif déclaré et consommation conservatrice du budget. La réussite
d'une nouvelle campagne ne transforme pas la première archive en campagne complète.
