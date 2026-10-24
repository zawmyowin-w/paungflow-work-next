"""SQLAlchemy models that describe the persisted dashboard data."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utc_now

LongText = LONGTEXT().with_variant(Text(), "sqlite")


class AdminUser(Base):
    """A signed-in account and the role it holds in the dashboard."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    open_id: Mapped[str] = mapped_column(String(191), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    name: Mapped[str] = mapped_column(String(191), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class Dataset(Base):
    """A validated time-series dataset owned by one account and origin."""

    __tablename__ = "forecast_datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_open_id: Mapped[str] = mapped_column(String(191), nullable=False, index=True)
    scope_origin: Mapped[str] = mapped_column(String(512), nullable=False, default="preview", index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    time_column: Mapped[str] = mapped_column(String(128), nullable=False)
    target_column: Mapped[str] = mapped_column(String(128), nullable=False)
    start_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    end_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    latest_value: Mapped[float] = mapped_column(Float, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    points_json: Mapped[str] = mapped_column(LongText, nullable=False)
    raw_csv: Mapped[str | None] = mapped_column(LongText, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, index=True)


class ForecastRun(Base):
    """A saved forecasting run and the metrics it produced."""

    __tablename__ = "forecast_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("forecast_datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_open_id: Mapped[str] = mapped_column(String(191), nullable=False, index=True)
    scope_origin: Mapped[str] = mapped_column(String(512), nullable=False, default="preview", index=True)
    model_name: Mapped[str] = mapped_column(String(32), nullable=False)
    horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    mae: Mapped[float] = mapped_column(Float, nullable=False)
    rmse: Mapped[float] = mapped_column(Float, nullable=False)
    mape: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_json: Mapped[str] = mapped_column(LongText, nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, index=True)
