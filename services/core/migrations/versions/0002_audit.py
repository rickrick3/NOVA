"""audit: audit_events

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("seq", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id", sa.String(36), nullable=False, unique=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("permission_class", sa.String(1), nullable=True),
        sa.Column("decision", sa.String(16), nullable=True),
        sa.Column("resource", sa.JSON(), nullable=True),
        sa.Column("task_id", sa.String(36), nullable=True),
        sa.Column("step_id", sa.String(36), nullable=True),
        sa.Column("approval_request_id", sa.String(36), nullable=True),
        sa.Column("outcome", sa.String(16), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
