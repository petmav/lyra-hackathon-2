"""Add workflow step leases.

Revision ID: 0002_step_run_leases
Revises: 0001
Create Date: 2026-04-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_step_run_leases"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("step_run", sa.Column("lease_owner", sa.String(255), nullable=True))
    op.add_column("step_run", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("step_run", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("step_run", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_step_run_lease_expires_at", "step_run", ["lease_expires_at"])
    op.create_index("ix_step_run_lease_owner", "step_run", ["lease_owner"])
    op.alter_column("step_run", "attempt_count", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_step_run_lease_owner", table_name="step_run")
    op.drop_index("ix_step_run_lease_expires_at", table_name="step_run")
    op.drop_column("step_run", "attempt_count")
    op.drop_column("step_run", "heartbeat_at")
    op.drop_column("step_run", "lease_expires_at")
    op.drop_column("step_run", "lease_owner")
