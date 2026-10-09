from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

ActorType = Literal["user", "nova", "agent", "system"]
AuditDecision = Literal["allowed", "confirmed", "denied", "refused"]
AuditOutcome = Literal["succeeded", "failed", "rejected", "cancelled"]
PermissionClass = Literal["A", "B", "C", "D"]


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    id: str
    ts: datetime
    actor_type: ActorType
    actor_id: str | None
    action: str
    permission_class: PermissionClass | None
    decision: AuditDecision | None
    resource: dict[str, Any] | None
    task_id: str | None
    step_id: str | None
    approval_request_id: str | None
    outcome: AuditOutcome


class AuditEventPage(BaseModel):
    items: list[AuditEventOut]
    next_cursor: str | None
