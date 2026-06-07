import argparse
import sys
from collections.abc import Sequence

from app.data.database import SessionLocal
from app.domain.price_refresh import refresh_prices_for_user
from app.integrations.yfinance_client import YFinanceMarketDataClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh latest market prices for one Portfolius user.",
    )
    parser.add_argument(
        "--user-id",
        help="Supabase Auth user ID whose held instruments should be refreshed.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.user_id:
        print("--user-id is required", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        result = refresh_prices_for_user(
            db,
            args.user_id,
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
