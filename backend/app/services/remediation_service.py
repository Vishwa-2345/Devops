"""Remediation execution service.

Executes only allowlisted actions. Never runs shell commands. A successful API
response is NOT treated as success; verification is a separate step.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.github import GitHubError
from app.models import (
    Approval,
    Execution,
    ExecutionStatus,
    Incident,
    IncidentStatus,
    PlanStatus,
    RemediationPlan,
    VerificationStatus,
    utcnow,
)
from app.remediation import UnsupportedActionError, get_action, validate_parameters
from app.services.audit import record_audit, record_event
from app.services.github_provider import get_github_client


class RemediationError(Exception):
    pass


def _latest_successful_execution(db: Session, plan_id: int) -> Execution | None:
    return db.scalar(
        select(Execution)
        .where(Execution.remediation_plan_id == plan_id)
        .where(Execution.status == ExecutionStatus.SUCCEEDED.value)
        .order_by(Execution.id.desc())
    )


def execute_plan(db: Session, plan: RemediationPlan, actor: str = "local-user") -> Execution:
    incident = db.get(Incident, plan.incident_id)

    # Defense-in-depth: approval enforced here regardless of caller.
    if plan.requires_approval:
        if plan.status != PlanStatus.APPROVED.value:
            raise RemediationError(
                "Approval required before execution (plan is not in 'approved' state)."
            )
        approval = (
            db.query(Approval)
            .filter(Approval.remediation_plan_id == plan.id)
            .order_by(Approval.created_at.desc(), Approval.id.desc())
            .first()
        )
        if approval is None or approval.decision != "approved":
            raise RemediationError("Approval required before execution.")
        if approval.plan_hash != plan.plan_hash:
            plan.status = PlanStatus.INVALIDATED.value
            db.commit()
            raise RemediationError(
                "Plan changed after approval; the previous approval is invalid. Re-approval required."
            )

    # Duplicate execution protection.
    if _latest_successful_execution(db, plan.id) is not None:
        raise RemediationError("This remediation plan has already been executed successfully.")

    try:
        action = get_action(plan.action_id)
        parameters = validate_parameters(action, plan.parameters or {})
    except UnsupportedActionError as exc:
        raise RemediationError(str(exc)) from exc

    execution = Execution(
        remediation_plan_id=plan.id,
        action_id=action.action_id,
        status=ExecutionStatus.RUNNING.value,
        actor=actor,
        parameters=parameters,
    )
    db.add(execution)
    plan.status = PlanStatus.EXECUTING.value
    if incident:
        incident.status = IncidentStatus.EXECUTING.value
    db.commit()
    db.refresh(execution)

    record_event(
        db,
        agent="remediation",
        event_type="execution_started",
        message=f"Executing '{action.action_id}'.",
        incident_id=plan.incident_id,
        data={"action_id": action.action_id},
    )

    try:
        result = _dispatch(action.action_id, parameters, incident)
        execution.status = ExecutionStatus.SUCCEEDED.value
        execution.result = result
        plan.status = PlanStatus.EXECUTED.value
        if incident:
            incident.status = IncidentStatus.VERIFYING.value
        execution.verification_status = VerificationStatus.PENDING.value
    except (RemediationError, GitHubError) as exc:
        execution.status = ExecutionStatus.FAILED.value
        execution.error = str(exc)
        plan.status = PlanStatus.FAILED.value
        if incident:
            incident.status = IncidentStatus.FAILED.value
        execution.verification_status = VerificationStatus.UNVERIFIED.value
        execution.verification_details = {"reason": str(exc)}
    except Exception as exc:  # noqa: BLE001
        execution.status = ExecutionStatus.FAILED.value
        execution.error = f"Unexpected execution error: {exc}"
        plan.status = PlanStatus.FAILED.value
        if incident:
            incident.status = IncidentStatus.FAILED.value
        execution.verification_status = VerificationStatus.UNVERIFIED.value

    execution.completed_at = utcnow()
    db.commit()
    db.refresh(execution)

    record_event(
        db,
        agent="remediation",
        event_type="execution_finished",
        message=f"Execution of '{action.action_id}' finished with status {execution.status}.",
        incident_id=plan.incident_id,
        data={"status": execution.status, "error": execution.error},
    )
    record_audit(
        db,
        action="remediation.execute",
        entity_type="execution",
        entity_id=execution.id,
        actor=actor,
        details={"action_id": action.action_id, "status": execution.status},
    )
    return execution


def _dispatch(action_id: str, parameters: dict, incident: Incident | None) -> dict:
    if action_id == "RERUN_WORKFLOW":
        client = get_github_client()
        if not client.configured:
            raise RemediationError(
                "Cannot re-run workflow: GITHUB_TOKEN with actions:write is not configured."
            )
        if incident is None:
            raise RemediationError("Incident context missing for workflow re-run.")
        repo = incident.repository
        run_id = int(parameters["run_id"])
        response = client.rerun_workflow(repo.owner, repo.name, run_id)
        return {
            "kind": "api_call",
            "endpoint": f"POST /repos/{repo.owner}/{repo.name}/actions/runs/{run_id}/rerun",
            "status_code": response.get("status_code"),
            "note": "API accepted the re-run request; success is confirmed during verification.",
        }

    if action_id in {"RECOMMEND_DEPENDENCY_FIX", "RECOMMEND_CONFIG_FIX", "RECOMMEND_ENV_VAR_FIX"}:
        return {
            "kind": "recommendation",
            "action_id": action_id,
            "recommendation": parameters,
            "note": "Recommendation recorded for human review (no external mutation).",
        }

    raise RemediationError(f"Action '{action_id}' is not executable.")
