"""Synthetic demonstration dataset used by the "Try synthetic sample" action."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from app.domain.series import ParsedDataset, TimeSeriesPoint

SAMPLE_LENGTH: int = 120
SAMPLE_START: datetime = datetime(2025, 1, 1)
SAMPLE_TIME_COLUMN: str = "date"
SAMPLE_TARGET_COLUMN: str = "inflow_m3_s"
SAMPLE_FILENAME: str = "synthetic-demo-inflow.csv"
SAMPLE_BASE_LEVEL: float = 26.0
SAMPLE_LONG_WAVE_AMPLITUDE: float = 7.5
SAMPLE_LONG_WAVE_PERIOD: float = 42.0
SAMPLE_SHORT_WAVE_AMPLITUDE: float = 4.2
SAMPLE_SHORT_WAVE_PERIOD: float = 15.0
SAMPLE_TREND_PER_STEP: float = 0.035
SAMPLE_MINIMUM_VALUE: float = 4.0


def build_synthetic_dataset() -> ParsedDataset:
    """Return a clearly labelled synthetic series for interface demonstration."""

    points: list[TimeSeriesPoint] = []
    lines: list[str] = [f"{SAMPLE_TIME_COLUMN},{SAMPLE_TARGET_COLUMN}"]
    for index in range(SAMPLE_LENGTH):
        value = round(_sample_value(index), 3)
        label = (SAMPLE_START + timedelta(days=index)).strftime("%Y-%m-%d")
        points.append(TimeSeriesPoint(label=label, value=value))
        lines.append(f"{label},{value}")
    return ParsedDataset(
        points=tuple(points),
        time_column=SAMPLE_TIME_COLUMN,
        target_column=SAMPLE_TARGET_COLUMN,
        filename=SAMPLE_FILENAME,
        raw_text="\n".join(lines),
    )


def _sample_value(index: int) -> float:
    """Return the synthetic inflow value of one day."""

    seasonal = (
        SAMPLE_BASE_LEVEL
        + SAMPLE_LONG_WAVE_AMPLITUDE * math.sin(index * 2 * math.pi / SAMPLE_LONG_WAVE_PERIOD)
        + SAMPLE_SHORT_WAVE_AMPLITUDE * math.sin(index * 2 * math.pi / SAMPLE_SHORT_WAVE_PERIOD)
    )
    trend = index * SAMPLE_TREND_PER_STEP
    return max(SAMPLE_MINIMUM_VALUE, seasonal + trend)
