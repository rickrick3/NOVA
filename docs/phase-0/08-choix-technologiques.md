# 08 — Choix technologiques

Statut : validé le 2026-10-09

## 1. Niveau de preuve

Chaque affirmation de ce document porte l'un de ces marqueurs.

| Marqueur | Signification |
| --- | --- |
| **[V]** | Vérifié le 2026-10-09, par commande sur le poste, par consultation d'un registre de paquets ou par lecture de la documentation officielle |
| **[E]** | Estimation raisonnée, non mesurée |
| **[H]** | Hypothèse, non vérifiée |

« Version observée » signifie : dernière version publiée sur le registre ce jour-là. Aucun paquet n'a été installé ni testé. Les versions seront figées par fichier de verrouillage au premier `install` de la Phase 1.

## 2. Environnement constaté

| Élément | Constat | Preuve |
| --- | --- | --- |
| Système | Windows 11 Pro 10.0.26200 | **[V]** |
| Processeur | Intel Core i5-1334U, 10 cœurs, 12 fils | **[V]** |
| Mémoire | 15,7 Go | **[V]** |
| Carte graphique | Intel Iris Xe intégrée, pas de carte dédiée | **[V]** |
| Disque C: | **1,3 Go libres** sur 464,8 Go ; aucun autre disque | **[V]** |
| Python | 3.13.9 | **[V]** |
| Node.js, npm | 24.11.1, 11.12.1 | **[V]** |
| uv | 0.12.5 | **[V]** |
| git | 2.52.0 | **[V]** |
| Docker | 29.1.2 | **[V]** |
| Ollama | 0.35.1 ; serveur actif sur `127.0.0.1:11434` ; `/api/version` et `/v1/models` répondent | **[V]** |
| pnpm, client PostgreSQL | Absents | **[V]** |
| Clés d'API | Aucune des variables `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `TAVILY_API_KEY`, `BRAVE_API_KEY` n'est définie | **[V]** |
| Dossier `NOVA` | Vide avant cette phase | **[V]** |
| Dépôt git | `NOVA` se trouve dans le dépôt `projects`, dont la branche est `farel` et le dépôt distant `Tamofarel/python-for-finances-` | **[V]** |

L'espace disque, l'absence de clé d'API et la situation du dépôt git sont repris comme points bloquants dans [09](09-risques-decisions.md).

## 3. NOVA Core

| Besoin | Choix | Version observée | Justification | Alternative écartée |
| --- | --- | --- | --- | --- |
| Langage | Python | 3.13.9 installé **[V]** | Imposé par le cahier des charges ; toutes les bibliothèques ci-dessous déclarent une compatibilité `>=3.10` ou `>=3.11` **[V]** | — |
| Gestion de projet | uv, espace de travail | 0.12.5 installé **[V]** | Déjà présent ; un seul verrouillage pour le Core, l'agent et le protocole | pip et environnements manuels |
| API | FastAPI | 0.143.0 **[V]** | Imposé ; génère le schéma OpenAPI qui sert de contrat | — |
| Validation | Pydantic, pydantic-settings | 2.14.0, 2.15.0 **[V]** | Imposé ; même outil pour l'API, le protocole agent et la configuration | — |
| Serveur | Uvicorn | 0.54.0 **[V]** | Serveur ASGI de référence pour FastAPI | — |
| Accès aux données | SQLAlchemy, avec son extra `asyncio` (qui apporte `greenlet`, requis par le moteur asynchrone) | 2.1.4 **[V]** | Un seul modèle pour SQLite et PostgreSQL | SQL écrit à la main |
| Migrations | Alembic | 1.20.0 **[V]** | Compagnon de SQLAlchemy | — |
| Pilotes | aiosqlite (local), psycopg (hébergé) | 0.22.1, 3.3.6 **[V]** | Pilotes asynchrones des deux moteurs | — |
| Client HTTP | httpx | 0.28.1 **[V]** | Asynchrone, délais fins, transport simulable en test | requests |
| Mots de passe | argon2-cffi | 25.1.0 **[V]** | Argon2id | bcrypt |
| Extraction de pages | trafilatura | 2.3.1 **[V]** | Extraction du texte principal d'une page HTML | Navigateur sans interface (trop lourd pour le MVP) |
| Signatures Ed25519 | `cryptography` | À relever à l'installation **[H]** | Bibliothèque de référence | Secret partagé |
| Temps réel vers le Studio | SSE fourni par FastAPI/Starlette | — | ADR-03 | WebSocket |
| Tâches longues | `asyncio` dans le processus | — | ADR-01 | Celery, Redis |
| Tests | pytest, pytest-asyncio | 9.1.1, 1.4.0 **[V]** | Standard | — |
| Qualité | ruff, mypy | 0.16.10, 2.4.0 **[V]** | Formatage, lint, typage | — |

