"""
MoskitConnector — wrapper da API Moskit CRM.
Documentacao: https://moskit.com.br/api
"""
import time

import httpx

from app.connectors.base import BaseConnector
from app.core.security import decrypt_secret
from app.schemas.api_connection import ConnectionTestResponse


class MoskitConnector(BaseConnector):
    def __init__(self, connection):
        super().__init__(connection)
        self._api_key: str | None = None

    def _get_api_key(self) -> str:
        if self._api_key is None and self.connection.api_key_enc:
            self._api_key = decrypt_secret(self.connection.api_key_enc)
        return self._api_key or ""

    def _headers(self) -> dict:
        return {
            "apikey": self._get_api_key(),
            "Content-Type": "application/json",
        }

    async def test(self) -> ConnectionTestResponse:
        base_url = self.connection.base_url or "https://api.moskitcrm.com"
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{base_url}/v2/deals",
                    headers=self._headers(),
                    params={"limit": 1},
                )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            ok = resp.status_code < 400
            return ConnectionTestResponse(
                ok=ok,
                message="Conexao bem-sucedida" if ok else f"HTTP {resp.status_code}: verifique a API Key",
                latency_ms=elapsed_ms,
            )
        except httpx.ConnectError:
            return ConnectionTestResponse(
                ok=False,
                message=f"DNS/conexao falhou para '{base_url}'. Verifique a Base URL da conexao.",
            )
        except httpx.TimeoutException:
            return ConnectionTestResponse(ok=False, message=f"Timeout ao conectar em '{base_url}'")
        except Exception as e:
            return ConnectionTestResponse(ok=False, message=str(e))

    async def list_deals(self, params: dict | None = None) -> dict:
        base_url = self.connection.base_url or "https://api.moskitcrm.com"
        response = await self._request(
            "GET", f"{base_url}/v2/deals", headers=self._headers(), params=params or {}
        )
        return response.json()

    async def create_deal(self, payload: dict) -> dict:
        base_url = self.connection.base_url or "https://api.moskitcrm.com"
        response = await self._request(
            "POST", f"{base_url}/v2/deals", headers=self._headers(), json=payload
        )
        return response.json()
