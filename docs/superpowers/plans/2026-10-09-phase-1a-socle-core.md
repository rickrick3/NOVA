# NOVA Core — Socle (plan 1A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un NOVA Core qui démarre, persiste ses données, authentifie l'utilisateur local, gère les projets et dit honnêtement ce qu'il ne sait pas encore faire.

**Architecture:** Monolithe modulaire FastAPI. Les modules métier `storage`, `audit`, `identity` et `projects` ont chacun les couches `api`, `service`, `repository`, `schemas` et `models`, et ne touchent jamais les tables d'un autre. Le noyau `kernel` porte la configuration, la base, les erreurs, l'horloge, la pagination, la limitation de débit et le registre de capacités. SQLite via SQLAlchemy asynchrone ; schéma géré par Alembic.

**Tech Stack:** Python 3.13, uv, FastAPI, Pydantic 2, SQLAlchemy 2 avec aiosqlite, Alembic, argon2-cffi, pytest, httpx, ruff, mypy.

**Spec:** `docs/phase-0/` — en particulier `02-architecture.md` §6, `03-modules.md` §2 et §3, `04-modele-donnees.md`, `05-contrats-api.md` §1 à §4.1 et §8, `07-permissions.md` §8, `10-backlog.md` §3 (récits P1-01 à P1-04 et socle de P1-12).

## Global Constraints

- Python `>=3.13`. Dépendances d'exécution, versions planchers : `fastapi>=0.143.0`, `pydantic>=2.14.0`, `pydantic-settings>=2.15.0`, `uvicorn>=0.54.0`, `sqlalchemy>=2.1.4`, `alembic>=1.20.0`, `aiosqlite>=0.22.1`, `argon2-cffi>=25.1.0`.
- Dépendances de développement : `pytest>=9.1.1`, `pytest-asyncio>=1.4.0`, `httpx>=0.28.1`, `ruff>=0.16.10`, `mypy>=2.4.0`.
- `uv.lock` est versionné. Aucune autre dépendance sans mise à jour de `docs/phase-0/08-choix-technologiques.md`.
- Toutes les routes sont sous `/api/v1`. JSON en UTF-8. Dates en ISO 8601, UTC.
- Toute erreur est rendue en `application/problem+json` avec un champ `code` pris dans `05-contrats-api.md` §8.
- Les valeurs énumérées sont celles de `04-modele-donnees.md` §1, à l'identique.
- Règles de dépendance de `03-modules.md` §2 : un module n'importe d'un autre que `service`, `schemas` ou `deps` ; `kernel` n'importe aucun module métier ; seul `providers` importe un SDK de fournisseur.
- En mode `local`, le Core n'écoute que sur une adresse de bouclage.
- Aucun mot de passe, jeton de session ou clé n'apparaît dans une réponse, un journal ou un événement d'audit.
- Colonnes de types génériques uniquement : texte, entier, booléen, horodatage UTC, JSON.
- La suite de tests s'exécute sans réseau.
- Identifiants et messages d'erreur (`detail`) en anglais. Le Core ne contient aucun texte d'interface.
- Un commit par tâche, message au format Conventional Commits, en anglais. `.env` n'est jamais commité.

## Review Focus

Cas que le cahier des charges implique sans les nommer, les plus susceptibles de gêner l'utilisateur. Chacun a son test dans la tâche indiquée.