## 4. NOVA Web Studio

| Besoin | Choix | Version observée | Justification | Alternative écartée |
| --- | --- | --- | --- | --- |
| Socle | React, TypeScript, Vite | 19.3.0, 7.0.2, 8.3.4 **[V]** | Imposés | — |
| Styles | Tailwind CSS avec jetons de design en variables CSS | 4.3.3 **[V]** | Système cohérent, thème sombre par jetons | CSS-in-JS |
| Composants | Composants écrits dans le dépôt sur les primitives Radix | `radix-ui` 1.7.0 **[V]** | Accessibilité au clavier fournie par les primitives ; aucun style imposé ; le code des composants reste à nous | Bibliothèque de composants stylée fermée |
| État serveur | TanStack Query | 5.104.1 **[V]** | Cache, invalidation, mise à jour par les événements SSE | Gestion manuelle |
| État d'interface | Zustand | 5.0.15 **[V]** | Léger ; disposition, sélection, posture | Redux |
| Routage | React Router | 8.4.0 **[V]** | Standard | — |
| Client d'API | Types générés par openapi-typescript | 7.13.0 **[V]** | ADR-12 | Types écrits à la main |
| Rendu Markdown | react-markdown, shiki | 10.1.0, 4.5.0 **[V]** | Rapports et documents, code coloré | — |
| Diagrammes | Mermaid | 12.1.0 **[V]** | Source texte, donc versionnable et comparable | Éditeur graphique |
| 3D | three.js, @react-three/fiber, @react-three/drei | 0.186.1, 9.8.1, 10.7.9 **[V]** | Three.js cité par le cahier des charges ; contrôles d'orbite fournis | Babylon.js |
| Diff | `diff` | 9.0.0 **[V]** | Affichage côte à côte | — |
| Internationalisation | i18next, react-i18next | 26.4.2, 17.0.16 **[V]** | FR et EN (hypothèse H3) | Textes en dur |
| Tests | Vitest, Testing Library, Playwright | 5.0.3, 16.3.3, 1.64.0 **[V]** | Unitaires, composants, bout en bout | — |

**Le moteur du canvas.** Le canvas est une scène d'artefacts typés (ADR-06). Son « moteur de rendu » est un registre : un composant par format, chargé à la demande. Les maquettes et aperçus s'affichent dans un cadre isolé du navigateur. Aucune bibliothèque de tableau blanc n'est nécessaire.

**Export glTF des scènes 3D.** Three.js fournit un exportateur glTF dans ses modules complémentaires **[H]** — non revérifié dans cette phase. La capacité ne sera annoncée dans le Studio qu'après un test d'export réussi en Phase 3.

**TypeScript 7.** La version 7.0.2 est la dernière publiée **[V]**. La compatibilité de l'outillage choisi avec cette version majeure n'a pas été testée **[H]** ; elle le sera à la création du gabarit, avec repli sur la version majeure précédente si nécessaire.

## 5. NOVA Desktop Agent

| Besoin | Choix | Version observée | Justification |
| --- | --- | --- | --- |
| Langage | Python | 3.13.9 **[V]** | Imposé |
| Canal | Client `websockets` | 17.2 **[V]** | Connexion sortante uniquement |
| Protocole | Paquet partagé `nova_protocol` (Pydantic) | — | ADR-12 |
| Processus | `subprocess` de la bibliothèque standard, sans interpréteur de commandes | — | Objectif S4 du protocole |
| Clé privée | Magasin d'identifiants du système via `keyring` | À relever à l'installation **[H]** | La clé ne reste pas en clair sur le disque |
| Politique | TOML, lu par `tomllib` de la bibliothèque standard | — | Lisible et modifiable à la main |

