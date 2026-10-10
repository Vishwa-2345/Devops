"""Shared node helpers."""

from __future__ import annotations

from app.models import Incident
from app.services.audit import record_event


def load_incident_parts(db, incident_id: int) -> tuple[Incident, object, object]:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found.")
    return incident, incident.workflow_run, incident.repository


def emit(db, state, *, agent: str, event_type: str, message: str, data=None):
    record_event(
        db,
        agent=agent,
        event_type=event_type,
        message=message,
        incident_id=state.get("incident_id"),
        data=data,
    )
