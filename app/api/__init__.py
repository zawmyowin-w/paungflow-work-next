"""HTTP layer of the dashboard.

The routers are grouped by concern: HTML pages, form actions, authentication,
the JSON API and the assets that are written in Python.
"""

from fastapi import APIRouter

from app.api import auth, data, pages

api_router = APIRouter()
api_router.include_router(pages.router)
api_router.include_router(auth.router)
api_router.include_router(data.router)

__all__ = ["api_router"]
