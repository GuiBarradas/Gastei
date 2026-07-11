"""Connections — list items / accounts and import OFX statements.

User-visible strings stay in Portuguese (Brazilian audience).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import components.ui as ui
from components.api_client import get_api_client

ui.page_header("Conexões", "Importe extratos, sincronize bancos e gerencie contas.")

api = get_api_client()

# ---------- Sincronização Pluggy ----------
with st.container(border=True):
    cols = st.columns([4, 1])
    with cols[0]:
        st.markdown(
            "**Open Finance (Pluggy)** — puxa items, contas e transações "
            "de bancos já conectados via Connect Widget."
        )
        st.caption(
            "Pra conectar um banco novo, use o dashboard.pluggy.ai. "
            "Na Fase 4 isso vai ter widget aqui dentro."
        )
    with cols[1]:
        if st.button(
            "Sincronizar agora",
            type="primary",
            icon=":material/sync:",
            width="stretch",
        ):
            with st.spinner("Sincronizando... pode levar ~30s"):
                try:
                    result = api.sync_all()
                except Exception as exc:
                    if "503" in str(exc):
                        st.error(
                            "Pluggy não configurado. Adicione PLUGGY_CLIENT_ID/SECRET ao .env.",
                            icon=":material/error:",
                        )
                    else:
                        st.error(f"Falhou: {exc}", icon=":material/error:")
                    st.stop()
            st.success(
                f"{result['items_synced']} item(s), "
                f"{result['accounts_synced']} conta(s), "
                f"{result['transactions_imported']} tx novas, "
                f"{result['transactions_duplicates']} duplicadas, "
                f"{result['transactions_categorized']} categorizadas.",
                icon=":material/check_circle:",
            )
            if result.get("errors"):
                with st.expander("Erros parciais", icon=":material/warning:"):
                    for e in result["errors"]:
                        st.code(e)
            st.rerun()

st.divider()

# ---------- Conexões bancárias agrupadas (1 item → N accounts) ----------
st.subheader("Conexões bancárias")
items = api.list_items()
accounts = api.list_accounts()

if not items:
    st.caption(
        "Nenhuma conexão. Importe OFX abaixo, ou conecte via "
        "dashboard.pluggy.ai e clique 'Sincronizar'."
    )
else:
    accounts_by_item: dict[str, list] = {}
    for a in accounts:
        accounts_by_item.setdefault(a["item_id"], []).append(a)

    for item in items:
        item_accounts = accounts_by_item.get(item["id"], [])
        total_balance = sum(a["balance"] for a in item_accounts)

        with st.container(border=True):
            head_l, head_r = st.columns([5, 1])
            with head_l:
                st.markdown(f"#### :material/account_balance: {item['institution_name']}")
                st.caption(
                    f"`{item['id']}` · status `{item['status']}` · "
                    f"{len(item_accounts)} conta(s) · saldo total **{ui.fmt_brl(total_balance)}**"
                )
            with head_r:
                # Confirmação em 2 cliques pra evitar acidente
                state_key = f"confirm_del_{item['id']}"
                if st.session_state.get(state_key):
                    if st.button(
                        "Confirmar exclusão",
                        key=f"do_del_{item['id']}",
                        type="primary",
                        icon=":material/warning:",
                        width="stretch",
                    ):
                        try:
                            api.delete_item(item["id"])
                            st.session_state[state_key] = False
                            st.success(
                                f"Removido: {item['institution_name']}",
                                icon=":material/check_circle:",
                            )
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Falhou: {exc}", icon=":material/error:")
                    if st.button(
                        "Cancelar",
                        key=f"cancel_del_{item['id']}",
                        width="stretch",
                    ):
                        st.session_state[state_key] = False
                        st.rerun()
                else:
                    if st.button(
                        "Apagar",
                        key=f"ask_del_{item['id']}",
                        icon=":material/delete:",
                        width="stretch",
                        help="Remove conexão + todas as contas + todas as transações",
                    ):
                        st.session_state[state_key] = True
                        st.rerun()

            if item_accounts:
                df_acc = pd.DataFrame(item_accounts)[
                    ["name", "type", "balance", "number", "currency_code"]
                ]
                df_acc.columns = ["Conta", "Tipo", "Saldo", "Número", "Moeda"]
                st.dataframe(df_acc, hide_index=True, width="stretch")

# ---------- Importar OFX ----------
st.divider()
st.subheader("Importar extrato OFX")
st.caption(
    "Arraste vários OFX de uma vez — o app **identifica o banco e a conta** "
    "automaticamente pelo conteúdo do arquivo (BANKID/ACCTID) e cria as contas "
    "que faltarem. Reimportar é seguro (idempotência por hash determinístico)."
)

uploaded = st.file_uploader(
    "Arquivos OFX/QFX",
    type=["ofx", "qfx"],
    accept_multiple_files=True,
    help="Selecione 1 ou múltiplos arquivos. Cada banco/conta vira sua própria Account.",
)

if uploaded:
    with st.expander("Preview (banco/conta detectados)", icon=":material/search:", expanded=True):
        preview_rows = []
        for f in uploaded:
            try:
                fp = api.inspect_ofx(file_bytes=f.getvalue(), filename=f.name)
                preview_rows.append(
                    {
                        "Arquivo": f.name,
                        "Banco": fp.get("bank_name") or f"código {fp.get('bank_id') or '?'}",
                        "Conta": fp.get("account_id") or "?",
                        "Tipo": "Cartão" if fp.get("account_kind") == "credit_card" else "Conta",
                        "Tx": fp.get("transaction_count", 0),
                        "Período": (
                            f"{fp.get('date_from')} → {fp.get('date_to')}"
                            if fp.get("date_from")
                            else "?"
                        ),
                    }
                )
            except Exception as exc:
                preview_rows.append(
                    {
                        "Arquivo": f.name,
                        "Banco": f"Erro: {exc}",
                        "Conta": "—",
                        "Tipo": "—",
                        "Tx": 0,
                        "Período": "—",
                    }
                )
        st.dataframe(pd.DataFrame(preview_rows), hide_index=True, width="stretch")

    cols_btn = st.columns([1, 3])
    with cols_btn[0]:
        do_import = st.button(
            "Importar todos",
            type="primary",
            icon=":material/upload_file:",
            width="stretch",
        )
    with cols_btn[1]:
        manual_account = None
        if accounts:
            account_options = {
                "Auto-detectar (recomendado)": None,
                **{f"{a['name']} — {a['id']}": a["id"] for a in accounts},
            }
            label = st.selectbox(
                "Sobrescrever conta destino (opcional)",
                list(account_options.keys()),
                label_visibility="collapsed",
            )
            manual_account = account_options[label]

    if do_import:
        total_new = 0
        total_dup = 0
        errors: list[str] = []

        progress = st.progress(0, text=f"0 / {len(uploaded)}")
        log_area = st.empty()

        for i, f in enumerate(uploaded, start=1):
            try:
                result = api.import_ofx(
                    file_bytes=f.getvalue(),
                    account_id=manual_account,  # None → backend auto-resolve
                    filename=f.name,
                )
                total_new += result["imported"]
                total_dup += result["duplicates"]
                log_area.markdown(
                    f"`{f.name}` → +{result['imported']} novas, ~{result['duplicates']} duplicadas"
                )
            except Exception as exc:
                errors.append(f"{f.name}: {exc}")
                log_area.error(f"`{f.name}` falhou: {exc}", icon=":material/error:")
            progress.progress(i / len(uploaded), text=f"{i} / {len(uploaded)}")

        progress.empty()
        if errors:
            st.warning(f"{len(errors)} arquivo(s) com erro:", icon=":material/warning:")
            for e in errors:
                st.code(e)

        st.success(
            f"Total: {total_new} novas, {total_dup} duplicadas em {len(uploaded)} arquivo(s).",
            icon=":material/check_circle:",
        )
        st.rerun()
