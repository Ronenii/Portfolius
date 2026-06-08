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
    ToolCall,
    ToolSpec,
    is_llm_configured,
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


def test_missing_llm_api_key_is_detectable() -> None:
    assert is_llm_configured(Settings(llm_api_key=None)) is False
    assert is_llm_configured(Settings(llm_api_key="")) is False
    assert is_llm_configured(Settings(llm_api_key="groq-key")) is True
