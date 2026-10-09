# 10 — Backlog initial

Statut : validé le 2026-10-09

## 1. Règles communes

**Un récit est terminé quand :**

1. ses critères d'acceptation sont couverts par des tests automatisés qui passent ;
2. la suite complète passe, sans API payante ;
3. le schéma OpenAPI et les types du Studio sont à jour ;
4. les limites connues sont documentées ;
5. les fichiers modifiés et les résultats réels des tests t'ont été présentés.

**Une phase est terminée quand** tous ses récits le sont, que son critère de sortie a été démontré, et que tu l'as validée explicitement. Aucune phase ne commence sans la validation de la précédente.

**Ordre d'exécution recommandé :** 0, 1, 2, 3, 5, 4, 6 — voir la décision D3 dans [09](09-risques-decisions.md). La numérotation des phases reste celle du cahier des charges.

Les modules cités sont ceux de [03](03-modules.md) ; `studio` désigne le Web Studio, `nova_agent` l'agent et `nova_protocol` le paquet partagé.

## 2. Préalables

| # | Préalable | Critère |
| --- | --- | --- |
| PRE-1 | Espace disque (point bloquant B1) | Au moins 2 Go libres avant le plan 1A ; au moins 10 Go avant le plan 1D |
| PRE-2 | Dépôt git (point bloquant B2) | `NOVA` a son propre dépôt ; la Phase 0 y est le premier commit |
| PRE-3 | Décisions D1, D2 et D7 | Validées ou explicitement laissées à leur valeur par défaut |

## 3. Phase 1 — NOVA Core

Critère de sortie : une conversation peut être enregistrée, reprise et utilisée pour analyser une idée.

La Phase 1 est livrée en quatre plans d'implémentation. Chacun produit un logiciel qui fonctionne et se teste seul ; chacun est rédigé une fois le précédent terminé, à partir du code réellement écrit.

| Plan | Contenu | Récits |
| --- | --- | --- |
| 1A — Socle du Core | Gabarit, persistance, stockage, audit, authentification, projets, registre de capacités | P1-01, P1-02, P1-03, P1-04, socle de P1-12 |
| 1B — Fournisseurs et conversations | Couche fournisseurs, routeur, Ollama, adaptateur cloud, conversations en flux, tâches | P1-05, P1-06, P1-07, P1-08 |
| 1C — Analyse et mémoire | Outils de l'orchestrateur, clarification, analyse structurée, mémoire, décisions, capacités réelles | P1-09, P1-10, reste de P1-12 |
| 1D — Studio | Coquille de l'interface, parcours de bout en bout | P1-11 |

**P1-01 — Gabarit du dépôt et outillage** · modules : tous

- Les espaces de travail `uv` et `npm` s'installent à partir des fichiers de verrouillage.
- Une commande lance la suite Python, une autre la suite du Studio ; les deux se terminent sans échec.
- `GET /api/v1/system/health` répond.
- Un test d'architecture échoue si un module importe les tables d'un autre ou si un module autre que `providers` importe un SDK de fournisseur.

**P1-02 — Persistance et migrations** · modules : `storage`

- Les migrations s'appliquent sur une base vide et se défont sans erreur.
- Un fichier stocké deux fois n'occupe qu'un emplacement ; il disparaît du disque quand plus rien ne le référence.

**P1-03 — Authentification locale et sessions** · modules : `identity`, `audit`

- Le compte se crée une fois ; une seconde tentative est refusée.
- Une requête modifiante sans jeton CSRF, ou avec une origine étrangère, est refusée.
- Une requête dont l'en-tête `Host` n'est pas attendu est refusée.
- Au-delà du débit autorisé, les tentatives de connexion reçoivent `rate_limited`.

**P1-04 — Projets** · modules : `projects`

- Créer, lire, modifier, archiver, supprimer un projet.
- Ajouter, confirmer et supprimer objectifs, exigences et contraintes ; un élément proposé par NOVA reste non confirmé tant que l'utilisateur ne l'a pas confirmé.
- Le projet « espace libre » existe après l'installation.

**P1-05 — Couche fournisseurs, routeur et fournisseur local** · modules : `providers`

