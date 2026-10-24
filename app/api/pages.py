"""HTML pages of the dashboard.

Every page is rendered by the server: the templates receive the data, the
charts and the current theme, so the browser only has to display HTML.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from app.api.dependencies import (
    current_user,
    get_dataset_service,
    get_forecast_service,
    page_origin,
)
from app.config import ROUTE_MANIFEST_PATH, get_settings
from app.core.errors import AppError
from app.domain.forecasting import ENGINE_NOTE, get_model
from app.services.datasets import DatasetService
from app.services.forecasts import ForecastDetail, ForecastService
from app.services.identity import UserProfile
from app.web.templates import templates
from app.web.theme import DARK_THEME, LIGHT_THEME, apply_theme, read_theme
from app.web.views import DASHBOARD_RUN_LIMIT, dashboard_view, results_view, status_message

router = APIRouter(tags=["pages"])

DEFAULT_HORIZON: int = 7
HORIZON_CHOICES: tuple[int, ...] = (7, 14, 30)
DASHBOARD_PATH: str = "/dashboard"


@router.get("/manus-routes.json", include_in_schema=False)
def route_manifest() -> FileResponse:
    """Serve the platform route manifest."""

    return FileResponse(ROUTE_MANIFEST_PATH, media_type="application/json")


@router.get("/", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: Annotated[UserProfile | None, Depends(current_user)],
) -> Response:
    """Render the sign-in page."""

    settings = get_settings()
    if user is not None and user.role == "admin":
        return RedirectResponse(DASHBOARD_PATH, status_code=303)
    auth_state = request.query_params.get("auth", "")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "auth_error": auth_state == "failed",
            "local_login_error": auth_state == "local-failed",
            "local_auth_enabled": settings.local_auth_enabled,
            "local_username": settings.local_admin_username,
            "not_admin": user is not None or auth_state == "not-admin",
            "login_origin": page_origin(request),
        },
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    user: Annotated[UserProfile | None, Depends(current_user)],
    datasets: Annotated[DatasetService, Depends(get_dataset_service)],
    forecasts: Annotated[ForecastService, Depends(get_forecast_service)],
) -> Response:
    """Render the dashboard with the current dataset and the saved runs."""

    if user is None:
        return RedirectResponse("/", status_code=303)
    if user.role != "admin":
        return _access_denied_page(request)
    origin = page_origin(request)
    dataset = datasets.latest(owner_open_id=user.open_id, scope_origin=origin)
    runs = (
        forecasts.list_runs(
            dataset_id=dataset.id,
            owner_open_id=user.open_id,
            scope_origin=origin,
            limit=DASHBOARD_RUN_LIMIT,
        )
        if dataset is not None
        else []
    )
    message, message_level = status_message(request.query_params.get("status", ""))
    context = dashboard_view(
        user=user,
        theme=read_theme(request),
        dataset=dataset,
        runs=runs,
        horizon=_read_horizon(request),
        engine_note=ENGINE_NOTE,
        message=message,
        message_level=message_level,
    )
    return templates.TemplateResponse(request=request, name="dashboard.html", context=context)


@router.get("/results/{model_key}", response_class=HTMLResponse)
async def prediction_results_page(
    request: Request,
    model_key: str,
    user: Annotated[UserProfile | None, Depends(current_user)],
    forecasts: Annotated[ForecastService, Depends(get_forecast_service)],
) -> Response:
    """Render the result page of one forecasting model."""

    if user is None:
        return RedirectResponse("/", status_code=303)
    if user.role != "admin":
        return _access_denied_page(request)
    model = get_model(model_key)
    run_id = _read_run_id(request)
    detail, notice, notice_class = _load_result(request, forecasts, user, run_id, model.key)
    context = results_view(
        user=user,
        theme=read_theme(request),
        model_key=model.key,
        model_title=model.title,
        run_id=run_id,
        detail=detail,
        notice=notice,
        notice_class=notice_class,
    )
    return templates.TemplateResponse(request=request, name="results.html", context=context)


@router.post("/theme/toggle")
async def toggle_theme(request: Request) -> RedirectResponse:
    """Switch between the light and dark theme and return to the previous page."""

    form = await request.form()
    target = _safe_path(str(form.get("next", DASHBOARD_PATH)))
    response = RedirectResponse(target, status_code=303)
    apply_theme(response, DARK_THEME if read_theme(request) == LIGHT_THEME else LIGHT_THEME)
    return response


def _load_result(
    request: Request,
    forecasts: ForecastService,
    user: UserProfile,
    run_id: int | None,
    model_key: str,
) -> tuple[ForecastDetail | None, str, str]:
    """Return the saved run of a result page with the notice that explains it."""

    if run_id is None:
        return None, "No saved forecast run was selected. Return to the dashboard and run a model.", ""
    try:
        detail = forecasts.build_detail(
            run_id=run_id,
            owner_open_id=user.open_id,
            scope_origin=page_origin(request),
        )
    except AppError:
        return None, "This saved forecast could not be found. Return to the dashboard and run a model.", ""
    if detail.run.model_name.lower() != model_key:
        return (
            None,
            "This saved forecast belongs to a different model. "
            "Return to the dashboard and open its result page.",
            "",
        )
    if detail.dataset.is_demo:
        return detail, "Synthetic demonstration data · Not validated for dam operations.", "demo-notice"
    return detail, "Preview forecast output · Confirm model validation before operational use.", ""


def _read_horizon(request: Request) -> int:
    """Return the forecast horizon selected in the dashboard."""

    try:
        value = int(request.query_params.get("horizon", ""))
    except (TypeError, ValueError):
        return DEFAULT_HORIZON
    return value if value in HORIZON_CHOICES else DEFAULT_HORIZON


def _read_run_id(request: Request) -> int | None:
    """Return the identifier of the forecast run shown on a result page."""

    try:
        value = int(request.query_params.get("run_id", ""))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _safe_path(target: str) -> str:
    """Return a redirect target that stays on this site."""

    if not target.startswith("/") or target.startswith("//"):
        return DASHBOARD_PATH
    return target


def _access_denied_page(request: Request) -> Response:
    """Render the page shown to signed-in accounts without the admin role."""

    return templates.TemplateResponse(
        request=request,
        name="access_denied.html",
        context={},
        status_code=403,
    )
