"""View models that turn service records into ready-to-render template context."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from app.domain.records import DatasetRecord, ForecastRunRecord
from app.services.forecasts import ForecastDetail
from app.services.identity import UserProfile
from app.web.charts import (
    DEFAULT_MODEL_COLOR,
    MODEL_COLORS,
    actual_vs_predicted_chart,
    number,
    overview_chart,
    scatter_chart,
    unit_label,
)
from app.web.theme import DARK_THEME

DASHBOARD_POINT_LIMIT: int = 90
DASHBOARD_RUN_LIMIT: int = 6
DEFAULT_HORIZON: int = 7
HORIZON_CHOICES: tuple[int, ...] = (7, 14, 30)

STATUS_MESSAGES: dict[str, tuple[str, str]] = {
    "uploaded": ("Dataset validated and ready for forecasting.", "info"),
    "sample": ("Synthetic demonstration data loaded. Do not use it for operational decisions.", "info"),
    "forecast": ("Forecast run finished.", "info"),
    "upload-failed": ("The dataset could not be validated. Check the file and try again.", "error"),
    "sample-failed": ("The synthetic sample could not be created.", "error"),
    "forecast-failed": ("The forecast run could not be completed.", "error"),
    "no-dataset": ("Upload a dataset or load the synthetic sample before running a model.", "error"),
}


def status_message(status: str) -> tuple[str | None, str]:
    """Return the message and the level of a dashboard status code."""

    return STATUS_MESSAGES.get(status, (None, "info"))


def dashboard_view(
    *,
    user: UserProfile,
    theme: str,
    dataset: DatasetRecord | None,
    runs: Sequence[ForecastRunRecord],
    horizon: int,
    engine_note: str,
    message: str | None = None,
    message_level: str = "info",
) -> dict[str, object]:
    """Return the template context of the dashboard page."""

    points = list(dataset.points[-DASHBOARD_POINT_LIMIT:]) if dataset is not None else []
    comparison_rows = [
        {
            "model_name": run.model_name,
            "color": MODEL_COLORS.get(run.model_name, DEFAULT_MODEL_COLOR),
            "mae": number(run.mae),
            "rmse": number(run.rmse),
            "mape": number(run.mape),
        }
        for run in runs
    ]
    return {
        "user": user,
        "theme": theme,
        "theme_icon": "☀" if theme == DARK_THEME else "☾",
        "theme_label": "light" if theme == DARK_THEME else "dark",
        "clock_date": _clock_values()[0],
        "clock_time": _clock_values()[1],
        "dataset": dataset,
        "runs": list(runs),
        "chart": overview_chart(points, runs),
        "comparison_rows": comparison_rows,
        "run_count": len(runs),
        "engine_note": engine_note,
        "current_inflow": number(dataset.latest_value, 3) if dataset is not None else "—",
        "inflow_label": dataset.target_column if dataset is not None else "No dataset",
        "horizon": horizon,
        "horizon_choices": HORIZON_CHOICES,
        "dataset_name": dataset.filename if dataset is not None else "No dataset loaded",
        "dataset_meta": _dataset_meta(dataset),
        "dataset_status": _dataset_status(dataset),
        "dataset_ready": dataset is not None,
        "chart_period": _chart_period(dataset),
        "feature_dataset_status": _feature_dataset_status(dataset),
        "feature_dataset_caption": (
            f"{number(dataset.row_count, 0)} records" if dataset is not None else "Upload a CSV"
        ),
        "feature_model_status": "Active" if runs else "Idle",
        "feature_model_caption": _run_caption(len(runs)),
        "message": message,
        "message_level": message_level,
    }


def results_view(
    *,
    user: UserProfile,
    theme: str,
    model_key: str,
    model_title: str,
    run_id: int | None,
    detail: ForecastDetail | None,
    notice: str,
    notice_class: str = "",
) -> dict[str, object]:
    """Return the template context of a model result page."""

    unit = unit_label(detail.dataset.target_column) if detail is not None else "dataset units"
    metrics = detail.metrics if detail is not None else None
    return {
        "user": user,
        "theme": theme,
        "theme_icon": "☀" if theme == DARK_THEME else "☾",
        "theme_label": "light" if theme == DARK_THEME else "dark",
        "model_key": model_key,
        "model_title": model_title,
        "run_id": run_id,
        "return_path": f"/results/{model_key}" + (f"?run_id={run_id}" if run_id else ""),
        "detail": detail,
        "unit": unit,
        "line_chart": actual_vs_predicted_chart(detail.history, unit) if detail is not None else "",
        "scatter_chart": scatter_chart(detail.validation, unit, metrics.r2)
        if detail is not None and metrics
        else "",
        "forecast_rows": [
            {"step": point.step, "label": point.label, "value": number(point.value, 3)}
            for point in (detail.forecast if detail is not None else ())
        ],
        "forecast_title": f"2. Next {detail.run.horizon} observations forecast" if detail is not None else "",
        "forecast_value_heading": f"Forecast Inflow ({unit})",
        "metric_rmse": number(metrics.rmse, 3) if metrics is not None else "—",
        "metric_r2": number(metrics.r2, 3) if metrics is not None and metrics.r2 is not None else "—",
        "metric_mae": number(metrics.mae, 3) if metrics is not None else "—",
        "metric_footnote": (
            f"Computed from the last {metrics.holdout} observations · MAPE {number(metrics.mape, 2)}%"
            if metrics is not None
            else "Metrics are calculated from the selected dataset."
        ),
        "history_caption": (
            f"Rolling one-step backtest · {detail.dataset.target_column} · "
            f"{metrics.holdout} holdout observations"
            if detail is not None and metrics is not None
            else "Observed inflow and rolling backtest predictions"
        ),
        "subtitle": _results_subtitle(detail),
        "dataset_summary": _results_summary(detail),
        "engine_note": (
            "Preview forecast output · Confirm model validation before operational use."
            if detail is None or not detail.dataset.is_demo
            else "Preview forecast output · This is synthetic demo data, not operational guidance."
        ),
        "notice": notice,
        "notice_class": notice_class,
    }


def _clock_values() -> tuple[str, str]:
    """Return the current date and time shown in the header clock."""

    now = datetime.now()
    return now.strftime("%d/%m/%Y"), now.strftime("%I:%M %p").lstrip("0")


def _dataset_meta(dataset: DatasetRecord | None) -> str:
    """Return the description line of the dataset strip."""

    if dataset is None:
        return "Upload a CSV time-series to enable model runs"
    demo_note = " · synthetic sample" if dataset.is_demo else ""
    return (
        f"{number(dataset.row_count, 0)} observations · {dataset.time_column} → "
        f"{dataset.target_column}{demo_note}"
    )


def _dataset_status(dataset: DatasetRecord | None) -> str:
    """Return the status label of the dataset strip."""

    if dataset is None:
        return "WAITING FOR DATA"
    return "DEMO DATA" if dataset.is_demo else "READY"


def _chart_period(dataset: DatasetRecord | None) -> str:
    """Return the period label of the chart."""

    if dataset is None:
        return "No active series"
    return f"{dataset.start_label or '—'} — {dataset.end_label or '—'}"


def _feature_dataset_status(dataset: DatasetRecord | None) -> str:
    """Return the dataset status of the key feature panel."""

    if dataset is None:
        return "Waiting"
    return "Demo" if dataset.is_demo else "Ready"


def _run_caption(run_count: int) -> str:
    """Return the caption of the model status indicator."""

    if not run_count:
        return "No runs yet"
    return f"{run_count} saved run{'' if run_count == 1 else 's'}"


def _results_subtitle(detail: ForecastDetail | None) -> str:
    """Return the subtitle of the result page."""

    if detail is None:
        return "No saved forecast run was selected."
    dataset = detail.dataset
    return (
        f"{dataset.filename} · {number(dataset.row_count, 0)} observations · "
        f"{dataset.start_label or '—'} to {dataset.end_label or '—'}"
    )


def _results_summary(detail: ForecastDetail | None) -> str:
    """Return the footer summary of the result page."""

    if detail is None:
        return "Lower Paung-Luang Dam · Python admin dashboard"
    return f"{detail.dataset.filename} · {detail.run.model_name} · {detail.run.horizon} forecast steps"
