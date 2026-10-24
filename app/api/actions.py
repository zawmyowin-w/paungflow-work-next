"""Form actions of the dashboard: dataset upload, sample data and forecast runs.

The pages are rendered by the server, so the interface works with plain HTML
forms and needs no client-side scripting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.api.dependencies import (
    current_user,
    form_request_origin,
    get_app_settings,
    get_dataset_service,
    get_forecast_service,
)
from app.config import Settings
from app.core.errors import AppError
from app.domain.forecasting import get_model
from app.services.datasets import DatasetService
from app.services.forecasts import ForecastService
from app.services.identity import UserProfile

router = APIRouter(tags=["actions"])

DASHBOARD_PATH: str = "/dashboard"
DEFAULT_HORIZON: int = 7
HORIZON_CHOICES: tuple[int, ...] = (7, 14, 30)
FILENAME_MAX_LENGTH: int = 255
DEFAULT_FILENAME: str = "dataset.csv"


@router.post("/datasets/upload")
async def upload_dataset(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
    user: Annotated[UserProfile | None, Depends(current_user)],
    datasets: Annotated[DatasetService, Depends(get_dataset_service)],
    file: UploadFile = File(...),
) -> RedirectResponse:
    """Validate an uploaded CSV and return to the dashboard."""

    admin = _require_admin(user)
    if isinstance(admin, RedirectResponse):
        return admin
    filename = _clean_filename(file.filename)
    if not filename.lower().endswith(".csv"):
        return _redirect("upload-failed")
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        return _redirect("upload-failed")
    origin = form_request_origin(request)
    try:
        datasets.create_from_upload(
            owner_open_id=admin.open_id,
            scope_origin=origin,
            filename=filename,
            raw=raw,
        )
    except AppError:
        return _redirect("upload-failed")
    return _redirect("uploaded")


@router.post("/datasets/sample")
async def create_sample_dataset(
    request: Request,
    user: Annotated[UserProfile | None, Depends(current_user)],
    datasets: Annotated[DatasetService, Depends(get_dataset_service)],
) -> RedirectResponse:
    """Create the labelled synthetic dataset and return to the dashboard."""

    admin = _require_admin(user)
    if isinstance(admin, RedirectResponse):
        return admin
    origin = form_request_origin(request)
    try:
        datasets.create_synthetic_sample(owner_open_id=admin.open_id, scope_origin=origin)
    except AppError:
        return _redirect("sample-failed")
    return _redirect("sample")


@router.post("/forecast/{model_name}")
async def run_forecast(
    request: Request,
    model_name: str,
    user: Annotated[UserProfile | None, Depends(current_user)],
    forecasts: Annotated[ForecastService, Depends(get_forecast_service)],
) -> RedirectResponse:
    """Run a forecasting model and open the result page of the saved run."""

    admin = _require_admin(user)
    if isinstance(admin, RedirectResponse):
        return admin
    model = get_model(model_name)
    form = await request.form()
    dataset_id = str(form.get("dataset_id", "")).strip()
    horizon = _read_horizon(form.get("horizon"))
    if not dataset_id:
        return _redirect("no-dataset")
    origin = form_request_origin(request)
    try:
        run = forecasts.create_run(
            owner_open_id=admin.open_id,
            scope_origin=origin,
            dataset_id=dataset_id,
            horizon=horizon,
            model_name=model.key,
        )
    except AppError:
        return _redirect("forecast-failed")
    return RedirectResponse(f"/results/{model.key}?run_id={run.id}", status_code=303)


def _require_admin(user: UserProfile | None) -> UserProfile | RedirectResponse:
    """Return the administrator, or the redirect that rejects the visitor."""

    if user is None:
        return RedirectResponse("/", status_code=303)
    if user.role != "admin":
        return RedirectResponse("/?auth=not-admin", status_code=303)
    return user


def _redirect(status: str) -> RedirectResponse:
    """Return to the dashboard with a status message."""

    return RedirectResponse(f"{DASHBOARD_PATH}?status={status}", status_code=303)


def _read_horizon(raw: object) -> int:
    """Return the forecast horizon of a submitted form."""

    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        return DEFAULT_HORIZON
    return value if value in HORIZON_CHOICES else DEFAULT_HORIZON


def _clean_filename(name: str | None) -> str:
    """Return a safe file name for the uploaded file."""

    value = Path(name or DEFAULT_FILENAME).name.strip()
    return value[:FILENAME_MAX_LENGTH] or DEFAULT_FILENAME