1. Répertoire de données dont le chemin contient des espaces ou des accents (nom d'utilisateur Windows) : le Core démarre et la base est créée. — Task 2
2. Horodatages relus depuis SQLite sans fuseau : l'expiration d'une session se calcule sans erreur de type et au bon instant. — Task 2, Task 5
3. Double envoi du formulaire de création de compte : un seul compte, la seconde requête reçoit `already_set_up`, jamais une erreur 500. — Task 5
4. Redémarrage du Core : la session reste valide, les migrations se rejouent sans effet sur une base existante. — Task 5
5. Saisies aux limites — nom vide ou fait d'espaces, texte trop long, mot de passe avec caractères non ASCII, curseur de pagination altéré : réponse `422`, jamais `500`, et aucune valeur sensible renvoyée. — Task 4, Task 5, Task 7

---

## Structure des fichiers

```text
.gitignore  .gitattributes  README.md  pyproject.toml  uv.lock
services/core/
├── pyproject.toml
├── alembic.ini
├── openapi.json                    instantané du schéma (Task 9)
├── migrations/
│   ├── env.py                      moteur synchrone, importe nova_core.all_models
│   └── versions/                   0001_storage, 0002_audit, 0003_identity, 0004_projects, 0005_project_spec_items
├── src/nova_core/
│   ├── __init__.py                 __version__ = "0.1.0"
│   ├── __main__.py                 lance uvicorn sur settings.host et settings.port
│   ├── app.py                      create_app : racine de composition
│   ├── all_models.py               importe les models de chaque module
│   ├── kernel/
│   │   ├── config.py               Settings
│   │   ├── clock.py  ids.py        Clock, SystemClock, new_id
│   │   ├── errors.py               NovaError, rendu problem+json
│   │   ├── logging.py              journaux JSON, identifiant de requête
│   │   ├── db.py                   Base, UTCDateTime, moteur, get_session
│   │   ├── migrate.py              upgrade, downgrade, sync_url
│   │   ├── pagination.py           Page, encode_cursor, decode_cursor
│   │   ├── http_guards.py          contrôle Host et Origin
│   │   ├── ratelimit.py            TokenBucketLimiter, rate_limit
│   │   ├── capabilities.py         CapabilityRegistry
│   │   └── api.py                  /system/health, /system/capabilities
│   ├── storage/                    models, repository, service
│   ├── audit/                      models, repository, service, schemas, api
│   ├── identity/                   models, repository, service, schemas, api, deps
│   └── projects/                   models, repository, service, schemas, api
└── tests/
    ├── conftest.py  support.py
    ├── architecture/               import_rules.py, test_import_rules.py
    └── kernel/ storage/ audit/ identity/ projects/
```

## Décisions transverses

Ces décisions s'appliquent à toutes les tâches.

1. **Transactions.** `get_session` fournit une session et annule toute transaction ouverte à la fermeture ; il ne valide jamais. Un service appelé par une route valide (`await session.commit()`) à la fin de son cas d'usage, et lève avant d'écrire en cas de refus. Les services collaborateurs — `AuditService.record`, `BlobService.put`, `BlobService.release` — ne valident jamais : l'appelant le fait.
2. **Horloge.** Aucun appel direct à `datetime.now`. Tout instant vient de `clock.now()`, où `clock` est `app.state.clock`.
3. **Migrations.** `migrate.upgrade` est synchrone et utilise un pilote synchrone ; le démarrage l'appelle par `asyncio.to_thread`.
4. **Identifiants.** `new_id()` renvoie un UUID version 4 sous forme de chaîne. Toute colonne d'instant utilise `UTCDateTime`.
5. **Schémas de requête.** Tous déclarent `extra="forbid"`.
6. **Commandes.** `uv sync --all-packages` à la racine ; toutes les autres commandes depuis `services/core`.
7. **Branche.** Le travail se fait sur la branche `phase-1a-socle-core`.

---

### Task 1: Gabarit, configuration, erreurs et santé

**Files:**
- Create: `.gitignore`, `.gitattributes`, `README.md`, `pyproject.toml`, `services/core/pyproject.toml`
- Create: `services/core/src/nova_core/__init__.py`, `__main__.py`, `app.py`, `all_models.py`
- Create: `services/core/src/nova_core/kernel/__init__.py`, `config.py`, `clock.py`, `ids.py`, `errors.py`, `logging.py`, `api.py`
- Test: `services/core/tests/conftest.py`, `support.py`, `kernel/test_config.py`, `kernel/test_errors.py`, `kernel/test_health.py`, `architecture/import_rules.py`, `architecture/test_import_rules.py`

**Interfaces:**
- Produces:
  - `nova_core.__version__: str = "0.1.0"`
  - `Settings` (pydantic-settings, préfixe `NOVA_`) : `env: Literal["local", "test", "hosted"] = "local"`, `host: str = "127.0.0.1"`, `port: int = 8000`, `studio_dev_port: int = 5173`, `data_dir: Path`, `database_url: str | None = None`, `session_cookie_name: str = "nova_session"`, `session_ttl_hours: int = 168`, `auth_rate_limit_attempts: int = 5`, `auth_rate_limit_window_seconds: int = 60`, `max_blob_bytes: int = 52_428_800` ; propriétés `resolved_database_url: str`, `allowed_hosts: frozenset[str]`, `allowed_origins: frozenset[str]`
  - `Clock` (protocole, `now() -> datetime` avec fuseau UTC), `SystemClock`, `new_id() -> str`
  - `NovaError(code: str, status: int, detail: str, *, extra: dict[str, Any] | None = None, headers: dict[str, str] | None = None)`, dont les arguments restent lisibles comme attributs du même nom
  - `create_app(settings: Settings | None = None, *, clock: Clock | None = None) -> FastAPI` ; pose `app.state.settings` et `app.state.clock`
  - `find_violations(package_dir: Path, package_name: str = "nova_core") -> list[Violation]`, `Violation(rule: str, importer: str, imported: str)`

- [ ] **Step 1: Vérifier l'espace disque**

Run (PowerShell) : `[math]::Round((Get-PSDrive C).Free / 1GB, 1)`
Expected : une valeur supérieure ou égale à `2`. En dessous, arrêter et le signaler : point bloquant B1.

- [ ] **Step 2: Créer la branche et les fichiers de dépôt**

`git switch -c phase-1a-socle-core`. `.gitattributes` contient `* text=auto eol=lf`. `.gitignore` couvre `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.env`, `.env.*`, `node_modules/`, `dist/`, `.playwright-mcp/`. `pyproject.toml` racine déclare l'espace de travail uv avec le membre `services/core`. `services/core/pyproject.toml` déclare le paquet `nova-core` en disposition `src/`, les dépendances des Global Constraints, et : pytest `asyncio_mode = "auto"`, `testpaths = ["tests"]`, `pythonpath = ["."]` ; ruff `line-length = 100`, `target-version = "py313"` ; mypy `strict = true` sur `src`.

Run : `uv sync --all-packages`
Expected : environnement créé, `uv.lock` écrit, aucune erreur.

- [ ] **Step 3: Écrire les utilitaires de test**

Chaque dossier de `tests/` contient un `__init__.py`, pour que `tests.support` soit importable.

```python
# services/core/tests/support.py
from datetime import UTC, datetime, timedelta

BASE_URL = "http://127.0.0.1:8000"
CREDS = {"username": "farel", "password": "correct horse battery"}


class FakeClock:
    def __init__(self, start: datetime = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta
```

```python
# services/core/tests/conftest.py
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from nova_core.app import create_app
from nova_core.kernel.config import Settings
from tests.support import BASE_URL, FakeClock


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, env="test", data_dir=tmp_path / "data")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
async def app(settings: Settings, clock: FakeClock) -> AsyncIterator[FastAPI]:
    application = create_app(settings, clock=clock)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as c:
        yield c
```

- [ ] **Step 4: Écrire les tests qui échouent**

```python
# services/core/tests/kernel/test_config.py
import pytest
from pydantic import ValidationError

from nova_core.kernel.config import Settings


def test_local_env_refuses_non_loopback_host(tmp_path):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="local", host="0.0.0.0", data_dir=tmp_path)


def test_hosted_env_accepts_any_host(tmp_path):
    assert Settings(_env_file=None, env="hosted", host="0.0.0.0", data_dir=tmp_path).host == "0.0.0.0"


def test_allowed_hosts_and_origins_cover_core_and_studio_dev_ports(tmp_path):
    s = Settings(_env_file=None, env="test", data_dir=tmp_path)
    assert s.allowed_hosts == {"127.0.0.1:8000", "localhost:8000", "127.0.0.1:5173", "localhost:5173"}
    assert s.allowed_origins == {
        "http://127.0.0.1:8000", "http://localhost:8000",
        "http://127.0.0.1:5173", "http://localhost:5173",
    }


def test_database_defaults_to_a_file_in_the_data_dir(tmp_path):
    s = Settings(_env_file=None, env="test", data_dir=tmp_path)
    assert s.resolved_database_url.startswith("sqlite+aiosqlite:///")
    assert s.resolved_database_url.endswith("nova.db")
```

```python
# services/core/tests/kernel/test_health.py
import nova_core


async def test_health_is_public_and_reports_version(client):
    r = await client.get("/api/v1/system/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["version"] == nova_core.__version__
```

```python
# services/core/tests/kernel/test_errors.py
import logging

import httpx

from nova_core.kernel.errors import NovaError
from tests.support import BASE_URL


async def test_unknown_route_is_problem_json_with_request_id(client):
    r = await client.get("/api/v1/nope")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert (body["code"], body["status"]) == ("not_found", 404)
    assert body["request_id"] == r.headers["x-request-id"]


async def test_nova_error_carries_code_extra_and_headers(app, client):
    @app.get("/api/v1/_refused")
    async def refused() -> None:
        raise NovaError("protected_resource", 409, "nope", extra={"hint": "x"}, headers={"Retry-After": "7"})

    r = await client.get("/api/v1/_refused")
    assert r.status_code == 409
    assert (r.json()["code"], r.json()["hint"]) == ("protected_resource", "x")
    assert r.headers["retry-after"] == "7"


async def test_unhandled_error_hides_internal_details(app):
    @app.get("/api/v1/_boom")
    async def boom() -> None:
        raise RuntimeError("secret detail")

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as c:
        r = await c.get("/api/v1/_boom")
    assert r.status_code == 500
    assert r.json()["code"] == "internal_error"
    assert "secret detail" not in r.text


async def test_wellformed_request_id_is_echoed_and_others_replaced(client):
    assert (await client.get("/api/v1/system/health", headers={"X-Request-ID": "abc-123"})).headers["x-request-id"] == "abc-123"
    replaced = (await client.get("/api/v1/system/health", headers={"X-Request-ID": "x" * 100})).headers["x-request-id"]
    assert replaced != "x" * 100 and len(replaced) <= 64


async def test_each_request_is_logged_with_its_id(client, caplog):
    caplog.set_level(logging.INFO, logger="nova_core.request")
    r = await client.get("/api/v1/system/health")
    record = next(rec for rec in caplog.records if rec.name == "nova_core.request")
    assert record.request_id == r.headers["x-request-id"]
    assert (record.method, record.path, record.status) == ("GET", "/api/v1/system/health", 200)
```

```python
# services/core/tests/architecture/test_import_rules.py
from pathlib import Path

import nova_core
from tests.architecture.import_rules import find_violations


def test_checker_detects_each_rule(tmp_path):
    pkg = tmp_path / "nova_core"
    sources = {
        "kernel/db.py": "from nova_core.projects.models import Project\n",
        "projects/models.py": "",
        "projects/service.py": "import anthropic\n",
        "audit/service.py": (
            "from nova_core.projects.repository import ProjectRepository\n"
            "from nova_core.projects.service import ProjectService\n"
        ),
        "app.py": "from nova_core.projects.api import router\n",
    }
    for rel, src in sources.items():
        path = pkg / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.parent / "__init__.py").touch()
        path.write_text(src, encoding="utf-8")
    assert sorted(v.rule for v in find_violations(pkg)) == [
        "cross-module-internal", "kernel-imports-business", "provider-sdk-outside-providers",
    ]


def test_real_package_respects_the_rules():
    assert find_violations(Path(nova_core.__file__).parent) == []
```

- [ ] **Step 5: Lancer les tests pour les voir échouer**

Run : `uv run pytest -q`
Expected : échec à l'import de `nova_core.app`.

- [ ] **Step 6: Implémenter le noyau**

- `Settings` : un validateur refuse `env == "local"` avec un `host` qui n'est pas une adresse de bouclage. `data_dir` vaut par défaut `%LOCALAPPDATA%\NOVA` sous Windows, `~/.local/share/nova` ailleurs. `resolved_database_url` construit l'URL à partir de `data_dir / "nova.db"` quand `database_url` est vide. `allowed_hosts` et `allowed_origins` sont dérivés de `port` et `studio_dev_port` pour `127.0.0.1` et `localhost`.
- Rendu des erreurs, corps commun : `{"type": "about:blank", "title": <libellé HTTP>, "status", "code", "detail", "request_id"}` plus les clés de `extra`. Correspondances : `NovaError` → son code ; 404 de routage → `not_found` ; erreur de validation → `validation_error` avec `errors: [{"loc", "msg", "type"}]`, **sans** les champs `input` et `ctx` ; toute autre exception → `internal_error`, détail générique, trace écrite au journal.
- Identifiant de requête : repris de `X-Request-ID` s'il correspond à `^[A-Za-z0-9-]{1,64}$`, sinon généré ; renvoyé dans l'en-tête et dans les corps d'erreur.
- Journal : une ligne JSON par requête sur le logger `nova_core.request`, qui propage vers le logger racine, avec les attributs `request_id`, `method`, `path` (sans paramètres de requête), `status`, `duration_ms`.
- `GET /api/v1/system/health` → `{"status": "ok", "version": __version__}`.
- `python -m nova_core` lance uvicorn sur `settings.host` et `settings.port`.
- `find_violations` analyse les imports par `ast`. Règles : `cross-module-internal` — un fichier de `nova_core.<a>` importe `nova_core.<b>.<x>` avec `b` différent de `a` et de `kernel`, et `x` hors de `service`, `schemas`, `deps` ; `kernel-imports-business` — un fichier de `nova_core.kernel` importe un autre sous-paquet ; `provider-sdk-outside-providers` — un fichier hors de `nova_core.providers` importe `anthropic`, `ollama`, `openai` ou `tavily`. Fichiers exemptés : `app.py`, `__main__.py`, `all_models.py`.
- `README.md` : objet du dépôt, lien vers `docs/phase-0/README.md`, commandes d'installation et de test.

- [ ] **Step 7: Lancer les tests et les contrôles de qualité**

Run : `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
Expected : tous les tests passent ; aucun signalement.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(core): scaffold workspace, settings, error rendering and health endpoint"
```

---

### Task 2: Base de données et migrations

**Files:**
- Create: `services/core/alembic.ini`, `services/core/migrations/env.py`, `services/core/migrations/script.py.mako`, `services/core/migrations/versions/.gitkeep`
- Create: `services/core/src/nova_core/kernel/db.py`, `migrate.py`
- Modify: `services/core/src/nova_core/app.py`, `kernel/api.py`, `tests/conftest.py`
- Test: `services/core/tests/kernel/test_db.py`, `test_migrations.py`

**Interfaces:**
- Consumes: `Settings.resolved_database_url`, `create_app`
- Produces:
  - `Base` (`DeclarativeBase`), `UTCDateTime` (`TypeDecorator`)
  - `app.state.engine: AsyncEngine`, `app.state.session_factory: async_sessionmaker[AsyncSession]`
  - `async def get_session(request: Request) -> AsyncIterator[AsyncSession]`
  - `async def ping_database(engine: AsyncEngine) -> None` — lève si la base ne répond pas
  - `migrate.sync_url(database_url: str) -> str`, `migrate.upgrade(database_url: str, revision: str = "head") -> None`, `migrate.downgrade(database_url: str, revision: str) -> None`
  - fixture `session`

- [ ] **Step 1: Ajouter la fixture `session`**

```python
# à ajouter dans services/core/tests/conftest.py
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    async with app.state.session_factory() as s:
        yield s
```

- [ ] **Step 2: Écrire les tests qui échouent**

```python
# services/core/tests/kernel/test_db.py
from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import text

from nova_core.app import create_app
from nova_core.kernel.config import Settings
from nova_core.kernel.db import UTCDateTime
from tests.support import BASE_URL


def test_utc_datetime_rejects_naive_values():
    with pytest.raises(ValueError):
        UTCDateTime().process_bind_param(datetime(2026, 10, 9, 12, 0), None)


def test_utc_datetime_converts_other_zones_to_utc():
    paris = datetime(2026, 10, 9, 14, 0, tzinfo=timezone(timedelta(hours=2)))
    stored = UTCDateTime().process_bind_param(paris, None)
    assert (stored.hour, stored.utcoffset()) == (12, timedelta(0))


def test_utc_datetime_returns_aware_values_from_naive_storage():
    loaded = UTCDateTime().process_result_value(datetime(2026, 10, 9, 12, 0), None)
    assert loaded == datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


async def test_sqlite_enforces_foreign_keys(session):
    assert (await session.execute(text("PRAGMA foreign_keys"))).scalar_one() == 1


async def test_health_reports_the_database(client):
    assert (await client.get("/api/v1/system/health")).json()["database"] == "ok"


async def test_health_is_503_when_the_database_is_unreachable(client, monkeypatch):
    async def failing(engine) -> None:
        raise OSError("disk gone")

    monkeypatch.setattr("nova_core.kernel.db.ping_database", failing)
    r = await client.get("/api/v1/system/health")
    assert r.status_code == 503
    assert (r.json()["status"], r.json()["database"]) == ("degraded", "error")


async def test_core_starts_in_a_data_dir_with_spaces_and_accents(tmp_path):
    settings = Settings(_env_file=None, env="test", data_dir=tmp_path / "Mes données NOVA")
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE_URL) as c:
            assert (await c.get("/api/v1/system/health")).json()["database"] == "ok"
    assert (settings.data_dir / "nova.db").is_file()
```

```python
# services/core/tests/kernel/test_migrations.py
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

import nova_core.all_models  # noqa: F401
from nova_core.kernel.config import Settings
from nova_core.kernel.db import Base
from nova_core.kernel.migrate import downgrade, sync_url, upgrade


def _url(tmp_path) -> str:
    return Settings(_env_file=None, env="test", data_dir=tmp_path).resolved_database_url


def test_upgrade_then_downgrade_leaves_an_empty_schema(tmp_path):
    url = _url(tmp_path)
    upgrade(url)
    downgrade(url, "base")
    tables = sa.inspect(sa.create_engine(sync_url(url))).get_table_names()
    assert set(tables) <= {"alembic_version"}


def test_upgrade_is_idempotent_on_an_existing_database(tmp_path):
    url = _url(tmp_path)
    upgrade(url)
    upgrade(url)


def test_models_match_migrations(tmp_path):
    url = _url(tmp_path)
    upgrade(url)
    with sa.create_engine(sync_url(url)).connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
```

- [ ] **Step 3: Lancer les tests pour les voir échouer**

Run : `uv run pytest tests/kernel/test_db.py tests/kernel/test_migrations.py -q`
Expected : échec à l'import de `nova_core.kernel.db`.

- [ ] **Step 4: Implémenter**

- `UTCDateTime` : à l'écriture, refuse une valeur sans fuseau (`ValueError`) et convertit en UTC ; à la lecture, attache UTC à une valeur sans fuseau.
- `sync_url` remplace `sqlite+aiosqlite` par `sqlite` et laisse les autres URL inchangées.
- `upgrade` et `downgrade` créent le répertoire parent du fichier SQLite s'il manque, puis appellent Alembic avec `sync_url(database_url)` et l'emplacement de `migrations/` résolu depuis le paquet, indépendamment du répertoire courant.
- `migrations/env.py` importe `nova_core.all_models`, cible `Base.metadata`, active `render_as_batch=True` pour SQLite.
- Cycle de vie de l'application : `await asyncio.to_thread(upgrade, url)`, création du moteur asynchrone et de `async_sessionmaker(engine, expire_on_commit=False)`, puis à chaque connexion SQLite `PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL` et `PRAGMA busy_timeout=5000` ; libération du moteur à l'arrêt.
- `get_session` : ouvre une session depuis `request.app.state.session_factory`, la fournit, annule à la sortie. Ne valide jamais.
- `ping_database` exécute `SELECT 1`. La route de santé l'appelle par son module (`db.ping_database(...)`), pour qu'un test puisse la remplacer. Succès → `200`, `{"status": "ok", "version", "database": "ok"}`. Toute exception → `503`, `{"status": "degraded", "version", "database": "error"}`.

- [ ] **Step 5: Lancer toute la suite**

Run : `uv run pytest -q && uv run ruff check . && uv run mypy src`
Expected : tous les tests passent ; aucun signalement.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(core): add database layer, UTC timestamps and Alembic migrations"
```

---

### Task 3: Stockage de fichiers adressé par contenu

**Files:**
- Create: `services/core/src/nova_core/storage/__init__.py`, `models.py`, `repository.py`, `service.py`
- Create: `services/core/migrations/versions/0001_storage.py`
- Modify: `services/core/src/nova_core/all_models.py`
- Test: `services/core/tests/storage/test_blob_service.py`

**Interfaces:**
- Consumes: `Base`, `UTCDateTime`, `Clock`, `NovaError`, `Settings.max_blob_bytes`, fixtures `session`, `settings`, `clock`
- Produces:
  - table `blobs` : `sha256` (clé primaire, texte), `size`, `media_type`, `ref_count`, `created_at`
  - `BlobRef(sha256: str, size: int, media_type: str)` (dataclass figée)
  - `BlobNotFoundError(NovaError)` — code `not_found`, 404 ; `BlobTooLargeError(NovaError)` — code `validation_error`, 422
  - `BlobService(session: AsyncSession, root: Path, clock: Clock, max_bytes: int)` avec l'attribut public `root` et les méthodes :
    - `async put(data: bytes, media_type: str) -> BlobRef`
    - `async open(sha256: str) -> bytes`
    - `async release(sha256: str) -> None`
    - `async collect_garbage() -> int`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# services/core/tests/storage/test_blob_service.py
import hashlib

import pytest

from nova_core.storage.models import Blob
from nova_core.storage.service import BlobNotFoundError, BlobService, BlobTooLargeError


@pytest.fixture
def blobs(session, settings, clock) -> BlobService:
    return BlobService(session, settings.data_dir / "blobs", clock, settings.max_blob_bytes)


def stored_files(service: BlobService) -> list:
    return [p for p in service.root.rglob("*") if p.is_file()]


async def test_same_content_is_stored_once_and_counted_twice(blobs, session):
    a = await blobs.put(b"hello", "text/plain")
    b = await blobs.put(b"hello", "text/plain")
    await session.commit()
    assert a.sha256 == b.sha256 == hashlib.sha256(b"hello").hexdigest()
    assert (a.size, a.media_type) == (5, "text/plain")
    assert len(stored_files(blobs)) == 1
    assert (await session.get(Blob, a.sha256)).ref_count == 2


async def test_open_returns_the_stored_bytes(blobs, session):
    ref = await blobs.put(b"hello", "text/plain")
    await session.commit()
    assert await blobs.open(ref.sha256) == b"hello"


async def test_file_disappears_only_when_the_last_reference_is_released(blobs, session):
    ref = await blobs.put(b"hello", "text/plain")
    await blobs.put(b"hello", "text/plain")
    await blobs.release(ref.sha256)
    await session.commit()
    assert await blobs.collect_garbage() == 0
    assert len(stored_files(blobs)) == 1

    await blobs.release(ref.sha256)
    await session.commit()
    assert await blobs.collect_garbage() == 1
    assert stored_files(blobs) == []
    assert await session.get(Blob, ref.sha256) is None


async def test_rolled_back_put_leaves_no_row_and_its_file_is_collected(blobs, session):
    ref = await blobs.put(b"orphan", "text/plain")
    await session.rollback()
    assert await session.get(Blob, ref.sha256) is None
    assert await blobs.collect_garbage() == 1


async def test_unknown_blob_is_reported(blobs):
    missing = "0" * 64
    with pytest.raises(BlobNotFoundError):
        await blobs.open(missing)
    with pytest.raises(BlobNotFoundError):
        await blobs.release(missing)


@pytest.mark.parametrize("key", ["../../etc/passwd", "ABC", "g" * 64, "A" * 64])
async def test_malformed_keys_are_rejected_before_touching_the_disk(blobs, key):
    with pytest.raises(ValueError):
        await blobs.open(key)


async def test_oversized_content_is_refused_and_nothing_is_written(session, settings, clock):
    small = BlobService(session, settings.data_dir / "blobs", clock, max_bytes=4)
    with pytest.raises(BlobTooLargeError):
        await small.put(b"12345", "text/plain")
    assert stored_files(small) == []
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run : `uv run pytest tests/storage -q`
Expected : échec à l'import de `nova_core.storage`.

- [ ] **Step 3: Implémenter**

- Emplacement d'un fichier : `root / sha[0:2] / sha[2:4] / sha`. Une clé n'est acceptée que si elle correspond à `^[0-9a-f]{64}$`.
- `put` écrit dans un fichier temporaire du même répertoire puis le renomme ; les accès disque passent par `asyncio.to_thread`. Si la ligne existe, incrémente `ref_count` ; sinon l'insère avec `ref_count = 1`. Dans les deux cas elle synchronise (`flush`), pour qu'un second `put` de la même transaction retrouve la ligne.
- `release` décrémente ; à zéro, supprime la ligne. Elle ne touche pas au disque.
- `collect_garbage` supprime les fichiers sans ligne correspondante et renvoie leur nombre. Elle est appelée au démarrage de l'application.
- Migration `0001_storage` : crée `blobs` ; `down_revision = None`.

- [ ] **Step 4: Lancer toute la suite**

Run : `uv run pytest -q && uv run ruff check . && uv run mypy src`
Expected : tous les tests passent, dont `test_models_match_migrations`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(core): add content-addressed blob storage"
```

---

### Task 4: Journal d'audit et pagination

**Files:**
- Create: `services/core/src/nova_core/kernel/pagination.py`
- Create: `services/core/src/nova_core/audit/__init__.py`, `models.py`, `repository.py`, `service.py`, `schemas.py`
- Create: `services/core/migrations/versions/0002_audit.py`
- Modify: `services/core/src/nova_core/all_models.py`
- Test: `services/core/tests/kernel/test_pagination.py`, `services/core/tests/audit/test_audit_service.py`

**Interfaces:**
- Consumes: `Base`, `UTCDateTime`, `Clock`, `NovaError`, `new_id`
- Produces:
  - `Page[T]` (dataclass figée : `items: list[T]`, `next_cursor: str | None`), `encode_cursor(values: Sequence[str | int]) -> str`, `decode_cursor(cursor: str, arity: int) -> list[str | int]`, `InvalidCursorError(NovaError)` — code `validation_error`, 422
  - table `audit_events` : `seq` (clé primaire entière auto-incrémentée), `id` (UUID unique), `ts`, `actor_type`, `actor_id`, `action`, `permission_class`, `decision`, `resource` (JSON), `task_id`, `step_id`, `approval_request_id`, `outcome`
  - `ActorType = Literal["user", "nova", "agent", "system"]`, `AuditDecision = Literal["allowed", "confirmed", "denied", "refused"]`, `AuditOutcome = Literal["succeeded", "failed", "rejected", "cancelled"]`, `PermissionClass = Literal["A", "B", "C", "D"]`
  - `AuditService(session: AsyncSession, clock: Clock)` :
    - `async record(*, actor_type: ActorType, actor_id: str | None, action: str, outcome: AuditOutcome, permission_class: PermissionClass | None = None, decision: AuditDecision | None = None, resource: Mapping[str, str | int | bool | None] | None = None, task_id: str | None = None, step_id: str | None = None, approval_request_id: str | None = None) -> AuditEvent` — ajoute et synchronise (`flush`), ne valide pas
    - `async list(*, limit: int = 50, cursor: str | None = None, action: str | None = None, actor_type: ActorType | None = None) -> Page[AuditEvent]` — du plus récent au plus ancien
  - `AuditImmutableError(RuntimeError)`
  - `AuditEventOut`, `AuditEventPage` (schémas de réponse)

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# services/core/tests/kernel/test_pagination.py
import pytest

from nova_core.kernel.pagination import InvalidCursorError, decode_cursor, encode_cursor


def test_cursor_roundtrip():
    assert decode_cursor(encode_cursor(["2026-10-09T12:00:00+00:00", 42]), arity=2) == ["2026-10-09T12:00:00+00:00", 42]


@pytest.mark.parametrize("cursor", ["", "not-a-cursor", "e30=", "W10="])
def test_tampered_cursor_is_a_validation_error(cursor):
    with pytest.raises(InvalidCursorError) as exc:
        decode_cursor(cursor, arity=2)
    assert (exc.value.code, exc.value.status) == ("validation_error", 422)
```

```python
# services/core/tests/audit/test_audit_service.py
import pytest

from nova_core.audit.service import AuditImmutableError, AuditService
from nova_core.kernel.pagination import InvalidCursorError


@pytest.fixture
def audit(session, clock) -> AuditService:
    return AuditService(session, clock)


async def test_events_get_increasing_sequence_numbers(audit, session, clock):
    first = await audit.record(actor_type="system", actor_id=None, action="test.one", outcome="succeeded")
    second = await audit.record(actor_type="user", actor_id="u1", action="test.two", outcome="failed")
    await session.commit()
    assert second.seq == first.seq + 1
    assert first.ts == clock.now()


async def test_an_event_cannot_be_modified(audit, session):
    event = await audit.record(actor_type="system", actor_id=None, action="test.one", outcome="succeeded")
    await session.commit()
    event.action = "tampered"
    with pytest.raises(AuditImmutableError):
        await session.commit()
    await session.rollback()


async def test_an_event_cannot_be_deleted(audit, session):
    event = await audit.record(actor_type="system", actor_id=None, action="test.one", outcome="succeeded")
    await session.commit()
    await session.delete(event)
    with pytest.raises(AuditImmutableError):
        await session.commit()
    await session.rollback()


@pytest.mark.parametrize("key", ["password", "token", "secret", "api_key", "content", "text"])
async def test_sensitive_resource_keys_are_refused(audit, key):
    with pytest.raises(ValueError):
        await audit.record(
            actor_type="system", actor_id=None, action="test.one", outcome="succeeded", resource={key: "x"}
        )


async def test_listing_pages_newest_first_without_gaps_or_repeats(audit, session):
    for i in range(5):
        await audit.record(actor_type="system", actor_id=None, action=f"test.{i}", outcome="succeeded")
    await session.commit()

    seen, cursor = [], None
    while True:
        page = await audit.list(limit=2, cursor=cursor)
        seen += [e.action for e in page.items]
        cursor = page.next_cursor
        if cursor is None:
            break
    assert seen == ["test.4", "test.3", "test.2", "test.1", "test.0"]


async def test_listing_filters_by_action_and_actor(audit, session):
    await audit.record(actor_type="system", actor_id=None, action="a.one", outcome="succeeded")
    await audit.record(actor_type="user", actor_id="u1", action="a.two", outcome="succeeded")
    await session.commit()
    assert [e.action for e in (await audit.list(action="a.two")).items] == ["a.two"]
    assert [e.action for e in (await audit.list(actor_type="system")).items] == ["a.one"]


async def test_tampered_cursor_is_refused(audit):
    with pytest.raises(InvalidCursorError):
        await audit.list(cursor="not-a-cursor")
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run : `uv run pytest tests/kernel/test_pagination.py tests/audit -q`
Expected : échec à l'import.

- [ ] **Step 3: Implémenter**

- Curseur : JSON d'une liste, encodé en base64 adapté aux URL. `decode_cursor` lève `InvalidCursorError` si le décodage échoue, si la valeur n'est pas une liste ou si sa longueur diffère de `arity`.
- Immutabilité : des écouteurs SQLAlchemy `before_update` et `before_delete` sur `AuditEvent` lèvent `AuditImmutableError`.
- `record` refuse (`ValueError`) toute clé de `resource` parmi `password`, `token`, `secret`, `api_key`, `content`, `text`.
- `list` : tri par `seq` décroissant ; curseur sur `seq`.
- Migration `0002_audit` : crée `audit_events` ; `down_revision = "0001"`.

- [ ] **Step 4: Lancer toute la suite**

Run : `uv run pytest -q && uv run ruff check . && uv run mypy src`
Expected : tous les tests passent.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(core): add append-only audit log and cursor pagination"
```

---

### Task 5: Compte local et sessions

**Files:**
- Create: `services/core/src/nova_core/identity/__init__.py`, `models.py`, `repository.py`, `service.py`, `schemas.py`, `api.py`, `deps.py`
- Create: `services/core/migrations/versions/0003_identity.py`
- Modify: `services/core/src/nova_core/app.py`, `all_models.py`, `services/core/tests/conftest.py`
- Test: `services/core/tests/identity/test_auth.py`

**Interfaces:**
- Consumes: `AuditService`, `Clock`, `Settings`, `NovaError`, `get_session`, `new_id`
- Produces:
  - tables `users` (`id`, `username` unique, `password_hash`, `singleton` entier unique valant toujours 1, `created_at`) et `sessions` (`id`, `user_id` avec suppression en cascade, `token_hash` unique, `csrf_token`, `created_at`, `expires_at`) ; classes `User` et `AuthSession`
  - `SessionGrant(token: str, csrf_token: str, expires_at: datetime)`, `SessionContext(session_id: str, user_id: str, username: str, csrf_token: str, expires_at: datetime)` (dataclasses figées)
  - `AlreadySetUpError` — `already_set_up`, 409 ; `InvalidCredentialsError` — `invalid_credentials`, 401
  - `IdentityService(session: AsyncSession, audit: AuditService, clock: Clock, settings: Settings)` :
    - `async is_setup() -> bool`
    - `async setup(username: str, password: str) -> User`
    - `async login(username: str, password: str) -> tuple[User, SessionGrant]`
    - `async authenticate(token: str) -> SessionContext | None`
    - `async logout(session_id: str) -> None`
  - `async def require_session(...) -> SessionContext` dans `identity/deps.py` — lève `not_authenticated`, 401
  - routes `POST /api/v1/auth/setup`, `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/session`
  - fixture `auth_client`

- [ ] **Step 1: Ajouter la fixture `auth_client`**

```python
# à ajouter dans services/core/tests/conftest.py ; importer aussi CREDS depuis tests.support


@pytest.fixture
async def auth_client(client: httpx.AsyncClient) -> httpx.AsyncClient:
    await client.post("/api/v1/auth/setup", json=CREDS)
    login = await client.post("/api/v1/auth/login", json=CREDS)
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    return client
```

- [ ] **Step 2: Écrire les tests qui échouent**

```python
# services/core/tests/identity/test_auth.py
import asyncio
import hashlib
from datetime import timedelta

import httpx
from sqlalchemy import select

from nova_core.app import create_app
from nova_core.audit.models import AuditEvent
from nova_core.identity.models import AuthSession, User
from tests.support import BASE_URL, CREDS

SETUP, LOGIN, LOGOUT, SESSION = (f"/api/v1/auth/{p}" for p in ("setup", "login", "logout", "session"))


async def test_session_says_setup_is_required_on_a_fresh_install(client):
    r = await client.get(SESSION)
    assert r.status_code == 401
    assert (r.json()["code"], r.json()["setup_required"]) == ("not_authenticated", True)


async def test_account_is_created_once(client):
    first = await client.post(SETUP, json=CREDS)
    assert first.status_code == 201
    assert first.json()["user"]["username"] == "farel"
    second = await client.post(SETUP, json={"username": "other", "password": "another long password"})
    assert (second.status_code, second.json()["code"]) == (409, "already_set_up")


async def test_double_submitted_setup_creates_one_account(client, session):
    a, b = await asyncio.gather(client.post(SETUP, json=CREDS), client.post(SETUP, json=CREDS))
    assert sorted([a.status_code, b.status_code]) == [201, 409]
    assert len((await session.execute(select(User))).scalars().all()) == 1


async def test_login_sets_a_strict_http_only_cookie(client):
    await client.post(SETUP, json=CREDS)
    r = await client.post(LOGIN, json=CREDS)
    assert r.status_code == 200
    name_value, *attributes = [part.strip() for part in r.headers["set-cookie"].split(";")]
    attributes = {a.lower() for a in attributes}
    assert name_value.startswith("nova_session=")
    assert {"httponly", "samesite=strict", "path=/"} <= attributes
    assert "secure" not in attributes
    assert len(r.json()["csrf_token"]) >= 32
    assert "password" not in r.text


async def test_session_endpoint_returns_the_user_and_the_same_csrf_token(client):
    await client.post(SETUP, json=CREDS)
    login = await client.post(LOGIN, json=CREDS)
    r = await client.get(SESSION)
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "farel"
    assert r.json()["csrf_token"] == login.json()["csrf_token"]


async def test_wrong_password_and_unknown_user_get_the_same_answer_and_are_audited(client, session):
    await client.post(SETUP, json=CREDS)
    wrong = await client.post(LOGIN, json={**CREDS, "password": "definitely not it"})
    unknown = await client.post(LOGIN, json={"username": "nobody", "password": "definitely not it"})
    assert (wrong.status_code, wrong.json()["code"]) == (401, "invalid_credentials")
    assert wrong.json()["detail"] == unknown.json()["detail"]
    failures = (await session.execute(select(AuditEvent).where(AuditEvent.action == "auth.login_failed"))).scalars().all()
    assert len(failures) == 2


async def test_logout_ends_the_session(auth_client):
    assert (await auth_client.post(LOGOUT)).status_code == 204
    r = await auth_client.get(SESSION)
    assert (r.status_code, r.json()["setup_required"]) == (401, False)


async def test_password_is_hashed_with_argon2id(auth_client, session):
    user = (await session.execute(select(User))).scalar_one()
    assert user.password_hash.startswith("$argon2id$")
    assert CREDS["password"] not in user.password_hash


async def test_only_a_digest_of_the_session_token_is_stored(auth_client, session):
    token = auth_client.cookies["nova_session"]
    row = (await session.execute(select(AuthSession))).scalar_one()
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()


async def test_username_is_trimmed_and_case_insensitive(client):
    await client.post(SETUP, json={"username": "  Farel ", "password": CREDS["password"]})
    assert (await client.post(LOGIN, json=CREDS)).status_code == 200


async def test_non_ascii_password_works(client):
    creds = {"username": "farel", "password": "mot de passe très sûr 🔐"}
    await client.post(SETUP, json=creds)
    assert (await client.post(LOGIN, json=creds)).status_code == 200


async def test_rejected_input_is_never_echoed_back(client):
    for body in ({"username": "farel", "password": "hunter2"}, {"username": "farel", "password": "x" * 129}):
        r = await client.post(SETUP, json=body)
        assert (r.status_code, r.json()["code"]) == (422, "validation_error")
        assert body["password"] not in r.text
    r = await client.post(SETUP, json={**CREDS, "role": "admin"})
    assert r.status_code == 422


async def test_expired_session_is_refused(auth_client, clock, settings):
    clock.advance(timedelta(hours=settings.session_ttl_hours, seconds=1))
    r = await auth_client.get(SESSION)
    assert (r.status_code, r.json()["code"]) == (401, "not_authenticated")


async def test_session_survives_a_core_restart(settings, clock):
    first = create_app(settings, clock=clock)
    async with first.router.lifespan_context(first):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=first), base_url=BASE_URL) as c:
            await c.post(SETUP, json=CREDS)
            await c.post(LOGIN, json=CREDS)
            token = c.cookies["nova_session"]

    second = create_app(settings, clock=clock)
    async with second.router.lifespan_context(second):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=second), base_url=BASE_URL, cookies={"nova_session": token}
        ) as c:
            assert (await c.get(SESSION)).status_code == 200


