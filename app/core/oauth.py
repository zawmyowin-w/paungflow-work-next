"""Client for the Manus OAuth and account-information endpoints."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.core.errors import ServiceUnavailableError

EXCHANGE_TIMEOUT_SECONDS: float = 20.0
USER_INFO_TIMEOUT_SECONDS: float = 15.0
AUTH_SERVICE_PATH: str = "/webdev.v1.WebDevAuthPublicService"


async def exchange_code(code: str, redirect_uri: str, settings: Settings) -> str:
    """Exchange an authorization code for an access token.

    Raises:
        ServiceUnavailableError: when the OAuth environment is not configured.
        RuntimeError: when the upstream service does not return a token.
    """

    if not settings.manus_project_id or not settings.manus_oauth_api_url:
        raise ServiceUnavailableError("Manus account sign-in is not configured.")
    url = f"{settings.manus_oauth_api_url}{AUTH_SERVICE_PATH}/ExchangeToken"
    async with httpx.AsyncClient(timeout=EXCHANGE_TIMEOUT_SECONDS) as client:
        response = await client.post(
            url,
            json={
                "clientId": settings.manus_project_id,
                "grantType": "authorization_code",
                "code": code,
                "redirectUri": redirect_uri,
            },
            headers={"Content-Type": "application/json", "connect-protocol-version": "1"},
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
    access_token = result.get("accessToken")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("OAuth exchange did not return an access token.")
    return access_token


async def fetch_manus_user(access_token: str, settings: Settings) -> dict[str, str]:
    """Return the account details that belong to an access token.

    Raises:
        ServiceUnavailableError: when the OAuth environment is not configured.
        RuntimeError: when the upstream response has no account id.
    """

    if not settings.manus_oauth_api_url:
        raise ServiceUnavailableError("Manus account sign-in is not configured.")
    url = f"{settings.manus_oauth_api_url}{AUTH_SERVICE_PATH}/GetUserInfo"
    async with httpx.AsyncClient(timeout=USER_INFO_TIMEOUT_SECONDS) as client:
        response = await client.post(
            url,
            json={"accessToken": access_token},
            headers={"Content-Type": "application/json", "connect-protocol-version": "1"},
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
    identity = result.get("userInfo", result)
    open_id = identity.get("openId")
    if not isinstance(open_id, str) or not open_id:
        raise RuntimeError("Manus identity response did not include an account ID.")
    return {
        "open_id": open_id,
        "name": str(identity.get("name") or "Manus Administrator")[:191],
        "email": str(identity.get("email") or "")[:320],
    }
