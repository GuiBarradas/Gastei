"""AnthropicLLMClient — adapter over the official Anthropic SDK.

Implements the ``LLMClient`` port by mapping onto ``anthropic.AsyncAnthropic``.
Applies prompt caching on the system block (no-op when the prefix is below
the model's minimum-cacheable size) and translates the SDK's ``Message`` into
the provider-neutral ``LLMResponse`` shape.

When making changes here, double-check against the Anthropic SDK release notes:
the exact shape of message content blocks can shift across SDK versions.
"""

from __future__ import annotations

from typing import Any

import anthropic

from gastei.config import get_settings
from gastei.schemas.llm import LLMResponse, LLMToolUse


class AnthropicLLMClient:
    """Async adapter over ``anthropic.AsyncAnthropic``."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or get_settings().anthropic_api_key or None
        )

    async def messages_create(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        # System content wrapped as a single cacheable block. Anthropic's
        # minimum cacheable prefix is 4096 tokens for Haiku 4.5 / Opus 4.x;
        # below that the cache_control flag is a silent no-op.
        system_blocks = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_blocks,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self._client.messages.create(**kwargs)
        return self._translate(response)

    @staticmethod
    def _translate(response: anthropic.types.Message) -> LLMResponse:
        text_parts: list[str] = []
        tool_uses: list[LLMToolUse] = []
        raw_content: list[dict[str, Any]] = []

        for block in response.content:
            raw_content.append(block.model_dump())
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(LLMToolUse(id=block.id, name=block.name, input=dict(block.input)))

        return LLMResponse(
            text="".join(text_parts),
            stop_reason=response.stop_reason or "end_turn",
            tool_uses=tool_uses,
            raw_content=raw_content,
            tokens_input=getattr(response.usage, "input_tokens", 0),
            tokens_output=getattr(response.usage, "output_tokens", 0),
        )
