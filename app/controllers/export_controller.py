import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.export import ExportCreate, ExportResponse, ExportListResponse
from app.services.export_service import ExportService
from app.schemas.common import PaginatedResponse

router = APIRouter()


def get_service(db: Session = Depends(get_db)) -> ExportService:
    return ExportService(db)


async def _run_export_background(export_id: uuid.UUID) -> None:
    """Cria session própria para o background task — a session do request já foi fechada."""
    db = SessionLocal()
    try:
        await ExportService(db).process(export_id)
    finally:
        db.close()


@router.get("", response_model=PaginatedResponse[ExportListResponse])
def list_exports(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_service),
):
    return service.list_by_user(current_user.id, page=page, page_size=page_size)


@router.post("", response_model=ExportResponse, status_code=202)
async def create_export(
    payload: ExportCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_service),
):
    export = service.create(payload, current_user.id)
    background_tasks.add_task(_run_export_background, export.id)
    return export


@router.get("/{export_id}", response_model=ExportResponse)
def get_export(
    export_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_service),
):
    return service.get(export_id, current_user.id)


@router.get("/{export_id}/download")
def download_export(
    export_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_service),
):
    file_path = service.get_file_path(export_id, current_user.id)
    export = service.get(export_id, current_user.id)
    return FileResponse(
        path=file_path,
        filename=export.output_file_name or f"export_{export_id}",
        media_type="application/octet-stream",
    )
