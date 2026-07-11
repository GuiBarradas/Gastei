"""FakeLLMClient — scriptable response queue for testing agents."""

from __future__ import annotations

from collections import deque
from typing import Any

from gastei.schemas.llm import LLMResponse


class FakeLLMClient:
    """Implements ``gastei.domain.ports.LLMClient``.

    Typical test usage::

        llm = FakeLLMClient(responses=[
            LLMResponse(stop_reason="tool_use", tool_uses=[...]),
            LLMResponse(stop_reason="end_turn", text="final answer"),
        ])

    ``calls`` records every call (model, system, messages, tools, max_tokens)
    so assertions like "the agent invoked tool X with args Y" are easy to write.
    """

    def __init__(self, responses: list[LLMResponse] | None = None) -> None:
        self._responses: deque[LLMResponse] = deque(responses or [])
        self.calls: list[dict[str, Any]] = []

    def queue(self, response: LLMResponse) -> None:
        self._responses.append(response)

    async def messages_create(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        self.calls.append(
            {
                "model": model,
                "system": system,
                "messages": list(messages),
                "tools": list(tools) if tools else None,
                "max_tokens": max_tokens,
            }
        )
        if not self._responses:
            raise AssertionError(
                "FakeLLMClient has no queued responses — script the test via .queue() or the constructor."
            )
        return self._responses.popleft()
