"""Verification Agent: confirm the real outcome of a remediation.

A remediation is only marked VERIFIED when an observable external state change
confirms it (for example a re-run workflow now shows queued/in_progress/success).
Recommendation-only actions cannot be verified automatically and are reported as
unverified with the reason.
"""

from __future__ import annotations

from app.agents.nodes.common import emit, load_incident_parts
from app.agents.state import AgentState
from app.database import SessionLocal
from app.github import GitHubError
from app.models import (
    Execution,
    IncidentStatus,
    PlanStatus,
    RemediationPlan,
    VerificationStatus,
    utcnow,
)
from app.services.github_provider import get_github_client


def verification_node(state: AgentState) -> AgentState:
    db = SessionLocal()
    try:
        incident, run, repo = load_incident_parts(db, state["incident_id"])
        events = state.get("events", [])
        plan_id = state.get("plan_id")
        if not plan_id:
            return {"phase": "verification", "verification": None, "events": events}

        plan = db.get(RemediationPlan, plan_id)
        if plan is None:
            return {"phase": "verification", "verification": None, "events": events}

        execution = (
            db.query(Execution)
            .filter(Execution.remediation_plan_id == plan.id)
            .order_by(Execution.id.desc())
            .first()
        )
        if execution is None:
            return {"phase": "verification", "verification": None, "events": events}

        if execution.status != "succeeded":
            execution.verification_status = VerificationStatus.UNVERIFIED.value
            execution.verification_details = {
                "reason": f"Execution did not succeed (status={execution.status})."
            }
            db.commit()
            emit(
                db,
                state,
                agent="verification",
                event_type="verification_result",
                message="Not verified: execution did not succeed.",
            )
            return {
                "phase": "verification",
                "verification": {
                    "status": execution.verification_status,
                    "details": execution.verification_details,
                },
                "events": events,
            }

        status, details = _verify(db, plan, execution, repo, run.github_run_id)
        execution.verification_status = status
        execution.verification_details = details

        if status == VerificationStatus.VERIFIED.value:
            plan.status = PlanStatus.EXECUTED.value
            if details.get("outcome") == "success":
                incident.status = IncidentStatus.RESOLVED.value
                incident.resolved_at = utcnow()
        elif status == VerificationStatus.UNVERIFIED.value:
            if details.get("outcome") == "manual_review_required":
                # Recommendation-only actions cannot be auto-verified; hand the
                # incident back to the operator instead of leaving it stuck in
                # 'verifying' forever.
                incident.status = IncidentStatus.OPEN.value
            elif incident.status in {
                IncidentStatus.EXECUTING.value,
                IncidentStatus.VERIFYING.value,
            }:
                incident.status = IncidentStatus.FAILED.value
        db.commit()

        emit(
            db,
            state,
            agent="verification",
            event_type="verification_result",
            message=f"Verification result: {status}.",
            data=details,
        )
        return {
            "phase": "verification",
            "verification": {"status": status, "details": details},
            "events": events,
        }
    finally:
        db.close()


def _verify(db, plan: RemediationPlan, execution: Execution, repo, run_id: int) -> tuple[str, dict]:
    if plan.action_id == "RERUN_WORKFLOW":
        client = get_github_client()
        if not client.configured:
            return VerificationStatus.UNVERIFIED.value, {
                "reason": "Cannot verify re-run without GitHub credentials.",
                "outcome": "unknown",
            }
        try:
            raw = client.get_workflow_run(repo.owner, repo.name, run_id)
        except GitHubError as exc:
            return VerificationStatus.UNVERIFIED.value, {
                "reason": exc.message,
                "outcome": "unknown",
            }

        gh_status = raw.get("status")
        gh_conclusion = raw.get("conclusion")
        if gh_status in {"queued", "in_progress", "requested", "waiting", "pending"}:
            return VerificationStatus.VERIFIED.value, {
                "reason": "Workflow re-run is queued or in progress.",
                "observed_status": gh_status,
                "observed_conclusion": gh_conclusion,
                "outcome": "rerun_accepted",
            }
        if gh_status == "completed" and gh_conclusion == "success":
            return VerificationStatus.VERIFIED.value, {
                "reason": "Workflow re-run completed successfully.",
                "observed_status": gh_status,
                "observed_conclusion": gh_conclusion,
                "outcome": "success",
            }
        return VerificationStatus.UNVERIFIED.value, {
            "reason": "Re-run has not yet produced a successful outcome.",
            "observed_status": gh_status,
            "observed_conclusion": gh_conclusion,
            "outcome": "not_confirmed",
        }

    if plan.action_id.startswith("RECOMMEND_"):
        return VerificationStatus.UNVERIFIED.value, {
            "reason": "Recommendation-only action: confirmation requires a subsequent workflow run "
            "or manual review.",
            "outcome": "manual_review_required",
        }

    return VerificationStatus.UNVERIFIED.value, {
        "reason": "No verification method.",
        "outcome": "unknown",
    }
