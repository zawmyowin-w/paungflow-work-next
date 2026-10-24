"""Light and dark theme handling with a plain cookie."""

from __future__ import annotations

from fastapi import Request, Response

THEME_COOKIE_NAME: str = "paung-dam-theme"
LIGHT_THEME: str = "light"
DARK_THEME: str = "dark"
DEFAULT_THEME: str = LIGHT_THEME
THEME_MAX_AGE_SECONDS: int = 365 * 24 * 3600


def read_theme(request: Request) -> str:
    """Return the theme the browser selected."""

    value = request.cookies.get(THEME_COOKIE_NAME, "")
    return DARK_THEME if value == DARK_THEME else DEFAULT_THEME


def apply_theme(response: Response, theme: str) -> None:
    """Store the selected theme in the browser cookie."""

    response.set_cookie(
        THEME_COOKIE_NAME,
        DARK_THEME if theme == DARK_THEME else LIGHT_THEME,
        max_age=THEME_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )
