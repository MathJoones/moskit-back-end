import uuid
from datetime import datetime, timezone

from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app.models.user import User, UserSession
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_all_active(self, skip: int = 0, limit: int = 20) -> list[User]:
        return (
            self.db.query(User)
            .filter(User.deleted_at.is_(None))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_email(self, email: str) -> User | None:
        return (
            self.db.query(User)
            .filter(User.email == email, User.deleted_at.is_(None))
            .first()
        )

    def get_active(self, user_id: uuid.UUID) -> User | None:
        return (
            self.db.query(User)
            .filter(User.id == user_id, User.deleted_at.is_(None), User.status == "active")
            .first()
        )

    def soft_delete(self, user: User) -> User:
        user.deleted_at = datetime.now(timezone.utc)
        return self.update(user)

    def increment_failed_attempts(self, user: User) -> User:
        self.db.execute(
            sa_update(User)
            .where(User.id == user.id)
            .values(failed_attempts=User.failed_attempts + 1)
        )
        self.db.commit()
        self.db.refresh(user)
        return user

    def reset_failed_attempts(self, user: User) -> User:
        user.failed_attempts = 0
        user.locked_until = None
        return self.update(user)


class SessionRepository(BaseRepository[UserSession]):
    def __init__(self, db: Session):
        super().__init__(UserSession, db)

    def get_valid_session(self, refresh_token: str) -> UserSession | None:
        return (
            self.db.query(UserSession)
            .filter(
                UserSession.refresh_token == refresh_token,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > datetime.now(timezone.utc),
            )
            .first()
        )

    def revoke(self, session: UserSession) -> UserSession:
        session.revoked_at = datetime.now(timezone.utc)
        return self.update(session)

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        now = datetime.now(timezone.utc)
        (
            self.db.query(UserSession)
            .filter(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .update({"revoked_at": now})
        )
        self.db.commit()
