"""InsightAgent specs — TDD.

Covers the tool-use loop:

- Immediate ``end_turn`` → ``AgentResponse.text`` carries the response.
- ``tool_use`` → tool executes → next iteration.
- Multiple tool calls in one response → all executed (logically in parallel).
- Unknown tool → ``tool_result`` with ``is_error=True`` (the LLM can recover).
- ``max_iterations`` reached → ``AgentTimeoutError``.
- System prompt and model are correct in the request payload.
"""

from __future__ import annotations

import pytest

from gastei.agents.insight_agent import (
    AgentResponse,
    AgentTimeoutError,
    InsightAgent,
)
from gastei.agents.tools import AgentTool
from gastei.schemas.llm import LLMResponse, LLMToolUse
from tests.fakes import FakeLLMClient

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------------------
# Tools de teste — não tocam serviços reais
# --------------------------------------------------------------------------------------


def _echo_tool() -> AgentTool:
    async def echo(text: str = "hi") -> str:
        return f"echo: {text}"

    return AgentTool(
        name="echo",
        description="Echo de uma string",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
        },
        fn=echo,
    )


def _add_tool() -> AgentTool:
    async def add(a: int, b: int) -> str:
        return str(a + b)

    return AgentTool(
        name="add",
        description="Soma dois inteiros",
        input_schema={
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
        fn=add,
    )


# --------------------------------------------------------------------------------------
# Caminho mais simples
# --------------------------------------------------------------------------------------


async def test_end_turn_immediately_returns_text() -> None:
    fake = FakeLLMClient(
        responses=[
            LLMResponse(stop_reason="end_turn", text="resposta direta"),
        ]
    )
    agent = InsightAgent(llm=fake, tools=[_echo_tool()], model="claude-opus-4-7")

    result = await agent.run("oi")

    assert isinstance(result, AgentResponse)
    assert result.text == "resposta direta"
    assert result.iterations == 1


async def test_uses_correct_model_and_passes_tools() -> None:
    fake = FakeLLMClient(
        responses=[
            LLMResponse(stop_reason="end_turn", text="ok"),
        ]
    )
    agent = InsightAgent(llm=fake, tools=[_echo_tool(), _add_tool()], model="claude-opus-4-7")
    await agent.run("oi")

    call = fake.calls[0]
    assert call["model"] == "claude-opus-4-7"
    tool_names = {t["name"] for t in call["tools"]}
    assert tool_names == {"echo", "add"}
    # System prompt presente
    assert call["system"]
    # Pergunta do usuário no histórico
    assert any(m.get("role") == "user" for m in call["messages"])


# --------------------------------------------------------------------------------------
# Loop com 1 tool call
# --------------------------------------------------------------------------------------


async def test_tool_use_executes_then_continues_loop() -> None:
    fake = FakeLLMClient(
        responses=[
            LLMResponse(
                stop_reason="tool_use",
                tool_uses=[LLMToolUse(id="tu_1", name="add", input={"a": 2, "b": 3})],
                raw_content=[
                    {"type": "tool_use", "id": "tu_1", "name": "add", "input": {"a": 2, "b": 3}}
                ],
            ),
            LLMResponse(stop_reason="end_turn", text="O resultado é 5"),
        ]
    )
    agent = InsightAgent(llm=fake, tools=[_add_tool()], model="claude-opus-4-7")

    result = await agent.run("quanto é 2+3?")

    assert result.text == "O resultado é 5"
    assert result.iterations == 2

    # Segunda chamada deve ter recebido o tool_result na conversa
    second_call_messages = fake.calls[1]["messages"]
    last_msg = second_call_messages[-1]
    assert last_msg["role"] == "user"
    assert last_msg["content"][0]["type"] == "tool_result"
    assert last_msg["content"][0]["tool_use_id"] == "tu_1"
    assert "5" in last_msg["content"][0]["content"]


# --------------------------------------------------------------------------------------
# Múltiplas tools na mesma resposta
# --------------------------------------------------------------------------------------


async def test_multiple_tool_uses_in_one_response() -> None:
    fake = FakeLLMClient(
        responses=[
            LLMResponse(
                stop_reason="tool_use",
                tool_uses=[
                    LLMToolUse(id="tu_1", name="echo", input={"text": "alpha"}),
                    LLMToolUse(id="tu_2", name="add", input={"a": 10, "b": 20}),
                ],
                raw_content=[
                    {"type": "tool_use", "id": "tu_1", "name": "echo", "input": {"text": "alpha"}},
                    {"type": "tool_use", "id": "tu_2", "name": "add", "input": {"a": 10, "b": 20}},
                ],
            ),
            LLMResponse(stop_reason="end_turn", text="feito"),
        ]
    )
    agent = InsightAgent(llm=fake, tools=[_echo_tool(), _add_tool()], model="claude-opus-4-7")

    await agent.run("faz tudo")

    # Ambos os results aparecem na 2ª chamada
    second_msgs = fake.calls[1]["messages"]
    last = second_msgs[-1]
    contents_by_id = {b["tool_use_id"]: b["content"] for b in last["content"]}
    assert "alpha" in contents_by_id["tu_1"]
    assert contents_by_id["tu_2"] == "30"


# --------------------------------------------------------------------------------------
# Erros
# --------------------------------------------------------------------------------------


async def test_unknown_tool_is_reported_as_error_and_loop_continues() -> None:
    fake = FakeLLMClient(
        responses=[
            LLMResponse(
                stop_reason="tool_use",
                tool_uses=[LLMToolUse(id="tu_1", name="nao_existe", input={})],
                raw_content=[{"type": "tool_use", "id": "tu_1", "name": "nao_existe", "input": {}}],
            ),
            LLMResponse(stop_reason="end_turn", text="desisti"),
        ]
    )
    agent = InsightAgent(llm=fake, tools=[_echo_tool()], model="claude-opus-4-7")

    result = await agent.run("?")

    assert result.iterations == 2
    last_msg = fake.calls[1]["messages"][-1]
    block = last_msg["content"][0]
    assert block["type"] == "tool_result"
    assert block.get("is_error") is True
    assert "nao_existe" in block["content"]


async def test_tool_raising_exception_reported_as_error() -> None:
    async def explode() -> str:
        raise RuntimeError("kaboom")

    bad = AgentTool(
        name="explode",
        description="x",
        input_schema={"type": "object", "properties": {}},
        fn=explode,
    )

    fake = FakeLLMClient(
        responses=[
            LLMResponse(
                stop_reason="tool_use",
                tool_uses=[LLMToolUse(id="tu_1", name="explode", input={})],
                raw_content=[{"type": "tool_use", "id": "tu_1", "name": "explode", "input": {}}],
            ),
            LLMResponse(stop_reason="end_turn", text="ok"),
        ]
    )
    agent = InsightAgent(llm=fake, tools=[bad], model="claude-opus-4-7")

    await agent.run("?")
    block = fake.calls[1]["messages"][-1]["content"][0]
    assert block["is_error"] is True
    assert "kaboom" in block["content"]


async def test_max_iterations_exceeded_raises_timeout() -> None:
    """Agent loops indefinidamente em tool_use e nunca termina → AgentTimeoutError."""
    looping_response = LLMResponse(
        stop_reason="tool_use",
        tool_uses=[LLMToolUse(id="tu_x", name="echo", input={"text": "again"})],
        raw_content=[
            {"type": "tool_use", "id": "tu_x", "name": "echo", "input": {"text": "again"}}
        ],
    )
    fake = FakeLLMClient(responses=[looping_response] * 10)
    agent = InsightAgent(llm=fake, tools=[_echo_tool()], model="claude-opus-4-7", max_iterations=3)

    with pytest.raises(AgentTimeoutError):
        await agent.run("?")

    assert len(fake.calls) == 3
