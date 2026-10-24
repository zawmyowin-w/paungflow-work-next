"""JSON endpoints that power the dashboard and the model result pages."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.dependencies import (
    get_app_settings,
    get_dataset_service,
    get_forecast_service,
    read_origin,
    require_admin,
    write_origin,
)
from app.api.serializers import dataset_payload, dataset_summary_payload, run_payload, user_payload
from app.config import Settings
from app.core.errors import PayloadTooLargeError, UnsupportedMediaTypeError
from app.domain.forecasting import ENGINE_NOTE
from app.schemas import (
    ComparisonPointPayload,
    DashboardStateResponse,
    DatasetResponse,
    ForecastDetailResponse,
    ForecastPointPayload,
    ForecastRequest,
    ForecastRunResponse,
    MetricsPayload,
)
from app.services.datasets import DatasetService
from app.services.forecasts import ForecastService
from app.services.identity import UserProfile

router = APIRouter(tags=["data"])

FILENAME_MAX_LENGTH: int = 255
DEFAULT_FILENAME: str = "dataset.csv"
DASHBOARD_RUN_LIMIT: int = 12
UPLOAD_MESSAGE: str = "Dataset validated and ready for forecasting."
SAMPLE_MESSAGE: str = "Synthetic demonstration data loaded. Do not use it for operational decisions."


@router.get("/api/dashboard/state", response_model=DashboardStateResponse)
async def dashboard_state(
    origin: Annotated[str, Depends(read_origin)],
    admin: Annotated[UserProfile, Depends(require_admin)],
    datasets: Annotated[DatasetService, Depends(get_dataset_service)],
    forecasts: Annotated[ForecastService, Depends(get_forecast_service)],
) -> DashboardStateResponse:
    """Return the dataset, the saved runs and the account of the dashboard."""

    dataset = datasets.latest(owner_open_id=admin.open_id, scope_origin=origin)
    runs = (
        forecasts.list_runs(
            dataset_id=dataset.id,
            owner_open_id=admin.open_id,
            scope_origin=origin,
            limit=DASHBOARD_RUN_LIMIT,
        )
        if dataset is not None
        else []
    )
    return DashboardStateResponse(
        user=user_payload(admin),
        dataset=dataset_payload(dataset) if dataset is not None else None,
        runs=[run_payload(run) for run in runs],
        engine_note=ENGINE_NOTE,
    )


@router.get("/api/forecast-runs/{run_id}", response_model=ForecastDetailResponse)
async def forecast_run_detail(
    run_id: int,
    origin: Annotated[str, Depends(read_origin)],
    admin: Annotated[UserProfile, Depends(require_admin)],
    forecasts: Annotated[ForecastService, Depends(get_forecast_service)],
) -> ForecastDetailResponse:
    """Return the charts, forecast table and metrics of one saved run."""

    detail = forecasts.build_detail(run_id=run_id, owner_open_id=admin.open_id, scope_origin=origin)
    return ForecastDetailResponse(
        run=run_payload(detail.run),
        dataset=dataset_summary_payload(detail.dataset),
        history=[
            ComparisonPointPayload(label=item.label, actual=item.actual, predicted=item.predicted)
            for item in detail.history
        ],
        validation=[
            ComparisonPointPayload(label=item.label, actual=item.actual, predicted=item.predicted)
            for item in detail.validation
        ],
        forecast=[
            ForecastPointPayload(step=item.step, label=item.label, value=item.value)
            for item in detail.forecast
        ],
        metrics=MetricsPayload(
            mae=detail.metrics.mae,
            rmse=detail.metrics.rmse,
            mape=detail.metrics.mape,
            r2=detail.metrics.r2,
            holdout=detail.metrics.holdout,
        ),
        engine_note=ENGINE_NOTE,
    )


@router.post("/api/datasets/upload", response_model=DatasetResponse)
async def upload_dataset(
    settings: Annotated[Settings, Depends(get_app_settings)],
    origin: Annotated[str, Depends(write_origin)],
    admin: Annotated[UserProfile, Depends(require_admin)],
    datasets: Annotated[DatasetService, Depends(get_dataset_service)],
    file: UploadFile = File(...),
) -> DatasetResponse:
    """Validate an uploaded CSV and store it for the signed-in administrator."""

    filename = _clean_filename(file.filename)
    if not filename.lower().endswith(".csv"):
        raise UnsupportedMediaTypeError("Upload a CSV file to continue.")
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise PayloadTooLargeError(f"Maximum CSV size is {settings.max_upload_bytes // (1024 * 1024)} MB.")
    dataset = datasets.create_from_upload(
        owner_open_id=admin.open_id,
        scope_origin=origin,
        filename=filename,
        raw=raw,
    )
    return DatasetResponse(dataset=dataset_payload(dataset), message=UPLOAD_MESSAGE)


@router.post("/api/datasets/sample", response_model=DatasetResponse)
async def create_sample_dataset(
    origin: Annotated[str, Depends(write_origin)],
    admin: Annotated[UserProfile, Depends(require_admin)],
    datasets: Annotated[DatasetService, Depends(get_dataset_service)],
) -> DatasetResponse:
    """Create the labelled synthetic dataset used for interface demonstration."""

    dataset = datasets.create_synthetic_sample(owner_open_id=admin.open_id, scope_origin=origin)
    return DatasetResponse(dataset=dataset_payload(dataset), message=SAMPLE_MESSAGE)


@router.post("/api/forecast/{model_name}", response_model=ForecastRunResponse)
async def run_forecast(
    model_name: str,
    payload: ForecastRequest,
    origin: Annotated[str, Depends(write_origin)],
    admin: Annotated[UserProfile, Depends(require_admin)],
    forecasts: Annotated[ForecastService, Depends(get_forecast_service)],
) -> ForecastRunResponse:
    """Run a forecasting model against the current dataset and store the result."""

    run = forecasts.create_run(
        owner_open_id=admin.open_id,
        scope_origin=origin,
        dataset_id=payload.dataset_id,
        horizon=payload.horizon,
        model_name=model_name,
    )
    return ForecastRunResponse(run=run_payload(run), engine_note=ENGINE_NOTE)


def _clean_filename(name: str | None) -> str:
    """Return a safe file name for the uploaded file."""

    value = Path(name or DEFAULT_FILENAME).name.strip()
    return value[:FILENAME_MAX_LENGTH] or DEFAULT_FILENAME
