import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.api_connection import ApiConnection
from app.repositories.base import BaseRepository


class ConnectionRepository(BaseRepository[ApiConnection]):
    def __init__(self, db: Session):
        super().__init__(ApiConnection, db)

    def get_all_active(self, skip: int = 0, limit: int = 20) -> tuple[list[ApiConnection], int]:
        query = (
            self.db.query(ApiConnection)
            .filter(ApiConnection.deleted_at.is_(None), ApiConnection.is_active == True)
        )
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total

    def soft_delete(self, conn: ApiConnection) -> ApiConnection:
        conn.deleted_at = datetime.now(timezone.utc)
        return self.update(conn)

    def update_test_result(self, conn: ApiConnection, ok: bool) -> ApiConnection:
        conn.last_tested_at = datetime.now(timezone.utc)
        conn.last_test_ok = ok
        return self.update(conn)
