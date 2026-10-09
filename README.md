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
