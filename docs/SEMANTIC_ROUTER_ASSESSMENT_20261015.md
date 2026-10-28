# Semantic Router et Deposium — examen du 15 octobre 2026

**Tester d'abord la qualité des décisions ; évaluer le routeur séparément, hors
trafic applicatif.** La comparaison Jev/BGE sur les passages répond à la question
« ce modèle reconnaît-il mieux les preuves ? ». Semantic Router répond à
« vers quel modèle ou chemin d'exécution envoyer cette requête ? ». Le second
ne résout pas automatiquement un défaut de pertinence du premier.

## Ce que le projet apporte

[Architecture officielle](https://vllm-sr.ai/docs/overview/semantic-router-overview/)
consultée le 15 octobre : couche de décision entre clients et backends, avec
signaux, politiques, modèles candidats et recettes. La sélection logique du
modèle est distincte de l'équilibrage entre réplicas et du moteur qui génère
les réponses. Envoy porte le trafic dans l'architecture décrite pour v0.4 ;
les backends sont des services compatibles, dont des endpoints fournisseurs.
Il n'est donc pas nécessaire de remplacer tous les serveurs par vLLM.

Les familles Decision/Vela/D3 déjà testées dans notre banc sont liées à cet
écosystème. Avoir mesuré un de leurs modèles seul ne qualifie pas le logiciel
Semantic Router, ses politiques ou une intégration Deposium. Aucun routeur
n'a été installé ou exécuté dans cet examen.

Attention aux versions : le [guide d'installation sur main](https://github.com/vllm-project/semantic-router/blob/main/website/docs/installation/installation.md)
décrit aussi une architecture autonome et un runtime modèle séparé postérieurs
à la version stable 0.4.0. Avant tout essai, épingler version/image/configuration
et vérifier quelles commandes et capacités sont réellement présentes. Les
ressources de cette installation ne sont pas mesurées ici.

## Ce qui existe déjà dans Deposium

Sources locales lues, sans modification ni appel de service : MCPs
`80b7f7f64d18b47ceb91b0f8c9609d3f95823872`, inference `14e2c47`.
Ces HEAD ne prouvent pas les images ou chemins effectivement exécutés.

| Frontière | Code présent | Effet d'un routeur supplémentaire |
|---|---|---|
| Choix selon tâche | MCPs `src/config/model-router.ts:33`, `:137` : table intention × portée, overrides et fallbacks | Comparer une nouvelle politique à cette table ; éviter deux choix contradictoires |
| Transport LLM | MCPs `src/services/llm-client.ts:132` : direct ou `deposium-inference` | Choisir un point d'injection, conserver les chemins explicitement directs |
| Échecs et provenance | MCPs `src/services/llm-failover.ts:237` : bascules et modèle utilisé | Définir un propriétaire des retries/bascules, tracer le modèle final |
| Catalogue/backend | inference `src/backend/mod.rs:105`, `src/proxy.rs:19` | L'identifiant explicite désigne déjà un backend ; une sélection sémantique serait un ajout |

La branche locale MCPs mentionne même dans `llm-client.ts` une préférence pour
certains transports directs, afin d'éviter un détour vers un fournisseur plus
lent. Ajouter un proxy supplémentaire sans mesurer ce trajet pourrait annuler
une partie du gain attendu. Ce commentaire de source n'est pas une nouvelle
mesure de latence de notre part.

L'identité, les autorisations, le consentement, les limites de ressources et
l'exécution des outils restent du ressort déterministe de Deposium. Le routage
entre LLM n'est pas une validation de la sélection et de l'enchaînement des
260+ outils MCP. Un endpoint de décision Jev `/v1/systemone` n'est pas non plus
un backend de génération OpenAI compatible à brancher sans adaptation.

## Pilote proposé, sans changement produit

1. Choisir une liste finie de modèles et de localisations déjà autorisés.
   Fixer les motifs de sélection attendus : langue, domaine, besoin d'outils,
   budget, confidentialité et profondeur d'analyse.
2. Préparer un corpus de demandes représentatives et revues, avec références
   de routage et réponses finales évaluables. Le pack de quatre passages reste
   utile pour la pertinence des preuves ; il ne suffit pas à choisir le meilleur
   LLM pour une conversation complète.
3. Exécuter hors trafic la table actuelle et le véritable routeur à une version
   précise. Le [CLI officiel](https://vllm-sr.ai/docs/api/cli/) documente une
   prévisualisation de route ; vérifier son existence et ses effets sur la
   version épinglée. Aucun appel de génération lors de cette première étape.
4. Mesurer accords par scénario, couverture, abstentions, distribution des
   modèles, violations de contraintes et temps ajouté par le routeur. Les
   erreurs techniques ne deviennent pas des prédictions correctes.
5. Sur un lot borné, appeler ensuite les mêmes backends pour les deux politiques.
   Comparer qualité finale, citations/outils, coût réel et latence de bout en
   bout médiane/p95, en conservant les échecs et le modèle effectivement utilisé.

Le point d'injection sera choisi après ce pilote : autour du choix de modèle
MCPs ou devant les backends approuvés d'inference, avec un seul propriétaire de
la politique. **Pas de nouveau moteur d'inférence ou service déployé pour
l'instant.** Le bénéfice à démontrer est un meilleur compromis qualité/coût/temps
sur les demandes Deposium, supérieur au coût ajouté par cette couche.
