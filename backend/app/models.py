"""SQLAlchemy ORM models for SelfHealOps."""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    DIAGNOSING = "diagnosing"
    DIAGNOSED = "diagnosed"
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    FAILED = "failed"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PlanStatus(str, enum.Enum):
    PROPOSED = "proposed"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    INVALIDATED = "invalidated"


class ExecutionStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("full_name", name="uq_repository_full_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    full_name: Mapped[str] = mapped_column(String(400), unique=True, index=True)
    html_url: Mapped[str] = mapped_column(String(500))
    default_branch: Mapped[str] = mapped_column(String(200), default="main")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    private: Mapped[bool] = mapped_column(Boolean, default=False)
    github_repo_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="github")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    workflow_runs: Mapped[list[WorkflowRun]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    incidents: Mapped[list[Incident]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint("repository_id", "github_run_id", name="uq_workflow_run_repo_run"),
        Index("ix_workflow_runs_repo_conclusion", "repository_id", "conclusion"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    github_run_id: Mapped[int] = mapped_column(Integer, index=True)
    workflow_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workflow_name: Mapped[str] = mapped_column(String(300), default="unknown")
    run_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event: Mapped[str | None] = mapped_column(String(100), nullable=True)
    head_branch: Mapped[str | None] = mapped_column(String(300), nullable=True)
    head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    conclusion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    html_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    actor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at_gh: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    repository: Mapped[Repository] = relationship(back_populates="workflow_runs")
    incident: Mapped[Incident | None] = relationship(back_populates="workflow_run", uselist=False)

    @property
    def failed(self) -> bool:
        return self.conclusion in {"failure", "timed_out", "startup_failure", "cancelled"}


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("repository_id", "workflow_run_id", name="uq_incident_repo_run"),
        Index("ix_incidents_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    workflow_run_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    failure_category: Mapped[str] = mapped_column(String(100), default="unknown")
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(40), default=IncidentStatus.OPEN.value)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    repository: Mapped[Repository] = relationship(back_populates="incidents")
    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="incident")
    diagnoses: Mapped[list[Diagnosis]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    remediation_plans: Mapped[list[RemediationPlan]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    agent_events: Mapped[list[AgentEvent]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )

    @property
    def latest_diagnosis(self) -> Diagnosis | None:
        return self.diagnoses[-1] if self.diagnoses else None

    @property
    def latest_plan(self) -> RemediationPlan | None:
        return self.remediation_plans[-1] if self.remediation_plans else None


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40), default="rules")
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text)
    probable_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_next_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    automatable: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    incident: Mapped[Incident] = relationship(back_populates="diagnoses")


class RemediationPlan(Base):
    __tablename__ = "remediation_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    action_id: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_level: Mapped[str] = mapped_column(String(20), default=RiskLevel.LOW.value)
    status: Mapped[str] = mapped_column(String(30), default=PlanStatus.PROPOSED.value)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    expected_effect: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    incident: Mapped[Incident] = relationship(back_populates="remediation_plans")
    approvals: Mapped[list[Approval]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    executions: Mapped[list[Execution]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )

    @property
    def latest_approval(self) -> Approval | None:
        return self.approvals[-1] if self.approvals else None


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    remediation_plan_id: Mapped[int] = mapped_column(
        ForeignKey("remediation_plans.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(20))  # approved | rejected
    decided_by: Mapped[str] = mapped_column(String(200), default="local-user")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    plan: Mapped[RemediationPlan] = relationship(back_populates="approvals")


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    remediation_plan_id: Mapped[int] = mapped_column(
        ForeignKey("remediation_plans.id", ondelete="CASCADE"), index=True
    )
    action_id: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default=ExecutionStatus.RUNNING.value)
    actor: Mapped[str] = mapped_column(String(200), default="local-user")
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(30), default=VerificationStatus.PENDING.value
    )
    verification_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    plan: Mapped[RemediationPlan] = relationship(back_populates="executions")


class AgentEvent(Base):
    __tablename__ = "agent_events"
    __table_args__ = (Index("ix_agent_events_incident_created", "incident_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    run_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    agent: Mapped[str] = mapped_column(String(60))
    event_type: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    incident: Mapped[Incident | None] = relationship(back_populates="agent_events")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(200), default="local-user")
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
