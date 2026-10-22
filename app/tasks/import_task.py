"""
Task Celery: process_import(import_id)

Fluxo por linha:
  1. MappingEngine.process(raw_row) → dict transformado
  2. Se dedup ativo → search na Moskit API
  3. Se não duplicata → create na Moskit API (POST /v2/{entity}s)
  4. Atualiza ImportRow com status, moskit_id ou error_message
  5. Atualiza progresso no ImportJob a cada lote

Trata HTTP 429: lê Retry-After, aguarda, reprocessa (max 3 tentativas por linha).
"""
import asyncio
import time
import uuid
from datetime import datetime, UTC
from pathlib import Path

from celery import Task

from app.worker import celery_app
from app.core.database import SessionLocal
from app.core.security import decrypt_secret
from app.core.config import settings
from app.mappings.engine import MappingEngine, MappingValidationError
from app.models.import_row import ImportRow
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.field_mapping_repository import FieldMappingGroupRepository
from app.repositories.import_repository import ImportRepository
from app.repositories.import_row_repository import ImportRowRepository

import httpx

BATCH_SIZE = 50          # linhas por lote antes de atualizar progresso
MAX_RETRIES = 3          # tentativas por linha em caso de 429

ENTITY_CREATE_ENDPOINTS = {
    "contact": "/v2/contacts",
    "company": "/v2/companies",
    "deal":    "/v2/deals",
}

ENTITY_SEARCH_ENDPOINTS = {
    "contact": "/v2/contacts/search",
    "company": "/v2/companies/search",
    "deal":    "/v2/deals/search",
}


def _parse_file(file_path: str, filename: str) -> list[dict]:
    """Reutiliza lógica do ImportService sem instanciar o service."""
    import csv, io, pandas as pd
    file_bytes = Path(file_path).read_bytes()
    ext = Path(filename).suffix.lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0, dtype=str)
        df = df.fillna("")
        return df.to_dict(orient="records")
    text = file_bytes.decode("utf-8-sig", errors="replace")
    dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    return [dict(row) for row in reader]


def _sync_post(client: httpx.Client, url: str, headers: dict, payload: dict, retry: int = 0) -> dict:
    """
    POST síncrono com tratamento de 429.
    Retorna dict da resposta ou lança httpx.HTTPStatusError.
    """
    resp = client.post(url, headers=headers, json=payload)

    if resp.status_code == 429 and retry < MAX_RETRIES:
        wait = int(resp.headers.get("Retry-After", 5))
        time.sleep(wait)
        return _sync_post(client, url, headers, payload, retry + 1)

    resp.raise_for_status()
    return resp.json()


def _sync_search(client: httpx.Client, url: str, headers: dict, payload: dict) -> list:
    """Busca deduplicação — retorna lista de resultados."""
    resp = client.post(url, headers=headers, json=payload)
    if resp.status_code >= 400:
        return []
    data = resp.json()
    return data if isinstance(data, list) else data.get("items", data.get("data", []))


@celery_app.task(bind=True, name="app.tasks.import_task.process_import")
def process_import(self: Task, import_id: str) -> dict:
    """
    Worker principal de importação.
    Retorna dict com contagens finais.
    """
    job_id = uuid.UUID(import_id)
    db = SessionLocal()

    try:
        import_repo = ImportRepository(db)
        row_repo = ImportRowRepository(db)
        conn_repo = ConnectionRepository(db)
        group_repo = FieldMappingGroupRepository(db)

        job = import_repo.get_active(job_id)
        if not job:
            return {"error": "Import não encontrado"}

        import_repo.update_status(job_id, "processing", started_at=datetime.now(UTC))

        # Carrega dependências
        connection = conn_repo.get_by_id(job.connection_id)
        group = group_repo.get_active(job.mapping_group_id)

        if not connection or not group:
            import_repo.update_status(
                job_id, "error",
                error_message="Conexão ou FieldMappingGroup não encontrado",
                completed_at=datetime.now(UTC),
            )
            return {"error": "Dependências não encontradas"}

        api_key = decrypt_secret(connection.api_key_enc) if connection.api_key_enc else ""
        base_url = connection.base_url or settings.MOSKIT_API_BASE_URL
        headers = {"apikey": api_key, "Content-Type": "application/json"}

        create_url = base_url + ENTITY_CREATE_ENDPOINTS[job.entity_type]
        search_url = base_url + ENTITY_SEARCH_ENDPOINTS.get(job.entity_type, "")

        engine = MappingEngine(group)
        raw_rows = _parse_file(job.input_file_path, job.input_file_name or "file.csv")

        counters = {"processed": 0, "created": 0, "duplicates": 0, "errors": 0}

        with httpx.Client(timeout=settings.MOSKIT_API_TIMEOUT) as client:
            for i, raw_row in enumerate(raw_rows, start=1):
                row_status = "error"
                moskit_id = None
                error_msg = None
                retry_count = 0

                try:
                    transformed = engine.process(raw_row)

                    # Deduplicação
                    if group.dedup_enabled and group.dedup_keys and search_url:
                        dedup_keys: list = group.dedup_keys if isinstance(group.dedup_keys, list) else []
                        search_payload = {
                            k: transformed[k] for k in dedup_keys if k in transformed
                        }
                        if search_payload:
                            results = _sync_search(client, search_url, headers, search_payload)
                            if results:
                                moskit_id = str(results[0].get("id", ""))
                                row_status = "duplicate"
                                counters["duplicates"] += 1

                    if row_status != "duplicate":
                        # Deals precisam de origem fixada conforme spec
                        if job.entity_type == "deal":
                            transformed.setdefault("origin", "MOSKIT_API_V2")

                        resp_data = _sync_post(client, create_url, headers, transformed)
                        moskit_id = str(resp_data.get("id", ""))
                        row_status = "created"
                        counters["created"] += 1

                except MappingValidationError as exc:
                    error_msg = str(exc)
                    counters["errors"] += 1

                except httpx.HTTPStatusError as exc:
                    retry_count = MAX_RETRIES if exc.response.status_code == 429 else 0
                    error_msg = f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
                    counters["errors"] += 1

                except Exception as exc:
                    error_msg = str(exc)
                    counters["errors"] += 1

                counters["processed"] += 1

                # Persiste ImportRow
                import_row = ImportRow(
                    import_id=job_id,
                    row_number=i,
                    raw_data=raw_row,
                    status=row_status,
                    moskit_id=moskit_id,
                    error_message=error_msg,
                    retry_count=retry_count,
                )
                db.add(import_row)

                # Atualiza progresso a cada lote
                if i % BATCH_SIZE == 0 or i == len(raw_rows):
                    db.commit()
                    pct = round((counters["processed"] / len(raw_rows)) * 100, 2) if raw_rows else 0
                    import_repo.update_progress(
                        job_id,
                        processed=counters["processed"],
                        created=counters["created"],
                        duplicates=counters["duplicates"],
                        errors=counters["errors"],
                        progress_pct=pct,
                    )

        import_repo.update_status(
            job_id, "completed", completed_at=datetime.now(UTC)
        )
        return counters

    except Exception as exc:
        try:
            import_repo = ImportRepository(db)
            import_repo.update_status(
                job_id, "error",
                error_message=str(exc),
                completed_at=datetime.now(UTC),
            )
        except Exception:
            pass
        raise

    finally:
        db.close()
