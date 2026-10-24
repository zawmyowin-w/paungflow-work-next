"""Tests for the CSV parsing and timestamp helpers of the domain layer."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.core.errors import DatasetValidationError, PayloadTooLargeError
from app.domain.series import (
    ParsedDataset,
    TimeSeriesPoint,
    future_labels,
    parse_csv_bytes,
    parse_timestamp,
)


def _csv(rows: int = 12, start_day: int = 1) -> bytes:
    """Return a small daily inflow CSV."""

    lines = ["date,inflow_m3_s"]
    for index in range(rows):
        lines.append(f"2024-01-{start_day + index:02d},{10 + index}")
    return "\n".join(lines).encode("utf-8")


def _parse(raw: bytes, *, max_rows: int = 100, min_observations: int = 8) -> ParsedDataset:
    return parse_csv_bytes(raw, "inflow.csv", max_rows=max_rows, min_observations=min_observations)


def test_parses_a_valid_csv() -> None:
    dataset = _parse(_csv())

    assert dataset.row_count == 12
    assert dataset.time_column == "date"
    assert dataset.target_column == "inflow_m3_s"
    assert dataset.start_label == "2024-01-01"
    assert dataset.end_label == "2024-01-12"
    assert dataset.latest_value == 21.0
    assert dataset.values[:3] == [10.0, 11.0, 12.0]


def test_rejects_duplicate_timestamps() -> None:
    raw = b"date,inflow\n2024-01-01,1\n2024-01-01,2\n2024-01-02,3"

    with pytest.raises(DatasetValidationError, match="repeats a timestamp"):
        _parse(raw)


def test_rejects_timestamps_that_are_not_increasing() -> None:
    raw = b"date,inflow\n2024-01-02,1\n2024-01-01,2\n2024-01-03,3"

    with pytest.raises(DatasetValidationError, match="strictly increasing"):
        _parse(raw)


def test_rejects_too_few_observations() -> None:
    with pytest.raises(DatasetValidationError, match="At least 8 valid numeric observations"):
        _parse(_csv(rows=4))


def test_rejects_too_many_rows() -> None:
    with pytest.raises(PayloadTooLargeError, match="up to 5 data rows"):
        _parse(_csv(rows=6), max_rows=5)


def test_rejects_files_that_are_not_utf8() -> None:
    with pytest.raises(DatasetValidationError, match="UTF-8"):
        _parse(b"date,inflow\n2024-01-01,\xff\xfe")


def test_rejects_a_single_column() -> None:
    with pytest.raises(DatasetValidationError, match="time column and at least one numeric"):
        _parse(b"date\n2024-01-01\n2024-01-02\n2024-01-03")


def test_rejects_duplicate_column_names() -> None:
    with pytest.raises(DatasetValidationError, match="unique after trimming"):
        _parse(b"date,inflow, inflow\n2024-01-01,1,2")


def test_rejects_a_file_without_numeric_values() -> None:
    with pytest.raises(DatasetValidationError, match="At least 8 valid numeric observations"):
        _parse(b"date,label\n2024-01-01,a\n2024-01-02,b")


def test_normalises_timestamps_to_utc() -> None:
    parsed = parse_timestamp("2024-01-01T06:00:00+06:00", 2)

    assert parsed == datetime(2024, 1, 1, 0, 0, 0)


def test_rejects_a_timestamp_that_is_not_iso8601() -> None:
    with pytest.raises(DatasetValidationError, match="ISO 8601"):
        parse_timestamp("not-a-date", 2)


def test_future_labels_follow_the_median_cadence() -> None:
    points = tuple(TimeSeriesPoint(label=f"2024-01-{day:02d}", value=float(day)) for day in range(1, 11))

    labels = future_labels(points, 3)

    assert labels == ["2024-01-11", "2024-01-12", "2024-01-13"]


def test_future_labels_keep_the_time_of_day_for_sub_daily_series() -> None:
    points = tuple(TimeSeriesPoint(label=f"2024-01-01T0{hour}:00:00", value=float(hour)) for hour in range(6))

    labels = future_labels(points, 2)

    assert labels == ["2024-01-01T06:00:00Z", "2024-01-01T07:00:00Z"]
