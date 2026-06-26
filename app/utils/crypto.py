"""
Utilitarios de criptografia para arquivos e dados em transito.
Para criptografia de segredos em repouso (API keys), use app.core.security.
"""
import hashlib
import hmac
import os
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generate_key() -> str:
    """Gera chave AES-256 aleatoria, retorna como base64. Para uso em testes e setup."""
    return base64.b64encode(os.urandom(32)).decode()


def encrypt_file_bytes(data: bytes, key: bytes) -> bytes:
    """
    Criptografa bytes de arquivo com AES-256-GCM.
    Retorna: nonce (12 bytes) + ciphertext + tag.

    Uso: criptografar CSV/XLSX em storage local antes de salvar.
    """
    if len(key) != 32:
        raise ValueError("Chave deve ter exatamente 32 bytes")
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce + ciphertext


def decrypt_file_bytes(blob: bytes, key: bytes) -> bytes:
    """
    Decriptografa blob gerado por encrypt_file_bytes.
    Raises cryptography.exceptions.InvalidTag se corrompido ou chave errada.
    """
    if len(key) != 32:
        raise ValueError("Chave deve ter exatamente 32 bytes")
    if len(blob) < 13:
        raise ValueError("Blob invalido: menor que nonce (12 bytes) + 1 byte")
    aesgcm = AESGCM(key)
    nonce, ciphertext = blob[:12], blob[12:]
    return aesgcm.decrypt(nonce, ciphertext, None)


def compute_file_hash(data: bytes) -> str:
    """SHA-256 hex digest do conteudo. Usado para deduplicacao e integridade."""
    return hashlib.sha256(data).hexdigest()


def safe_compare(a: str, b: str) -> bool:
    """Comparacao em tempo constante para evitar timing attacks."""
    return hmac.compare_digest(a.encode(), b.encode())
