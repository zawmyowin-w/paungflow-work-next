"""End-to-end tests of the dashboard HTTP API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from constants import TEST_ORIGIN, TEST_PASSWORD, TEST_USERNAME

DAILY_CSV: bytes = b"date,inflow_m3_s\n" + b"".join(
    f"2024-01-{day:02d},{day}\n".encode() for day in range(1, 13)
)
BROKEN_CSV: bytes = b"date,inflow\n2024-01-01,1\n2024-01-01,2\n2024-01-02,3"


def test_login_page_is_public(app_client: TestClient) -> None:
    response = app_client.get("/")

    assert response.status_code == 200
    assert "Lower Paung-Luang" in response.text


def test_dashboard_requires_a_session(app_client: TestClient) -> None:
    response = app_client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_api_requires_authentication(app_client: TestClient, api_headers: dict[str, str]) -> None:
    response = app_client.get("/api/dashboard/state", headers=api_headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Sign in is required."


def test_local_login_creates_a_session(app_client: TestClient) -> None:
    response = app_client.post(
        "/auth/local-login",
        data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        headers={"origin": TEST_ORIGIN},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
    assert "webdev_app_session" in response.cookies


def test_local_login_rejects_a_wrong_password(app_client: TestClient) -> None:
    response = app_client.post(
        "/auth/local-login",
        data={"username": TEST_USERNAME, "password": "wrong"},
        headers={"origin": TEST_ORIGIN},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/?auth=local-failed"


def test_cross_origin_requests_are_blocked(signed_in_client: TestClient, api_headers: dict[str, str]) -> None:
    response = signed_in_client.post(
        "/api/datasets/sample", headers={**api_headers, "origin": "http://127.0.0.1:3000"}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Cross-origin request blocked."


def test_sample_dataset_and_forecast_round_trip(
    signed_in_client: TestClient, api_headers: dict[str, str]
) -> None:
    sample = signed_in_client.post("/api/datasets/sample", headers=api_headers)

    assert sample.status_code == 200
    dataset = sample.json()["dataset"]
    assert dataset["is_demo"] is True
    assert dataset["rows"] == 120

    state = signed_in_client.get("/api/dashboard/state", headers=api_headers).json()
    assert state["user"]["role"] == "admin"
    assert state["dataset"]["id"] == dataset["id"]
    assert state["runs"] == []

    run = signed_in_client.post(
        "/api/forecast/lstm", json={"dataset_id": dataset["id"], "horizon": 7}, headers=api_headers
    )

    assert run.status_code == 200
    saved_run = run.json()["run"]
    assert saved_run["model_name"] == "LSTM"
    assert len(saved_run["forecast"]) == 7

    state = signed_in_client.get("/api/dashboard/state", headers=api_headers).json()
    assert [item["id"] for item in state["runs"]] == [saved_run["id"]]

    detail = signed_in_client.get(f"/api/forecast-runs/{saved_run['id']}", headers=api_headers)

    assert detail.status_code == 200
    body = detail.json()
    assert body["metrics"]["holdout"] > 0
    assert len(body["validation"]) == body["metrics"]["holdout"]
    assert body["history"]
    assert body["forecast"][0]["label"] == "2025-05-01"


def test_upload_accepts_a_csv(signed_in_client: TestClient, api_headers: dict[str, str]) -> None:
    response = signed_in_client.post(
        "/api/datasets/upload",
        files={"file": ("inflow.csv", DAILY_CSV, "text/csv")},
        headers=api_headers,
    )

    assert response.status_code == 200
    assert response.json()["dataset"]["rows"] == 12


def test_upload_rejects_other_file_types(signed_in_client: TestClient, api_headers: dict[str, str]) -> None:
    response = signed_in_client.post(
        "/api/datasets/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=api_headers,
    )

    assert response.status_code == 415


def test_upload_rejects_a_broken_csv(signed_in_client: TestClient, api_headers: dict[str, str]) -> None:
    response = signed_in_client.post(
        "/api/datasets/upload",
        files={"file": ("broken.csv", BROKEN_CSV, "text/csv")},
        headers=api_headers,
    )

    assert response.status_code == 400
    assert "repeats a timestamp" in response.json()["detail"]


def test_forecast_rejects_an_unknown_model(signed_in_client: TestClient, api_headers: dict[str, str]) -> None:
    response = signed_in_client.post(
        "/api/forecast/transformer", json={"dataset_id": "missing", "horizon": 7}, headers=api_headers
    )

    assert response.status_code == 404


def test_forecast_run_of_another_account_is_not_found(
    signed_in_client: TestClient, api_headers: dict[str, str]
) -> None:
    response = signed_in_client.get("/api/forecast-runs/9999", headers=api_headers)

    assert response.status_code == 404
