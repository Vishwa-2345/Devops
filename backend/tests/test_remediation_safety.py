"""Remediation safety tests: allowlist, approval enforcement, invalidation."""

from __future__ import annotations

import pytest

from app.models import PlanStatus, RemediationPlan
from app.remediation import ACTIONS, UnsupportedActionError, get_action, validate_parameters
from app.remediation.registry import compute_plan_hash
from app.services.remediation_service import RemediationError, execute_plan
from tests.conftest import create_repo_and_incident


def test_registry_is_an_allowlist():
    assert set(ACTIONS) == {
        "RERUN_WORKFLOW",
        "RECOMMEND_DEPENDENCY_FIX",
        "RECOMMEND_CONFIG_FIX",
        "RECOMMEND_ENV_VAR_FIX",
    }
    # No shell / arbitrary command action may ever exist.
    for action_id in ACTIONS:
        assert "SHELL" not in action_id
        assert "EXEC" not in action_id
        assert "COMMAND" not in action_id


def test_unknown_action_rejected():
    with pytest.raises(UnsupportedActionError):
        get_action("RUN_ARBITRARY_SHELL")


def test_invalid_parameters_rejected():
    action = get_action("RERUN_WORKFLOW")
    with pytest.raises(UnsupportedActionError):
        validate_parameters(action, {"run_id": "not-an-int"})
    with pytest.raises(UnsupportedActionError):
        validate_parameters(action, {})  # missing required
    with pytest.raises(UnsupportedActionError):
        validate_parameters(action, {"run_id": 1, "malicious": "rm -rf /"})


def test_plan_hash_changes_with_parameters():
    action = get_action("RERUN_WORKFLOW")
    h1 = compute_plan_hash("RERUN_WORKFLOW", {"run_id": 1}, action.risk_level)
    h2 = compute_plan_hash("RERUN_WORKFLOW", {"run_id": 2}, action.risk_level)
    assert h1 != h2


def test_execute_refuses_unapproved_plan(client, db, github_fixture):
    github_fixture()
    _repo, run, incident = create_repo_and_incident(db)
    plan = RemediationPlan(
        incident_id=incident.id,
        action_id="RERUN_WORKFLOW",
        title="rerun",
        parameters={"run_id": run.github_run_id},
        risk_level="medium",
        status=PlanStatus.AWAITING_APPROVAL.value,
        requires_approval=True,
        plan_hash="abc",
    )
    db.add(plan)
    db.commit()

    with pytest.raises(RemediationError):
        execute_plan(db, plan)


def test_execute_rejects_unknown_action_plan(client, db, github_fixture):
    github_fixture()
    _repo, run, incident = create_repo_and_incident(db)
    plan = RemediationPlan(
        incident_id=incident.id,
        action_id="RUN_ARBITRARY_SHELL",
        title="evil",
        parameters={"cmd": "rm -rf /"},
        risk_level="low",
        status=PlanStatus.PROPOSED.value,
        requires_approval=False,
        plan_hash="abc",
    )
    db.add(plan)
    db.commit()

    resp = client.post(f"/api/v1/remediations/{plan.id}/execute", json={})
    assert resp.status_code == 422


def test_approval_invalidation_on_plan_change(client, db, github_fixture):
    github_fixture()
    _repo, run, incident = create_repo_and_incident(db)
    plan = RemediationPlan(
        incident_id=incident.id,
        action_id="RERUN_WORKFLOW",
        title="rerun",
        parameters={"run_id": run.github_run_id},
        risk_level="medium",
        status=PlanStatus.AWAITING_APPROVAL.value,
        requires_approval=True,
        plan_hash="hash-v1",
    )
    db.add(plan)
    db.commit()

    client.post(f"/api/v1/remediations/{plan.id}/approve", json={"decided_by": "tester"})

    # Simulate the plan changing after approval.
    db.refresh(plan)
    plan.plan_hash = "hash-v2"
    db.commit()

    resp = client.post(f"/api/v1/remediations/{plan.id}/execute", json={})
    assert resp.status_code == 409

    db.refresh(plan)
    assert plan.status == PlanStatus.INVALIDATED.value


def test_execution_record_persisted(client, db, github_fixture):
    github_fixture()
    _repo, run, incident = create_repo_and_incident(db)
    plan = RemediationPlan(
        incident_id=incident.id,
        action_id="RECOMMEND_ENV_VAR_FIX",
        title="env fix",
        parameters={"variable_name": "API_KEY"},
        risk_level="low",
        status=PlanStatus.PROPOSED.value,
        requires_approval=False,
        plan_hash="h",
    )
    db.add(plan)
    db.commit()

    resp = client.post(f"/api/v1/remediations/{plan.id}/execute", json={"actor": "tester"})
    assert resp.status_code == 200
    execution = resp.json()
    assert execution["actor"] == "tester"

    history = client.get("/api/v1/executions").json()
    assert history["total"] == 1
    assert history["items"][0]["action_id"] == "RECOMMEND_ENV_VAR_FIX"


def test_audit_log_written(client, db, github_fixture):
    github_fixture()
    _repo, _run, incident = create_repo_and_incident(db)
    client.post(f"/api/v1/incidents/{incident.id}/analyze")
    logs = client.get("/api/v1/audit-logs").json()
    assert logs["total"] >= 1
    actions = {item["action"] for item in logs["items"]}
    assert "incident.analyze" in actions
