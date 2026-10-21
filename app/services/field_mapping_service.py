import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ForbiddenError
from app.models.field_mapping_group import FieldMappingGroup
from app.models.field_mapping import FieldMapping
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.field_mapping_repository import (
    FieldMappingGroupRepository,
    FieldMappingRepository,
)
from app.schemas.field_mapping import (
    FieldMappingGroupCreate,
    FieldMappingGroupListResponse,
    FieldMappingGroupResponse,
)


class FieldMappingService:
    def __init__(self, db: Session):
        self.db = db
        self.group_repo = FieldMappingGroupRepository(db)
        self.mapping_repo = FieldMappingRepository(db)
        self.audit = AuditLogRepository(db)

    def create(
        self, payload: FieldMappingGroupCreate, user_id: uuid.UUID
    ) -> FieldMappingGroupResponse:
        group = FieldMappingGroup(
            name=payload.name,
            entity_type=payload.entity_type,
            dedup_enabled=payload.dedup_enabled,
            dedup_keys=payload.dedup_keys,
            created_by=user_id,
        )
        self.group_repo.create(group)

        if payload.mappings:
            field_mappings = [
                FieldMapping(
                    group_id=group.id,
                    source_column=m.source_column,
                    target_field=m.target_field,
                    transformer_type=m.transformer_type,
                    transformer_config=m.transformer_config,
                    is_required=m.is_required,
                )
                for m in payload.mappings
            ]
            self.mapping_repo.bulk_create(field_mappings)
            self.db.refresh(group)

        self.audit.log(
            action="create",
            user_id=user_id,
            entity_type="field_mapping_group",
            entity_id=str(group.id),
            new_value={"name": group.name, "entity_type": group.entity_type},
        )
        return FieldMappingGroupResponse.model_validate(group)

    def list(
        self,
        page: int = 1,
        page_size: int = 20,
        entity_type: str | None = None,
    ) -> dict:
        skip = (page - 1) * page_size
        items, total = self.group_repo.list_active(
            skip=skip, limit=page_size, entity_type=entity_type
        )
        return {
            "items": [FieldMappingGroupListResponse.model_validate(i) for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if total else 0,
        }

    def get(self, group_id: uuid.UUID) -> FieldMappingGroupResponse:
        group = self.group_repo.get_active(group_id)
        if not group:
            raise NotFoundError("FieldMappingGroup", str(group_id))
        return FieldMappingGroupResponse.model_validate(group)

    def delete(self, group_id: uuid.UUID, user_id: uuid.UUID) -> None:
        group = self.group_repo.get_active(group_id)
        if not group:
            raise NotFoundError("FieldMappingGroup", str(group_id))
        self.group_repo.soft_delete(group)
        self.audit.log(
            action="delete",
            user_id=user_id,
            entity_type="field_mapping_group",
            entity_id=str(group_id),
        )
