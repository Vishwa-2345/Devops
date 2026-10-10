"""Health and database initialization tests."""

from __future__ import annotations

from sqlalchemy import inspect

from app.database import Base, engine


def test_root_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_versioned_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] == "ok"
    assert "github_configured" in body


def test_database_tables_created():
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    expected = {
        "repositories",
        "workflow_runs",
        "incidents",
        "diagnoses",
        "remediation_plans",
        "approvals",
        "executions",
        "agent_events",
        "audit_logs",
    }
    assert expected.issubset(tables)


def test_database_persistence(db):
    from app.models import Repository

    repo = Repository(
        owner="octocat",
        name="persist-app",
        full_name="octocat/persist-app",
        html_url="https://github.com/octocat/persist-app",
        default_branch="main",
    )
    db.add(repo)
    db.commit()

    from app.database import SessionLocal

    fresh = SessionLocal()
    try:
        found = fresh.query(Repository).filter_by(full_name="octocat/persist-app").first()
        assert found is not None
        assert found.owner == "octocat"
    finally:
        fresh.close()
