import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


EntityType = Literal["contact", "company", "deal"]
ImportStatus = Literal["pending", "processing", "completed", "cancelled", "error"]
ImportRowStatus = Literal["created", "duplicate", "error"]
ResultFileType = Literal["created", "duplicate", "error"]


class ColumnMapping(BaseModel):
    csv_column: str
    target_field: str
    transformer: str | None = "string"
    transformer_config: dict | None = None
    is_required: bool = False


class ImportCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    entity_type: EntityType
    connection_id: uuid.UUID
    column_mappings: list[ColumnMapping] = Field(default_factory=list)
    dedup_keys: list[str] | None = None


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
    column_mappings: list[dict] | None
    dedup_keys: list[str] | None
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
    input_file_name: str | None
    total_rows: int | None
    processed: int
    created: int
    duplicates: int
    errors: int
    progress_pct: float
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportPreviewRow(BaseModel):
    row_number: int
    raw: dict[str, Any]
    transformed: dict[str, Any] | None
    error: str | None


class ImportPreviewResponse(BaseModel):
    entity_type: EntityType
    rows: list[ImportPreviewRow]
