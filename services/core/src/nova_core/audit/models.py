from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column

from nova_core.kernel.db import Base, UTCDateTime


class AuditImmutableError(RuntimeError):
    """Raised when something tries to modify or delete an audit event (INV-8)."""


class AuditEvent(Base):
    __tablename__ = "audit_events"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), unique=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime)
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(100))
    permission_class: Mapped[str | None] = mapped_column(String(1))
    decision: Mapped[str | None] = mapped_column(String(16))
    resource: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    task_id: Mapped[str | None] = mapped_column(String(36))
    step_id: Mapped[str | None] = mapped_column(String(36))
    approval_request_id: Mapped[str | None] = mapped_column(String(36))
    outcome: Mapped[str] = mapped_column(String(16))


@event.listens_for(AuditEvent, "before_update")
def _refuse_update(*_: Any) -> None:
    raise AuditImmutableError("audit events are append-only: they cannot be modified")


@event.listens_for(AuditEvent, "before_delete")
def _refuse_delete(*_: Any) -> None:
    raise AuditImmutableError("audit events are append-only: they cannot be deleted")
