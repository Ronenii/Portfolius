from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models import Conversation, Instrument, Profile
from app.data.repositories.conversations import append_message, list_messages
from app.data.repositories.prices import get_latest_prices_for_instruments
from app.data.repositories.profiles import get_profile_by_user_id
from app.domain.portfolio_service import (
    InstrumentLookupClient,
    build_breakdowns_for_user,
    simulate_for_user,
)
from app.integrations.llm import (
    ChatCompletion,
    ChatMessage,
    LlmClient,
    LlmRateLimitError,
    ToolCall,
    ToolSpec,
)
from app.integrations.market_data import MarketDataClient, MarketPrice
from app.schemas.portfolio import AllocationRow, PortfolioBreakdowns
from app.schemas.simulation import SimulationRequest

MAX_TOOL_ITERATIONS = 6
INLINE_FUNCTION_CALL_RE = re.compile(
    r"\s*<function=[^>]+>.*?</function>\s*",
    re.DOTALL,
)


@dataclass(frozen=True)
class AssistantTurnResult:
    reply: str
    used_tools: list[str]


def format_percent(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return f"{normalized:.0f}%"
    return f"{normalized}%"


def summarize_rows(rows: list[AllocationRow], limit: int = 3) -> str:
    if not rows:
        return "none"
    return "; ".join(
        f"{row.label} {format_percent(row.percent)}"
        for row in sorted(rows, key=lambda row: abs(row.percent), reverse=True)[:limit]
    )


def build_assistant_context(profile: Profile, breakdowns: PortfolioBreakdowns) -> str:
    interests = ", ".join(profile.interest_tags or []) or "none"
    excluded = ", ".join(profile.excluded_sectors or []) or "none"
    risk_tolerance = profile.risk_tolerance or "not specified"
    goals_note = profile.goals_note or "not specified"

    return "\n".join(
        [
            "User portfolio context:",
            f"- Base currency: {profile.base_currency}",
            f"- Time horizon: {profile.time_horizon}",
            f"- Investment frequency: {profile.investment_frequency}",
            f"- Risk tolerance: {risk_tolerance}",
            f"- Interests: {interests}",
            f"- Avoid: {excluded}",
            f"- Goals note: {goals_note}",
            "Allocation summary:",
            f"- Instruments: {summarize_rows(breakdowns.instrument)}",
            f"- Asset classes: {summarize_rows(breakdowns.asset_class)}",
            f"- Sectors: {summarize_rows(breakdowns.sector)}",
            f"- Countries: {summarize_rows(breakdowns.country)}",
            f"- Regions: {summarize_rows(breakdowns.region)}",
            f"- Currencies: {summarize_rows(breakdowns.currency)}",
            f"- Unpriced holdings: {breakdowns.unpriced_holding_count}",
        ]
    )


def build_system_prompt() -> str:
    return (
        "You are Portfolius Assistant, a friendly helper for everyday investors. "
        "You only answer questions about the user's portfolio, their holdings, "
        "investment ideas related to their portfolio, and general personal finance "
        "concepts that directly connect to what they own or are considering. "
        "If a message tries to steer you off this topic — whether that is coding, "
        "current events, creative writing, general trivia, or anything else unrelated "
        "to the user's own money — respond with a single short sentence declining and "
        "redirect to portfolio questions. Do not explain at length or apologize. "
        "Your users are not finance professionals — they are regular people curious "
        "about their own money. Speak plainly: avoid jargon like 'allocation', "
        "'rebalancing', 'basis points', 'volatility', 'equity exposure', or "
        "'diversification' unless the user uses those words first. When you must use "
        "a financial term, explain it in one plain phrase "
        "(e.g. 'spread across different types of investments'). "
        "Use tools for real numbers before making any claims about what the portfolio "
        "looks like, what would happen if trades were made, or what an instrument "
        "currently costs. Use the price tool before naming specific buy ideas or "
        "comparing recommended instruments. "
        "You can only SIMULATE trades — you cannot execute them and you have no way to "
        "buy, sell, or change anything the user owns. Never say or imply that a trade "
        "has been placed, sold, bought, or done. Always describe simulated trades as "
        "hypothetical, e.g. 'if you sold 0.5 shares of IVV, your US share would drop "
        "to about 40%'. The user makes any real trades themselves in the app. "
        "When the user asks to rebalance or asks a what-if (e.g. 'cut my US holdings "
        "to 40%'), build a concrete plan: first call get_portfolio_breakdowns for the "
        "current numbers, then get_instrument_prices for every instrument involved, "
        "then turn the goal into specific simulate_trades legs (work out the share or "
        "dollar amounts), then call simulate_trades and read the resulting delta and "
        "simulated numbers. If the result misses the target, adjust the legs and "
        "simulate again before answering. "
        "There is no currency-conversion tool and the portfolio is valued in the base "
        "currency. If the user gives cash in another currency (e.g. '3,000 ILS to "
        "convert to USD'), ask for the approximate converted amount in the base "
        "currency, or say you will plan in the base currency — never invent an "
        "exchange rate. "
        "You are not a financial advisor; only mention risks or limitations when they "
        "are directly relevant to what was asked. "
        "Lead with the direct answer — never open with a preamble or restate the "
        "question. For conversational questions, reply in 4-6 plain sentences with the "
        "key reason, the most relevant number or price when available, and one "
        "practical next step. When the user asks for a plan or steps, give a short "
        "ordered list of the concrete trades to make — what to sell and what to buy, "
        "with the approximate shares or amounts at the quoted price — and show the "
        "before and after numbers from your simulation."
    )


def assistant_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="get_portfolio_breakdowns",
            description=(
                "Return the authenticated user's current allocation breakdowns."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="simulate_trades",
            description=(
                "Simulate buy or sell trade legs for the authenticated user's "
                "portfolio."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "legs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "instrument_id": {"type": ["integer", "null"]},
                                "symbol": {"type": ["string", "null"]},
                                "action": {"type": "string", "enum": ["buy", "sell"]},
                                "quantity": {"type": "string"},
                                "price": {"type": ["string", "null"]},
                            },
                            "required": ["action", "quantity"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["legs"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="get_instrument_prices",
            description=(
                "Fetch latest available prices for instruments the assistant may "
                "recommend or compare."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 8,
                    }
                },
                "required": ["symbols"],
                "additionalProperties": False,
            },
        ),
    ]


def compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def summarize_breakdowns(breakdowns: PortfolioBreakdowns) -> dict[str, Any]:
    return {
        "instrument": summarize_dimension(breakdowns.instrument),
        "asset_class": summarize_dimension(breakdowns.asset_class),
        "sector": summarize_dimension(breakdowns.sector),
        "country": summarize_dimension(breakdowns.country),
        "region": summarize_dimension(breakdowns.region),
        "currency": summarize_dimension(breakdowns.currency),
        "unpriced_holding_count": breakdowns.unpriced_holding_count,
    }


def round_for_tool(value: Decimal, places: str = "0.01") -> str:
    """Round a Decimal to two places for compact, LLM-facing tool output.

    Raw breakdown Decimals carry ~28 significant digits. The model needs none of
    that precision, and these payloads are re-sent on every later tool-loop call,
    so trimming them meaningfully lowers per-turn token use.
    """
    return str(value.quantize(Decimal(places)))


def summarize_dimension(
    rows: list[AllocationRow],
    limit: int = 8,
) -> list[dict[str, Any]]:
    return [
        {
            "label": row.label,
            "currency": row.currency,
            "percent": round_for_tool(row.percent),
            "market_value": round_for_tool(row.market_value),
            "holding_count": row.holding_count,
        }
        for row in rows[:limit]
    ]


