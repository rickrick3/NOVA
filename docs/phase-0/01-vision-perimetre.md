# 01 — Vision et périmètre du MVP

Statut : validé le 2026-10-09

## 1. Vision

NOVA est un assistant IA personnel qui accompagne un utilisateur sur tout le cycle de création d'un projet : idée, discussion, analyse, recherche, conception, visualisation, validation, développement, tests, amélioration.

Trois propriétés le distinguent d'un chatbot :

1. **Il produit des livrables, pas seulement des réponses.** Rapports, analyses, maquettes, scènes 3D, modifications de code et résultats de tests sont des objets persistants, versionnés et rattachés à un projet.
2. **Il agit sous contrôle.** Toute action ayant un effet hors de la conversation passe par une politique d'autorisation appliquée en code, à deux endroits (Core et agent local), et laisse une trace.
3. **Il ne prétend rien.** Une capacité absente est signalée comme absente ; un test n'est « réussi » que si son code de sortie a été observé ; une citation n'est « vérifiée » que si l'extrait figure dans la page récupérée.

L'utilisateur peut entrer à n'importe quelle étape, interrompre, changer d'avis ou revenir sur une décision. Il n'y a pas d'enchaînement imposé : les étapes sont des capacités que NOVA mobilise selon l'intention, pas un pipeline.

## 2. Utilisateur cible et hypothèses de cadrage

| # | Élément | Nature | Détail |
| --- | --- | --- | --- |
| H1 | Un seul utilisateur | Hypothèse à valider | NOVA est un assistant *personnel*. Pas de comptes multiples, de partage ni de collaboration au MVP. |
| H2 | Exécution locale d'abord | Hypothèse à valider | Core, Studio et agent tournent sur le poste de l'utilisateur. L'architecture reste compatible avec un hébergement (PostgreSQL, TLS), sans le livrer au MVP. |
| H3 | Interface en français et en anglais | Hypothèse à valider | Textes d'interface externalisés dès la Phase 1 (FR par défaut, EN disponible). |
| H4 | Au moins un fournisseur IA configuré pour un usage réel | Fait du cahier des charges | Sans fournisseur, NOVA démarre, affiche les capacités indisponibles et ne simule rien. |

Ces hypothèses conditionnent des choix d'architecture ; elles sont reprises comme décisions à valider dans [09](09-risques-decisions.md).

## 3. Comment chaque principe non négociable est garanti

Un principe qui ne repose que sur une consigne donnée au modèle n'est pas garanti. Chacun est donc adossé à un mécanisme vérifiable par un test.

| Principe du cahier des charges | Mécanisme | Où |
| --- | --- | --- |
| 1. Pas un chatbot classique | Livrables versionnés, tâches explicites, canvas, agent | [03](03-modules.md), [04](04-modele-donnees.md) |
| 2. Pas d'interface sans backend | Chaque écran du backlog a ses critères d'acceptation côté API et ses tests | [10](10-backlog.md) |
| 3. Pas d'intégration simulée | Registre de capacités : `available`, `degraded`, `unavailable`, `not_implemented`, avec raison affichée | [05](05-contrats-api.md) §2 |
| 4. Pas de fournisseur unique | Ports `ChatProvider`, `SearchProvider`, `ImageProvider` ; la logique métier ne connaît que les ports | [03](03-modules.md) §4 |
| 5. Suggestion ≠ décision | Entité `Decision` distincte ; le statut `confirmed` n'est atteignable que par une requête authentifiée de l'utilisateur | [04](04-modele-donnees.md) INV-4 |
| 6. Pas de modification silencieuse | Écriture dans un projet = classe C : diff présenté, confirmation, point de reprise git | [07](07-permissions.md) |
| 7. Pas d'action sensible sans politique | Moteur de permissions en code, appliqué par Core puis de nouveau par l'agent | [07](07-permissions.md) §5 |
| 8. Pas de recherche présentée comme exhaustive | Section « limites » du rapport générée par le code à partir des métadonnées réelles de la recherche | [03](03-modules.md) §3.7 |
| 9. Pas de test « réussi » non exécuté | Les artefacts `test_run` ne sont créés que par le système à partir du résultat renvoyé par l'agent | [04](04-modele-donnees.md) INV-5 |
| 10. Préserver l'acquis | Versions immuables, tests de non-régression, validation explicite à chaque jalon | [04](04-modele-donnees.md) INV-2, [10](10-backlog.md) |

## 4. Périmètre du MVP

