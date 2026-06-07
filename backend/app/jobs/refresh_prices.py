import argparse
from collections.abc import Sequence

from app.data.database import SessionLocal
from app.domain.price_refresh import refresh_prices_for_all_users
from app.integrations.yfinance_client import YFinanceMarketDataClient


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Refresh latest market prices for all held Portfolius instruments.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)

    db = SessionLocal()
    try:
        result = refresh_prices_for_all_users(
            db,
            YFinanceMarketDataClient(),
        )
    finally:
        db.close()

    print(
        "Price refresh complete: "
        f"requested={result.requested} "
        f"updated={result.updated} "
        f"skipped={result.skipped} "
        f"failed={result.failed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
