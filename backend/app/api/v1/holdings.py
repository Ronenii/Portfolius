from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.data.database import get_db
from app.data.repositories.holdings import (
    create_holding,
    delete_holding,
    get_holding_for_user,
    list_holdings_for_user,
    update_holding,
)
from app.schemas.holdings import HoldingRequest, HoldingResponse

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


@router.post(
    "/api/v1/holdings",
    response_model=HoldingResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_holding(
    payload: HoldingRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> HoldingResponse:
    holding = create_holding(db, current_user.user_id, payload)
    return HoldingResponse.model_validate(holding)


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


@router.put("/api/v1/holdings/{holding_id}", response_model=HoldingResponse)
def edit_holding(
    holding_id: int,
    payload: HoldingRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> HoldingResponse:
    holding = get_holding_for_user(db, current_user.user_id, holding_id)
    if holding is None:
        raise not_found()
    updated_holding = update_holding(db, holding, payload)
    return HoldingResponse.model_validate(updated_holding)


@router.delete(
    "/api/v1/holdings/{holding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_holding(
    holding_id: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    holding = get_holding_for_user(db, current_user.user_id, holding_id)
    if holding is None:
        raise not_found()
    delete_holding(db, holding)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
