"""Remediation proposal, approval and execution endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents import run_execution
from app.database import get_db
from app.models import (
    Approval,
    Execution,
    ExecutionStatus,
    Incident,
    IncidentStatus,
    PlanStatus,
    RemediationPlan,
)
from app.schemas import (
    ApprovalDecision,
    ApprovalOut,
    ExecuteRequest,
    ExecutionOut,
    Page,
    RemediationPlanOut,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/remediations", tags=["remediations"])


def _get_plan_or_404(db: Session, plan_id: int) -> RemediationPlan:
    plan = db.get(RemediationPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Remediation plan {plan_id} not found.")
    return plan


@router.get("", response_model=Page[RemediationPlanOut])
def list_remediations(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
) -> Page[RemediationPlanOut]:
    query = select(RemediationPlan)
    count_query = select(func.count()).select_from(RemediationPlan)
    if status_filter:
        query = query.where(RemediationPlan.status == status_filter)
        count_query = count_query.where(RemediationPlan.status == status_filter)
    total = db.scalar(count_query) or 0
    rows = db.scalars(
        query.order_by(RemediationPlan.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return Page[RemediationPlanOut](
        items=[RemediationPlanOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{plan_id}", response_model=RemediationPlanOut)
def get_remediation(plan_id: int, db: Session = Depends(get_db)) -> RemediationPlanOut:
    return RemediationPlanOut.model_validate(_get_plan_or_404(db, plan_id))


@router.post("/{plan_id}/approve", response_model=ApprovalOut)
def approve_plan(
    plan_id: int, payload: ApprovalDecision, db: Session = Depends(get_db)
) -> ApprovalOut:
    plan = _get_plan_or_404(db, plan_id)
    if plan.status in {PlanStatus.EXECUTING.value, PlanStatus.EXECUTED.value}:
        raise HTTPException(status_code=409, detail="Plan is already executing or executed.")

    approval = Approval(
        remediation_plan_id=plan.id,
        decision="approved",
        decided_by=payload.decided_by,
        reason=payload.reason,
        plan_hash=plan.plan_hash,
    )
    db.add(approval)
    plan.status = PlanStatus.APPROVED.value
    incident = db.get(Incident, plan.incident_id)
    if incident:
        incident.status = IncidentStatus.APPROVED.value
    db.commit()
    db.refresh(approval)
    record_audit(
        db,
        action="remediation.approve",
        entity_type="remediation_plan",
        entity_id=plan.id,
        actor=payload.decided_by,
        details={"reason": payload.reason},
    )
    return ApprovalOut.model_validate(approval)


@router.post("/{plan_id}/reject", response_model=ApprovalOut)
def reject_plan(
    plan_id: int, payload: ApprovalDecision, db: Session = Depends(get_db)
) -> ApprovalOut:
    plan = _get_plan_or_404(db, plan_id)
    approval = Approval(
        remediation_plan_id=plan.id,
        decision="rejected",
        decided_by=payload.decided_by,
        reason=payload.reason,
        plan_hash=plan.plan_hash,
    )
    db.add(approval)
    plan.status = PlanStatus.REJECTED.value
    incident = db.get(Incident, plan.incident_id)
    if incident:
        incident.status = IncidentStatus.DIAGNOSED.value
    db.commit()
    db.refresh(approval)
    record_audit(
        db,
        action="remediation.reject",
        entity_type="remediation_plan",
        entity_id=plan.id,
        actor=payload.decided_by,
        details={"reason": payload.reason},
    )
    return ApprovalOut.model_validate(approval)


@router.post("/{plan_id}/execute", response_model=ExecutionOut)
def execute_remediation(
    plan_id: int, payload: ExecuteRequest, db: Session = Depends(get_db)
) -> ExecutionOut:
    plan = _get_plan_or_404(db, plan_id)

    already = db.scalar(
        select(Execution)
        .where(Execution.remediation_plan_id == plan.id)
        .where(Execution.status == ExecutionStatus.SUCCEEDED.value)
    )
    if already is not None:
        raise HTTPException(status_code=409, detail="Plan already executed successfully.")

    if plan.requires_approval:
        if plan.status != PlanStatus.APPROVED.value:
            raise HTTPException(
                status_code=403,
                detail="Approval required before execution. Approve the plan first.",
            )
        approval = (
            db.query(Approval)
            .filter(Approval.remediation_plan_id == plan.id)
            .order_by(Approval.created_at.desc(), Approval.id.desc())
            .first()
        )
        if approval is None or approval.decision != "approved":
            raise HTTPException(status_code=403, detail="Approval required before execution.")
        if approval.plan_hash != plan.plan_hash:
            plan.status = PlanStatus.INVALIDATED.value
            db.commit()
            raise HTTPException(
                status_code=409,
                detail="Plan changed after approval; previous approval invalidated. Re-approval required.",
            )

    try:
        state = run_execution(plan.incident_id, plan.id, actor=payload.actor)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Execution failed: {exc}") from exc

    latest = db.scalar(
        select(Execution)
        .where(Execution.remediation_plan_id == plan.id)
        .order_by(Execution.id.desc())
    )
    if latest is None:
        detail = (state or {}).get("error") or "Execution was refused."
        raise HTTPException(status_code=422, detail=detail)

    record_audit(
        db,
        action="remediation.execute",
        entity_type="remediation_plan",
        entity_id=plan.id,
        actor=payload.actor,
        details={"execution_id": latest.id, "status": latest.status},
    )
    return ExecutionOut.model_validate(latest)
