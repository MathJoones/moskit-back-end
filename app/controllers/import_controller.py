import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middleware.auth import require_operator_or_admin
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.import_job import (
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
    current_user: User = Depends(require_operator_or_admin),
    service: ImportService = Depends(get_service),
):
    return service.list_by_user(current_user.id, page=page, page_size=page_size)


@router.post("", response_model=ImportResponse, status_code=202)
async def create_import(
    name: str = Form(...),
    entity_type: Literal["contact", "company", "deal"] = Form(...),
    connection_id: uuid.UUID = Form(...),
    mapping_group_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_operator_or_admin),
    service: ImportService = Depends(get_service),
):
    from app.schemas.import_job import ImportCreate
    file_bytes = await file.read()
    payload = ImportCreate(
        name=name,
        entity_type=entity_type,
        connection_id=connection_id,
        mapping_group_id=mapping_group_id,
    )
    job = service.create(payload, file_bytes, file.filename or "import.csv", current_user.id)

    # Despacha task Celery e salva task_id no job
    task = process_import.delay(str(job.id))
    service.repo.update_status(job.id, "pending", celery_task_id=task.id)

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
