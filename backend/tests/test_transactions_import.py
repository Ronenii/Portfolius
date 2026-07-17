from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
from test_transactions_api import (
    FakeInstrumentLookupClient,
    FakeMarketDataClient,
    make_instrument,
    profile_result,
)

from app.api.v1.transactions import import_transactions
from app.core.auth import AuthenticatedUser
from app.data.repositories.transactions import (
    get_holding_by_instrument,
    list_transactions_for_user,
)
from app.schemas.transactions import TransactionImportRequest, TransactionImportRow


def row(**overrides: object) -> dict:
    payload: dict[str, object] = {
        "symbol": "voo",
        "action": "buy",
        "quantity": "10",
        "price": "100",
        "fees": "1",
        "trade_date": date(2026, 1, 1),
        "notes": "opening",
    }
    payload.update(overrides)
    return payload


def import_rows(
    rows: list[dict],
    authenticated_user: AuthenticatedUser,
    db_session: Session,
    lookup_client: FakeInstrumentLookupClient | None = None,
    market_data_client: FakeMarketDataClient | None = None,
):
    request = TransactionImportRequest(
        rows=[TransactionImportRow.model_validate(r) for r in rows]
    )
    return import_transactions(
        request,
        authenticated_user,
        db_session,
        lookup_client or FakeInstrumentLookupClient(),
        market_data_client or FakeMarketDataClient(),
    )


def test_multiple_valid_rows_all_import_and_fold_holding(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    instrument = make_instrument(db_session)

    response = import_rows(
        [
            row(quantity="10", price="100", fees="0", trade_date=date(2026, 1, 1)),
            row(quantity="10", price="120", fees="0", trade_date=date(2026, 1, 2)),
        ],
        authenticated_user,
        db_session,
    )

    assert [r.status for r in response.results] == ["imported", "imported"]
    assert [r.reason for r in response.results] == [None, None]

    transactions = list_transactions_for_user(db_session, authenticated_user.user_id)
    assert len(transactions) == 2
    assert all(t.user_id == authenticated_user.user_id for t in transactions)

    holding = get_holding_by_instrument(
        db_session, authenticated_user.user_id, instrument.id
    )
    assert holding is not None
    assert holding.quantity == Decimal("20")
    # Weighted average cost across the two buys: (10*100 + 10*120) / 20 = 110.
    assert holding.average_cost == Decimal("110")


def test_unresolvable_symbol_fails_but_other_rows_still_import(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    make_instrument(db_session, symbol="VOO")
    lookup_client = FakeInstrumentLookupClient(profile_result=None)

    response = import_rows(
        [
            row(symbol="voo"),
            row(symbol="zzz", trade_date=date(2026, 1, 2)),
        ],
        authenticated_user,
        db_session,
        lookup_client,
    )

    assert response.results[0].status == "imported"
    assert response.results[1].status == "failed"
    assert response.results[1].reason is not None

    transactions = list_transactions_for_user(db_session, authenticated_user.user_id)
    assert len(transactions) == 1


def test_oversell_row_fails_and_earlier_valid_row_remains_persisted(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    make_instrument(db_session)

    response = import_rows(
        [
            row(action="buy", quantity="10", trade_date=date(2026, 1, 1)),
            row(action="sell", quantity="20", trade_date=date(2026, 1, 2)),
        ],
        authenticated_user,
        db_session,
    )

    assert response.results[0].status == "imported"
    assert response.results[1].status == "failed"
    assert response.results[1].reason is not None

    transactions = list_transactions_for_user(db_session, authenticated_user.user_id)
    assert len(transactions) == 1
    assert transactions[0].action == "buy"


def test_business_invalid_row_fails_but_others_import(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    make_instrument(db_session)

    response = import_rows(
        [
            row(action="hold", trade_date=date(2026, 1, 1)),
            row(quantity="0", trade_date=date(2026, 1, 2)),
            row(action="buy", quantity="10", trade_date=date(2026, 1, 3)),
        ],
        authenticated_user,
        db_session,
    )

    assert response.results[0].status == "failed"
    assert response.results[0].reason is not None
    assert response.results[1].status == "failed"
    assert response.results[1].reason is not None
    assert response.results[2].status == "imported"

    transactions = list_transactions_for_user(db_session, authenticated_user.user_id)
    assert len(transactions) == 1


def test_resolving_new_symbol_via_lookup_client_creates_instrument_and_imports(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    lookup_client = FakeInstrumentLookupClient(profile_result())

    response = import_rows(
        [row(symbol="voo")],
        authenticated_user,
        db_session,
        lookup_client,
    )

    assert lookup_client.profile_symbols == ["VOO"]
    assert response.results[0].status == "imported"

    transactions = list_transactions_for_user(db_session, authenticated_user.user_id)
    assert len(transactions) == 1
    assert transactions[0].instrument.symbol == "VOO"


def test_row_indices_are_1_based_and_match_input_order_with_interleaved_failures(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    make_instrument(db_session)

    response = import_rows(
        [
            row(action="buy", quantity="10", trade_date=date(2026, 1, 1)),
            row(action="hold", trade_date=date(2026, 1, 2)),
            row(action="buy", quantity="5", trade_date=date(2026, 1, 3)),
            row(quantity="0", trade_date=date(2026, 1, 4)),
        ],
        authenticated_user,
        db_session,
    )

    assert [r.row for r in response.results] == [1, 2, 3, 4]
    assert [r.status for r in response.results] == [
        "imported",
        "failed",
        "imported",
        "failed",
    ]


def test_empty_rows_returns_200_with_empty_results(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = import_rows([], authenticated_user, db_session)

    assert response.results == []
