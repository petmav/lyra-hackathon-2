from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from praetor_api.models.base import Base, EntityMixin


class Asset(EntityMixin, Base):
    __tablename__ = "asset"

    type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(8), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_asset_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("asset.id"),
        nullable=True,
    )
    jurisdictions: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    data_classifications: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    sectors: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
