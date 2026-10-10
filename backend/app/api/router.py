"""Aggregate router for /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    agents,
    dashboard,
    health,
    incidents,
    remediations,
    repositories,
    settings,
    workflows,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(dashboard.router)
api_router.include_router(repositories.router)
api_router.include_router(workflows.router)
api_router.include_router(incidents.router)
api_router.include_router(remediations.router)
api_router.include_router(agents.router)
api_router.include_router(settings.router)
