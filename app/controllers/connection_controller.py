import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.security import encrypt_secret
from app.middleware.auth import get_current_user, require_admin
from app.models.api_connection import ApiConnection
from app.models.user import User
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.api_connection import (
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionResponse,
    ConnectionTestResponse,
)
from app.connectors.moskit import MoskitConnector

router = APIRouter()


@router.get("", response_model=list[ConnectionResponse])
async def list_connections(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, _ = ConnectionRepository(db).get_all_active(skip=skip, limit=limit)
    return items


@router.get("/{conn_id}", response_model=ConnectionResponse)
async def get_connection(
    conn_id: uuid.UUID,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conn = ConnectionRepository(db).get_by_id(conn_id)
    if not conn or conn.is_deleted:
        raise NotFoundError("Connection", str(conn_id))
    return conn


@router.post("", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(
    request: Request,
    data: ConnectionCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    conn = ApiConnection(
        name=data.name,
        description=data.description,
        connection_type=data.connection_type,
        base_url=data.base_url,
        extra_config=data.extra_config,
        created_by=current_user.id,
        api_key_enc=encrypt_secret(data.api_key) if data.api_key else None,
        api_secret_enc=encrypt_secret(data.api_secret) if data.api_secret else None,
    )
    ConnectionRepository(db).create(conn)

    AuditLogRepository(db).log(
        action="create",
        user_id=current_user.id,
        entity_type="connection",
        entity_id=str(conn.id),
        new_value={"name": conn.name, "connection_type": conn.connection_type, "base_url": conn.base_url},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return conn


@router.patch("/{conn_id}", response_model=ConnectionResponse)
async def update_connection(
    request: Request,
    conn_id: uuid.UUID,
    data: ConnectionUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    repo = ConnectionRepository(db)
    conn = repo.get_by_id(conn_id)
    if not conn or conn.is_deleted:
        raise NotFoundError("Connection", str(conn_id))

    old_value = {"name": conn.name, "is_active": conn.is_active, "base_url": conn.base_url}
    changes = {k: v for k, v in data.model_dump(exclude_none=True).items() if k not in ("api_key", "api_secret")}

    for field, value in data.model_dump(exclude_none=True).items():
        if field == "api_key":
            conn.api_key_enc = encrypt_secret(value) if value else None
        elif field == "api_secret":
            conn.api_secret_enc = encrypt_secret(value) if value else None
        else:
            setattr(conn, field, value)
    repo.update(conn)

    AuditLogRepository(db).log(
        action="update",
        user_id=current_user.id,
        entity_type="connection",
        entity_id=str(conn_id),
        old_value=old_value,
        new_value=changes,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return conn


@router.delete("/{conn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    request: Request,
    conn_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    repo = ConnectionRepository(db)
    conn = repo.get_by_id(conn_id)
    if not conn or conn.is_deleted:
        raise NotFoundError("Connection", str(conn_id))

    repo.soft_delete(conn)

    AuditLogRepository(db).log(
        action="delete",
        user_id=current_user.id,
        entity_type="connection",
        entity_id=str(conn_id),
        old_value={"name": conn.name, "connection_type": conn.connection_type},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/{conn_id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    conn_id: uuid.UUID,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = ConnectionRepository(db)
    conn = repo.get_by_id(conn_id)
    if not conn or conn.is_deleted:
        raise NotFoundError("Connection", str(conn_id))

    connector = MoskitConnector(conn)
    result = await connector.test()
    repo.update_test_result(conn, result.ok)
    return result
