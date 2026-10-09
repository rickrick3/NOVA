# 07 — Matrice de permissions

Statut : validé le 2026-10-09

## 1. Classes

<!-- enum:permission_class -->
Classes : `A`, `B`, `C`, `D`

| Classe | Nature | Règle | Trace |
| --- | --- | --- | --- |
| `A` | Sans impact externe significatif | Autorisée dans le cadre de la demande | Étape de tâche |
| `B` | Modification locale réversible | Autorisée si une autorisation permanente la couvre ; sinon demande à l'utilisateur, qui peut la mémoriser pour cette portée | Étape de tâche et journal d'audit |
| `C` | Action sensible | Confirmation explicite de l'action exacte, à chaque fois. Jamais mémorisable | Étape de tâche et journal d'audit |
| `D` | Action interdite | Refus systématique, sans possibilité de confirmation | Journal d'audit |

## 2. Qui peut faire quoi

Trois acteurs, trois niveaux de confiance.

| Acteur | Ce qu'il peut faire |
| --- | --- |
| Utilisateur authentifié | Tout ce que le Studio propose. Seul à pouvoir approuver, valider, confirmer une décision et modifier les réglages |
| Modèle IA | Proposer des appels d'outils. Chaque appel est classé puis autorisé, soumis à confirmation ou refusé par le code |
| Contenu externe (page Web, document, fichier lu) | Rien. C'est une donnée ; il ne peut ni déclencher une action ni modifier une permission |

## 3. Algorithme de décision

Exécuté par le Core pour chaque appel d'outil, avant toute exécution.

1. **Décrire.** L'outil produit la description canonique de l'action : nom, paramètres, ressources touchées.
2. **Interdire.** Si une règle de classe D s'applique : refus.
3. **Classer.** Déterminer la classe A, B ou C à partir de l'action et de ses paramètres.
4. **Contamination.** Si le tour contient du contenu externe, les autorisations permanentes sont suspendues (§6).
5. **Décider.**
   - Classe A : autorisée.
   - Classe B : autorisée si une autorisation permanente active couvre l'action et que le tour n'est pas contaminé ; sinon, demande d'approbation.
   - Classe C : demande d'approbation, toujours.
6. **Tracer.** La décision est inscrite au journal d'audit, quelle qu'elle soit.
7. **Revérifier.** Si l'action s'exécute sur le poste, l'agent applique sa propre politique à la commande reçue ([06](06-protocole-agent.md)).

Le texte produit par le modèle n'entre dans aucune de ces étapes autrement que comme paramètres validés par un schéma.

## 4. Matrice

### 4.1 Actions du Core

| Action | Classe | Condition ou remarque |
| --- | --- | --- |
| Discuter, analyser, résumer, proposer un design | `A` | — |
| Poser une question, proposer un plan, une décision, un élément de mémoire | `A` | Une proposition n'est jamais une décision |
| Appeler un fournisseur cloud | `A` | Projet en `cloud_allowed` et message non marqué « local uniquement » |
| Appeler un fournisseur cloud | `D` | Projet en `local_only` ou message marqué « local uniquement » |
| Lancer une recherche Web, récupérer une page publique | `A` | Projet avec `web_access` à `enabled` |
| Lancer une recherche Web, récupérer une page | `D` | Projet avec `web_access` à `disabled` |
| Récupérer une adresse privée, de bouclage, ou hors `http`/`https` | `D` | — |
| Créer ou réviser un artefact dans le stockage de NOVA | `B` | Autorisation permanente créée par défaut avec le projet, révocable |
| Transmettre au cloud le contenu de fichiers lus par l'agent | `B` | Autorisation permanente par projet et par répertoire ; les secrets détectés sont masqués |
| Transmettre au cloud un contenu où un secret a été détecté, sans masquage | `C` | La demande montre ce qui a été détecté |
| Supprimer un projet, une conversation, un artefact ou un élément de mémoire à l'initiative de NOVA | `C` | À l'initiative de l'utilisateur dans le Studio : action directe avec confirmation d'interface |
| Confirmer une décision, valider une version, approuver une demande | `D` pour le modèle | Réservé à l'utilisateur |
| Modifier permissions, confidentialité, budgets, configuration des fournisseurs | `D` pour le modèle | Réservé à l'utilisateur |
| Créer un artefact `test_run` | `D` pour le modèle | Réservé au système, à partir d'un résultat de l'agent |

### 4.2 Actions de l'agent local

