"""Landing view — quick summary and navigation hints. Strings in pt-BR."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import components.ui as ui
from components.api_client import get_api_client

ui.page_header("Gastei", "Assistente financeiro pessoal com IA")

api = get_api_client()
items = api.list_items()
accounts = api.list_accounts()
total_balance = sum(a["balance"] for a in accounts)

col1, col2, col3 = st.columns(3)
col1.metric("Conexões bancárias", len(items))
col2.metric("Contas", len(accounts))
col3.metric("Saldo total", ui.fmt_brl(total_balance))

st.divider()

f1, f2, f3, f4 = st.columns(4)
with f1:
    st.markdown(":material/dashboard: **Dashboard**")
    st.caption("Saldos por banco, gastos por categoria e evolução mensal.")
with f2:
    st.markdown(":material/receipt_long: **Transações**")
    st.caption("Liste, filtre e recategorize com um clique.")
with f3:
    st.markdown(":material/forum: **Chat**")
    st.caption("Pergunte em linguagem natural: “quanto gastei com delivery em abril?”")
with f4:
    st.markdown(":material/account_balance: **Conexões**")
    st.caption("Importe OFX, sincronize Open Finance e gerencie contas.")

if not accounts:
    st.info(
        "Vá em **Conexões** e importe um extrato OFX pra começar.",
        icon=":material/upload_file:",
    )
