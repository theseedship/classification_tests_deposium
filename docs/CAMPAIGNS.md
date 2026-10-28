# Campagnes locales du banc — lot 1

Le noyau CLI/notebook nécessite Python 3.11+ et Git. Ses tests ordinaires
n'installent rien et n'appellent ni fournisseur de modèle ni service de stack.
Le corpus contient 36 cas synthétiques FR/EN, répartis entre DOC, FOLLOWUP,
PRESENTATION, SOURCES et EVIDENCE. Il mélange les splits pour ce contrôle
exploratoire; ce total n'est pas un score final sur un jeu de test indépendant.

Le [local-only material, not distributed](PROTOCOL.md) utilise une projection de 14 cas avec
assertions `/task` uniquement. Il dispose d'un runtime séparé, téléchargé
explicitement; les commandes ordinaires ci-dessous restent sans poids.
La commande `compare --baseline ARCHIVE --candidate ARCHIVE --output NOUVEAU`
compare les archives d'un replay de composant et d'un modèle isolé sans inférence.

## Contrôle sans stack

Depuis la racine du clone, choisir chaque fois une nouvelle destination :

```bash
python3 -m unittest discover -s tests -v
python3 -m deposium_bench validate-registry
python3 -m deposium_bench validate-cases
python3 -m deposium_bench run \
  --profile profiles/fixture-control.json --output results/control-001
```

Le profil contient des sorties figées écrites séparément des références :
bonnes réponses, erreurs délibérées, réponse vide et états non réussis.
**Le verdict attendu est `fail`, code de sortie 1**, avec 28 cas scorés sur 36,
21 réussis et 7 échoués. Cela vérifie le banc; ce n'est pas un modèle évalué.
Les tests de transport Node sont optionnels si Node est absent; les tests
MCPs réels ne s'activent qu'avec `DEPOSIUM_MCP_STACK_ROOT`. Les validations
JSON Schema complètes s'exécutent si `jsonschema` est déjà installé; elles
ne constituent pas une dépendance du noyau. Les skips sont affichés comme tels.

## Interrompre, reprendre, rescorrer

```bash
python3 -m deposium_bench run --profile profiles/fixture-control.json \
  --max-new-cases 4 --output results/control-partial-001
python3 -m deposium_bench resume --archive results/control-partial-001 \
  --output results/control-resumed-001
python3 -m deposium_bench rescore --archive results/control-resumed-001 \
  --output results/control-rescored-001
```

Une reprise crée une autre archive et n'appelle que les cas sans trace.
Les erreurs, timeouts, abstentions et résultats `missing` déjà enregistrés
sont conservés. Elle exige une identité d'adaptateur/runtime compatible.
Un appel interrompu avant son écriture durable peut être réexécuté : aucune
garantie d'exécution unique n'est annoncée pour ce cas.

Le rescore utilise uniquement les octets validés de l'archive : aucune
création d'adaptateur, aucun accès au checkout MCPs. La source et les sorties
brutes restent inchangées. Une trace finale tronquée ou une archive modifiée
est rejetée; elle n'est pas réparée silencieusement. Une trace durable non
scellée, interrompue avant la production du résumé, peut être reprise.

Codes CLI : `0` uniquement pour une campagne complète dont tous les cas
passent; `1` pour échec ou campagne partielle; `2` pour entrée/archive invalide
ou zéro cas scoré; `130` pour interruption clavier interceptée. La validation
du corpus réussie reste `not_run`. `--format json` affiche le résumé structuré.

## Replay MCPs explicite

Prérequis séparés : clone de la stack avec sous-module MCPs initialisé,
HEAD identique à `profiles/mcps-current.json`, Node et dépendances MCPs déjà
installées. Le banc ne fait aucun checkout, reset, installation ni démarrage.

```bash
python3 -m deposium_bench run --profile profiles/mcps-current.json \
  --stack-root /chemin/deposium_fullstack --output results/mcps-001
```

Le profil exige MCPs `391be12078b1f3daa24a50c31c3a39eb72d7fb94`.
Le bridge appelle quatre exports du checkout, un processus par cas :
`normalizeChatDocumentRequest`, `resolveDocumentFollowUp`,
`buildScopeDispatchDecision`, `resolveSemanticSourceRoute`.
Il importe le code réel et ne recopie pas les règles. Les références ne
traversent pas le transport : seuls `case_id`, `contract_id` et `input` passent.
`mcps.search` reste `unsupported` : aucun EVIDENCE n'est scoré par ce bridge.

L'inventaire Git couvre tous les sous-modules et leurs gitlinks HEAD/index,
HEAD locaux et états de travail. Le manifeste distingue composant sélectionné,
contrats supportés, cas associés et omission. Le préflight sélectionne MCPs
pour les empreintes de contrats; les autres sous-modules restent recensés.
Le SHA parent, la présence d'un bridge et un fichier source ne prouvent pas
qu'un service ou une image correspondante est exécuté.

Les empreintes du bridge, de sa fermeture d'imports revue, des lockfiles et
des fichiers installés Node/tsx/esbuild/zod sont relevées. Les sources et les
identités de fichiers runtime sont vérifiées autour des appels. Une extension
de la fermeture d'imports exige une revue avant de devenir supportée.
Le corpus est petit et le lancement d'un processus est inclus dans la durée;
ces durées ne sont pas un benchmark de latence du serveur chaud.

Un checkout sale est non canonique. Les hashes identifient les octets observés,
ils ne reconstruisent pas un WIP perdu. Les sources, bibliothèques système,
poids, images et données ne sont pas archivés. L'inventaire n'est pas atomique;
services, ACL, `/api/chat-stream`, recherche, génération, clients et persistance
restent hors de cette preuve A. Les annotations sont exploratoires, sans revue
humaine revendiquée.

## Contenu d'une archive

| Fichier | Rôle |
|---|---|
| `manifest.json` | Protocole, cas, fingerprints banc/scorer/profil/runtime, inventaire et parent éventuel |
| `cases.jsonl`, `profile.json` | Entrées exactes et références séparées de l'entrée candidat |
| `recordings.jsonl` | Copie des contrôles réellement utilisés, pour un profil figé |
| `stack-preflight.json` | Observation des sources de stack lorsqu'une racine accessible est fournie |
| `raw.jsonl` | Statut, sortie brute/normalisée, durée et hash de requête de chaque résultat durable |
| `summary.json`, `report.md` | Scores, dénominateurs, couverture par pack/langue/composant et échecs |
| `seal.json` | Empreintes des fichiers terminés; intégrité locale, pas signature d'authenticité |

`source_profile_sha256` identifie les octets du profil original;
`profile_sha256` ceux de sa copie archivée (chemin de recordings relocalisé).
Le hash du profil dans `adapter_provenance` porte sur sa représentation JSON
canonique effectivement reçue. Les références, schemas et scorers sont versionnés;
modifier une référence demande une explication et une revue, jamais un simple
ajustement au résultat observé.

Les archives et notebooks exécutés restent hors Git. Ils comportent des chemins
locaux et des entrées/sorties du corpus choisi : les relire avant tout partage.
Le [notebook](NOTEBOOK.md) appelle les mêmes fonctions du noyau et dispose d'une
vérification de parité distincte. Les [résultats locaux](LOT1_VALIDATION.md)
conservent la frontière entre test du banc, replay d'un composant et produit.
