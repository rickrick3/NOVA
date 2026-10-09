# 09 — Risques techniques et décisions ouvertes

Statut : validé le 2026-10-09

## 0. État au 2026-10-09

La Phase 0 a été validée le 2026-10-09 par le message « proceed », sans réserve exprimée. Les recommandations ont donc été retenues telles que proposées. Chaque ligne reste révisable sur simple demande.

| # | État |
| --- | --- |
| B1 | **Partiellement levé.** 2,6 Go libres constatés. Suffisant, par estimation, pour le plan 1A (Core, Python seul) ; les 10 Go restent nécessaires avant le plan 1D (Studio) |
| B2 | **Levé.** Dépôt git dédié initialisé dans `NOVA` |
| B3 | **Ouvert.** Fournisseur retenu (D2), clé d'API à fournir avant le récit P1-06 |
| D1 | Retenue : un utilisateur, exécution locale |
| D2 | Retenue : Claude, `claude-opus-5-5` ; plafonds de départ de 1 $ par tâche, 5 $ par jour, 30 $ par mois, modifiables dans les réglages |
| D3 | Retenue : agent local avant développement. Rappel prévu à la fin de la Phase 3 |
| D4 | Retenue : Tavily. Clé à fournir avant la Phase 2 |
| D5 | Retenue : scène d'artefacts typés |
| D6 | Retenue : génération d'images reportée |
| D7 | Retenue : français et anglais |

Les sections suivantes conservent l'analyse d'origine.

## 1. Points bloquants avant la Phase 1

Ces trois points empêchent de commencer. Aucun ne se règle sans toi.

### B1 — Espace disque : 1,3 Go libres sur le disque C

Constaté sur le poste ; il n'y a pas d'autre disque. L'installation des dépendances de la Phase 1 échouera ou saturera le système.

Besoin estimé — estimation, non mesurée :

| Poste | Ordre de grandeur |
| --- | --- |
| Environnements Python (Core, agent) | 0,5 Go |
| `node_modules` du Studio | 0,5 à 1 Go |
| Navigateur de test Playwright | 0,5 Go |
| Caches `uv` et `npm` | 1 Go |
| Données de NOVA, journaux, marge | 2 Go |

**Demande : libérer au moins 10 Go avant la Phase 1.** Piste à ta main : les modèles Ollama occupent 7,45 Go, dont `phi` (1,6 Go) que NOVA ne peut pas utiliser. Je ne supprime rien sans ton accord.

### B2 — Le dossier `NOVA` est dans un dépôt git sans rapport

`NOVA` se trouve dans le dépôt `projects`, branche `farel`, relié au dépôt distant `python-for-finances-`. Un commit de NOVA partirait dans l'historique de cet autre projet.

**Recommandation : un dépôt git dédié, initialisé dans `NOVA`.** Le dépôt parent le verra comme un dossier non suivi. Rien n'a été commité dans cette phase : les documents sont sur le disque, non versionnés.

### B3 — Aucun fournisseur cloud configuré

Aucune clé d'API n'est présente dans l'environnement. Voir la décision D2.

Sans fournisseur cloud, la Phase 1 reste réalisable et testable : faux fournisseurs pour les tests automatisés, Ollama pour l'usage réel. Mais le critère de sortie « analyser une idée » ne serait démontré qu'avec un modèle local de 3 à 7 milliards de paramètres sur un poste sans carte graphique, donc avec une qualité incertaine.

## 2. Décisions à valider

Chaque décision porte une recommandation et ce qui sera appliqué si tu ne te prononces pas.

