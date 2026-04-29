"""Workflow graph + corpus metadata + document binary path.

Revision ID: 0007_workflow_graph_metadata
Revises: 0006_mcp_oauth_connections
Create Date: 2026-04-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_workflow_graph_metadata"
down_revision: str | None = "0006_mcp_oauth_connections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflow",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "workflow",
        sa.Column("graph", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )

    op.add_column("corpus", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("corpus", sa.Column("framework", sa.String(128), nullable=True))
    op.add_column("corpus", sa.Column("jurisdiction", sa.String(64), nullable=True))
    op.add_column("corpus", sa.Column("retention", sa.String(255), nullable=True))
    op.add_column("corpus", sa.Column("source_url", sa.String(1024), nullable=True))

    op.add_column("document", sa.Column("binary_path", sa.String(1024), nullable=True))
    op.add_column("document", sa.Column("media_type", sa.String(128), nullable=True))
    op.add_column("document", sa.Column("size_bytes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("document", "size_bytes")
    op.drop_column("document", "media_type")
    op.drop_column("document", "binary_path")

    op.drop_column("corpus", "source_url")
    op.drop_column("corpus", "retention")
    op.drop_column("corpus", "jurisdiction")
    op.drop_column("corpus", "framework")
    op.drop_column("corpus", "description")

    op.drop_column("workflow", "graph")
    op.drop_column("workflow", "description")
