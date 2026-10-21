import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class ImportJob(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "imports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(
        SAEnum("contact", "company", "deal", name="import_entity_type", create_type=False),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "processing", "completed", "cancelled", "error", name="import_status", create_type=False),
        nullable=False,
        default="pending",
    )
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    mapping_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("field_mapping_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    input_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    input_file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    rows: Mapped[list["ImportRow"]] = relationship(
        "ImportRow", back_populates="import_job", cascade="all, delete-orphan"
    )
