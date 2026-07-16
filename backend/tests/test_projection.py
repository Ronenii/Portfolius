from decimal import Decimal

from app.domain.projection import build_projection


def series_by_year(response):
    return {point.year: point for point in response.series}


def test_annual_compounding_no_contribution() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        target=None,
        contribution=None,
        annual_return=Decimal("10"),
        years=2,
        frequency="annually",
    )

    points = series_by_year(response)
    assert points[0].expected == Decimal("10000.00")
    assert points[1].expected == Decimal("11000.00")
    assert points[2].expected == Decimal("12100.00")


def test_zero_rate_branch_with_contributions() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("0"),
        target=None,
        contribution=Decimal("1000"),
        annual_return=Decimal("0"),
        years=3,
        frequency="annually",
    )

    points = series_by_year(response)
    assert points[0].expected == Decimal("0.00")
    assert points[1].expected == Decimal("1000.00")
    assert points[2].expected == Decimal("2000.00")
    assert points[3].expected == Decimal("3000.00")


def test_band_ordering_conservative_le_expected_le_optimistic() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        target=None,
        contribution=Decimal("100"),
        annual_return=Decimal("10"),
        years=5,
        frequency="monthly",
    )

    for point in response.series:
        if point.year == 0:
            assert point.conservative == point.expected == point.optimistic
        else:
            assert point.conservative <= point.expected <= point.optimistic


def test_target_progress_not_reached_within_horizon() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        target=Decimal("15000"),
        contribution=None,
        annual_return=Decimal("10"),
        years=2,
        frequency="annually",
    )

    assert response.target_progress_percent == Decimal("66.67")
    assert response.target_reached_year is None
    assert response.on_track is False
    assert response.target_amount == Decimal("15000")


def test_target_already_met() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        target=Decimal("10000"),
        contribution=None,
        annual_return=Decimal("10"),
        years=2,
        frequency="annually",
    )

    assert response.target_progress_percent == Decimal("100.00")
    assert response.target_reached_year == 0
    assert response.on_track is True


def test_target_none_leaves_all_target_fields_none() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        target=None,
        contribution=None,
        annual_return=Decimal("10"),
        years=2,
        frequency="annually",
    )

    assert response.target_amount is None
    assert response.target_progress_percent is None
    assert response.on_track is None
    assert response.target_reached_year is None


def test_target_zero_treated_as_already_met() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        target=Decimal("0"),
        contribution=None,
        annual_return=Decimal("10"),
        years=2,
        frequency="annually",
    )

    assert response.target_progress_percent == Decimal("100.00")
    assert response.on_track is True
    assert response.target_reached_year == 0


def test_unrecognized_frequency_falls_back_to_monthly() -> None:
    fallback = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        target=None,
        contribution=None,
        annual_return=Decimal("10"),
        years=1,
        frequency="biweekly",
    )
    monthly = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        target=None,
        contribution=None,
        annual_return=Decimal("10"),
        years=1,
        frequency="monthly",
    )

    assert fallback.series == monthly.series
    assert fallback.contribution_frequency == "biweekly"


def test_contribution_none_echoes_zero_in_response() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        target=None,
        contribution=None,
        annual_return=Decimal("10"),
        years=1,
        frequency="annually",
    )

    assert response.contribution_amount == Decimal("0")


def test_response_echoes_inputs() -> None:
    response = build_projection(
        base_currency="ILS",
        start_value=Decimal("5000"),
        target=Decimal("20000"),
        contribution=Decimal("200"),
        annual_return=Decimal("6.5"),
        years=4,
        frequency="quarterly",
    )

    assert response.base_currency == "ILS"
    assert response.start_value == Decimal("5000")
    assert response.horizon_years == 4
    assert response.contribution_amount == Decimal("200")
    assert response.contribution_frequency == "quarterly"
    assert response.annual_return_expected == Decimal("6.5")
    assert len(response.series) == 5


def test_series_covers_year_zero_through_years_inclusive() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("1000"),
        target=None,
        contribution=None,
        annual_return=Decimal("5"),
        years=10,
        frequency="annually",
    )

    assert [point.year for point in response.series] == list(range(11))


def test_cost_basis_starts_at_start_cost_basis() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        start_cost_basis=Decimal("8000"),
        target=None,
        contribution=None,
        annual_return=Decimal("10"),
        years=2,
        frequency="annually",
    )

    points = series_by_year(response)
    assert points[0].cost_basis == Decimal("8000.00")


def test_cost_basis_accumulates_contributions_without_growth() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        start_cost_basis=Decimal("8000"),
        target=None,
        contribution=Decimal("1000"),
        annual_return=Decimal("10"),
        years=3,
        frequency="annually",
    )

    points = series_by_year(response)
    assert points[0].cost_basis == Decimal("8000.00")
    assert points[1].cost_basis == Decimal("9000.00")
    assert points[2].cost_basis == Decimal("10000.00")
    assert points[3].cost_basis == Decimal("11000.00")


def test_cost_basis_flat_when_no_contribution() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        start_cost_basis=Decimal("8000"),
        target=None,
        contribution=None,
        annual_return=Decimal("10"),
        years=2,
        frequency="annually",
    )

    points = series_by_year(response)
    assert (
        points[0].cost_basis
        == points[1].cost_basis
        == points[2].cost_basis
        == Decimal("8000.00")
    )


def test_cost_basis_defaults_to_zero_when_not_provided() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        target=None,
        contribution=Decimal("500"),
        annual_return=Decimal("10"),
        years=1,
        frequency="annually",
    )

    points = series_by_year(response)
    assert points[0].cost_basis == Decimal("0.00")
    assert points[1].cost_basis == Decimal("500.00")
