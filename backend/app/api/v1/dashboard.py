"""Dashboard summary endpoint — all values are computed from persisted data."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.llm import get_provider
from app.models import (
    AgentEvent,
    Execution,
    ExecutionStatus,
    Incident,
    IncidentStatus,
    PlanStatus,
    RemediationPlan,
    Repository,
    WorkflowRun,
)
from app.schemas import (
    AgentEventOut,
    DashboardCounts,
    DashboardSummary,
    RecentIncident,
    SuccessStat,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

FAILED = ("failure", "timed_out", "startup_failure", "cancelled")
OPEN_STATUSES = (
    IncidentStatus.OPEN.value,
    IncidentStatus.DIAGNOSING.value,
    IncidentStatus.DIAGNOSED.value,
    IncidentStatus.PLANNED.value,
    IncidentStatus.AWAITING_APPROVAL.value,
    IncidentStatus.APPROVED.value,
    IncidentStatus.EXECUTING.value,
    IncidentStatus.VERIFYING.value,
)


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    settings = get_settings()

    repositories = db.scalar(select(func.count()).select_from(Repository)) or 0
    workflow_runs = db.scalar(select(func.count()).select_from(WorkflowRun)) or 0
    failed_runs = (
        db.scalar(
            select(func.count()).select_from(WorkflowRun).where(WorkflowRun.conclusion.in_(FAILED))
        )
        or 0
    )
    open_incidents = (
        db.scalar(
            select(func.count()).select_from(Incident).where(Incident.status.in_(OPEN_STATUSES))
        )
        or 0
    )
    pending_approvals = (
        db.scalar(
            select(func.count())
            .select_from(RemediationPlan)
            .where(RemediationPlan.status == PlanStatus.AWAITING_APPROVAL.value)
        )
        or 0
    )
    successful_remediations = (
        db.scalar(
            select(func.count())
            .select_from(Execution)
            .where(Execution.status == ExecutionStatus.SUCCEEDED.value)
        )
        or 0
    )

    counts = DashboardCounts(
        repositories=repositories,
        workflow_runs=workflow_runs,
        failed_runs=failed_runs,
        open_incidents=open_incidents,
        pending_approvals=pending_approvals,
        successful_remediations=successful_remediations,
    )

    recent_rows = db.execute(
        select(Incident, Repository.full_name)
        .join(Repository, Repository.id == Incident.repository_id)
        .order_by(Incident.detected_at.desc())
        .limit(10)
    ).all()
    recent_incidents = [
        RecentIncident(
            id=inc.id,
            title=inc.title,
            failure_category=inc.failure_category,
            severity=inc.severity,
            status=inc.status,
            repository=full_name,
            detected_at=inc.detected_at,
        )
        for inc, full_name in recent_rows
    ]

    events = db.scalars(
        select(AgentEvent).order_by(AgentEvent.created_at.desc(), AgentEvent.id.desc()).limit(15)
    ).all()
    recent_events = [AgentEventOut.model_validate(e) for e in events]

    success = (
        db.scalar(
            select(func.count()).select_from(WorkflowRun).where(WorkflowRun.conclusion == "success")
        )
        or 0
    )
    cancelled = (
        db.scalar(
            select(func.count())
            .select_from(WorkflowRun)
            .where(WorkflowRun.conclusion == "cancelled")
        )
        or 0
    )
    completed_other = max(workflow_runs - success - failed_runs, 0)
    workflow_stats = [
        SuccessStat(label="Success", total=success),
        SuccessStat(label="Failed", total=failed_runs),
        SuccessStat(label="Cancelled", total=cancelled),
        SuccessStat(label="Other/In progress", total=completed_other),
    ]

    provider = get_provider()
    llm_health = provider.health()

    return DashboardSummary(
        counts=counts,
        recent_incidents=recent_incidents,
        recent_events=recent_events,
        workflow_stats=workflow_stats,
        github_connected=settings.github_configured,
        llm_provider=provider.name,
        llm_available=llm_health.available,
    )
