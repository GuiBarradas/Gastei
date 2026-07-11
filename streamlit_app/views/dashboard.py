"""Dashboard — consolidated view across all banks, with drill-down per bank or account.

User-visible strings stay in Portuguese (Brazilian audience).
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import components.ui as ui
from components.api_client import get_api_client

ui.page_header("Dashboard", "Visão consolidada — filtre por banco, conta e período.")

api = get_api_client()
items = api.list_items()
accounts = api.list_accounts()

if not items:
    st.info("Importe um extrato em **Conexões** primeiro.", icon=":material/upload_file:")
    st.stop()


# ---------- Saldos por banco (sempre visível, visão geral) ----------
bank_balances = api.balances_by_bank()
if bank_balances:
    st.subheader("Saldos por banco")
    cols = st.columns(min(len(bank_balances), 5) or 1)
    grand_total = sum(b["total_balance"] for b in bank_balances)
    for i, b in enumerate(bank_balances):
        with cols[i % len(cols)]:
            pct = (b["total_balance"] / grand_total * 100) if grand_total else 0
            st.metric(
                b["bank_name"],
                ui.fmt_brl(b["total_balance"]),
                delta=f"{b['account_count']} conta(s) · {pct:.0f}% do total",
                delta_color="off",
            )
    st.divider()


# ---------- Filtros: banco-first ----------
st.subheader("Análise por período")
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


# Helper: passa item_id OU account_id, nunca ambos
def query_kwargs() -> dict:
    if selected_account_id:
        return {"account_id": selected_account_id}
    if selected_item_id:
        return {"item_id": selected_item_id}
    return {}


qk = query_kwargs()

# ---------- KPIs do período ----------
monthly = api.monthly_summary(start=start, end=end, **qk)
if monthly:
    total_income = sum(m["income"] for m in monthly)
    total_expense = sum(m["expense"] for m in monthly)
    net = total_income - total_expense

    k1, k2, k3 = st.columns(3)
    k1.metric("Receitas no período", ui.fmt_brl(total_income))
    k2.metric("Despesas no período", ui.fmt_brl(total_expense))
    k3.metric(
        "Saldo do período",
        ui.fmt_brl(net),
        delta=ui.fmt_brl(net),
        delta_color="normal" if net >= 0 else "inverse",
    )
else:
    st.info("Sem transações no período. Tente aumentar o intervalo de datas.")


# ---------- Gastos por categoria ----------
st.divider()
col_left, col_right = st.columns([3, 2])

with col_left:
    st.subheader("Onde foi o dinheiro")
    cats = api.spending_by_category(start=start, end=end, top_n=8, **qk)
    if cats:
        df = pd.DataFrame(cats)
        total = df["amount"].sum()
        df["label"] = df["category"].apply(ui.category_label)
        df.loc[df["category"] == "outros", "label"] = "Outros"
        # Horizontal bars, largest on top (plotly draws the last row at the top).
        df = df.iloc[::-1].reset_index(drop=True)
        colors = [
            ui.BAR_AGGREGATE if c in ("outros", "sem_categoria") else ui.BAR for c in df["category"]
        ]

        fig = go.Figure(
            go.Bar(
                x=df["amount"],
                y=df["label"],
                orientation="h",
                marker=dict(color=colors, cornerradius=4),
                text=[
                    f"{ui.fmt_brl(v)}  ·  {v / total:.0%}" if total else ui.fmt_brl(v)
                    for v in df["amount"]
                ],
                textposition="outside",
                cliponaxis=False,
                customdata=df["transaction_count"],
                hovertemplate="<b>%{y}</b><br>%{text}<br>%{customdata} transações<extra></extra>",
            )
        )
        fig.update_xaxes(visible=False)
        fig.update_yaxes(showgrid=False, ticksuffix="  ")
        ui.style_chart(fig, height=420)
        fig.update_layout(margin=dict(r=110))  # room for the outside labels
        st.plotly_chart(fig, width="stretch")
        st.caption(f"Total de despesas no período: **{ui.fmt_brl(total)}**")
    else:
        st.caption("Sem despesas no período.")

with col_right:
    st.subheader("Top estabelecimentos")
    merchants = api.top_merchants(start=start, end=end, limit=8, **qk)
    if merchants:
        df_m = pd.DataFrame(merchants)
        df_m["amount_fmt"] = df_m["amount"].apply(ui.fmt_brl)
        st.dataframe(
            df_m[["merchant", "amount_fmt", "transaction_count"]].rename(
                columns={
                    "merchant": "Estabelecimento",
                    "amount_fmt": "Total",
                    "transaction_count": "Nº de tx",
                }
            ),
            column_config={
                "Estabelecimento": st.column_config.TextColumn(width="large"),
                "Total": st.column_config.TextColumn(width="small"),
                "Nº de tx": st.column_config.NumberColumn(width="small"),
            },
            hide_index=True,
            width="stretch",
            height=420,
        )
    else:
        st.caption("Sem dados.")


# ---------- Evolução mensal ----------
st.divider()
st.subheader("Evolução mensal · Receitas vs Despesas")
if monthly:
    df_m = pd.DataFrame(monthly)
    df_m["year"] = df_m["year"].astype(int)
    df_m["month"] = df_m["month"].astype(int)
    df_m["periodo"] = df_m.apply(lambda r: f"{int(r['year']):04d}-{int(r['month']):02d}", axis=1)
    df_m["Receitas"] = df_m["income"]
    df_m["Despesas"] = df_m["expense"]
    df_m["Saldo líquido"] = df_m["net"]

    df_long = df_m.melt(
        id_vars=["periodo"],
        value_vars=["Receitas", "Despesas"],
        var_name="Tipo",
        value_name="Valor",
    )

    fig2 = px.bar(
        df_long,
        x="periodo",
        y="Valor",
        color="Tipo",
        barmode="group",
        color_discrete_map={"Receitas": ui.INCOME, "Despesas": ui.EXPENSE},
        labels={"periodo": "Mês", "Valor": "R$"},
    )
    fig2.update_traces(marker=dict(cornerradius=4))
    fig2.add_scatter(
        x=df_m["periodo"],
        y=df_m["Saldo líquido"],
        mode="lines+markers",
        name="Saldo líquido",
        line=dict(color=ui.NET, width=2),
        marker=dict(size=8),
        hovertemplate="<b>%{x}</b><br>Saldo: R$ %{y:,.2f}<extra></extra>",
    )
    ui.style_chart(fig2, height=400)
    fig2.update_layout(hovermode="x unified", bargap=0.35)
    fig2.update_yaxes(tickformat=",.0f", tickprefix="R$ ")
    st.plotly_chart(fig2, width="stretch")
else:
    st.caption("Sem dados mensais.")
