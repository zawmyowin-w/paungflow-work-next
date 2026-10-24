"""Time-series domain objects, CSV parsing, and timestamp helpers."""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median

from app.core.errors import DatasetValidationError, PayloadTooLargeError

DATE_ONLY_FORMAT: str = "%Y-%m-%d"
LABEL_MAX_LENGTH: int = 80
VALUE_PRECISION: int = 6
CADENCE_SAMPLE_SIZE: int = 31
MINIMUM_HEADERS: int = 2
TIME_COLUMN_TOKENS: tuple[str, ...] = ("date", "time", "timestamp")
TARGET_COLUMN_TOKENS: tuple[str, ...] = ("inflow", "discharge", "flow", "volume")


@dataclass(frozen=True, slots=True)
class TimeSeriesPoint:
    """A single observation: the original label and its numeric value."""

    label: str
    value: float

    def as_dict(self) -> dict[str, object]:
        """Return the JSON friendly representation stored in the database."""

        return {"label": self.label, "value": self.value}


@dataclass(frozen=True, slots=True)
class ParsedDataset:
    """A validated time series ready to be stored and forecast."""

    points: tuple[TimeSeriesPoint, ...]
    time_column: str
    target_column: str
    filename: str
    raw_text: str

    @property
    def row_count(self) -> int:
        """Return the number of observations in the series."""

        return len(self.points)

    @property
    def start_label(self) -> str:
        """Return the label of the first observation."""

        return self.points[0].label

    @property
    def end_label(self) -> str:
        """Return the label of the last observation."""

        return self.points[-1].label

    @property
    def values(self) -> list[float]:
        """Return the observation values in row order."""

        return [point.value for point in self.points]

    @property
    def latest_value(self) -> float:
        """Return the most recent observation value."""

        return self.points[-1].value

    def points_payload(self) -> list[dict[str, object]]:
        """Return the points in the JSON shape persisted in the database."""

        return [point.as_dict() for point in self.points]


def parse_timestamp(value: str, row_number: int) -> datetime:
    """Parse an ISO 8601 timestamp into a naive UTC datetime.

    Raises:
        DatasetValidationError: when the value is not an ISO 8601 timestamp.
    """

    normalized = value.strip()
    if normalized.endswith(("Z", "z")):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%Y %b %d", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(normalized.replace("Z", "").replace("+00:00", ""), fmt)
                break
            except ValueError:
                parsed = None
        if parsed is None:
            raise DatasetValidationError(f"CSV row {row_number} needs an ISO 8601 timestamp.")
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def future_labels(points: Sequence[TimeSeriesPoint], horizon: int) -> list[str]:
    """Return the labels of the ``horizon`` observations that follow the series."""

    timestamps = [parse_timestamp(point.label, index + 2) for index, point in enumerate(points)]
    recent = timestamps[-CADENCE_SAMPLE_SIZE:]
    intervals = sorted(
        (right - left).total_seconds()
        for left, right in zip(recent, recent[1:], strict=False)
        if right > left
    )
    cadence = timedelta(seconds=median(intervals)) if intervals else timedelta(days=1)
    last = timestamps[-1]
    labels: list[str] = []
    for step in range(1, horizon + 1):
        future = last + cadence * step
        if future.time() == datetime.min.time():
            labels.append(future.strftime(DATE_ONLY_FORMAT))
        else:
            labels.append(future.isoformat(timespec="seconds") + "Z")
    return labels


def parse_csv_bytes(
    raw: bytes,
    filename: str,
    *,
    max_rows: int,
    min_observations: int,
) -> ParsedDataset:
    """Validate an uploaded CSV and return the parsed time series.

    Raises:
        DatasetValidationError: when the file is not a usable time series.
        PayloadTooLargeError: when the file contains more rows than allowed.
    """

    text = _decode_csv(raw)
    headers, rows = _read_table(text)
    enforce_row_limit(len(rows), max_rows)
    time_column = _detect_time_column(headers)
    target_column = _detect_target_column(headers, time_column, rows)
    points = _extract_points(rows, time_column, target_column)
    if len(points) < min_observations:
        raise DatasetValidationError(
            f"At least {min_observations} valid numeric observations are required for forecasting."
        )
    return ParsedDataset(
        points=tuple(points),
        time_column=time_column,
        target_column=target_column,
        filename=filename,
        raw_text=text,
    )


