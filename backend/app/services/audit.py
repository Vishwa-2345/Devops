"""Audit log and agent event helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AgentEvent, AuditLog


def record_event(
    db: Session,
    *,
    agent: str,
    event_type: str,
    message: str,
    incident_id: int | None = None,
    run_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> AgentEvent:
    event = AgentEvent(
        incident_id=incident_id,
        run_id=run_id,
        agent=agent,
        event_type=event_type,
        message=message,
        data=data,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def record_audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    actor: str = "local-user",
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=details,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
