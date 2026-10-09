# 05 — Principaux contrats d'API

Statut : validé le 2026-10-09

Ces contrats fixent la forme des échanges. Le schéma OpenAPI généré par le Core fera foi dès la Phase 1 ; les types TypeScript du Studio en seront dérivés. Le vocabulaire est celui de [04](04-modele-donnees.md).

## 1. Conventions

| Sujet | Règle |
| --- | --- |
| Préfixe | `/api/v1` |
| Format | JSON, UTF-8, dates ISO 8601 en UTC |
| Authentification | Cookie de session `HttpOnly`, `SameSite=Strict` |
| Requêtes modifiantes | En-tête `X-CSRF-Token` obligatoire ; `Origin` et `Host` contrôlés |
| Idempotence | En-tête `Idempotency-Key` accepté sur les créations de messages, de tâches et de décisions d'approbation |
| Pagination | Par curseur : `?limit=&cursor=` ; la réponse porte `next_cursor` |
| Erreurs | `application/problem+json` avec un champ `code` stable (§8) |
| Travaux longs | La requête répond `202` avec un `task_id` ; la suite arrive par le flux d'événements |

## 2. Système et capacités

| Méthode | Chemin | Rôle |
| --- | --- | --- |
| GET | `/system/health` | État du processus et de la base |
| GET | `/system/capabilities` | Ce qui fonctionne réellement, et pourquoi le reste ne fonctionne pas |

<!-- enum:capability_status -->
Statuts possibles : `available`, `degraded`, `unavailable`, `not_implemented`

```json
{
  "capabilities": [
    { "id": "chat.local", "status": "available", "detail": "ollama / llama3.2" },
    { "id": "chat.cloud", "status": "unavailable", "reason": "provider_not_configured" },
    { "id": "research.search", "status": "unavailable", "reason": "provider_not_configured" },
    { "id": "research.fetch", "status": "available" },
    { "id": "image.generate", "status": "unavailable", "reason": "provider_not_configured" },
    { "id": "agent.fs", "status": "unavailable", "reason": "agent_offline" },
    { "id": "agent.exec", "status": "unavailable", "reason": "agent_offline" },
    { "id": "agent.git", "status": "unavailable", "reason": "agent_offline" },
    { "id": "voice.stt", "status": "not_implemented" },
    { "id": "voice.tts", "status": "not_implemented" }
  ]
}
```

## 3. Authentification

| Méthode | Chemin | Rôle |
| --- | --- | --- |
| POST | `/auth/setup` | Crée le compte local au premier lancement ; refusé ensuite |
| POST | `/auth/login` | Ouvre une session |
| POST | `/auth/logout` | Ferme la session |
| GET | `/auth/session` | Session courante et jeton CSRF |

Sans session, `GET /auth/session` répond `401` avec le code `not_authenticated` et un champ `setup_required` indiquant si le compte reste à créer. `POST /auth/setup` et `POST /auth/login` sont dispensés de jeton CSRF, faute de session ; le contrôle de l'origine s'y applique.

## 4. Ressources

### 4.1 Projets et mémoire

| Méthode | Chemin | Rôle |
| --- | --- | --- |
| GET, POST | `/projects` | Lister, créer |
| GET, PATCH, DELETE | `/projects/{project_id}` | Lire, modifier (dont `llm_privacy`, `web_access`), supprimer en cascade |
| GET, POST | `/projects/{project_id}/spec-items` | Objectifs, exigences, contraintes |
| PATCH, DELETE | `/spec-items/{item_id}` | Modifier, confirmer, supprimer |
| POST | `/projects/{project_id}/export` | Archive du projet (tâche) |
| GET, POST | `/projects/{project_id}/memory` | Lister (filtre `kind`), ajouter |
| PATCH, DELETE | `/memory/{item_id}` | Corriger, épingler, archiver, supprimer |
| GET, POST | `/projects/{project_id}/decisions` | Lister, proposer |
| POST | `/decisions/{decision_id}/confirm` | Confirmer — **utilisateur uniquement** |
| POST | `/decisions/{decision_id}/reject` | Rejeter une proposition |
| POST | `/decisions/{decision_id}/revoke` | Revenir sur une décision confirmée |
| DELETE | `/decisions/{decision_id}` | Supprimer |

À la création d'un projet, `llm_privacy` vaut `local_only` et `web_access` vaut `disabled` si le client ne précise rien : rien ne sort du poste sans choix explicite. Le projet « espace libre » ne peut être ni supprimé ni archivé (`protected_resource`). La liste accepte `?status=active|archived|all`, `active` par défaut.

<!-- enum:llm_privacy -->
Valeurs de `llm_privacy` : `local_only`, `cloud_allowed`

<!-- enum:web_access -->
Valeurs de `web_access` : `enabled`, `disabled`

