"""DTOs for the ``LLMClient`` port.

The shape is intentionally minimal and stable. Provider-specific quirks
(Anthropic vs. Gemini response shapes, SDK version drift) are encapsulated
inside the concrete adapters in ``gastei.clients``.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

StopReason = Literal["end_turn", "tool_use", "max_tokens", "stop_sequence"]


class LLMToolUse(BaseModel):
    id: str
    name: str
    input: dict[str, Any]


class LLMResponse(BaseModel):
    """Provider-neutral LLM response."""

    text: str = ""
    stop_reason: StopReason
    tool_uses: list[LLMToolUse] = Field(default_factory=list)
    raw_content: list[dict[str, Any]] = Field(default_factory=list)
    tokens_input: int = 0
    tokens_output: int = 0
