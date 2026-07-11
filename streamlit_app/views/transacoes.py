"""Transactions — list, filter, recategorize inline. User-visible strings in pt-BR."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import components.ui as ui
from components.api_client import get_api_client

ui.page_header("Transações", "Liste, filtre e recategorize suas transações.")

api = get_api_client()
items = api.list_items()
accounts = api.list_accounts()

if not items:
    st.info("Importe um extrato em **Conexões** primeiro.", icon=":material/upload_file:")
    st.stop()

# ---------- Taxonomia (labels humanos pros dropdowns) ----------
categories = api.list_categories()
_by_code = {c["code"]: c for c in categories}


def cat_display(code: str | None) -> str:
    # Uncategorized rows arrive as None (or NaN once inside a DataFrame).
    if not isinstance(code, str) or not code:
        return "—"
    c = _by_code.get(code)
    if c is None:
        return ui.category_label(code)
    parent = _by_code.get(c["parent_code"] or "")
    return f"{parent['label']} · {c['label']}" if parent else c["label"]


# Só folhas são atribuíveis (códigos com ponto, ex: alimentacao.delivery).
leaf_codes = sorted(c["code"] for c in categories if "." in c["code"])

SOURCE_LABELS = {"rule": "Regra", "llm": "LLM", "user": "Manual", "pluggy": "Pluggy"}

# ---------- Recategorizar pendentes (header) ----------
with st.container(border=True):
    cols = st.columns([4, 1])
    with cols[0]:
        st.markdown(
            "**Categorização automática** — roda regras + LLM nas transações "
            "ainda sem categoria. Útil depois de importar OFX."
        )
        st.caption(
            "Sem chave de LLM no `.env`, só regras (cobertura ~60%). "
            "Com Gemini configurado, o LLM completa o resto. "
            "Correções manuais viram few-shot pro próximo run."
        )
    with cols[1]:
        if st.button(
            "Recategorizar pendentes",
            type="primary",
            icon=":material/smart_toy:",
            width="stretch",
        ):
            with st.spinner("Categorizando..."):
                try:
                    result = api.recategorize_pending(limit=500)
                except Exception as exc:
                    st.error(f"Falhou: {exc}", icon=":material/error:")
                    st.stop()
            st.success(
                f"{result['categorized']}/{result['candidates']} categorizadas "
                f"({result['skipped']} pendentes).",
                icon=":material/check_circle:",
            )
            if result["skipped"]:
                st.caption(
                    "Se o LLM estiver indisponível (free tier), o app segue só com "
                    "regras e as demais ficam pra depois — rode de novo mais tarde."
                )
            st.rerun()

st.divider()

# ---------- Filtros bank-first ----------
filt_l, filt_m, filt_r1, filt_r2 = st.columns([2, 2, 1, 1])
with filt_l:
    item_options = {"Todos os bancos": None} | {
        item["institution_name"]: item["id"] for item in items
    }
    bank_label = st.selectbox("Banco", list(item_options.keys()))
    selected_item_id = item_options[bank_label]

with filt_m:
    if selected_item_id is None:
        relevant_accounts = accounts
    else:
        relevant_accounts = [a for a in accounts if a["item_id"] == selected_item_id]
    account_options = {"Todas do banco": None} | {
        f"{a['name']}": a["id"] for a in relevant_accounts
    }
    account_label = st.selectbox("Conta", list(account_options.keys()))
    selected_account_id = account_options[account_label]

today = date.today()
with filt_r1:
    start = st.date_input("De", value=today - timedelta(days=365))
with filt_r2:
    end = st.date_input("Até", value=today)

c3, c4 = st.columns(2)
with c3:
    category = st.selectbox(
        "Categoria",
        options=[None, *leaf_codes],
        format_func=lambda c: "Todas as categorias" if c is None else cat_display(c),
    )
with c4:
    search = st.text_input("Buscar na descrição", value="")

# Helper: passa item_id OU account_id
qk: dict = {}
if selected_account_id:
    qk["account_id"] = selected_account_id
elif selected_item_id:
    qk["item_id"] = selected_item_id

txs = api.list_transactions(
    start=start,
    end=end,
    category=category,
    search=search.strip() or None,
    limit=1000,
    **qk,
)

if not txs:
    st.warning("Nenhuma transação no filtro.", icon=":material/search_off:")
    st.stop()

st.caption(f"Mostrando {len(txs)} transação(ões).")

df = pd.DataFrame(txs)[["date", "description", "amount", "category", "category_source", "id"]]
df.columns = ["Data", "Descrição", "Valor", "Categoria", "Fonte", "ID"]
df["Data"] = pd.to_datetime(df["Data"]).dt.date
df["Categoria"] = df["Categoria"].map(cat_display)
df["Fonte"] = df["Fonte"].map(lambda s: SOURCE_LABELS.get(s, "—"))

st.dataframe(
    df.drop(columns=["ID"]),
    column_config={
        "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", width="small"),
        "Descrição": st.column_config.TextColumn("Descrição", width="large"),
        "Valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f", width="small"),
        "Categoria": st.column_config.TextColumn("Categoria"),
        "Fonte": st.column_config.TextColumn("Fonte", width="small"),
    },
    width="stretch",
    hide_index=True,
)

# ---------- Recategorização manual ----------
st.divider()
st.subheader("Recategorizar manualmente")

edit_left, edit_right = st.columns(2)
with edit_left:
    selected_id = st.selectbox(
        "Transação",
        options=df["ID"].tolist(),
        format_func=lambda tid: next(
            f"{t['date']} • {t['description'][:40]} • R$ {t['amount']:.2f}"
            for t in txs
            if t["id"] == tid
        ),
    )
with edit_right:
    new_category = st.selectbox(
        "Nova categoria",
        options=leaf_codes,
        format_func=cat_display,
        index=None,
        placeholder="Escolha a categoria...",
    )

if st.button(
    "Aplicar",
    type="primary",
    icon=":material/check:",
    disabled=new_category is None,
):
    try:
        api.update_category(selected_id, new_category)
        st.success(
            f"Categoria atualizada pra **{cat_display(new_category)}**.",
            icon=":material/check_circle:",
        )
        st.rerun()
    except Exception as exc:
        st.error(f"Falhou: {exc}", icon=":material/error:")
