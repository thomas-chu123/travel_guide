from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base


def _sqlite_connect_args(database_url: str) -> dict[str, bool]:
    return {"check_same_thread": False} if database_url.startswith("sqlite") else {}


def _ensure_sqlite_directory(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    database_path = database_url.removeprefix("sqlite:///")
    if database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)


def _new_engine(database_url: str) -> Engine:
    _ensure_sqlite_directory(database_url)
    return create_engine(database_url, connect_args=_sqlite_connect_args(database_url), future=True)


engine = _new_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def configure_database(database_url: str) -> None:
    """Replace the engine for tests or future database-provider migration."""
    global engine, SessionLocal
    engine.dispose()
    engine = _new_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def create_local_schema() -> None:
    """Create the local development schema when migrations have not run yet."""
    Base.metadata.create_all(bind=engine)


def get_session_factory() -> sessionmaker[Session]:
    return SessionLocal


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
