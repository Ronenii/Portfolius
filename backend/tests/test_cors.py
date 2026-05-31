from fastapi.testclient import TestClient

from app.main import app


def test_local_frontend_origin_is_allowed_for_healthz() -> None:
    response = TestClient(app).options(
        "/healthz",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_local_loopback_frontend_origin_is_allowed_for_healthz() -> None:
    response = TestClient(app).options(
        "/healthz",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_unknown_origin_is_not_allowed_for_healthz() -> None:
    response = TestClient(app).options(
        "/healthz",
        headers={
            "Origin": "http://example.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers
