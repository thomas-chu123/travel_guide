from secrets import compare_digest
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.services.supabase import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/supabase")


class SupabaseWriteResult(BaseModel):
    data: Any


def require_admin(
    x_supabase_admin_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.supabase_admin_token:
        raise HTTPException(status_code=503, detail="Supabase admin API is not configured")
    if not x_supabase_admin_token or not compare_digest(
        x_supabase_admin_token, settings.supabase_admin_token
    ):
        raise HTTPException(status_code=401, detail="Invalid Supabase admin token")


def get_client(settings: Settings = Depends(get_settings)) -> SupabaseRestClient:
    if not settings.supabase_public_url or not settings.supabase_secret_key:
        raise HTTPException(status_code=503, detail="Supabase REST client is not configured")
    return SupabaseRestClient(settings.supabase_public_url, settings.supabase_secret_key)


def require_allowed_table(table: str, settings: Settings) -> None:
    if table not in settings.supabase_allowed_tables:
        raise HTTPException(status_code=404, detail="Supabase table is not enabled")


def filters_from(request: Request) -> dict[str, str]:
    return {key: value for key, value in request.query_params.items() if key != "select"}


async def execute(operation: Any) -> Any:
    try:
        return await operation
    except SupabaseRestError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/health", dependencies=[Depends(require_admin)])
async def supabase_health(client: SupabaseRestClient = Depends(get_client)) -> dict[str, Any]:
    return await execute(client.check_connection())


@router.get("/{table}", dependencies=[Depends(require_admin)])
async def select_rows(
    table: str,
    request: Request,
    settings: Settings = Depends(get_settings),
    client: SupabaseRestClient = Depends(get_client),
) -> SupabaseWriteResult:
    require_allowed_table(table, settings)
    return SupabaseWriteResult(data=await execute(client.request("GET", table, params=request.query_params)))


@router.post("/{table}", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def insert_rows(
    table: str,
    payload: dict[str, Any] | list[dict[str, Any]],
    settings: Settings = Depends(get_settings),
    client: SupabaseRestClient = Depends(get_client),
) -> SupabaseWriteResult:
    require_allowed_table(table, settings)
    return SupabaseWriteResult(
        data=await execute(client.request("POST", table, body=payload, prefer="return=representation"))
    )


@router.patch("/{table}", dependencies=[Depends(require_admin)])
async def update_rows(
    table: str,
    payload: dict[str, Any],
    request: Request,
    settings: Settings = Depends(get_settings),
    client: SupabaseRestClient = Depends(get_client),
) -> SupabaseWriteResult:
    require_allowed_table(table, settings)
    filters = filters_from(request)
    if not filters:
        raise HTTPException(status_code=422, detail="PATCH requires at least one PostgREST filter")
    return SupabaseWriteResult(
        data=await execute(
            client.request("PATCH", table, params=filters, body=payload, prefer="return=representation")
        )
    )


@router.delete("/{table}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_rows(
    table: str,
    request: Request,
    settings: Settings = Depends(get_settings),
    client: SupabaseRestClient = Depends(get_client),
) -> Response:
    require_allowed_table(table, settings)
    filters = filters_from(request)
    if not filters:
        raise HTTPException(status_code=422, detail="DELETE requires at least one PostgREST filter")
    await execute(client.request("DELETE", table, params=filters, prefer="return=minimal"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
