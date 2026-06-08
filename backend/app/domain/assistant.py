from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.data.models import Conversation, Profile
from app.data.repositories.conversations import append_message, list_messages
from app.data.repositories.profiles import get_profile_by_user_id
from app.domain.portfolio_service import build_breakdowns_for_user, simulate_for_user
from app.integrations.llm import (
    ChatCompletion,
    ChatMessage,
    LlmClient,
    ToolCall,
    ToolSpec,
)
from app.schemas.portfolio import AllocationRow, PortfolioBreakdowns
from app.schemas.simulation import SimulationRequest

MAX_TOOL_ITERATIONS = 4


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
        "a financial term, explain it in one plain phrase (e.g. 'spread across different "
        "types of investments'). "
        "Use tools for real numbers before making any claims about what the portfolio "
        "looks like or what would happen if trades were made. "
        "You are not a financial advisor; only mention risks or limitations when they "
        "are directly relevant to what was asked. "
        "Reply in 2-4 plain sentences for conversational questions. Only give a longer "
        "answer when the user asks for detail. Lead with the direct answer — never "
        "open with a preamble or restate the question."
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


def summarize_dimension(
    rows: list[AllocationRow],
    limit: int = 8,
) -> list[dict[str, Any]]:
    return [
        {
            "label": row.label,
            "currency": row.currency,
            "percent": str(row.percent),
            "market_value": str(row.market_value),
            "holding_count": row.holding_count,
        }
        for row in rows[:limit]
    ]


def execute_tool(
    db: Session,
    user_id: str,
    tool_call: ToolCall,
) -> str:
    if tool_call.name == "get_portfolio_breakdowns":
        breakdowns = build_breakdowns_for_user(db, user_id)
        return compact_json(summarize_breakdowns(breakdowns))

    if tool_call.name == "simulate_trades":
        request = SimulationRequest.model_validate(tool_call.arguments)
        response = simulate_for_user(db, user_id, request.legs)
        db.rollback()
        return compact_json(
            {
                "current": summarize_breakdowns(response.current),
                "simulated": summarize_breakdowns(response.simulated),
                "delta": [
                    {
                        "dimension": delta.dimension,
                        "label": delta.label,
                        "currency": delta.currency,
                        "percent_before": str(delta.percent_before),
                        "percent_after": str(delta.percent_after),
                        "percent_change": str(delta.percent_change),
                    }
                    for delta in response.delta[:20]
                ],
                "warnings": response.warnings,
            }
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


def final_reply_from_completion(completion: ChatCompletion) -> str:
    return completion.message.content or ""


def run_assistant_turn(
    db: Session,
    user_id: str,
    conversation: Conversation,
    user_message: str,
    llm_client: LlmClient,
) -> AssistantTurnResult:
    append_message(db, conversation, "user", user_message)
    messages = build_initial_messages(db, user_id, conversation)
    tools = assistant_tool_specs()
    used_tools: list[str] = []

    for _index in range(MAX_TOOL_ITERATIONS):
        completion = llm_client.complete(messages, tools)
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
                    content=execute_tool(db, user_id, tool_call),
                    tool_call_id=tool_call.id,
                )
            )

    reply = (
        "I could not complete the tool analysis within the allowed number of steps. "
        "Please try a narrower question."
    )
    append_message(db, conversation, "assistant", reply)
    return AssistantTurnResult(reply=reply, used_tools=used_tools)
