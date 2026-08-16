# Orquestra criacao, processamento (background) e download de exports
import csv
import json
import os
import uuid
from datetime import datetime, UTC
from pathlib import Path

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


# Normalizadores por tipo de entidade Moskit
def _fmt_date(iso: str | None) -> str:
    """ISO 8601 → DD/MM/YYYY HH:MM"""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso or ""


def _extract_list_field(items: list, field: str, sep: str = " | ") -> str:
    """Extrai campo de lista de dicts e junta com separador."""
    if not isinstance(items, list):
        return ""
    return sep.join(str(i.get(field, "")) for i in items if i.get(field))


def normalize_contact(r: dict) -> dict:
    phones = r.get("phones") or []
    emails = r.get("emails") or []
    employers = r.get("employers") or []

    return {
        "ID": r.get("id", ""),
        "Nome": r.get("name", ""),
        "Email": _extract_list_field(emails, "address"),
        "Telefone": _extract_list_field(phones, "number"),
        "Empresa (ID)": " | ".join(
            str(e.get("company", {}).get("id", "")) for e in employers if e.get("company")
        ),
        "Responsável (ID)": (r.get("responsible") or {}).get("id", ""),
        "Observações": r.get("notes", ""),
        "Origem": r.get("origin", ""),
        "Data Criação": _fmt_date(r.get("dateCreated")),
    }


def normalize_deal(r: dict) -> dict:
    contacts = r.get("contacts") or []
    companies = r.get("companies") or []
    stage = r.get("stage") or {}

    return {
        "ID": r.get("id", ""),
        "Nome": r.get("name", ""),
        "Valor": r.get("price", ""),
        "Status": r.get("status", ""),
        "Etapa (ID)": stage.get("id", ""),
        "Contatos (IDs)": _extract_list_field(contacts, "id"),
        "Empresas (IDs)": _extract_list_field(companies, "id"),
        "Responsável (ID)": (r.get("responsible") or {}).get("id", ""),
        "Origem": r.get("origin", ""),
        "Data Criação": _fmt_date(r.get("dateCreated")),
        "Previsão Fechamento": _fmt_date(r.get("previsionCloseDate")),
        "Data Fechamento": _fmt_date(r.get("closeDate")),
    }


def normalize_company(r: dict) -> dict:
    phones = r.get("phones") or []
    emails = r.get("emails") or []

    return {
        "ID": r.get("id", ""),
        "Nome": r.get("name", ""),
        "Email": _extract_list_field(emails, "address"),
        "Telefone": _extract_list_field(phones, "number"),
        "Site": r.get("site", ""),
        "CNPJ": r.get("cnpj", ""),
        "Responsável (ID)": (r.get("responsible") or {}).get("id", ""),
        "Observações": r.get("notes", ""),
        "Data Criação": _fmt_date(r.get("dateCreated")),
    }


def normalize_activity(r: dict) -> dict:
    return {
        "ID": r.get("id", ""),
        "Título": r.get("title", ""),
        "Tipo": r.get("type", ""),
        "Status": r.get("status", ""),
        "Responsável (ID)": (r.get("responsible") or {}).get("id", ""),
        "Negócio (ID)": (r.get("deal") or {}).get("id", ""),
        "Contato (ID)": (r.get("contact") or {}).get("id", ""),
        "Data": _fmt_date(r.get("date")),
        "Data Criação": _fmt_date(r.get("dateCreated")),
        "Observações": r.get("notes", ""),
    }


NORMALIZERS = {
    "contact":  normalize_contact,
    "deal":     normalize_deal,
    "company":  normalize_company,
    "activity": normalize_activity,
}

ALLOWED_FILTER_PARAMS = {
    "deal":     {"status", "responsible_id", "stage_id", "origin"},
    "contact":  {"responsible_id", "origin"},
    "company":  {"responsible_id", "origin"},
    "activity": {"responsible_id", "status", "type"},
}

