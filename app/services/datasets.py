"""Dataset ingestion, validation and persistence."""

from __future__ import annotations

import json
import uuid

from app.config import Settings
from app.db.base import session_scope, utc_now
from app.db.models import Dataset
from app.db.repositories import DatasetRepository
from app.domain.records import DatasetRecord
from app.domain.series import ParsedDataset, TimeSeriesPoint, parse_csv_bytes
from app.domain.synthetic import build_synthetic_dataset


class DatasetService:
    """Store and read the time series that back the dashboard."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_from_upload(
        self,
        *,
        owner_open_id: str,
        scope_origin: str,
        filename: str,
        raw: bytes,
    ) -> DatasetRecord:
        """Validate an uploaded CSV and store it for the owner."""

        parsed = parse_csv_bytes(
            raw,
            filename,
            max_rows=self._settings.max_csv_rows,
            min_observations=self._settings.min_observations,
        )
        return self._store(
            parsed=parsed,
            owner_open_id=owner_open_id,
            scope_origin=scope_origin,
            is_demo=False,
        )

    def create_synthetic_sample(self, *, owner_open_id: str, scope_origin: str) -> DatasetRecord:
        """Store the labelled synthetic sample used for interface demonstration."""

        parsed = build_synthetic_dataset()
        return self._store(
            parsed=parsed,
            owner_open_id=owner_open_id,
            scope_origin=scope_origin,
            is_demo=True,
        )

    def latest(self, *, owner_open_id: str, scope_origin: str) -> DatasetRecord | None:
        """Return the most recently uploaded dataset of the owner and scope."""

        with session_scope() as session:
            dataset = DatasetRepository(session).latest_for(owner_open_id, scope_origin)
            return _to_record(dataset) if dataset is not None else None

    def get(self, *, dataset_id: str, owner_open_id: str, scope_origin: str) -> DatasetRecord | None:
        """Return a dataset of the owner and scope, or ``None``."""

        with session_scope() as session:
            dataset = DatasetRepository(session).find_by_id(dataset_id, owner_open_id, scope_origin)
            return _to_record(dataset) if dataset is not None else None

    def _store(
        self,
        *,
        parsed: ParsedDataset,
        owner_open_id: str,
        scope_origin: str,
        is_demo: bool,
    ) -> DatasetRecord:
        """Persist a parsed dataset and return the stored record."""

        dataset = Dataset(
            id=str(uuid.uuid4()),
            owner_open_id=owner_open_id,
            scope_origin=scope_origin,
            filename=parsed.filename,
            row_count=parsed.row_count,
            time_column=parsed.time_column,
            target_column=parsed.target_column,
            start_label=parsed.start_label,
            end_label=parsed.end_label,
            latest_value=parsed.latest_value,
            is_demo=is_demo,
            points_json=json.dumps(parsed.points_payload(), separators=(",", ":")),
            raw_csv=parsed.raw_text,
            uploaded_at=utc_now(),
        )
        with session_scope() as session:
            DatasetRepository(session).add(dataset)
            session.flush()
            session.refresh(dataset)
            return _to_record(dataset)


def _to_record(dataset: Dataset) -> DatasetRecord:
    """Convert a stored dataset into a :class:`DatasetRecord`."""

    return DatasetRecord(
        id=dataset.id,
        filename=dataset.filename,
        row_count=dataset.row_count,
        time_column=dataset.time_column,
        target_column=dataset.target_column,
        start_label=dataset.start_label,
        end_label=dataset.end_label,
        latest_value=dataset.latest_value,
        is_demo=bool(dataset.is_demo),
        points=_parse_points(dataset.points_json),
        uploaded_at=dataset.uploaded_at,
    )


def _parse_points(raw: str) -> tuple[TimeSeriesPoint, ...]:
    """Return the stored observations of a dataset."""

    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return ()
    if not isinstance(payload, list):
        return ()
    points: list[TimeSeriesPoint] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            points.append(TimeSeriesPoint(label=str(item["label"]), value=float(item["value"])))
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(points)
