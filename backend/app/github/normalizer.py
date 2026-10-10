"""Normalize raw GitHub API payloads into internal dictionaries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

FAILED_CONCLUSIONS = {"failure", "timed_out", "startup_failure", "cancelled"}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_repository(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a GitHub repository payload to Repository model fields."""
    owner = (raw.get("owner") or {}).get("login") or ""
    return {
        "owner": owner,
        "name": raw.get("name") or "",
        "full_name": raw.get("full_name") or f"{owner}/{raw.get('name', '')}",
        "html_url": raw.get("html_url") or "",
        "default_branch": raw.get("default_branch") or "main",
        "description": raw.get("description"),
        "private": bool(raw.get("private", False)),
        "github_repo_id": raw.get("id"),
    }


def normalize_workflow_run(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a GitHub workflow run payload to WorkflowRun model fields."""
    return {
        "github_run_id": raw.get("id"),
        "workflow_id": raw.get("workflow_id"),
        "workflow_name": raw.get("name") or "unknown",
        "run_number": raw.get("run_number"),
        "event": raw.get("event"),
        "head_branch": raw.get("head_branch"),
        "head_sha": raw.get("head_sha"),
        "status": raw.get("status") or "queued",
        "conclusion": raw.get("conclusion"),
        "html_url": raw.get("html_url"),
        "actor": (raw.get("actor") or {}).get("login") if raw.get("actor") else None,
        "started_at": _parse_dt(raw.get("run_started_at") or raw.get("created_at")),
        "completed_at": _parse_dt(raw.get("updated_at")),
        "created_at_gh": _parse_dt(raw.get("created_at")),
    }


def is_failed(conclusion: str | None) -> bool:
    return conclusion in FAILED_CONCLUSIONS
