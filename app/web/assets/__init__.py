"""Front-end assets that are authored in Python and served by the application.

The stylesheets and the single remaining script live in Python modules, so the
whole interface is written in one language and no static asset pipeline is
needed.
"""

from app.web.assets.dashboard_css import DASHBOARD_CSS
from app.web.assets.dashboard_js import DASHBOARD_JS
from app.web.assets.results_css import RESULTS_CSS

STYLESHEETS: dict[str, str] = {
    "dashboard": DASHBOARD_CSS,
    "results": RESULTS_CSS,
}

SCRIPTS: dict[str, str] = {
    "dashboard": DASHBOARD_JS,
}

__all__ = ["SCRIPTS", "STYLESHEETS"]
