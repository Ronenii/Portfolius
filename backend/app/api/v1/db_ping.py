from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.data.models import AppHealthCheck

router = APIRouter()


@router.get("/api/v1/db-ping", tags=["health"])
def db_ping(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    db.execute(select(AppHealthCheck.id).limit(1))
    return {"status": "ok"}
