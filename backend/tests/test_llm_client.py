import json
from typing import Protocol

import httpx
import pytest

from app.core.config import Settings
from app.integrations.llm import (
    ChatCompletion,
    ChatMessage,
    GroqLlmClient,
    LlmError,
    LlmRateLimitError,
    ToolCall,
    ToolSpec,
    is_llm_configured,
    parse_completion,
)


class FakeLlmClient(Protocol):
    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> ChatCompletion: ...


class ScriptedLlmClient:
    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> ChatCompletion:
        return ChatCompletion(
            message=ChatMessage(role="assistant", content="Canned reply."),
            tool_calls=[],
        )


def test_fake_llm_client_can_return_canned_completion() -> None:
    client: FakeLlmClient = ScriptedLlmClient()

    completion = client.complete([ChatMessage(role="user", content="Hello")])

    assert completion.message.content == "Canned reply."
    assert completion.tool_calls == []


def test_groq_client_serializes_messages_and_tools() -> None:
    captured_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["authorization"] = request.headers["Authorization"]
        captured_request["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "Use VXUS."}}
                ]
            },
        )

    client = GroqLlmClient(
        api_key="groq-key",
        base_url="https://example.test/openai/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_tokens=256,
        model="llama-test",
    )

    completion = client.complete(
        messages=[
            ChatMessage(role="system", content="You are careful."),
            ChatMessage(role="user", content="How should I diversify?"),
        ],
        tools=[
            ToolSpec(
                name="get_portfolio_breakdowns",
                description="Read allocation breakdowns.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            )
        ],
    )

    assert completion.message.content == "Use VXUS."
    assert captured_request["url"] == "https://example.test/openai/v1/chat/completions"
    assert captured_request["authorization"] == "Bearer groq-key"
    assert captured_request["body"] == {
        "model": "llama-test",
        "messages": [
            {"role": "system", "content": "You are careful."},
            {"role": "user", "content": "How should I diversify?"},
        ],
        "max_tokens": 256,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_portfolio_breakdowns",
                    "description": "Read allocation breakdowns.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                },
            }
        ],
    }


def test_groq_client_parses_tool_calls() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "simulate_trades",
                                        "arguments": json.dumps(
                                            {
                                                "legs": [
                                                    {
                                                        "symbol": "VXUS",
                                                        "action": "buy",
                                                        "quantity": "5",
                                                    }
                                                ]
                                            }
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    client = GroqLlmClient(
        api_key="groq-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    completion = client.complete([ChatMessage(role="user", content="Try VXUS")])

    assert completion.message.role == "assistant"
    assert completion.message.content is None
    assert completion.tool_calls == [
        ToolCall(
            id="call-1",
            name="simulate_trades",
            arguments={
                "legs": [
                    {
                        "symbol": "VXUS",
                        "action": "buy",
                        "quantity": "5",
                    }
                ]
            },
        )
    ]


def test_parse_completion_captures_finish_reason() -> None:
    """The loop needs finish_reason to tell a truncated answer from a blank one."""
    completion = parse_completion(
        {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"role": "assistant", "content": ""},
                }
            ]
        }
    )

    assert completion.finish_reason == "length"


def test_groq_client_default_reasoning_effort_is_provider_valid() -> None:
    """Groq's gpt-oss models reject reasoning_effort outside low/medium/high.

    Regression: the default was ``"default"``, which Groq rejected with HTTP
    400 ("`reasoning_effort` must be one of `low`, `medium`, or `high`"),
    breaking every assistant turn.
    """
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "OK"}}]}
        )

    settings = Settings(llm_api_key="groq-key")
    client = GroqLlmClient.from_settings(
        settings,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.complete([ChatMessage(role="user", content="Hello")])

    assert captured.get("reasoning_effort") in {"low", "medium", "high"}


def test_groq_client_retries_on_429_and_succeeds() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 2:
            return httpx.Response(
                429, headers={"retry-after": "0"}, text="rate limited"
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "OK"}}]}
        )

    client = GroqLlmClient(
        api_key="groq-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    completion = client.complete([ChatMessage(role="user", content="Hello")])

    assert completion.message.content == "OK"
    assert len(calls) == 2


def test_groq_client_raises_rate_limit_error_after_all_retries() -> None:
    client = GroqLlmClient(
        api_key="groq-key",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    429, headers={"retry-after": "0"}, text="rate limited"
                )
            )
        ),
    )

    with pytest.raises(LlmRateLimitError, match="rate-limited"):
        client.complete([ChatMessage(role="user", content="Hello")])


def test_groq_client_raises_llm_error_for_provider_errors() -> None:
    client = GroqLlmClient(
        api_key="groq-key",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(500, text="provider failed")
            )
        ),
    )

    with pytest.raises(LlmError, match="LLM provider request failed"):
        client.complete([ChatMessage(role="user", content="Hello")])


def test_groq_client_raises_llm_error_for_timeouts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("too slow", request=request)

    client = GroqLlmClient(
        api_key="groq-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(LlmError, match="LLM provider timed out"):
        client.complete([ChatMessage(role="user", content="Hello")])


def test_parse_completion_recovers_inline_function_call() -> None:
    completion = parse_completion(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": (
                            "On it. "
                            "<function=simulate_trades>"
                            '{"legs":[{"symbol":"VXUS","action":"buy",'
                            '"quantity":"5"}]}'
                            "</function>"
                        ),
                    }
                }
            ]
        }
    )

    assert completion.tool_calls == [
        ToolCall(
            id="inline-call-0",
            name="simulate_trades",
            arguments={
                "legs": [{"symbol": "VXUS", "action": "buy", "quantity": "5"}]
            },
        )
    ]
    assert completion.message.content == "On it."
    assert "<function=" not in (completion.message.content or "")


def test_parse_completion_recovers_self_closing_inline_call() -> None:
    completion = parse_completion(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": (
                            "Checking your mix. "
                            "<function=get_portfolio_breakdowns></function>"
                        ),
                    }
                }
            ]
        }
    )

    assert completion.tool_calls == [
        ToolCall(
            id="inline-call-0",
            name="get_portfolio_breakdowns",
            arguments={},
        )
    ]
    assert completion.message.content == "Checking your mix."


def test_parse_completion_prefers_structured_tool_calls_over_inline() -> None:
    completion = parse_completion(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "<function=simulate_trades></function>",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "get_portfolio_breakdowns",
                                    "arguments": "{}",
                                },
                            }
                        ],
                    }
                }
            ]
        }
    )

    assert [call.name for call in completion.tool_calls] == [
        "get_portfolio_breakdowns"
    ]


def test_missing_llm_api_key_is_detectable() -> None:
    assert is_llm_configured(Settings(llm_api_key=None)) is False
    assert is_llm_configured(Settings(llm_api_key="")) is False
    assert is_llm_configured(Settings(llm_api_key="groq-key")) is True
