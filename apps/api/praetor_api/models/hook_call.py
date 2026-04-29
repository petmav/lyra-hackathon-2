from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from praetor_api.models.base import Base


class HookCall(Base):
    __tablename__ = "hook_call"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    hook_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("hook.id"))
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    workflow_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    step_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    inputs_redacted: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    outputs_redacted: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    errors: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    policy_decision_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
