"""Planning Agent: map a diagnosis to a concrete, allowlisted remediation plan."""

from __future__ import annotations

from app.agents.nodes.common import emit, load_incident_parts
from app.agents.state import AgentState
from app.database import SessionLocal
from app.models import IncidentStatus, PlanStatus, RemediationPlan
from app.remediation import (
    UnsupportedActionError,
    build_plan_for_category,
    compute_plan_hash,
    get_action,
    validate_parameters,
)


def planning_node(state: AgentState) -> AgentState:
    db = SessionLocal()
    try:
        incident, run, _repo = load_incident_parts(db, state["incident_id"])
        category = (state.get("diagnosis") or {}).get("category") or incident.failure_category

        plan_blueprint = build_plan_for_category(category, run_id=run.github_run_id)
        if plan_blueprint is None:
            incident.status = IncidentStatus.DIAGNOSED.value
            db.commit()
            emit(
                db,
                state,
                agent="planning",
                event_type="no_remediation",
                message=f"No allowlisted remediation available for category '{category}'.",
                data={"category": category},
            )
            return {
                "phase": "planning",
                "plan": None,
                "plan_id": None,
                "requires_approval": False,
                "risk_level": None,
                "events": state.get("events", []),
            }

        try:
            action = get_action(plan_blueprint["action_id"])
            parameters = validate_parameters(action, plan_blueprint.get("parameters", {}))
        except UnsupportedActionError as exc:
            emit(
                db,
                state,
                agent="planning",
                event_type="plan_rejected",
                message=f"Planning rejected: {exc}",
            )
            return {
                "phase": "planning",
                "plan": None,
                "plan_id": None,
                "requires_approval": False,
                "risk_level": None,
                "error": str(exc),
                "events": state.get("events", []),
            }

        plan_hash = compute_plan_hash(action.action_id, parameters, action.risk_level)
        requires_approval = action.requires_approval
        status = (
            PlanStatus.AWAITING_APPROVAL.value if requires_approval else PlanStatus.PROPOSED.value
        )

        plan = RemediationPlan(
            incident_id=incident.id,
            action_id=action.action_id,
            title=plan_blueprint.get("title") or action.title,
            description=action.description,
            parameters=parameters,
            risk_level=action.risk_level,
            status=status,
            requires_approval=requires_approval,
            expected_effect=action.expected_effect,
            verification_method=action.verification_method,
            plan_hash=plan_hash,
        )
        db.add(plan)
        incident.status = (
            IncidentStatus.AWAITING_APPROVAL.value
            if requires_approval
            else IncidentStatus.PLANNED.value
        )
        db.commit()
        db.refresh(plan)

        emit(
            db,
            state,
            agent="planning",
            event_type="plan_created",
            message=(
                f"Proposed action '{action.action_id}' (risk {action.risk_level}); "
                + ("approval required." if requires_approval else "auto-executable.")
            ),
            data={"action_id": action.action_id, "risk": action.risk_level},
        )
        return {
            "phase": "planning",
            "plan": {
                "action_id": action.action_id,
                "title": plan.title,
                "parameters": parameters,
                "risk_level": action.risk_level,
                "requires_approval": requires_approval,
            },
            "plan_id": plan.id,
            "risk_level": action.risk_level,
            "requires_approval": requires_approval,
            "events": state.get("events", []),
        }
    finally:
        db.close()
