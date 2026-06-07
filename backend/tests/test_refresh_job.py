from app.domain.price_refresh import PriceRefreshResult
from app.jobs import refresh_prices


class FakeSession:
    closed = False

    def close(self) -> None:
        self.closed = True


class FakeMarketDataClient:
    pass


def test_job_command_calls_global_refresh_service(
    monkeypatch,
    capsys,
) -> None:
    session = FakeSession()
    calls: list[tuple[FakeSession, FakeMarketDataClient]] = []

    monkeypatch.setattr(refresh_prices, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        refresh_prices,
        "YFinanceMarketDataClient",
        FakeMarketDataClient,
    )

    def fake_refresh_prices_for_all_users(
        db: FakeSession,
        market_data_client: FakeMarketDataClient,
    ) -> PriceRefreshResult:
        calls.append((db, market_data_client))
        return PriceRefreshResult(requested=3, updated=2, skipped=1, failed=0)

    monkeypatch.setattr(
        refresh_prices,
        "refresh_prices_for_all_users",
        fake_refresh_prices_for_all_users,
    )

    exit_code = refresh_prices.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [(session, calls[0][1])]
    assert isinstance(calls[0][1], FakeMarketDataClient)
    assert session.closed is True
    assert "requested=3" in captured.out
    assert "updated=2" in captured.out
    assert "skipped=1" in captured.out
    assert "failed=0" in captured.out
