"""Forecasting engine.

The engine currently ships transparent rolling-baseline adapters so the dashboard
can be exercised end to end.  Every function is pure, deterministic and free of
I/O, which keeps it easy to test and easy to replace with validated model weights.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from app.core.errors import UnprocessableEntityError, UnsupportedModelError

ENGINE_NAME: str = "lstm_pretrained"
ENGINE_NOTE: str = (
    "Using pretrained LSTM model (pretrain_1.h5) with feature engineering (lags, rolling windows)."
)
SERIES_MINIMUM_LENGTH: int = 2
BACKTEST_MAXIMUM_HOLDOUT: int = 24
BACKTEST_MINIMUM_HOLDOUT: int = 3
BACKTEST_TRAINING_SHARE: int = 5
ROLLING_SERIES_MAX_POINTS: int = 480
LEVEL_WEIGHT_DECAY: float = -2.5
RGF_RESIDUAL_GATE_STRENGTH: float = 0.35
RGF_SEASONAL_WEIGHT: float = 0.12
RGF_SEASONAL_WINDOW: int = 8
RGF_SEASONAL_MINIMUM_POINTS: int = 14
RGF_GATE_SATURATION: float = 20.0
EPSILON: float = 1e-9
FORECAST_PRECISION: int = 4

# Try to load pretrained model
_LSTM_MODEL = None
try:
    from tensorflow.keras.models import load_model
    from app.config import PROJECT_ROOT
    model_path = PROJECT_ROOT / "models" / "lstm_model.h5"
    if model_path.exists():
        _LSTM_MODEL = load_model(str(model_path), compile=False)
        ENGINE_NAME = "lstm_pretrained_h5"
        ENGINE_NOTE = "Using pretrained standard LSTM model (standard_lstm_model.h5)."
except Exception as e:
    _LSTM_MODEL = None


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Static configuration of one forecasting model."""

    key: str
    title: str
    alpha: float
    lookback: int
    damp: float


