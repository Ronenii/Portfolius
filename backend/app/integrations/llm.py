from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.core.config import Settings

INLINE_FUNCTION_CALL_RE = re.compile(
    r"<function=([^>\s]+)\s*>(.*?)</function>",
    re.DOTALL,
)


class LlmError(RuntimeError):
    pass


class LlmRateLimitError(LlmError):
    """Raised when the provider rate-limits us and retries are exhausted.

    Distinct from LlmError so callers can show a "try again in a minute" notice
    instead of treating it as a hard failure (Groq's free tier caps tokens per
    minute, and each assistant turn makes several calls).
    """


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
    finish_reason: str | None = None


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


def parse_inline_tool_calls(content: str) -> tuple[list[ToolCall], str]:
    """Recover tool calls some models emit as inline ``<function=...>`` text.

    Certain Groq-hosted models (e.g. Llama) sometimes write tool calls into the
    reply ``content`` instead of the structured ``tool_calls`` field. Without
    this fallback those calls are silently treated as a final answer and never
    executed, so the model narrates an outcome that never happened.

    Returns the recovered calls and the content with the markup removed.
    """
    tool_calls: list[ToolCall] = []
    for index, match in enumerate(INLINE_FUNCTION_CALL_RE.finditer(content)):
        name = match.group(1).strip()
        if not name:
            continue
        raw_arguments = match.group(2).strip()
        try:
            arguments = parse_arguments(raw_arguments)
        except LlmError:
            arguments = {}
        tool_calls.append(
            ToolCall(
                id=f"inline-call-{index}",
                name=name,
                arguments=arguments,
            )
        )
    cleaned_content = INLINE_FUNCTION_CALL_RE.sub(" ", content).strip()
    return tool_calls, cleaned_content


def parse_completion(payload: object) -> ChatCompletion:
    if not isinstance(payload, dict):
        raise LlmError("LLM provider returned an invalid response")

    raw_choices = payload.get("choices")
    if not isinstance(raw_choices, list) or not raw_choices:
        raise LlmError("LLM provider returned no choices")

    raw_choice = raw_choices[0]
    finish_reason = raw_choice.get("finish_reason")
    if not isinstance(finish_reason, str):
        finish_reason = None

    raw_message = raw_choice.get("message")
    if not isinstance(raw_message, dict):
        raise LlmError("LLM provider returned no assistant message")

    role = raw_message.get("role")
    content = raw_message.get("content")
    if not isinstance(role, str):
        raise LlmError("LLM provider returned a message without a role")
    if content is not None and not isinstance(content, str):
        raise LlmError("LLM provider returned invalid message content")

    tool_calls = parse_tool_calls(raw_message.get("tool_calls"))
    if not tool_calls and content:
        inline_calls, cleaned_content = parse_inline_tool_calls(content)
        if inline_calls:
            tool_calls = inline_calls
            content = cleaned_content

    return ChatCompletion(
        message=ChatMessage(role=role, content=content, tool_calls=tool_calls),
        tool_calls=tool_calls,
        finish_reason=finish_reason,
    )


class GroqLlmClient:
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2.0  # seconds; doubles each attempt

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.groq.com/openai/v1",
        http_client: httpx.Client | None = None,
        max_tokens: int = 1024,
        model: str = "llama-3.3-70b-versatile",
        reasoning_effort: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=20.0)
        self.max_tokens = max_tokens
        self.model = model
        self.reasoning_effort = reasoning_effort

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
            reasoning_effort=settings.llm_reasoning_effort,
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
        if self.reasoning_effort is not None:
            body["reasoning_effort"] = self.reasoning_effort
        if tools is not None:
            body["tools"] = [serialize_tool(tool) for tool in tools]

        last_exc: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.http_client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=body,
                )
                if response.status_code == 429:
                    retry_after = float(
                        response.headers.get(
                            "retry-after", self.RETRY_BASE_DELAY * (2**attempt)
                        )
                    )
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(retry_after)
                        continue
                    raise LlmRateLimitError(
                        "LLM provider rate-limited; try again in a moment"
                    )
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise LlmError("LLM provider timed out") from exc
            except httpx.HTTPStatusError as exc:
                raise LlmError("LLM provider request failed") from exc
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_BASE_DELAY * (2**attempt))
                    continue
                raise LlmError("LLM provider request failed") from exc
            else:
                return parse_completion(response.json())

        raise LlmError("LLM provider request failed") from last_exc
