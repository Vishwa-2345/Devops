"""Pytest fixtures: isolated test database + mocked GitHub client.

Environment is configured BEFORE importing the app so the engine points at a
throwaway SQLite file. Tests never require real GitHub credentials or Ollama.
"""

from __future__ import annotations

import json
import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="selfhealops-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test.db"
os.environ["LLM_PROVIDER"] = "rules"
os.environ["POLL_INTERVAL_SECONDS"] = "0"
os.environ["GITHUB_TOKEN"] = ""

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.github import GitHubClient  # noqa: E402
from app.main import app  # noqa: E402
from app.services.github_provider import set_github_client_override  # noqa: E402

# --------------------------------------------------------------------------- #
# Dataset used by the mocked GitHub transport.
# --------------------------------------------------------------------------- #
SAMPLE_REPO = {
    "id": 123456,
    "name": "demo-app",
    "full_name": "octocat/demo-app",
    "html_url": "https://github.com/octocat/demo-app",
    "default_branch": "main",
    "description": "A demo repository",
    "private": False,
    "owner": {"login": "octocat"},
}

SAMPLE_RUNS = [
    {
        "id": 9001,
        "workflow_id": 11,
        "name": "CI",
        "run_number": 42,
        "event": "push",
        "head_branch": "main",
        "head_sha": "abc123",
        "status": "completed",
        "conclusion": "failure",
        "html_url": "https://github.com/octocat/demo-app/actions/runs/9001",
        "actor": {"login": "octocat"},
        "run_started_at": "2026-01-01T10:00:00Z",
        "updated_at": "2026-01-01T10:05:00Z",
        "created_at": "2026-01-01T10:00:00Z",
    },
    {
        "id": 9002,
        "workflow_id": 11,
        "name": "CI",
        "run_number": 41,
        "event": "push",
        "head_branch": "main",
        "head_sha": "def456",
        "status": "completed",
        "conclusion": "success",
        "html_url": "https://github.com/octocat/demo-app/actions/runs/9002",
        "actor": {"login": "octocat"},
        "run_started_at": "2026-01-01T09:00:00Z",
        "updated_at": "2026-01-01T09:04:00Z",
        "created_at": "2026-01-01T09:00:00Z",
    },
]

FAILURE_LOG = (
    "Run npm install\n"
    "npm ERR! code ERESOLVE\n"
    "npm ERR! Could not resolve dependency:\n"
    "npm ERR! ERESOLVE unable to resolve dependency tree\n"
)
TEST_FAILURE_LOG = (
    "Run npm test\nFAIL src/app.test.ts\n  ● App › renders\nTests failed: 1 failed, 2 passed\n"
)

SAMPLE_JOBS = [
    {
        "id": 555,
        "name": "build",
        "conclusion": "failure",
    }
]

DEFAULT_RUN_DETAIL = {
    "id": 9001,
    "status": "queued",
    "conclusion": None,
    "html_url": "https://github.com/octocat/demo-app/actions/runs/9001",
}


def make_transport(
    log_text: str = FAILURE_LOG, run_detail: dict | None = None
) -> httpx.MockTransport:
    detail = run_detail or DEFAULT_RUN_DETAIL

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method
        if method == "GET" and path == "/repos/octocat/demo-app":
            return httpx.Response(200, json=SAMPLE_REPO)
        if method == "GET" and path == "/repos/octocat/demo-app/actions/runs":
            return httpx.Response(200, json={"workflow_runs": SAMPLE_RUNS})
        if method == "GET" and path.endswith("/actions/runs/9001"):
            return httpx.Response(200, json=detail)
        if method == "GET" and path.endswith("/jobs"):
            return httpx.Response(200, json={"jobs": SAMPLE_JOBS})
        if method == "GET" and "/actions/jobs/" in path and path.endswith("/logs"):
            return httpx.Response(200, text=log_text)
        if method == "POST" and path.endswith("/rerun"):
            return httpx.Response(201, json={})
        if method == "GET" and path == "/repos/octocat/missing":
            return httpx.Response(404, json={"message": "Not Found"})
        return httpx.Response(404, json={"message": f"Unmocked: {method} {path}"})

    return httpx.MockTransport(handler)


def install_github(
    token: str = "ghp_testtoken000000000000000000000",
    log_text: str = FAILURE_LOG,
    run_detail: dict | None = None,
) -> GitHubClient:
    http_client = httpx.Client(
        base_url="https://api.github.com", transport=make_transport(log_text, run_detail)
    )
    client = GitHubClient(client=http_client, token=token)
    set_github_client_override(client)
    return client


@pytest.fixture(autouse=True)
def _reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    set_github_client_override(None)
    yield
    set_github_client_override(None)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def github_fixture():
    return install_github


def create_repo_and_incident(db, *, run_id: int = 9001, conclusion: str = "failure"):
    """Helper: seed a repository, a failed workflow run and an incident."""
    from app.models import Incident, IncidentStatus, Repository, WorkflowRun

    repo = Repository(
        owner="octocat",
        name="demo-app",
        full_name="octocat/demo-app",
        html_url="https://github.com/octocat/demo-app",
        default_branch="main",
        github_repo_id=123456,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    run = WorkflowRun(
        repository_id=repo.id,
        github_run_id=run_id,
        workflow_id=11,
        workflow_name="CI",
        run_number=42,
        event="push",
        head_branch="main",
        head_sha="abc123",
        status="completed",
        conclusion=conclusion,
        html_url=f"https://github.com/octocat/demo-app/actions/runs/{run_id}",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    incident = Incident(
        repository_id=repo.id,
        workflow_run_id=run.id,
        title="Workflow 'CI' failed on main",
        failure_category="unknown",
        severity="medium",
        status=IncidentStatus.OPEN.value,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return repo, run, incident


def json_body(response):
    return json.loads(response.text)
