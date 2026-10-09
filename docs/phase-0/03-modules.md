# 03 — Structure des modules

Statut : validé le 2026-10-09

## 1. Organisation du dépôt

```text
NOVA/
├── apps/
│   └── studio/                 NOVA Web Studio (React, TypeScript, Vite)
├── services/
│   ├── core/                   NOVA Core (paquet Python nova_core)
│   └── agent/                  NOVA Desktop Agent (paquet Python nova_agent)
├── packages/
│   └── protocol/               Protocole agent partagé (paquet Python nova_protocol)
├── tests/
│   └── e2e/                    Parcours de bout en bout (Playwright)
└── docs/
    └── phase-0/                Ce dossier
```

Un espace de travail `uv` regroupe les trois paquets Python ; un espace de travail `npm` regroupe le Studio et les tests de bout en bout. L'agent ne dépend que de `nova_protocol`, jamais de `nova_core` : il reste installable seul.

## 2. Règles de dépendance du Core

1. Chaque module a quatre couches : `api` (routes), `service` (cas d'usage), `repository` (accès aux données), `schemas` (modèles Pydantic).
2. Un module n'importe d'un autre module que son interface de service. Il ne lit ni n'écrit ses tables.
3. Les modules se notifient par événements de domaine publiés sur le bus interne (`events`).
4. Le noyau `kernel` (configuration, session de base, erreurs, horloge, identifiants, registre de capacités) ne dépend d'aucun module métier.
5. Aucun module n'appelle un SDK de fournisseur ; seul `providers` le fait.

Un test d'architecture vérifie les règles 2 et 5 par analyse des imports.

## 3. Modules du Core

Seize modules métier, plus le noyau.

<!-- enum:core_module -->
Identifiants : `identity`, `projects`, `conversations`, `orchestrator`, `providers`, `memory`, `research`, `artifacts`, `tasks`, `permissions`, `audit`, `agent_gateway`, `devflow`, `storage`, `events`, `voice`.

| Module | Responsabilité | Dépend de | Module du cahier des charges | Phase |
| --- | --- | --- | --- | --- |
| `identity` | Compte local, sessions, protection CSRF | `audit` | Sécurité §10 | 1 |
| `projects` | Projets, objectifs, exigences, contraintes, réglages de confidentialité | `audit` | M4 | 1 |
| `conversations` | Conversations, messages en ajout seul, assemblage du contexte | `projects`, `memory` | M1 | 1 |
| `orchestrator` | Boucle modèle–outils, registre d'outils, posture, questions de clarification | `conversations`, `providers`, `permissions`, `tasks`, `memory` | M1, M2 | 1 |
| `providers` | Ports de capacité, adaptateurs, routeur, budgets, usage | — | §5 | 1 |
| `memory` | Éléments de mémoire, décisions, restitution pour le contexte | `projects` | M4 | 1 |
| `research` | Recherche, récupération de pages, sources, citations, rapports | `providers`, `artifacts`, `storage` | M3 | 2 |
| `artifacts` | Artefacts, versions, validations, commentaires, diff, restauration, export | `projects`, `storage` | M5, M6, M7, M8 | 2 puis 3 |
| `tasks` | Cycle de vie des tâches, étapes, progression, annulation | `events` | §7 | 1 |
| `permissions` | Classement A/B/C/D, demandes d'approbation, autorisations permanentes, contamination | `audit` | §8 | 1 (socle), 5 (complet) |
| `audit` | Journal en ajout seul | — | §10 | 1 |
| `agent_gateway` | Appairage, authentification, canal WebSocket, envoi de commandes | `permissions`, `audit` | M10 | 5 |
| `devflow` | Plan d'implémentation, change sets, application, exécutions de tests, restauration | `artifacts`, `agent_gateway`, `permissions`, `tasks` | M9 | 4 |
| `storage` | Stockage privé adressé par contenu (`BlobStore`) | — | §4.B | 1 |
| `events` | Bus interne, journal d'événements, flux SSE rejouable | — | §4.B | 1 |
| `voice` | Ports de reconnaissance et de synthèse vocales, sans implémentation | `providers` | M11 | 6 (ports seulement) |

### 3.1 `orchestrator` — comment NOVA s'adapte sans workflow rigide

Un tour suit toujours la même boucle : assembler le contexte, appeler le modèle, traiter ses appels d'outils, recommencer jusqu'à la réponse finale. Ce qui change d'une demande à l'autre, ce sont les outils que le modèle choisit.

- **Posture.** L'orchestrateur déduit une posture (`conversation`, `analysis`, `research`, `design`, `development`) qui ajuste les consignes et les outils proposés. Elle est affichée dans le Studio et l'utilisateur peut la changer. Ce n'est pas une machine à états : aucune étape n'est obligatoire.
- **Clarification.** L'outil `ask_user` affiche une question structurée ; la tâche reste en `to_qualify` jusqu'à la réponse.
- **Contradiction argumentée.** Les consignes demandent d'exposer les désaccords et les alternatives. C'est un comportement du modèle, évalué en démonstration, non garanti par le code.
- **Capacité du modèle.** Si le fournisseur retenu ne gère pas les appels d'outils, l'orchestrateur n'expose aucun outil et le Studio indique que le tour est limité à la discussion.

### 3.2 Registre d'outils

Un outil est une fonction du Core décrite par : un nom, un schéma d'entrée, la capacité requise, et une fonction qui calcule sa classe de permission à partir de ses arguments.

| Outil | Effet | Classe | Module |
| --- | --- | --- | --- |
| `ask_user` | Pose une question structurée | A | `orchestrator` |
| `remember` | Propose un élément de mémoire (`user_info`, `nova_hypothesis`) | A | `memory` |
| `propose_decision` | Crée une décision à l'état `proposed` | A | `memory` |
| `search_web` | Interroge le fournisseur de recherche | A | `research` |
| `fetch_page` | Récupère et extrait une page | A | `research` |
| `create_artifact` | Crée un artefact et sa première version | B | `artifacts` |
| `revise_artifact` | Crée une nouvelle version | B | `artifacts` |
| `propose_plan` | Enregistre le plan de la tâche | A | `tasks` |
| `agent_list_files`, `agent_read_file`, `agent_search_files` | Lecture dans les répertoires autorisés | A | `agent_gateway` |
| `propose_change_set` | Crée un artefact `change_set` (aucune écriture sur disque) | B | `devflow` |
| `request_apply_change_set` | Demande l'application d'un change set approuvé | C | `devflow` |
| `request_test_run` | Demande l'exécution d'une commande de test prédéfinie | B | `devflow` |

Aucun outil ne permet au modèle de confirmer une décision, valider une version, approuver une demande, modifier une permission ou écrire un résultat de test.

### 3.3 `providers` — ports et routeur

| Port | Rôle | Implémentations prévues |
| --- | --- | --- |
| `ChatProvider` | Génération en flux, appels d'outils, sorties structurées | `FakeChatProvider` (tests), `OllamaProvider`, un adaptateur cloud (décision D2) |
| `SearchProvider` | Recherche Web | `FakeSearchProvider` (tests), un fournisseur réel (décision D4) |
| `ImageProvider` | Génération d'images | Aucune au MVP sauf décision D6 |
| `SpeechToTextProvider`, `TextToSpeechProvider` | Voix | Aucune au MVP |

Le routeur choisit un `ChatProvider` en deux temps.

1. **Contraintes dures, éliminatoires :** mode de confidentialité (`local_only` exclut tout fournisseur cloud, sans exception ni repli), capacités requises par la tâche (outils, sortie structurée, vision, taille de contexte), disponibilité, budget restant.
2. **Préférences, parmi les admissibles :** affectation choisie par l'utilisateur pour la classe de tâche, puis latence et coût.

S'il ne reste aucun fournisseur admissible, le routeur renvoie une erreur `capability_unavailable` avec la contrainte en cause. Il ne dégrade jamais silencieusement une contrainte dure.

### 3.4 `memory`

Trois catégories d'éléments (`user_info`, `source_fact`, `nova_hypothesis`) et une entité distincte, `Decision`. Le contexte d'un tour reçoit, dans des sections séparées et étiquetées : les décisions confirmées du projet, les éléments épinglés, puis les éléments retrouvés par mots-clés. L'utilisateur peut tout consulter, corriger et supprimer.

### 3.5 `artifacts`

Porte le modèle commun à tous les livrables : artefact, versions immuables, validations, commentaires. Le rendu est l'affaire du Studio ; le module fournit le contenu, le diff textuel et la restauration. Modèle détaillé : [04](04-modele-donnees.md).

### 3.6 `tasks`

Une tâche est créée pour chaque tour de conversation et pour chaque travail long. Le module garantit que les changements d'état suivent la table de transitions ([04](04-modele-donnees.md) §4.1), publie la progression et propage l'annulation par un jeton coopératif.

### 3.7 `research`

Déroulement d'une recherche : requêtes, récupération des pages, extraction, instantané, rédaction avec citations, vérification.

- **Citations vérifiées par le code.** Une citation n'est marquée `verified` que si son extrait est une sous-chaîne exacte de l'instantané de la source. Sinon elle est marquée `unverified` et affichée comme telle.
- **Limites écrites par le code.** La section « limites » du rapport est produite à partir des métadonnées réelles : requêtes lancées, pages récupérées, pages en échec et raison, date, fournisseur de recherche.

### 3.8 `devflow`

Enchaîne les onze étapes du module 9. Deux garde-fous structurels : un `change_set` ne peut être appliqué que si sa version est `approved` ; une tâche de développement ne peut passer à `in_review` que si une exécution de tests réelle lui est rattachée, quel qu'en soit le résultat.

## 4. Indépendance vis-à-vis des fournisseurs

La logique métier manipule un format de message propre à NOVA (rôle, blocs de texte, appels d'outils, résultats d'outils, images). Chaque adaptateur traduit dans les deux sens et conserve la charge utile brute du fournisseur dans un champ opaque, renvoyé tel quel au même fournisseur (ADR-13). Changer de fournisseur revient à ajouter un adaptateur et une entrée de configuration.

## 5. NOVA Web Studio

```text
apps/studio/src/
├── app/            coquille, routage, fournisseurs de contexte, disposition
├── features/
│   ├── projects/       navigation projets et conversations
│   ├── conversation/   fil, saisie, questions de clarification, badge fournisseur
│   ├── canvas/         scène, barre d'actions, registre des moteurs de rendu
│   │   └── renderers/  markdown, diagram, html-preview, image, scene3d, diff, test-run
│   ├── versions/       historique, comparaison, validation, restauration
│   ├── tasks/          progression, annulation
│   ├── approvals/      demandes d'autorisation
│   ├── memory/         mémoire et décisions
│   ├── research/       lancement, sources
│   ├── agent/          appairage, état, journal
│   └── settings/       fournisseurs, budgets, confidentialité, langue
└── shared/
    ├── api/        client généré depuis OpenAPI
    ├── events/     client SSE, mise à jour du cache
    ├── ui/         composants de base
    └── i18n/       textes FR et EN
```

| Type d'artefact | Moteur de rendu | Actions propres |
| --- | --- | --- |
| `report`, `document` | `markdown` | Copier, exporter en Markdown |
| `diagram` | `diagram` | Exporter en SVG |
| `wireframe`, `mockup`, `app_preview` | `html-preview` (cadre isolé) | Changer de largeur d'écran, voir le source, exporter en HTML |
| `image` | `image` | Zoom, télécharger |
| `scene3d` | `scene3d` | Rotation, zoom, déplacement, paramètres, capture, export glTF (à vérifier en Phase 3) |
| `change_set` | `diff` | Demander l'application, restaurer |
| `test_run` | `test-run` | Voir la sortie complète |

Tous les types partagent : commentaires, historique des versions, comparaison, validation.

## 6. NOVA Desktop Agent

```text
services/agent/nova_agent/
├── cli.py          pair, run, stop, revoke, status
├── connection.py   WebSocket sortant, poignée de main, reconnexion
├── policy.py       chargement et application de la politique locale
├── paths.py        validation des chemins
├── actions/        fs, cmd, git — une fonction par action
├── runner.py       exécution de processus sans interpréteur de commandes
└── journal.py      journal d'activité local
```

## 7. Correspondance modules du cahier des charges → composants

| Module | Core | Studio | Agent |
| --- | --- | --- | --- |
| M1 Conversation | `conversations`, `orchestrator` | `conversation` | — |
| M2 Analyse | `orchestrator`, `artifacts` | `conversation`, `canvas` | — |
| M3 Recherche | `research` | `research`, `canvas` | — |
| M4 Projets et mémoire | `projects`, `memory` | `projects`, `memory` | — |
| M5 Canvas | `artifacts` | `canvas`, `versions` | — |
| M6 Studio UI/UX | `artifacts`, `orchestrator` | `canvas` (`html-preview`) | — |
| M7 2D et 3D | `artifacts`, `providers` | `canvas` (`diagram`, `image`, `scene3d`) | — |
| M8 Validation et versionnement | `artifacts` | `versions` | — |
| M9 Développement | `devflow` | `canvas` (`diff`, `test-run`), `approvals` | `actions` |
| M10 Agent local | `agent_gateway`, `permissions` | `agent`, `approvals` | tout le paquet |
| M11 Voix | `voice` | états d'interface prévus | — |
