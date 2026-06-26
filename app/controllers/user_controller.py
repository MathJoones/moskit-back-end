import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError, ConflictError
from app.core.security import hash_password
from app.middleware.auth import require_admin
from app.models.user import User
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.user_repository import UserRepository, SessionRepository
from app.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter()


@router.get("", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 20,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return UserRepository(db).get_all(skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user or user.is_deleted:
        raise NotFoundError("User", str(user_id))
    return user


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    data: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    repo = UserRepository(db)
    if repo.get_by_email(data.email):
        raise ConflictError("E-mail ja cadastrado")
    user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    repo.create(user)

    AuditLogRepository(db).log(
        action="create",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(user.id),
        new_value={"email": user.email, "full_name": user.full_name, "role": user.role},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    request: Request,
    user_id: uuid.UUID,
    data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user or user.is_deleted:
        raise NotFoundError("User", str(user_id))

    old_value = {"full_name": user.full_name, "role": user.role, "status": user.status}
    changes = data.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(user, field, value)
    repo.update(user)

    AuditLogRepository(db).log(
        action="update",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(user_id),
        old_value=old_value,
        new_value=changes,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    request: Request,
    user_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user or user.is_deleted:
        raise NotFoundError("User", str(user_id))

    SessionRepository(db).revoke_all_for_user(user_id)
    repo.soft_delete(user)

    AuditLogRepository(db).log(
        action="delete",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(user_id),
        old_value={"email": user.email, "role": user.role},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
