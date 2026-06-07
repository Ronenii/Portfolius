from fastapi import HTTPException

from app.api.v1.instruments import router, search_instruments
from app.core.auth import AuthenticatedUser, get_current_user
from app.main import app
from app.schemas.instruments import InstrumentSearchResult


class FakeLookupClient:
    def __init__(self, should_raise: bool = False) -> None:
        self.should_raise = should_raise
        self.queries: list[str] = []

    def search(self, query: str, limit: int = 10) -> list[InstrumentSearchResult]:
        self.queries.append(query)
        if self.should_raise:
            raise RuntimeError("provider down")
        return [
            InstrumentSearchResult(
                symbol="INDA",
                name="iShares MSCI India ETF",
                exchange="BATS",
                currency="USD",
                asset_class="ETF",
                sector="Broad Market",
                country="India",
                region="Asia",
                source="fmp",
            )
        ]


def test_instrument_search_route_is_registered_and_requires_auth() -> None:
    route_paths = {getattr(route, "path", None) for route in app.routes}

    assert "/api/v1/instruments/search" in route_paths
    for route in router.routes:
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_current_user in dependency_calls


def test_instrument_search_returns_lookup_results(
    authenticated_user: AuthenticatedUser,
) -> None:
    lookup_client = FakeLookupClient()

    results = search_instruments("IN", authenticated_user, lookup_client)

    assert lookup_client.queries == ["IN"]
    assert results[0].symbol == "INDA"
    assert results[0].country == "India"


def test_instrument_search_short_query_skips_provider(
    authenticated_user: AuthenticatedUser,
) -> None:
    lookup_client = FakeLookupClient()

    assert search_instruments("I", authenticated_user, lookup_client) == []
    assert lookup_client.queries == []


def test_instrument_search_provider_failure_returns_empty_list(
    authenticated_user: AuthenticatedUser,
) -> None:
    lookup_client = FakeLookupClient(should_raise=True)

    assert search_instruments("IN", authenticated_user, lookup_client) == []


def test_instrument_search_rejects_missing_auth() -> None:
    lookup_client = FakeLookupClient()

    try:
        search_instruments("IN", None, lookup_client)  # type: ignore[arg-type]
    except HTTPException as exc:
        assert exc.status_code == 401
