"""Diagnosis Agent: LLM/rule-based failure diagnosis."""

from __future__ import annotations

from app.agents.nodes.common import emit, load_incident_parts
from app.agents.state import AgentState
from app.database import SessionLocal
from app.llm import DiagnosisContext, get_provider
from app.models import Diagnosis, IncidentStatus


def diagnosis_node(state: AgentState) -> AgentState:
    db = SessionLocal()
    try:
        incident, _run, repo = load_incident_parts(db, state["incident_id"])
        context = DiagnosisContext(
            repository_full_name=repo.full_name,
            workflow_name=state.get("workflow_name", "") or repo.full_name,
            conclusion=state.get("conclusion"),
            logs=state.get("logs", ""),
            run_url=state.get("run_url"),
            failure_hint=state.get("conclusion") or "",
        )
        result = get_provider().diagnose(context)

        diagnosis = Diagnosis(
            incident_id=incident.id,
            provider=result.provider,
            model=result.model,
            category=result.category,
            summary=result.summary,
            probable_cause=result.probable_cause,
            suggested_next_step=result.suggested_next_step,
            confidence=result.confidence,
            evidence=result.evidence,
            automatable=result.automatable,
            raw_output=result.raw,
        )
        db.add(diagnosis)

        incident.failure_category = result.category
        incident.summary = result.summary
        incident.status = IncidentStatus.DIAGNOSED.value
        if result.category in {"k8s_oomkilled", "k8s_crashloopbackoff", "authentication_failure"}:
            incident.severity = "high"
        db.commit()

        emit(
            db,
            state,
            agent="diagnosis",
            event_type="diagnosis_complete",
            message=(
                f"Diagnosed '{result.category}' via {result.provider} "
                f"(confidence {result.confidence:.2f})."
            ),
            data={"category": result.category, "provider": result.provider},
        )
        return {
            "phase": "diagnosis",
            "diagnosis": result.model_dump(),
            "events": state.get("events", []),
        }
    finally:
        db.close()
