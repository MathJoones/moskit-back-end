import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
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
    # session propria — a sessao do request ja foi fechada ao chegar aqui
    db = SessionLocal()
    try:
        await ExportService(db).process(export_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("", response_model=PaginatedResponse[ExportListResponse])
def list_exports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filtrar por status"),
    entity_type: Optional[str] = Query(None, description="Filtrar por entidade"),
    date_from: Optional[date] = Query(None, description="Data início (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Data fim (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_service),
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