- `FakeChatProvider` rejoue un scénario déterministe : fragments, appels d'outils, erreurs, délai.
- `OllamaProvider` dialogue avec le serveur local ; son test réel porte le marqueur `live`.
- Pour un projet `local_only`, le routeur ne retient jamais un fournisseur cloud, même si le fournisseur local est indisponible (INV-10).
- Sans fournisseur admissible, l'erreur `capability_unavailable` porte la contrainte en cause.
- Les erreurs réessayables sont retentées dans la limite configurée ; les autres ne le sont pas.
- Chaque appel crée un enregistrement d'usage ; un plafond atteint bloque les appels cloud avec `budget_exceeded`.
- Une mesure est produite sur ce poste pour chaque modèle local : délai avant le premier fragment, débit, part d'appels d'outils valides.

**P1-06 — Premier fournisseur cloud** · modules : `providers` · dépend de D2

- L'adaptateur passe la même suite de contrat que `FakeChatProvider`, avec un transport simulé.
- Un refus du fournisseur est rapporté comme tel à l'utilisateur.
- Un test de fumée `live` existe et ne s'exécute que sur demande.
- La clé n'apparaît dans aucune réponse d'API, aucun journal, aucun événement.

**P1-07 — Conversations en flux, persistance et reprise** · modules : `conversations`, `orchestrator`, `events`

- Envoyer un message répond `202` ; la réponse arrive par fragments sur le flux d'événements.
- Après un redémarrage du Core, l'historique est intact et la conversation reprend avec son contexte.
- Après une coupure du flux, le client rattrape les événements manqués sans doublon.
- Chaque réponse porte le fournisseur, le modèle et la raison du routage.
- Les messages sont en ajout seul (INV-9).
- Une conversation appartient toujours à un projet ; elle peut être déplacée de l'« espace libre » vers un autre (INV-12).

**P1-08 — Tâches, progression et annulation** · modules : `tasks`, `events`

- Toute transition hors de la table est refusée avec `invalid_state_transition` (INV-11).
- Annuler un tour en cours interrompt la génération ; la tâche passe à `cancelled`.
- Une tâche en cours au moment d'un arrêt du Core est retrouvée à l'état `failed`, raison `interrupted`.

**P1-09 — Clarification et analyse structurée** · modules : `orchestrator`, `conversations`, `permissions`

- Chaque appel d'outil passe par le moteur de permissions. À ce stade seuls des outils de classe A existent ; tout autre appel est refusé et journalisé.
- `ask_user` affiche une question structurée ; la tâche attend en `to_qualify`.
- Une analyse contient les neuf rubriques du module 2.
- Chaque affirmation porte l'étiquette `verified_fact`, `estimate` ou `assumption` ; un `verified_fact` sans référence de source est rejeté par le schéma.
- Si le modèle retenu ne gère pas les outils, le tour se déroule sans outil et le Studio l'indique.

**P1-10 — Mémoire et décisions** · modules : `memory`

- Consulter, corriger, épingler, archiver, supprimer un élément de mémoire.
- Le contexte d'un tour présente séparément décisions confirmées, éléments épinglés et éléments retrouvés.
- Une décision proposée par NOVA reste `proposed` ; seule la route de confirmation, appelée par l'utilisateur, la rend `confirmed` (INV-4).
- Revenir sur une décision confirmée la passe à `revoked` et en garde la trace.

**P1-11 — Studio : coquille** · modules : `studio`

- Navigation par projets et conversations, fil de discussion, zone de tâches, état des capacités.
- Tout le parcours est utilisable au clavier ; les états de chargement et d'erreur sont affichés.
- L'interface est disponible en français et en anglais.
- Une capacité indisponible est visible comme telle, avec sa raison.
- Bout en bout : créer un projet, envoyer un message, recharger la page, retrouver l'échange.

**P1-12 — Capacités et journal d'audit** · modules : `audit`, `providers`

- `GET /system/capabilities` reflète l'état réel : fournisseur arrêté, clé absente, agent non connecté.
- Aucune route ne permet de modifier ou de supprimer un événement d'audit (INV-8).

## 4. Phase 2 — Recherche

Critère de sortie : un rapport contient des références vérifiables et peut être consulté ultérieurement.

**P2-01 — Fournisseur de recherche** · modules : `providers` · dépend de D4

