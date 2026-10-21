import uuid

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class FieldMappingGroup(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "field_mapping_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(
        SAEnum("contact", "company", "deal", name="import_entity_type", create_type=False),
        nullable=False,
    )
    dedup_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dedup_keys: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    mappings: Mapped[list["FieldMapping"]] = relationship(
        "FieldMapping", back_populates="group", cascade="all, delete-orphan"
    )
