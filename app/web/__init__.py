"""Front-end layer of the dashboard.

The templates, the stylesheets, the scripts and the charts are all authored in
Python; the application renders finished HTML for the browser.
"""

from app.web.templates import templates

__all__ = ["templates"]