- `FakeSearchProvider` pour les tests ; une implémentation réelle avec test `live`.
- Sans fournisseur configuré, `research.search` est `unavailable` et la demande de recherche l'explique.

**P2-02 — Récupération de pages sécurisée** · modules : `research`

- Les adresses privées, de bouclage et les schémas autres que `http` et `https` sont refusés, y compris après redirection.
- Taille et durée sont bornées ; le dépassement est rapporté.
- Une page non extractible est marquée en échec avec sa raison.

**P2-03 — Sources et instantanés** · modules : `research`, `storage`

- Chaque source conserve son URL, sa date de récupération, son empreinte et son texte extrait.
- Une source reste consultable après la fin de la recherche.

**P2-04 — Socle des artefacts** · modules : `artifacts`

- Créer un artefact avec une première version ; créer la version suivante ; lire le contenu.
- Le contenu d'une version sortie de `draft` et `in_progress` ne peut plus être modifié (INV-2).

**P2-05 — Recherche et rapport cité** · modules : `research`, `orchestrator`, `tasks`

- Une recherche est une tâche dont la progression est visible.
- Une citation n'est `verified` que si son extrait figure dans l'instantané (INV-6) ; les autres sont affichées `unverified`.
- La section « limites » est produite par le code à partir des requêtes lancées, des pages obtenues et des échecs.
- Le rapport est un artefact `report` enregistré dans le projet.
- Un fait tiré d'une source peut être mémorisé comme `source_fact` relié à cette source (INV-13).

**P2-06 — Contenu non fiable** · modules : `orchestrator`, `permissions`

- Une page contenant une instruction hostile ne peut déclencher aucune action de classe B ou C sans approbation : jeu de pages piégées en test.
- Un tour qui a lu du contenu Web est marqué contaminé ; les autorisations permanentes n'y sont pas appliquées.

**P2-07 — Studio : recherche** · modules : `studio`

- Lancer une recherche, suivre sa progression, lire le rapport, ouvrir chaque source et son extrait.
- Les citations non vérifiées et les limites sont visibles sans action de l'utilisateur.

## 5. Phase 3 — Canvas et création

Critère de sortie : une maquette peut être comparée, modifiée et validée.

**P3-01 — Scène du canvas et moteurs de rendu de base** · modules : `studio`

- Le canvas affiche l'artefact sélectionné, lié à la conversation et au projet.
- Moteurs `markdown` et `diagram` ; un type sans moteur affiche un message explicite.

**P3-02 — Wireframes et maquettes interactives** · modules : `artifacts`, `orchestrator`, `studio`

- NOVA produit un wireframe puis une maquette en HTML autonome, avec sa spécification de design.
- L'aperçu est interactif dans un cadre isolé : un test vérifie qu'il n'accède ni aux cookies, ni au stockage, ni au réseau.
- Plusieurs variantes d'une même maquette peuvent coexister.

**P3-03 — Cycle de validation** · modules : `artifacts`

- Soumettre, valider, demander des modifications.
- Une validation porte l'identifiant et l'empreinte de la version ; elle est refusée si le contenu affiché n'est plus celui de la version (INV-3).
- Un artefact n'a jamais deux versions `approved` (INV-1).
- Modifier une version validée crée une nouvelle version, non validée.

**P3-04 — Comparaison de versions** · modules : `artifacts`, `studio`

- L'API renvoie le diff unifié de deux versions pour les formats textuels.
- Le Studio affiche deux versions côte à côte, rendu et source.

**P3-05 — Commentaires** · modules : `artifacts`, `studio`

- Commenter une version, avec ou sans ancre ; résoudre un commentaire.
- Les commentaires ouverts sont transmis à NOVA lors d'une demande de révision.

**P3-06 — Restauration** · modules : `artifacts`

- Restaurer une version en crée une nouvelle, identique, à l'état `in_review` ; aucune version n'est modifiée ni supprimée.

**P3-07 — Scène 3D paramétrique** · modules : `artifacts`, `studio`

- Une scène décrite par primitives s'affiche ; rotation, zoom et déplacement fonctionnent.
- Modifier un paramètre met la scène à jour ; l'enregistrer crée une version.
- L'export glTF n'est proposé que si son test d'export et de relecture passe.

