"""Jinja2 template environment of the dashboard."""

from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app.config import TEMPLATES_DIR

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
