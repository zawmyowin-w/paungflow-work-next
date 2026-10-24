# Lower Paung-Luang Dam Inflow Forecasting System

Python/FastAPI admin dashboard based on the supplied control-room reference. It includes a Manus account login page, a protected dashboard, light/dark themes, CSV ingestion and validation, persistent dataset/model-run records, dam reference panels, a map overview, and model-specific results pages with actual-vs-predicted charts, future forecasts, holdout metrics, and scatter plots.

## Run locally

See the Burmese [local setup guide](LOCAL_SETUP_MY.md). On Windows, open `run_local.bat`; on macOS/Linux run `bash run_local.sh`. The launchers create a Python virtual environment, install pinned dependencies, prepare a local-only `.env`, generate a strong local admin password the first time, and start the server at `http://127.0.0.1:3000`. Local data is stored in SQLite at `data/local.db`.

Every dependency is pinned to a release that publishes a wheel for Python 3.12 and newer, so the installation never needs a C compiler. The launchers keep the pip cache and the temporary files inside the project folder (`.pip-cache`, `.tmp`), so a full system drive cannot break the installation.

The local launchers remove inherited hosted database/auth environment values before starting so the local app uses its own `.env` and SQLite fallback. Local username/password authentication is enabled only when `APP_MODE=local`, is limited to localhost, and is not used by the hosted app. Do not expose the local development server to the internet. Hosted Cloud continues to use Manus OAuth and its managed database.

To start manually, install `requirements.txt`, configure the needed environment, then run `uvicorn app.main:app --host 0.0.0.0 --port 3000`. Cloud supplies `DATABASE_URL` and Manus OAuth values; local mode leaves `DATABASE_URL` blank for SQLite. The current project Preview hostname pattern and localhost are included by default. Set `APP_ALLOWED_ORIGINS` to comma-separated origins for a custom published domain.

The first authenticated Manus account is registered as the application administrator. Later accounts are stored as viewers and cannot open the dashboard until an administrator role-management flow is added. The current starter does not include a user-management screen.

## Project structure

The backend follows a layered design so that every rule lives in exactly one place.

| Layer | Package | Responsibility |
| --- | --- | --- |
| Entry point | `app/main.py` | Application factory, middleware, static files, error translation |
| HTTP | `app/api/` | Routers (`pages`, `actions`, `auth`, `data`, `assets`), dependencies, payload serializers |
| Contracts | `app/schemas.py` | Pydantic request and response models |
| Services | `app/services/` | Use cases: identity, datasets, forecasting runs |
| Domain | `app/domain/` | Pure time-series parsing, forecasting engine, record types |
| Persistence | `app/db/` | Engine, ORM models, schema migrations, repositories |
| Cross-cutting | `app/core/`, `app/config.py` | Errors, security, OAuth client, environment settings |
| Front end | `app/web/`, `templates/` | View models, server-side SVG charts, theme handling, stylesheets, scripts, HTML templates |

Design rules that the code follows:

- Dependencies point inwards: `api → services → domain`, and only the services and repositories know about SQLAlchemy.
- The domain layer is pure Python with no I/O, which is what makes it cheap to test.
- Services raise the typed errors from `app/core/errors.py`; the API layer converts them into HTTP responses, so business rules never mention status codes.
- Configuration is read in one place (`app/config.py`) instead of through scattered `os.environ` calls.
- Every public function has a type annotation and a short docstring; modules stay small and single-purpose.

## Front end

The browser receives finished HTML, so the interface is written in Python only.

| Piece | Location | How it reaches the browser |
| --- | --- | --- |
| Pages | `templates/*.html` | Jinja2 templates rendered by `app/web/templates.py` |
| View data | `app/web/views.py` | Turns service records into the template context |
| Charts | `app/web/charts.py` | Builds SVG markup in Python, injected into the page |
| Stylesheets | `app/web/assets/*_css.py` | Served by `app/api/assets.py` at `/static/css/<name>.css` |
| Scripts | `app/web/assets/dashboard_js.py` | Served by `app/api/assets.py` at `/static/js/<name>.js` |
| Theme | `app/web/theme.py` | Cookie plus a `POST /theme/toggle` form |
| Images | `static/images/` | Static file mount at `/static/images` |

Actions are plain HTML forms that post to the server and return with a redirect, so no client-side framework or charting library is needed. The map zoom buttons are radio inputs with CSS `:checked` rules, and the only remaining browser script is the header clock ticker in `app/web/assets/dashboard_js.py`.


## Dataset and forecast behavior

Upload a UTF-8 CSV with an ISO 8601 time column and a numeric inflow/flow/discharge column. Timestamps must be unique and strictly increasing; irregular gaps are allowed, and forecast horizons count rows rather than inferred calendar periods. Files are limited to 5 MB and 20,000 rows, and at least eight finite numeric observations are required. Use the included `sample_inflow_dataset.csv` for a full-year daily upload example; its values are synthetic placeholders, not Lower Paung-Luang Dam telemetry or an operational forecast input. The **Try synthetic sample** action also creates a clearly labeled synthetic dataset for interface demonstration.

Clicking an LSTM, GRU, or RGF-LSTM control opens a dedicated result page for that saved run. The page shows a rolling actual-vs-predicted chart, the selected horizon, RMSE/R²/MAE holdout metrics, and a scatter plot. These controls currently call transparent rolling-baseline preview adapters; no trained neural-network weights or dam telemetry were supplied. Replace the adapters in `app/domain/forecasting.py` with validated model weights and confirm engineering units/metrics before using forecasts for operational decisions.Dataset, user-role, and forecast-run records are stored in the project-managed MySQL database when available; local mode uses SQLite. Development and published environments share the managed database. Dataset and run queries are restricted to the authenticated owner and validated browser origin, separating Preview and published-domain data scopes. State-changing requests reject missing or cross-site browser origins.

## Code quality

Install the development tooling with `pip install -r requirements-dev.txt` and run the checks from the project root:

```bash
python -m pytest          # unit and end-to-end tests (tests/)
python -m ruff check .    # lint rules
python -m ruff format .   # consistent formatting
python -m mypy            # static type checking
```

The test suite covers the CSV validation rules, the forecasting engine, the origin and session helpers, the JSON API (sign-in, upload, forecast run, result page), and the server-rendered pages, stylesheets, scripts and form actions.
