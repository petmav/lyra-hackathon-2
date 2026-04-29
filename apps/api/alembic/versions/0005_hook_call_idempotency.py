"""Add hook call idempotency keys.

Revision ID: 0005_hook_call_idempotency
Revises: 0004_hook_config
Create Date: 2026-04-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_hook_call_idempotency"
down_revision: str | None = "0004_hook_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("hook_call", sa.Column("idempotency_key", sa.String(255), nullable=True))
    op.create_index("ix_hook_call_idempotency_key", "hook_call", ["idempotency_key"])


def downgrade() -> None:
    op.drop_index("ix_hook_call_idempotency_key", table_name="hook_call")
    op.drop_column("hook_call", "idempotency_key")
