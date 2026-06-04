from starlette.middleware.cors import CORSMiddleware

from app.main import app


def cors_options() -> dict[str, object]:
    cors_middleware = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls is CORSMiddleware
    )
    return cors_middleware.kwargs


def test_local_frontend_origin_is_allowed_for_healthz() -> None:
    options = cors_options()

    assert "http://localhost:5173" in options["allow_origins"]
    assert "GET" in options["allow_methods"]


def test_local_loopback_frontend_origin_is_allowed_for_healthz() -> None:
    options = cors_options()

    assert "http://127.0.0.1:5173" in options["allow_origins"]
    assert "GET" in options["allow_methods"]


def test_unknown_origin_is_not_allowed_for_healthz() -> None:
    options = cors_options()

    assert "http://example.test" not in options["allow_origins"]
