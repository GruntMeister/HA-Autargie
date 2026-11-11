"""aiohttp-Client für die lokale sonnenBatterie API v2."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import (
    API_PATH,
    API_TIMEOUT,
    FIELD_CONSUMPTION_W,
    FIELD_GRID_FEED_IN_W,
    FIELD_PAC_TOTAL_W,
    FIELD_PRODUCTION_W,
)


class SonnenApiError(Exception):
    """Zentraler Fehler: Netzwerk, Timeout oder HTTP-Status != 200."""


class SonnenAuthError(SonnenApiError):
    """Authentifizierung fehlgeschlagen (HTTP 401/403)."""


REQUIRED_NUMERIC_FIELDS = (
    FIELD_CONSUMPTION_W,
    FIELD_GRID_FEED_IN_W,
    FIELD_PAC_TOTAL_W,
    FIELD_PRODUCTION_W,
)


class SonnenApiClient:
    """Minimaler Client für GET /api/v2/status."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        token: str,
        timeout: int = API_TIMEOUT,
    ) -> None:
        self._session = session
        self._url = f"http://{host}{API_PATH}"
        self._headers = {"Auth-Token": token}
        self._timeout = timeout

    async def async_get_status(self) -> dict[str, Any]:
        """Liefert den Status-Datensatz oder wirft SonnenApiError/SonnenAuthError."""
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.get(self._url, headers=self._headers) as resp:
                    if resp.status in (401, 403):
                        raise SonnenAuthError(
                            f"Authentifizierung fehlgeschlagen (HTTP {resp.status})"
                        )
                    if resp.status != 200:
                        raise SonnenApiError(f"Unerwarteter HTTP-Status {resp.status}")
                    data = await resp.json(content_type=None)
        except SonnenApiError:
            raise
        except (TimeoutError, aiohttp.ClientError) as err:
            raise SonnenApiError(f"API nicht erreichbar: {err}") from err

        if not isinstance(data, dict):
            raise SonnenApiError("Antwort ist kein JSON-Objekt")
        for field in REQUIRED_NUMERIC_FIELDS:
            value = data.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise SonnenApiError(f"Feld '{field}' fehlt oder ist nicht numerisch")
        return data