**P3-08 — Images** · modules : `artifacts`, `providers`, `studio`

- Importer une image comme artefact, avec sa provenance.
- La génération d'images n'existe que si D6 est tranchée en ce sens ; sinon `image.generate` reste `unavailable`.

**P3-09 — Exports** · modules : `artifacts`

- Markdown pour rapports et documents, SVG pour diagrammes, HTML pour maquettes, PNG pour une capture de scène.
- Un format non pris en charge pour un type est refusé avec un message explicite.

## 6. Phase 5 — Agent local

Critère de sortie : les actions autorisées fonctionnent et les actions interdites sont bloquées.

**P5-01 — Paquet du protocole** · modules : `nova_protocol`

- Modèles de tous les messages ; fonction d'empreinte d'action.
- Un jeu de cas partagé est exécuté à l'identique côté Core et côté agent.

**P5-02 — Appairage et session authentifiée** · modules : `agent_gateway`, `nova_agent`

- Un code expiré ou déjà utilisé est refusé.
- Une signature invalide, d'un côté comme de l'autre, ferme la connexion.
- L'agent refuse une URL en clair vers une adresse qui n'est pas de bouclage.

**P5-03 — Politique locale et chemins** · modules : `nova_agent`

- Les cas du protocole §8 sont tous testés : remontée, lien symbolique, jonction, chemin absolu, UNC, casse, motif interdit.
- Un répertoire inconnu de la politique est refusé même si le Core le demande.

**P5-04 — Actions sur les fichiers** · modules : `nova_agent`

- Lister, lire, chercher dans un répertoire autorisé.
- Écrire dans l'espace dédié ; toute écriture ailleurs par `fs.write` est refusée.

**P5-05 — Commandes prédéfinies** · modules : `nova_agent`

- Une commande déclarée s'exécute et renvoie code de sortie, durée et sortie en flux.
- Un identifiant inconnu, un argument hors motif ou une tentative d'injection est refusé.
- Le dépassement de durée et l'annulation arrêtent le processus et ses descendants.

**P5-06 — Git contrôlé** · modules : `nova_agent`

- État, diff, journal, point de reprise, commit sur une branche `nova/`, restauration.
- Toute opération de la liste des refus est rejetée.

**P5-07 — Arrêt, révocation, journal local** · modules : `nova_agent`, `agent_gateway`

- `stop` et `revoke` fonctionnent sans le Core.
- Un agent révoqué depuis le Studio ne peut plus se reconnecter.
- Chaque commande reçue figure au journal local avec sa décision.

**P5-08 — Moteur de permissions complet** · modules : `permissions`, `audit`, `agent_gateway`

- Chaque ligne de la matrice a un test autorisé et un test refusé.
- Une approbation ne sert qu'une fois et seulement pour l'action dont elle porte l'empreinte (INV-7).
- Une autorisation permanente ne peut être créée que pour la classe B ; elle est révocable.
- Chaque ligne de l'agent est testée contre l'agent seul : il refuse même si le Core laisse passer.

**P5-09 — Studio : autorisations et agent** · modules : `studio`

- Une demande présente action, éléments concernés, conséquences, risques, retour arrière et origine.
- Appairer, voir l'état, arrêter et révoquer un agent.
- Consulter le journal d'audit et les autorisations permanentes.

## 7. Phase 4 — Développement

Critère de sortie : le système peut implémenter une version approuvée dans un projet de test et présenter les différences.

**P4-01 — Plan d'implémentation** · modules : `devflow`, `orchestrator`

- Le plan part d'une version `approved` et la référence explicitement.
- Il contient exigences, architecture proposée, étapes et fichiers concernés.

**P4-02 — Exploration du projet cible** · modules : `devflow`, `agent_gateway`

- NOVA lit et cherche dans le projet de test par l'agent ; chaque lecture figure parmi les étapes de la tâche.
- Le contenu des fichiers n'est transmis à un fournisseur cloud que si le projet et l'autorisation le permettent.

**P4-03 — Préparation d'un change set** · modules : `devflow`, `artifacts`

- Un change set est un artefact `change_set` : opérations par fichier, empreintes attendues, diff.
- Sa préparation n'écrit rien sur le disque.

