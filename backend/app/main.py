from fastapi import FastAPI

from app.api.v1.db_ping import router as db_ping_router
from app.api.v1.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Portfolius API")
    app.include_router(health_router)
    app.include_router(db_ping_router)
    return app


app = create_app()
