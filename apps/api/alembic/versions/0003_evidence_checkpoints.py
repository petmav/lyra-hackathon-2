"""Add evidence consumer checkpoints.

Revision ID: 0003_evidence_checkpoints
Revises: 0002_step_run_leases
Create Date: 2026-04-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_evidence_checkpoints"
down_revision: str | None = "0002_step_run_leases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_checkpoint",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("consumer", sa.String(128), nullable=False),
        sa.Column("last_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_event_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_evidence_checkpoint_consumer", "evidence_checkpoint", ["consumer"], unique=True)
    op.create_index("ix_agent_event_ts", "agent_event", ["ts"])


def downgrade() -> None:
    op.drop_index("ix_agent_event_ts", table_name="agent_event")
    op.drop_index("ix_evidence_checkpoint_consumer", table_name="evidence_checkpoint")
    op.drop_table("evidence_checkpoint")
