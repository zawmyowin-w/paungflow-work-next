"""Environment-driven configuration for the dam forecasting dashboard.

Every module reads its configuration through :func:`get_settings` instead of
touching ``os.environ`` directly.  That keeps the environment contract of the
application documented in one place and makes the settings easy to override in
tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
TEMPLATES_DIR: Path = PROJECT_ROOT / "templates"
STATIC_DIR: Path = PROJECT_ROOT / "static"
ROUTE_MANIFEST_PATH: Path = PROJECT_ROOT / "public" / "manus-routes.json"

TRUTHY_VALUES: frozenset[str] = frozenset({"1", "true", "yes", "on"})

PREVIEW_ORIGIN: str = "https://8328-iwmrvb1uox9hjxchfrvyf-e0c236d2.us5.manus.computer"
PREVIEW_HOST_PATTERN: str = r"^[0-9]+-iwmrvb1uox9hjxchfrvyf-e0c236d2\.us5\.manus\.computer$"
LOCAL_HOSTNAMES: frozenset[str] = frozenset({"localhost", "127.0.0.1"})
BUILTIN_LOCAL_ORIGINS: frozenset[str] = frozenset({"http://localhost:3000", "http://127.0.0.1:3000"})

MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024
MAX_CSV_ROWS: int = 20_000
MIN_OBSERVATIONS: int = 8
SESSION_TTL_HOURS: int = 8
LOCAL_SESSION_SECRET_MIN_LENGTH: int = 32


def _raw(name: str) -> str:
    """Return an environment value verbatim (secrets may contain any character)."""

    return os.getenv(name, "")


def _text(name: str, default: str = "") -> str:
    """Return a trimmed, non-sensitive environment value."""

    return os.getenv(name, default).strip()


def _optional(name: str) -> str | None:
    """Return an environment value, or ``None`` when it is missing or blank."""

    value = os.getenv(name, "")
    return value if value.strip() else None


def _flag(name: str) -> bool:
    """Return ``True`` when the environment flag holds a truthy value."""

    return os.getenv(name, "").strip().lower() in TRUTHY_VALUES


def _origins(name: str) -> tuple[str, ...]:
    """Return comma separated origins as a tuple of normalised values."""

    raw = os.getenv(name, "")
    return tuple(item.strip().rstrip("/") for item in raw.split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable snapshot of the environment the application runs with."""

    app_mode: str
    local_auth_enabled: bool
    local_admin_username: str
    local_admin_password: str | None
    local_session_secret: str | None
    database_url: str
    allowed_origins: tuple[str, ...]
    manus_project_id: str | None
    manus_oauth_portal_url: str
    manus_oauth_api_url: str
    manus_jwt_secret: str | None
    preview_origin: str
    preview_host_pattern: str
    max_upload_bytes: int = MAX_UPLOAD_BYTES
    max_csv_rows: int = MAX_CSV_ROWS
    min_observations: int = MIN_OBSERVATIONS
    session_ttl_hours: int = SESSION_TTL_HOURS

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from the current process environment."""

        app_mode = _text("APP_MODE").lower()
        local_password = _optional("LOCAL_ADMIN_PASSWORD")
        local_secret = _optional("LOCAL_SESSION_SECRET")
        local_enabled = (
            app_mode == "local"
            and _flag("LOCAL_AUTH_ENABLED")
            and local_password is not None
            and local_secret is not None
            and len(local_secret) >= LOCAL_SESSION_SECRET_MIN_LENGTH
        )
        return cls(
            app_mode=app_mode,
            local_auth_enabled=local_enabled,
            local_admin_username=_text("LOCAL_ADMIN_USERNAME", "admin") or "admin",
            local_admin_password=local_password,
            local_session_secret=local_secret,
            database_url=_text("DATABASE_URL"),
            allowed_origins=_origins("APP_ALLOWED_ORIGINS"),
            manus_project_id=_optional("MANUS_PROJECT_ID"),
            manus_oauth_portal_url=_text("MANUS_OAUTH_PORTAL_URL").rstrip("/"),
            manus_oauth_api_url=_text("MANUS_OAUTH_API_URL").rstrip("/"),
            manus_jwt_secret=_optional("MANUS_JWT_SECRET"),
            preview_origin=PREVIEW_ORIGIN,
            preview_host_pattern=PREVIEW_HOST_PATTERN,
        )

    def browser_origins(self) -> frozenset[str]:
        """Return every origin the application accepts requests from."""

        return frozenset(self.allowed_origins) | BUILTIN_LOCAL_ORIGINS | {self.preview_origin}

    def local_session_is_configured(self) -> bool:
        """Return ``True`` when a local session can be signed and verified."""

        secret = self.local_session_secret
        return self.local_auth_enabled and secret is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, reading the environment on first use."""

    return Settings.from_env()


def reset_settings_cache() -> None:
    """Clear the cached settings so the next call re-reads the environment."""

    get_settings.cache_clear()
