"""Remediation Agent: execute the approved, allowlisted remediation action."""

from __future__ import annotations

from app.agents.nodes.common import emit, load_incident_parts
from app.agents.state import AgentState
from app.database import SessionLocal
from app.models import RemediationPlan
from app.services.remediation_service import RemediationError, execute_plan


def remediation_node(state: AgentState) -> AgentState:
    db = SessionLocal()
    try:
        incident, _run, _repo = load_incident_parts(db, state["incident_id"])
        plan_id = state.get("plan_id")
        events = state.get("events", [])
        if not plan_id:
            return {"phase": "remediation", "execution_result": None, "events": events}

        plan = db.get(RemediationPlan, plan_id)
        if plan is None:
            return {
                "phase": "remediation",
                "execution_result": None,
                "error": "Plan missing.",
                "events": events,
            }

        try:
            execution = execute_plan(db, plan, actor=state.get("actor") or "local-user")
        except RemediationError as exc:
            emit(
                db,
                state,
                agent="remediation",
                event_type="execution_refused",
                message=f"Refused to execute: {exc}",
            )
            return {
                "phase": "remediation",
                "execution_result": {"status": "failed", "error": str(exc)},
                "error": str(exc),
                "events": events,
            }

        return {
            "phase": "remediation",
            "execution_result": {
                "execution_id": execution.id,
                "status": execution.status,
                "action_id": execution.action_id,
                "result": execution.result,
                "error": execution.error,
            },
            "events": events,
        }
    finally:
        db.close()
