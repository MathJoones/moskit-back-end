import ipaddress
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import UnauthorizedError, AccountLockedError, ConflictError
from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
)
from app.models.user import User, UserSession
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.user_repository import UserRepository, SessionRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


def _sanitize_ip(ip: str | None) -> str | None:
    """Valida IP antes de persistir em coluna INET. Retorna None se inválido."""
    if not ip:
        return None
    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        return None


class AuthService:
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)
        self.session_repo = SessionRepository(db)
        self.audit = AuditLogRepository(db)

    def register(self, data: RegisterRequest, ip: str | None, user_agent: str | None) -> TokenResponse:
        if self.user_repo.get_by_email(data.email):
            raise ConflictError("E-mail ja cadastrado")

        user = User(
            email=data.email,
            full_name=data.full_name,
            password_hash=hash_password(data.password),
            role="operator",
        )
        self.user_repo.create(user)

        self.audit.log(
            action="create",
            user_id=user.id,
            entity_type="user",
            entity_id=str(user.id),
            new_value={"email": user.email, "full_name": user.full_name, "role": user.role},
            ip_address=_sanitize_ip(ip),
            user_agent=user_agent,
        )

        access_token = create_access_token({"sub": str(user.id), "email": user.email})
        refresh_token = create_refresh_token()

        session = UserSession(
            user_id=user.id,
            refresh_token=refresh_token,
            ip_address=_sanitize_ip(ip),
            user_agent=user_agent,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            created_at=datetime.now(timezone.utc),
        )
        self.session_repo.create(session)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def login(self, data: LoginRequest, ip: str | None, user_agent: str | None) -> TokenResponse:
        user = self.user_repo.get_by_email(data.email)

        if not user:
            raise UnauthorizedError()

        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            raise AccountLockedError()

        if not verify_password(data.password, user.password_hash):
            self.user_repo.increment_failed_attempts(user)
            if user.failed_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.ACCOUNT_LOCKOUT_MINUTES
                )
                self.user_repo.update(user)
            raise UnauthorizedError()

        self.user_repo.reset_failed_attempts(user)
        user.last_login_at = datetime.now(timezone.utc)
        self.user_repo.update(user)

        self.audit.log(
            action="login",
            user_id=user.id,
            entity_type="user",
            entity_id=str(user.id),
            ip_address=_sanitize_ip(ip),
            user_agent=user_agent,
        )

        access_token = create_access_token({"sub": str(user.id), "email": user.email})
        refresh_token = create_refresh_token()

        session = UserSession(
            user_id=user.id,
            refresh_token=refresh_token,
            ip_address=_sanitize_ip(ip),
            user_agent=user_agent,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            created_at=datetime.now(timezone.utc),
        )
        self.session_repo.create(session)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def logout(self, refresh_token: str) -> None:
        session = self.session_repo.get_valid_session(refresh_token)
        if session:
            self.audit.log(
                action="logout",
                user_id=session.user_id,
                entity_type="user",
                entity_id=str(session.user_id),
            )
            self.session_repo.revoke(session)

    def refresh(self, refresh_token: str) -> dict:
        session = self.session_repo.get_valid_session(refresh_token)
        if not session:
            raise UnauthorizedError("Refresh token invalido ou expirado")

        user = self.user_repo.get_active(session.user_id)
        if not user:
            raise UnauthorizedError()

        access_token = create_access_token({"sub": str(user.id), "email": user.email})
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
