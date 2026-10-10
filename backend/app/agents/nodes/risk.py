"""Risk Evaluation Agent: deterministic security/risk rules.

Risk is never inferred from model output. It is derived solely from the
allowlisted action definition plus fixed, auditable escalation rules.
"""

from __future__ import annotations

from app.agents.nodes.common import emit, load_incident_parts
from app.agents.state import AgentState
from app.database import SessionLocal
from app.models import RemediationPlan, RiskLevel
from app.remediation import get_action

_ORDER = [
    RiskLevel.LOW.value,
    RiskLevel.MEDIUM.value,
    RiskLevel.HIGH.value,
    RiskLevel.CRITICAL.value,
]


def _escalate(level: str) -> str:
    idx = _ORDER.index(level) if level in _ORDER else 1
    return _ORDER[min(idx + 1, len(_ORDER) - 1)]


def risk_node(state: AgentState) -> AgentState:
    db = SessionLocal()
    try:
        incident, _run, _repo = load_incident_parts(db, state["incident_id"])
        plan_id = state.get("plan_id")
        if not plan_id:
            return {
                "phase": "risk",
                "risk_level": None,
                "requires_approval": False,
                "events": state.get("events", []),
            }

        plan = db.get(RemediationPlan, plan_id)
        if plan is None:
            return {
                "phase": "risk",
                "risk_level": None,
                "requires_approval": False,
                "error": "Plan disappeared.",
                "events": state.get("events", []),
            }

        try:
            action = get_action(plan.action_id)
        except Exception as exc:  # noqa: BLE001 - unknown action => reject
            plan.status = "rejected"
            db.commit()
            return {
                "phase": "risk",
                "risk_level": None,
                "requires_approval": False,
                "error": str(exc),
                "events": state.get("events", []),
            }

        level = action.risk_level
        reasons = [f"action '{action.action_id}' base risk is {level}"]
        if action.mutates_external_state and level == RiskLevel.LOW.value:
            level = RiskLevel.MEDIUM.value
            reasons.append("mutates external state -> escalated to medium")
        if incident.failure_category == "authentication_failure" and action.mutates_external_state:
            level = _escalate(level)
            reasons.append("authentication-related failure -> escalated")

        requires_approval = action.requires_approval or level in {
            RiskLevel.MEDIUM.value,
            RiskLevel.HIGH.value,
            RiskLevel.CRITICAL.value,
        }

        # Persist the evaluated risk.
        if plan.risk_level != level:
            plan.risk_level = level
        plan.requires_approval = requires_approval
        db.commit()

        emit(
            db,
            state,
            agent="risk_evaluation",
            event_type="risk_evaluated",
            message=f"Risk evaluated as {level}; approval {'required' if requires_approval else 'not required'}.",
            data={"risk_level": level, "reasons": reasons},
        )
        return {
            "phase": "risk",
            "risk_level": level,
            "requires_approval": requires_approval,
            "events": state.get("events", []),
        }
    finally:
        db.close()
