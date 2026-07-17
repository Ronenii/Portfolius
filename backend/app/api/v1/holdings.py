from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.data.database import get_db
from app.data.repositories.holdings import get_holding_for_user, list_holdings_for_user
from app.schemas.holdings import HoldingResponse

router = APIRouter(tags=["holdings"])


def not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Holding not found",
    )


@router.get("/api/v1/holdings", response_model=list[HoldingResponse])
def list_holdings(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[HoldingResponse]:
    holdings = list_holdings_for_user(db, current_user.user_id)
    return [HoldingResponse.model_validate(holding) for holding in holdings]


@router.get("/api/v1/holdings/{holding_id}", response_model=HoldingResponse)
def read_holding(
    holding_id: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> HoldingResponse:
    holding = get_holding_for_user(db, current_user.user_id, holding_id)
    if holding is None:
        raise not_found()
    return HoldingResponse.model_validate(holding)