Le MVP est le plus petit système qui démontre le parcours **idée → analyse → design → validation → code** de bout en bout avec de vraies intégrations.

| Module du cahier des charges | Inclus dans le MVP | Exclu ou reporté |
| --- | --- | --- |
| M1 Conversation | Discussion libre en flux continu, questions de clarification, reprise d'une conversation, indication du fournisseur utilisé | Branches de conversation, édition d'un message passé |
| M2 Analyse | Analyse structurée (reformulation, hypothèses, avantages, inconvénients, risques, contraintes, options, recommandation, étapes) ; chaque affirmation étiquetée fait vérifié, estimation ou hypothèse | — |
| M3 Recherche | Recherche via un fournisseur réel, récupération de pages, citations vérifiées par le code, rapport persistant, limites affichées | Pages nécessitant JavaScript, PDF, sites derrière authentification |
| M4 Projets et mémoire | Projets, objectifs, exigences, contraintes, mémoire à quatre catégories, décisions, consultation, modification, suppression | Recherche sémantique par embeddings (mots-clés et épinglage au MVP) |
| M5 Canvas | Scène d'artefacts typés : rapport, document, diagramme, maquette, image, scène 3D, aperçu d'application, diff, résultats de tests ; commentaires, comparaison, historique | Tableau blanc infini à positionnement libre |
| M6 Studio UI/UX | Wireframes et maquettes en HTML interactif, variantes, retours, spécification de design exploitable ; maquette approuvée = référence d'implémentation | Export vers des outils de design tiers |
| M7 2D et 3D | Diagrammes, import d'images, scène 3D paramétrique à base de primitives (rotation, zoom, déplacement, paramètres, variantes) | Génération d'images matricielles : optionnelle, selon décision D6. Modèles 3D complexes : hors périmètre |
| M8 Validation et versionnement | Identifiant stable, version, état, historique, validation liée à une version, restauration | — |
| M9 Développement | Plan, fichiers concernés, change set, autorisation, application, tests réels, diff, correction, restauration — sur un projet de test | Publication, déploiement, `git push` |
| M10 Agent local | Lecture et recherche dans les répertoires autorisés, écriture en espace dédié, commandes prédéfinies, tests, git contrôlé, arrêt et révocation | Commandes arbitraires (désactivées par défaut), contrôle souris/clavier/applications |
| M11 Voix | Ports et états d'interface prévus ; capacité déclarée `not_implemented` | Toute implémentation vocale |

**Hors périmètre du MVP, tous modules confondus :** multi-utilisateur, application mobile, microservices, exécution de tâches survivant à un redémarrage du Core (une tâche interrompue est marquée en échec et relançable), isolation par conteneur des commandes exécutées.

## 5. Critères d'acceptation finaux et preuve attendue

| # | Critère | Preuve attendue |
| --- | --- | --- |
| AC1 | Une idée peut être discutée et enregistrée dans un projet | Test de bout en bout : création de projet, échange, redémarrage du Core, historique retrouvé |
| AC2 | NOVA produit une analyse argumentée | Test de schéma sur l'analyse structurée + démonstration avec un fournisseur réel |
| AC3 | Une recherche produit des sources consultables | Rapport dont chaque citation renvoie à une source avec URL, date et extrait présent dans l'instantané |
| AC4 | Une production visuelle est affichée dans le canvas | Maquette HTML et scène 3D rendues et manipulables dans le Studio |
| AC5 | Les versions peuvent être comparées | Diff textuel renvoyé par l'API + vue côte à côte |
| AC6 | Une validation est liée à une version précise | Test : la validation porte l'identifiant et l'empreinte de la version ; modifier crée une nouvelle version non validée |
| AC7 | Le code est préparé puis modifié avec autorisation | Test : sans approbation, aucun fichier n'est modifié ; avec approbation, le change set exact est appliqué |
| AC8 | Les tests sont réellement exécutés et affichés | Artefact `test_run` portant le code de sortie et la sortie réels renvoyés par l'agent |
| AC9 | L'agent respecte les permissions | Suite de tests de la matrice : chaque action autorisée passe, chaque action interdite est refusée par l'agent lui-même |
| AC10 | Les données sont conservées et supprimables | Tests de persistance et de suppression en cascade, y compris les fichiers stockés |
| AC11 | Erreurs et indisponibilités présentées honnêtement | Tests : fournisseur absent, agent hors ligne, budget atteint → message explicite, aucun contenu inventé |
| AC12 | Scénarios critiques reproductibles | Suite automatisée exécutable sans API payante |
