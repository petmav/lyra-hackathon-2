from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from praetor_api.models.base import Base, EntityMixin


class Document(EntityMixin, Base):
    __tablename__ = "document"

    corpus_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("corpus.id"))
    source_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    citation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    framework: Mapped[str | None] = mapped_column(String(128), nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    text_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    binary_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parsed_structure: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
