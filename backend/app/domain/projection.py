"""Pure goal-projection math.

This module is deliberately I/O-free: no SQLAlchemy, no DB session, no
profile-reading. By the time ``build_projection`` is called, the caller has
already resolved ``annual_return`` (from the profile's explicit value or a
risk-tolerance default) and ``years`` (from a time-horizon label). This
module only does the arithmetic and shapes the response schema.

Two interpretive decisions worth documenting explicitly, since the plan does
not spell out either of them:

1. Periodic-rate convention: we convert the annual return to a fraction and
   divide it evenly across the periods in a year (``(annual_return / 100) /
   periods_per_year``). This is the simpler "nominal annual rate compounded
   periodically" convention, not the compound-equivalent convention
   (``(1 + r) ** (1 / n) - 1``). The nominal convention slightly
   understates true effective annual growth for periods_per_year > 1, but it
   keeps the periodic rate a simple, explainable fraction of the stated
   annual return.
2. Band spread: conservative/optimistic bands are the expected annual return
   shifted by a flat +/- percentage-point constant (``BAND_SPREAD_PERCENT``),
   not a multiplicative spread. A resulting negative conservative rate is
   allowed and is not floored at zero -- it represents a legitimate
   pessimistic scenario.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.schemas.portfolio import ProjectionResponse, ProjectionYearPoint

PERIODS_PER_YEAR = {"weekly": 52, "monthly": 12, "quarterly": 4, "annually": 1}

# Fallback when `frequency` doesn't match a known key. `investment_frequency`
# is a free-form string field elsewhere in the app (not DB-constrained to the
# four keys above), so an unrecognized value falls back to monthly instead of
# raising.
DEFAULT_PERIODS_PER_YEAR = 12

# +/- percentage points applied to `annual_return` to derive the
# conservative/optimistic bands, per the plan's own suggested example.
BAND_SPREAD_PERCENT = Decimal("2")

MONEY_QUANTIZE = Decimal("0.01")


def _periods_per_year(frequency: str) -> int:
    return PERIODS_PER_YEAR.get(
        frequency.strip().lower(), DEFAULT_PERIODS_PER_YEAR
    )


def _periodic_rate(annual_return_percent: Decimal, periods_per_year: int) -> Decimal:
    return (annual_return_percent / Decimal(100)) / periods_per_year


def _future_value(
    start_value: Decimal,
    contribution_per_period: Decimal,
    rate: Decimal,
    n: int,
) -> Decimal:
    if rate == 0:
        return start_value + contribution_per_period * n
    growth = (1 + rate) ** n
    return start_value * growth + contribution_per_period * ((growth - 1) / rate)


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTIZE, rounding=ROUND_HALF_UP)


def build_projection(
    *,
    base_currency: str,
    start_value: Decimal,
    target: Decimal | None,
    contribution: Decimal | None,
    annual_return: Decimal,
    years: int,
    frequency: str,
) -> ProjectionResponse:
    periods_per_year = _periods_per_year(frequency)
    contribution_per_period = contribution if contribution is not None else Decimal("0")

    conservative_rate = _periodic_rate(
        annual_return - BAND_SPREAD_PERCENT, periods_per_year
    )
    expected_rate = _periodic_rate(annual_return, periods_per_year)
    optimistic_rate = _periodic_rate(
        annual_return + BAND_SPREAD_PERCENT, periods_per_year
    )

    series: list[ProjectionYearPoint] = []
    expected_by_year: dict[int, Decimal] = {}
    for year in range(years + 1):
        n = periods_per_year * year
        conservative = _quantize(
            _future_value(
                start_value, contribution_per_period, conservative_rate, n
            )
        )
        expected = _quantize(
            _future_value(start_value, contribution_per_period, expected_rate, n)
        )
        optimistic = _quantize(
            _future_value(
                start_value, contribution_per_period, optimistic_rate, n
            )
        )
        expected_by_year[year] = expected
        series.append(
            ProjectionYearPoint(
                year=year,
                conservative=conservative,
                expected=expected,
                optimistic=optimistic,
            )
        )

    target_progress_percent: Decimal | None = None
    on_track: bool | None = None
    target_reached_year: int | None = None

    if target is not None:
        if target == 0:
            target_progress_percent = Decimal("100.00")
            on_track = True
            target_reached_year = 0
        else:
            target_progress_percent = _quantize(
                (start_value / target) * Decimal(100)
            )
            target_reached_year = next(
                (
                    year
                    for year in range(years + 1)
                    if expected_by_year[year] >= target
                ),
                None,
            )
            on_track = target_reached_year is not None

    return ProjectionResponse(
        base_currency=base_currency,
        start_value=start_value,
        target_amount=target,
        horizon_years=years,
        contribution_amount=contribution_per_period,
        contribution_frequency=frequency,
        annual_return_expected=annual_return,
        series=series,
        target_progress_percent=target_progress_percent,
        on_track=on_track,
        target_reached_year=target_reached_year,
    )
