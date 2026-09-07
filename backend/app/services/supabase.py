from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx


class SupabaseRestError(Exception):
    """An unsuccessful response from the Supabase REST API."""

    def __init__(self, status_code: int, detail: object) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Supabase REST request failed with status {status_code}")


class SupabaseRestClient:
    """Small PostgREST client that keeps the Supabase secret on the backend."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "TokyoEventMapBackend/1.0",
        }

    async def request(
        self,
        method: str,
        table: str,
        *,
        params: Mapping[str, str] | None = None,
        body: Any = None,
        prefer: str | None = None,
        profile: str | None = None,
    ) -> Any:
        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer
        if profile:
            headers["Accept-Profile"] = profile
            if method in {"POST", "PATCH", "DELETE"}:
                headers["Content-Profile"] = profile
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(
                method,
                f"{self._base_url}/{quote(table, safe='')}",
                params=params,
                json=body,
                headers=headers,
            )
        if response.is_error:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise SupabaseRestError(response.status_code, detail)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    async def check_connection(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(self._base_url + "/", headers=self._headers)
        if response.is_error:
            try:
                detail: object = response.json()
            except ValueError:
                detail = response.text
            raise SupabaseRestError(response.status_code, detail)
        document = response.json()
        return {"connected": True, "api_version": document.get("info", {}).get("version")}