<!-- enum:memory_kind -->
Valeurs de `kind` pour la mémoire : `user_info`, `source_fact`, `nova_hypothesis`

<!-- enum:decision_status -->
Valeurs de `status` pour une décision : `proposed`, `confirmed`, `rejected`, `revoked`, `superseded`

### 4.2 Conversations

| Méthode | Chemin | Rôle |
| --- | --- | --- |
| GET, POST | `/projects/{project_id}/conversations` | Lister, créer |
| GET, PATCH, DELETE | `/conversations/{conversation_id}` | Lire, renommer ou déplacer, supprimer |
| GET | `/conversations/{conversation_id}/messages` | Historique paginé |
| POST | `/conversations/{conversation_id}/messages` | Envoyer un message ; répond `202` |

Envoi d'un message :

```json
{
  "text": "Compare ces deux approches et dis-moi laquelle tu retiendrais.",
  "force_local": false,
  "stance": null,
  "input_modality": "text"
}
```

Réponse `202` :

```json
{ "message_id": "…", "task_id": "…" }
```

Message de NOVA une fois terminé :

```json
{
  "id": "…",
  "seq": 12,
  "role": "assistant",
  "status": "completed",
  "blocks": [ { "type": "text", "text": "…" } ],
  "provider": { "id": "ollama", "model": "llama3.2", "route_reason": "project_local_only" },
  "usage": { "input_tokens": 1830, "output_tokens": 412, "estimated_cost_usd": null }
}
```

### 4.3 Artefacts, versions, validations

| Méthode | Chemin | Rôle |
| --- | --- | --- |
| GET, POST | `/projects/{project_id}/artifacts` | Lister (filtre `type`), créer avec une première version |
| GET, PATCH, DELETE | `/artifacts/{artifact_id}` | Lire, renommer, supprimer |
| GET, POST | `/artifacts/{artifact_id}/versions` | Historique ; créer la version suivante |
| GET | `/artifact-versions/{version_id}` | Métadonnées d'une version |
| GET | `/artifact-versions/{version_id}/content` | Contenu |
| PUT | `/artifact-versions/{version_id}/content` | Modifier le contenu — accepté seulement en `draft` ; pendant `in_progress`, seul NOVA écrit |
| POST | `/artifact-versions/{version_id}/submit` | Passer en `in_review` |
| POST | `/artifact-versions/{version_id}/reviews` | Valider ou demander des modifications — **utilisateur uniquement** |
| GET | `/artifacts/{artifact_id}/diff?from={v}&to={v}` | Diff unifié entre deux versions (formats textuels) |
| POST | `/artifacts/{artifact_id}/restore` | Créer une nouvelle version à partir d'une ancienne |
| GET, POST | `/artifact-versions/{version_id}/comments` | Commentaires |
| PATCH | `/comments/{comment_id}` | Modifier, résoudre |
| GET | `/artifact-versions/{version_id}/export?format=` | Export dans un format pris en charge par le type |

<!-- enum:artifact_type -->
Valeurs de `type` : `report`, `document`, `diagram`, `wireframe`, `mockup`, `image`, `scene3d`, `app_preview`, `change_set`, `test_run`

<!-- enum:version_state -->
Valeurs de `state` : `draft`, `in_progress`, `in_review`, `changes_requested`, `approved`, `superseded`, `failed`

<!-- enum:review_decision -->
Valeurs de `decision` pour une validation : `approve`, `request_changes`

Version d'artefact :

```json
{
  "id": "…",
  "artifact_id": "…",
  "number": 3,
  "state": "in_review",
  "content_format": "html",
  "content_hash": "sha256:…",
  "created_by": "nova",
  "parent_version_id": "…",
  "restored_from_version_id": null,
  "change_summary": "Navigation latérale repliable ; contraste des boutons relevé",
  "created_at": "2026-10-09T14:02:11Z"
}
```

Validation — le client renvoie l'empreinte du contenu qu'il a affiché ; le Core refuse si elle ne correspond plus :

```json
{ "decision": "approve", "content_hash": "sha256:…", "comment": "Bon pour implémentation." }
```

### 4.4 Recherche

| Méthode | Chemin | Rôle |
| --- | --- | --- |
| POST | `/projects/{project_id}/research` | Lancer une recherche ; répond `202` avec un `task_id` |
| GET | `/projects/{project_id}/sources` | Sources du projet |
| GET | `/sources/{source_id}` | Métadonnées d'une source |
| GET | `/sources/{source_id}/snapshot` | Texte extrait conservé |
| GET | `/artifact-versions/{version_id}/citations` | Citations d'un rapport, avec leur statut |

<!-- enum:citation_status -->
Valeurs de `status` pour une citation : `verified`, `unverified`

### 4.5 Tâches

