"""Repository URL validation and secret redaction tests."""

from __future__ import annotations

import pytest

from app.security import (
    InvalidRepositoryURLError,
    redact_secrets,
    sanitize_log,
    validate_repository_url,
)


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/octocat/Hello-World", ("octocat", "Hello-World")),
        ("https://github.com/octocat/Hello-World.git", ("octocat", "Hello-World")),
        ("https://github.com/octocat/Hello-World/", ("octocat", "Hello-World")),
        ("https://github.com/a/b_c.d-e", ("a", "b_c.d-e")),
    ],
)
def test_valid_repository_urls(url, expected):
    assert validate_repository_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/octocat/Hello-World",
        "https://gitlab.com/octocat/Hello-World",
        "https://github.com/octocat",
        "https://github.com/",
        "git@github.com:octocat/Hello-World.git",
        "javascript:alert(1)",
        "https://github.com/octocat/Hello-World/../../etc/passwd",
        "https://evil.com/github.com/octocat/repo",
        "",
    ],
)
def test_invalid_repository_urls(url):
    with pytest.raises(InvalidRepositoryURLError):
        validate_repository_url(url)


def test_redact_secrets_masks_tokens():
    text = "Authorization: Bearer ghp_abcdefghijklmnopqrstuvwxyz0123"
    cleaned = redact_secrets(text)
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123" not in cleaned
    assert "REDACTED" in cleaned


def test_sanitize_log_truncates():
    big = "x" * 500
    result = sanitize_log(big, max_chars=100)
    assert "truncated" in result
    assert len(result) < 500


def test_redact_password_assignment():
    cleaned = redact_secrets("PASSWORD=supersecretvalue123")
    assert "supersecretvalue123" not in cleaned
