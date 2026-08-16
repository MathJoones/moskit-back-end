import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "operator"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "operator", "viewer"):
            raise ValueError("Role invalido. Validos: admin, operator, viewer")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Senha deve ter no minimo 8 caracteres")
        if not any(c.isupper() for c in v):
            raise ValueError("Senha deve ter ao menos uma letra maiuscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("Senha deve ter ao menos um numero")
        return v


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    status: str | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in ("admin", "operator", "viewer"):
            raise ValueError("Role invalido. Validos: admin, operator, viewer")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("active", "inactive", "suspended"):
            raise ValueError("Status invalido. Validos: active, inactive, suspended")
        return v


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    status: str
    last_login_at: datetime | None
    created_at: datetime
    # password_hash NUNCA incluido aqui
