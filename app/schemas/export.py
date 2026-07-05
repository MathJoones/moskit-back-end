import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


EntityType = Literal["deal", "contact", "company", "activity"]
ExportFormat = Literal["csv", "xlsx", "json"]
ExportStatus = Literal["pending", "processing", "completed", "failed"]


class ExportCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    entity_type: EntityType
    connection_id: uuid.UUID
    output_format: ExportFormat = "xlsx"
    filter_config: dict | None = None
    columns_config: dict | None = None


class ExportResponse(BaseModel):
    id: uuid.UUID
    name: str
    entity_type: EntityType
    status: ExportStatus
    connection_id: uuid.UUID | None
    output_format: ExportFormat
    output_file_name: str | None
    total_records: int | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ExportListResponse(BaseModel):
    id: uuid.UUID
    name: str
    entity_type: EntityType
    status: ExportStatus
    output_format: ExportFormat
    total_records: int | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
