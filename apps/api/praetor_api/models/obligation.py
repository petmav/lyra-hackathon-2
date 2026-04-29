from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from praetor_api.models.base import Base, EntityMixin


class Obligation(EntityMixin, Base):
    __tablename__ = "obligation"

    framework: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    citation: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    applicability: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    severity_default: Mapped[str] = mapped_column(String(32), nullable=False)