| # | Décision | Recommandation | Si tu ne dis rien | À trancher avant |
| --- | --- | --- | --- | --- |
| D1 | Cible du MVP | Un seul utilisateur, exécution locale ; hébergement possible plus tard | Recommandation appliquée | Phase 1 |
| D2 | Premier fournisseur cloud, modèle par défaut, plafonds de dépense | Claude ; `claude-opus-5-5` ; plafonds de départ suggérés : 1 $ par tâche, 5 $ par jour, 30 $ par mois | Phase 1 construite sur Ollama et les faux fournisseurs ; l'adaptateur cloud attend ta décision | Phase 1, récit P1-06 |
| D3 | Ordre des phases 4 et 5 | Construire l'agent local (Phase 5) avant le développement (Phase 4) | **Bloquant pour la Phase 4** : je redemanderai | Fin de la Phase 3 |
| D4 | Fournisseur de recherche | Tavily derrière le port `SearchProvider` | Je redemanderai : une clé est nécessaire | Phase 2 |
| D5 | Nature du canvas | Scène d'artefacts typés, sans tableau blanc infini | Recommandation appliquée | Phase 3 |
| D6 | Génération d'images matricielles | Reporter ; le MVP s'appuie sur maquettes HTML, diagrammes et scènes 3D | Non implémentée ; capacité affichée comme indisponible | Phase 3 |
| D7 | Langues de l'interface | Français et anglais dès la Phase 1 | Recommandation appliquée | Phase 1 |

### D3 en détail

Le cahier des charges place le développement (Phase 4) avant l'agent local (Phase 5). Or le critère de sortie de la Phase 4 — implémenter une version approuvée dans un projet de test et présenter les différences — exige d'écrire des fichiers et de lancer des tests, ce qui est précisément le rôle de l'agent.

| Option | Conséquence |
| --- | --- |
| **Agent d'abord, développement ensuite** (recommandé) | L'ordre devient 0, 1, 2, 3, 5, 4, 6. Les critères de sortie de chaque phase restent ceux du cahier des charges. Aucun code jetable |
| Ordre du cahier des charges | La Phase 4 doit embarquer un exécuteur provisoire dans le Core, avec ses propres contrôles de chemins et de commandes, remplacé en Phase 5. Travail en double et surface de risque supplémentaire |

Le backlog garde la numérotation du cahier des charges et indique l'ordre d'exécution recommandé.

### Choix par défaut, appliqués sauf objection

| Sujet | Choix |
| --- | --- |
| Authentification locale | Compte avec mot de passe, même en local |
| Emplacement des données | Répertoire de données applicatif de l'utilisateur, hors du dépôt |
| Clés d'API | Dans un fichier `.env` ignoré par git ; jamais saisies dans le Studio au MVP |
| Gestionnaire de paquets JavaScript | npm, déjà installé |
| Identifiants techniques | En anglais ; libellés d'interface traduits |

## 3. Écarts et ambiguïtés du cahier des charges

Relevés à la lecture, avec la résolution proposée.

| # | Constat | Résolution |
| --- | --- | --- |
| E1 | La Phase 4 dépend de l'agent livré en Phase 5 | Décision D3 |
| E2 | Un rapport de recherche (Phase 2) doit être sauvegardé et versionné, mais les versions arrivent en Phase 3 | Le socle des artefacts (artefact, version, contenu) est livré en Phase 2 ; comparaison, commentaires et validation en Phase 3 |
| E3 | « Canvas » n'est pas défini : visionneuse de livrables ou tableau blanc | Décision D5 |
| E4 | Les commandes arbitraires sont classées C, mais l'agent doit n'exécuter que des commandes « explicitement permises » | Au MVP, seules les commandes prédéfinies s'exécutent ; les commandes arbitraires sont refusées |
| E5 | « WebSocket ou mécanisme équivalent » pour le temps réel | SSE vers le Studio, WebSocket pour l'agent (ADR-03) |
| E6 | La mémoire doit distinguer quatre catégories, dont les décisions confirmées | Trois catégories de mémoire et une entité `Decision` à part, pour qu'une proposition ne puisse pas passer pour une décision |

## 4. Risques techniques

Probabilité et impact : faible, moyen, élevé — appréciations, non mesurées.

