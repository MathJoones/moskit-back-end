import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.field_mapping_group import FieldMappingGroup
from app.models.field_mapping import FieldMapping
from app.repositories.base import BaseRepository


class FieldMappingGroupRepository(BaseRepository[FieldMappingGroup]):
    def __init__(self, db: Session):
        super().__init__(FieldMappingGroup, db)

    def list_active(
        self,
        skip: int = 0,
        limit: int = 20,
        entity_type: str | None = None,
    ) -> tuple[list[FieldMappingGroup], int]:
        query = self.db.query(FieldMappingGroup).filter(
            FieldMappingGroup.deleted_at.is_(None)
        )
        if entity_type:
            query = query.filter(FieldMappingGroup.entity_type == entity_type)
        total = query.with_entities(func.count(FieldMappingGroup.id)).scalar()
        items = query.order_by(FieldMappingGroup.created_at.desc()).offset(skip).limit(limit).all()
        return items, total or 0

    def get_active(self, group_id: uuid.UUID) -> FieldMappingGroup | None:
        return (
            self.db.query(FieldMappingGroup)
            .filter(
                FieldMappingGroup.id == group_id,
                FieldMappingGroup.deleted_at.is_(None),
            )
            .first()
        )

    def soft_delete(self, group: FieldMappingGroup) -> FieldMappingGroup:
        group.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(group)
        return group


class FieldMappingRepository(BaseRepository[FieldMapping]):
    def __init__(self, db: Session):
        super().__init__(FieldMapping, db)

    def list_by_group(self, group_id: uuid.UUID) -> list[FieldMapping]:
        return (
            self.db.query(FieldMapping)
            .filter(FieldMapping.group_id == group_id)
            .all()
        )

    def bulk_create(self, mappings: list[FieldMapping]) -> list[FieldMapping]:
        self.db.add_all(mappings)
        self.db.commit()
        for m in mappings:
            self.db.refresh(m)
        return mappings
