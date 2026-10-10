"""GitHub client error handling and normalization tests."""

from __future__ import annotations

import httpx
import pytest

from app.github import GitHubClient, GitHubError
from app.github.normalizer import is_failed, normalize_repository, normalize_workflow_run


def _client_with(handler) -> GitHubClient:
    transport = httpx.MockTransport(handler)
    return GitHubClient(client=httpx.Client(base_url="https://api.github.com", transport=transport))


def test_not_found_raises():
    def handler(request):
        return httpx.Response(404, json={"message": "Not Found"})

    client = _client_with(handler)
    with pytest.raises(GitHubError) as exc:
        client.get_repository("octocat", "nope")
    assert exc.value.status_code == 404


def test_rate_limit_detected():
    def handler(request):
        return httpx.Response(
            403,
            json={"message": "rate limit"},
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1700000000"},
        )

    client = _client_with(handler)
    with pytest.raises(GitHubError) as exc:
        client.get_repository("octocat", "demo")
    assert exc.value.rate_limited is True


def test_unauthorized():
    def handler(request):
        return httpx.Response(401, json={"message": "Bad credentials"})

    client = _client_with(handler)
    with pytest.raises(GitHubError) as exc:
        client.get_repository("octocat", "demo")
    assert exc.value.status_code == 401


def test_timeout():
    def handler(request):
        raise httpx.TimeoutException("timed out")

    client = _client_with(handler)
    with pytest.raises(GitHubError):
        client.get_repository("octocat", "demo")


def test_pagination_follows_pages():
    calls = {"n": 0}

    def handler(request):
        page = int(request.url.params.get("page", "1"))
        calls["n"] += 1
        if page == 1:
            return httpx.Response(200, json={"workflow_runs": [{"id": i} for i in range(50)]})
        return httpx.Response(200, json={"workflow_runs": [{"id": 999}]})

    client = _client_with(handler)
    runs = client.list_workflow_runs("octocat", "demo", per_page=50, max_pages=3)
    assert len(runs) == 51
    assert calls["n"] == 2


def test_collect_failure_logs_returns_text():
    def handler(request):
        if "/jobs" in request.url.path and request.url.path.endswith("/logs"):
            return httpx.Response(200, text="npm ERR! code ERESOLVE")
        if request.url.path.endswith("/jobs"):
            return httpx.Response(
                200, json={"jobs": [{"id": 1, "name": "build", "conclusion": "failure"}]}
            )
        return httpx.Response(404, json={})

    client = _client_with(handler)
    result = client.collect_failure_logs("octocat", "demo", 9001)
    assert result.available is True
    assert "ERESOLVE" in result.text


def test_normalize_repository():
    meta = normalize_repository(
        {
            "id": 1,
            "name": "demo",
            "full_name": "octocat/demo",
            "html_url": "https://github.com/octocat/demo",
            "default_branch": "trunk",
            "description": None,
            "private": True,
            "owner": {"login": "octocat"},
        }
    )
    assert meta["owner"] == "octocat"
    assert meta["default_branch"] == "trunk"
    assert meta["private"] is True


def test_normalize_workflow_run_and_failed_flag():
    data = normalize_workflow_run(
        {
            "id": 5,
            "name": "CI",
            "status": "completed",
            "conclusion": "failure",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:05:00Z",
            "run_started_at": "2026-01-01T00:00:00Z",
            "actor": {"login": "octocat"},
        }
    )
    assert data["github_run_id"] == 5
    assert data["workflow_name"] == "CI"
    assert is_failed(data["conclusion"]) is True
    assert is_failed("success") is False
