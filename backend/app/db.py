"""SQLite database configuration and session dependency.

SQLite WAL is persistent on disk. It is intentionally not enabled for in-memory
SQLite connections (which do not support WAL). All access stays local.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def default_database_url() -> str:
    root = Path(__file__).resolve().parents[1]
    path = root / "data" / "blueprint.sqlite3"
    return "sqlite:///" + path.as_posix()


def build_engine(url: str | None = None) -> Engine:
    database_url = url or os.getenv("BLUEPRINT_DATABASE_URL") or default_database_url()
    if not database_url.startswith("sqlite:"):
        raise ValueError("BS-M2 supports only local SQLite database URLs")
    if database_url.startswith("sqlite:///") and ":memory:" not in database_url:
        location = database_url.removeprefix("sqlite:///").split("?", 1)[0]
        Path(location).resolve().parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, connect_args={"check_same_thread": False}, future=True)

    @event.listens_for(engine, "connect")
    def sqlite_connection_setup(connection: object, _: object) -> None:
        # None lets SQLAlchemy emit BEGIN itself, so writers can take an immediate lock.
        connection.isolation_level = None  # type: ignore[attr-defined]
        cursor = connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        listed = cursor.execute("PRAGMA database_list").fetchone()
        if listed and listed[2] not in ("", ":memory:"):
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    @event.listens_for(engine, "begin")
    def sqlite_begin_immediate(connection: object) -> None:
        connection.exec_driver_sql("BEGIN IMMEDIATE")  # type: ignore[attr-defined]

    return engine


def init_database(engine: Engine) -> None:
    # Import models to register all tables with Base.metadata.
    from . import models  # noqa: F401

    with engine.connect() as connection:
        database_name = connection.exec_driver_sql("PRAGMA database_list").fetchone()
        # File-backed SQLite supports WAL. In-memory databases do not.
        if database_name and database_name[2] not in ("", ":memory:"):
            journal_mode = connection.exec_driver_sql("PRAGMA journal_mode=WAL").scalar()
            if str(journal_mode).lower() != "wal":
                raise RuntimeError(f"Expected WAL journal mode, got {journal_mode!r}")
        connection.commit()
    Base.metadata.create_all(engine)
    from .migrations import apply_migrations
    from .services.media_store import ensure_media_root

    apply_migrations(engine)
    ensure_media_root()


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session
