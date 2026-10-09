from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from nova_core.audit.service import AuditService
from nova_core.kernel.clock import Clock
from nova_core.kernel.errors import NovaError
from nova_core.kernel.ids import new_id
from nova_core.kernel.pagination import InvalidCursorError, Page, decode_cursor, encode_cursor
from nova_core.projects.models import Project
from nova_core.projects.repository import ProjectRepository
from nova_core.projects.schemas import ProjectCreate, ProjectStatusFilter, ProjectUpdate

DEFAULT_PROJECT_NAME = "Espace libre"


class ProjectNotFoundError(NovaError):
    def __init__(self) -> None:
        super().__init__("not_found", 404, "Project not found.")


class ProtectedResourceError(NovaError):
    def __init__(self) -> None:
        super().__init__(
            "protected_resource", 409, "The default project can be neither deleted nor archived."
        )


def _decode_position(cursor: str) -> tuple[datetime, str]:
    created_at, project_id = decode_cursor(cursor, arity=2)
    if not isinstance(created_at, str) or not isinstance(project_id, str):
        raise InvalidCursorError()
    try:
        return datetime.fromisoformat(created_at), project_id
    except ValueError:
        raise InvalidCursorError() from None


class ProjectService:
    def __init__(self, session: AsyncSession, audit: AuditService, clock: Clock) -> None:
        self._session = session
        self._projects = ProjectRepository(session)
        self._audit = audit
        self._clock = clock

    def _new(self, data: ProjectCreate, *, is_default: bool) -> Project:
        now = self._clock.now()
        return Project(
            id=new_id(),
            name=data.name,
            description=data.description,
            llm_privacy=data.llm_privacy,
            web_access=data.web_access,
            status="active",
            is_default=is_default,
            created_at=now,
            updated_at=now,
        )

    async def ensure_default(self) -> Project:
        """Creates the "free space" project on first start. Writes no audit event."""
        existing = await self._projects.default()
        if existing is not None:
            return existing
        project = self._new(ProjectCreate(name=DEFAULT_PROJECT_NAME), is_default=True)
        self._projects.add(project)
        await self._session.commit()
        return project

    async def create(self, data: ProjectCreate) -> Project:
        project = self._new(data, is_default=False)
        self._projects.add(project)
        await self._session.commit()
        return project

    async def get(self, project_id: str) -> Project:
        project = await self._projects.get(project_id)
        if project is None:
            raise ProjectNotFoundError()
        return project

    async def update(self, project_id: str, data: ProjectUpdate) -> Project:
        project = await self.get(project_id)
        if project.is_default and data.status == "archived":
            raise ProtectedResourceError()
        for field in ("name", "description", "llm_privacy", "web_access", "status"):
            value = getattr(data, field)
            if value is not None:
                setattr(project, field, value)
        project.updated_at = self._clock.now()
        await self._session.commit()
        return project

    async def delete(self, project_id: str, *, actor_id: str) -> None:
        project = await self.get(project_id)
        if project.is_default:
            raise ProtectedResourceError()
        await self._projects.delete(project)
        # The trace keeps who and what, never the project's name or content.
        await self._audit.record(
            actor_type="user",
            actor_id=actor_id,
            action="project.deleted",
            outcome="succeeded",
            resource={"project_id": project_id},
        )
        await self._session.commit()

    async def list(
        self,
        *,
        status: ProjectStatusFilter = "active",
        limit: int = 50,
        cursor: str | None = None,
    ) -> Page[Project]:
        before = _decode_position(cursor) if cursor is not None else None
        # One extra row tells whether another page exists.
        rows = await self._projects.newest_first(
            status=None if status == "all" else status, limit=limit + 1, before=before
        )
        items = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            last = items[-1]
            next_cursor = encode_cursor([last.created_at.isoformat(), last.id])
        return Page(items=items, next_cursor=next_cursor)
