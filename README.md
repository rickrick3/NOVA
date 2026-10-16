 # NOVA

NOVA est un assistant IA personnel : un studio Web, un Core d'orchestration et un agent local. Ce dépôt contient les trois.

Le cadrage, l'architecture et l'état des décisions sont dans [docs/phase-0/README.md](docs/phase-0/README.md). Les plans d'implémentation sont dans `docs/superpowers/plans/`.

## Installation

Prérequis : Python 3.13 et [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-packages
```

Si l'installation échoue sur une erreur de certificat (`invalid peer certificate: UnknownIssuer`), le trafic HTTPS du poste est inspecté par un proxy ou un antivirus. Faire alors confiance au magasin de certificats du système :

```bash
uv sync --all-packages --system-certs
```

## Tests et contrôles

Depuis `services/core` :

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

La suite ne fait aucun appel réseau et ne consomme aucune API payante.

## Démarrer le Core

Depuis `services/core` :

```bash
uv run python -m nova_core
```

Le Core écoute sur `http://127.0.0.1:8000` et range ses données dans le répertoire applicatif de l'utilisateur (`%LOCALAPPDATA%\NOVA` sous Windows). Les réglages se passent par variables d'environnement préfixées `NOVA_`, ou par un fichier `.env` : `NOVA_DATA_DIR` pour un autre répertoire de données, `NOVA_PORT` si le port 8000 est pris.

La page interactive de l'API est désactivée par défaut, parce qu'elle charge des scripts depuis un CDN public. Pour le développement, `NOVA_API_DOCS=1` la sert sur `/api/v1/docs`.

## État actuel

Plan 1A livré — socle du Core :

- compte local et sessions, avec contrôle de l'hôte, de l'origine, jeton CSRF et limitation des tentatives de connexion ;
- projets, objectifs, exigences et contraintes ;
- stockage privé de fichiers, journal d'audit en ajout seul ;
- `GET /api/v1/system/capabilities`, qui dit ce que le Core sait réellement faire.

Limites connues :

- toutes les capacités — conversation, recherche, images, agent local, voix — sont déclarées `not_implemented` ; elles arrivent avec les plans 1B à 1D, et il n'y a pas encore d'interface ;
- il n'existe aucun moyen de changer ou de récupérer le mot de passe du compte local : en cas d'oubli, il faut supprimer le répertoire de données ;
- pour les migrations en ligne de commande, la base doit être désignée explicitement : `uv run alembic -x database_url=sqlite:///chemin/nova.db upgrade head`.

Le contrat d'API est figé dans `services/core/openapi.json`. Après un changement voulu de l'API, le régénérer :

```bash
NOVA_UPDATE_SNAPSHOTS=1 uv run pytest tests/test_openapi_snapshot.py -q
```
