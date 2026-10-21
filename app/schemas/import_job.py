import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


EntityType = Literal["contact", "company", "deal"]
ImportStatus = Literal["pending", "processing", "completed", "cancelled", "error"]
ImportRowStatus = Literal["created", "duplicate", "error"]
ResultFileType = Literal["created", "duplicate", "error"]


class ImportCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    entity_type: EntityType
    connection_id: uuid.UUID
    mapping_group_id: uuid.UUID


class ImportRowResponse(BaseModel):
    id: uuid.UUID
    row_number: int
    status: ImportRowStatus
    moskit_id: str | None
    error_message: str | None
    retry_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportResponse(BaseModel):
    id: uuid.UUID
    name: str
    entity_type: EntityType
    status: ImportStatus
    connection_id: uuid.UUID | None
    mapping_group_id: uuid.UUID | None
    input_file_name: str | None
    total_rows: int | None
    processed: int
    created: int
    duplicates: int
    errors: int
    progress_pct: float
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_by: uuid.UUID
    created_at: datetime
    rows: list[ImportRowResponse] = []

    model_config = {"from_attributes": True}


class ImportListResponse(BaseModel):
    id: uuid.UUID
    name: str
    entity_type: EntityType
    status: ImportStatus
    total_rows: int | None
    processed: int
    created: int
    duplicates: int
    errors: int
    progress_pct: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportPreviewRow(BaseModel):
    row_number: int
    raw: dict[str, Any]
    transformed: dict[str, Any] | None
    error: str | None


class ImportPreviewResponse(BaseModel):
    entity_type: EntityType
    mapping_group_id: uuid.UUID
    rows: list[ImportPreviewRow]
