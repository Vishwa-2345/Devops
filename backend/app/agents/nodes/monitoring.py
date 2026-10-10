"""Monitoring Agent: gather context and normalize failure logs."""

from __future__ import annotations

from app.agents.nodes.common import emit, load_incident_parts
from app.agents.state import AgentState
from app.database import SessionLocal
from app.services.github_provider import get_github_client


def monitoring_node(state: AgentState) -> AgentState:
    update: AgentState = {"phase": "monitoring", "events": state.get("events", [])}
    db = SessionLocal()
    try:
        incident, run, repo = load_incident_parts(db, state["incident_id"])
        update.update(
            {
                "repository_full_name": repo.full_name,
                "repository_owner": repo.owner,
                "repository_name": repo.name,
                "github_run_id": run.github_run_id,
                "workflow_name": run.workflow_name,
                "conclusion": run.conclusion,
                "run_url": run.html_url,
            }
        )

        logs = ""
        available = False
        note = ""
        try:
            client = get_github_client()
            result = client.collect_failure_logs(repo.owner, repo.name, run.github_run_id)
            logs, available, note = result.text, result.available, result.note
        except Exception as exc:  # noqa: BLE001 - monitoring must be resilient
            note = f"Could not retrieve logs: {exc}"

        update.update({"logs": logs, "logs_available": available, "logs_note": note})
        emit(
            db,
            state,
            agent="monitoring",
            event_type="context_loaded",
            message=(
                f"Loaded run {run.github_run_id} ({run.conclusion}). "
                + ("Failure logs retrieved." if available else f"Logs unavailable: {note}")
            ),
            data={"logs_available": available, "logs_bytes": len(logs)},
        )
        return update
    finally:
        db.close()
