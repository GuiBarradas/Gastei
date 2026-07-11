"""Integration: ``ChatService`` against a real database (SQLite tmpfile via fixture)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from gastei.agents.insight_agent import InsightAgent
from gastei.agents.tools import AgentTool
from gastei.models.chat import Conversation, Message
from gastei.schemas.llm import LLMResponse, LLMToolUse
from gastei.services.chat_service import ChatService
from tests.fakes import FakeLLMClient

pytestmark = pytest.mark.integration


def _add_tool() -> AgentTool:
    async def add(a: int, b: int) -> str:
        return str(a + b)

    return AgentTool(
        name="add",
        description="Soma",
        input_schema={
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
        fn=add,
    )


def _make_agent(*responses: LLMResponse) -> tuple[InsightAgent, FakeLLMClient]:
    fake = FakeLLMClient(responses=list(responses))
    agent = InsightAgent(llm=fake, tools=[_add_tool()], model="claude-opus-4-7")
    return agent, fake


async def test_chat_creates_conversation_and_persists_messages(db_session: Session) -> None:
    agent, _fake = _make_agent(
        LLMResponse(stop_reason="end_turn", text="oi de volta", tokens_input=10, tokens_output=5),
    )
    service = ChatService(agent=agent, session=db_session)

    response = await service.chat("oi")

    assert response.answer == "oi de volta"
    assert response.iterations == 1
    assert response.conversation_id > 0

    # Persistência
    convs = db_session.scalars(select(Conversation)).all()
    assert len(convs) == 1
    msgs = db_session.scalars(select(Message).where(Message.conversation_id == convs[0].id)).all()
    roles = [m.role for m in msgs]
    assert roles == ["user", "assistant"]
    assert msgs[0].content == "oi"
    assert msgs[1].content == "oi de volta"
    assert msgs[1].tokens_input == 10
    assert msgs[1].tokens_output == 5


async def test_chat_continues_existing_conversation(db_session: Session) -> None:
    agent1, _ = _make_agent(LLMResponse(stop_reason="end_turn", text="r1"))
    response1 = await ChatService(agent=agent1, session=db_session).chat("q1")

    agent2, _ = _make_agent(LLMResponse(stop_reason="end_turn", text="r2"))
    response2 = await ChatService(agent=agent2, session=db_session).chat(
        "q2", conversation_id=response1.conversation_id
    )

    assert response2.conversation_id == response1.conversation_id

    msgs = db_session.scalars(
        select(Message)
        .where(Message.conversation_id == response1.conversation_id)
        .order_by(Message.id)
    ).all()
    assert [m.role for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert [m.content for m in msgs] == ["q1", "r1", "q2", "r2"]


async def test_chat_with_invalid_conversation_id_raises(db_session: Session) -> None:
    agent, _ = _make_agent(LLMResponse(stop_reason="end_turn", text="x"))
    service = ChatService(agent=agent, session=db_session)
    with pytest.raises(KeyError):
        await service.chat("oi", conversation_id=9999)


async def test_chat_persists_tool_calls(db_session: Session) -> None:
    agent, _ = _make_agent(
        LLMResponse(
            stop_reason="tool_use",
            tool_uses=[LLMToolUse(id="tu_1", name="add", input={"a": 2, "b": 3})],
            raw_content=[
                {"type": "tool_use", "id": "tu_1", "name": "add", "input": {"a": 2, "b": 3}}
            ],
        ),
        LLMResponse(stop_reason="end_turn", text="2+3=5"),
    )
    service = ChatService(agent=agent, session=db_session)

    response = await service.chat("quanto é 2+3?")

    assert response.answer == "2+3=5"
    assert len(response.tool_calls) == 1
    tc = response.tool_calls[0]
    assert tc.name == "add"
    assert tc.input == {"a": 2, "b": 3}
    assert tc.output == "5"
    assert tc.is_error is False

    # Persistência inclui tool message
    msgs = db_session.scalars(
        select(Message)
        .where(Message.conversation_id == response.conversation_id)
        .order_by(Message.id)
    ).all()
    roles = [m.role for m in msgs]
    assert roles == ["user", "tool", "assistant"]
