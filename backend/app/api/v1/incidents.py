"""Incident endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.agents import run_analysis, run_planning
from app.database import get_db
from app.models import Diagnosis, Incident
from app.schemas import (
    DiagnosisOut,
    IncidentDetailOut,
    IncidentOut,
    Page,
    RemediationPlanOut,
    RepositoryOut,
    WorkflowRunOut,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/incidents", tags=["incidents"])


def get_incident_or_404(db: Session, incident_id: int) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found.")
    return incident


@router.get("", response_model=Page[IncidentOut])
def list_incidents(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = Query(None),
    repository_id: int | None = Query(None),
) -> Page[IncidentOut]:
    query = select(Incident)
    count_query = select(func.count()).select_from(Incident)
    if status_filter:
        query = query.where(Incident.status == status_filter)
        count_query = count_query.where(Incident.status == status_filter)
    if category:
        query = query.where(Incident.failure_category == category)
        count_query = count_query.where(Incident.failure_category == category)
    if repository_id:
        query = query.where(Incident.repository_id == repository_id)
        count_query = count_query.where(Incident.repository_id == repository_id)

    total = db.scalar(count_query) or 0
    rows = db.scalars(query.order_by(Incident.detected_at.desc()).limit(limit).offset(offset)).all()
    return Page[IncidentOut](
        items=[IncidentOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/{incident_id}", response_model=IncidentDetailOut)
def get_incident(incident_id: int, db: Session = Depends(get_db)) -> IncidentDetailOut:
    incident = db.scalar(
        select(Incident)
        .where(Incident.id == incident_id)
        .options(
            selectinload(Incident.diagnoses),
            selectinload(Incident.remediation_plans),
        )
    )
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found.")

    return IncidentDetailOut(
        **IncidentOut.model_validate(incident).model_dump(),
        repository=RepositoryOut.model_validate(incident.repository)
        if incident.repository
        else None,
        workflow_run=WorkflowRunOut.model_validate(incident.workflow_run)
        if incident.workflow_run
        else None,
        diagnoses=[DiagnosisOut.model_validate(d) for d in incident.diagnoses],
        remediation_plans=[
            RemediationPlanOut.model_validate(p) for p in incident.remediation_plans
        ],
    )


@router.post("/{incident_id}/analyze", response_model=IncidentDetailOut)
def analyze_incident(incident_id: int, db: Session = Depends(get_db)) -> IncidentDetailOut:
    incident = get_incident_or_404(db, incident_id)
    try:
        run_analysis(incident.id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc
    record_audit(db, action="incident.analyze", entity_type="incident", entity_id=incident.id)
    return get_incident(incident_id, db)


@router.post("/{incident_id}/plan-remediation", response_model=IncidentDetailOut)
def plan_remediation(incident_id: int, db: Session = Depends(get_db)) -> IncidentDetailOut:
    incident = get_incident_or_404(db, incident_id)
    has_diagnosis = (
        db.scalar(
            select(func.count()).select_from(Diagnosis).where(Diagnosis.incident_id == incident.id)
        )
        or 0
    ) > 0
    try:
        if has_diagnosis:
            run_planning(incident.id)
        else:
            run_analysis(incident.id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Planning failed: {exc}") from exc
    record_audit(
        db, action="incident.plan_remediation", entity_type="incident", entity_id=incident.id
    )
    return get_incident(incident_id, db)