| Méthode | Chemin | Rôle |
| --- | --- | --- |
| GET | `/projects/{project_id}/tasks` | Lister (filtre `state`) |
| GET | `/tasks/{task_id}` | Détail : demande, plan, étapes, approbations, résultats, erreurs, versions concernées |
| POST | `/tasks/{task_id}/cancel` | Annuler |
| POST | `/tasks/{task_id}/retry` | Relancer une tâche en échec |
| POST | `/tasks/{task_id}/review` | Valider le résultat ou demander une reprise — **utilisateur uniquement** |

<!-- enum:task_state -->
Valeurs de `state` : `to_qualify`, `ready`, `awaiting_approval`, `running`, `in_review`, `validated`, `done`, `cancelled`, `failed`

Réponse à une annulation — elle dit ce qui n'a pas pu être défait :

```json
{
  "task_id": "…",
  "state": "cancelled",
  "irreversible_effects": [
    { "step": 4, "action": "cmd.run", "detail": "Commande interrompue après 12 s ; ses effets éventuels ne sont pas connus." }
  ]
}
```

### 4.6 Approbations et autorisations permanentes

| Méthode | Chemin | Rôle |
| --- | --- | --- |
| GET | `/approvals?status=pending` | Demandes en attente |
| GET | `/approvals/{approval_id}` | Détail d'une demande |
| POST | `/approvals/{approval_id}/decision` | Approuver ou refuser — **utilisateur uniquement** |
| GET, POST | `/projects/{project_id}/grants` | Autorisations permanentes de classe B |
| DELETE | `/grants/{grant_id}` | Révoquer |

<!-- enum:approval_status -->
Valeurs de `status` pour une demande : `pending`, `approved`, `denied`, `expired`, `consumed`

<!-- enum:permission_class -->
Valeurs de `permission_class` : `A`, `B`, `C`, `D`

Demande d'approbation :

```json
{
  "id": "…",
  "task_id": "…",
  "permission_class": "C",
  "status": "pending",
  "action": { "name": "fs.apply_patch", "params": { "root": "demo-app", "change_set_version_id": "…" } },
  "action_hash": "sha256:…",
  "summary": "Appliquer 3 modifications de fichiers dans demo-app",
  "resources": [
    { "path": "src/app.py", "operation": "modify" },
    { "path": "src/routes/items.py", "operation": "create" },
    { "path": "tests/test_items.py", "operation": "create" }
  ],
  "consequences": "Deux fichiers créés, un fichier modifié.",
  "risks": "Le fichier modifié sera écrasé. L'application échoue si son contenu a changé depuis la préparation.",
  "rollback": { "possible": true, "how": "Point de reprise git créé avant application ; restauration en un clic." },
  "expires_at": "2026-10-09T14:20:00Z"
}
```

Décision — le client renvoie l'empreinte de l'action qu'il a affichée :

```json
{ "decision": "approve", "action_hash": "sha256:…", "remember": false }
```

`remember` n'est accepté que pour la classe B. Il est refusé pour la classe C.

### 4.7 Développement

| Méthode | Chemin | Rôle |
| --- | --- | --- |
| POST | `/projects/{project_id}/dev/plans` | Demander un plan d'implémentation à partir d'une version approuvée ; `202` |
| POST | `/artifact-versions/{version_id}/apply` | Demander l'application d'un change set approuvé ; crée une demande de classe C |
| GET | `/change-applications/{application_id}` | État d'une application |
| POST | `/change-applications/{application_id}/rollback` | Restaurer le point de reprise ; crée une demande de classe C |
| POST | `/projects/{project_id}/dev/test-runs` | Lancer une commande de test prédéfinie ; `202` |

### 4.8 Agents

| Méthode | Chemin | Rôle |
| --- | --- | --- |
| POST | `/agents/pairing-codes` | Créer un code d'appairage à usage unique |
| POST | `/agents/pair` | Appelé par l'agent : échange le code contre un identifiant |
| GET | `/agents` | Agents, statut, capacités annoncées |
| POST | `/agents/{agent_id}/shutdown` | Demander l'arrêt de l'agent |
| POST | `/agents/{agent_id}/revoke` | Révoquer définitivement |
| WebSocket | `/agent/v1/ws` | Canal de l'agent — voir [06](06-protocole-agent.md) |

<!-- enum:agent_status -->
Valeurs de `status` pour un agent : `online`, `offline`, `revoked`

### 4.9 Fournisseurs, usage, audit

| Méthode | Chemin | Rôle |
| --- | --- | --- |
| GET | `/providers` | Fournisseurs connus, « configuré » ou non, capacités déclarées |
| PATCH | `/providers/{provider_id}` | Réglages non secrets : modèle par défaut, affectation par classe de tâche, délais |
| POST | `/providers/{provider_id}/test` | Test de connexion réel |
| GET, PATCH | `/settings/budgets` | Plafonds par jour, par mois, par tâche |
| GET | `/usage` | Usage et coût estimé |
| GET | `/audit` | Journal d'audit, filtrable |

