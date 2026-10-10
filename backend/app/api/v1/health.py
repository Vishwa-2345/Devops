"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.config import get_settings
from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness and readiness check")
def health(db: Session = Depends(get_db)) -> dict:
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    settings = get_settings()
    return {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "database": "ok" if db_ok else "error",
        "github_configured": settings.github_configured,
        "llm_provider": settings.llm_provider,
    }
