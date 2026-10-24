"""FastAPI dependencies for settings, services, roles and origin checks."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.core.errors import AuthenticationError, InvalidOriginError, PermissionDeniedError
from app.core.security import SESSION_COOKIE_NAME, validate_origin
from app.services.datasets import DatasetService
from app.services.forecasts import ForecastService
from app.services.identity import IdentityService, UserProfile


def get_app_settings() -> Settings:
    """Return the application settings."""

    return get_settings()


def get_identity_service(settings: Annotated[Settings, Depends(get_app_settings)]) -> IdentityService:
    """Return the identity service."""

    return IdentityService(settings)


def get_dataset_service(settings: Annotated[Settings, Depends(get_app_settings)]) -> DatasetService:
    """Return the dataset service."""

    return DatasetService(settings)


def get_forecast_service(
    datasets: Annotated[DatasetService, Depends(get_dataset_service)],
) -> ForecastService:
    """Return the forecasting service."""

    return ForecastService(datasets)


async def current_user(
    request: Request,
    service: Annotated[IdentityService, Depends(get_identity_service)],
) -> UserProfile | None:
    """Return the signed-in account, or ``None`` for an anonymous visitor."""

    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return await service.current_user(token)


async def require_admin(user: Annotated[UserProfile | None, Depends(current_user)]) -> UserProfile:
    """Return the signed-in administrator.

    Raises:
        AuthenticationError: when nobody is signed in.
        PermissionDeniedError: when the account does not hold the admin role.
    """

    if user is None:
        raise AuthenticationError("Sign in is required.")
    if user.role != "admin":
        raise PermissionDeniedError("Administrator access is required.")
    return user


def application_origin(request: Request, *, require_csrf: bool = False) -> str:
    """Return the origin the request was made for and verify it against the browser.

    Raises:
        PermissionDeniedError: when the origins are missing or do not match.
    """

    settings = get_settings()
    try:
        app_origin = validate_origin(request.headers.get("x-application-origin", ""), settings)
    except InvalidOriginError as exc:
        raise PermissionDeniedError("A valid application origin is required.") from exc
    browser_origin = request.headers.get("origin", "")
    if require_csrf and not browser_origin:
        raise PermissionDeniedError("The request origin could not be verified.")
    if browser_origin:
        try:
            normalized_browser_origin = validate_origin(browser_origin, settings)
        except InvalidOriginError as exc:
            raise PermissionDeniedError("Cross-origin request blocked.") from exc
        if normalized_browser_origin != app_origin:
            raise PermissionDeniedError("Cross-origin request blocked.")
    return app_origin


def form_origin(request: Request) -> str:
    """Return the verified origin of a form submission.

    Raises:
        PermissionDeniedError: when the browser origin is missing or unknown.
    """

    try:
        return validate_origin(request.headers.get("origin", ""), get_settings())
    except InvalidOriginError as exc:
        raise PermissionDeniedError("Cross-origin request blocked.") from exc


def page_origin(request: Request) -> str:
    """Return the browser origin of a page request.

    The origin is derived from the ``Host`` header because a normal browser
    navigation sends no custom headers.

    Raises:
        PermissionDeniedError: when the host is not a registered origin.
    """

    host = request.headers.get("host", "").strip()
    settings = get_settings()
    if host:
        for scheme in ("https", "http"):
            try:
                return validate_origin(f"{scheme}://{host}", settings)
            except InvalidOriginError:
                continue
    raise PermissionDeniedError("A valid application origin is required.")


def form_request_origin(request: Request) -> str:
    """Return the verified origin of a form submission that targets a page.

    Raises:
        PermissionDeniedError: when the browser origin does not match the page.
    """

    origin = page_origin(request)
    browser_origin = request.headers.get("origin", "")
    if browser_origin:
        try:
            normalized = validate_origin(browser_origin, get_settings())
        except InvalidOriginError as exc:
            raise PermissionDeniedError("Cross-origin request blocked.") from exc
        if normalized != origin:
            raise PermissionDeniedError("Cross-origin request blocked.")
    return origin


def _origin_dependency(require_csrf: bool) -> Callable[[Request], str]:
    """Build a dependency that verifies the application origin of a request."""

    def dependency(request: Request) -> str:
        return application_origin(request, require_csrf=require_csrf)

    return dependency


read_origin = _origin_dependency(False)
write_origin = _origin_dependency(True)