async def test_auth_events_are_audited_without_secrets(auth_client, session):
    events = (await session.execute(select(AuditEvent))).scalars().all()
    assert {"auth.setup", "auth.login"} <= {e.action for e in events}
    assert all(CREDS["password"] not in str(e.resource) for e in events)
```

- [ ] **Step 3: Lancer les tests pour les voir échouer**

Run : `uv run pytest tests/identity -q`
Expected : échec à l'import de `nova_core.identity`.

- [ ] **Step 4: Implémenter**

- Schéma `Credentials` : `username` de 3 à 64 caractères après suppression des espaces de bord, stocké avec `casefold()` ; `password` de 10 à 128 caractères.
- Hachage : `argon2.PasswordHasher()` avec ses paramètres par défaut, exécuté par `asyncio.to_thread`. Un nom inconnu déclenche tout de même une vérification factice, pour une durée comparable.
- `setup` : sans lecture préalable, insère l'utilisateur avec `singleton = 1` ; une violation d'unicité devient `AlreadySetUpError`. Audit : `auth.setup`.
- `login` : jeton `secrets.token_urlsafe(32)`, dont seul le SHA-256 hexadécimal est stocké ; jeton CSRF `secrets.token_urlsafe(32)` ; `expires_at = clock.now() + session_ttl_hours`. Audit : `auth.login`, ou `auth.login_failed` avec `actor_type="system"` et `resource={"reason": "invalid_credentials"}`, validé avant de lever.
- `authenticate` : renvoie `None` si le jeton est inconnu ou si `expires_at <= clock.now()`.
- Cookie : nom `settings.session_cookie_name`, `HttpOnly`, `SameSite=Strict`, `Path=/`, `Max-Age` égal à la durée de session, `Secure` uniquement si `settings.env == "hosted"`.
- Réponses : `setup` → `201 {"user": {"id", "username"}}` ; `login` → `200 {"user", "csrf_token", "expires_at"}` ; `logout` → `204` et suppression du cookie, audit `auth.logout` ; `session` → `200 {"user", "csrf_token", "expires_at"}`, ou `401 not_authenticated` avec `extra={"setup_required": not await is_setup()}`.
- Migration `0003_identity` : crée `users` et `sessions` ; `down_revision = "0002"`.

- [ ] **Step 5: Lancer toute la suite**

Run : `uv run pytest -q && uv run ruff check . && uv run mypy src`
Expected : tous les tests passent.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(core): add local account, sessions and auth endpoints"
```

