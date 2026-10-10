"""GitHub client provider with an injectable override for tests."""

from __future__ import annotations

import httpx

from app.github import GitHubClient

_override: GitHubClient | None = None
_default: GitHubClient | None = None


def set_github_client_override(client: GitHubClient | None) -> None:
    """Test hook: force a specific client (e.g. backed by MockTransport)."""
    global _override
    _override = client


def get_github_client() -> GitHubClient:
    """Return the active GitHub client.

    A single default client is reused per process to share the connection pool.
    Tests may override it via ``set_github_client_override``.
    """
    global _default
    if _override is not None:
        return _override
    if _default is None:
        _default = GitHubClient()
    return _default


def close_default_client() -> None:
    global _default
    if _default is not None:
        _default.close()
        _default = None


def get_github_client_for_http(client: httpx.Client, token: str | None = None) -> GitHubClient:
    return GitHubClient(client=client, token=token)
