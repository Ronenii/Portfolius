from app.api.v1.health import healthz
from app.main import app


def test_healthz_route_is_registered() -> None:
    health_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/healthz"
        and "GET" in getattr(route, "methods", set())
    ]

    assert len(health_routes) == 1


def test_healthz_returns_ok_payload() -> None:
    assert healthz() == {"status": "ok"}
