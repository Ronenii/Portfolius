from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import ValidationError
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
from app.schemas.transactions import (
    TransactionImportRequest,
    TransactionImportResponse,
    TransactionImportResult,
    TransactionRequest,
    TransactionResponse,
)

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


@router.post(
    "/api/v1/transactions/import",
    response_model=TransactionImportResponse,
)
def import_transactions(
    payload: TransactionImportRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    lookup_client: Annotated[
        InstrumentLookupClient,
        Depends(get_instrument_lookup_client),
    ],
    market_data_client: Annotated[MarketDataClient, Depends(get_market_data_client)],
) -> TransactionImportResponse:
    # Per-row commit: each row is validated, resolved, and created
    # independently (reusing the same resolve/create path as `add_transaction`),
    # so a single bad row is reported and skipped instead of discarding the
    # valid rows already imported in this batch. `create_transaction` commits
    # (and recomputes the holding) for each row on success, and rolls back
    # only that row on `InsufficientQuantityError`. The tradeoff is a holding
    # recompute per row rather than once per instrument at the end, but import
    # batches are small (tens to low-hundreds of rows) so this is negligible.
    results: list[TransactionImportResult] = []

    for index, row in enumerate(payload.rows, start=1):
        try:
            transaction_request = TransactionRequest(
                symbol=row.symbol,
                action=row.action,
                quantity=row.quantity,
                price=row.price,
                fees=row.fees,
                trade_date=row.trade_date,
                notes=row.notes,
            )
        except ValidationError as exc:
            reason = exc.errors()[0]["msg"]
            results.append(
                TransactionImportResult(row=index, status="failed", reason=reason)
            )
            continue

        try:
            instrument = resolve_transaction_instrument(
                transaction_request, db, lookup_client
            )
        except HTTPException as exc:
            results.append(
                TransactionImportResult(
                    row=index, status="failed", reason=str(exc.detail)
                )
            )
            continue

        ensure_instrument_has_price(db, instrument, market_data_client)
        currency = instrument.currency or "USD"

        try:
            create_transaction(
                db,
                current_user.user_id,
                instrument_id=instrument.id,
                action=transaction_request.action,
                quantity=transaction_request.quantity,
                price=transaction_request.price,
                fees=transaction_request.fees,
                currency=currency,
                trade_date=transaction_request.trade_date,
                notes=transaction_request.notes,
            )
        except InsufficientQuantityError as exc:
            results.append(
                TransactionImportResult(row=index, status="failed", reason=str(exc))
            )
            continue

        results.append(TransactionImportResult(row=index, status="imported"))

    return TransactionImportResponse(results=results)


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
