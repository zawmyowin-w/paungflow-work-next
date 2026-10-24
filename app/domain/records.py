"""Records exchanged between the persistence layer and the services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.series import TimeSeriesPoint


@dataclass(frozen=True, slots=True)
class DatasetRecord:
    """A stored dataset together with its parsed observations."""

    id: str
    filename: str
    row_count: int
    time_column: str
    target_column: str
    start_label: str | None
    end_label: str | None
    latest_value: float
    is_demo: bool
    points: tuple[TimeSeriesPoint, ...]
    uploaded_at: datetime | None


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    """A single forecast value with its step and label."""

    step: int
    label: str
    value: float

    def as_dict(self) -> dict[str, object]:
        """Return the JSON friendly representation stored in the database."""

        return {"step": self.step, "label": self.label, "value": self.value}


@dataclass(frozen=True, slots=True)
class ForecastRunRecord:
    """A stored forecasting run and the metrics it produced."""

    id: int
    dataset_id: str
    model_name: str
    horizon: int
    mae: float
    rmse: float
    mape: float
    forecast: tuple[ForecastPoint, ...]
    created_at: datetime | None


@dataclass(frozen=True, slots=True)
class SeriesComparison:
    """One point of an actual-versus-predicted chart."""

    label: str
    actual: float
    predicted: float | None
