"""Pydantic schemas (request/response models) for the SelfHealOps API."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Repositories
# --------------------------------------------------------------------------- #
class RepositoryCreate(BaseModel):
    url: str = Field(..., min_length=10, max_length=300)


class RepositoryOut(ORMModel):
    id: int
    owner: str
    name: str
    full_name: str
    html_url: str
    default_branch: str
    description: str | None = None
    private: bool
    github_repo_id: int | None = None
    source: str
    last_synced_at: datetime | None = None
    last_sync_error: str | None = None
    created_at: datetime


class SyncResult(BaseModel):
    repository_id: int
    runs_fetched: int
    runs_created: int
    runs_updated: int
    incidents_created: int
    incidents_updated: int
    message: str


# --------------------------------------------------------------------------- #
# Workflow runs
# --------------------------------------------------------------------------- #
class WorkflowRunOut(ORMModel):
    id: int
    repository_id: int
    github_run_id: int
    workflow_name: str
    run_number: int | None = None
    event: str | None = None
    head_branch: str | None = None
    head_sha: str | None = None
    status: str
    conclusion: str | None = None
    html_url: str | None = None
    actor: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Diagnoses / plans / approvals / executions / events
# --------------------------------------------------------------------------- #
class DiagnosisOut(ORMModel):
    id: int
    incident_id: int
    provider: str
    model: str | None = None
    category: str
    summary: str
    probable_cause: str | None = None
    suggested_next_step: str | None = None
    confidence: float
    evidence: list | None = None
    automatable: bool
    created_at: datetime


class RemediationPlanOut(ORMModel):
    id: int
    incident_id: int
    action_id: str
    title: str
    description: str | None = None
    parameters: dict
    risk_level: str
    status: str
    requires_approval: bool
    expected_effect: str | None = None
    verification_method: str | None = None
    plan_hash: str
    created_at: datetime
    updated_at: datetime


class ApprovalOut(ORMModel):
    id: int
    remediation_plan_id: int
    decision: str
    decided_by: str
    reason: str | None = None
    plan_hash: str
    created_at: datetime


class ExecutionOut(ORMModel):
    id: int
    remediation_plan_id: int
    action_id: str
    status: str
    actor: str
    parameters: dict | None = None
    result: dict | None = None
    error: str | None = None
    verification_status: str
    verification_details: dict | None = None
    started_at: datetime
    completed_at: datetime | None = None


class AgentEventOut(ORMModel):
    id: int
    incident_id: int | None = None
    run_id: str | None = None
    agent: str
    event_type: str
    message: str
    data: dict | None = None
    created_at: datetime


class AuditLogOut(ORMModel):
    id: int
    actor: str
    action: str
    entity_type: str
    entity_id: str | None = None
    details: dict | None = None
    created_at: datetime


class IncidentOut(ORMModel):
    id: int
    repository_id: int
    workflow_run_id: int
    title: str
    failure_category: str
    severity: str
    status: str
    summary: str | None = None
    detected_at: datetime
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class IncidentDetailOut(IncidentOut):
    repository: RepositoryOut | None = None
    workflow_run: WorkflowRunOut | None = None
    diagnoses: list[DiagnosisOut] = []
    remediation_plans: list[RemediationPlanOut] = []


# --------------------------------------------------------------------------- #
# Approvals / execution actions
# --------------------------------------------------------------------------- #
class ApprovalDecision(BaseModel):
    decided_by: str = Field(default="local-user", max_length=200)
    reason: str | None = Field(default=None, max_length=2000)


class ExecuteRequest(BaseModel):
    actor: str = Field(default="local-user", max_length=200)


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
class DashboardCounts(BaseModel):
    repositories: int
    workflow_runs: int
    failed_runs: int
    open_incidents: int
    pending_approvals: int
    successful_remediations: int


class RecentIncident(BaseModel):
    id: int
    title: str
    failure_category: str
    severity: str
    status: str
    repository: str
    detected_at: datetime


class SuccessStat(BaseModel):
    label: str
    total: int


class DashboardSummary(BaseModel):
    counts: DashboardCounts
    recent_incidents: list[RecentIncident]
    recent_events: list[AgentEventOut]
    workflow_stats: list[SuccessStat]
    github_connected: bool
    llm_provider: str
    llm_available: bool


# --------------------------------------------------------------------------- #
# Settings / integration status
# --------------------------------------------------------------------------- #
class IntegrationStatus(BaseModel):
    name: str
    configured: bool
    status: str
    detail: str


class SettingsStatus(BaseModel):
    app_version: str
    environment: str
    github: IntegrationStatus
    llm: IntegrationStatus
    polling_enabled: bool
    poll_interval_seconds: int
    database: str
    cors_origins: list[str]


# --------------------------------------------------------------------------- #
# Generic
# --------------------------------------------------------------------------- #
class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class Message(BaseModel):
    message: str


class ErrorBody(BaseModel):
    detail: str
    code: str | None = None
