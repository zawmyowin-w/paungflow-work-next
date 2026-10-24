"""Sign-in, local sign-in, OAuth callback and sign-out routes."""

from __future__ import annotations

import logging
import secrets
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.api.dependencies import form_origin, get_app_settings, get_identity_service
from app.config import LOCAL_HOSTNAMES, Settings
from app.core.errors import BadRequestError, InvalidOriginError, NotFoundError, ServiceUnavailableError
from app.core.oauth import exchange_code, fetch_manus_user
from app.core.security import (
    OAUTH_NONCE_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    constant_time_equals,
    cookie_policy,
    issue_local_session,
    make_state,
    parse_state,
    validate_origin,
)
from app.services.identity import LOCAL_SOURCE, OAUTH_SOURCE, Identity, IdentityService, UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(tags=["authentication"])

NONCE_MAX_AGE_SECONDS: int = 600
NONCE_BYTES: int = 32


@router.get("/auth/login")
async def begin_login(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> RedirectResponse:
    """Start the Manus sign-in flow."""

    try:
        origin = validate_origin(request.query_params.get("origin", ""), settings)
    except InvalidOriginError as exc:
        raise BadRequestError(str(exc)) from exc
    if not settings.manus_project_id or not settings.manus_oauth_portal_url:
        raise ServiceUnavailableError("Manus account sign-in is not configured.")
    redirect_uri = f"{origin}/auth/callback"
    nonce = secrets.token_urlsafe(NONCE_BYTES)
    state = make_state(redirect_uri, nonce)
    auth_url = (
        f"{settings.manus_oauth_portal_url}/app-auth?appId={quote(settings.manus_project_id)}"
        f"&redirectUri={quote(redirect_uri, safe='')}&state={quote(state, safe='')}&responseType=code"
    )
    response = RedirectResponse(auth_url, status_code=302)
    secure, same_site = cookie_policy(origin)
    response.set_cookie(
        OAUTH_NONCE_COOKIE_NAME,
        nonce,
        max_age=NONCE_MAX_AGE_SECONDS,
        httponly=True,
        secure=secure,
        samesite=same_site,
        path="/",
    )
    return response


@router.post("/auth/local-login")
async def local_login(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
    identity_service: Annotated[IdentityService, Depends(get_identity_service)],
) -> RedirectResponse:
    """Sign in with the local administrator account."""

    if not settings.local_auth_enabled or request.url.hostname not in LOCAL_HOSTNAMES:
        raise NotFoundError("Local sign-in is available only in local mode on localhost.")
    origin = form_origin(request)
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    expected_username = settings.local_admin_username
    expected_password = settings.local_admin_password or ""
    username_ok = constant_time_equals(username, expected_username)
    password_ok = constant_time_equals(password, expected_password)
    if not (username_ok and password_ok):
        return RedirectResponse("/?auth=local-failed", status_code=303)
    user = identity_service.provision_user(
        Identity(open_id=f"local:{expected_username}", name=expected_username, email="", source=LOCAL_SOURCE)
    )
    if user.role != "admin":
        return RedirectResponse("/?auth=not-admin", status_code=303)
    response = RedirectResponse("/dashboard", status_code=303)
    secure, same_site = cookie_policy(origin)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        issue_local_session(expected_username, settings),
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=secure,
        samesite=same_site,
        path="/",
    )
    return response


@router.get("/auth/callback")
async def oauth_callback(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
    identity_service: Annotated[IdentityService, Depends(get_identity_service)],
) -> RedirectResponse:
    """Complete the Manus sign-in flow and start the session."""

    try:
        origin, access_token, user = await _complete_oauth(request, settings, identity_service)
    except Exception as exc:
        logger.info("OAuth callback failed: %s", type(exc).__name__)
        response = RedirectResponse("/?auth=failed", status_code=303)
        response.delete_cookie(OAUTH_NONCE_COOKIE_NAME, path="/")
        return response
    if user.role != "admin":
        return RedirectResponse("/?auth=not-admin", status_code=303)
    response = RedirectResponse(f"{origin}/dashboard", status_code=303)
    secure, same_site = cookie_policy(origin)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        access_token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=secure,
        samesite=same_site,
        path="/",
    )
    response.delete_cookie(OAUTH_NONCE_COOKIE_NAME, path="/", secure=secure, samesite=same_site)
    return response


@router.post("/auth/logout")
async def logout(request: Request) -> RedirectResponse:
    """End the session and return to the sign-in page."""

    origin = form_origin(request)
    response = RedirectResponse("/", status_code=303)
    secure, same_site = cookie_policy(origin)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", secure=secure, samesite=same_site)
    return response


async def _complete_oauth(
    request: Request,
    settings: Settings,
    identity_service: IdentityService,
) -> tuple[str, str, UserProfile]:
    """Exchange the authorization code and register the account behind it.

    Raises:
        ValueError: when the state does not belong to this browser session.
        RuntimeError: when the upstream service does not return an account.
    """

    state_cookie = request.cookies.get(OAUTH_NONCE_COOKIE_NAME, "")
    state = parse_state(request.query_params.get("state", ""))
    redirect_uri = state["redirectUri"]
    origin = validate_origin(redirect_uri.removesuffix("/auth/callback"), settings)
    nonce_matches = constant_time_equals(state.get("nonce", ""), state_cookie)
    if redirect_uri != f"{origin}/auth/callback" or not nonce_matches:
        raise ValueError("OAuth state did not match this browser session.")
    code = request.query_params.get("code", "")
    if not code:
        raise ValueError("Authorization code was not provided.")
    access_token = await exchange_code(code, redirect_uri, settings)
    profile = await fetch_manus_user(access_token, settings)
    user = identity_service.provision_user(
        Identity(
            open_id=profile["open_id"],
            name=profile["name"],
            email=profile["email"],
            source=OAUTH_SOURCE,
        )
    )
    return origin, access_token, user
