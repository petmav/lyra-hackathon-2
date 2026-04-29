"""Add MCP OAuth connections.

Revision ID: 0006_mcp_oauth_connections
Revises: 0005_hook_call_idempotency
Create Date: 2026-04-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_mcp_oauth_connections"
down_revision: str | None = "0005_hook_call_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_oauth_connection",
        sa.Column("hook_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hook.id"), nullable=True),
        sa.Column("endpoint", sa.String(512), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("issuer", sa.String(512), nullable=True),
        sa.Column("authorization_endpoint", sa.String(1024), nullable=False),
        sa.Column("token_endpoint", sa.String(1024), nullable=False),
        sa.Column("registration_endpoint", sa.String(1024), nullable=True),
        sa.Column("client_id", sa.String(512), nullable=False),
        sa.Column("client_secret", sa.String(1024), nullable=True),
        sa.Column("redirect_uri", sa.String(1024), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("state", sa.String(255), nullable=True),
        sa.Column("code_verifier", sa.String(255), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registration", postgresql.JSONB(), nullable=True),
        sa.Column("token_set", postgresql.JSONB(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("urn", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_mcp_oauth_connection_urn", "mcp_oauth_connection", ["urn"], unique=True)
    op.create_index("ix_mcp_oauth_connection_state", "mcp_oauth_connection", ["state"])
    op.create_index("ix_mcp_oauth_connection_status", "mcp_oauth_connection", ["status"])


def downgrade() -> None:
    op.drop_index("ix_mcp_oauth_connection_status", table_name="mcp_oauth_connection")
    op.drop_index("ix_mcp_oauth_connection_state", table_name="mcp_oauth_connection")
    op.drop_index("ix_mcp_oauth_connection_urn", table_name="mcp_oauth_connection")
    op.drop_table("mcp_oauth_connection")
