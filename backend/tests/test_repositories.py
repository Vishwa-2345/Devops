"""Repository CRUD, sync and workflow endpoint tests (GitHub mocked)."""

from __future__ import annotations


def test_create_repository_requires_valid_url(client):
    resp = client.post("/api/v1/repositories", json={"url": "https://gitlab.com/a/b"})
    assert resp.status_code == 422


def test_create_repository_and_list(client, github_fixture):
    github_fixture()
    resp = client.post("/api/v1/repositories", json={"url": "https://github.com/octocat/demo-app"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["full_name"] == "octocat/demo-app"

    listing = client.get("/api/v1/repositories")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1


def test_duplicate_repository_conflict(client, github_fixture):
    github_fixture()
    payload = {"url": "https://github.com/octocat/demo-app"}
    assert client.post("/api/v1/repositories", json=payload).status_code == 201
    assert client.post("/api/v1/repositories", json=payload).status_code == 409


def test_get_and_delete_repository(client, github_fixture):
    github_fixture()
    created = client.post(
        "/api/v1/repositories", json={"url": "https://github.com/octocat/demo-app"}
    ).json()
    rid = created["id"]

    fetched = client.get(f"/api/v1/repositories/{rid}")
    assert fetched.status_code == 200

    deleted = client.delete(f"/api/v1/repositories/{rid}")
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/repositories/{rid}").status_code == 404


def test_github_404_on_create(client, github_fixture):
    github_fixture()
    resp = client.post("/api/v1/repositories", json={"url": "https://github.com/octocat/missing"})
    assert resp.status_code == 404


def test_sync_creates_runs_and_incidents(client, github_fixture):
    github_fixture()
    created = client.post(
        "/api/v1/repositories", json={"url": "https://github.com/octocat/demo-app"}
    ).json()
    rid = created["id"]

    sync = client.post(f"/api/v1/repositories/{rid}/sync")
    assert sync.status_code == 200, sync.text
    body = sync.json()
    assert body["runs_fetched"] == 2
    assert body["runs_created"] == 2
    assert body["incidents_created"] == 1  # only the failed run

    workflows = client.get(f"/api/v1/repositories/{rid}/workflows")
    assert workflows.status_code == 200
    assert workflows.json()["total"] == 2

    failed = client.get(f"/api/v1/repositories/{rid}/workflows?only_failed=true")
    assert failed.json()["total"] == 1


def test_duplicate_incident_prevention(client, github_fixture):
    github_fixture()
    rid = client.post(
        "/api/v1/repositories", json={"url": "https://github.com/octocat/demo-app"}
    ).json()["id"]

    first = client.post(f"/api/v1/repositories/{rid}/sync").json()
    second = client.post(f"/api/v1/repositories/{rid}/sync").json()

    assert first["incidents_created"] == 1
    assert second["incidents_created"] == 0  # duplicate prevented

    incidents = client.get("/api/v1/incidents")
    assert incidents.json()["total"] == 1