---

### Task 6: Garde-fous HTTP et limitation de débit

**Files:**
- Create: `services/core/src/nova_core/kernel/http_guards.py`, `ratelimit.py`
- Modify: `services/core/src/nova_core/app.py`, `identity/deps.py`, `identity/api.py`
- Test: `services/core/tests/kernel/test_ratelimit.py`, `services/core/tests/identity/test_guards.py`

**Interfaces:**
- Consumes: `Settings.allowed_hosts`, `Settings.allowed_origins`, `Settings.auth_rate_limit_attempts`, `Settings.auth_rate_limit_window_seconds`, `Clock`, `NovaError`, `require_session`
- Produces:
  - `HostOriginMiddleware(app, allowed_hosts: frozenset[str], allowed_origins: frozenset[str])` (middleware ASGI)
  - `RateDecision(allowed: bool, retry_after_seconds: int)`, `TokenBucketLimiter(capacity: int, refill_per_second: float, clock: Clock)` avec `check(key: str) -> RateDecision`
  - `rate_limit(name: str) -> Callable[[Request], Awaitable[None]]` — dépendance FastAPI ; limiteurs dans `app.state.rate_limiters: dict[str, TokenBucketLimiter]`
  - `require_session` exige désormais `X-CSRF-Token` sur toute méthode autre que `GET`, `HEAD`, `OPTIONS`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# services/core/tests/kernel/test_ratelimit.py
