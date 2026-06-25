from __future__ import annotations

import logging
import json
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class GHLClientError(Exception):
    pass


class GHLClient:
    def __init__(self, token: str) -> None:
        settings = get_settings()
        self.token = token.strip()
        self.base_url = settings.ghl_base_url.rstrip('/')
        self.api_version = settings.ghl_api_version

    def _headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Version': self.api_version,
        }

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=40) as client:
                response = await client.get(url, headers=self._headers(), params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.exception('Erro HTTP GHL: %s', exc.response.text)
            raise GHLClientError(self._format_error(exc.response)) from exc
        except httpx.RequestError as exc:
            logger.exception('Erro de conexão com GHL')
            raise GHLClientError('Falha de conexão com GHL') from exc

    def _format_error(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = {}

        message = payload.get('message') or response.text
        if response.status_code == 401:
            return 'Token GHL invalido ou expirado.'
        if response.status_code == 403 and 'does not have access to this location' in message:
            return 'Token GHL nao tem acesso a este Location ID. Libere esta subconta no Private Integration ou use o token correto da location.'
        return f'GHL retornou {response.status_code}: {message}'
