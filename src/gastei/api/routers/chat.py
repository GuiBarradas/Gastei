"""``POST /chat`` — talk to the InsightAgent."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from gastei.agents.insight_agent import AgentTimeoutError
from gastei.api.deps import get_chat_service, get_db_session
from gastei.domain.ports import LLMUnavailableError
from gastei.models.chat import Conversation, Message
from gastei.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationOut,
    MessageOut,
)
from gastei.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: ChatService | None = Depends(get_chat_service),
) -> ChatResponse:
    if service is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Chat unavailable: set LLM_PROVIDER=anthropic with "
                "ANTHROPIC_API_KEY or LLM_PROVIDER=gemini with GOOGLE_API_KEY in .env."
            ),
        )
    try:
        return await service.chat(
            user_message=payload.message,
            conversation_id=payload.conversation_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM provider temporarily unavailable — try again shortly. ({exc})",
        ) from exc


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    session: Session = Depends(get_db_session),
) -> list[ConversationOut]:
    rows = session.scalars(select(Conversation).order_by(Conversation.started_at.desc())).all()
    return [ConversationOut.model_validate(c) for c in rows]


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
)
def list_messages(
    conversation_id: int,
    session: Session = Depends(get_db_session),
) -> list[MessageOut]:
    if session.get(Conversation, conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = session.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
    ).all()
    return [MessageOut.model_validate(m) for m in rows]
