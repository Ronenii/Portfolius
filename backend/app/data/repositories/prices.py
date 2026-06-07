from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models import Instrument, Price
from app.integrations.market_data import MarketPrice


def get_latest_prices_for_instruments(
    db: Session,
    instrument_ids: list[int],
) -> dict[int, Price]:
    latest_prices: dict[int, Price] = {}
    if not instrument_ids:
        return latest_prices

    prices = db.scalars(
        select(Price)
        .where(Price.instrument_id.in_(instrument_ids))
        .order_by(Price.instrument_id, Price.price_date.desc(), Price.id.desc())
    )
    for price in prices:
        latest_prices.setdefault(price.instrument_id, price)
    return latest_prices


def upsert_price(
    db: Session,
    instrument: Instrument,
    market_price: MarketPrice,
) -> Price:
    price = db.scalar(
        select(Price).where(
            Price.instrument_id == instrument.id,
            Price.price_date == market_price.price_date,
            Price.source == market_price.source,
        )
    )
    if price is None:
        price = Price(
            instrument=instrument,
            price_date=market_price.price_date,
            close_price=market_price.close_price,
            currency=market_price.currency,
            source=market_price.source,
        )
        db.add(price)
    else:
        price.close_price = market_price.close_price
        price.currency = market_price.currency

    return price
