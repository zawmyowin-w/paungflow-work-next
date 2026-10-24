"""Tests of the server-rendered front end: pages, assets and form actions."""

from __future__ import annotations

from fastapi.testclient import TestClient

from constants import TEST_ORIGIN

DAILY_CSV: bytes = b"date,inflow_m3_s\n" + b"".join(
    f"2024-01-{day:02d},{day}\n".encode() for day in range(1, 13)
)


def _form_headers() -> dict[str, str]:
    """Return the headers a browser sends with a form submission."""

    return {"origin": TEST_ORIGIN}


def test_login_page_has_no_inline_script(app_client: TestClient) -> None:
    response = app_client.get("/")

    assert response.status_code == 200
    assert "<script" not in response.text
    assert 'action="/auth/local-login"' in response.text
    assert "onerror=" not in response.text


def test_stylesheet_is_served_from_python(app_client: TestClient) -> None:
    response = app_client.get("/static/css/dashboard.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert ".topbar" in response.text


def test_results_stylesheet_is_served_from_python(app_client: TestClient) -> None:
    response = app_client.get("/static/css/results.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert ".results-topbar" in response.text


def test_script_is_served_from_python(app_client: TestClient) -> None:
    response = app_client.get("/static/js/dashboard.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "clock-date" in response.text


def test_unknown_asset_is_not_found(app_client: TestClient) -> None:
    response = app_client.get("/static/css/missing.css")

    assert response.status_code == 404


def test_dashboard_renders_the_chart_on_the_server(
    signed_in_client: TestClient, api_headers: dict[str, str]
) -> None:
    signed_in_client.post("/api/datasets/sample", headers=api_headers)

    response = signed_in_client.get("/dashboard")

    assert response.status_code == 200
    assert "<svg" in response.text
    assert "polyline" in response.text
    assert "onerror=" not in response.text
    assert '<script src="/static/js/dashboard.js" defer></script>' in response.text


def test_form_actions_require_a_session(app_client: TestClient) -> None:
    response = app_client.post("/datasets/sample", headers=_form_headers(), follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_sample_form_creates_a_dataset(signed_in_client: TestClient) -> None:
    response = signed_in_client.post("/datasets/sample", headers=_form_headers(), follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard?status=sample"

    dashboard = signed_in_client.get("/dashboard?status=sample")
    assert "Synthetic demonstration data loaded" in dashboard.text


def test_upload_form_accepts_a_csv(signed_in_client: TestClient) -> None:
    response = signed_in_client.post(
        "/datasets/upload",
        files={"file": ("inflow.csv", DAILY_CSV, "text/csv")},
        headers=_form_headers(),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard?status=uploaded"


def test_upload_form_rejects_other_file_types(signed_in_client: TestClient) -> None:
    response = signed_in_client.post(
        "/datasets/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=_form_headers(),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard?status=upload-failed"


def test_forecast_form_opens_the_result_page(
    signed_in_client: TestClient, api_headers: dict[str, str]
) -> None:
    sample = signed_in_client.post("/api/datasets/sample", headers=api_headers)
    dataset_id = sample.json()["dataset"]["id"]

    response = signed_in_client.post(
        "/forecast/lstm",
        data={"dataset_id": dataset_id, "horizon": "14"},
        headers=_form_headers(),
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/results/lstm?run_id=")

    result = signed_in_client.get(location)
    assert result.status_code == 200
    assert "Actual vs Predicted Inflow" in result.text
    assert "<svg" in result.text


def test_forecast_form_without_a_dataset_reports_the_status(signed_in_client: TestClient) -> None:
    response = signed_in_client.post(
        "/forecast/lstm", data={"horizon": "7"}, headers=_form_headers(), follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard?status=no-dataset"


def test_theme_toggle_switches_the_theme(signed_in_client: TestClient) -> None:
    response = signed_in_client.post(
        "/theme/toggle",
        data={"next": "/dashboard"},
        headers=_form_headers(),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.cookies["paung-dam-theme"] == "dark"

    dashboard = signed_in_client.get("/dashboard")
    assert 'data-theme="dark"' in dashboard.text
