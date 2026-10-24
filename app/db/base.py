"""Database engine, session factory and declarative base."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

SQLITE_FALLBACK_URL: str = "sqlite:///./data/local.db"
SSL_DISABLED_VALUES: frozenset[str] = frozenset({"0", "false", "off", "none"})


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


def utc_now() -> datetime:
    """Return the current UTC time as a naive datetime (matching the schema)."""

    return datetime.now(UTC).replace(tzinfo=None)


def resolve_database_url(raw_url: str) -> tuple[str, dict[str, object]]:
    """Return the SQLAlchemy URL and connect arguments for the configured database.

    MySQL URLs are rewritten to the PyMySQL driver and an ``ssl`` query parameter
    is translated into a verified TLS connection.
    """

    value = raw_url.strip()
    if value.startswith("mysql://"):
        value = value.replace("mysql://", "mysql+pymysql://", 1)
    if not value:
        Path("data").mkdir(exist_ok=True)
        return SQLITE_FALLBACK_URL, {}
    url = make_url(value)
    query = dict(url.query)
    ssl_mode = query.pop("ssl", None)
    connect_args: dict[str, object] = {}
    if ssl_mode is not None and str(ssl_mode).lower() not in SSL_DISABLED_VALUES:
        connect_args["ssl"] = {"check_hostname": True}
    return url.set(query=query).render_as_string(hide_password=False), connect_args


def create_engine_for(url: str, connect_args: dict[str, object]) -> Engine:
    """Create the SQLAlchemy engine used by the application."""

    options: dict[str, object] = {"pool_pre_ping": True}
    if url.startswith("sqlite:"):
        options["connect_args"] = {"check_same_thread": False}
        if url.endswith(":memory:"):
            options["poolclass"] = StaticPool
    elif connect_args:
        options["connect_args"] = connect_args
    return create_engine(url, **options)


def build_engine() -> Engine:
    """Build the engine from the current application settings."""

    url, connect_args = resolve_database_url(get_settings().database_url)
    return create_engine_for(url, connect_args)


engine: Engine = build_engine()
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional session scope around a block of work."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
