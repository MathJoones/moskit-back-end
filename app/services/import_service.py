"""
ImportService — orquestra upload, parse, preview, criacao do job e CSVs de resultado.
O despacho do Celery task fica no controller (mesmo padrao do ExportService).
"""
import csv
import io
import uuid
from datetime import datetime, UTC
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppException, NotFoundError
from app.mappings.engine import MappingEngine
from app.models.import_job import ImportJob
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.import_repository import ImportRepository
from app.repositories.import_row_repository import ImportRowRepository
from app.schemas.import_job import (
    ImportCreate,
    ImportListResponse,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportResponse,
)

PREVIEW_ROWS = 5
RESULT_STATUSES = ("created", "duplicate", "error")


def _upload_dir() -> Path:
    path = Path(settings.STORAGE_LOCAL_PATH) / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _result_dir() -> Path:
    path = Path(settings.STORAGE_LOCAL_PATH) / "results"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _parse_file(file_bytes: bytes, filename: str) -> list[dict[str, str]]:
    """CSV ou XLSX → lista de dicts com headers como chaves."""
    ext = Path(filename).suffix.lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0, dtype=str)
        df = df.fillna("")
        return df.to_dict(orient="records")

    text = file_bytes.decode("utf-8-sig", errors="replace")
    dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    return [dict(row) for row in reader]


class ImportService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ImportRepository(db)
        self.row_repo = ImportRowRepository(db)
        self.conn_repo = ConnectionRepository(db)
        self.audit = AuditLogRepository(db)

    # ── Criacao ──────────────────────────────────────────────────────────────

    def create(
        self,
        payload: ImportCreate,
        file_bytes: bytes,
        filename: str,
        user_id: uuid.UUID,
    ) -> ImportJob:
        """
        Salva arquivo, cria ImportJob com status 'pending'.
        Retorna o modelo ORM — controller despacha Celery task.
        """
        connection = self.conn_repo.get_by_id(payload.connection_id)
        if not connection or not connection.is_active:
            raise NotFoundError("ApiConnection", str(payload.connection_id))

        upload_path = _upload_dir() / f"import_{uuid.uuid4()}_{filename}"
        upload_path.write_bytes(file_bytes)

        rows = _parse_file(file_bytes, filename)
        total_rows = len(rows)

        column_mappings = [m.model_dump() for m in payload.column_mappings]

        job = ImportJob(
            name=payload.name,
            entity_type=payload.entity_type,
            status="pending",
            connection_id=payload.connection_id,
            column_mappings=column_mappings,
            dedup_keys=payload.dedup_keys,
            input_file_path=str(upload_path),
            input_file_name=filename,
            total_rows=total_rows,
            created_by=user_id,
        )
        self.repo.create(job)

        self.audit.log(
            action="import",
            user_id=user_id,
            entity_type="import",
            entity_id=str(job.id),
            new_value={
                "name": job.name,
                "entity_type": job.entity_type,
                "total_rows": total_rows,
                "filename": filename,
            },
        )
        return job

    # ── Listagem / Detalhe ───────────────────────────────────────────────────

    def list_by_user(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        entity_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        skip = (page - 1) * page_size
        items, total = self.repo.list_by_user(
            user_id,
            skip=skip,
            limit=page_size,
            status=status,
            entity_type=entity_type,
            date_from=date_from,
            date_to=date_to,
        )
        return {
            "items": [ImportListResponse.model_validate(i) for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if total else 0,
        }

    def get(self, import_id: uuid.UUID, user_id: uuid.UUID) -> ImportResponse:
        job = self.repo.get_active(import_id)
        if not job or job.created_by != user_id:
            raise NotFoundError("Import", str(import_id))
        return ImportResponse.model_validate(job)

    # ── Preview ──────────────────────────────────────────────────────────────

    def preview(self, import_id: uuid.UUID, user_id: uuid.UUID) -> ImportPreviewResponse:
        job = self.repo.get_active(import_id)
        if not job or job.created_by != user_id:
            raise NotFoundError("Import", str(import_id))

        if not job.input_file_path or not Path(job.input_file_path).exists():
            raise AppException(
                error_code="FILE_NOT_FOUND",
                detail="Arquivo de importacao nao encontrado no servidor",
            )

        file_bytes = Path(job.input_file_path).read_bytes()
        rows = _parse_file(file_bytes, job.input_file_name or "file.csv")
        sample = rows[:PREVIEW_ROWS]

        engine = MappingEngine(job.column_mappings or [])
        results = engine.process_preview(sample)

        return ImportPreviewResponse(
            entity_type=job.entity_type,
            rows=[
                ImportPreviewRow(
                    row_number=r["row_number"],
                    raw=r["raw"],
                    transformed=r["transformed"],
                    error=r["error"],
                )
                for r in results
            ],
        )

    # ── Cancelamento ─────────────────────────────────────────────────────────

    def cancel(self, import_id: uuid.UUID, user_id: uuid.UUID) -> ImportResponse:
        job = self.repo.get_active(import_id)
        if not job or job.created_by != user_id:
            raise NotFoundError("Import", str(import_id))

        if job.status in ("completed", "cancelled", "error"):
            raise AppException(
                error_code="IMPORT_ALREADY_FINISHED",
                detail=f"Import ja finalizado com status '{job.status}'",
            )

        if job.celery_task_id:
            try:
                from app.worker import celery_app
                celery_app.control.revoke(job.celery_task_id, terminate=True)
            except Exception:
                pass

        self.repo.update_status(import_id, "cancelled", completed_at=datetime.now(UTC))
        self.audit.log(
            action="update",
            user_id=user_id,
            entity_type="import",
            entity_id=str(import_id),
            new_value={"status": "cancelled"},
        )
        return self.get(import_id, user_id)

    # ── CSVs de resultado ────────────────────────────────────────────────────

    def get_result_file(
        self,
        import_id: uuid.UUID,
        user_id: uuid.UUID,
        result_type: str,
    ) -> str:
        if result_type not in RESULT_STATUSES:
            raise AppException(
                error_code="INVALID_RESULT_TYPE",
                detail=f"Tipo invalido: '{result_type}'. Use: {RESULT_STATUSES}",
            )

        job = self.repo.get_active(import_id)
        if not job or job.created_by != user_id:
            raise NotFoundError("Import", str(import_id))

        if job.status not in ("completed", "cancelled"):
            raise AppException(
                error_code="IMPORT_NOT_READY",
                detail="Import ainda nao finalizado",
            )

        result_path = _result_dir() / f"import_{import_id}_{result_type}.csv"

        rows, _ = self.row_repo.list_by_import(
            import_id, skip=0, limit=100_000, status=result_type
        )

        fieldnames = ["row_number", "status", "moskit_id", "error_message", "retry_count"]
        with open(result_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({
                    "row_number": row.row_number,
                    "status": row.status,
                    "moskit_id": row.moskit_id or "",
                    "error_message": row.error_message or "",
                    "retry_count": row.retry_count,
                })

        return str(result_path)
