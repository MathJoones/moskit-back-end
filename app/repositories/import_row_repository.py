import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.import_row import ImportRow
from app.repositories.base import BaseRepository


class ImportRowRepository(BaseRepository[ImportRow]):
    def __init__(self, db: Session):
        super().__init__(ImportRow, db)

    def list_by_import(
        self,
        import_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> tuple[list[ImportRow], int]:
        query = self.db.query(ImportRow).filter(ImportRow.import_id == import_id)
        if status:
            query = query.filter(ImportRow.status == status)
        total = query.with_entities(func.count(ImportRow.id)).scalar()
        items = query.order_by(ImportRow.row_number.asc()).offset(skip).limit(limit).all()
        return items, total or 0

    def count_by_status(self, import_id: uuid.UUID) -> dict[str, int]:
        rows = (
            self.db.query(ImportRow.status, func.count(ImportRow.id))
            .filter(ImportRow.import_id == import_id)
            .group_by(ImportRow.status)
            .all()
        )
        return {status: count for status, count in rows}

    def bulk_create(self, rows: list[ImportRow]) -> list[ImportRow]:
        self.db.add_all(rows)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows

    def update_row(
        self,
        row: ImportRow,
        *,
        status: str,
        moskit_id: str | None = None,
        error_message: str | None = None,
        retry_count: int | None = None,
    ) -> ImportRow:
        row.status = status
        if moskit_id is not None:
            row.moskit_id = moskit_id
        if error_message is not None:
            row.error_message = error_message
        if retry_count is not None:
            row.retry_count = retry_count
        self.db.commit()
        self.db.refresh(row)
        return row
