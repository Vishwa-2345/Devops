"""Security utilities: URL validation, secret redaction, log sanitization."""

from __future__ import annotations

import re

from app.config import get_settings

# Strict GitHub repository URL: https://github.com/OWNER/REPO with optional .git
_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/"
    r"(?P<repo>[A-Za-z0-9_.-]{1,100}?)(?:\.git)?/?$"
)

# Secret-ish patterns to redact from logs / model output.
_SECRET_PATTERNS = [
    re.compile(r"(ghp_[A-Za-z0-9]{20,})"),
    re.compile(r"(github_pat_[A-Za-z0-9_]{20,})"),
    re.compile(r"(gho_[A-Za-z0-9]{20,})"),
    re.compile(r"(ghs_[A-Za-z0-9]{20,})"),
    re.compile(r"(?i)(authorization\s*:\s*(?:bearer|token)\s+)(\S+)"),
    re.compile(r"(?i)(token|password|secret|api[_-]?key)(\s*[:=]\s*)(\S{6,})"),
    re.compile(r"(?i)(aws_secret_access_key\s*[:=]\s*)(\S+)"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
]

# Patterns commonly found in CI logs that look like credentials.
_ENV_ASSIGN_RE = re.compile(r"\b[A-Z][A-Z0-9_]{2,}=(\S+)")


class InvalidRepositoryURLError(ValueError):
    """Raised when a repository URL fails strict validation."""


def validate_repository_url(url: str) -> tuple[str, str]:
    """Validate a GitHub repository URL and return (owner, repo).

    Only canonical https://github.com/OWNER/REPO URLs are accepted.
    """
    if not isinstance(url, str):
        raise InvalidRepositoryURLError("Repository URL must be a string.")
    url = url.strip()
    if len(url) > 300:
        raise InvalidRepositoryURLError("Repository URL is too long.")
    match = _GITHUB_URL_RE.match(url)
    if not match:
        raise InvalidRepositoryURLError(
            "Only https://github.com/OWNER/REPOSITORY URLs are supported."
        )
    owner = match.group("owner")
    repo = match.group("repo")
    if repo.lower() in {"none", "null"}:
        raise InvalidRepositoryURLError("Invalid repository name.")
    return owner, repo


def redact_secrets(text: str) -> str:
    """Best-effort redaction of credentials from untrusted text."""
    if not text:
        return ""
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda m: _mask_match(m), redacted)
    return redacted


def _mask_match(match: re.Match) -> str:
    # Keep the key/prefix, mask the secret value.
    groups = [g for g in match.groups() if g]
    if len(groups) >= 2:
        return match.group(0).replace(groups[-1], "***REDACTED***")
    return "***REDACTED***"


def sanitize_log(text: str, max_chars: int | None = None) -> str:
    """Truncate and redact untrusted log content before storage or LLM use."""
    if not text:
        return ""
    limit = max_chars or get_settings().max_log_chars
    if len(text) > limit:
        head = text[: limit // 2]
        tail = text[-limit // 2 :]
        text = f"{head}\n... [truncated {len(text) - limit} chars] ...\n{tail}"
    return redact_secrets(text)


def contains_secret(text: str) -> bool:
    return any(p.search(text) for p in _SECRET_PATTERNS)
