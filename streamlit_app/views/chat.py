"""Chat with the Gastei agent — uses tool-use under the hood (ARCHITECTURE.md §7.3).

History is persisted in the database (``conversations`` + ``messages`` tables).
The sidebar lists every conversation; clicking one loads it. The "Nova conversa"
button starts a fresh one.

User-visible strings stay in Portuguese.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import components.ui as ui
from components.api_client import get_api_client

ui.page_header(
    "Pergunte ao Gastei",
    "Pergunte sobre seus gastos. O agente consulta seus dados via tools.",
)

api = get_api_client()

ASSISTANT_AVATAR = ":material/savings:"


def _md(text: str) -> str:
    # "R$ 10 ... R$ 20" pairs the dollars as LaTeX delimiters in st.markdown.
    return text.replace("$", r"\$")


# ---------- Estado ----------
if "chat_conversation_id" not in st.session_state:
    st.session_state.chat_conversation_id = None


def _load_messages_from_db(conversation_id: int) -> list[dict]:
    """Hidrata as mensagens da conversa do DB pro formato do st.chat_message."""
    raw = api.list_messages(conversation_id)
    out: list[dict] = []
    for m in raw:
        role = m["role"]
        if role == "user":
            out.append({"role": "user", "content": m["content"]})
        elif role == "assistant":
            out.append({"role": "assistant", "content": m["content"], "tool_calls": []})
        elif role == "tool":
            # Tool result foi serializado como JSON pelo ChatService
            try:
                tc = json.loads(m["content"])
            except (json.JSONDecodeError, TypeError):
                tc = {"name": "?", "input": {}, "output": m["content"]}
            if out and out[-1]["role"] == "assistant":
                out[-1]["tool_calls"].append(tc)
            else:
                # Tool result órfão: cria mini-bloco
                out.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [tc],
                    }
                )
    return out


# ---------- Sidebar: lista de conversas ----------
with st.sidebar:
    st.subheader("Conversas")
    if st.button("Nova conversa", icon=":material/add:", width="stretch"):
        st.session_state.chat_conversation_id = None
        st.rerun()

    try:
        conversations = api.list_conversations()
    except Exception as exc:
        conversations = []
        st.caption(f"Falhou listar: {exc}")

    if conversations:
        st.divider()
        for conv in conversations:
            cid = conv["id"]
            is_active = st.session_state.chat_conversation_id == cid
            if st.button(
                f"#{cid} · {conv['started_at'][:10]}",
                key=f"conv-{cid}",
                icon=":material/chat_bubble:",
                width="stretch",
                type="primary" if is_active else "secondary",
            ):
                st.session_state.chat_conversation_id = cid
                st.rerun()


def _render_tool_call(tc: dict) -> None:
    with st.expander(tc.get("name", "?"), icon=":material/build:", expanded=False):
        st.json(tc.get("input", {}))
        output = tc.get("output", "")
        if output:
            st.code(output, language="text")


# ---------- Render histórico (sempre do DB) ----------
messages_for_display: list[dict] = []
if st.session_state.chat_conversation_id is not None:
    try:
        messages_for_display = _load_messages_from_db(st.session_state.chat_conversation_id)
    except Exception as exc:
        st.error(f"Falhou carregar conversa: {exc}", icon=":material/error:")

for msg in messages_for_display:
    avatar = ASSISTANT_AVATAR if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        if msg["content"]:
            st.markdown(_md(msg["content"]))
        for tc in msg.get("tool_calls", []):
            _render_tool_call(tc)


# ---------- Input ----------
prompt = st.chat_input("Ex: quanto gastei com delivery em abril?")
if prompt:
    with st.chat_message("user"):
        st.markdown(_md(prompt))

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        with st.spinner("Pensando..."):
            try:
                response = api.chat(
                    message=prompt,
                    conversation_id=st.session_state.chat_conversation_id,
                )
            except Exception as exc:
                st.error(f"Falha no chat: {exc}", icon=":material/error:")
                st.stop()

        st.session_state.chat_conversation_id = response["conversation_id"]
        st.markdown(_md(response["answer"]))
        for tc in response.get("tool_calls", []) or []:
            _render_tool_call(tc)

        st.caption(
            f"{response['iterations']} iteração(ões) · "
            f"in {response.get('tokens_input', 0)} / out {response.get('tokens_output', 0)} tokens"
        )

    # Refresh pra puxar do DB e atualizar a sidebar
    st.rerun()
