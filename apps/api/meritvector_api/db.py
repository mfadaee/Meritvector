"""Database engine and session management (PostgreSQL in Docker, SQLite for local tests)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from meritvector_api.models import Base
from meritvector_api.settings import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def configure(url: str | None = None) -> Engine:
    global _engine, _SessionLocal
    url = url or get_settings().database_url
    kwargs = {}
    if url.startswith("sqlite"):
        path = url.split("///", 1)[-1]
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
    _engine = create_engine(url, **kwargs)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def engine() -> Engine:
    return _engine or configure()


def create_all() -> None:
    Base.metadata.create_all(engine())


def session() -> Session:
    if _SessionLocal is None:
        configure()
    assert _SessionLocal is not None
    return _SessionLocal()


def get_db() -> Iterator[Session]:
    db = session()
    try:
        yield db
    finally:
        db.close()
