from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from praetor_api.models.base import Base
from praetor_api.models.vector import Vector


class DocumentChunk(Base):
    __tablename__ = "document_chunk"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document.id"))
    ord: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    keyword_tokens: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    citation_path: Mapped[str] = mapped_column(String(512), nullable=False)
