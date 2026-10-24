"""Request and response models exchanged with the dashboard front end."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SeriesPointPayload(BaseModel):
    """One observation of a stored dataset."""

    label: str
    value: float


class UserPayload(BaseModel):
    """The signed-in account shown in the dashboard."""

    open_id: str
    name: str
    email: str
    role: str


class DatasetPayload(BaseModel):
    """A dataset and, optionally, its most recent observations."""

    id: str
    filename: str
    rows: int
    time_column: str
    target_column: str
    start: str | None = None
    end: str | None = None
    latest_value: float
    is_demo: bool
    uploaded_at: str | None = None
    points: list[SeriesPointPayload] | None = None


class DatasetSummaryPayload(BaseModel):
    """The dataset facts shown next to a forecast result."""

    filename: str
    rows: int
    target_column: str
    start: str | None = None
    end: str | None = None
    is_demo: bool


class ForecastPointPayload(BaseModel):
    """One future value of a forecast."""

    step: int
    label: str
    value: float


class ForecastRunPayload(BaseModel):
    """A saved forecasting run and its holdout metrics."""

    id: int
    dataset_id: str
    model_name: str
    horizon: int
    mae: float
    rmse: float
    mape: float
    forecast: list[ForecastPointPayload] = Field(default_factory=list)
    created_at: str | None = None


class MetricsPayload(BaseModel):
    """Holdout accuracy of a model."""

    mae: float
    rmse: float
    mape: float
    r2: float | None = None
    holdout: int


class ComparisonPointPayload(BaseModel):
    """One point of an actual-versus-predicted chart."""

    label: str
    actual: float
    predicted: float | None = None


class DashboardStateResponse(BaseModel):
    """Everything the dashboard renders on load."""

    user: UserPayload
    dataset: DatasetPayload | None = None
    runs: list[ForecastRunPayload] = Field(default_factory=list)
    engine_note: str


class DatasetResponse(BaseModel):
    """The result of uploading or creating a dataset."""

    dataset: DatasetPayload
    message: str


class ForecastRunResponse(BaseModel):
    """The result of running a forecasting model."""

    run: ForecastRunPayload
    engine_note: str


class ForecastDetailResponse(BaseModel):
    """Everything the model result page renders."""

    run: ForecastRunPayload
    dataset: DatasetSummaryPayload
    history: list[ComparisonPointPayload] = Field(default_factory=list)
    validation: list[ComparisonPointPayload] = Field(default_factory=list)
    forecast: list[ForecastPointPayload] = Field(default_factory=list)
    metrics: MetricsPayload
    engine_note: str


class ForecastRequest(BaseModel):
    """The body of a forecast run request."""

    dataset_id: str
    horizon: int = Field(default=7, ge=1, le=30)
