# Plan 1A — journal d'exécution

Plan : [2026-10-09-phase-1a-socle-core.md](2026-10-09-phase-1a-socle-core.md) · Branche : `phase-1a-socle-core` · 2026-10-09

Ce journal consigne ce que le plan ne décidait pas ou décidait mal, la revue finale, et ce qui a été volontairement laissé de côté. Chaque décision indique ce qu'elle coûte si elle est mauvaise.

## Résultat

| Élément | État |
| --- | --- |
| Tâches du plan | 9 sur 9, un commit par tâche |
| Tests | 128 réussis ; aucun appel réseau |
| Contrôles | `ruff check`, `ruff format --check` et `mypy --strict` sans signalement |
| Démarrage réel | Vérifié deux fois avec `python -m nova_core` sur un répertoire de données jetable |
| Revue finale | Un relecteur indépendant sur toute la branche : 1 défaut critique, 8 importants, tous corrigés |

## Décisions prises pendant l'exécution

### Mise en place

| Décision | Raison | Coût si elle est mauvaise |
| --- | --- | --- |
| Travail sur une branche dans le dépôt principal, sans copie de travail séparée | Le plan nomme la branche ; le disque était presque plein | Le dépôt porte le travail en cours jusqu'à la fusion |
| Les routes système et d'audit reçoivent le contrôle de session par injection depuis `app.py` | Le plan plaçait une route authentifiée dans `kernel`, qui ne doit importer aucun module métier | Un paramètre de plus |

### Tâche par tâche

| Tâche | Décision | Raison | Coût si elle est mauvaise |
| --- | --- | --- | --- |
| 1 | `uv sync` exécuté avec `--system-certs` | Le poste inspecte le trafic HTTPS ; uv refusait le certificat. La vérification reste faite, contre le magasin du système | Aucun |
| 1 | Dépendance déclarée `sqlalchemy[asyncio]` | Le moteur asynchrone de SQLAlchemy 2.1 exige `greenlet` | Un paquet de plus |
| 1 | Tests du plan passés au formateur ; règle S104 ignorée dans les tests | Le code de test du plan dépassait la limite de 100 colonnes que le plan fixe | Aucun, mise en forme seulement |
| 1 | Code `method_not_allowed` pour les réponses 405, ajouté au contrat | Le contrat n'avait pas de code pour ce cas | Renommer un code |
| 1 | Les erreurs inattendues sont rendues par le middleware de requête | La réponse 500 garde son identifiant de requête et n'est journalisée qu'une fois | Aucun |
| 2 | L'environnement Alembic ne reconfigure pas la journalisation | L'appel habituel aurait désactivé les journaux de l'application | Aucun |
| 3 | Le ramassage des fichiers orphelins ne s'exécute qu'au démarrage | Un fichier en cours d'écriture ressemble à un orphelin | Un fichier libéré reste sur le disque jusqu'au redémarrage suivant |
| 5 | La connexion renvoie le même corps que `GET /auth/session` | Le plan liste les trois mêmes champs | Aucun |
| 7 | L'alias de dépendance de session de base déplacé dans `kernel` | Tous les modules le partagent sans passer par `identity` | Aucun |
| 8 | `SpecItemService.list` annoncé comme renvoyant une séquence | Dans une classe qui définit une méthode `list`, le vérificateur de types confond les deux | Aucun |
| 8 | Routes `/spec-items/{id}` sur un second routeur | Leur chemin n'est pas sous `/projects` | Aucun |
| 9 | Vérification du démarrage réel sur un répertoire jetable | Ne pas créer le vrai répertoire de données de l'utilisateur pendant un test | L'emplacement par défaut n'est exercé qu'au premier vrai lancement |
| 9 | Journal d'accès d'uvicorn désactivé | Il doublait la ligne par requête demandée par le plan | Un argument |

### Sonde de concurrence SQLite

