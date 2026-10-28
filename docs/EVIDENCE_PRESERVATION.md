# Conserver les preuves hors Git

Le push sauvegarde code, corpus publics/synthétiques, profils, schémas,
protocoles et rapports versionnés. Il ne sauvegarde **pas** `results/`,
`models/`, `.cache/`, `secrets/` ou les données privées, ignorés par Git.
Les scores agrégés dans les rapports ne remplacent pas les sorties brutes.

## À conserver après une campagne

1. Fermer les runners et kernels concernés; ne pas copier un journal pendant
   un appel en cours. Conserver les tentatives échouées et les archives dérivées.
2. Copier les archives complètes : manifestes, corpus/profil figés, raw, résumé,
   préflight éventuel et scellement. Inclure les sélections/générations utilisées
   pour les longueurs, les comparaisons, les rapports d'analyse et les preuves de
   validation. Les rapports [Julia](CONTEXT_RESULTS.md), [GLiNER](GLINER_RESULTS.md),
   [Jev](JEV_RESULTS.md) et [Indecis](INDECIS_RESULTS.md) donnent les emplacements
   et empreintes correspondants.
3. Conserver aussi le journal `results/jev-pilot-budget-001.jsonl`, avec les
   réserves non réglées. Une copie restaurée ancienne ne doit pas servir à
   reprendre des appels en oubliant des tentatives plus récentes.
4. Créer une archive de ces fichiers avec un index SHA-256, puis la copier sur
   un support durable distinct du disque/WSL à purger. Vérifier le hash après
   transfert. Une seconde copie dans le même WSL n'est pas une sauvegarde contre
   la perte de ce disque. Aucun transfert externe n'a été effectué par ce lot.
5. Restaurer dans un répertoire neuf; vérifier l'index puis les scellements
   internes. Avec la révision du banc et le scorer archivés, exécuter un
   `rescore` hors ligne dans une nouvelle sortie et comparer les scores/raw
   à l'archive source. Un scorer ultérieur peut légitimement changer les scores;
   cette comparaison constitue alors une nouvelle évaluation. Ne pas écraser
   les originaux.

Une copie de `results/` avant purge conserve les preuves locales actuelles.
Vérifier son contenu et son volume avant transfert, notamment si des campagnes
sur données privées sont ajoutées plus tard. Les notebooks exécutés et logs
appartiennent aux preuves; le notebook source reste sans sorties.

## À séparer des preuves

Les clés restent dans un stockage de secrets, hors archives de résultats et
hors publication. Les poids et runtimes peuvent être téléchargés de nouveau
à partir des révisions, manifests et locks; une copie facultative accélère la
reprise mais ne remplace pas la conservation des résultats non reproductibles
bit à bit. Ne pas inclure tout le cache dans un paquet de preuves par défaut.

## À la reprise

Lire [local-only material, not distributed](PROTOCOL.md), vérifier HEAD et l'état de travail, puis valider
le registre et les corpus. Le rescore ne demande ni poids ni accès API.
Avant un nouvel appel Jev, retrouver le journal le plus récent et son budget;
ne jamais le vider pour rendre une campagne admissible. Une nouvelle campagne
scientifique doit avoir son protocole et son budget propres annoncés.

Les chemins absolus des profils archivés décrivent la machine d'origine : ils
ne rendent pas un replay modèle directement portable. Le rescore exploite les
snapshots sans modèle. Pour une nouvelle inférence sur une autre machine,
préparer un profil distinct et une nouvelle archive, en gardant l'ancienne intacte.
