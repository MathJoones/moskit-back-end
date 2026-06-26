"""
BaseConnector — interface para todos os conectores de API externa.
"""
from abc import ABC, abstractmethod

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.schemas.api_connection import ConnectionTestResponse


class BaseConnector(ABC):
    def __init__(self, connection):
        self.connection = connection
        self.timeout = 30

    @abstractmethod
    async def test(self) -> ConnectionTestResponse:
        """Testa conectividade com a API."""
        ...

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _request(
        self,
        method: str,
        url: str,
        headers: dict,
        **kwargs,
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response
