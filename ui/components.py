"""
Reusable UI components for the Market-Neutral Hedge Builder dashboard.

Each ``render_*`` function encapsulates a self-contained visual block that
can be placed anywhere in the Streamlit layout.  Chart components delegate
to :pymod:`ui.charts` for figure construction and add the Streamlit
rendering call (``st.plotly_chart``).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from ui.charts import (
    create_correlation_heatmap_figure,
    create_cumulative_returns_figure,
    create_drawdown_figure,
    create_rolling_beta_figure,
    create_zscore_figure,
)


# ═══════════════════════════════════════════════════════════════════════════
# Metric Cards
# ═══════════════════════════════════════════════════════════════════════════

def render_metric_card(
    label: str,
    unhedged_val: float,
    hedged_val: float,
    format_str: str = "{:.2f}",
    invert: bool = False,
    accent_class: str = "",
) -> None:
    """Render a glass-morphism metric card comparing unhedged → hedged values.

    Parameters
    ----------
    label : str
        Card title (e.g. ``"Portfolio Beta"``).
    unhedged_val : float
        Metric value *before* hedging.
    hedged_val : float
        Metric value *after* hedging.
    format_str : str
        Python format spec applied to both values.
    invert : bool
        If ``True`` a *decrease* is treated as positive improvement
        (e.g. drawdown, beta).
    accent_class : str
        Extra CSS class for the top-accent colour strip
        (``mc-beta``, ``mc-dd``, ``mc-sharpe``, ``mc-sortino``).
    """
    diff = hedged_val - unhedged_val
    if invert:
        pct = ((abs(unhedged_val) - abs(hedged_val)) / max(abs(unhedged_val), 1e-9)) * 100
    else:
        pct = (diff / max(abs(unhedged_val), 1e-9)) * 100

    is_positive = (diff <= 0) if invert else (diff >= 0)
    delta_cls = "positive" if is_positive else "negative"
    arrow = "▲" if is_positive else "▼"

    before_str = format_str.format(unhedged_val)
    after_str = format_str.format(hedged_val)

    st.markdown(f"""
    <div class="metric-card {accent_class}">
        <div class="mc-label">{label}</div>
        <div class="mc-row">
            <span class="mc-before">{before_str}</span>
            <span class="mc-after">{after_str}</span>
        </div>
        <span class="mc-delta {delta_cls}">{arrow} {abs(pct):.1f}% improvement</span>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# Chart Wrappers
# ═══════════════════════════════════════════════════════════════════════════

