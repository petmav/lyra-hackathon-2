from uuid import UUID, uuid4

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from praetor_api.models.base import Base


class StepRun(Base):
    __tablename__ = "step_run"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workflow_run.id"))
    step_id: Mapped[str] = mapped_column(String(255), nullable=False)
    step_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    sandbox_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    hook_call_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    policy_decision_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    approval_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    emitted_finding_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    emitted_proposal_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    inputs_redacted: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    outputs_redacted: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
