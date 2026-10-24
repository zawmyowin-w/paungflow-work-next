"""Schema creation and lightweight additive migrations."""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.db import models  # noqa: F401  (imported so the metadata is populated)
from app.db.base import Base, engine

SCOPED_TABLES: tuple[str, ...] = ("forecast_datasets", "forecast_runs")
SCOPE_ORIGIN_DDL: str = "ALTER TABLE {table} ADD COLUMN scope_origin VARCHAR(512) NOT NULL DEFAULT 'preview'"


def init_db() -> None:
    """Create missing tables and apply the additive column migrations."""

    Base.metadata.create_all(bind=engine)
    _add_missing_scope_origin_columns()


def _add_missing_scope_origin_columns() -> None:
    """Add the ``scope_origin`` column to datasets and runs created before it existed."""

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    for table_name in SCOPED_TABLES:
        if table_name not in table_names:
            continue
        if "scope_origin" in {column["name"] for column in inspector.get_columns(table_name)}:
            continue
        try:
            with engine.begin() as connection:
                connection.execute(text(SCOPE_ORIGIN_DDL.format(table=table_name)))
        except Exception:
            # Another serving instance may have completed this migration during rollout.
            refreshed = {column["name"] for column in inspector.get_columns(table_name)}
            if "scope_origin" not in refreshed:
                raise