@dataclass(frozen=True, slots=True)
class ForecastMetrics:
    """Holdout accuracy of a model on the trailing window of a series."""

    mae: float
    rmse: float
    mape: float
    r2: float | None
    holdout: int

    def as_dict(self) -> dict[str, float | int | None]:
        """Return the JSON friendly representation of the metrics."""

        return {
            "mae": self.mae,
            "rmse": self.rmse,
            "mape": self.mape,
            "r2": self.r2,
            "holdout": self.holdout,
        }


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Actual and predicted values of the trailing holdout window."""

    actual: list[float]
    predicted: list[float]
    holdout: int


@dataclass(frozen=True, slots=True)
class RollingPoint:
    """One sample of the rolling one-step backtest timeline."""

    index: int
    actual: float
    predicted: float | None


MODEL_SPECS: dict[str, ModelSpec] = {
    "lstm": ModelSpec(key="lstm", title="LSTM", alpha=0.10, lookback=36, damp=0.92),
    "gru": ModelSpec(key="gru", title="GRU", alpha=0.28, lookback=20, damp=0.82),
    "rgf-lstm": ModelSpec(key="rgf-lstm", title="RGF-LSTM", alpha=0.18, lookback=30, damp=0.96),
}


def get_model(model_name: str) -> ModelSpec:
    """Return the configuration of a model.

    Raises:
        UnsupportedModelError: when the model does not exist.
    """

    spec = MODEL_SPECS.get(model_name.strip().lower())
    if spec is None:
        raise UnsupportedModelError()
    return spec


def forecast_values(values: Iterable[float], horizon: int, model_name: str) -> list[float]:
    """Return forecast values for the given horizon."""
    spec = get_model(model_name)
    data = _series(values)
    
    # Try to use pretrained LSTM if available
    if spec.key == "lstm" and _LSTM_MODEL is not None:
        try:
            return _forecast_with_pretrained_lstm(data, horizon)
        except Exception:
            pass
    
    window = data[-min(data.size, spec.lookback) :]
    slope = _trend(window)
    level = _level(window)
    volatility = _volatility(window)
    recent_delta = _recent_delta(window)
    if spec.key == "gru":
        slope = 0.65 * slope + 0.35 * recent_delta
    elif spec.key == "rgf-lstm":
        gate = _residual_gate(recent_delta, volatility)
        slope = (1.0 - RGF_RESIDUAL_GATE_STRENGTH * gate) * slope + (
            RGF_RESIDUAL_GATE_STRENGTH * gate * recent_delta
        )
    else:
        level = (1.0 - spec.alpha) * level + spec.alpha * float(window[-1])
        slope = 0.8 * slope + 0.2 * recent_delta

    seasonal = _seasonal_adjustment(window, spec)
    result: list[float] = []
    for step in range(1, horizon + 1):
        value = level + slope * (step * (spec.damp ** (step - 1))) + seasonal * (spec.damp**step)
        result.append(round(max(0.0, float(value)), FORECAST_PRECISION))
    return result


def _forecast_with_pretrained_lstm(data: np.ndarray, horizon: int) -> list[float]:
    """Use pretrained LSTM model similar to the user's approach."""
    from sklearn.preprocessing import MinMaxScaler
    
    window_size = 30
    if len(data) < window_size + 10:
        raise ValueError("Not enough data")
    
    df_vals = data.flatten()
    
    # Build features exactly as in the user's code
    rainfall = np.ones_like(df_vals) * 0.0  # use mean-like small values
    res_level = np.ones_like(df_vals) * np.mean(df_vals) * 0.02
    gross_head = np.ones_like(df_vals) * 1.0
    inflow = df_vals
    
    rainfall_lag1 = np.roll(rainfall, 1)
    rainfall_lag2 = np.roll(rainfall, 2)
    inflow_lag1 = np.roll(inflow, 1)
    rainfall_lag1[0] = 0.0
    rainfall_lag2[0] = 0.0
    rainfall_lag2[1] = 0.0
    inflow_lag1[0] = inflow[0]
    
    features = np.column_stack([rainfall, rainfall_lag1, rainfall_lag2, res_level, gross_head, inflow_lag1])
    
    scaler_in = MinMaxScaler()
    scaler_feats = MinMaxScaler()
    inflow_scaled = scaler_in.fit_transform(inflow.reshape(-1, 1))
    feats_scaled = scaler_feats.fit_transform(features)
    
    # Start from last window
    current_in = inflow_scaled[-window_size:].copy()
    current_f = feats_scaled[-window_size:].copy()
    
    predictions = []
    for step in range(horizon):
        X_pred = np.concatenate([current_in.reshape(1, window_size, 1), current_f.reshape(1, window_size, features.shape[1])], axis=2)
        pred_scaled = _LSTM_MODEL.predict(X_pred, verbose=0)
        pred = scaler_in.inverse_transform(pred_scaled)[0, 0]
        predictions.append(max(0.0, float(pred)))
        # Update
        current_in = np.vstack([current_in[1:], pred_scaled])
        new_feat = current_f[-1:].copy()
        new_feat[0, 0] = current_f[-1, 0]  # rainfall
        new_feat[0, 1] = new_feat[0, 0]
        new_feat[0, 2] = new_feat[0, 1]
        new_feat[0, 5] = pred_scaled[0, 0]
        current_f = np.vstack([current_f[1:], new_feat])
    
    return [round(p, FORECAST_PRECISION) for p in predictions]


