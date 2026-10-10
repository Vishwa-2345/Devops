"""Optional background polling service.

Disabled by default (POLL_INTERVAL_SECONDS=0). When enabled, a single scheduler
instance syncs all repositories on an interval. Duplicate schedulers are
prevented with a module-level guard.
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import Repository
from app.services.sync import SyncError, sync_repository

logger = logging.getLogger(__name__)

_scheduler: Scheduler | None = None
_lock = threading.Lock()


class Scheduler:
    def __init__(self, interval_seconds: int) -> None:
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="selfhealops-poller", daemon=True)
        self._thread.start()
        logger.info("Polling scheduler started (interval=%ss).", self.interval_seconds)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            db = SessionLocal()
            try:
                repos = db.scalars(select(Repository)).all()
                for repo in repos:
                    try:
                        sync_repository(db, repo)
                    except SyncError as exc:
                        logger.warning("Scheduled sync failed for %s: %s", repo.full_name, exc)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Scheduled sync cycle failed: %s", exc)
            finally:
                db.close()


def start_scheduler_if_enabled() -> Scheduler | None:
    global _scheduler
    interval = get_settings().poll_interval_seconds
    if interval <= 0:
        return None
    with _lock:
        if _scheduler is not None and _scheduler._thread and _scheduler._thread.is_alive():
            return _scheduler
        _scheduler = Scheduler(interval)
        _scheduler.start()
        return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    with _lock:
        if _scheduler is not None:
            _scheduler.stop()
            _scheduler = None
