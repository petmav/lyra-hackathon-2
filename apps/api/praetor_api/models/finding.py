from uuid import UUID

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from praetor_api.models.base import Base, EntityMixin


class Finding(EntityMixin, Base):
    __tablename__ = "finding"

    workflow_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workflow_run.id"))
    asset_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("asset.id"))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    obligations_cited: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    documents_cited: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    proposed_change_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
