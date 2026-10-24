"""Shared fixtures for the test suite.

The environment is configured before the application package is imported so the
database and the local authentication settings are isolated from the developer
machine.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from constants import TEST_ORIGIN, TEST_PASSWORD, TEST_SESSION_SECRET, TEST_USERNAME

_WORKSPACE: Path = Path(tempfile.mkdtemp(prefix="paungflow-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_WORKSPACE / 'dashboard.db').as_posix()}"
os.environ["APP_MODE"] = "local"
os.environ["LOCAL_AUTH_ENABLED"] = "true"
os.environ["LOCAL_ADMIN_USERNAME"] = TEST_USERNAME
os.environ["LOCAL_ADMIN_PASSWORD"] = TEST_PASSWORD
os.environ["LOCAL_SESSION_SECRET"] = TEST_SESSION_SECRET
os.environ["APP_ALLOWED_ORIGINS"] = TEST_ORIGIN

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.core.security import issue_local_session  # noqa: E402
from app.db.base import SessionLocal  # noqa: E402
from app.db.models import AdminUser, Dataset, ForecastRun  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.identity import LOCAL_SOURCE, Identity, IdentityService  # noqa: E402


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    """Provide a test client that talks to an isolated database."""

    with TestClient(create_app(), base_url=TEST_ORIGIN) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_database(app_client: TestClient) -> Iterator[None]:
    """Start every test with an empty database."""

    with SessionLocal() as session:
        session.query(ForecastRun).delete()
        session.query(Dataset).delete()
        session.query(AdminUser).delete()
        session.commit()
    yield


@pytest.fixture
def signed_in_client(app_client: TestClient) -> Iterator[TestClient]:
    """Provide a test client that carries a valid administrator session."""

    settings = get_settings()
    IdentityService(settings).provision_user(
        Identity(open_id=f"local:{TEST_USERNAME}", name=TEST_USERNAME, email="", source=LOCAL_SOURCE)
    )
    app_client.cookies.set("webdev_app_session", issue_local_session(TEST_USERNAME, settings))
    yield app_client
    app_client.cookies.clear()


@pytest.fixture
def api_headers() -> dict[str, str]:
    """Return the headers the dashboard front end sends with API requests."""

    return {"x-application-origin": TEST_ORIGIN, "origin": TEST_ORIGIN}
