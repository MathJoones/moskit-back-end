import uuid
from math import ceil

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ConflictError
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repository import UserRepository, SessionRepository
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)
        self.session_repo = SessionRepository(db)

    def list_users(self, skip: int = 0, limit: int = 20) -> list[User]:
        return self.repo.get_all(skip=skip, limit=limit)

    def get_user(self, user_id: uuid.UUID) -> User:
        user = self.repo.get_by_id(user_id)
        if not user or user.deleted_at is not None:
            raise NotFoundError("User", str(user_id))
        return user

    def create_user(self, data: UserCreate) -> User:
        if self.repo.get_by_email(data.email):
            raise ConflictError("E-mail ja cadastrado")
        user = User(
            email=data.email,
            full_name=data.full_name,
            password_hash=hash_password(data.password),
            role=data.role,
        )
        return self.repo.create(user)

    def update_user(self, user_id: uuid.UUID, data: UserUpdate) -> User:
        user = self.get_user(user_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(user, field, value)
        return self.repo.update(user)

    def delete_user(self, user_id: uuid.UUID) -> None:
        user = self.get_user(user_id)
        # Revogar todas as sessoes ativas antes de soft delete (LGPD)
        self.session_repo.revoke_all_for_user(user_id)
        self.repo.soft_delete(user)
