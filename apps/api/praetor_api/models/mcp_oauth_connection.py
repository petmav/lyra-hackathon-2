from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from praetor_api.models.base import Base, EntityMixin


class McpOAuthConnection(EntityMixin, Base):
    __tablename__ = "mcp_oauth_connection"

    hook_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("hook.id"), nullable=True)
    endpoint: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    authorization_endpoint: Mapped[str] = mapped_column(String(1024), nullable=False)
    token_endpoint: Mapped[str] = mapped_column(String(1024), nullable=False)
    registration_endpoint: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    client_id: Mapped[str] = mapped_column(String(512), nullable=False)
    client_secret: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    redirect_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    state: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    code_verifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registration: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    token_set: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
