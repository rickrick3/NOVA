# NOVA — Phase 0 : cadrage et architecture

Statut : **validé le 2026-10-09** par le message « proceed », recommandations retenues telles que proposées.

À cette date, aucun code produit n'a été écrit et aucune dépendance n'a été installée.

## Par où commencer

1. [09 — Risques et décisions ouvertes](09-risques-decisions.md) : l'état des trois points bloquants et des sept décisions est en tête du document.
2. [01 — Vision et périmètre](01-vision-perimetre.md) : ce que le MVP contient et ce qu'il exclut.
3. [02 — Architecture](02-architecture.md) : le schéma d'ensemble et les quinze décisions d'architecture.

Le reste se lit à la demande.

## Livrables

| # | Livrable demandé | Document |
| --- | --- | --- |
| 1 | Résumé de la vision et du périmètre du MVP | [01-vision-perimetre.md](01-vision-perimetre.md) |
| 2 | Diagramme d'architecture | [02-architecture.md](02-architecture.md) |
| 3 | Structure de modules | [03-modules.md](03-modules.md) |
| 4 | Modèle de données conceptuel | [04-modele-donnees.md](04-modele-donnees.md) |
| 5 | Principaux contrats d'API | [05-contrats-api.md](05-contrats-api.md) |
| 6 | Protocole de communication de l'agent local | [06-protocole-agent.md](06-protocole-agent.md) |
| 7 | Matrice de permissions | [07-permissions.md](07-permissions.md) |
| 8 | Choix technologiques et justifications | [08-choix-technologiques.md](08-choix-technologiques.md) |
| 9 | Risques techniques et décisions ouvertes | [09-risques-decisions.md](09-risques-decisions.md) |
| 10 | Backlog initial avec critères d'acceptation | [10-backlog.md](10-backlog.md) |

## Points bloquants et décisions

### Points bloquants

| # | Constat d'origine | État au 2026-10-09 |
| --- | --- | --- |
| B1 | 1,3 Go libres sur le disque C, aucun autre disque | Partiellement levé : 2,6 Go libres. Suffisant par estimation pour le plan 1A ; 10 Go nécessaires avant le plan 1D |
| B2 | Le dossier `NOVA` était dans le dépôt git d'un autre projet | Levé : dépôt dédié |
| B3 | Aucun fournisseur cloud configuré | Ouvert : clé d'API à fournir avant le récit P1-06 |

### Décisions retenues

| # | Sujet | Décision |
| --- | --- | --- |
| D1 | Cible du MVP | Un utilisateur, exécution locale |
| D2 | Premier fournisseur cloud et plafonds de dépense | Claude, `claude-opus-5-5` ; 1 $ par tâche, 5 $ par jour, 30 $ par mois au départ |
| D3 | Ordre des phases 4 et 5 | Agent local avant développement |
| D4 | Fournisseur de recherche | Tavily, derrière un port propre à NOVA |
| D5 | Nature du canvas | Scène d'artefacts typés |
| D6 | Génération d'images | Reportée |
| D7 | Langues de l'interface | Français et anglais |

Détail et alternatives : [09](09-risques-decisions.md).

## Conventions

- Les documents sont en français. Les identifiants techniques (états, types, champs, routes) sont en anglais ; leur libellé d'interface sera traduit.
- [04](04-modele-donnees.md) §1 est la référence du vocabulaire. Les autres documents le reprennent sans le redéfinir.
- Dans [08](08-choix-technologiques.md), chaque affirmation est marquée **[V]** vérifiée, **[E]** estimée ou **[H]** supposée.
- « Cahier des charges » désigne le prompt maître de NOVA. « M1 » à « M11 » désignent ses modules, « AC1 » à « AC12 » ses critères d'acceptation finaux.

## Vérifications faites sur ces documents

Exécutées le 2026-10-09.

| Vérification | Résultat |
| --- | --- |
| Cohérence entre documents, par script : 51 contrôles | 51 réussis, 0 anomalie |
| Capacité du script à détecter une erreur : 5 incohérences injectées dans une copie | Toutes détectées |
| Diagrammes Mermaid : 7 diagrammes analysés et rendus avec Mermaid 12.1.0 dans un navigateur | 7 rendus sans erreur ; schéma d'architecture relu visuellement |

Ce que le script contrôle :

- les 17 énumérations sont identiques partout où elles apparaissent ;
- les diagrammes d'états utilisent exactement les états déclarés, tous atteignables ;
- les 25 entités du diagramme, de la liste et du tableau coïncident, chacune rattachée à un module existant ;
- chaque action de l'agent a la même classe de permission dans le protocole et dans la matrice ;
- les 50 récits du backlog citent des modules existants ; chaque module, chaque invariant, chaque critère AC et chaque module M est couvert par au moins un récit ;
- toute référence à un invariant, une décision d'architecture, une décision ouverte ou un point bloquant pointe vers une définition ;
- les routes, codes d'erreur, capacités et événements cités hors du document d'API y figurent ;
- les liens entre documents aboutissent.

Ce script n'est pas dans le dépôt.

## Ce qui n'a pas été vérifié

- Aucun paquet n'a été installé : les versions citées sont celles des registres, leur compatibilité entre elles reste à constater à la Phase 1.
- Aucun appel réel à un fournisseur IA ou de recherche n'a été fait, faute de clé.
- La qualité des modèles locaux sur ce poste n'a pas été mesurée.
- L'export glTF, les fournisseurs d'images et la compatibilité de l'outillage avec TypeScript 7 sont des hypothèses.
- Le rendu des diagrammes n'a été testé que dans un navigateur, pas dans d'autres visionneuses Markdown.

## Suite

La Phase 1 est découpée en quatre plans d'implémentation ([10](10-backlog.md) §3). Chaque plan est soumis à ta relecture avant la première ligne de code. Les plans sont dans `docs/superpowers/plans/`.
