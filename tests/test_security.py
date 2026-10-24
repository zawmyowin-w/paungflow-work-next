"""Tests for the origin validation and session helpers."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.core.errors import InvalidOriginError
from app.core.security import (
    constant_time_equals,
    cookie_policy,
    issue_local_session,
    make_state,
    parse_state,
    validate_origin,
    verify_local_session,
)


def test_accepts_a_registered_origin() -> None:
    settings = get_settings()

    assert validate_origin("http://localhost:3000", settings) == "http://localhost:3000"


def test_rejects_an_unregistered_origin() -> None:
    settings = get_settings()

    with pytest.raises(InvalidOriginError, match="not registered"):
        validate_origin("https://example.com", settings)


def test_rejects_an_origin_with_a_path() -> None:
    settings = get_settings()

    with pytest.raises(InvalidOriginError, match="without a path"):
        validate_origin("http://localhost:3000/dashboard", settings)


def test_rejects_plain_http_for_remote_hosts() -> None:
    settings = get_settings()

    with pytest.raises(InvalidOriginError, match="not registered"):
        validate_origin("http://example.com", settings)


def test_rejects_credentials_in_the_origin() -> None:
    settings = get_settings()

    with pytest.raises(InvalidOriginError, match="credentials"):
        validate_origin("http://user:pass@localhost:3000", settings)


def test_state_round_trip() -> None:
    state = make_state("http://localhost:3000/auth/callback", "nonce-value")

    assert parse_state(state) == {
        "redirectUri": "http://localhost:3000/auth/callback",
        "nonce": "nonce-value",
    }


def test_invalid_state_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_state("not-base64-json")


def test_cookie_policy_depends_on_the_scheme() -> None:
    assert cookie_policy("https://example.org") == (True, "none")
    assert cookie_policy("http://localhost:3000") == (False, "lax")


def test_local_session_round_trip() -> None:
    settings = get_settings()
    token = issue_local_session(settings.local_admin_username, settings)

    claims = verify_local_session(token, settings)

    assert claims is not None
    assert claims["open_id"] == f"local:{settings.local_admin_username}"
    assert claims["source"] == "local"


def test_constant_time_comparison() -> None:
    assert constant_time_equals("secret", "secret")
    assert not constant_time_equals("secret", "secrets")
