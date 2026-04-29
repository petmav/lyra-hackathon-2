from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from praetor_api.models.base import Base, EntityMixin


class AuditPacket(EntityMixin, Base):
    __tablename__ = "audit_packet"

    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scope: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    pdf_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    json_sidecar_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    packet_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(String(512), nullable=False)
