"""Tests for the forecasting engine of the domain layer."""

from __future__ import annotations

import math

import pytest

from app.core.errors import UnprocessableEntityError, UnsupportedModelError
from app.domain.forecasting import (
    MODEL_SPECS,
    backtest_metrics,
    backtest_predictions,
    forecast_values,
    get_model,
    rolling_backtest_series,
)


def _series(count: int = 40) -> list[float]:
    return [20.0 + 3.0 * math.sin(index / 3.0) + index * 0.1 for index in range(count)]


def test_every_documented_model_is_available() -> None:
    assert set(MODEL_SPECS) == {"lstm", "gru", "rgf-lstm"}
    assert get_model("LSTM").title == "LSTM"
    assert get_model("rgf-lstm").title == "RGF-LSTM"


def test_unknown_models_are_rejected() -> None:
    with pytest.raises(UnsupportedModelError):
        get_model("transformer")


def test_forecasts_are_deterministic() -> None:
    values = _series()

    assert forecast_values(values, 7, "lstm") == forecast_values(values, 7, "lstm")


def test_forecasts_have_the_requested_horizon() -> None:
    forecast = forecast_values(_series(), 12, "gru")

    assert len(forecast) == 12
    assert all(value >= 0.0 for value in forecast)


def test_forecasts_need_at_least_two_observations() -> None:
    with pytest.raises(UnprocessableEntityError, match="two finite numeric observations"):
        forecast_values([1.0], 3, "lstm")


def test_metrics_describe_the_holdout_window() -> None:
    metrics = backtest_metrics(_series(), "lstm")

    assert metrics.holdout > 0
    assert metrics.mae >= 0.0
    assert metrics.rmse >= metrics.mae - 1e-9
    assert metrics.mape >= 0.0
    assert metrics.r2 is None or metrics.r2 <= 1.0
    assert set(metrics.as_dict()) == {"mae", "rmse", "mape", "r2", "holdout"}


def test_backtest_predictions_align_actual_and_predicted() -> None:
    result = backtest_predictions(_series(), "rgf-lstm")

    assert len(result.actual) == len(result.predicted) == result.holdout


def test_rolling_series_covers_the_whole_history() -> None:
    values = _series(count=30)
    points = rolling_backtest_series(values, "lstm", max_points=10)

    assert 0 < len(points) <= 10
    assert points[0].actual == values[0]
    assert any(point.predicted is None for point in points)
    assert any(point.predicted is not None for point in points)
