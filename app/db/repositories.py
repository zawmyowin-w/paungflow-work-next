"""Repositories: the only place that knows how datasets and runs are stored."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AdminUser, Dataset, ForecastRun


class UserRepository:
    """Read and write access to :class:`~app.db.models.AdminUser` rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_open_id(self, open_id: str) -> AdminUser | None:
        """Return the account with this identity, if it exists."""

        return self._session.scalar(select(AdminUser).where(AdminUser.open_id == open_id))

    def count(self) -> int:
        """Return the number of registered accounts."""

        return self._session.scalar(select(func.count(AdminUser.id))) or 0

    def add(self, user: AdminUser) -> None:
        """Stage a new account for insertion."""

        self._session.add(user)


class DatasetRepository:
    """Read and write access to :class:`~app.db.models.Dataset` rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, dataset_id: str, owner_open_id: str, scope_origin: str) -> Dataset | None:
        """Return a dataset that belongs to the owner and origin scope."""

        return self._session.scalar(
            select(Dataset).where(
                Dataset.id == dataset_id,
                Dataset.owner_open_id == owner_open_id,
                Dataset.scope_origin == scope_origin,
            )
        )

    def latest_for(self, owner_open_id: str, scope_origin: str) -> Dataset | None:
        """Return the most recently uploaded dataset of the owner and scope."""

        return self._session.scalar(
            select(Dataset)
            .where(Dataset.owner_open_id == owner_open_id, Dataset.scope_origin == scope_origin)
            .order_by(Dataset.uploaded_at.desc())
            .limit(1)
        )

    def add(self, dataset: Dataset) -> None:
        """Stage a new dataset for insertion."""

        self._session.add(dataset)


class ForecastRunRepository:
    """Read and write access to :class:`~app.db.models.ForecastRun` rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, run_id: int, owner_open_id: str, scope_origin: str) -> ForecastRun | None:
        """Return a forecast run that belongs to the owner and origin scope."""

        return self._session.scalar(
            select(ForecastRun).where(
                ForecastRun.id == run_id,
                ForecastRun.owner_open_id == owner_open_id,
                ForecastRun.scope_origin == scope_origin,
            )
        )

    def list_for_dataset(
        self, dataset_id: str, owner_open_id: str, scope_origin: str, limit: int
    ) -> list[ForecastRun]:
        """Return the newest forecast runs of a dataset."""

        return list(
            self._session.scalars(
                select(ForecastRun)
                .where(
                    ForecastRun.dataset_id == dataset_id,
                    ForecastRun.owner_open_id == owner_open_id,
                    ForecastRun.scope_origin == scope_origin,
                )
                .order_by(ForecastRun.created_at.desc())
                .limit(limit)
            ).all()
        )

    def add(self, run: ForecastRun) -> None:
        """Stage a new forecast run for insertion."""

        self._session.add(run)
