from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.supabase import SupabaseRestClient


def test_supabase_read_requires_admin_token_and_uses_rest_client(monkeypatch) -> None:
    async def fake_request(self, method, table, **kwargs):
        assert method == "GET"
        assert table == "events"
        assert kwargs["params"]["id"] == "eq.1"
        return [{"id": 1, "title": "Tokyo"}]

    monkeypatch.setattr(SupabaseRestClient, "request", fake_request)
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
        supabase_admin_token="test-admin-token",
        supabase_public_url="https://supabase.example.test",
        supabase_secret_key="test-secret-key",
        supabase_allowed_tables={"events"},
    )
    try:
        with TestClient(app) as client:
            unauthorized = client.get("/api/v1/supabase/events")
            response = client.get(
                "/api/v1/supabase/events?id=eq.1",
                headers={"X-Supabase-Admin-Token": "test-admin-token"},
            )
    finally:
        app.dependency_overrides.clear()

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json() == {"data": [{"id": 1, "title": "Tokyo"}]}


def test_supabase_update_and_delete_require_filters() -> None:
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
        supabase_admin_token="test-admin-token",
        supabase_public_url="https://supabase.example.test",
        supabase_secret_key="test-secret-key",
        supabase_allowed_tables={"events"},
    )
    headers = {"X-Supabase-Admin-Token": "test-admin-token"}
    try:
        with TestClient(app) as client:
            update = client.patch("/api/v1/supabase/events", headers=headers, json={"title": "New"})
            delete = client.delete("/api/v1/supabase/events", headers=headers)
    finally:
        app.dependency_overrides.clear()

    assert update.status_code == 422
    assert delete.status_code == 422