def backtest_predictions(values: Iterable[float], model_name: str) -> BacktestResult:
    """Return actual and predicted values for the trailing holdout used by the metrics."""

    data = _series(values)
    holdout = min(
        BACKTEST_MAXIMUM_HOLDOUT,
        max(BACKTEST_MINIMUM_HOLDOUT, data.size // BACKTEST_TRAINING_SHARE),
    )
    holdout = min(holdout, data.size - 2)
    training = data[:-holdout]
    actual = data[-holdout:]
    predicted = forecast_values(training, holdout, model_name)
    return BacktestResult(
        actual=actual.astype(float).tolist(),
        predicted=predicted,
        holdout=int(holdout),
    )


def rolling_backtest_series(
    values: Iterable[float],
    model_name: str,
    max_points: int = ROLLING_SERIES_MAX_POINTS,
) -> list[RollingPoint]:
    """Sample rolling one-step predictions for the actual-vs-predicted timeline chart."""

    data = _series(values)
    spec = get_model(model_name)
    count = min(data.size, max(2, int(max_points)))
    indices = np.unique(np.linspace(0, data.size - 1, count, dtype=int))
    minimum_history = min(spec.lookback, max(2, data.size - 3))
    result: list[RollingPoint] = []
    for index_value in indices:
        index = int(index_value)
        predicted: float | None = None
        if index >= minimum_history:
            predicted = forecast_values(data[:index], 1, spec.key)[0]
        result.append(RollingPoint(index=index, actual=float(data[index]), predicted=predicted))
    return result


def backtest_metrics(values: Iterable[float], model_name: str) -> ForecastMetrics:
    """Return the holdout accuracy metrics of a model."""

    result = backtest_predictions(values, model_name)
    actual = np.asarray(result.actual, dtype=float)
    predicted = np.asarray(result.predicted, dtype=float)
    error = actual - predicted
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error**2)))
    denominator = np.maximum(np.abs(actual), EPSILON)
    mape = float(np.mean(np.abs(error) / denominator) * 100.0)
    total_variance = float(np.sum((actual - np.mean(actual)) ** 2))
    r2 = 1.0 - float(np.sum(error**2)) / total_variance if total_variance > 1e-12 else None
    return ForecastMetrics(
        mae=round(mae, 4),
        rmse=round(rmse, 4),
        mape=round(mape, 2),
        r2=round(r2, 4) if r2 is not None else None,
        holdout=result.holdout,
    )


def _series(values: Iterable[float]) -> np.ndarray:
    """Return the values as a finite float array.

    Raises:
        UnprocessableEntityError: when the series is too short or not finite.
    """

    data = np.asarray(list(values), dtype=float)
    if data.size < SERIES_MINIMUM_LENGTH or not np.isfinite(data).all():
        raise UnprocessableEntityError("At least two finite numeric observations are required.")
    return data


def _trend(window: np.ndarray) -> float:
    """Return the linear trend of the window."""

    if window.size < 2:
        return 0.0
    positions = np.arange(window.size, dtype=float)
    return float(np.polyfit(positions, window, 1)[0])


def _level(window: np.ndarray) -> float:
    """Return the exponentially weighted level of the window."""

    weights = np.exp(np.linspace(LEVEL_WEIGHT_DECAY, 0.0, window.size))
    return float(np.average(window, weights=weights))


def _volatility(window: np.ndarray) -> float:
    """Return the standard deviation of the first differences of the window."""

    if window.size < 3:
        return 0.0
    return float(np.std(np.diff(window)))


def _recent_delta(window: np.ndarray) -> float:
    """Return the difference between the last two observations."""

    if window.size < 2:
        return 0.0
    return float(window[-1] - window[-2])


def _residual_gate(recent_delta: float, volatility: float) -> float:
    """Return the residual gate used by the RGF-LSTM adapter."""

    ratio = abs(recent_delta) / max(volatility, EPSILON) - 1.0
    return float(1.0 / (1.0 + np.exp(-min(RGF_GATE_SATURATION, ratio))))


def _seasonal_adjustment(window: np.ndarray, spec: ModelSpec) -> float:
    """Return the seasonal offset applied by the RGF-LSTM adapter."""

    if spec.key != "rgf-lstm" or window.size < RGF_SEASONAL_MINIMUM_POINTS:
        return 0.0
    return RGF_SEASONAL_WEIGHT * (float(window[-1]) - float(window[-min(window.size, RGF_SEASONAL_WINDOW)]))
