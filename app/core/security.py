import base64
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


# Senha
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# JWT
def create_access_token(payload: dict[str, Any]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    data = {**payload, "exp": expire, "type": "access"}
    return jwt.encode(data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token() -> str:
    # token opaco (nao JWT) — nao decodificavel, apenas comparado no banco
    return secrets.token_urlsafe(64)


def decode_access_token(token: str) -> dict[str, Any]:
    # levanta JWTError se invalido ou expirado — controller trata e retorna 401
    payload = jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
    if payload.get("type") != "access":
        raise JWTError("Tipo de token invalido")
    return payload


# AES-256-GCM para API keys em repouso
def _get_encryption_key() -> bytes:
    key = base64.b64decode(settings.APP_ENCRYPTION_KEY)
    if len(key) != 32:
        raise ValueError("APP_ENCRYPTION_KEY deve ter exatamente 32 bytes apos decodificacao")
    return key


def encrypt_secret(plaintext: str) -> bytes:
    # retorna nonce (12 bytes) + ciphertext+tag — salvar blob completo na coluna BYTEA
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ciphertext


def decrypt_secret(blob: bytes) -> str:
    # levanta InvalidTag se blob corrompido ou chave errada
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce, ciphertext = blob[:12], blob[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
