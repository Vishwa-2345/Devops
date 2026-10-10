"""Secret-exposure tests: a configured GitHub token must never leak via the API."""

from __future__ import annotations

from app.config import get_settings

SECRET_TOKEN = "ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


def _with_configured_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", SECRET_TOKEN)
    get_settings.cache_clear()


def test_settings_status_reports_configured_without_leaking_token(client, monkeypatch):
    _with_configured_token(monkeypatch)
    try:
        resp = client.get("/api/v1/settings/status")
        assert resp.status_code == 200
        assert SECRET_TOKEN not in resp.text

        data = resp.json()
        assert data["github"]["configured"] is True
        assert set(data["github"]) <= {"name", "configured", "status", "detail"}
        # The raw token is never mirrored into any other field.
        assert SECRET_TOKEN not in str(data)
    finally:
        get_settings.cache_clear()


def test_read_endpoints_never_return_the_token(client, monkeypatch):
    _with_configured_token(monkeypatch)
    try:
        for path in (
            "/api/v1/settings/status",
            "/api/v1/dashboard/summary",
            "/api/v1/repositories",
            "/api/v1/incidents",
            "/api/v1/remediations",
            "/api/v1/executions",
            "/api/v1/audit-logs",
            "/health",
        ):
            resp = client.get(path)
            assert resp.status_code == 200, path
            assert SECRET_TOKEN not in resp.text, path
    finally:
        get_settings.cache_clear()