## 6. Fournisseurs IA

### 6.1 Fournisseur local : Ollama

| Fait | Preuve |
| --- | --- |
| Le serveur répond sur le poste | **[V]** |
| `/api/chat` accepte un champ `tools` et renvoie des `tool_calls` ; le flux est pris en charge avec les appels d'outils | **[V]** documentation Ollama |
| `/api/chat` accepte un champ `format` portant un schéma JSON pour contraindre la sortie | **[V]** documentation Ollama |
| Une interface compatible OpenAI est exposée sous `/v1` | **[V]** réponse 200 sur `/v1/models` |
| Client Python officiel `ollama` | 0.6.3 **[V]** |

Modèles installés sur le poste **[V]** :

| Modèle | Taille | Contexte | Appels d'outils | Utilisable par NOVA |
| --- | --- | --- | --- | --- |
| `llama3.2` | 3,2 Md de paramètres, 2,0 Go | 131 072 | Oui | Oui |
| `mistral` | 7,2 Md de paramètres, 4,4 Go | 32 768 | Oui | Oui |
| `phi` | 3 Md de paramètres, 1,6 Go | 2 048 | Non | Non : contexte trop court, pas d'outils |

**[E]** Sans carte graphique dédiée et avec 15,7 Go de mémoire, la génération locale sera lente et la fiabilité des appels d'outils limitée sur des modèles de cette taille. Aucun chiffre n'est avancé : une mesure (délai avant le premier fragment, débit, taux d'appels d'outils valides) fait partie de la Phase 1.

Conséquence : le mode local permettra la discussion et des analyses simples. La recherche, la conception et le développement demanderont en pratique un fournisseur plus capable.

### 6.2 Premier fournisseur cloud — décision D2

**Recommandation : Claude (Anthropic), derrière le port `ChatProvider`.** Seule la documentation de ce fournisseur a été vérifiée en détail dans cette phase ; les autres n'ont pas été évalués et restent possibles par l'ajout d'un adaptateur.

| Fait | Preuve |
| --- | --- |
| SDK Python officiel `anthropic` | 1.12.1 **[V]** |
| `claude-opus-5-5` : 4 $ par million de jetons en entrée, 20 $ en sortie ; contexte d'un million de jetons | **[V]** page de tarifs |
| `claude-sonnet-5-5` : 2 $ et 10 $ | **[V]** page de tarifs |
| `claude-haiku-4-5` : 1 $ et 5 $ | **[V]** page de tarifs |
| Recherche Web côté serveur : 10 $ pour 1 000 recherches, en plus des jetons ; récupération de page sans supplément | **[V]** page de tarifs |
| Sur `claude-opus-5-5`, le raisonnement ne peut pas être désactivé et le choix d'outil forcé est refusé | **[V]** guide de l'API |
| Une réponse peut se terminer par un refus (`stop_reason: "refusal"`), à traiter explicitement | **[V]** guide de l'API |
| Les blocs de raisonnement doivent être renvoyés à l'identique, sur un historique non modifié | **[V]** guide de l'API — fonde l'ADR-13 |
| La page de tarifs liste aussi « Claude Haiku 5.5 » | **[V]** ; son identifiant de modèle n'a pas été vérifié et ne sera utilisé qu'après lecture de la liste renvoyée par l'API |

Modèle par défaut proposé : `claude-opus-5-5` pour toutes les classes de tâches. L'affectation d'un modèle moins coûteux à certaines classes est un réglage de l'utilisateur, pas un choix fait à sa place.

Ordre de grandeur **[E]** : un tour de 10 000 jetons en entrée et 1 000 en sortie coûte 0,04 $ + 0,02 $ = 0,06 $ sur `claude-opus-5-5`. Les volumes sont une hypothèse ; les prix sont vérifiés.

### 6.3 Fournisseur de recherche — décision D4, à prendre avant la Phase 2

