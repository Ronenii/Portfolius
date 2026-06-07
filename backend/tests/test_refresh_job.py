from app.domain.price_refresh import PriceRefreshResult
from app.jobs import refresh_prices


class FakeSession:
    closed = False

    def close(self) -> None:
        self.closed = True


class FakeMarketDataClient:
    pass


def test_job_command_calls_refresh_service_with_supplied_user_id(
    monkeypatch,
    capsys,
) -> None:
    session = FakeSession()
    calls: list[tuple[FakeSession, str, FakeMarketDataClient]] = []

    monkeypatch.setattr(refresh_prices, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        refresh_prices,
        "YFinanceMarketDataClient",
        FakeMarketDataClient,
    )

    def fake_refresh_prices_for_user(
        db: FakeSession,
        user_id: str,
        market_data_client: FakeMarketDataClient,
    ) -> PriceRefreshResult:
        calls.append((db, user_id, market_data_client))
        return PriceRefreshResult(requested=3, updated=2, skipped=1, failed=0)

    monkeypatch.setattr(
        refresh_prices,
        "refresh_prices_for_user",
        fake_refresh_prices_for_user,
    )

    exit_code = refresh_prices.main(["--user-id", "user-123"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [(session, "user-123", calls[0][2])]
    assert isinstance(calls[0][2], FakeMarketDataClient)
    assert session.closed is True
    assert "requested=3" in captured.out
    assert "updated=2" in captured.out
    assert "skipped=1" in captured.out
    assert "failed=0" in captured.out


def test_missing_user_id_exits_with_useful_error(capsys) -> None:
    exit_code = refresh_prices.main([])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "--user-id is required" in captured.err
