"""
ExportService — orquestra criação, processamento e download de exports.

Fluxo:
  1. create() → persiste job no PG com status=pending
  2. process() → chamado via BackgroundTasks, atualiza status no PG
  3. get_file_path() → retorna caminho do arquivo gerado
"""
import io
import os
import uuid
from datetime import datetime, UTC

import httpx
import pandas as pd

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.export import Export
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.export_repository import ExportRepository
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.export import ExportCreate, ExportResponse, ExportListResponse
from app.core.security import decrypt_secret


class ExportService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ExportRepository(db)
        self.conn_repo = ConnectionRepository(db)
        self.audit = AuditLogRepository(db)

    def create(self, payload: ExportCreate, user_id: uuid.UUID) -> ExportResponse:
        connection = self.conn_repo.get_by_id(payload.connection_id)
        if not connection or not connection.is_active:
            raise AppException(status_code=404, error_code="CONNECTION_NOT_FOUND", detail="Conexão não encontrada ou inativa")

        export = Export(
            name=payload.name,
            entity_type=payload.entity_type,
            status="pending",
            connection_id=payload.connection_id,
            filter_config=payload.filter_config,
            columns_config=payload.columns_config,
            output_format=payload.output_format,
            created_by=user_id,
        )
        self.repo.create(export)
        return ExportResponse.model_validate(export)

    def list_by_user(self, user_id: uuid.UUID, page: int = 1, page_size: int = 20) -> dict:
        skip = (page - 1) * page_size
        items, total = self.repo.list_by_user(user_id, skip=skip, limit=page_size)
        return {
            "items": [ExportListResponse.model_validate(i) for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if total else 0,
        }

    def get(self, export_id: uuid.UUID, user_id: uuid.UUID) -> ExportResponse:
        export = self.repo.get_by_id(export_id)
        if not export or export.created_by != user_id:
            raise AppException(status_code=404, error_code="EXPORT_NOT_FOUND", detail="Export não encontrado")
        return ExportResponse.model_validate(export)

    def get_file_path(self, export_id: uuid.UUID, user_id: uuid.UUID) -> str:
        export = self.repo.get_by_id(export_id)
        if not export or export.created_by != user_id:
            raise AppException(status_code=404, error_code="EXPORT_NOT_FOUND", detail="Export não encontrado")
        if export.status != "completed" or not export.output_file_path:
            raise AppException(status_code=409, error_code="EXPORT_NOT_READY", detail="Export ainda não concluído")
        if not os.path.exists(export.output_file_path):
            raise AppException(status_code=410, error_code="FILE_EXPIRED", detail="Arquivo expirado ou removido")
        return export.output_file_path

    async def process(self, export_id: uuid.UUID) -> None:
        """Executa o export assincronamente (chamado via BackgroundTasks)."""
        export = self.repo.get_by_id(export_id)
        if not export:
            return

        self.repo.update_status(export_id, "processing", started_at=datetime.now(UTC))

        try:
            connection = self.conn_repo.get_by_id(export.connection_id)
            if not connection:
                raise ValueError("Conexão não encontrada")

            api_key = decrypt_secret(connection.api_key_enc) if connection.api_key_enc else ""
            base_url = connection.base_url or settings.MOSKIT_API_BASE_URL

            records = await self._fetch_records(
                base_url=base_url,
                api_key=api_key,
                entity_type=export.entity_type,
                filter_config=export.filter_config or {},
            )

            columns = (export.columns_config or {}).get("fields")
            file_path, file_name = self._generate_file(
                records=records,
                output_format=export.output_format,
                export_id=export_id,
                columns=columns,
            )

            self.repo.update_status(
                export_id,
                "completed",
                total_records=len(records),
                output_file_path=file_path,
                output_file_name=file_name,
                completed_at=datetime.now(UTC),
            )
            self.audit.log(
                action="export",
                user_id=export.created_by,
                entity_type="export",
                entity_id=str(export_id),
                new_value={"file_name": file_name, "total_records": len(records), "format": export.output_format},
            )

        except Exception as exc:
            self.repo.update_status(
                export_id,
                "failed",
                error_message=str(exc),
                completed_at=datetime.now(UTC),
            )
            self.audit.log(
                action="export",
                user_id=export.created_by,
                entity_type="export",
                entity_id=str(export_id),
                new_value={"status": "failed", "error": str(exc)},
            )

    async def _fetch_records(
        self,
        base_url: str,
        api_key: str,
        entity_type: str,
        filter_config: dict,
    ) -> list[dict]:
        endpoints = {
            "deal":     "/v2/deals",
            "contact":  "/v2/people",
            "company":  "/v2/companies",
            "activity": "/v2/activities",
        }
        endpoint = endpoints.get(entity_type, f"/v2/{entity_type}s")

        records: list[dict] = []
        page = 1

        async with httpx.AsyncClient(timeout=settings.MOSKIT_API_TIMEOUT) as client:
            while True:
                params: dict = {"page": page, "limit": 100, **filter_config}
                resp = await client.get(
                    f"{base_url}{endpoint}",
                    headers={"apikey": api_key, "Content-Type": "application/json"},
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()

                # Moskit retorna lista direta ou objeto com items
                batch = data if isinstance(data, list) else data.get("items", data.get("data", []))
                if not batch:
                    break
                records.extend(batch)
                if len(batch) < 100:
                    break
                page += 1

        return records

    def _generate_file(
        self,
        records: list[dict],
        output_format: str,
        export_id: uuid.UUID,
        columns: list[str] | None = None,
    ) -> tuple[str, str]:
        os.makedirs(settings.STORAGE_LOCAL_PATH, exist_ok=True)
        df = pd.json_normalize(records)

        if columns:
            existing = [c for c in columns if c in df.columns]
            df = df[existing] if existing else df

        file_name = f"export_{export_id}.{output_format}"
        file_path = os.path.join(settings.STORAGE_LOCAL_PATH, file_name)

        if output_format == "csv":
            df.to_csv(file_path, index=False, encoding="utf-8-sig")
        elif output_format == "xlsx":
            df.to_excel(file_path, index=False, engine="openpyxl")
        elif output_format == "json":
            df.to_json(file_path, orient="records", force_ascii=False, indent=2)

        return file_path, file_name