**P4-04 — Application sous autorisation** · modules : `devflow`, `permissions`, `agent_gateway`

- Sans approbation, aucun fichier du projet n'est modifié.
- Seul un change set `approved` peut être appliqué (INV-14).
- Un point de reprise est créé avant l'application.
- Si un fichier a changé depuis la préparation, l'application est refusée sans rien modifier.

**P4-05 — Exécution réelle des tests** · modules : `devflow`, `artifacts`

- Les tests sont lancés par l'agent ; l'artefact `test_run` porte le code de sortie et la sortie réels.
- Aucun outil du modèle ne peut créer ou modifier un `test_run` (INV-5).
- Une tâche de développement ne passe pas à `in_review` sans exécution de tests rattachée.

**P4-06 — Correction et restauration** · modules : `devflow`

- Un échec de test est présenté tel quel ; NOVA peut proposer un nouveau change set.
- La restauration ramène les fichiers à l'état du point de reprise, vérifié par empreinte.

**P4-07 — Studio : développement** · modules : `studio`

- Vue des différences, résultats de tests avec sortie complète, bouton de restauration.

## 8. Phase 6 — Parcours complet

Critère de sortie : le parcours idée → analyse → design → validation → code est démontré de bout en bout.

**P6-01 — Scénario de bout en bout** · modules : tous

- Un test Playwright déroule : idée, analyse, maquette, validation, plan, change set, approbation, application, tests, diff — avec de faux fournisseurs et un agent réel sur un projet de test.

**P6-02 — Erreurs et interruptions** · modules : tous

- Fournisseur indisponible, agent déconnecté en cours de commande, budget atteint, annulation, redémarrage du Core : chaque cas aboutit à un état cohérent et à un message exact.

**P6-03 — Revue de sécurité** · modules : `permissions`, `nova_agent`, `research`

- Matrice de permissions, jeu de pages piégées, validation des chemins et isolation des aperçus rejoués et consignés.

**P6-04 — Suppression et export des données** · modules : `projects`, `storage`, `audit`

- Supprimer un projet retire toutes ses données et ses fichiers ; le journal d'audit en garde la trace sans contenu.
- Un projet peut être exporté en archive.

**P6-05 — Démonstration avec fournisseurs réels** · modules : tous

- Le parcours est rejoué avec le fournisseur configuré ; les tests `live` sont exécutés.
- Un compte rendu liste ce qui a fonctionné, ce qui a échoué et les limites constatées.

**P6-06 — Préparation de la voix** · modules : `voice`, `studio`

- Les ports existent ; `voice.stt` et `voice.tts` sont `not_implemented`.
- L'absence de service vocal n'affecte aucun parcours.

## 9. Traçabilité

### Critères d'acceptation finaux

| Critère | Récits |
| --- | --- |
| AC1 | P1-04, P1-07, P1-11 |
| AC2 | P1-09 |
| AC3 | P2-03, P2-05, P2-07 |
| AC4 | P3-01, P3-02, P3-07 |
| AC5 | P3-04 |
| AC6 | P3-03 |
| AC7 | P4-03, P4-04, P5-08 |
| AC8 | P4-05, P4-07 |
| AC9 | P5-03, P5-04, P5-05, P5-06, P5-08 |
| AC10 | P1-02, P1-10, P6-04 |
| AC11 | P1-05, P1-12, P6-02 |
| AC12 | P1-01, P6-01, P6-03 |

### Modules du cahier des charges

| Module | Récits |
| --- | --- |
| M1 | P1-07, P1-09, P1-11 |
| M2 | P1-09 |
| M3 | P2-01, P2-02, P2-03, P2-05, P2-06, P2-07 |
| M4 | P1-04, P1-10 |
| M5 | P3-01, P3-04, P3-05 |
| M6 | P3-02, P3-03 |
| M7 | P3-07, P3-08, P3-09 |
| M8 | P2-04, P3-03, P3-06 |
| M9 | P4-01, P4-02, P4-03, P4-04, P4-05, P4-06, P4-07 |
| M10 | P5-01, P5-02, P5-03, P5-04, P5-05, P5-06, P5-07, P5-09 |
| M11 | P6-06 |
