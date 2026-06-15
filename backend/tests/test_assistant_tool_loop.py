from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser
from app.data.models import Conversation, Holding, Instrument, Price, Profile
from app.data.repositories.conversations import (
    create_conversation,
    list_messages,
)
from app.domain.assistant import (
    MAX_TOOL_ITERATIONS,
    build_system_prompt,
    run_assistant_turn,
)
from app.integrations.llm import (
    ChatCompletion,
    ChatMessage,
    LlmRateLimitError,
    ToolCall,
    ToolSpec,
    parse_completion,
)
from app.integrations.market_data import MarketPrice


class ScriptedLlmClient:
    def __init__(self, completions: list[ChatCompletion]) -> None:
        self.completions = completions
        self.calls: list[tuple[list[ChatMessage], list[ToolSpec] | None]] = []

    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> ChatCompletion:
        self.calls.append((messages, tools))
        if not self.completions:
            raise AssertionError("No scripted completion left")
        return self.completions.pop(0)


class FakeMarketDataClient:
    def __init__(self, prices: dict[str, MarketPrice | None]) -> None:
        self.prices = prices
        self.requests: list[tuple[str, str, str | None]] = []

    def get_latest_close(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> MarketPrice | None:
        self.requests.append((symbol, exchange, currency_hint))
        return self.prices.get(symbol)


def add_profile(db_session: Session, user_id: str) -> Profile:
    profile = Profile(
        user_id=user_id,
        display_name="Ronen",
        base_currency="USD",
        time_horizon="10+ years",
        investment_frequency="monthly",
        risk_tolerance="balanced",
        interest_tags=["dividends"],
        excluded_sectors=[],
        goals_note="Prefer broad ETFs.",
    )
    db_session.add(profile)
    db_session.commit()
    return profile


def add_instrument(
    db_session: Session,
    symbol: str,
    close_price: str,
    *,
    sector: str = "Broad Market",
) -> Instrument:
    instrument = Instrument(
        symbol=symbol,
        name=f"{symbol} Fund",
        exchange="NYSEARCA",
        currency="USD",
        asset_class="ETF",
        sector=sector,
        country="United States",
        region="North America",
    )
    db_session.add(instrument)
    db_session.flush()
    db_session.add(
        Price(
            instrument=instrument,
            price_date=date(2026, 6, 5),
            close_price=Decimal(close_price),
            currency="USD",
            source="fake",
        )
    )
    db_session.commit()
    return instrument


def add_holding(
    db_session: Session,
    user_id: str,
    instrument: Instrument,
    quantity: str,
) -> Holding:
    holding = Holding(
        user_id=user_id,
        instrument=instrument,
        quantity=Decimal(quantity),
        average_cost=Decimal("100"),
    )
    db_session.add(holding)
    db_session.commit()
    return holding


@pytest.fixture
def conversation(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
) -> Conversation:
    add_profile(db_session, authenticated_user.user_id)
    return create_conversation(db_session, authenticated_user.user_id, "What if")


def assistant_completion(content: str) -> ChatCompletion:
    return ChatCompletion(
        message=ChatMessage(role="assistant", content=content),
        tool_calls=[],
    )


def tool_completion(name: str, arguments: dict[str, object]) -> ChatCompletion:
    tool_call = ToolCall(id="tool-call-1", name=name, arguments=arguments)
    return ChatCompletion(
        message=ChatMessage(role="assistant", content=None, tool_calls=[tool_call]),
        tool_calls=[tool_call],
    )


def empty_completion(finish_reason: str | None = None) -> ChatCompletion:
    """A completion with no tool calls and no content — the blank-bubble case."""
    return ChatCompletion(
        message=ChatMessage(role="assistant", content=""),
        tool_calls=[],
        finish_reason=finish_reason,
    )


def inline_completion(content: str) -> ChatCompletion:
    """Build a completion the way GroqLlmClient would for inline tool markup."""
    return parse_completion(
        {"choices": [{"message": {"role": "assistant", "content": content}}]}
    )


def market_price(symbol: str, close_price: str) -> MarketPrice:
    return MarketPrice(
        symbol=symbol,
        exchange="NYSEARCA",
        price_date=date(2026, 6, 8),
        close_price=Decimal(close_price),
        currency="USD",
        source="fake",
    )


def test_system_prompt_requires_hypothetical_framing_and_plans() -> None:
    prompt = build_system_prompt()

    assert "only SIMULATE trades" in prompt
    assert "Never say or imply that a trade" in prompt
    assert "ordered list of the concrete trades" in prompt
    assert "never invent an" in prompt
    assert "price tool" in prompt


def test_turn_without_tools_persists_user_and_assistant_messages(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    conversation: Conversation,
) -> None:
    llm_client = ScriptedLlmClient([assistant_completion("You are diversified.")])

    result = run_assistant_turn(
        db_session,
        authenticated_user.user_id,
        conversation,
        "How diversified am I?",
        llm_client,
    )

    assert result.reply == "You are diversified."
    assert result.used_tools == []
    assert len(llm_client.calls) == 1
    assert llm_client.calls[0][1] is not None
    assert {tool.name for tool in llm_client.calls[0][1] or []} == {
        "get_instrument_prices",
        "get_portfolio_breakdowns",
        "simulate_trades",
    }
    saved_messages = [
        (message.role, message.content)
        for message in list_messages(db_session, conversation)
    ]
    assert saved_messages == [
        ("user", "How diversified am I?"),
        ("assistant", "You are diversified."),
    ]


def test_empty_final_content_does_not_persist_blank_reply(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    conversation: Conversation,
) -> None:
    """A model turn that returns no content must not be stored as an empty bubble.

    Regression: reasoning-model turns sometimes return HTTP 200 with empty
    ``content`` and no tool calls; the loop used to persist ``""`` and the UI
    showed a blank message with only a "ran a simulation" badge.
    """
    llm_client = ScriptedLlmClient([empty_completion()])

    result = run_assistant_turn(
        db_session,
        authenticated_user.user_id,
        conversation,
        "Plan a rebalance for me.",
        llm_client,
    )

    assert result.reply.strip() != ""
    saved_messages = [
        (message.role, message.content)
        for message in list_messages(db_session, conversation)
    ]
    assert saved_messages[-1][0] == "assistant"
    assert (saved_messages[-1][1] or "").strip() != ""


def test_truncated_final_content_explains_it_was_cut_off(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    conversation: Conversation,
) -> None:
    llm_client = ScriptedLlmClient([empty_completion(finish_reason="length")])

    result = run_assistant_turn(
        db_session,
        authenticated_user.user_id,
        conversation,
        "Plan a rebalance for me.",
        llm_client,
    )

    assert "shorter" in result.reply.lower() or "cut off" in result.reply.lower()


class RateLimitedLlmClient:
    """Raises a rate-limit error the way GroqLlmClient does after retries."""

    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> ChatCompletion:
        raise LlmRateLimitError("LLM provider rate-limited; try again in a moment")


def test_rate_limit_returns_friendly_retry_message_not_an_error(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    conversation: Conversation,
) -> None:
    """Free-tier TPM exhaustion must surface a clear 'try again' notice.

    The user accepted the free-tier limit but asked for a message telling them
    the per-minute token budget is used up and to retry in a minute, rather than
    a 500 or a blank bubble.
    """
    result = run_assistant_turn(
        db_session,
        authenticated_user.user_id,
        conversation,
        "Plan a rebalance for me.",
        RateLimitedLlmClient(),
    )

    assert "minute" in result.reply.lower()
    saved_messages = [
        (message.role, message.content)
        for message in list_messages(db_session, conversation)
    ]
    assert saved_messages[-1][0] == "assistant"
    assert (saved_messages[-1][1] or "").strip() != ""


def test_final_reply_strips_inline_function_call_markup(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    conversation: Conversation,
) -> None:
    llm_client = ScriptedLlmClient(
        [
            assistant_completion(
                "You could consider broad international ETFs. "
                "<function=get_portfolio_breakdowns></function>"
            )
        ]
    )

    result = run_assistant_turn(
        db_session,
        authenticated_user.user_id,
        conversation,
        "What should I add?",
        llm_client,
    )

    assert result.reply == "You could consider broad international ETFs."
    saved_messages = [
        (message.role, message.content)
        for message in list_messages(db_session, conversation)
    ]
    assert saved_messages[-1] == (
        "assistant",
        "You could consider broad international ETFs.",
    )


def test_tool_loop_executes_simulation_and_feeds_result_back(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    conversation: Conversation,
) -> None:
    voo = add_instrument(db_session, "VOO", "500")
    add_instrument(db_session, "VXUS", "100", sector="International")
    add_holding(db_session, authenticated_user.user_id, voo, quantity="2")
    llm_client = ScriptedLlmClient(
        [
            tool_completion(
                "simulate_trades",
                {"legs": [{"symbol": "VXUS", "action": "buy", "quantity": "5"}]},
            ),
            assistant_completion("Buying VXUS would add international exposure."),
        ]
    )

    result = run_assistant_turn(
        db_session,
        authenticated_user.user_id,
        conversation,
        "What if I buy VXUS?",
        llm_client,
    )

    assert result.reply == "Buying VXUS would add international exposure."
    assert result.used_tools == ["simulate_trades"]
    assert len(llm_client.calls) == 2
    tool_messages = [
        message for message in llm_client.calls[1][0] if message.role == "tool"
    ]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "tool-call-1"
    assert "VXUS" in (tool_messages[0].content or "")
    assert "simulated" in (tool_messages[0].content or "")


def test_simulation_prices_instruments_via_market_data_client(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    conversation: Conversation,
) -> None:
    """simulate_trades must price instruments that lack a local DB price.

    Regression: run_assistant_turn called simulate_for_user without the
    market-data client, so any instrument without a cached local price was
    valued at $0. Buying e.g. VWO then under-counted the trade, and the
    assistant's numbers diverged from the Simulation tab (which passes the
    client and prices the instrument live).
    """
    voo = add_instrument(db_session, "VOO", "500")
    add_holding(db_session, authenticated_user.user_id, voo, quantity="10")
    # EEM exists locally but has NO price row — only the market client can price it.
    eem = Instrument(
        symbol="EEM",
        name="EEM Fund",
        exchange="NYSEARCA",
        currency="USD",
        asset_class="ETF",
        sector="Broad Market",
        country="China",
        region="Emerging Markets",
    )
    db_session.add(eem)
    db_session.commit()
    market = FakeMarketDataClient({"EEM": market_price("EEM", "50")})
    llm_client = ScriptedLlmClient(
        [
            tool_completion(
                "simulate_trades",
                {"legs": [{"symbol": "EEM", "action": "buy", "quantity": "20"}]},
            ),
            assistant_completion("Done."),
        ]
    )

    run_assistant_turn(
        db_session,
        authenticated_user.user_id,
        conversation,
        "What if I buy EEM?",
        llm_client,
        market,
    )

    tool_messages = [
        message for message in llm_client.calls[1][0] if message.role == "tool"
    ]
    content = tool_messages[0].content or ""
    assert "simulated holding is unpriced" not in content.lower()
    assert "Emerging Markets" in content


def test_tool_loop_recovers_inline_function_call(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    conversation: Conversation,
) -> None:
    voo = add_instrument(db_session, "VOO", "500")
    add_instrument(db_session, "VXUS", "100", sector="International")
    add_holding(db_session, authenticated_user.user_id, voo, quantity="2")
    llm_client = ScriptedLlmClient(
        [
            inline_completion(
                "Let me check that. "
                "<function=simulate_trades>"
                '{"legs":[{"symbol":"VXUS","action":"buy","quantity":"5"}]}'
                "</function>"
            ),
            assistant_completion("Buying VXUS would add international exposure."),
        ]
    )

    result = run_assistant_turn(
        db_session,
        authenticated_user.user_id,
        conversation,
        "What if I buy VXUS?",
        llm_client,
    )

    assert result.used_tools == ["simulate_trades"]
    assert result.reply == "Buying VXUS would add international exposure."
    tool_messages = [
        message for message in llm_client.calls[1][0] if message.role == "tool"
    ]
    assert len(tool_messages) == 1
    assert "simulated" in (tool_messages[0].content or "")


def test_tool_loop_fetches_prices_for_recommended_instruments(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    conversation: Conversation,
) -> None:
    llm_client = ScriptedLlmClient(
        [
            tool_completion("get_instrument_prices", {"symbols": ["IEMG", "VGK"]}),
            assistant_completion(
                "IEMG is around $54.12 and VGK is around $71.34, so both are "
                "priced options to compare before deciding."
            ),
        ]
    )
    market_data_client = FakeMarketDataClient(
        {
            "IEMG": market_price("IEMG", "54.12"),
            "VGK": market_price("VGK", "71.34"),
        }
    )

    result = run_assistant_turn(
        db_session,
        authenticated_user.user_id,
        conversation,
        "What ETFs should I consider?",
        llm_client,
        market_data_client,
    )

    assert result.used_tools == ["get_instrument_prices"]
    assert market_data_client.requests == [
        ("IEMG", "", None),
        ("VGK", "", None),
    ]
    tool_messages = [
        message for message in llm_client.calls[1][0] if message.role == "tool"
    ]
    assert len(tool_messages) == 1
    assert '"symbol":"IEMG"' in (tool_messages[0].content or "")
    assert '"close_price":"54.12"' in (tool_messages[0].content or "")
    assert '"price_date":"2026-06-08"' in (tool_messages[0].content or "")
    assert result.reply.startswith("IEMG is around")


def test_tool_executors_are_user_scoped(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    conversation: Conversation,
) -> None:
    voo = add_instrument(db_session, "VOO", "500")
    bnd = add_instrument(db_session, "BND", "80")
    add_profile(db_session, second_user.user_id)
    add_holding(db_session, authenticated_user.user_id, voo, quantity="2")
    add_holding(db_session, second_user.user_id, bnd, quantity="10")
    llm_client = ScriptedLlmClient(
        [
            tool_completion("get_portfolio_breakdowns", {}),
            assistant_completion("Only your VOO allocation is in scope."),
        ]
    )

    run_assistant_turn(
        db_session,
        authenticated_user.user_id,
        conversation,
        "Show my allocation.",
        llm_client,
    )

    tool_messages = [
        message for message in llm_client.calls[1][0] if message.role == "tool"
    ]
    assert "VOO" in (tool_messages[0].content or "")
    assert "BND" not in (tool_messages[0].content or "")


def test_loop_stops_at_tool_iteration_cap(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    conversation: Conversation,
) -> None:
    llm_client = ScriptedLlmClient(
        [
            tool_completion("get_portfolio_breakdowns", {})
            for _index in range(MAX_TOOL_ITERATIONS + 1)
        ]
    )

    result = run_assistant_turn(
        db_session,
        authenticated_user.user_id,
        conversation,
        "Keep checking tools.",
        llm_client,
    )

    assert len(llm_client.calls) == MAX_TOOL_ITERATIONS
    assert result.used_tools == ["get_portfolio_breakdowns"] * MAX_TOOL_ITERATIONS
    assert "could not complete" in result.reply.lower()
