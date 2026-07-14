from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.v1.instruments import (
    InstrumentLookupClient,
    get_instrument_lookup_client,
)
from app.api.v1.portfolio import get_market_data_client
from app.core.auth import AuthenticatedUser, get_current_user
from app.data.database import get_db
from app.data.models import Instrument
from app.data.repositories.holdings import get_or_create_instrument
from app.data.repositories.transactions import (
    create_transaction,
    delete_transaction,
    get_transaction_for_user,
    list_transactions_for_user,
    update_transaction,
)
from app.domain.portfolio_service import resolve_or_create_instrument
from app.domain.price_refresh import ensure_instrument_has_price
from app.domain.transactions import InsufficientQuantityError
from app.integrations.market_data import MarketDataClient
from app.schemas.transactions import TransactionRequest, TransactionResponse

router = APIRouter(tags=["transactions"])

RICH_METADATA_FIELDS = {
    "name",
    "exchange",
    "currency",
    "asset_class",
    "sector",
    "country",
    "region",
}


def not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Transaction not found",
    )


def instrument_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Instrument not found",
    )


def insufficient_quantity(exc: InsufficientQuantityError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
    )


def resolve_transaction_instrument(
    payload: TransactionRequest,
    db: Session,
    lookup_client: InstrumentLookupClient,
) -> Instrument:
    if payload.instrument_id is not None:
        instrument = db.get(Instrument, payload.instrument_id)
        if instrument is None:
            raise instrument_not_found()
        return instrument

    if RICH_METADATA_FIELDS & payload.model_fields_set:
        return get_or_create_instrument(db, payload)

    assert payload.symbol is not None
    instrument = resolve_or_create_instrument(db, payload.symbol, lookup_client)
    if instrument is None:
        raise instrument_not_found()
    return instrument


@router.get("/api/v1/transactions", response_model=list[TransactionResponse])
def list_transactions(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    instrument_id: int | None = None,
    symbol: str | None = None,
) -> list[TransactionResponse]:
    if instrument_id is not None and symbol is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at most one of instrument_id or symbol",
        )

    normalized_symbol = symbol.strip().upper() if symbol is not None else None
    transactions = list_transactions_for_user(
        db,
        current_user.user_id,
        instrument_id=instrument_id,
        symbol=normalized_symbol,
    )
    return [
        TransactionResponse.model_validate(transaction)
        for transaction in transactions
    ]


@router.post(
    "/api/v1/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_transaction(
    payload: TransactionRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    lookup_client: Annotated[
        InstrumentLookupClient,
        Depends(get_instrument_lookup_client),
    ],
    market_data_client: Annotated[MarketDataClient, Depends(get_market_data_client)],
) -> TransactionResponse:
    instrument = resolve_transaction_instrument(payload, db, lookup_client)
    ensure_instrument_has_price(db, instrument, market_data_client)
    currency = instrument.currency or "USD"

    try:
        transaction = create_transaction(
            db,
            current_user.user_id,
            instrument_id=instrument.id,
            action=payload.action,
            quantity=payload.quantity,
            price=payload.price,
            fees=payload.fees,
            currency=currency,
            trade_date=payload.trade_date,
            notes=payload.notes,
        )
    except InsufficientQuantityError as exc:
        raise insufficient_quantity(exc) from exc

    return TransactionResponse.model_validate(transaction)


@router.get(
    "/api/v1/transactions/{transaction_id}",
    response_model=TransactionResponse,
)
def read_transaction(
    transaction_id: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TransactionResponse:
    transaction = get_transaction_for_user(db, current_user.user_id, transaction_id)
    if transaction is None:
        raise not_found()
    return TransactionResponse.model_validate(transaction)


@router.put(
    "/api/v1/transactions/{transaction_id}",
    response_model=TransactionResponse,
)
def edit_transaction(
    transaction_id: int,
    payload: TransactionRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    lookup_client: Annotated[
        InstrumentLookupClient,
        Depends(get_instrument_lookup_client),
    ],
) -> TransactionResponse:
    transaction = get_transaction_for_user(db, current_user.user_id, transaction_id)
    if transaction is None:
        raise not_found()

    instrument = resolve_transaction_instrument(payload, db, lookup_client)
    currency = instrument.currency or "USD"

    try:
        updated_transaction = update_transaction(
            db,
            transaction,
            instrument_id=instrument.id,
            action=payload.action,
            quantity=payload.quantity,
            price=payload.price,
            fees=payload.fees,
            currency=currency,
            trade_date=payload.trade_date,
            notes=payload.notes,
        )
    except InsufficientQuantityError as exc:
        raise insufficient_quantity(exc) from exc

    return TransactionResponse.model_validate(updated_transaction)


@router.delete(
    "/api/v1/transactions/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_transaction(
    transaction_id: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    transaction = get_transaction_for_user(db, current_user.user_id, transaction_id)
    if transaction is None:
        raise not_found()

    try:
        delete_transaction(db, transaction)
    except InsufficientQuantityError as exc:
        raise insufficient_quantity(exc) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
