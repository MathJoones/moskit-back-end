import json
import threading
import uuid
from datetime import date, datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppException
from app.middleware.auth import require_operator_or_admin
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.import_job import (
    ColumnMapping,
    ImportCreate,
    ImportListResponse,
    ImportPreviewResponse,
    ImportResponse,
)
from app.services.import_service import ImportService
from app.tasks.import_task import process_import

router = APIRouter()


def get_service(db: Session = Depends(get_db)) -> ImportService:
    return ImportService(db)


@router.get("", response_model=PaginatedResponse[ImportListResponse])
def list_imports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: User = Depends(require_operator_or_admin),
    service: ImportService = Depends(get_service),
):
    dt_from = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc) if date_from else None
    dt_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc) if date_to else None
    return service.list_by_user(
        current_user.id,
        page=page,
        page_size=page_size,
        status=status,
        entity_type=entity_type,
        date_from=dt_from,
        date_to=dt_to,
    )


@router.post("", response_model=ImportResponse, status_code=202)
async def create_import(
    name: str = Form(...),
    entity_type: Literal["contact", "company", "deal"] = Form(...),
    connection_id: uuid.UUID = Form(...),
    column_mappings: str = Form(..., description="JSON array de ColumnMapping"),
    dedup_keys: Optional[str] = Form(None, description="JSON array de strings ou null"),
    file: UploadFile = File(...),
    current_user: User = Depends(require_operator_or_admin),
    service: ImportService = Depends(get_service),
):
    try:
        mappings_raw: list = json.loads(column_mappings)
        parsed_mappings = [ColumnMapping(**m) for m in mappings_raw]
    except Exception:
        raise AppException(
            error_code="INVALID_COLUMN_MAPPINGS",
            detail="column_mappings deve ser um JSON array valido de ColumnMapping",
        )

    dedup_list: list[str] | None = None
    if dedup_keys:
        try:
            dedup_list = json.loads(dedup_keys)
        except Exception:
            raise AppException(
                error_code="INVALID_DEDUP_KEYS",
                detail="dedup_keys deve ser um JSON array de strings ou null",
            )

    file_bytes = await file.read()
    payload = ImportCreate(
        name=name,
        entity_type=entity_type,
        connection_id=connection_id,
        column_mappings=parsed_mappings,
        dedup_keys=dedup_list,
    )
    job = service.create(payload, file_bytes, file.filename or "import.csv", current_user.id)

    try:
        task = process_import.delay(str(job.id))
        service.repo.update_status(job.id, "pending", celery_task_id=task.id)
    except Exception:
        threading.Thread(
            target=process_import,
            args=(str(job.id),),
            daemon=True,
        ).start()

    return ImportResponse.model_validate(job)


@router.get("/{import_id}", response_model=ImportResponse)
def get_import(
    import_id: uuid.UUID,
    current_user: User = Depends(require_operator_or_admin),
    service: ImportService = Depends(get_service),
):
    return service.get(import_id, current_user.id)


@router.delete("/{import_id}", response_model=ImportResponse)
def cancel_import(
    import_id: uuid.UUID,
    current_user: User = Depends(require_operator_or_admin),
    service: ImportService = Depends(get_service),
):
    return service.cancel(import_id, current_user.id)


@router.post("/{import_id}/preview", response_model=ImportPreviewResponse)
def preview_import(
    import_id: uuid.UUID,
    current_user: User = Depends(require_operator_or_admin),
    service: ImportService = Depends(get_service),
):
    return service.preview(import_id, current_user.id)


@router.get("/{import_id}/download/{result_type}")
def download_result(
    import_id: uuid.UUID,
    result_type: Literal["created", "duplicate", "error"],
    current_user: User = Depends(require_operator_or_admin),
    service: ImportService = Depends(get_service),
):
    file_path = service.get_result_file(import_id, current_user.id, result_type)
    filename = f"import_{import_id}_{result_type}.csv"
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="text/csv; charset=utf-8",
    )
