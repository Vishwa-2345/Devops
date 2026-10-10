"""Database engine, session management and initialization."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _resolve_sqlite_path(url: str) -> str:
    """Ensure relative SQLite paths resolve against the backend directory,
    and that the parent directory exists."""
    if not url.startswith("sqlite"):
        return url
    # sqlite:///./data/x.db  -> ./data/x.db
    prefix = "sqlite:///"
    if url.startswith(prefix + "/"):
        # absolute path form sqlite:////data/x.db
        return url
    if url.startswith(prefix):
        rel = url[len(prefix) :]
        if rel.startswith("./"):
            rel = rel[2:]
        path = (Path(__file__).resolve().parent.parent / rel).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}"
    return url


def _build_engine(database_url: str) -> Engine:
    url = _resolve_sqlite_path(database_url)
    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    engine = create_engine(url, connect_args=connect_args, future=True)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


_settings = get_settings()
engine: Engine = _build_engine(_settings.database_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def init_db() -> None:
    """Create all tables. Import models first so metadata is populated."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
