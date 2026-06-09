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
from app.domain.assistant import MAX_TOOL_ITERATIONS, run_assistant_turn
from app.integrations.llm import ChatCompletion, ChatMessage, ToolCall, ToolSpec


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
