import uuid
from math import ceil

from sqlalchemy.orm import Session

from app.connectors.moskit import MoskitConnector
from app.core.exceptions import NotFoundError, ConflictError
from app.core.security import encrypt_secret
from app.models.api_connection import ApiConnection
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.api_connection import (
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionTestResponse,
)


class ConnectionService:
    def __init__(self, db: Session):
        self.repo = ConnectionRepository(db)

    def list_connections(self, skip: int = 0, limit: int = 20) -> dict:
        items, total = self.repo.get_all_active(skip=skip, limit=limit)
        return {
            "items": items,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def get_connection(self, conn_id: uuid.UUID) -> ApiConnection:
        conn = self.repo.get_by_id(conn_id)
        if not conn or conn.deleted_at is not None:
            raise NotFoundError("Connection", str(conn_id))
        return conn

    def create_connection(
        self, data: ConnectionCreate, created_by: uuid.UUID
    ) -> ApiConnection:
        conn = ApiConnection(
            name=data.name,
            description=data.description,
            connection_type=data.connection_type,
            base_url=data.base_url,
            extra_config=data.extra_config,
            created_by=created_by,
            api_key_enc=encrypt_secret(data.api_key) if data.api_key else None,
            api_secret_enc=encrypt_secret(data.api_secret) if data.api_secret else None,
        )
        return self.repo.create(conn)

    def update_connection(
        self, conn_id: uuid.UUID, data: ConnectionUpdate
    ) -> ApiConnection:
        conn = self.get_connection(conn_id)
        for field, value in data.model_dump(exclude_none=True).items():
            if field == "api_key":
                conn.api_key_enc = encrypt_secret(value) if value else None
            elif field == "api_secret":
                conn.api_secret_enc = encrypt_secret(value) if value else None
            else:
                setattr(conn, field, value)
        return self.repo.update(conn)

    def delete_connection(self, conn_id: uuid.UUID) -> None:
        conn = self.get_connection(conn_id)
        self.repo.soft_delete(conn)

    async def test_connection(self, conn_id: uuid.UUID) -> ConnectionTestResponse:
        conn = self.get_connection(conn_id)
        connector = MoskitConnector(conn)
        result = await connector.test()
        self.repo.update_test_result(conn, result.ok)
        return result