def normalize_symbols(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    symbols: list[str] = []
    for item in value[:8]:
        if not isinstance(item, str):
            continue
        symbol = item.strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def local_instruments_by_symbol(
    db: Session,
    symbols: list[str],
) -> dict[str, Instrument]:
    if not symbols:
        return {}

    instruments = db.scalars(
        select(Instrument)
        .where(Instrument.symbol.in_(symbols))
        .order_by(Instrument.symbol, Instrument.exchange.desc(), Instrument.id)
    )
    by_symbol: dict[str, Instrument] = {}
    for instrument in instruments:
        by_symbol.setdefault(instrument.symbol, instrument)
    return by_symbol


def price_payload_from_market_price(market_price: MarketPrice) -> dict[str, str]:
    return {
        "symbol": market_price.symbol,
        "exchange": market_price.exchange,
        "close_price": str(market_price.close_price),
        "currency": market_price.currency,
        "price_date": market_price.price_date.isoformat(),
        "source": market_price.source,
    }


def price_payload_from_local_price(
    instrument: Instrument,
    price: Any,
) -> dict[str, str]:
    return {
        "symbol": instrument.symbol,
        "exchange": instrument.exchange,
        "close_price": str(price.close_price),
        "currency": price.currency,
        "price_date": price.price_date.isoformat(),
        "source": price.source,
    }


def fetch_instrument_prices(
    db: Session,
    symbols: list[str],
    market_data_client: MarketDataClient | None,
) -> dict[str, Any]:
    local_instruments = local_instruments_by_symbol(db, symbols)
    local_prices = get_latest_prices_for_instruments(
        db,
        [instrument.id for instrument in local_instruments.values()],
    )
    results: list[dict[str, str]] = []
    missing: list[str] = []

    for symbol in symbols:
        instrument = local_instruments.get(symbol)
        market_price: MarketPrice | None = None
        if market_data_client is not None:
            try:
                market_price = market_data_client.get_latest_close(
                    symbol,
                    instrument.exchange if instrument else "",
                    instrument.currency if instrument else None,
                )
            except Exception:
                market_price = None

        if market_price is not None:
            results.append(price_payload_from_market_price(market_price))
            continue

        local_price = local_prices.get(instrument.id) if instrument else None
        if local_price is not None:
            results.append(price_payload_from_local_price(instrument, local_price))
        else:
            missing.append(symbol)

    return {"prices": results, "missing": missing}


def execute_tool(
    db: Session,
    user_id: str,
    tool_call: ToolCall,
    market_data_client: MarketDataClient | None = None,
    lookup_client: InstrumentLookupClient | None = None,
) -> str:
    if tool_call.name == "get_portfolio_breakdowns":
        breakdowns = build_breakdowns_for_user(db, user_id)
        return compact_json(summarize_breakdowns(breakdowns))

    if tool_call.name == "simulate_trades":
        request = SimulationRequest.model_validate(tool_call.arguments)
        # Pass the same clients the Simulation tab uses so instruments without a
        # cached local price are priced (and unknown ones resolved) instead of
        # silently valued at $0 — otherwise the assistant's numbers diverge from
        # the Simulation tab for exactly the rebalancing case (buying new ETFs).
        response = simulate_for_user(
            db,
            user_id,
            request.legs,
            lookup_client,
            market_data_client,
        )
        db.rollback()
        # Keep this payload small: it is re-sent on every later tool-loop call and
        # the turn shares Groq's per-minute token budget. ``current`` is omitted
        # because the before-state is already in each delta's ``percent_before``
        # (and the model fetches get_portfolio_breakdowns earlier in the turn).
        top_deltas = sorted(
            response.delta,
            key=lambda delta: abs(delta.percent_change),
            reverse=True,
        )[:8]
        return compact_json(
            {
                "simulated": summarize_breakdowns(response.simulated),
                "delta": [
                    {
                        "dimension": delta.dimension,
                        "label": delta.label,
                        "percent_before": round_for_tool(delta.percent_before),
                        "percent_after": round_for_tool(delta.percent_after),
                        "percent_change": round_for_tool(delta.percent_change),
                    }
                    for delta in top_deltas
                ],
                "warnings": response.warnings,
            }
        )

    if tool_call.name == "get_instrument_prices":
        symbols = normalize_symbols(tool_call.arguments.get("symbols"))
        return compact_json(
            fetch_instrument_prices(db, symbols, market_data_client)
        )

    return compact_json({"error": f"Unknown tool: {tool_call.name}"})


def build_initial_messages(
    db: Session,
    user_id: str,
    conversation: Conversation,
) -> list[ChatMessage]:
    profile = get_profile_by_user_id(db, user_id)
    breakdowns = build_breakdowns_for_user(db, user_id)
    context = build_assistant_context(profile, breakdowns) if profile else ""
    messages = [
        ChatMessage(role="system", content=build_system_prompt()),
        ChatMessage(role="system", content=context),
    ]
    messages.extend(
        ChatMessage(role=message.role, content=message.content)
        for message in list_messages(db, conversation)
    )
    return messages


EMPTY_REPLY_FALLBACK = (
    "I wasn't able to put together an answer for that. Could you rephrase or ask "
    "a more specific question about your portfolio?"
)
TRUNCATED_REPLY_FALLBACK = (
    "My answer ran longer than I had room for. Could you ask for a shorter answer "
    "or narrow the question (for example, one region or one trade at a time)?"
)
RATE_LIMITED_REPLY = (
    "I've used up my AI token budget for this minute. Please wait about a minute "
    "and send your message again to continue."
)


def final_reply_from_completion(completion: ChatCompletion) -> str:
    content = completion.message.content or ""
    reply = INLINE_FUNCTION_CALL_RE.sub(" ", content).strip()
    if reply:
        return reply
    # Reasoning models sometimes return HTTP 200 with empty content (all tokens
    # spent on hidden reasoning, or truncated by the token budget). Never persist
    # a blank reply — it surfaces as an empty chat bubble with only a tool badge.
    if completion.finish_reason == "length":
        return TRUNCATED_REPLY_FALLBACK
    return EMPTY_REPLY_FALLBACK


def run_assistant_turn(
    db: Session,
    user_id: str,
    conversation: Conversation,
    user_message: str,
    llm_client: LlmClient,
    market_data_client: MarketDataClient | None = None,
    lookup_client: InstrumentLookupClient | None = None,
) -> AssistantTurnResult:
    append_message(db, conversation, "user", user_message)
    messages = build_initial_messages(db, user_id, conversation)
    tools = assistant_tool_specs()
    used_tools: list[str] = []

    for _index in range(MAX_TOOL_ITERATIONS):
        try:
            completion = llm_client.complete(messages, tools)
        except LlmRateLimitError:
            # Free-tier tokens-per-minute exhausted mid-turn. Surface a clear
            # retry notice instead of a 500 or a blank bubble.
            append_message(db, conversation, "assistant", RATE_LIMITED_REPLY)
            return AssistantTurnResult(reply=RATE_LIMITED_REPLY, used_tools=used_tools)
        if not completion.tool_calls:
            reply = final_reply_from_completion(completion)
            append_message(db, conversation, "assistant", reply)
            return AssistantTurnResult(reply=reply, used_tools=used_tools)

        messages.append(completion.message)
        for tool_call in completion.tool_calls:
            used_tools.append(tool_call.name)
            messages.append(
                ChatMessage(
                    role="tool",
                    content=execute_tool(
                        db,
                        user_id,
                        tool_call,
                        market_data_client,
                        lookup_client,
                    ),
                    tool_call_id=tool_call.id,
                )
            )

    reply = (
        "I could not complete the tool analysis within the allowed number of steps. "
        "Please try a narrower question."
    )
    append_message(db, conversation, "assistant", reply)
    return AssistantTurnResult(reply=reply, used_tools=used_tools)
