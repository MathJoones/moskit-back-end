import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.import_job import ImportJob
from app.repositories.base import BaseRepository


class ImportRepository(BaseRepository[ImportJob]):
    def __init__(self, db: Session):
        super().__init__(ImportJob, db)

    def list_by_user(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ImportJob], int]:
        query = self.db.query(ImportJob).filter(
            ImportJob.created_by == user_id,
            ImportJob.deleted_at.is_(None),
        )
        total = query.with_entities(func.count(ImportJob.id)).scalar()
        items = query.order_by(ImportJob.created_at.desc()).offset(skip).limit(limit).all()
        return items, total or 0

    def get_active(self, import_id: uuid.UUID) -> ImportJob | None:
        return (
            self.db.query(ImportJob)
            .filter(
                ImportJob.id == import_id,
                ImportJob.deleted_at.is_(None),
            )
            .first()
        )

    def update_status(
        self,
        import_id: uuid.UUID,
        status: str,
        *,
        error_message: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        celery_task_id: str | None = None,
        total_rows: int | None = None,
    ) -> ImportJob | None:
        job = self.get_active(import_id)
        if not job:
            return None
        job.status = status
        if error_message is not None:
            job.error_message = error_message
        if started_at is not None:
            job.started_at = started_at
        if completed_at is not None:
            job.completed_at = completed_at
        if celery_task_id is not None:
            job.celery_task_id = celery_task_id
        if total_rows is not None:
            job.total_rows = total_rows
        self.db.commit()
        self.db.refresh(job)
        return job

    def update_progress(
        self,
        import_id: uuid.UUID,
        *,
        processed: int,
        created: int,
        duplicates: int,
        errors: int,
        progress_pct: float,
    ) -> ImportJob | None:
        job = self.get_active(import_id)
        if not job:
            return None
        job.processed = processed
        job.created = created
        job.duplicates = duplicates
        job.errors = errors
        job.progress_pct = progress_pct
        self.db.commit()
        self.db.refresh(job)
        return job

    def soft_delete(self, job: ImportJob) -> ImportJob:
        job.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job
