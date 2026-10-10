"""Approval Gate: server-side enforcement of human approval.

An approval is only valid if its recorded plan hash matches the current plan
hash. If the plan changed after approval, the approval is invalidated and the
gate routes back to awaiting approval.
"""

from __future__ import annotations

from app.agents.nodes.common import emit, load_incident_parts
from app.agents.state import AgentState
from app.database import SessionLocal
from app.models import Approval, IncidentStatus, PlanStatus, RemediationPlan


def approval_gate_node(state: AgentState) -> AgentState:
    db = SessionLocal()
    try:
        incident, _run, _repo = load_incident_parts(db, state["incident_id"])
        plan_id = state.get("plan_id")
        events = state.get("events", [])
        if not plan_id:
            return {
                "phase": "approval_gate",
                "approval_status": "not_required",
                "next_step": "end",
                "events": events,
            }

        plan = db.get(RemediationPlan, plan_id)
        if plan is None:
            return {
                "phase": "approval_gate",
                "approval_status": "not_required",
                "next_step": "end",
                "events": events,
            }

        if not plan.requires_approval:
            execute_now = bool(state.get("execute_now", False))
            return {
                "phase": "approval_gate",
                "approval_status": "not_required",
                "next_step": "remediation" if execute_now else "end",
                "events": events,
            }

        approval = (
            db.query(Approval)
            .filter(Approval.remediation_plan_id == plan.id)
            .order_by(Approval.created_at.desc(), Approval.id.desc())
            .first()
        )
        if approval is None:
            plan.status = PlanStatus.AWAITING_APPROVAL.value
            incident.status = IncidentStatus.AWAITING_APPROVAL.value
            db.commit()
            emit(
                db,
                state,
                agent="approval_gate",
                event_type="awaiting_approval",
                message="Remediation is high risk and is awaiting human approval.",
            )
            return {
                "phase": "approval_gate",
                "approval_status": "pending",
                "next_step": "end",
                "events": events,
            }

        if approval.plan_hash != plan.plan_hash:
            # The plan changed after approval -> invalidate.
            plan.status = PlanStatus.INVALIDATED.value
            incident.status = IncidentStatus.AWAITING_APPROVAL.value
            db.commit()
            emit(
                db,
                state,
                agent="approval_gate",
                event_type="approval_invalidated",
                message="Plan changed after approval; previous approval invalidated.",
            )
            return {
                "phase": "approval_gate",
                "approval_status": "invalidated",
                "next_step": "end",
                "events": events,
            }

        if approval.decision == "approved":
            plan.status = PlanStatus.APPROVED.value
            incident.status = IncidentStatus.APPROVED.value
            db.commit()
            emit(
                db,
                state,
                agent="approval_gate",
                event_type="approval_confirmed",
                message=f"Approved by {approval.decided_by}.",
            )
            return {
                "phase": "approval_gate",
                "approval_status": "approved",
                "next_step": "remediation" if state.get("execute_now") else "end",
                "events": events,
            }

        plan.status = PlanStatus.REJECTED.value
        incident.status = IncidentStatus.DIAGNOSED.value
        db.commit()
        emit(
            db,
            state,
            agent="approval_gate",
            event_type="approval_rejected",
            message=f"Rejected by {approval.decided_by}.",
        )
        return {
            "phase": "approval_gate",
            "approval_status": "rejected",
            "next_step": "end",
            "events": events,
        }
    finally:
        db.close()
