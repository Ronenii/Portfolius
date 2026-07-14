from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.holdings import list_holdings, read_holding, router
from app.core.auth import AuthenticatedUser, get_current_user
from app.data.models import Holding, Instrument
from app.main import app


def make_holding(
    db_session: Session,
    user_id: str,
    **overrides: object,
) -> Holding:
    instrument_fields: dict[str, object] = {
        "symbol": "VOO",
        "name": "Vanguard S&P 500 ETF",
        "exchange": "NYSEARCA",
        "currency": "USD",
        "asset_class": "ETF",
        "sector": "Broad Market",
        "country": "United States",
        "region": "North America",
    }
    for field in list(instrument_fields):
        if field in overrides:
            instrument_fields[field] = overrides.pop(field)
    instrument = Instrument(**instrument_fields)
    db_session.add(instrument)
    db_session.flush()

    holding_fields: dict[str, object] = {
        "user_id": user_id,
        "instrument_id": instrument.id,
        "quantity": Decimal("12.5"),
        "average_cost": Decimal("145.20"),
    }
    holding_fields.update(overrides)
    holding = Holding(**holding_fields)
    db_session.add(holding)
    db_session.commit()
    db_session.refresh(holding)
    return holding


def test_holdings_routes_require_auth() -> None:
    route_paths = {getattr(route, "path", None) for route in app.routes}

    assert {"/api/v1/holdings", "/api/v1/holdings/{holding_id}"}.issubset(
        route_paths
    )
    for route in router.routes:
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_current_user in dependency_calls


def test_listing_holdings_returns_only_authenticated_users_holdings(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    own_holding = make_holding(db_session, authenticated_user.user_id, symbol="VOO")
    make_holding(db_session, second_user.user_id, symbol="VXUS")

    holdings = list_holdings(authenticated_user, db_session)

    assert [holding.id for holding in holdings] == [own_holding.id]


def test_getting_own_holding_returns_it(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    holding = make_holding(db_session, authenticated_user.user_id)

    response = read_holding(holding.id, authenticated_user, db_session)

    assert response.id == holding.id
    assert response.instrument.symbol == "VOO"
    assert response.quantity == Decimal("12.5")


def test_getting_another_users_holding_returns_404(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    other_holding = make_holding(db_session, second_user.user_id)

    with pytest.raises(HTTPException) as exc_info:
        read_holding(other_holding.id, authenticated_user, db_session)

    assert exc_info.value.status_code == 404
