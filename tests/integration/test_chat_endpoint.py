"""End-to-end integration of the ``/chat`` endpoint with a fake LLM."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from gastei.agents.insight_agent import InsightAgent
from gastei.agents.tools import AgentTool
from gastei.api.deps import get_chat_service, get_db_session, get_insight_agent
from gastei.api.main import create_app
from gastei.schemas.llm import LLMResponse, LLMToolUse
from gastei.services.chat_service import ChatService
from tests.fakes import FakeLLMClient

pytestmark = pytest.mark.integration


def _build_agent_with_responses(responses: list[LLMResponse]) -> InsightAgent:
    fake = FakeLLMClient(responses=responses)

    async def _passthrough() -> str:
        return "ok"

    tool = AgentTool(
        name="noop",
        description="x",
        input_schema={"type": "object", "properties": {}},
        fn=_passthrough,
    )
    return InsightAgent(llm=fake, tools=[tool], model="claude-opus-4-7")


@pytest.fixture
def client_with_chat(db_session: Session, request) -> Iterator[TestClient]:
    """Client que injeta um agente fake. Use indirect param pra customizar respostas."""
    responses: list[LLMResponse] = getattr(
        request,
        "param",
        [
            LLMResponse(stop_reason="end_turn", text="resposta padrão"),
        ],
    )

    app = create_app()

    def _override_db() -> Iterator[Session]:
        yield db_session

    def _override_chat_service() -> ChatService:
        agent = _build_agent_with_responses(responses)
        return ChatService(agent=agent, session=db_session)

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_chat_service] = _override_chat_service

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_no_llm(db_session: Session) -> Iterator[TestClient]:
    """Client onde o agente vem como None (LLM não configurado)."""
    app = create_app()

    def _override_db() -> Iterator[Session]:
        yield db_session

    def _override_agent() -> None:
        return None

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_insight_agent] = _override_agent

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------------------
# Caminho feliz
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "client_with_chat",
    [[LLMResponse(stop_reason="end_turn", text="oi de volta")]],
    indirect=True,
)
def test_post_chat_returns_answer_and_creates_conversation(
    client_with_chat: TestClient,
) -> None:
    r = client_with_chat.post("/chat", json={"message": "oi"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"] == "oi de volta"
    assert body["conversation_id"] > 0
    assert body["iterations"] == 1
    assert body["tool_calls"] == []


@pytest.mark.parametrize(
    "client_with_chat",
    [
        [
            LLMResponse(
                stop_reason="tool_use",
                tool_uses=[LLMToolUse(id="tu_1", name="noop", input={})],
                raw_content=[{"type": "tool_use", "id": "tu_1", "name": "noop", "input": {}}],
            ),
            LLMResponse(stop_reason="end_turn", text="terminei"),
        ]
    ],
    indirect=True,
)
def test_chat_response_includes_tool_calls(client_with_chat: TestClient) -> None:
    r = client_with_chat.post("/chat", json={"message": "faça o noop"})
    body = r.json()
    assert body["answer"] == "terminei"
    assert body["iterations"] == 2
    assert len(body["tool_calls"]) == 1
    assert body["tool_calls"][0]["name"] == "noop"
    assert body["tool_calls"][0]["output"] == "ok"


# --------------------------------------------------------------------------------------
# GET conversations / messages
# --------------------------------------------------------------------------------------


def test_list_messages_after_chat(client_with_chat: TestClient) -> None:
    chat_response = client_with_chat.post("/chat", json={"message": "oi"}).json()
    conv_id = chat_response["conversation_id"]

    r = client_with_chat.get(f"/chat/conversations/{conv_id}/messages")
    assert r.status_code == 200
    msgs = r.json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "oi"


def test_list_messages_404_on_missing_conversation(
    client_with_chat: TestClient,
) -> None:
    r = client_with_chat.get("/chat/conversations/99999/messages")
    assert r.status_code == 404


def test_list_conversations_includes_created(client_with_chat: TestClient) -> None:
    client_with_chat.post("/chat", json={"message": "oi"})
    r = client_with_chat.get("/chat/conversations")
    assert r.status_code == 200
    assert len(r.json()) >= 1


# --------------------------------------------------------------------------------------
# Sem LLM configurado → 503
# --------------------------------------------------------------------------------------


def test_chat_returns_503_when_llm_not_configured(client_no_llm: TestClient) -> None:
    r = client_no_llm.post("/chat", json={"message": "oi"})
    assert r.status_code == 503
    assert "LLM_PROVIDER" in r.json()["detail"]


# --------------------------------------------------------------------------------------
# Provider fora do ar → 503 amigável, não 500
# --------------------------------------------------------------------------------------


@pytest.fixture
def client_llm_down(db_session: Session) -> Iterator[TestClient]:
    from gastei.domain.ports import LLMUnavailableError

    class DownLLM:
        async def messages_create(self, **kwargs):
            raise LLMUnavailableError("Gemini: 503 UNAVAILABLE")

    app = create_app()

    def _override_db() -> Iterator[Session]:
        yield db_session

    def _override_chat_service() -> ChatService:
        agent = InsightAgent(llm=DownLLM(), tools=[], model="x")
        return ChatService(agent=agent, session=db_session)

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_chat_service] = _override_chat_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_chat_returns_503_when_provider_is_down(client_llm_down: TestClient) -> None:
    r = client_llm_down.post("/chat", json={"message": "oi"})
    assert r.status_code == 503
    assert "temporarily unavailable" in r.json()["detail"]
