from decimal import Decimal

from app.data.models import Profile
from app.domain.assistant import build_assistant_context, build_system_prompt
from app.schemas.portfolio import AllocationRow, PortfolioBreakdowns


def breakdowns() -> PortfolioBreakdowns:
    return PortfolioBreakdowns(
        instrument=[
            AllocationRow(
                currency="USD",
                dimension="instrument",
                holding_count=1,
                label="VOO",
                market_value=Decimal("1000"),
                percent=Decimal("62.5"),
            )
        ],
        asset_class=[
            AllocationRow(
                currency="USD",
                dimension="asset_class",
                holding_count=1,
                label="ETF",
                market_value=Decimal("1000"),
                percent=Decimal("62.5"),
            )
        ],
        sector=[],
        country=[],
        region=[],
        currency=[],
        unpriced_holding_count=0,
    )


def test_context_summary_includes_goals_and_allocation_percentages() -> None:
    profile = Profile(
        user_id="user-secret-123",
        display_name="Ronen",
        base_currency="USD",
        time_horizon="10+ years",
        investment_frequency="monthly",
        risk_tolerance="balanced",
        interest_tags=["dividends", "technology"],
        excluded_sectors=["tobacco"],
        goals_note="Build long-term wealth without concentrated single-stock risk.",
    )

    context = build_assistant_context(profile, breakdowns())

    assert "Base currency: USD" in context
    assert "Time horizon: 10+ years" in context
    assert "Investment frequency: monthly" in context
    assert "Risk tolerance: balanced" in context
    assert "Interests: dividends, technology" in context
    assert "Avoid: tobacco" in context
    assert "Build long-term wealth" in context
    assert "VOO 62.5%" in context
    assert "ETF 62.5%" in context
    assert "user-secret-123" not in context
    assert "Ronen" not in context
    assert "holding_id" not in context
    assert "access_token" not in context


def test_system_prompt_sets_educational_guardrail_and_tool_expectation() -> None:
    prompt = build_system_prompt()

    assert "not a financial advisor" in prompt.lower()
    assert "use tools" in prompt.lower()
    assert "real numbers" in prompt.lower()