| Action | Classe | Condition ou remarque |
| --- | --- | --- |
| `fs.list`, `fs.read`, `fs.search` | `A` | Dans un répertoire autorisé, hors motifs interdits |
| `fs.write` | `B` | Création d'un fichier dans l'espace dédié du répertoire |
| `fs.apply_patch` | `C` | Modification de fichiers du projet. Diff présenté, point de reprise créé avant application |
| `fs.delete` | `C` | — |
| `cmd.run` | `B` | Commande prédéfinie dans la politique locale |
| `cmd.run` | `C` | Commande prédéfinie déclarée `sensitive` (installation de dépendances, par exemple) |
| `git.status`, `git.diff`, `git.log` | `A` | — |
| `git.checkpoint`, `git.commit` | `B` | Commit sur une branche préfixée `nova/` uniquement |
| `git.restore_checkpoint` | `C` | Écrase l'état courant des fichiers concernés |
| Commande arbitraire | Refus au MVP | Classe C dans le principe ; non prise en charge tant que `allow_arbitrary_commands` reste à `false` |
| Publication, déploiement, `git push` | Refus au MVP | Classe C dans le principe ; non implémenté |
| `git reset --hard`, `clean`, `rebase`, forçage, suppression de branche, modification de la configuration git | `D` | — |
| Accès hors des répertoires autorisés, échappement par lien ou jonction, motif interdit | `D` | — |
| Modifier la politique locale de l'agent | `D` | Seul l'utilisateur modifie ce fichier, à la main |
| Contrôle de la souris, du clavier ou d'applications | `D` | Hors périmètre |

## 5. Points d'application

| Point | Applique | Source de vérité |
| --- | --- | --- |
| Core — moteur de permissions | Classement, autorisations permanentes, demandes d'approbation, contamination, confidentialité | Base du Core |
| Agent — politique locale | Répertoires, motifs interdits, commandes déclarées, classe de chaque action, présence et empreinte de l'approbation | Fichier local `policy.toml` |
| Studio | Aucun contrôle de sécurité. Il affiche et recueille la décision de l'utilisateur | — |

Les deux premiers points sont indépendants. Le Core peut restreindre davantage que l'agent ; il ne peut pas l'élargir.

## 6. Contenu externe et contamination

Un tour est **contaminé** dès qu'un contenu venu de l'extérieur entre dans le contexte du modèle : résultat de recherche, page récupérée, document importé.

| # | Règle |
| --- | --- |
| C1 | Le contenu externe est transmis au modèle dans un bloc délimité et étiqueté comme donnée non fiable. |
| C2 | Dans un tour contaminé, aucune autorisation permanente ne s'applique : toute action de classe B demande une approbation. |
| C3 | Dans un tour contaminé qui contient aussi des données lues sur le poste, toute nouvelle requête sortante (recherche, récupération de page) demande une approbation. Cela ferme la fuite de données par l'adresse d'une requête. |
| C4 | Une demande d'approbation émise dans un tour contaminé le signale à l'utilisateur. |
| C5 | Aucun contenu externe ne peut créer, modifier ou satisfaire une approbation : celle-ci n'existe que par une requête authentifiée, protégée contre le CSRF, portant l'empreinte de l'action. |

Ces règles limitent les conséquences d'une instruction malveillante ; elles ne garantissent pas que le modèle l'ignore. Le texte d'une réponse peut rester influencé, ce que l'utilisateur doit savoir.

## 7. Demande d'approbation

Une demande présente toujours :

| Élément | Contenu |
| --- | --- |
| Action | Nom et paramètres exacts |
| Éléments concernés | Fichiers, répertoire, commande, destinataire |
| Conséquences | Ce qui sera créé, modifié, supprimé ou transmis |
| Risques | Ce qui peut mal tourner |
| Retour arrière | Possible ou non, et comment |
| Origine | Tâche et étape ; tour contaminé ou non |
| Échéance | Dix minutes par défaut ; expirée, elle doit être redemandée |

<!-- enum:approval_status -->
Statuts : `pending`, `approved`, `denied`, `expired`, `consumed`

Règles :

- Une approbation vaut pour une action, identifiée par son empreinte, et une seule exécution.
- Le Studio renvoie l'empreinte de l'action qu'il a affichée. Si l'action a changé entre-temps, la décision est refusée.
- Approuver une action n'autorise ni la suivante ni une action semblable.
- Seule la classe B peut donner lieu à une autorisation permanente, sur une portée précise : projet, type d'action, répertoire ou identifiant de commande.
- Toute autorisation permanente est consultable et révocable dans le Studio.

## 8. Journal d'audit

Sont journalisés : chaque décision de permission, chaque approbation ou refus, chaque commande envoyée à l'agent et son issue, chaque validation de version, chaque confirmation de décision, chaque appairage ou révocation, chaque appel à un fournisseur cloud (fournisseur, modèle, volumes), chaque suppression de données, chaque modification de réglage de sécurité.

| Champ | Contenu |
| --- | --- |
| Acteur | `user`, `nova`, `agent` ou `system` |
| Action et classe | Nom canonique, classe attribuée |
| Ressource | Résumé sans contenu sensible |
| Décision | `allowed`, `confirmed`, `denied`, `refused` |
| Liens | Tâche, étape, demande d'approbation |
| Issue | `succeeded`, `failed`, `rejected`, `cancelled` |

Le journal est en ajout seul (INV-8). Il ne contient ni contenu de fichier, ni texte de message, ni secret.

## 9. Tests

La matrice est la spécification des tests de permissions : chaque ligne donne au moins un cas autorisé et un cas refusé. Les lignes de l'agent sont testées deux fois, contre le moteur du Core et contre l'agent seul, pour vérifier que l'agent refuse même si le Core laisse passer.
