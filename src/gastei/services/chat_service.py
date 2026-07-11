"""ChatService — wraps the ``InsightAgent`` and persists ``Conversation`` / ``Message`` rows.

MVP strategy: each agent call is independent. We do not feed conversation
history back into the LLM (the bookkeeping for re-emitting ``tool_use`` /
``tool_result`` blocks across turns is non-trivial). The UI surfaces history
through a separate read endpoint.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from gastei.agents.insight_agent import InsightAgent
from gastei.models.chat import Conversation, Message
from gastei.schemas.chat import ChatResponse, ToolCallSummary


class ChatService:
    def __init__(self, agent: InsightAgent, session: Session) -> None:
        self._agent = agent
        self._session = session

    async def chat(self, user_message: str, conversation_id: int | None = None) -> ChatResponse:
        conv = self._get_or_create_conversation(conversation_id)

        # Persist the user message before running the agent — if the agent
        # raises, we still have the input recorded.
        self._session.add(
            Message(
                conversation_id=conv.id,
                role="user",
                content=user_message,
            )
        )
        self._session.flush()

        agent_response = await self._agent.run(user_message)

        tool_calls = self._extract_tool_calls(agent_response.messages)

        # Persist each tool call as a ``role='tool'`` message for audit purposes.
        for tc in tool_calls:
            self._session.add(
                Message(
                    conversation_id=conv.id,
                    role="tool",
                    content=json.dumps(tc.model_dump(), ensure_ascii=False),
                )
            )

        # Persist the final assistant reply.
        self._session.add(
            Message(
                conversation_id=conv.id,
                role="assistant",
                content=agent_response.text,
                tokens_input=agent_response.tokens_input,
                tokens_output=agent_response.tokens_output,
            )
        )
        self._session.commit()

        return ChatResponse(
            conversation_id=conv.id,
            answer=agent_response.text,
            tool_calls=tool_calls,
            iterations=agent_response.iterations,
            tokens_input=agent_response.tokens_input,
            tokens_output=agent_response.tokens_output,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_create_conversation(self, conversation_id: int | None) -> Conversation:
        if conversation_id is not None:
            conv = self._session.get(Conversation, conversation_id)
            if conv is None:
                raise KeyError(f"Conversation {conversation_id} does not exist")
            return conv
        conv = Conversation()
        self._session.add(conv)
        self._session.flush()  # populates conv.id
        return conv

    @staticmethod
    def _extract_tool_calls(messages: list[dict[str, Any]]) -> list[ToolCallSummary]:
        """Pair ``tool_use`` blocks (assistant) with ``tool_result`` blocks (user)."""
        # Map tool_use_id → (name, input)
        uses: dict[str, dict[str, Any]] = {}
        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    uses[block["id"]] = {
                        "name": block.get("name", ""),
                        "input": block.get("input", {}),
                    }

        # Find the matching tool_result blocks.
        results: list[ToolCallSummary] = []
        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                tu_id = block.get("tool_use_id")
                meta = uses.get(tu_id, {})
                results.append(
                    ToolCallSummary(
                        name=meta.get("name", "?"),
                        input=meta.get("input", {}),
                        output=str(block.get("content", "")),
                        is_error=bool(block.get("is_error", False)),
                    )
                )
        return results