from datetime import timedelta

from nova_core.kernel.ratelimit import TokenBucketLimiter
from tests.support import FakeClock


def test_bucket_allows_capacity_then_denies_then_refills():
    clock = FakeClock()
    limiter = TokenBucketLimiter(capacity=2, refill_per_second=1.0, clock=clock)
    assert limiter.check("k").allowed and limiter.check("k").allowed
    denied = limiter.check("k")
    assert (denied.allowed, denied.retry_after_seconds) == (False, 1)
    clock.advance(timedelta(seconds=1))
    assert limiter.check("k").allowed


def test_keys_are_independent():
    limiter = TokenBucketLimiter(capacity=1, refill_per_second=1.0, clock=FakeClock())
    assert limiter.check("a").allowed
    assert limiter.check("b").allowed
    assert not limiter.check("a").allowed
```

```python
# services/core/tests/identity/test_guards.py
from datetime import timedelta

from tests.support import CREDS

LOGIN, LOGOUT, SESSION, SETUP = "/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/auth/session", "/api/v1/auth/setup"


async def test_unexpected_host_is_refused_even_on_public_routes(client):
    r = await client.get("/api/v1/system/health", headers={"Host": "evil.example"})
    assert (r.status_code, r.json()["code"]) == (403, "host_not_allowed")


