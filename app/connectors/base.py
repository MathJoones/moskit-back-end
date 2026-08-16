# Interface base para todos os conectores de API externa
from abc import ABC, abstractmethod

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.schemas.api_connection import ConnectionTestResponse


def _is_retryable(exc: BaseException) -> bool:
    """Retenta apenas erros de rede e respostas 5xx. 4xx são erros do cliente — não retentar."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError))


class BaseConnector(ABC):
    def __init__(self, connection):
        self.connection = connection
        self.timeout = settings.MOSKIT_API_TIMEOUT

    @abstractmethod
    async def test(self) -> ConnectionTestResponse:
        # testa conectividade com a API externa
        ...

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError)),
    )
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