Avec SQLAlchemy 2.1.4 et aiosqlite 0.22.1, une session qui lit puis écrit après la validation d'une autre session n'obtient pas d'erreur de verrou. Aucune transaction immédiate n'est donc nécessaire. À resonder si l'une des deux bibliothèques change de version.

## Revue finale

Relecteur indépendant, sans contexte préalable, sur toute la branche. Il a tourné sur Opus et non sur le modèle le plus coûteux, puisque le mode d'exécution économique avait été choisi ; un relecteur plus puissant aurait pu trouver davantage.

Chaque correction a d'abord été reproduite par un test qui échouait.

| # | Défaut | Correction |
| --- | --- | --- |
| C1 | Sur le vrai serveur, un en-tête `X-Forwarded-For` différent à chaque requête contournait la limite de tentatives de connexion. Le test du plan ne le voyait pas | En-têtes de proxy désactivés dans uvicorn ; mémoire du limiteur bornée. Revérifié sur le vrai serveur : 5 refus `401` puis `429` |
| I1 | Un curseur de pagination forgé (date sans fuseau, entier hors limites, imbrication profonde) renvoyait `500` | Curseur plafonné à 512 caractères et validé ; réponse `422` |
| I2 | Le test « aucune route ne modifie l'audit » ne pouvait pas échouer | Test refait sur le schéma et sur les réponses réelles, avec un second test qui prouve qu'il détecte une route d'écriture |
| I3 | Une erreur de base de données écrivait dans le journal les valeurs liées : jeton CSRF, empreintes | Paramètres masqués sur les moteurs |
| I4 | Changer `llm_privacy` ou `web_access`, ou supprimer un élément, ne laissait aucune trace d'audit | Actions `project.settings_changed` et `spec_item.deleted` |
| I5 | Compteur de références des fichiers faussé par deux écritures entrelacées ; un second lancement pouvait supprimer un fichier en cours d'écriture | Incrément fait par la base en une instruction ; fichiers de moins de 5 minutes épargnés au démarrage |
| I6 | Le test d'architecture se contournait par `all_models`, `app` ou un fichier ajouté à la racine du paquet | Ces chemins sont maintenant signalés |
| I7 | Le schéma OpenAPI figé décrivait un format d'erreur que le serveur n'envoie jamais | Corps `problem+json` documentés sur chaque opération |
| I8 | La page interactive de l'API était publique et chargeait des scripts depuis un CDN | Désactivée par défaut ; `NOVA_API_DOCS=1` pour le développement |
| — | En ligne de commande, Alembic visait par défaut la vraie base de l'utilisateur | L'URL de la base doit être donnée explicitement |

Deux décisions antérieures sont ainsi annulées : la page de documentation servie par défaut (tâche 1) et « les éléments de projet ne sont pas audités » (contrôle préalable).

### Décisions prises pendant la passe de correction

| Décision | Raison | Coût si elle est mauvaise |
| --- | --- | --- |
| Pas de verrou d'instance unique | Fonction nouvelle ; le délai de grâce ferme la course sur les fichiers | Deux Cores lancés sur le même répertoire exécutent tous deux les migrations avant que le second n'échoue sur le port |
| Les imports dynamiques et les SDK hors des quatre nommés restent invisibles du test d'architecture | Limite de l'analyse statique ; liste fixée par le plan | Un contournement délibéré passe |
| Erreurs documentées par une réponse `default` par opération, plus le cas `422` | Suffisant pour des types clients corrects | Le schéma ne dit pas quels statuts une route donnée renvoie |
| Âge des fichiers mesuré avec l'heure du système | Les dates de fichiers viennent du système de fichiers, pas de l'horloge injectée | Aucun |
| Instruction `INSERT … ON CONFLICT` propre à SQLite et PostgreSQL | Rendre le compteur atomique en une instruction | Un troisième moteur demanderait sa propre instruction |
| `projects` importe directement les dépendances d'`identity` ; le tableau des modules a été amendé | La règle 2 autorise l'import des dépendances d'un autre module | Un routeur injecté de plus |

### Points que le relecteur a écartés, et ce qui en est décidé