async def test_foreign_origin_is_refused_on_unsafe_methods(client):
    await client.post(SETUP, json=CREDS)
    r = await client.post(LOGIN, json=CREDS, headers={"Origin": "https://evil.example"})
    assert (r.status_code, r.json()["code"]) == (403, "csrf_failed")
    assert "set-cookie" not in r.headers


async def test_allowed_origin_and_absent_origin_pass(client):
    await client.post(SETUP, json=CREDS)
    assert (await client.post(LOGIN, json=CREDS, headers={"Origin": "http://localhost:5173"})).status_code == 200
    assert (await client.post(LOGIN, json=CREDS)).status_code == 200


async def test_unsafe_request_without_csrf_token_is_refused(auth_client):
    del auth_client.headers["X-CSRF-Token"]
    r = await auth_client.post(LOGOUT)
    assert (r.status_code, r.json()["code"]) == (403, "csrf_failed")
    assert (await auth_client.get(SESSION)).status_code == 200


async def test_unsafe_request_with_a_wrong_csrf_token_is_refused(auth_client):
    r = await auth_client.post(LOGOUT, headers={"X-CSRF-Token": "wrong"})
    assert (r.status_code, r.json()["code"]) == (403, "csrf_failed")


async def test_login_attempts_are_rate_limited_then_recover(client, clock):
    await client.post(SETUP, json=CREDS)
    bad = {**CREDS, "password": "definitely not it"}
    for _ in range(5):
        assert (await client.post(LOGIN, json=bad)).status_code == 401
    limited = await client.post(LOGIN, json=bad)
    assert (limited.status_code, limited.json()["code"]) == (429, "rate_limited")
    assert int(limited.headers["retry-after"]) >= 1

    clock.advance(timedelta(seconds=60))
    assert (await client.post(LOGIN, json=bad)).status_code == 401
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run : `uv run pytest tests/kernel/test_ratelimit.py tests/identity/test_guards.py -q`
Expected : échec à l'import de `nova_core.kernel.ratelimit`.

- [ ] **Step 3: Implémenter**

- `HostOriginMiddleware`, appliqué à toutes les routes : en-tête `Host` absent ou hors de `allowed_hosts` → `403 host_not_allowed`. Pour toute méthode autre que `GET`, `HEAD`, `OPTIONS` : en-tête `Origin` présent et hors de `allowed_origins` → `403 csrf_failed`. Un `Origin` absent est accepté — le jeton CSRF protège les routes à session. Les refus utilisent le même rendu `problem+json`.
- `TokenBucketLimiter` : seau par clé, rempli à `refill_per_second`, plafonné à `capacity` ; `retry_after_seconds` est le délai avant le prochain jeton, arrondi à l'entier supérieur, au minimum 1.
- `rate_limit(name)` : clé `f"{name}:{adresse du client}"` ; refus → `NovaError("rate_limited", 429, ..., headers={"Retry-After": ...})`. Deux limiteurs, `auth.setup` et `auth.login`, de capacité `auth_rate_limit_attempts` et de remplissage `auth_rate_limit_attempts / auth_rate_limit_window_seconds`.
- `require_session` compare `X-CSRF-Token` au jeton de la session par `hmac.compare_digest` ; absence ou différence → `403 csrf_failed`.

- [ ] **Step 4: Lancer toute la suite**

Run : `uv run pytest -q && uv run ruff check . && uv run mypy src`
Expected : tous les tests passent.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(core): enforce host, origin and CSRF checks and rate-limit auth"
```

---

### Task 7: Projets

**Files:**
- Create: `services/core/src/nova_core/projects/__init__.py`, `models.py`, `repository.py`, `service.py`, `schemas.py`, `api.py`
- Create: `services/core/migrations/versions/0004_projects.py`
- Modify: `services/core/src/nova_core/app.py`, `all_models.py`
- Test: `services/core/tests/projects/test_projects.py`

**Interfaces:**
- Consumes: `require_session`, `SessionContext`, `AuditService`, `Clock`, `Page`, `encode_cursor`, `decode_cursor`, `NovaError`, `get_session`
- Produces:
  - table `projects` : `id`, `name`, `description`, `llm_privacy`, `web_access`, `status`, `is_default`, `created_at`, `updated_at`
  - `ProjectCreate` (`name` de 1 à 120 caractères après suppression des espaces de bord, `description` d'au plus 2000 caractères et vide par défaut, `llm_privacy: Literal["local_only", "cloud_allowed"] = "local_only"`, `web_access: Literal["enabled", "disabled"] = "disabled"`), `ProjectUpdate` (mêmes champs facultatifs, plus `status: Literal["active", "archived"] | None`), `ProjectOut`, `ProjectPage`
  - `ProjectNotFoundError` — `not_found`, 404 ; `ProtectedResourceError` — `protected_resource`, 409
  - `ProjectService(session: AsyncSession, audit: AuditService, clock: Clock)` :
    - `async ensure_default() -> Project`
    - `async create(data: ProjectCreate) -> Project`
    - `async get(project_id: str) -> Project`
    - `async list(*, status: Literal["active", "archived", "all"] = "active", limit: int = 50, cursor: str | None = None) -> Page[Project]`
    - `async update(project_id: str, data: ProjectUpdate) -> Project`
    - `async delete(project_id: str, *, actor_id: str) -> None`
  - routes `GET`, `POST /api/v1/projects` ; `GET`, `PATCH`, `DELETE /api/v1/projects/{project_id}`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# services/core/tests/projects/test_projects.py
import httpx
from sqlalchemy import select

from nova_core.app import create_app
from nova_core.audit.models import AuditEvent
from tests.support import BASE_URL, CREDS

PROJECTS = "/api/v1/projects"


async def default_project(c) -> dict:
    return next(p for p in (await c.get(PROJECTS)).json()["items"] if p["is_default"])


async def test_projects_require_a_session(client):
    r = await client.get(PROJECTS)
    assert (r.status_code, r.json()["code"]) == (401, "not_authenticated")


async def test_free_space_project_exists_after_install(auth_client):
    items = (await auth_client.get(PROJECTS)).json()["items"]
    assert [(p["name"], p["is_default"]) for p in items] == [("Espace libre", True)]


async def test_restart_does_not_duplicate_the_free_space_project(settings, clock):
    for _ in range(2):
        app = create_app(settings, clock=clock)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE_URL) as c:
                await c.post("/api/v1/auth/setup", json=CREDS)
                await c.post("/api/v1/auth/login", json=CREDS)
                assert len((await c.get(PROJECTS)).json()["items"]) == 1


async def test_new_project_keeps_everything_on_the_machine_by_default(auth_client):
    r = await auth_client.post(PROJECTS, json={"name": "  NOVA  "})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "NOVA"
    assert (body["llm_privacy"], body["web_access"]) == ("local_only", "disabled")
    assert (body["status"], body["is_default"], body["description"]) == ("active", False, "")


async def test_names_at_the_limits(auth_client):
    assert (await auth_client.post(PROJECTS, json={"name": "x" * 120})).status_code == 201
    for bad in ("", "   ", "x" * 121):
        r = await auth_client.post(PROJECTS, json={"name": bad})
        assert (r.status_code, r.json()["code"]) == (422, "validation_error")
    assert (await auth_client.post(PROJECTS, json={"name": "ok", "description": "d" * 2001})).status_code == 422
    assert (await auth_client.post(PROJECTS, json={"name": "ok", "is_default": True})).status_code == 422


async def test_privacy_settings_can_be_changed_and_are_validated(auth_client):
    pid = (await auth_client.post(PROJECTS, json={"name": "NOVA"})).json()["id"]
    r = await auth_client.patch(f"{PROJECTS}/{pid}", json={"llm_privacy": "cloud_allowed", "web_access": "enabled"})
    assert (r.json()["llm_privacy"], r.json()["web_access"]) == ("cloud_allowed", "enabled")
    assert (await auth_client.patch(f"{PROJECTS}/{pid}", json={"llm_privacy": "anywhere"})).status_code == 422


async def test_archived_projects_leave_the_default_listing(auth_client):
    pid = (await auth_client.post(PROJECTS, json={"name": "NOVA"})).json()["id"]
    assert (await auth_client.patch(f"{PROJECTS}/{pid}", json={"status": "archived"})).json()["status"] == "archived"
    active = [p["id"] for p in (await auth_client.get(PROJECTS)).json()["items"]]
    archived = [p["id"] for p in (await auth_client.get(PROJECTS, params={"status": "archived"})).json()["items"]]
    everything = (await auth_client.get(PROJECTS, params={"status": "all"})).json()["items"]
    assert pid not in active and archived == [pid] and len(everything) == 2


async def test_delete_removes_the_project_and_leaves_a_content_free_trace(auth_client, session):
    pid = (await auth_client.post(PROJECTS, json={"name": "Projet secret"})).json()["id"]
    assert (await auth_client.delete(f"{PROJECTS}/{pid}")).status_code == 204
    gone = await auth_client.get(f"{PROJECTS}/{pid}")
    assert (gone.status_code, gone.json()["code"]) == (404, "not_found")
    event = (await session.execute(select(AuditEvent).where(AuditEvent.action == "project.deleted"))).scalar_one()
    assert event.resource == {"project_id": pid}
    assert event.actor_type == "user"


async def test_free_space_project_can_be_neither_deleted_nor_archived(auth_client):
    pid = (await default_project(auth_client))["id"]
    for r in (
        await auth_client.delete(f"{PROJECTS}/{pid}"),
        await auth_client.patch(f"{PROJECTS}/{pid}", json={"status": "archived"}),
    ):
        assert (r.status_code, r.json()["code"]) == (409, "protected_resource")


async def test_listing_is_paginated_without_gaps_or_repeats(auth_client):
    for name in ("a", "b", "c"):
        await auth_client.post(PROJECTS, json={"name": name})
    first = (await auth_client.get(PROJECTS, params={"limit": 2})).json()
    second = (await auth_client.get(PROJECTS, params={"limit": 2, "cursor": first["next_cursor"]})).json()
    ids = [p["id"] for p in first["items"] + second["items"]]
    assert len(first["items"]) == 2 and second["next_cursor"] is None
    assert len(ids) == len(set(ids)) == 4


async def test_bad_pagination_parameters_are_validation_errors(auth_client):
    for params in ({"cursor": "not-a-cursor"}, {"limit": 0}, {"limit": 201}, {"status": "deleted"}):
        r = await auth_client.get(PROJECTS, params=params)
        assert (r.status_code, r.json()["code"]) == (422, "validation_error")
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run : `uv run pytest tests/projects -q`
Expected : échec, routes absentes.

- [ ] **Step 3: Implémenter**

- `ensure_default` : crée le projet nommé `Espace libre` avec `is_default = True` s'il n'existe pas ; appelé au démarrage. Il n'écrit aucun événement d'audit.
- `list` : tri `created_at` décroissant puis `id` décroissant ; curseur sur ces deux valeurs ; `limit` de 1 à 200.
- `update` et `delete` lèvent `ProtectedResourceError` quand le projet par défaut serait archivé ou supprimé. `update` renseigne `updated_at`.
- `delete` enregistre l'audit `project.deleted` avec `actor_type="user"`, `actor_id`, `resource={"project_id": id}`, `outcome="succeeded"`, dans la même transaction que la suppression.
- Toutes les routes dépendent de `require_session`. `POST` → `201` ; `DELETE` → `204`.
- Migration `0004_projects` : crée `projects` ; `down_revision = "0003"`.

- [ ] **Step 4: Lancer toute la suite**

Run : `uv run pytest -q && uv run ruff check . && uv run mypy src`
Expected : tous les tests passent.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(core): add projects with private-by-default settings"
```

