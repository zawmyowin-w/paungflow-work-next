"""Routes that serve the stylesheets and scripts that are written in Python.

The browser loads the interface from ``/static/css`` and ``/static/js`` as
usual, but the content is generated from Python modules instead of files that
are shipped next to the application.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.core.errors import NotFoundError
from app.web.assets import SCRIPTS, STYLESHEETS

router = APIRouter(tags=["assets"], include_in_schema=False)


@router.get("/static/css/{name}.css")
def stylesheet(name: str) -> PlainTextResponse:
    """Serve a stylesheet that is defined in a Python module."""

    source = STYLESHEETS.get(name)
    if source is None:
        raise NotFoundError("Stylesheet not found.")
    return PlainTextResponse(source, media_type="text/css")


@router.get("/static/js/{name}.js")
def script(name: str) -> PlainTextResponse:
    """Serve a browser script that is defined in a Python module."""

    source = SCRIPTS.get(name)
    if source is None:
        raise NotFoundError("Script not found.")
    return PlainTextResponse(source, media_type="text/javascript")