MAX_EXPORT_RECORDS = 100_000


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
        storage_dir = Path(settings.STORAGE_LOCAL_PATH).resolve()
        file_path = Path(export.output_file_path).resolve()
        if not str(file_path).startswith(str(storage_dir)):
            raise AppException(status_code=403, error_code="FORBIDDEN", detail="Acesso negado")
        if not file_path.exists():
            raise AppException(status_code=410, error_code="FILE_EXPIRED", detail="Arquivo expirado ou removido")
        return str(file_path)

    async def process(self, export_id: uuid.UUID) -> None:
        # chamado via BackgroundTasks — roda apos o request ser fechado
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
                entity_type=export.entity_type,
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
            "contact":  "/v2/contacts",
            "company":  "/v2/companies",
            "activity": "/v2/activities",
        }
        endpoint = endpoints.get(entity_type, f"/v2/{entity_type}s")

        records: list[dict] = []
        start = 0
        page_size = 100  # Moskit retorna no máx ~10 por chamada mas aceita start como offset

        allowed = ALLOWED_FILTER_PARAMS.get(entity_type, set())
        safe_filters = {k: v for k, v in filter_config.items() if k in allowed}

        async with httpx.AsyncClient(timeout=settings.MOSKIT_API_TIMEOUT) as client:
            while True:
                if len(records) >= MAX_EXPORT_RECORDS:
                    break
                params: dict = {"start": start, **safe_filters}
                try:
                    resp = await client.get(
                        f"{base_url}{endpoint}",
                        headers={"apikey": api_key, "Content-Type": "application/json"},
                        params=params,
                    )
                except httpx.ConnectError:
                    raise ValueError(
                        f"DNS/conexao falhou para '{base_url}'. "
                        "Verifique a Base URL da conexao no cadastro."
                    )
                except httpx.TimeoutException:
                    raise ValueError(f"Timeout ao conectar em '{base_url}'")
                if resp.status_code >= 400:
                    raise ValueError(f"Moskit API HTTP {resp.status_code}: {resp.text[:300]}")

                data = resp.json()
                batch = data if isinstance(data, list) else data.get("items", data.get("data", []))
                if not batch:
                    break
                records.extend(batch)

                # Moskit informa total real no header
                total = int(resp.headers.get("x-moskit-listing-total", 0))
                if total and len(records) >= total:
                    break

                # Para quando retorna menos que o esperado (última página)
                batch_size = int(resp.headers.get("x-moskit-listing-quantity", len(batch)))
                start += batch_size
                if batch_size == 0:
                    break

        return records

    def _generate_file(
        self,
        records: list[dict],
        entity_type: str,
        output_format: str,
        export_id: uuid.UUID,
        columns: list[str] | None = None,
    ) -> tuple[str, str]:
        storage_dir = Path(settings.STORAGE_LOCAL_PATH).resolve()
        storage_dir.mkdir(parents=True, exist_ok=True)

        file_name = f"export_{export_id}.{output_format}"
        file_path = storage_dir / file_name

        # path traversal guard — resolve para expandir symlinks antes de comparar
        if not str(file_path.resolve()).startswith(str(storage_dir)):
            raise ValueError("Path traversal detectado: caminho fora do diretório de storage")

        normalizer = NORMALIZERS.get(entity_type)
        normalized = [normalizer(r) for r in records] if normalizer else records

        if output_format == "csv":
            if not normalized:
                fieldnames = columns or []
            else:
                fieldnames = list(columns) if columns else list(normalized[0].keys())
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(normalized)

        elif output_format == "json":
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(normalized, f, ensure_ascii=False, indent=2, default=str)

        elif output_format == "xlsx":
            df = pd.DataFrame(normalized)
            if columns:
                existing = [c for c in columns if c in df.columns]
                df = df[existing] if existing else df
            df.to_excel(str(file_path), index=False, engine="openpyxl")  # datas ja formatadas pelo normalizer

        return str(file_path), file_name

    @staticmethod
    def _flatten(record: dict, parent_key: str = "", sep: str = ".") -> dict:
        """Flatten aninhado — usado apenas para entidades sem normalizer."""
        items: list = []
        for k, v in record.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(ExportService._flatten(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
