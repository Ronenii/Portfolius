from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.db_ping import router as db_ping_router
from app.api.v1.health import router as health_router
from app.api.v1.holdings import router as holdings_router
from app.api.v1.instruments import router as instruments_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.profile import router as profile_router
from app.core.config import get_settings


def create_app() -> FastAPI:
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
    return app


app = create_app()