| # | Risque | Prob. | Impact | Parade | Phase |
| --- | --- | --- | --- | --- | --- |
| R1 | Les modèles locaux disponibles ne suffisent pas pour l'orchestration par outils | Élevée | Élevé | Mesure dès la Phase 1 ; capacités annoncées honnêtement par modèle ; fournisseur cloud recommandé | 1 |
| R2 | Injection d'instructions par une page Web ou un document | Élevée | Élevé | Permissions en code, contamination, approbations liées à l'action, double contrôle par l'agent. Le texte des réponses peut rester influencé | 2, 5 |
| R3 | Dépense cloud non maîtrisée | Moyenne | Moyen | Plafonds par tâche, jour et mois ; usage enregistré par appel ; blocage explicite au plafond | 1 |
| R4 | Erreurs de validation de chemins sous Windows (jonctions, casse, chemins UNC, noms réservés) | Moyenne | Élevé | Algorithme en six étapes, tests dédiés par cas, refus par défaut | 5 |
| R5 | Une commande de test exécute du code du projet sans isolation | Moyenne | Élevé | Commandes prédéfinies uniquement, répertoires approuvés, environnement réduit, bornes de durée. Isolation par conteneur reportée | 5 |
| R6 | Un aperçu HTML généré s'échappe de son cadre ou appelle le réseau | Faible | Élevé | Cadre isolé à origine opaque, politique de sécurité de contenu sans réseau, tests dédiés | 3 |
| R7 | Le périmètre — onze modules — dépasse la capacité d'une équipe réduite | Élevée | Élevé | Phases à critère de sortie strict, validation à chaque jalon, périmètre du MVP réduit et explicite | Toutes |
| R8 | Le code généré est incorrect | Élevée | Moyen | Aucune application sans diff approuvé ; tests réellement exécutés ; point de reprise et restauration | 4 |
| R9 | Écart de comportement entre SQLite et PostgreSQL | Moyenne | Moyen | Types génériques, pas de fonction propre à un moteur ; suite à rejouer sur PostgreSQL avant tout hébergement | Après le MVP |
| R10 | Une tâche longue est perdue au redémarrage du Core | Moyenne | Faible | État persisté, tâche marquée interrompue et relançable. Reprise à chaud reportée | 1 |
| R11 | Un fournisseur modifie son API ou ses tarifs | Moyenne | Moyen | Adaptateurs isolés, prix en configuration datée, tests `live` de fumée | Toutes |
| R12 | L'outillage n'est pas compatible avec TypeScript 7 | Faible | Faible | Vérification à la création du gabarit ; repli sur la version majeure précédente | 1 |
| R13 | Quotas ou conditions d'usage du fournisseur de recherche | Moyenne | Moyen | Port `SearchProvider` ; limites de la recherche affichées dans chaque rapport | 2 |
| R14 | Pages non extractibles (JavaScript, accès restreint) | Élevée | Faible | Signalées comme telles dans le rapport ; jamais remplacées par un contenu supposé | 2 |
| R15 | Les scènes 3D attendues dépassent ce qu'une description par primitives permet | Moyenne | Moyen | Périmètre annoncé : scènes paramétriques simples ; export annoncé seulement après test | 3 |
| R16 | Trop d'onglets ouverts épuisent les connexions SSE du navigateur | Faible | Faible | Un seul flux par onglet ; limite documentée | 1 |

## 5. Limites connues du MVP

À afficher dans le produit et à rappeler lors de la démonstration finale.

- Une tâche interrompue par un redémarrage du Core n'est pas reprise ; elle est relançable.
- Les commandes exécutées par l'agent ne sont pas isolées dans un conteneur.
- La mémoire ne fait pas de recherche sémantique.
- La recherche ne lit ni les pages exigeant JavaScript ni les PDF.
- Les données déjà transmises à un fournisseur cloud ne peuvent pas être effacées par NOVA.
- La voix n'est pas implémentée.
- La contradiction argumentée et la qualité des analyses dépendent du modèle utilisé ; elles sont démontrées, pas garanties.
