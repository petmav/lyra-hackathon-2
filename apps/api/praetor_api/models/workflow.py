from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from praetor_api.models.base import Base, EntityMixin


class Workflow(EntityMixin, Base):
    __tablename__ = "workflow"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    inputs_schema: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    outputs_schema: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    required_hooks: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    required_corpora: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    default_policy_set: Mapped[str] = mapped_column(String(255), nullable=False)
    template_origin: Mapped[str | None] = mapped_column(String(512), nullable=True)
