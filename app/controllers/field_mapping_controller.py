import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middleware.auth import require_admin, require_operator_or_admin
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.field_mapping import FieldMappingGroupCreate, FieldMappingGroupListResponse, FieldMappingGroupResponse
from app.services.field_mapping_service import FieldMappingService

router = APIRouter()


def get_service(db: Session = Depends(get_db)) -> FieldMappingService:
    return FieldMappingService(db)


@router.get("", response_model=PaginatedResponse[FieldMappingGroupListResponse])
def list_field_mapping_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    entity_type: Literal["contact", "company", "deal"] | None = None,
    current_user: User = Depends(require_operator_or_admin),
    service: FieldMappingService = Depends(get_service),
):
    return service.list(page=page, page_size=page_size, entity_type=entity_type)


@router.post("", response_model=FieldMappingGroupResponse, status_code=201)
def create_field_mapping_group(
    payload: FieldMappingGroupCreate,
    current_user: User = Depends(require_admin),
    service: FieldMappingService = Depends(get_service),
):
    return service.create(payload, current_user.id)


@router.get("/{group_id}", response_model=FieldMappingGroupResponse)
def get_field_mapping_group(
    group_id: uuid.UUID,
    current_user: User = Depends(require_operator_or_admin),
    service: FieldMappingService = Depends(get_service),
):
    return service.get(group_id)


@router.delete("/{group_id}", status_code=204)
def delete_field_mapping_group(
    group_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    service: FieldMappingService = Depends(get_service),
):
    service.delete(group_id, current_user.id)