---

### Task 8: Objectifs, exigences et contraintes

**Files:**
- Modify: `services/core/src/nova_core/projects/models.py`, `repository.py`, `service.py`, `schemas.py`, `api.py`
- Create: `services/core/migrations/versions/0005_project_spec_items.py`
- Test: `services/core/tests/projects/test_spec_items.py`

**Interfaces:**
- Consumes: `ProjectService`, `ProjectNotFoundError`, `require_session`, `AuditService`, `Clock`
- Produces:
  - table `project_spec_items` : `id`, `project_id` (clé étrangère vers `projects.id`, suppression en cascade), `kind`, `text`, `origin`, `confirmed`, `created_at`, `updated_at`
  - `SpecItemKind = Literal["objective", "requirement", "constraint"]`, `SpecItemCreate` (`kind`, `text` de 1 à 2000 caractères après suppression des espaces de bord), `SpecItemUpdate` (`text` facultatif, `confirmed: Literal[True] | None`), `SpecItemOut`
  - `SpecItemNotFoundError` — `not_found`, 404
  - `SpecItemService(session: AsyncSession, clock: Clock)` :
    - `async add(project_id: str, data: SpecItemCreate) -> ProjectSpecItem` — origine `user`, confirmé
    - `async propose(project_id: str, *, kind: SpecItemKind, text: str) -> ProjectSpecItem` — origine `nova`, non confirmé
    - `async list(project_id: str, *, kind: SpecItemKind | None = None) -> list[ProjectSpecItem]`
    - `async update(item_id: str, data: SpecItemUpdate) -> ProjectSpecItem`
    - `async delete(item_id: str) -> None`
  - routes `GET`, `POST /api/v1/projects/{project_id}/spec-items` ; `PATCH`, `DELETE /api/v1/spec-items/{item_id}`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# services/core/tests/projects/test_spec_items.py
import pytest
from sqlalchemy import func, select

from nova_core.projects.models import ProjectSpecItem
from nova_core.projects.service import SpecItemService

PROJECTS = "/api/v1/projects"


@pytest.fixture
async def project_id(auth_client) -> str:
    return (await auth_client.post(PROJECTS, json={"name": "NOVA"})).json()["id"]


async def test_items_added_by_the_user_are_confirmed(auth_client, project_id):
    r = await auth_client.post(f"{PROJECTS}/{project_id}/spec-items", json={"kind": "objective", "text": " Livrer le MVP "})
    assert r.status_code == 201
    assert (r.json()["text"], r.json()["origin"], r.json()["confirmed"]) == ("Livrer le MVP", "user", True)


async def test_the_client_cannot_choose_the_origin_or_the_confirmation(auth_client, project_id):
    url = f"{PROJECTS}/{project_id}/spec-items"
    assert (await auth_client.post(url, json={"kind": "objective", "text": "x", "origin": "nova"})).status_code == 422
    assert (await auth_client.post(url, json={"kind": "objective", "text": "x", "confirmed": False})).status_code == 422


async def test_a_proposal_from_nova_stays_unconfirmed_until_the_user_confirms(auth_client, project_id, session, clock):
    item = await SpecItemService(session, clock).propose(project_id, kind="requirement", text="Fonctionner hors ligne")
    assert (item.origin, item.confirmed) == ("nova", False)
    listed = (await auth_client.get(f"{PROJECTS}/{project_id}/spec-items")).json()
    assert listed[0]["confirmed"] is False

    r = await auth_client.patch(f"/api/v1/spec-items/{item.id}", json={"confirmed": True})
    assert (r.status_code, r.json()["confirmed"], r.json()["origin"]) == (200, True, "nova")


async def test_a_confirmation_cannot_be_withdrawn(auth_client, project_id):
    url = f"{PROJECTS}/{project_id}/spec-items"
    item_id = (await auth_client.post(url, json={"kind": "constraint", "text": "Budget nul"})).json()["id"]
    assert (await auth_client.patch(f"/api/v1/spec-items/{item_id}", json={"confirmed": False})).status_code == 422


async def test_text_can_be_edited_and_items_deleted(auth_client, project_id):
    url = f"{PROJECTS}/{project_id}/spec-items"
    item_id = (await auth_client.post(url, json={"kind": "constraint", "text": "Budget nul"})).json()["id"]
    edited = await auth_client.patch(f"/api/v1/spec-items/{item_id}", json={"text": "Budget de 30 $ par mois"})
    assert edited.json()["text"] == "Budget de 30 $ par mois"
    assert (await auth_client.delete(f"/api/v1/spec-items/{item_id}")).status_code == 204
    assert (await auth_client.get(url)).json() == []


async def test_listing_filters_by_kind_and_validates_it(auth_client, project_id):
    url = f"{PROJECTS}/{project_id}/spec-items"
    for kind in ("objective", "requirement", "constraint"):
        await auth_client.post(url, json={"kind": kind, "text": kind})
    assert [i["kind"] for i in (await auth_client.get(url, params={"kind": "requirement"})).json()] == ["requirement"]
    assert (await auth_client.get(url, params={"kind": "wish"})).status_code == 422
    assert (await auth_client.post(url, json={"kind": "wish", "text": "x"})).status_code == 422
    assert (await auth_client.post(url, json={"kind": "objective", "text": "   "})).status_code == 422
    assert (await auth_client.post(url, json={"kind": "objective", "text": "x" * 2001})).status_code == 422


async def test_unknown_project_or_item_is_not_found(auth_client):
    missing = "00000000-0000-4000-8000-000000000000"
    for r in (
        await auth_client.get(f"{PROJECTS}/{missing}/spec-items"),
        await auth_client.post(f"{PROJECTS}/{missing}/spec-items", json={"kind": "objective", "text": "x"}),
        await auth_client.patch(f"/api/v1/spec-items/{missing}", json={"text": "x"}),
        await auth_client.delete(f"/api/v1/spec-items/{missing}"),
    ):
        assert (r.status_code, r.json()["code"]) == (404, "not_found")


