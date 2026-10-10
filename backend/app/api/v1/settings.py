"""Settings and integration status endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.config import get_settings
from app.llm import get_provider
from app.schemas import IntegrationStatus, SettingsStatus

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/status", response_model=SettingsStatus)
def settings_status() -> SettingsStatus:
    settings = get_settings()

    if settings.github_configured:
        github = IntegrationStatus(
            name="GitHub",
            configured=True,
            status="connected",
            detail="GITHUB_TOKEN is configured. Private repositories and higher rate limits available.",
        )
    else:
        github = IntegrationStatus(
            name="GitHub",
            configured=False,
            status="unconfigured",
            detail=(
                "No GITHUB_TOKEN configured. Public repositories only, with lower rate limits; "
                "workflow logs and re-runs require a token."
            ),
        )

    provider = get_provider()
    health = provider.health()
    llm = IntegrationStatus(
        name="LLM",
        configured=health.available,
        status="available" if health.available else "rules-fallback",
        detail=health.detail,
    )

    return SettingsStatus(
        app_version=__version__,
        environment=settings.environment,
        github=github,
        llm=llm,
        polling_enabled=settings.poll_interval_seconds > 0,
        poll_interval_seconds=settings.poll_interval_seconds,
        database=("sqlite" if settings.is_sqlite else "external") + " database",
        cors_origins=settings.cors_origin_list,
    )
