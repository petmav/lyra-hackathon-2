from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from praetor_api.models.base import Base, EntityMixin


class ProposedChange(EntityMixin, Base):
    __tablename__ = "proposed_change"

    finding_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("finding.id"))
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    diff: Mapped[str] = mapped_column(Text, nullable=False)
    diff_format: Mapped[str] = mapped_column(String(32), nullable=False)
    target_asset_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    target_hook_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    obligations_addressed: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    residual_risk_estimate: Mapped[str | None] = mapped_column(Text, nullable=True)
    sandbox_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    approver: Mapped[str | None] = mapped_column(String(255), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    apply_via_hook_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
