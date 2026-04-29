"""Add persisted hook configuration.

Revision ID: 0004_hook_config
Revises: 0003_evidence_checkpoints
Create Date: 2026-04-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_hook_config"
down_revision: str | None = "0003_evidence_checkpoints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("hook", sa.Column("config", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("hook", "config")
