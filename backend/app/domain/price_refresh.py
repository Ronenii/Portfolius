from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.data.repositories.holdings import list_instruments_for_user_holdings
from app.data.repositories.prices import upsert_price
from app.integrations.market_data import MarketDataClient


@dataclass(frozen=True)
class PriceRefreshResult:
    requested: int
    updated: int
    skipped: int
    failed: int


def refresh_prices_for_user(
    db: Session,
    user_id: str,
    market_data_client: MarketDataClient,
) -> PriceRefreshResult:
    instruments = list_instruments_for_user_holdings(db, user_id)
    requested = 0
    updated = 0
    skipped = 0
    failed = 0

    for instrument in instruments:
        requested += 1
        try:
            market_price = market_data_client.get_latest_close(
                instrument.symbol,
                instrument.exchange,
                instrument.currency,
            )
        except Exception:
            failed += 1
            continue

        if market_price is None:
            skipped += 1
            continue

        upsert_price(db, instrument, market_price)
        updated += 1

    db.commit()
    return PriceRefreshResult(
        requested=requested,
        updated=updated,
        skipped=skipped,
        failed=failed,
    )
