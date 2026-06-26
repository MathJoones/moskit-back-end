import uuid
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.export import Export
from app.repositories.base import BaseRepository


class ExportRepository(BaseRepository[Export]):
    def __init__(self, db: Session):
        super().__init__(Export, db)

    def list_by_user(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Export], int]:
        total = self.db.query(func.count(Export.id)).filter(Export.created_by == user_id).scalar()
        items = (
            self.db.query(Export)
            .filter(Export.created_by == user_id)
            .order_by(Export.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total or 0

    def update_status(
        self,
        export_id: uuid.UUID,
        status: str,
        *,
        total_records: int | None = None,
        output_file_path: str | None = None,
        output_file_name: str | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> Export | None:
        export = self.get_by_id(export_id)
        if not export:
            return None
        export.status = status
        if total_records is not None:
            export.total_records = total_records
        if output_file_path is not None:
            export.output_file_path = output_file_path
        if output_file_name is not None:
            export.output_file_name = output_file_name
        if error_message is not None:
            export.error_message = error_message
        if started_at is not None:
            export.started_at = started_at
        if completed_at is not None:
            export.completed_at = completed_at
        self.db.commit()
        self.db.refresh(export)
        return export
