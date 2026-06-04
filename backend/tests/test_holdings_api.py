from decimal import Decimal

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.holdings import (
    add_holding,
    edit_holding,
    list_holdings,
    read_holding,
    remove_holding,
    router,
)
from app.core.auth import AuthenticatedUser, get_current_user
from app.data.models import Holding, Instrument
from app.schemas.holdings import HoldingRequest


def holding_payload(**overrides: object) -> HoldingRequest:
    payload: dict[str, object] = {
        "symbol": " voo ",
        "name": " Vanguard S&P 500 ETF ",
        "exchange": " nysearca ",
        "currency": "usd",
        "asset_class": " ETF ",
        "sector": " Broad Market ",
        "country": " United States ",
        "region": " North America ",
        "quantity": "12.5",
        "average_cost": "418.23",
    }
    payload.update(overrides)
    return HoldingRequest.model_validate(payload)


def test_holdings_routes_require_auth() -> None:
    route_paths = {getattr(route, "path", None) for route in router.routes}

    assert route_paths == {"/api/v1/holdings", "/api/v1/holdings/{holding_id}"}
    for route in router.routes:
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_current_user in dependency_calls


def test_creating_holding_inserts_and_reuses_instrument(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    first_response = add_holding(holding_payload(), authenticated_user, db_session)
    second_response = add_holding(
        holding_payload(quantity="3"),
        authenticated_user,
        db_session,
    )

    instrument_count = db_session.scalar(select(func.count()).select_from(Instrument))
    holding_count = db_session.scalar(select(func.count()).select_from(Holding))

    assert instrument_count == 1
    assert holding_count == 2
    assert first_response.instrument.id == second_response.instrument.id
    assert first_response.instrument.symbol == "VOO"
    assert first_response.instrument.exchange == "NYSEARCA"
    assert first_response.instrument.currency == "USD"


def test_listing_holdings_returns_only_authenticated_users_holdings(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    own_holding = add_holding(
        holding_payload(symbol="VOO"),
        authenticated_user,
        db_session,
    )
    add_holding(holding_payload(symbol="VXUS"), second_user, db_session)

    holdings = list_holdings(authenticated_user, db_session)

    assert [holding.id for holding in holdings] == [own_holding.id]


def test_getting_another_users_holding_returns_404(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    other_holding = add_holding(holding_payload(), second_user, db_session)

    with pytest.raises(HTTPException) as exc_info:
        read_holding(other_holding.id, authenticated_user, db_session)

    assert exc_info.value.status_code == 404


def test_updating_another_users_holding_returns_404(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    other_holding = add_holding(holding_payload(), second_user, db_session)

    with pytest.raises(HTTPException) as exc_info:
        edit_holding(
            other_holding.id,
            holding_payload(quantity="5"),
            authenticated_user,
            db_session,
        )

    assert exc_info.value.status_code == 404


def test_deleting_another_users_holding_returns_404(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    other_holding = add_holding(holding_payload(), second_user, db_session)

    with pytest.raises(HTTPException) as exc_info:
        remove_holding(other_holding.id, authenticated_user, db_session)

    assert exc_info.value.status_code == 404


def test_updating_own_holding_changes_quantity_and_instrument(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    holding = add_holding(holding_payload(), authenticated_user, db_session)

    response = edit_holding(
        holding.id,
        holding_payload(symbol="vxus", exchange="", quantity="7.25"),
        authenticated_user,
        db_session,
    )

    assert response.id == holding.id
    assert response.quantity == Decimal("7.25")
    assert response.instrument.symbol == "VXUS"
    assert response.instrument.exchange == ""


def test_deleting_own_holding_returns_204_and_removes_row(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    holding = add_holding(holding_payload(), authenticated_user, db_session)

    response = remove_holding(holding.id, authenticated_user, db_session)

    assert isinstance(response, Response)
    assert response.status_code == 204
    assert db_session.get(Holding, holding.id) is None


def test_invalid_quantity_or_average_cost_is_rejected() -> None:
    with pytest.raises(ValidationError):
        holding_payload(quantity="0")

    with pytest.raises(ValidationError):
        holding_payload(average_cost="-1")


def test_symbol_and_currency_are_normalized_in_responses(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = add_holding(
        holding_payload(symbol="voo", currency="usd"),
        authenticated_user,
        db_session,
    )

    assert response.instrument.symbol == "VOO"
    assert response.instrument.currency == "USD"
    assert response.model_dump(mode="json")["quantity"] == "12.50000000"
