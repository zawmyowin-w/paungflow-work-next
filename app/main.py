"""Application factory and entry point.

Start the dashboard with ``uvicorn app.main:app``.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import actions, api_router, assets
from app.config import STATIC_DIR
from app.core.errors import AppError
from app.db.schema import init_db

logger = logging.getLogger(__name__)

APP_TITLE: str = "Lower Paung-Luang Dam Forecasting System"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Prepare the database before the application starts serving requests."""

    init_db()
    yield


def create_app() -> FastAPI:
    """Build the FastAPI application with every router mounted."""

    application = FastAPI(title=APP_TITLE, lifespan=lifespan)
    application.include_router(api_router)
    application.include_router(assets.router)
    application.include_router(actions.router)
    application.mount("/static/images", StaticFiles(directory=str(STATIC_DIR / "images")), name="images")
    application.add_exception_handler(AppError, app_error_handler)
    return application


async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Translate an application error into a JSON response."""

    assert isinstance(exc, AppError)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app = create_app()
