"""Repository synchronization service (GitHub -> local database)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.github import GitHubClient, GitHubError
from app.github.normalizer import is_failed, normalize_repository, normalize_workflow_run
from app.models import Incident, IncidentStatus, Repository, WorkflowRun, utcnow
from app.services.audit import record_audit, record_event
from app.services.github_provider import get_github_client


class SyncError(Exception):
    pass


def _category_placeholder(conclusion: str | None) -> str:
    return "unknown"


def sync_repository(
    db: Session, repository: Repository, client: GitHubClient | None = None
) -> dict:
    """Fetch metadata + recent workflow runs and persist them.

    Creates incidents for newly observed failed runs, idempotently.
    """
    client = client or get_github_client()
    try:
        raw_repo = client.get_repository(repository.owner, repository.name)
        meta = normalize_repository(raw_repo)
        for key, value in meta.items():
            setattr(repository, key, value)

        runs = client.list_workflow_runs(repository.owner, repository.name)

        runs_created = runs_updated = incidents_created = 0
        for raw_run in runs:
            data = normalize_workflow_run(raw_run)
            if data.get("github_run_id") is None:
                continue
            existing = db.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.repository_id == repository.id,
                    WorkflowRun.github_run_id == data["github_run_id"],
                )
            )
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                run_obj = existing
                runs_updated += 1
            else:
                run_obj = WorkflowRun(repository_id=repository.id, **data)
                db.add(run_obj)
                db.flush()
                runs_created += 1

            if is_failed(run_obj.conclusion):
                existing_incident = db.scalar(
                    select(Incident).where(
                        Incident.repository_id == repository.id,
                        Incident.workflow_run_id == run_obj.id,
                    )
                )
                if existing_incident is None:
                    incident = Incident(
                        repository_id=repository.id,
                        workflow_run_id=run_obj.id,
                        title=f"Workflow '{run_obj.workflow_name}' failed"
                        + (f" on {run_obj.head_branch}" if run_obj.head_branch else ""),
                        failure_category=_category_placeholder(run_obj.conclusion),
                        severity="medium",
                        status=IncidentStatus.OPEN.value,
                        summary=f"GitHub Actions reported conclusion '{run_obj.conclusion}'.",
                    )
                    db.add(incident)
                    db.flush()
                    incidents_created += 1
                    record_event(
                        db,
                        agent="monitoring",
                        event_type="incident_created",
                        message=f"Detected failed run #{run_obj.run_number or run_obj.github_run_id} "
                        f"({run_obj.conclusion}).",
                        incident_id=incident.id,
                        data={"run_id": run_obj.github_run_id},
                    )

        repository.last_synced_at = utcnow()
        repository.last_sync_error = None
        db.commit()
        record_audit(
            db,
            action="repository.sync",
            entity_type="repository",
            entity_id=repository.id,
            details={
                "runs_fetched": len(runs),
                "runs_created": runs_created,
                "runs_updated": runs_updated,
                "incidents_created": incidents_created,
            },
        )
        return {
            "repository_id": repository.id,
            "runs_fetched": len(runs),
            "runs_created": runs_created,
            "runs_updated": runs_updated,
            "incidents_created": incidents_created,
            "incidents_updated": 0,
            "message": "Synchronization complete.",
        }
    except GitHubError as exc:
        repository.last_sync_error = exc.message
        db.commit()
        raise SyncError(exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        repository.last_sync_error = str(exc)
        db.commit()
        raise SyncError(f"Unexpected synchronization error: {exc}") from exc