async def test_deleting_a_project_removes_its_items(auth_client, project_id, session):
    await auth_client.post(f"{PROJECTS}/{project_id}/spec-items", json={"kind": "objective", "text": "x"})
    await auth_client.delete(f"{PROJECTS}/{project_id}")
    assert (await session.execute(select(func.count()).select_from(ProjectSpecItem))).scalar_one() == 0
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run : `uv run pytest tests/projects/test_spec_items.py -q`
Expected : échec à l'import de `SpecItemService`.

- [ ] **Step 3: Implémenter**

- `list` trie par `created_at` puis `id` croissants et renvoie une liste simple, sans pagination.
- `add`, `propose` et `list` lèvent `ProjectNotFoundError` si le projet n'existe pas.
- `update` : `confirmed=True` passe l'élément à confirmé ; toute modification renseigne `updated_at`.
- Migration `0005_project_spec_items` : crée `project_spec_items` ; `down_revision = "0004"`.

- [ ] **Step 4: Lancer toute la suite**

Run : `uv run pytest -q && uv run ruff check . && uv run mypy src`
Expected : tous les tests passent.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(core): add project objectives, requirements and constraints"
```

---

### Task 9: Capacités, consultation de l'audit et instantané du contrat

**Files:**
- Create: `services/core/src/nova_core/kernel/capabilities.py`, `services/core/src/nova_core/audit/api.py`, `services/core/openapi.json`
- Modify: `services/core/src/nova_core/kernel/api.py`, `app.py`, `README.md`
- Test: `services/core/tests/kernel/test_capabilities.py`, `services/core/tests/audit/test_audit_api.py`, `services/core/tests/test_openapi_snapshot.py`

**Interfaces:**
- Consumes: `require_session`, `AuditService`, `AuditEventPage`, `get_session`
- Produces:
  - `CapabilityStatus = Literal["available", "degraded", "unavailable", "not_implemented"]`, `CapabilityState(id: str, status: CapabilityStatus, reason: str | None = None, detail: str | None = None)` (modèle Pydantic), `Probe = Callable[[], Awaitable[CapabilityState]]`
  - `CAPABILITY_IDS: tuple[str, ...] = ("chat.local", "chat.cloud", "research.search", "research.fetch", "image.generate", "agent.fs", "agent.exec", "agent.git", "voice.stt", "voice.tts")`
  - `CapabilityRegistry` : `register(capability_id: str, probe: Probe) -> None`, `declare_not_implemented(capability_id: str) -> None`, `async snapshot() -> list[CapabilityState]` ; instance dans `app.state.capabilities`
  - routes `GET /api/v1/system/capabilities` et `GET /api/v1/audit`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# services/core/tests/kernel/test_capabilities.py
from nova_core.kernel.capabilities import CAPABILITY_IDS, CapabilityRegistry, CapabilityState

URL = "/api/v1/system/capabilities"


async def test_capabilities_require_a_session(client):
    assert (await client.get(URL)).status_code == 401


async def test_every_capability_is_listed_and_none_is_overstated(auth_client):
    listed = (await auth_client.get(URL)).json()["capabilities"]
    assert [c["id"] for c in listed] == list(CAPABILITY_IDS)
    assert {c["status"] for c in listed} == {"not_implemented"}


async def test_a_failing_probe_reports_unavailable_instead_of_crashing():
    registry = CapabilityRegistry()

    async def broken() -> CapabilityState:
        raise RuntimeError("boom")

    registry.register("chat.local", broken)
    state = (await registry.snapshot())[0]
    assert (state.id, state.status, state.reason) == ("chat.local", "unavailable", "probe_failed")


async def test_registering_again_replaces_the_probe_and_keeps_the_order():
    registry = CapabilityRegistry()
    registry.declare_not_implemented("chat.local")
    registry.declare_not_implemented("chat.cloud")

    async def ready() -> CapabilityState:
        return CapabilityState(id="chat.local", status="available", detail="ollama / llama3.2")

    registry.register("chat.local", ready)
    assert [(s.id, s.status) for s in await registry.snapshot()] == [
        ("chat.local", "available"), ("chat.cloud", "not_implemented"),
    ]
```

```python
# services/core/tests/audit/test_audit_api.py
from tests.support import CREDS

AUDIT = "/api/v1/audit"


async def test_audit_requires_a_session(client):
    assert (await client.get(AUDIT)).status_code == 401


async def test_audit_lists_events_newest_first_without_secrets(auth_client):
    r = await auth_client.get(AUDIT)
    assert r.status_code == 200
    assert [e["action"] for e in r.json()["items"]] == ["auth.login", "auth.setup"]
    assert CREDS["password"] not in r.text


async def test_audit_filters_and_paginates(auth_client):
    only_login = (await auth_client.get(AUDIT, params={"action": "auth.login"})).json()["items"]
    assert [e["action"] for e in only_login] == ["auth.login"]
    first = (await auth_client.get(AUDIT, params={"limit": 1})).json()
    second = (await auth_client.get(AUDIT, params={"limit": 1, "cursor": first["next_cursor"]})).json()
    assert (first["items"][0]["action"], second["items"][0]["action"]) == ("auth.login", "auth.setup")
    assert (await auth_client.get(AUDIT, params={"actor_type": "robot"})).status_code == 422


async def test_no_route_can_modify_or_delete_audit_events(app):
    methods = set().union(*(r.methods for r in app.routes if getattr(r, "path", "").startswith("/api/v1/audit")))
    assert methods <= {"GET", "HEAD"}
```

```python
# services/core/tests/test_openapi_snapshot.py
import json
import os
from pathlib import Path

SNAPSHOT = Path(__file__).parent.parent / "openapi.json"


async def test_openapi_schema_matches_the_committed_snapshot(app):
    current = json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if os.environ.get("NOVA_UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT.write_text(current, encoding="utf-8", newline="\n")
    assert SNAPSHOT.read_text(encoding="utf-8") == current
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run : `uv run pytest tests/kernel/test_capabilities.py tests/audit/test_audit_api.py tests/test_openapi_snapshot.py -q`
Expected : échec à l'import de `nova_core.kernel.capabilities`.

- [ ] **Step 3: Implémenter**

- `snapshot` renvoie les états dans l'ordre du premier enregistrement ; une sonde qui lève produit `status="unavailable"`, `reason="probe_failed"`, et l'erreur est journalisée.
- Au démarrage, `create_app` déclare `not_implemented` chacun des identifiants de `CAPABILITY_IDS`. Les plans suivants remplaceront ces déclarations par de vraies sondes.
- `GET /api/v1/system/capabilities` → `{"capabilities": [...]}`, session requise.
- `GET /api/v1/audit` : paramètres `limit` de 1 à 200 (50 par défaut), `cursor`, `action`, `actor_type` ; réponse `AuditEventPage` ; session requise. Aucune autre méthode n'est déclarée sur ce chemin.
- `README.md` : ajouter ce que le Core fait à ce stade, la commande de démarrage, et la limite suivante — toutes les capacités sont `not_implemented` tant que les plans 1B à 1D ne sont pas livrés.

- [ ] **Step 4: Générer l'instantané puis lancer toute la suite**

Run (PowerShell) : `$env:NOVA_UPDATE_SNAPSHOTS = "1"; uv run pytest tests/test_openapi_snapshot.py -q; Remove-Item Env:NOVA_UPDATE_SNAPSHOTS`
Expected : `openapi.json` écrit, test réussi.

Run : `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
Expected : tous les tests passent ; aucun signalement.

- [ ] **Step 5: Vérifier le démarrage réel**

Run : `uv run python -m nova_core`, puis dans un second terminal `curl http://127.0.0.1:8000/api/v1/system/health`
Expected : `{"status":"ok","version":"0.1.0","database":"ok"}`. Arrêter ensuite le serveur.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(core): expose capabilities and audit log, pin OpenAPI snapshot"
```

---

## Couverture du cahier des charges

| Récit | Critère | Tâche |
| --- | --- | --- |
| P1-01 | Installation depuis les fichiers de verrouillage ; une commande lance la suite | 1 |
| P1-01 | `GET /api/v1/system/health` répond | 1, 2 |
| P1-01 | Test d'architecture sur les imports | 1 |
| P1-02 | Migrations appliquées puis défaites sans erreur | 2 |
| P1-02 | Fichier stocké une fois ; supprimé quand plus rien ne le référence | 3 |
| P1-03 | Compte créé une seule fois | 5 |
| P1-03 | Requête modifiante sans jeton CSRF ou d'origine étrangère refusée | 6 |
| P1-03 | En-tête `Host` inattendu refusé | 6 |
| P1-03 | Tentatives de connexion limitées (`rate_limited`) | 6 |
| P1-04 | Créer, lire, modifier, archiver, supprimer un projet | 7 |
| P1-04 | Objectifs, exigences, contraintes ; proposition de NOVA non confirmée par défaut | 8 |
| P1-04 | Projet « espace libre » présent après installation | 7 |
| P1-12 | `GET /system/capabilities` reflète l'état réel | 9 |
| P1-12 | Aucune route ne modifie ni ne supprime un événement d'audit (INV-8) | 4, 9 |

Reporté aux plans suivants : l'espace de travail `npm` et la suite du Studio (plan 1D) ; les sondes réelles des capacités (plans 1B et 1C).
