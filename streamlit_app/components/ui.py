"""Shared UI layer — design tokens, BRL formatting, page scaffold, Plotly styling.

Iconography is Material Symbols (``:material/name:``) everywhere — no emoji in
chrome, labels, or buttons. The chart palette is a validated set (lightness
band, chroma floor, adjacent-pair CVD ΔE 13.3, ≥3:1 contrast on the light
surface). Charts reference these role constants instead of raw hex, so a
re-theme is one edit here plus ``.streamlit/config.toml``.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

# ---------- Tokens (light mode — mirrors .streamlit/config.toml) ----------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

# Semantic series — validated together as a categorical set.
INCOME = "#008300"
EXPENSE = "#e34948"
NET = "#2a78d6"
BAR = "#2a78d6"  # single-measure magnitude bars use one hue, not one per row
BAR_AGGREGATE = "#898781"  # the "outros" bucket stays visually recessive

FONT_STACK = 'system-ui, -apple-system, "Segoe UI", sans-serif'

_CSS = """
<style>
  [data-testid="stMetric"] {
      background: #fcfcfb;
      border: 1px solid rgba(11, 11, 11, 0.10);
      border-radius: 12px;
      padding: 14px 16px;
  }
  [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
  .block-container { padding-top: 2.4rem; }
</style>
"""


def inject_css() -> None:
    """Shared CSS. Called once by the router (``app.py``) on every rerun."""
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str | None = None) -> None:
    st.title(title)
    if subtitle:
        st.caption(subtitle)


def fmt_brl(v: float) -> str:
    s = f"{v:,.2f}"
    # Swap separators: 1,234.56 → 1.234,56
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def category_label(code: str) -> str:
    """Fallback prettifier: 'alimentacao.delivery' → 'Alimentacao · Delivery'."""
    return " · ".join(p.capitalize().replace("_", " ") for p in code.split("."))


def style_chart(fig: Any, height: int = 400) -> Any:
    """House chart chrome: recessive grid/axes, ink text, transparent paper."""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_STACK, color=INK_SECONDARY, size=13),
        margin=dict(t=28, b=16, l=8, r=8),
        hoverlabel=dict(bgcolor=SURFACE, font=dict(family=FONT_STACK, color=INK)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS)
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS)
    return fig