| Point | Décision | Coût si elle est mauvaise |
| --- | --- | --- |
| Aucune route pour changer ou récupérer le mot de passe | Maintenu pour ce plan ; indiqué dans le README | Un mot de passe oublié oblige à supprimer le répertoire de données |
| Session de 7 jours sans renouvellement ; une nouvelle connexion ne révoque pas les précédentes ; le jeton CSRF d'un second onglet devient invalide | Maintenu ; le Studio devra relire la session sur `csrf_failed` | Un refus déroutant dans un second onglet |
| Pas de CORS | Maintenu ; le serveur de développement du Studio passera par un proxy | Un middleware à ajouter au plan 1D |
| Mode hébergé incomplet | Maintenu, décision D1 | Aucun pour l'instant |
| Pas de limite de taille des requêtes | Maintenu en mode local | Un processus local peut faire lire un corps très volumineux |
| Un double envoi crée deux projets | Maintenu ; le Studio désactivera le bouton | Un doublon à supprimer |
| Modifier une proposition de NOVA ne la confirme pas ; un projet archivé accepte encore les écritures | Maintenu tel que construit | Une règle à ajouter quand le Studio existera |
| Type de média des fichiers non validé ; clé mal formée signalée par une erreur interne | Maintenu tant qu'aucune route ne sert de fichier | À régler avec le premier consommateur |
| Pas de bus d'événements ni de limite de débit sur les messages et les tâches | Relève du plan 1B | Aucun pour l'instant |
| Comportement sous PostgreSQL, index secondaires | Reporté avec l'hébergement | Aucun pour un utilisateur local |

## Points mineurs reportés

Aucun n'a été corrigé. Ils sont à reprendre dans les plans suivants ou sur demande.

Durcissement :

- L'immutabilité de l'audit n'est garantie que sur les objets ; une instruction de mise à jour ou de suppression en masse passerait.
- Les clés interdites dans les ressources d'audit sont comparées exactement : `csrf_token`, `password_hash` ou une valeur imbriquée seraient acceptés.
- Nom d'utilisateur et mot de passe ne sont pas normalisés en Unicode : un même accent saisi sous une autre forme ne correspond pas.
- `NOVA_HOST=::1` est accepté alors que son en-tête `Host` est refusé ; le mode `test` accepte `0.0.0.0` ; le port de développement du Studio est toujours une origine autorisée.
- Les connexions non HTTP échappent au contrôle `Host` et `Origin` : à fermer avant le WebSocket de l'agent.
- Le répertoire de données est créé avec les permissions par défaut sous Linux et macOS.
- Un recul de l'horloge du système peut allonger un blocage du limiteur.
- Les sessions expirées ne sont jamais purgées.

Robustesse :

- La création du projet par défaut n'est pas protégée contre deux lancements simultanés.
- Les fichiers temporaires laissés dans le stockage ne sont jamais ramassés.
- Le répertoire des migrations est résolu hors du paquet : une installation non modifiable ne démarre pas. Aucune sauvegarde de la base avant migration.
- `PATCH` ignore un `null` explicite, met à jour la date même sans changement, et accepte un nom fait de caractères de largeur nulle.
- `SpecItemService.propose` valide la transaction : à changer avant que l'orchestrateur du plan 1C ne l'appelle dans la sienne.
- Les erreurs 4xx du framework autres que 401, 403, 404, 405 et 429 portent le code `validation_error`.
- Les horodatages des journaux sont en heure locale ; un champ de couleur d'uvicorn apparaît dans les lignes JSON.

Tests et documentation :

- Les tests lisent les variables `NOVA_*` de l'environnement : deux échouent si `NOVA_PORT` est défini.
- Pas de test générique vérifiant sur chaque route le refus sans session et sans jeton CSRF ; le relecteur l'a vérifié à la main, tout est correct.
- Le nom du projet par défaut, « Espace libre », est écrit en dur dans le Core ; le Studio devrait le traduire à partir de l'indicateur `is_default`.
