"""Security helpers: browser origins, OAuth state, and session tokens.

The functions here are pure and side-effect free so they can be unit tested
without a web server.
"""

from __future__ import annotations

import base64
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlsplit

import jwt

from app.config import LOCAL_HOSTNAMES, Settings
from app.core.errors import InvalidOriginError

SESSION_COOKIE_NAME: str = "webdev_app_session"
OAUTH_NONCE_COOKIE_NAME: str = "manus_oauth_nonce"
LOCAL_SESSION_APP_ID: str = "paungflow-local"
LOCAL_SESSION_AUTH_MODE: str = "local"

CookiePolicy = tuple[bool, Literal["none", "lax"]]


def is_project_preview_origin(origin: str, settings: Settings) -> bool:
    """Return ``True`` when the origin matches the hosted project preview pattern."""

    parsed = urlsplit(origin)
    pattern = re.compile(settings.preview_host_pattern)
    return parsed.scheme == "https" and parsed.port is None and bool(pattern.fullmatch(parsed.hostname or ""))


def validate_origin(value: str, settings: Settings) -> str:
    """Validate a browser origin and return it in normalised form.

    Raises:
        InvalidOriginError: when the value is not an origin of this application.
    """

    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise InvalidOriginError("A valid browser origin is required.")
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise InvalidOriginError("Only an origin, without a path or credentials, is accepted.")
    origin = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}".rstrip("/")
    if origin not in settings.browser_origins() and not is_project_preview_origin(origin, settings):
        raise InvalidOriginError("This browser origin is not registered for the application.")
    if parsed.scheme == "http" and parsed.hostname not in LOCAL_HOSTNAMES:
        raise InvalidOriginError("Non-local application origins must use HTTPS.")
    return origin


def make_state(redirect_uri: str, nonce: str) -> str:
    """Encode the OAuth ``state`` parameter."""

    payload = json.dumps({"redirectUri": redirect_uri, "nonce": nonce}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def parse_state(state: str) -> dict[str, str]:
    """Decode and validate an OAuth ``state`` parameter.

    Raises:
        ValueError: when the payload is malformed.
    """

    padding = "=" * (-len(state) % 4)
    payload = base64.urlsafe_b64decode(state + padding)
    value = json.loads(payload.decode())
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("redirectUri"), str)
        or not isinstance(value.get("nonce"), str)
    ):
        raise ValueError("Invalid sign-in state.")
    return value


def verify_preview_jwt(token: str, settings: Settings) -> dict | None:
    """Return the claims of a hosted preview token, or ``None`` when invalid."""

    secret = settings.manus_jwt_secret
    app_id = settings.manus_project_id
    if not secret or not app_id:
        return None
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["exp", "appId", "openId"], "verify_aud": False},
        )
    except jwt.PyJWTError:
        return None
    if claims.get("appId") != app_id or not claims.get("openId"):
        return None
    return claims


def issue_local_session(username: str, settings: Settings) -> str:
    """Sign a local session token for the configured administrator.

    Raises:
        RuntimeError: when local authentication is disabled or misconfigured.
    """

    if not settings.local_session_is_configured():
        raise RuntimeError("Local authentication is disabled or not fully configured.")
    now = datetime.now(UTC)
    claims = {
        "openId": f"local:{username}",
        "name": username,
        "appId": LOCAL_SESSION_APP_ID,
        "authMode": LOCAL_SESSION_AUTH_MODE,
        "iat": now,
        "exp": now + timedelta(hours=settings.session_ttl_hours),
    }
    return jwt.encode(claims, settings.local_session_secret or "", algorithm="HS256")


def verify_local_session(token: str, settings: Settings) -> dict | None:
    """Return the claims of a local session token, or ``None`` when invalid."""

    if not settings.local_session_is_configured():
        return None
    try:
        claims = jwt.decode(
            token,
            settings.local_session_secret or "",
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "openId", "appId", "authMode"]},
        )
    except jwt.PyJWTError:
        return None
    expected_username = settings.local_admin_username
    if claims.get("appId") != LOCAL_SESSION_APP_ID or claims.get("authMode") != LOCAL_SESSION_AUTH_MODE:
        return None
    if claims.get("openId") != f"local:{expected_username}" or claims.get("name") != expected_username:
        return None
    return {
        "open_id": str(claims["openId"]),
        "name": expected_username[:191],
        "email": "",
        "source": "local",
    }


def cookie_policy(origin: str) -> CookiePolicy:
    """Return the ``(secure, same_site)`` cookie policy for an origin."""

    secure = urlsplit(origin).scheme == "https"
    return secure, "none" if secure else "lax"


def constant_time_equals(left: str, right: str) -> bool:
    """Compare two secrets without leaking their length through timing."""

    return secrets.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