| Option | Fait | Preuve |
| --- | --- | --- |
| Tavily | 1 000 crédits gratuits par mois, sans carte bancaire ; une recherche simple coûte 1 crédit ; 0,008 $ le crédit à l'usage | **[V]** documentation Tavily |
| Brave Search API | 5 $ de crédits offerts chaque mois ; 5 $ pour 1 000 requêtes | **[V]** page de l'API Brave. Conditions d'accès aux crédits offerts non précisées sur la page |
| Recherche Web de Claude | 10 $ pour 1 000 recherches ; liée à ce fournisseur, inutilisable en mode local | **[V]** page de tarifs |

Recommandation : un port `SearchProvider` propre à NOVA, avec Tavily comme première implémentation. La recherche reste ainsi utilisable quel que soit le fournisseur de conversation.

### 6.4 Génération d'images — décision D6, à prendre avant la Phase 3

Aucun fournisseur n'a été vérifié dans cette phase **[H]**. Le critère AC4 est satisfait sans génération d'images matricielles, par les maquettes HTML, les diagrammes et les scènes 3D. Le port `ImageProvider` est défini ; son implémentation n'est engagée que si tu la demandes, après vérification de la documentation du fournisseur retenu.

### 6.5 Voix

Aucun choix. Les ports existent ; la capacité est déclarée `not_implemented`.

## 7. Ce qui est écarté, et pourquoi

| Technologie | Raison |
| --- | --- |
| tldraw | Depuis sa version 4, le SDK exige une clé de licence en production ; la licence gratuite impose un filigrane et un usage non commercial **[V]**. Inutile au vu de l'ADR-06 |
| Framework d'agents | ADR-04 |
| File de messages, Redis | ADR-01 |
| Base vectorielle | ADR-14 |
| Enveloppe de bureau (Electron, Tauri) | Le Studio est une application Web locale ; rien dans le périmètre ne l'exige |
| Isolation des commandes par conteneur | Souhaitable, reportée : complexité et espace disque. Limite assumée du MVP |
| Navigateur sans interface pour la récupération de pages | Poids et espace disque ; les pages exigeant JavaScript sont signalées comme non extractibles |

## 8. Stratégie de tests

| Niveau | Outil | Couvre |
| --- | --- | --- |
| Unitaire Core | pytest | Services, machines à états, moteur de permissions, routeur |
| Schémas | pytest | Modèles Pydantic, schéma OpenAPI figé par instantané |
| API | pytest avec transport ASGI httpx | Routes, erreurs, CSRF, limitation de débit |
| Fournisseurs | `FakeChatProvider`, `FakeSearchProvider`, serveur HTTP local | Flux, appels d'outils, erreurs, délais — sans réseau ni coût |
| Versionnement | pytest | Invariants INV-1 à INV-3, restauration, diff |
| Permissions | pytest, piloté par la matrice | Chaque ligne de [07](07-permissions.md), cas autorisé et cas refusé |
| Agent | pytest dans des répertoires temporaires | Chemins, commandes, annulation, git, protocole |
| Studio | Vitest, Testing Library | Composants, moteurs de rendu, client d'événements |
| Bout en bout | Playwright, Core en mode test avec faux fournisseurs | Parcours complet |
| Non-régression | Toute la suite, à chaque phase | Critères de sortie des phases précédentes |
| Fournisseurs réels | pytest, marqueur `live`, exclu par défaut | Un test de fumée par fournisseur configuré |

La suite par défaut ne consomme aucune API payante. Les tests `live` ne s'exécutent que sur demande explicite et avec une clé présente.

## 9. Sources consultées le 2026-10-09

- Registres : API JSON de PyPI et `npm view` pour chaque paquet cité.
- Ollama, appels d'outils : <https://docs.ollama.com/capabilities/tool-calling>
- Ollama, sorties structurées : <https://docs.ollama.com/capabilities/structured-outputs>
- Claude, tarifs : <https://platform.claude.com/docs/en/about-claude/pricing>
- Claude, guide de l'API : référence fournie avec l'environnement de développement, datée du 2026-09-25
- Tavily, crédits : <https://docs.tavily.com/documentation/api-credits>
- Brave Search API : <https://brave.com/search/api/>
- tldraw, clé de licence : <https://tldraw.dev/sdk-features/license-key>