def _decode_csv(raw: bytes) -> str:
    """Decode the uploaded bytes as UTF-8 text."""

    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DatasetValidationError("CSV must be encoded as UTF-8.") from exc


def _read_table(text: str) -> tuple[list[str], list[dict[str, str | None]]]:
    """Read the CSV into a header list and a list of row dictionaries."""

    reader = csv.DictReader(io.StringIO(text))
    headers = [str(header or "").strip() for header in (reader.fieldnames or [])]
    reader.fieldnames = headers
    if len(headers) < MINIMUM_HEADERS:
        raise DatasetValidationError("CSV needs a time column and at least one numeric column.")
    if len(set(headers)) != len(headers):
        raise DatasetValidationError("CSV column names must be unique after trimming spaces.")
    return headers, list(reader)


def _normalize(header: str) -> str:
    """Return a header reduced to comparable alphanumeric characters."""

    return "".join(character for character in header.lower() if character.isalnum())


def _detect_time_column(headers: Sequence[str]) -> str:
    """Return the column that holds the timestamps."""

    for header in headers:
        if any(token in _normalize(header) for token in TIME_COLUMN_TOKENS):
            return header
    # check if first is date-like
    return headers[0]


def _detect_target_column(
    headers: Sequence[str],
    time_column: str,
    rows: Sequence[dict[str, str | None]],
) -> str:
    """Return the numeric column that holds the measured values."""

    numeric_counts = {header: _numeric_count(rows, header) for header in headers if header != time_column}
    candidates = [
        header for header in headers if any(token in _normalize(header) for token in TARGET_COLUMN_TOKENS)
    ]
    if candidates:
        best = max(candidates, key=lambda header: numeric_counts.get(header, 0))
        if numeric_counts.get(best, 0) == 0:
            # try any numeric
            if numeric_counts:
                return max(numeric_counts, key=lambda header: numeric_counts[header])
        return best
    if numeric_counts:
        return max(numeric_counts, key=lambda header: numeric_counts[header])
    raise DatasetValidationError("No numeric time-series column was found.")


def _numeric_count(rows: Sequence[dict[str, str | None]], header: str) -> int:
    """Return how many rows hold a finite number in the given column."""

    count = 0
    for row in rows:
        value = _cell_to_float(row.get(header))
        if value is not None:
            count += 1
    return count


def _cell_to_float(raw: str | None) -> float | None:
    """Return the cell as a finite float, or ``None`` when it is not numeric."""

    text = str(raw or "").strip().replace(",", "")
    try:
        value = float(text)
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) else None


def _extract_points(
    rows: Sequence[dict[str, str | None]],
    time_column: str,
    target_column: str,
) -> list[TimeSeriesPoint]:
    """Return the ordered observations, rejecting duplicate or unordered timestamps."""

    points: list[TimeSeriesPoint] = []
    seen_timestamps: set[datetime] = set()
    previous_timestamp: datetime | None = None
    for index, row in enumerate(rows):
        label = str(row.get(time_column, "") or "").strip() or str(index + 1)
        value = _cell_to_float(row.get(target_column))
        if value is None:
            continue
        timestamp = parse_timestamp(label, index + 2)
        if timestamp in seen_timestamps:
            raise DatasetValidationError(
                f"CSV row {index + 2} repeats a timestamp; timestamps must be unique."
            )
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise DatasetValidationError("Time-series timestamps must be strictly increasing in row order.")
        seen_timestamps.add(timestamp)
        previous_timestamp = timestamp
        points.append(TimeSeriesPoint(label=label[:LABEL_MAX_LENGTH], value=round(value, VALUE_PRECISION)))
    return points


def enforce_row_limit(row_count: int, max_rows: int) -> None:
    """Reject datasets that contain more rows than the application accepts.

    Raises:
        PayloadTooLargeError: when the row count exceeds the limit.
    """

    if row_count > max_rows:
        raise PayloadTooLargeError(f"This prototype accepts up to {max_rows:,} data rows per CSV.")
