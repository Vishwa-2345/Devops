"""Agent activity and execution history endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentEvent, AuditLog, Execution
from app.schemas import AgentEventOut, AuditLogOut, ExecutionOut, Page

router = APIRouter(tags=["agents"])


@router.get("/agents/activity", response_model=Page[AgentEventOut])
def agent_activity(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    agent: str | None = Query(None),
    incident_id: int | None = Query(None),
) -> Page[AgentEventOut]:
    query = select(AgentEvent)
    count_query = select(func.count()).select_from(AgentEvent)
    if agent:
        query = query.where(AgentEvent.agent == agent)
        count_query = count_query.where(AgentEvent.agent == agent)
    if incident_id:
        query = query.where(AgentEvent.incident_id == incident_id)
        count_query = count_query.where(AgentEvent.incident_id == incident_id)
    total = db.scalar(count_query) or 0
    rows = db.scalars(
        query.order_by(AgentEvent.created_at.desc(), AgentEvent.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return Page[AgentEventOut](
        items=[AgentEventOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/executions", response_model=Page[ExecutionOut])
def list_executions(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
) -> Page[ExecutionOut]:
    query = select(Execution)
    count_query = select(func.count()).select_from(Execution)
    if status_filter:
        query = query.where(Execution.status == status_filter)
        count_query = count_query.where(Execution.status == status_filter)
    total = db.scalar(count_query) or 0
    rows = db.scalars(
        query.order_by(Execution.started_at.desc(), Execution.id.desc()).limit(limit).offset(offset)
    ).all()
    return Page[ExecutionOut](
        items=[ExecutionOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/audit-logs", response_model=Page[AuditLogOut])
def list_audit_logs(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[AuditLogOut]:
    total = db.scalar(select(func.count()).select_from(AuditLog)) or 0
    rows = db.scalars(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return Page[AuditLogOut](
        items=[AuditLogOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )
