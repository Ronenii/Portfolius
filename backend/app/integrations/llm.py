from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.core.config import Settings


class LlmError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ChatCompletion:
    message: ChatMessage
    tool_calls: list[ToolCall]


class LlmClient(Protocol):
    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> ChatCompletion: ...


def is_llm_configured(settings: Settings) -> bool:
    return bool(settings.llm_api_key and settings.llm_api_key.strip())


def serialize_tool_call(tool_call: ToolCall) -> dict[str, Any]:
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.name,
            "arguments": json.dumps(tool_call.arguments),
        },
    }


def serialize_message(message: ChatMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": message.role,
        "content": message.content,
    }
    if message.tool_calls:
        payload["tool_calls"] = [
            serialize_tool_call(tool_call) for tool_call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    return payload


def serialize_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def parse_arguments(raw_arguments: object) -> dict[str, Any]:
    if not isinstance(raw_arguments, str) or not raw_arguments.strip():
        return {}

    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise LlmError("LLM provider returned invalid tool arguments") from exc

    if not isinstance(parsed, dict):
        return {}
    return parsed


def parse_tool_calls(raw_tool_calls: object) -> list[ToolCall]:
    if not isinstance(raw_tool_calls, list):
        return []

    tool_calls: list[ToolCall] = []
    for raw_tool_call in raw_tool_calls:
        if not isinstance(raw_tool_call, dict):
            continue
        raw_function = raw_tool_call.get("function")
        if not isinstance(raw_function, dict):
            continue
        call_id = raw_tool_call.get("id")
        name = raw_function.get("name")
        if not isinstance(call_id, str) or not isinstance(name, str):
            continue
        tool_calls.append(
            ToolCall(
                id=call_id,
                name=name,
                arguments=parse_arguments(raw_function.get("arguments")),
            )
        )
    return tool_calls


def parse_completion(payload: object) -> ChatCompletion:
    if not isinstance(payload, dict):
        raise LlmError("LLM provider returned an invalid response")

    raw_choices = payload.get("choices")
    if not isinstance(raw_choices, list) or not raw_choices:
        raise LlmError("LLM provider returned no choices")

    raw_message = raw_choices[0].get("message")
    if not isinstance(raw_message, dict):
        raise LlmError("LLM provider returned no assistant message")

    role = raw_message.get("role")
    content = raw_message.get("content")
    if not isinstance(role, str):
        raise LlmError("LLM provider returned a message without a role")
    if content is not None and not isinstance(content, str):
        raise LlmError("LLM provider returned invalid message content")

    tool_calls = parse_tool_calls(raw_message.get("tool_calls"))
    return ChatCompletion(
        message=ChatMessage(role=role, content=content, tool_calls=tool_calls),
        tool_calls=tool_calls,
    )


class GroqLlmClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.groq.com/openai/v1",
        http_client: httpx.Client | None = None,
        max_tokens: int = 1024,
        model: str = "llama-3.3-70b-versatile",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=20.0)
        self.max_tokens = max_tokens
        self.model = model

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        http_client: httpx.Client | None = None,
    ) -> GroqLlmClient:
        if not is_llm_configured(settings):
            raise LlmError("LLM provider is not configured")
        return cls(
            api_key=settings.llm_api_key or "",
            base_url=settings.llm_base_url,
            http_client=http_client,
            max_tokens=settings.llm_max_tokens,
            model=settings.llm_model,
        )

    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> ChatCompletion:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [serialize_message(message) for message in messages],
            "max_tokens": self.max_tokens,
        }
        if tools is not None:
            body["tools"] = [serialize_tool(tool) for tool in tools]

        try:
            response = self.http_client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LlmError("LLM provider timed out") from exc
        except httpx.HTTPError as exc:
            raise LlmError("LLM provider request failed") from exc

        return parse_completion(response.json())
