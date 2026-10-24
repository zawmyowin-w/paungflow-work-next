"""Convert service records into the payloads the dashboard front end expects."""

from __future__ import annotations

from app.domain.records import DatasetRecord, ForecastRunRecord
from app.schemas import (
    DatasetPayload,
    DatasetSummaryPayload,
    ForecastPointPayload,
    ForecastRunPayload,
    SeriesPointPayload,
    UserPayload,
)
from app.services.identity import UserProfile

DASHBOARD_POINT_LIMIT: int = 90


def user_payload(user: UserProfile) -> UserPayload:
    """Return the signed-in account as a payload."""

    return UserPayload(
        open_id=user.open_id,
        name=user.name,
        email=user.email,
        role=user.role,
    )


def dataset_payload(
    dataset: DatasetRecord,
    *,
    point_limit: int = DASHBOARD_POINT_LIMIT,
) -> DatasetPayload:
    """Return a dataset as a payload with its most recent points."""

    points = [
        SeriesPointPayload(label=point.label, value=point.value) for point in dataset.points[-point_limit:]
    ]
    return DatasetPayload(
        id=dataset.id,
        filename=dataset.filename,
        rows=dataset.row_count,
        time_column=dataset.time_column,
        target_column=dataset.target_column,
        start=dataset.start_label,
        end=dataset.end_label,
        latest_value=dataset.latest_value,
        is_demo=dataset.is_demo,
        uploaded_at=dataset.uploaded_at.isoformat() if dataset.uploaded_at else None,
        points=points,
    )


def dataset_summary_payload(dataset: DatasetRecord) -> DatasetSummaryPayload:
    """Return the dataset facts shown next to a forecast result."""

    return DatasetSummaryPayload(
        filename=dataset.filename,
        rows=dataset.row_count,
        target_column=dataset.target_column,
        start=dataset.start_label,
        end=dataset.end_label,
        is_demo=dataset.is_demo,
    )


def run_payload(run: ForecastRunRecord) -> ForecastRunPayload:
    """Return a saved forecasting run as a payload."""

    return ForecastRunPayload(
        id=run.id,
        dataset_id=run.dataset_id,
        model_name=run.model_name,
        horizon=run.horizon,
        mae=run.mae,
        rmse=run.rmse,
        mape=run.mape,
        forecast=[
            ForecastPointPayload(step=point.step, label=point.label, value=point.value)
            for point in run.forecast
        ],
        created_at=run.created_at.isoformat() if run.created_at else None,
    )
