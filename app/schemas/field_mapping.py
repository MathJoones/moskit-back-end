import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


EntityType = Literal["contact", "company", "deal"]
TransformerType = Literal["date", "phone", "enum", "string", "number"]


class FieldMappingCreate(BaseModel):
    source_column: str = Field(..., min_length=1, max_length=255)
    target_field: str = Field(..., min_length=1, max_length=255)
    transformer_type: TransformerType = "string"
    transformer_config: dict | None = None
    is_required: bool = False


class FieldMappingResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    source_column: str
    target_field: str
    transformer_type: TransformerType
    transformer_config: dict | None
    is_required: bool

    model_config = {"from_attributes": True}


class FieldMappingGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    entity_type: EntityType
    dedup_enabled: bool = False
    dedup_keys: list[str] | None = None
    mappings: list[FieldMappingCreate] = Field(default_factory=list)


class FieldMappingGroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    entity_type: EntityType
    dedup_enabled: bool
    dedup_keys: list[str] | None
    created_by: uuid.UUID
    created_at: datetime
    mappings: list[FieldMappingResponse] = []

    model_config = {"from_attributes": True}


class FieldMappingGroupListResponse(BaseModel):
    id: uuid.UUID
    name: str
    entity_type: EntityType
    dedup_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}
