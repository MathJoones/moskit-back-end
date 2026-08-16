import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator, AnyHttpUrl


VALID_CONNECTION_TYPES = {"moskit", "external_api", "csv", "xlsx", "database"}


class ConnectionCreate(BaseModel):
    name: str
    description: str | None = None
    connection_type: str
    base_url: AnyHttpUrl | None = None
    api_key: str | None = None       # plaintext — criptografado antes de persistir
    api_secret: str | None = None    # plaintext — criptografado antes de persistir
    extra_config: dict | None = None

    @field_validator("connection_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_CONNECTION_TYPES:
            raise ValueError(f"Tipo invalido. Validos: {VALID_CONNECTION_TYPES}")
        return v


class ConnectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    base_url: AnyHttpUrl | None = None
    api_key: str | None = None
    api_secret: str | None = None
    extra_config: dict | None = None
    is_active: bool | None = None


class ConnectionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    connection_type: str
    base_url: str | None
    is_active: bool
    last_tested_at: datetime | None
    last_test_ok: bool | None
    created_at: datetime
    # api_key/api_secret NUNCA retornados aqui


class ConnectionTestResponse(BaseModel):
    ok: bool
    message: str
    latency_ms: int | None = None
