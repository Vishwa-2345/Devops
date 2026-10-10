"""Global workflow run endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WorkflowRun
from app.schemas import Page, WorkflowRunOut

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=Page[WorkflowRunOut])
def list_workflows(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    repository_id: int | None = Query(None),
    only_failed: bool = Query(False),
) -> Page[WorkflowRunOut]:
    query = select(WorkflowRun)
    count_query = select(func.count()).select_from(WorkflowRun)
    if repository_id:
        query = query.where(WorkflowRun.repository_id == repository_id)
        count_query = count_query.where(WorkflowRun.repository_id == repository_id)
    if only_failed:
        failed = ("failure", "timed_out", "startup_failure", "cancelled")
        query = query.where(WorkflowRun.conclusion.in_(failed))
        count_query = count_query.where(WorkflowRun.conclusion.in_(failed))

    total = db.scalar(count_query) or 0
    rows = db.scalars(
        query.order_by(WorkflowRun.created_at_gh.desc().nullslast()).limit(limit).offset(offset)
    ).all()
    return Page[WorkflowRunOut](
        items=[WorkflowRunOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
