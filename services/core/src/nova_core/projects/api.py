from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from nova_core.audit.service import AuditService
from nova_core.identity.deps import CurrentSession, require_session
from nova_core.kernel.db import DbSession
from nova_core.projects.schemas import (
    ProjectCreate,
    ProjectOut,
    ProjectPage,
    ProjectStatusFilter,
    ProjectUpdate,
)
from nova_core.projects.service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(require_session)])


def get_project_service(request: Request, session: DbSession) -> ProjectService:
    clock = request.app.state.clock
    return ProjectService(session, AuditService(session, clock), clock)


ProjectsDep = Annotated[ProjectService, Depends(get_project_service)]


@router.get("")
async def list_projects(
    projects: ProjectsDep,
    status: ProjectStatusFilter = "active",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> ProjectPage:
    page = await projects.list(status=status, limit=limit, cursor=cursor)
    return ProjectPage(
        items=[ProjectOut.model_validate(project) for project in page.items],
        next_cursor=page.next_cursor,
    )


@router.post("", status_code=201)
async def create_project(body: ProjectCreate, projects: ProjectsDep) -> ProjectOut:
    return ProjectOut.model_validate(await projects.create(body))


@router.get("/{project_id}")
async def get_project(project_id: str, projects: ProjectsDep) -> ProjectOut:
    return ProjectOut.model_validate(await projects.get(project_id))


@router.patch("/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate, projects: ProjectsDep) -> ProjectOut:
    return ProjectOut.model_validate(await projects.update(project_id, body))


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, projects: ProjectsDep, context: CurrentSession) -> None:
    await projects.delete(project_id, actor_id=context.user_id)
