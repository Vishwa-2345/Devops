"""End-to-end agent workflow tests using the real LangGraph orchestration."""

from __future__ import annotations

from tests.conftest import FAILURE_LOG, TEST_FAILURE_LOG, create_repo_and_incident


def test_analysis_creates_diagnosis_and_plan(client, db, github_fixture):
    github_fixture(log_text=FAILURE_LOG)
    _repo, _run, incident = create_repo_and_incident(db)

    resp = client.post(f"/api/v1/incidents/{incident.id}/analyze")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert len(body["diagnoses"]) == 1
    assert body["diagnoses"][0]["category"] == "missing_npm_dependencies"
    assert body["diagnoses"][0]["provider"] == "rules"
    assert len(body["remediation_plans"]) == 1
    plan = body["remediation_plans"][0]
    assert plan["action_id"] == "RECOMMEND_DEPENDENCY_FIX"
    assert plan["requires_approval"] is False
    assert body["failure_category"] == "missing_npm_dependencies"


def test_agent_events_are_recorded(client, db, github_fixture):
    github_fixture(log_text=FAILURE_LOG)
    _repo, _run, incident = create_repo_and_incident(db)
    client.post(f"/api/v1/incidents/{incident.id}/analyze")

    events = client.get(f"/api/v1/agents/activity?incident_id={incident.id}").json()
    agents = {e["agent"] for e in events["items"]}
    assert {"monitoring", "diagnosis", "planning", "risk_evaluation"} <= agents


def test_approval_required_flow_and_rerun(client, db, github_fixture):
    github_fixture(log_text=TEST_FAILURE_LOG)
    _repo, run, incident = create_repo_and_incident(db, run_id=9001)

    analysis = client.post(f"/api/v1/incidents/{incident.id}/analyze").json()
    plan = analysis["remediation_plans"][-1]
    assert plan["action_id"] == "RERUN_WORKFLOW"
    assert plan["requires_approval"] is True
    assert plan["status"] == "awaiting_approval"

    # Execution must be blocked before approval.
    blocked = client.post(f"/api/v1/remediations/{plan['id']}/execute", json={})
    assert blocked.status_code == 403

    # Approve, then execute.
    approved = client.post(
        f"/api/v1/remediations/{plan['id']}/approve",
        json={"decided_by": "tester", "reason": "looks safe"},
    )
    assert approved.status_code == 200
    assert approved.json()["decision"] == "approved"

    executed = client.post(f"/api/v1/remediations/{plan['id']}/execute", json={})
    assert executed.status_code == 200, executed.text
    execution = executed.json()
    assert execution["status"] == "succeeded"
    assert execution["verification_status"] == "verified"
    assert execution["verification_details"]["outcome"] == "rerun_accepted"

    # Duplicate execution protection.
    duplicate = client.post(f"/api/v1/remediations/{plan['id']}/execute", json={})
    assert duplicate.status_code == 409


def test_auto_executable_recommendation(client, db, github_fixture):
    github_fixture(log_text=FAILURE_LOG)
    _repo, _run, incident = create_repo_and_incident(db)
    analysis = client.post(f"/api/v1/incidents/{incident.id}/analyze").json()
    plan = analysis["remediation_plans"][-1]
    assert plan["requires_approval"] is False

    executed = client.post(f"/api/v1/remediations/{plan['id']}/execute", json={})
    assert executed.status_code == 200, executed.text
    body = executed.json()
    assert body["status"] == "succeeded"
    assert body["result"]["kind"] == "recommendation"
    assert body["verification_status"] == "unverified"

    # A successfully executed recommendation cannot be auto-verified; the
    # incident must reach a terminal-ish state (open) rather than being stuck
    # in 'verifying' forever.
    incident_after = client.get(f"/api/v1/incidents/{incident.id}").json()
    assert incident_after["status"] == "open"


def test_rerun_success_resolves_incident(client, db, github_fixture):
    github_fixture(
        log_text=TEST_FAILURE_LOG,
        run_detail={
            "id": 9001,
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/octocat/demo-app/actions/runs/9001",
        },
    )
    _repo, _run, incident = create_repo_and_incident(db, run_id=9001)
    plan = client.post(f"/api/v1/incidents/{incident.id}/analyze").json()["remediation_plans"][-1]
    client.post(f"/api/v1/remediations/{plan['id']}/approve", json={"decided_by": "tester"})

    executed = client.post(f"/api/v1/remediations/{plan['id']}/execute", json={})
    assert executed.status_code == 200, executed.text
    execution = executed.json()
    assert execution["verification_status"] == "verified"
    assert execution["verification_details"]["outcome"] == "success"

    incident_after = client.get(f"/api/v1/incidents/{incident.id}").json()
    assert incident_after["status"] == "resolved"
    assert incident_after["resolved_at"] is not None


def test_reject_flow(client, db, github_fixture):
    github_fixture(log_text=TEST_FAILURE_LOG)
    _repo, _run, incident = create_repo_and_incident(db)
    plan = client.post(f"/api/v1/incidents/{incident.id}/analyze").json()["remediation_plans"][-1]

    rejected = client.post(
        f"/api/v1/remediations/{plan['id']}/reject", json={"decided_by": "tester"}
    )
    assert rejected.status_code == 200
    assert rejected.json()["decision"] == "rejected"

    blocked = client.post(f"/api/v1/remediations/{plan['id']}/execute", json={})
    assert blocked.status_code == 403


def test_dashboard_summary_reflects_data(client, db, github_fixture):
    github_fixture(log_text=FAILURE_LOG)
    create_repo_and_incident(db)
    summary = client.get("/api/v1/dashboard/summary").json()
    assert summary["counts"]["repositories"] == 1
    assert summary["counts"]["open_incidents"] == 1
    assert summary["counts"]["failed_runs"] == 1
    assert summary["llm_provider"] == "rules"
