"""Gastei — Streamlit entry point (router).

Run with::

    uv run streamlit run streamlit_app/app.py

Prerequisite: the FastAPI backend must be running
(``uv run uvicorn gastei.api.main:app --reload``).

Uses the MPA-v2 API (``st.navigation`` + ``st.Page``): Material icons in the
sidebar, clean URLs, and this file runs before every page — so the shared CSS
and the backend health check live here.

User-facing strings stay in Portuguese (Brazilian audience).
"""

from __future__ import annotations

import streamlit as st
from components import ui
from components.api_client import get_api_client

st.set_page_config(
    page_title="Gastei — A planilha do século XXI",
    page_icon=":material/savings:",
    layout="wide",
)
ui.inject_css()

api = get_api_client()

# Backend health check — every page depends on the API, so gate here.
with st.sidebar:
    try:
        api.health()
        st.caption(f":material/check_circle: API online · `{api.base_url}`")
    except Exception as exc:
        st.error(f"API offline: {exc}", icon=":material/error:")
        st.stop()

pages = [
    st.Page("views/home.py", title="Início", icon=":material/home:", default=True),
    st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:"),
    st.Page("views/transacoes.py", title="Transações", icon=":material/receipt_long:"),
    st.Page("views/chat.py", title="Chat", icon=":material/forum:"),
    st.Page("views/conexoes.py", title="Conexões", icon=":material/account_balance:"),
]

st.navigation(pages).run()
