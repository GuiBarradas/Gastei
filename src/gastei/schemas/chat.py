"""DTOs for the ``/chat`` endpoint."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: int | None = None


class ToolCallSummary(BaseModel):
    name: str
    input: dict[str, Any]
    output: str
    is_error: bool = False


class ChatResponse(BaseModel):
    conversation_id: int
    answer: str
    tool_calls: list[ToolCallSummary] = []
    iterations: int
    tokens_input: int = 0
    tokens_output: int = 0


class MessageOut(BaseModel):
    """Persisted chat message — returned by ``GET /chat/conversations/{id}/messages``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    tokens_input: int | None = None
    tokens_output: int | None = None
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
