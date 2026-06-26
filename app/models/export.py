import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Export(Base, TimestampMixin):
    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(
        SAEnum("deal", "contact", "company", "activity", name="export_entity_type"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "processing", "completed", "failed", name="export_status"),
        nullable=False,
        default="pending",
    )
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_connections.id", ondelete="SET NULL"), nullable=True
    )
    filter_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    columns_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_format: Mapped[str] = mapped_column(
        SAEnum("csv", "xlsx", "json", name="export_format"),
        nullable=False,
        default="xlsx",
    )
    output_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    output_file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    total_records: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
