"""Forecasting runs: creation, listing and result assembly."""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.core.errors import NotFoundError
from app.db.base import session_scope, utc_now
from app.db.models import ForecastRun
from app.db.repositories import ForecastRunRepository
from app.domain.forecasting import (
    ENGINE_NAME,
    ForecastMetrics,
    backtest_metrics,
    backtest_predictions,
    forecast_values,
    get_model,
    rolling_backtest_series,
)
from app.domain.records import DatasetRecord, ForecastPoint, ForecastRunRecord, SeriesComparison
from app.domain.series import future_labels
from app.services.datasets import DatasetService


@dataclass(frozen=True, slots=True)
class ForecastDetail:
    """Everything the result page needs to render one saved run."""

    run: ForecastRunRecord
    dataset: DatasetRecord
    history: tuple[SeriesComparison, ...]
    validation: tuple[SeriesComparison, ...]
    forecast: tuple[ForecastPoint, ...]
    metrics: ForecastMetrics


class ForecastService:
    """Run the forecasting engine and persist its results."""

    def __init__(self, datasets: DatasetService) -> None:
        self._datasets = datasets

    def create_run(
        self,
        *,
        owner_open_id: str,
        scope_origin: str,
        dataset_id: str,
        horizon: int,
        model_name: str,
    ) -> ForecastRunRecord:
        """Run a model against a dataset and store the resulting forecast."""

        spec = get_model(model_name)
        dataset = self._require_dataset(dataset_id, owner_open_id, scope_origin)
        values = [point.value for point in dataset.points]
        forecast = forecast_values(values, horizon, spec.key)
        metrics = backtest_metrics(values, spec.key)
        points = tuple(
            ForecastPoint(step=index + 1, label=f"+{index + 1}", value=value)
            for index, value in enumerate(forecast)
        )
        run = ForecastRun(
            dataset_id=dataset.id,
            owner_open_id=owner_open_id,
            scope_origin=scope_origin,
            model_name=spec.title,
            horizon=horizon,
            mae=metrics.mae,
            rmse=metrics.rmse,
            mape=metrics.mape,
            forecast_json=json.dumps([point.as_dict() for point in points], separators=(",", ":")),
            metrics_json=json.dumps(
                {
                    **metrics.as_dict(),
                    "last_observed_label": dataset.end_label or "",
                    "engine": ENGINE_NAME,
                },
                separators=(",", ":"),
            ),
            created_at=utc_now(),
        )
        with session_scope() as session:
            ForecastRunRepository(session).add(run)
            session.flush()
            session.refresh(run)
            return _to_record(run)

    def list_runs(
        self,
        *,
        dataset_id: str,
        owner_open_id: str,
        scope_origin: str,
        limit: int,
    ) -> list[ForecastRunRecord]:
        """Return the newest forecast runs of a dataset."""

        with session_scope() as session:
            runs = ForecastRunRepository(session).list_for_dataset(
                dataset_id, owner_open_id, scope_origin, limit
            )
            return [_to_record(run) for run in runs]

    def get_run(self, *, run_id: int, owner_open_id: str, scope_origin: str) -> ForecastRunRecord | None:
        """Return a saved run of the owner and scope, or ``None``."""

        with session_scope() as session:
            run = ForecastRunRepository(session).find_by_id(run_id, owner_open_id, scope_origin)
            return _to_record(run) if run is not None else None

    def build_detail(
        self,
        *,
        run_id: int,
        owner_open_id: str,
        scope_origin: str,
    ) -> ForecastDetail:
        """Assemble the charts, table and metrics of one saved run.

        Raises:
            NotFoundError: when the run or its dataset is not available.
        """

        run = self.get_run(run_id=run_id, owner_open_id=owner_open_id, scope_origin=scope_origin)
        if run is None:
            raise NotFoundError("Forecast run not found for this account and site.")
        dataset = self._require_dataset(run.dataset_id, owner_open_id, scope_origin)
        values = [point.value for point in dataset.points]
        model_key = run.model_name.lower()
        metrics = backtest_metrics(values, model_key)
        backtest = backtest_predictions(values, model_key)
        rolling = rolling_backtest_series(values, model_key)
        history = tuple(
            SeriesComparison(
                label=dataset.points[item.index].label,
                actual=item.actual,
                predicted=item.predicted,
            )
            for item in rolling
        )
        validation = tuple(
            SeriesComparison(
                label=dataset.points[len(dataset.points) - backtest.holdout + index].label,
                actual=backtest.actual[index],
                predicted=backtest.predicted[index],
            )
            for index in range(backtest.holdout)
        )
        labels = future_labels(dataset.points, len(run.forecast))
        forecast = tuple(
            ForecastPoint(step=point.step, label=label, value=point.value)
            for point, label in zip(run.forecast, labels, strict=False)
        )
        return ForecastDetail(
            run=run,
            dataset=dataset,
            history=history,
            validation=validation,
            forecast=forecast,
            metrics=metrics,
        )

    def _require_dataset(self, dataset_id: str, owner_open_id: str, scope_origin: str) -> DatasetRecord:
        """Return a dataset of the owner and scope.

        Raises:
            NotFoundError: when the dataset does not exist.
        """

        dataset = self._datasets.get(
            dataset_id=dataset_id, owner_open_id=owner_open_id, scope_origin=scope_origin
        )
        if dataset is None:
            raise NotFoundError("Dataset not found. Upload a dataset and try again.")
        return dataset


def _to_record(run: ForecastRun) -> ForecastRunRecord:
    """Convert a stored run into a :class:`ForecastRunRecord`."""

    return ForecastRunRecord(
        id=run.id,
        dataset_id=run.dataset_id,
        model_name=run.model_name,
        horizon=run.horizon,
        mae=run.mae,
        rmse=run.rmse,
        mape=run.mape,
        forecast=_parse_forecast(run.forecast_json),
        created_at=run.created_at,
    )


def _parse_forecast(raw: str) -> tuple[ForecastPoint, ...]:
    """Return the stored forecast values of a run."""

    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return ()
    if not isinstance(payload, list):
        return ()
    points: list[ForecastPoint] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            points.append(
                ForecastPoint(
                    step=int(item["step"]),
                    label=str(item["label"]),
                    value=float(item["value"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(points)
