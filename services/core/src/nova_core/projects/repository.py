from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from nova_core.projects.models import Project, ProjectSpecItem


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, project_id: str) -> Project | None:
        return await self._session.get(Project, project_id)

    async def default(self) -> Project | None:
        statement = select(Project).where(Project.is_default.is_(True))
        return (await self._session.execute(statement)).scalars().first()

    def add(self, project: Project) -> None:
        self._session.add(project)

    async def delete(self, project: Project) -> None:
        await self._session.delete(project)

    async def newest_first(
        self, *, status: str | None, limit: int, before: tuple[datetime, str] | None
    ) -> list[Project]:
        statement = (
            select(Project).order_by(Project.created_at.desc(), Project.id.desc()).limit(limit)
        )
        if status is not None:
            statement = statement.where(Project.status == status)
        if before is not None:
            created_at, project_id = before
            statement = statement.where(
                or_(
                    Project.created_at < created_at,
                    and_(Project.created_at == created_at, Project.id < project_id),
                )
            )
        return list((await self._session.execute(statement)).scalars())


class SpecItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, item_id: str) -> ProjectSpecItem | None:
        return await self._session.get(ProjectSpecItem, item_id)

    def add(self, item: ProjectSpecItem) -> None:
        self._session.add(item)

    async def delete(self, item: ProjectSpecItem) -> None:
        await self._session.delete(item)

    async def oldest_first(self, project_id: str, *, kind: str | None) -> list[ProjectSpecItem]:
        statement = (
            select(ProjectSpecItem)
            .where(ProjectSpecItem.project_id == project_id)
            .order_by(ProjectSpecItem.created_at, ProjectSpecItem.id)
        )
        if kind is not None:
            statement = statement.where(ProjectSpecItem.kind == kind)
        return list((await self._session.execute(statement)).scalars())