Aucune route ne renvoie ni n'accepte une clé d'API.

## 5. Flux d'événements

`GET /api/v1/events/stream` — Server-Sent Events. Le client rouvre le flux avec `Last-Event-ID` ; le Core rejoue ce qui manque à partir du journal d'événements.

Enveloppe :

```json
{ "id": 4182, "type": "task.updated", "ts": "2026-10-09T14:02:12Z", "project_id": "…", "data": { } }
```

| Type | Émis quand |
| --- | --- |
| `message.delta` | Un fragment de réponse arrive |
| `message.completed`, `message.failed` | La réponse se termine ou échoue |
| `task.created`, `task.updated` | Une tâche est créée ou change d'état |
| `task.step` | Une étape commence ou se termine |
| `task.progress` | Progression d'un travail long |
| `approval.requested`, `approval.resolved` | Une demande est créée, décidée, expirée ou consommée |
| `artifact.version.created`, `artifact.version.updated` | Une version est créée ou change d'état |
| `agent.status` | Un agent se connecte, se déconnecte ou est révoqué |
| `capability.changed` | Le statut d'une capacité change |

## 6. Contrat d'un fournisseur de conversation

Le port que tout adaptateur implémente. Les signatures sont indicatives ; le contrat porte sur le comportement.

```python
class ChatProvider(Protocol):
    id: str

    def capabilities(self) -> ChatCapabilities:
        """Local ou cloud, flux, appels d'outils, sorties structurées, vision, taille de contexte."""

    async def health(self) -> ProviderHealth:
        """Test réel de disponibilité ; jamais de valeur supposée."""

    def stream(self, request: ChatRequest, cancel: CancelToken) -> AsyncIterator[ChatEvent]:
        """Émet text_delta, tool_call, usage, completed ou error. Respecte l'annulation et le délai."""
```

| Obligation | Détail |
| --- | --- |
| Ne déclarer que le vérifiable | `capabilities()` reflète ce que l'adaptateur sait faire avec le modèle configuré |
| Erreurs typées | `unavailable`, `timeout`, `rate_limited`, `refused`, `invalid_request`, chacune marquée réessayable ou non |
| Fidélité | Les blocs propres au fournisseur sont renvoyés à l'identique au tour suivant |
| Usage | Les jetons consommés sont rapportés quand le fournisseur les communique ; sinon le champ est vide, jamais estimé en silence |

## 7. Contrat d'un outil de l'orchestrateur

```python
class Tool(Protocol):
    name: str
    input_schema: type[BaseModel]
    requires_capability: str | None

    def classify(self, args: BaseModel, ctx: ToolContext) -> PermissionRequest:
        """Décrit l'action exacte, ses ressources et sa classe. Fonction pure, sans effet."""

    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        """N'est appelée qu'après autorisation par le moteur de permissions."""
```

## 8. Codes d'erreur

| `code` | HTTP | Signification |
| --- | --- | --- |
| `validation_error` | 422 | Corps ou paramètres invalides |
| `not_authenticated` | 401 | Session absente ou expirée |
| `invalid_credentials` | 401 | Nom d'utilisateur ou mot de passe incorrect |
| `already_set_up` | 409 | Le compte local existe déjà |
| `csrf_failed` | 403 | Jeton CSRF ou origine invalide |
| `host_not_allowed` | 403 | En-tête `Host` inattendu |
| `protected_resource` | 409 | Ressource qui ne peut être ni supprimée ni archivée |
| `internal_error` | 500 | Erreur inattendue ; aucun détail interne n'est renvoyé |
| `not_found` | 404 | Ressource inconnue |
| `invalid_state_transition` | 409 | Transition d'état interdite |
| `version_immutable` | 409 | Tentative de modifier une version figée |
| `content_hash_mismatch` | 409 | Le contenu a changé depuis son affichage |
| `action_hash_mismatch` | 409 | L'action approuvée n'est pas celle demandée |
| `approval_required` | 403 | Action de classe B sans autorisation, ou de classe C |
| `permission_denied` | 403 | Action de classe D |
| `capability_unavailable` | 503 | Capacité absente ; le champ `reason` dit pourquoi |
| `privacy_violation_blocked` | 403 | Appel cloud refusé par le mode de confidentialité |
| `budget_exceeded` | 402 | Plafond de dépense atteint |
| `provider_error` | 502 | Erreur renvoyée par un fournisseur, transmise telle quelle |
| `agent_offline` | 503 | Aucun agent connecté |
| `agent_rejected` | 403 | L'agent a refusé la commande ; le champ `reason` porte son code |
| `rate_limited` | 429 | Trop de requêtes |