def render_cumulative_chart(
    data: Dict[str, Any],
    crash_periods: Optional[List[Tuple[str, str, str]]] = None,
) -> None:
    """Render the cumulative returns chart.

    Parameters
    ----------
    data : dict
        Must contain ``dates``, ``nifty_cum``, ``unhedged_cum``, ``hedged_cum``.
    crash_periods : list[tuple], optional
        ``(start, end, label)`` crash-regime tuples.
    """
    fig = create_cumulative_returns_figure(
        dates=data["dates"],
        nifty_cum=data["nifty_cum"],
        unhedged_cum=data["unhedged_cum"],
        hedged_cum=data["hedged_cum"],
        crash_periods=crash_periods,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_beta_chart(rolling_beta: pd.Series) -> None:
    """Render the rolling portfolio-beta chart.

    Parameters
    ----------
    rolling_beta : pd.Series
        DatetimeIndex → beta values.
    """
    fig = create_rolling_beta_figure(
        dates=rolling_beta.index,
        rolling_beta=rolling_beta.values,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_zscore_chart(zscore: pd.Series) -> None:
    """Render the spread Z-score chart with ±1.5σ bands.

    Parameters
    ----------
    zscore : pd.Series
        DatetimeIndex → Z-score values.
    """
    fig = create_zscore_figure(
        dates=zscore.index,
        zscore=zscore.values,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_correlation_heatmap(corr_matrix: pd.DataFrame) -> None:
    """Render the sector correlation heatmap.

    Parameters
    ----------
    corr_matrix : pd.DataFrame
        Square correlation matrix.
    """
    fig = create_correlation_heatmap_figure(corr_matrix)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_drawdown_chart(
    dates: Sequence,
    unhedged_dd: Sequence[float],
    hedged_dd: Sequence[float],
) -> None:
    """Render the drawdown underwater chart.

    Parameters
    ----------
    dates, unhedged_dd, hedged_dd : array-like
    """
    fig = create_drawdown_figure(dates, unhedged_dd, hedged_dd)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ═══════════════════════════════════════════════════════════════════════════
# Agent Trace Panel
# ═══════════════════════════════════════════════════════════════════════════

def render_agent_trace(
    rejection_log: List[Dict[str, str]],
    approved: bool = True,
) -> None:
    """Render the agent reasoning & rejection trace panel.

    Parameters
    ----------
    rejection_log : list[dict]
        Each dict must have ``agent``, ``message``, and ``timestamp`` keys.
        Optional ``status`` key: ``"rejected"`` or ``"approved"``.
    approved : bool
        Whether the pipeline ultimately found an approved pair.
    """
    with st.expander("🔍 Agent Reasoning & Rejection Trace", expanded=False):
        # Visual flow
        st.markdown(
            "<div style='text-align:center; color:#94a3b8; font-size:0.82rem; "
            "margin-bottom:1rem;'>"
            "📝 Parser → 🔎 Screener → 📊 Quant → ✅ Verifier → "
            "(🔁 Loop or 🎯 Approve)"
            "</div>",
            unsafe_allow_html=True,
        )

        for entry in rejection_log:
            status = entry.get("status", "info")
            css_cls = ""
            if status == "rejected":
                css_cls = "rejected"
            elif status == "approved":
                css_cls = "approved"

            st.markdown(f"""
            <div class="trace-step {css_cls}">
                <span class="ts-time">{entry.get('timestamp', '')}</span>
                <span class="ts-agent">{entry['agent']}</span>
                <div style="margin-top:0.25rem; color:#cbd5e1;">{entry['message']}</div>
            </div>
            """, unsafe_allow_html=True)

        if approved:
            st.success("✅ Final pair approved – hedge portfolio constructed.")
        else:
            st.error("⚠️ All candidate pairs exhausted. No valid hedge found.")


# ═══════════════════════════════════════════════════════════════════════════
# F&O Lot-Size Execution Table
# ═══════════════════════════════════════════════════════════════════════════

def render_fno_table(fno_data: List[Dict[str, Any]]) -> None:
    """Render the F&O lot-size execution table.

    Parameters
    ----------
    fno_data : list[dict]
        Each dict: ``symbol``, ``direction``, ``lot_size``, ``lots``,
        ``price``, ``notional``.
    """
    header = "".join(
        f"<th>{col}</th>"
        for col in ["Symbol", "Direction", "Lot Size", "# Lots", "Price (₹)", "Notional (₹)"]
    )
    rows = ""
    for row in fno_data:
        direction_color = _GREEN if row["direction"] == "LONG" else _RED
        rows += (
            f"<tr>"
            f"<td style='font-weight:600'>{row['symbol']}</td>"
            f"<td style='color:{direction_color};font-weight:600'>{row['direction']}</td>"
            f"<td>{row['lot_size']:,}</td>"
            f"<td>{row['lots']}</td>"
            f"<td>₹{row['price']:,.2f}</td>"
            f"<td>₹{row['notional']:,.0f}</td>"
            f"</tr>"
        )
    st.markdown(f"""
    <table class="fno-table">
        <thead><tr>{header}</tr></thead>
        <tbody>{rows}</tbody>
    </table>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# Pair-Details Fundamentals Table
# ═══════════════════════════════════════════════════════════════════════════

def render_pair_details(
    long_stock: Dict[str, Any],
    short_stock: Dict[str, Any],
) -> None:
    """Render side-by-side comparison of long vs short stock fundamentals.

    Parameters
    ----------
    long_stock, short_stock : dict
        Keys: ``symbol``, ``weight``, ``pe``, ``roe``, ``rev_growth``,
        ``de_ratio``, ``market_cap``.
    """
    def _fmt(v: Any, pct: bool = False) -> str:
        if v is None:
            return "—"
        if pct:
            return f"{v:+.1f}%"
        if isinstance(v, float):
            return f"{v:.2f}"
        return str(v)

    metrics = [
        ("P/E Ratio", "pe", False),
        ("ROE (%)", "roe", True),
        ("Revenue Growth", "rev_growth", True),
        ("D/E Ratio", "de_ratio", False),
        ("Market Cap", "market_cap", False),
        ("Weight", "weight", True),
    ]

    header = (
        f"<th>Metric</th>"
        f"<th style='color:{_GREEN}'>📈 {long_stock['symbol']} (LONG)</th>"
        f"<th style='color:{_RED}'>📉 {short_stock['symbol']} (SHORT)</th>"
    )
    rows = ""
    for label, key, pct in metrics:
        rows += (
            f"<tr>"
            f"<td style='font-weight:600; color:#94a3b8'>{label}</td>"
            f"<td>{_fmt(long_stock.get(key), pct)}</td>"
            f"<td>{_fmt(short_stock.get(key), pct)}</td>"
            f"</tr>"
        )
    st.markdown(f"""
    <table class="fno-table">
        <thead><tr>{header}</tr></thead>
        <tbody>{rows}</tbody>
    </table>
    """, unsafe_allow_html=True)


# private colour aliases used in HTML rendering
_GREEN = "#22c55e"
_RED = "#ef4444"
