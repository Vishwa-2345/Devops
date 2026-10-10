"""Typed state for the LangGraph self-healing agent workflow."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class AgentState(TypedDict, total=False):
    # routing
    entry: Literal["monitoring", "planning", "remediation"]
    execute_now: bool
    actor: str
    phase: str

    # context
    incident_id: int
    plan_id: int | None
    repository_full_name: str
    repository_owner: str
    repository_name: str
    github_run_id: int
    workflow_name: str
    conclusion: str | None
    run_url: str | None

    # logs
    logs: str
    logs_available: bool
    logs_note: str

    # analysis artifacts
    diagnosis: dict[str, Any] | None
    plan: dict[str, Any] | None
    risk_level: str | None
    requires_approval: bool
    approval_status: str | None  # approved | rejected | pending | not_required

    # execution
    execution_result: dict[str, Any] | None
    verification: dict[str, Any] | None

    # bookkeeping
    events: list[dict[str, Any]]
    error: str | None
    next_step: str
