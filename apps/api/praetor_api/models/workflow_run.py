from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from praetor_api.models.base import Base, EntityMixin


class WorkflowRun(EntityMixin, Base):
    __tablename__ = "workflow_run"

    workflow_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workflow.id"))
    asset_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("asset.id"))
    triggered_by: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    inputs: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    outputs: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    evidence_record_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
