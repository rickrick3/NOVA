from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

LlmPrivacy = Literal["local_only", "cloud_allowed"]
WebAccess = Literal["enabled", "disabled"]
ProjectStatus = Literal["active", "archived"]
ProjectStatusFilter = Literal["active", "archived", "all"]

ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ProjectDescription = Annotated[str, StringConstraints(max_length=2000)]


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ProjectName
    description: ProjectDescription = ""
    # Nothing leaves the machine unless the user says so.
    llm_privacy: LlmPrivacy = "local_only"
    web_access: WebAccess = "disabled"


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ProjectName | None = None
    description: ProjectDescription | None = None
    llm_privacy: LlmPrivacy | None = None
    web_access: WebAccess | None = None
    status: ProjectStatus | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    llm_privacy: LlmPrivacy
    web_access: WebAccess
    status: ProjectStatus
    is_default: bool
    created_at: datetime
    updated_at: datetime


class ProjectPage(BaseModel):
    items: list[ProjectOut]
    next_cursor: str | None


SpecItemKind = Literal["objective", "requirement", "constraint"]
SpecItemOrigin = Literal["user", "nova"]
SpecItemText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class SpecItemCreate(BaseModel):
    # No origin and no confirmed field: an item created through the API is the user's.
    model_config = ConfigDict(extra="forbid")

    kind: SpecItemKind
    text: SpecItemText


class SpecItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: SpecItemText | None = None
    # A confirmation can be given, never withdrawn.
    confirmed: Literal[True] | None = None


class SpecItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    kind: SpecItemKind
    text: str
    origin: SpecItemOrigin
    confirmed: bool
    created_at: datetime
    updated_at: datetime
