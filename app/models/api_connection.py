import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class ApiConnection(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "api_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    connection_type: Mapped[str] = mapped_column(
        SAEnum("moskit", "external_api", "csv", "xlsx", "database", name="connection_type"),
        nullable=False,
    )
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Armazenados como blobs criptografados AES-256-GCM
    # Nunca expor diretamente — usar security.decrypt_secret()
    api_key_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    api_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    extra_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
