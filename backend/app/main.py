import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.assistant import router as assistant_router
from app.api.v1.db_ping import router as db_ping_router
from app.api.v1.health import router as health_router
from app.api.v1.holdings import router as holdings_router
from app.api.v1.instruments import router as instruments_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.profile import router as profile_router
from app.core.config import get_settings


def configure_logging() -> None:
    """Make ``app.*`` INFO logs visible under uvicorn.

    uvicorn does not attach a handler to the root logger, so without this the
    last-resort handler drops anything below WARNING and diagnostic INFO lines
    (e.g. the per-symbol ETF metadata refresh trace) never reach the Render logs.
    Attaching a handler directly to the ``app`` logger guarantees emission
    regardless of how the host configures logging.
    """
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(levelname)s:     %(name)s - %(message)s")
        )
        app_logger.addHandler(handler)


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="Portfolius API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(db_ping_router)
    app.include_router(profile_router)
    app.include_router(instruments_router)
    app.include_router(holdings_router)
    app.include_router(portfolio_router)
    app.include_router(jobs_router)
    app.include_router(assistant_router)
    return app


app = create_app()
