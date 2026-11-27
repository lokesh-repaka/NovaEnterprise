"""Database engine, session management, and table initialization module."""

from collections.abc import Generator
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.models  # noqa: F401 - ensure all models are registered on Base.metadata
from backend.app.core.config import get_settings
from backend.app.models.base import Base


@lru_cache
def _get_cached_engine(database_url: str) -> Engine:
    """Create or return a cached SQLAlchemy engine for a resolved connection string."""
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {}
    if "sqlite" in database_url:
        connect_args["check_same_thread"] = False
        if ":memory:" in database_url:
            engine_kwargs["poolclass"] = StaticPool
        else:
            db_path_str = database_url.split("sqlite:///")[-1]
            if db_path_str:
                Path(db_path_str).parent.mkdir(parents=True, exist_ok=True)

    return create_engine(database_url, connect_args=connect_args, **engine_kwargs)


def get_engine(database_url: str | None = None) -> Engine:
    """Create or return a cached SQLAlchemy engine."""
    url = database_url if database_url is not None else get_settings().database_url
    return _get_cached_engine(url)


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Create a sessionmaker factory bound to the active engine."""
    if engine is None:
        engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(engine: Engine | None = None) -> None:
    """Create all registered database tables from SQLAlchemy metadata."""
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(bind=engine)


def get_db(database_url: str | None = None) -> Generator[Session, None, None]:
    """FastAPI dependency yielding a transactional database session."""
    engine = get_engine(database_url)
    session_factory = get_session_factory(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
