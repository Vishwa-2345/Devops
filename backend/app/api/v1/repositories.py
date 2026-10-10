"""Repository endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.github import GitHubError
from app.github.normalizer import normalize_repository
from app.models import Repository, WorkflowRun
from app.schemas import Page, RepositoryCreate, RepositoryOut, SyncResult, WorkflowRunOut
from app.security import InvalidRepositoryURLError, validate_repository_url
from app.services.audit import record_audit
from app.services.github_provider import get_github_client
from app.services.sync import SyncError, sync_repository

router = APIRouter(prefix="/repositories", tags=["repositories"])


def get_repository_or_404(db: Session, repository_id: int) -> Repository:
    repo = db.get(Repository, repository_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository {repository_id} not found.")
    return repo


@router.get("", response_model=Page[RepositoryOut])
def list_repositories(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[RepositoryOut]:
    total = db.scalar(select(func.count()).select_from(Repository)) or 0
    rows = db.scalars(
        select(Repository).order_by(Repository.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return Page[RepositoryOut](
        items=[RepositoryOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=RepositoryOut, status_code=status.HTTP_201_CREATED)
def create_repository(payload: RepositoryCreate, db: Session = Depends(get_db)) -> RepositoryOut:
    try:
        owner, name = validate_repository_url(payload.url)
    except InvalidRepositoryURLError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    full_name = f"{owner}/{name}"
    existing = db.scalar(select(Repository).where(Repository.full_name == full_name))
    if existing:
        raise HTTPException(status_code=409, detail=f"Repository '{full_name}' is already tracked.")

    repo = Repository(
        owner=owner,
        name=name,
        full_name=full_name,
        html_url=f"https://github.com/{full_name}",
        default_branch="main",
    )

    client = get_github_client()
    try:
        meta = normalize_repository(client.get_repository(owner, name))
        for key, value in meta.items():
            setattr(repo, key, value)
    except GitHubError as exc:
        if exc.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Repository not found on GitHub or not accessible with current credentials.",
            ) from exc
        # Rate-limited / unconfigured / transient: still track it and surface the error.
        repo.last_sync_error = exc.message

    db.add(repo)
    db.commit()
    db.refresh(repo)
    record_audit(
        db,
        action="repository.create",
        entity_type="repository",
        entity_id=repo.id,
        details={"full_name": repo.full_name},
    )
    return RepositoryOut.model_validate(repo)


@router.get("/{repository_id}", response_model=RepositoryOut)
def get_repository(repository_id: int, db: Session = Depends(get_db)) -> RepositoryOut:
    return RepositoryOut.model_validate(get_repository_or_404(db, repository_id))


@router.delete("/{repository_id}", status_code=status.HTTP_200_OK)
def delete_repository(repository_id: int, db: Session = Depends(get_db)) -> dict:
    repo = get_repository_or_404(db, repository_id)
    full_name = repo.full_name
    db.delete(repo)
    db.commit()
    record_audit(
        db,
        action="repository.delete",
        entity_type="repository",
        entity_id=repository_id,
        details={"full_name": full_name},
    )
    return {"message": f"Repository '{full_name}' removed."}


@router.post("/{repository_id}/sync", response_model=SyncResult)
def sync_one(repository_id: int, db: Session = Depends(get_db)) -> SyncResult:
    repo = get_repository_or_404(db, repository_id)
    try:
        result = sync_repository(db, repo)
    except SyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SyncResult(**result)


@router.get("/{repository_id}/workflows", response_model=Page[WorkflowRunOut])
def repository_workflows(
    repository_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    only_failed: bool = Query(False),
) -> Page[WorkflowRunOut]:
    get_repository_or_404(db, repository_id)
    query = select(WorkflowRun).where(WorkflowRun.repository_id == repository_id)
    count_query = (
        select(func.count())
        .select_from(WorkflowRun)
        .where(WorkflowRun.repository_id == repository_id)
    )
    if only_failed:
        failed = ("failure", "timed_out", "startup_failure", "cancelled")
        query = query.where(WorkflowRun.conclusion.in_(failed))
        count_query = count_query.where(WorkflowRun.conclusion.in_(failed))
    total = db.scalar(count_query) or 0
    rows = db.scalars(
        query.order_by(WorkflowRun.created_at_gh.desc().nullslast()).limit(limit).offset(offset)
    ).all()
    return Page[WorkflowRunOut](
        items=[WorkflowRunOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
