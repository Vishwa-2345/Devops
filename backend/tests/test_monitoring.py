"""Monitoring scheduler tests: polling interval behaviour and lifecycle.

These exercise the real background polling service (no network): sync is
replaced with a spy so the test observes that the scheduler honours the
configured interval rather than asserting on real GitHub calls.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

from app.services import monitoring
from app.services.monitoring import start_scheduler_if_enabled, stop_scheduler
from tests.conftest import create_repo_and_incident


def test_scheduler_disabled_when_interval_zero(monkeypatch):
    stop_scheduler()
    monkeypatch.setattr(
        monitoring, "get_settings", lambda: SimpleNamespace(poll_interval_seconds=0)
    )
    try:
        assert start_scheduler_if_enabled() is None
    finally:
        stop_scheduler()


def test_scheduler_polls_on_configured_interval(monkeypatch, db):
    stop_scheduler()
    create_repo_and_incident(db)

    called = threading.Event()

    def fake_sync(session, repo):
        called.set()
        return {"created": 0}

    monkeypatch.setattr(monitoring, "sync_repository", fake_sync)
    monkeypatch.setattr(
        monitoring, "get_settings", lambda: SimpleNamespace(poll_interval_seconds=0.05)
    )

    scheduler = start_scheduler_if_enabled()
    try:
        assert scheduler is not None
        assert called.wait(timeout=2.0), "scheduler never ran a sync cycle"
    finally:
        stop_scheduler()

    assert scheduler._thread is None or not scheduler._thread.is_alive()


def test_scheduler_start_is_idempotent(monkeypatch):
    stop_scheduler()
    monkeypatch.setattr(
        monitoring, "get_settings", lambda: SimpleNamespace(poll_interval_seconds=60)
    )
    scheduler_one = start_scheduler_if_enabled()
    try:
        scheduler_two = start_scheduler_if_enabled()
        assert scheduler_one is not None
        assert scheduler_one is scheduler_two
    finally:
        stop_scheduler()
