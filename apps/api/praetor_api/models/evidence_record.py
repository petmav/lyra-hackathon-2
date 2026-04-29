from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from praetor_api.models.base import Base, EntityMixin


class EvidenceRecord(EntityMixin, Base):
    __tablename__ = "evidence_record"

    obligation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("obligation.id"))
    control_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("asset.id"))
    workflow_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workflow_run.id"))
    event_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    decision_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
