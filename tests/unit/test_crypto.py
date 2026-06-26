import base64
import os
import pytest
from unittest.mock import patch


def make_key():
    return base64.b64encode(os.urandom(32)).decode()


class TestCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        key = make_key()
        with patch.dict("os.environ", {"APP_ENCRYPTION_KEY": key}):
            # Reimportar com nova key
            import importlib
            import app.core.config as cfg
            cfg.get_settings.cache_clear()

            from app.core.security import encrypt_secret, decrypt_secret
            plaintext = "minha_api_key_secreta_123"
            blob = encrypt_secret(plaintext)
            assert isinstance(blob, bytes)
            assert len(blob) > 12  # nonce (12) + ciphertext
            recovered = decrypt_secret(blob)
            assert recovered == plaintext

    def test_different_nonces(self):
        key = make_key()
        with patch.dict("os.environ", {"APP_ENCRYPTION_KEY": key}):
            import app.core.config as cfg
            cfg.get_settings.cache_clear()
            from app.core.security import encrypt_secret
            blob1 = encrypt_secret("mesma_string")
            blob2 = encrypt_secret("mesma_string")
            # Nonces diferentes = blobs diferentes (AES-GCM com nonce aleatorio)
            assert blob1 != blob2

    def test_plaintext_not_in_blob(self):
        key = make_key()
        with patch.dict("os.environ", {"APP_ENCRYPTION_KEY": key}):
            import app.core.config as cfg
            cfg.get_settings.cache_clear()
            from app.core.security import encrypt_secret
            secret = "super_secret_api_key"
            blob = encrypt_secret(secret)
            assert secret.encode() not in blob
