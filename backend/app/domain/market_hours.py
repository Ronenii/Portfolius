from datetime import datetime, time
from zoneinfo import ZoneInfo

US_MARKET_TIMEZONE = ZoneInfo("America/New_York")
REGULAR_SESSION_OPEN = time(9, 30)
REGULAR_SESSION_CLOSE = time(16, 0)


def is_us_market_open(now: datetime) -> bool:
    market_time = now.astimezone(US_MARKET_TIMEZONE)
    if market_time.weekday() >= 5:
        return False

    current_time = market_time.time()
    return REGULAR_SESSION_OPEN <= current_time < REGULAR_SESSION_CLOSE
