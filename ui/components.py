"""Reusable UI components for the Market-Neutral Hedge Builder dashboard.

All components are strictly offline and render deterministically from
cached data or DashboardViewModel structures without triggering network calls.
"""

from __future__ import annotations

import html
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

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

logger = logging.getLogger(__name__)

# Standard cache file path
NEWS_CACHE_PATH = Path("data_cache/headlines.json")

# Private colour aliases used in HTML rendering
_GREEN = "#22c55e"
_RED = "#ef4444"


# ==============================================================================
# OFFLINE NEWS CACHE LOADER
# ==============================================================================

def load_cached_news_for_ticker(
    ticker: str,
    limit: int = 5,
    cache_path: Union[str, Path] = NEWS_CACHE_PATH,
) -> List[Dict[str, Any]]:
    """Load news items from the local disk cache without making network calls.

    Normalizes ticker keys (with or without .NS) and returns up to `limit` items.
    Returns an empty list on missing cache, corrupt JSON, or missing ticker.
    """
    path = Path(cache_path)
    if not path.is_file():
        logger.debug("News cache file not found: %s", path)
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("Failed to load news cache from %s: %s", path, exc)
        return []

    if not isinstance(data, dict):
        return []

    # Check direct match, upper-case, or with/without .NS
    clean_ticker = (ticker or "").strip().upper()
    alt_ticker = clean_ticker[:-3] if clean_ticker.endswith(".NS") else f"{clean_ticker}.NS"

    raw_items = data.get(clean_ticker) or data.get(alt_ticker) or []
    if not isinstance(raw_items, list):
        return []

    results: List[Dict[str, Any]] = []
    for item in raw_items[:limit]:
        if isinstance(item, dict):
            results.append(item)
    return results


# ==============================================================================
# METRIC CARDS
# ==============================================================================

def render_metric_card(
    label: str,
    unhedged_val: Optional[Union[float, str]] = None,
    hedged_val: Optional[Union[float, str]] = None,
    format_str: str = "{:.2f}",
    invert: bool = False,
    accent_class: str = "",
    delta: Optional[str] = None,
    help_text: Optional[str] = None,
    format_pct: bool = False,
    format_currency: bool = False,
    is_neutral: bool = False,
) -> None:
    """Render a metric card comparing unhedged vs hedged values.

    Fully backwards-compatible with existing app.py callers while supporting
    new DashboardViewModel metrics and None/missing values safely.
    """
    def _format_val(val: Optional[Union[float, str]]) -> str:
        if val is None or val == "":
            return "N/A"
        if isinstance(val, (int, float)):
            if format_pct:
                pct_val = val * 100 if abs(val) <= 1.0 else val
                return f"{pct_val:.2f}%"
            if format_currency:
                return f"₹{val:,.2f}"
            try:
                return format_str.format(val)
            except Exception:
                return f"{val:.2f}"
        return str(val)

    u_str = _format_val(unhedged_val)
    h_str = _format_val(hedged_val)

    # Compute delta if not explicitly provided
    if delta is None and isinstance(unhedged_val, (int, float)) and isinstance(hedged_val, (int, float)):
        diff = hedged_val - unhedged_val
        if invert:
            pct = ((abs(unhedged_val) - abs(hedged_val)) / max(abs(unhedged_val), 1e-9)) * 100
        else:
            pct = (diff / max(abs(unhedged_val), 1e-9)) * 100

        is_positive = (diff <= 0) if invert else (diff >= 0)
        arrow = "▲" if is_positive else "▼"
        delta = f"{arrow} {abs(pct):.1f}% improvement"

    delta_html = ""
    if delta:
        if is_neutral:
            css_cls = "metric-delta-neutral"
        elif "▲" in delta or "+" in delta or "positive" in accent_class:
            css_cls = "metric-delta-pos positive"
        else:
            css_cls = "metric-delta-neg negative"

        safe_delta = html.escape(str(delta))
        delta_html = f'<div class="metric-delta {css_cls}">{safe_delta}</div>'

    help_attr = f' title="{html.escape(help_text)}"' if help_text else ""
    safe_label = html.escape(label)

    card_html = f"""
    <div class="metric-card {accent_class}"{help_attr}>
        <div class="mc-label metric-label">{safe_label}</div>
        <div class="mc-row">
            <span class="mc-before metric-val-unhedged">Unhedged: {html.escape(u_str)}</span>
            <span class="mc-after metric-val-hedged">{html.escape(h_str)}</span>
        </div>
        {delta_html}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


# ==============================================================================
# CHART WRAPPERS (PRESERVED & ENHANCED)
# ==============================================================================

def render_cumulative_chart(
    data: Any,
    crash_periods: Optional[List[Tuple[str, str, str]]] = None,
) -> None:
    """Render the cumulative returns comparison chart."""
    if data is None:
        st.info("No cumulative returns data available.")
        return

    dates = None
    nifty = None
    unhedged = None
    hedged = None

    if isinstance(data, dict):
        dates = data.get("dates")
        nifty = data.get("nifty_cum")
        unhedged = data.get("unhedged_cum")
        hedged = data.get("hedged_cum")
    elif isinstance(data, pd.DataFrame) and not data.empty:
        dates = data.index
        nifty = data.get("NIFTY 50", data.get("nifty_cum", [1.0] * len(data)))
        unhedged = data.get("Unhedged Long", data.get("unhedged_cum", [1.0] * len(data)))
        hedged = data.get("Hedged Portfolio", data.get("hedged_cum", [1.0] * len(data)))

    if dates is None or unhedged is None or hedged is None:
        st.info("No cumulative returns data available.")
        return

    fig = create_cumulative_returns_figure(
        dates=dates,
        nifty_cum=nifty,
        unhedged_cum=unhedged,
        hedged_cum=hedged,
        crash_periods=crash_periods,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_beta_chart(rolling_beta: Any) -> None:
    """Render the rolling beta time-series chart."""
    if rolling_beta is None:
        st.info("No rolling beta data available.")
        return

    if isinstance(rolling_beta, pd.Series) and not rolling_beta.empty:
        dates = rolling_beta.index
        values = rolling_beta.values
    elif isinstance(rolling_beta, pd.DataFrame) and not rolling_beta.empty:
        dates = rolling_beta.index
        values = rolling_beta.iloc[:, 0].values
    else:
        st.info("No rolling beta data available.")
        return

    fig = create_rolling_beta_figure(dates=dates, rolling_beta=values)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_zscore_chart(zscore: Any) -> None:
    """Render the spread and z-score cointegration chart."""
    if zscore is None:
        st.info("No spread z-score data available.")
        return

    if isinstance(zscore, pd.Series) and not zscore.empty:
        dates = zscore.index
        values = zscore.values
    elif isinstance(zscore, pd.DataFrame) and not zscore.empty:
        dates = zscore.index
        values = zscore.iloc[:, 0].values
    else:
        st.info("No spread z-score data available.")
        return

    fig = create_zscore_figure(dates=dates, zscore=values)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_correlation_heatmap(corr_matrix: Any) -> None:
    """Render the sector correlation matrix heatmap."""
    if corr_matrix is None:
        st.info("No correlation data available.")
        return
    if isinstance(corr_matrix, pd.DataFrame) and corr_matrix.empty:
        st.info("No correlation data available.")
        return

    fig = create_correlation_heatmap_figure(corr_matrix)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_drawdown_chart(
    dates_or_df: Any,
    unhedged_dd: Optional[Sequence[float]] = None,
    hedged_dd: Optional[Sequence[float]] = None,
) -> None:
    """Render the underwater drawdown comparison chart."""
    if dates_or_df is None:
        st.info("No drawdown data available.")
        return

    if unhedged_dd is not None and hedged_dd is not None:
        dates = dates_or_df
        u_dd = unhedged_dd
        h_dd = hedged_dd
    elif isinstance(dates_or_df, pd.DataFrame) and not dates_or_df.empty:
        dates = dates_or_df.index
        u_dd = dates_or_df.get("Unhedged", dates_or_df.iloc[:, 0]).values
        h_dd = dates_or_df.get("Hedged", dates_or_df.iloc[:, 1] if len(dates_or_df.columns) > 1 else dates_or_df.iloc[:, 0]).values
    else:
        st.info("No drawdown data available.")
        return

    fig = create_drawdown_figure(dates=dates, unhedged_dd=u_dd, hedged_dd=h_dd)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ==============================================================================
# NEWS INTELLIGENCE PANEL
# ==============================================================================

def _render_single_news_card(item: Dict[str, Any]) -> None:
    """Render an individual news article card with verified metadata."""
    if not isinstance(item, dict):
        return

    title = str(item.get("headline") or item.get("title") or "Untitled Article").strip()
    publisher = str(item.get("publisher") or item.get("source") or "Unknown Publisher").strip()
    timestamp = str(item.get("published_at") or item.get("published") or item.get("date") or "").strip()
    url = str(item.get("url") or item.get("link") or "").strip()
    provider = str(item.get("provider") or "").strip()
    snippet = str(item.get("snippet") or item.get("summary") or "").strip()

    safe_title = html.escape(title)
    safe_publisher = html.escape(publisher)
    safe_timestamp = html.escape(timestamp) if timestamp else "Timestamp unavailable"
    safe_provider = html.escape(provider.upper()) if provider else "NEWS"

    url_html = '<span style="color:#64748b; font-size:11px;">Source link unavailable</span>'
    if url.startswith("http://") or url.startswith("https://"):
        safe_url = html.escape(url, quote=True)
        url_html = f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" style="color:#38bdf8; text-decoration:none; font-size:12px; font-weight:500;">Read Source ↗</a>'

    snippet_html = ""
    if snippet:
        snippet_html = f'<div style="color:#94a3b8; font-size:12px; line-height:1.4; margin:6px 0 8px 0;">{html.escape(snippet)}</div>'

    card_html = f"""
    <div style="background:rgba(30,41,59,0.7); border:1px solid #334155; border-radius:6px; padding:12px 14px; margin-bottom:10px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <span style="background:#1e293b; color:#38bdf8; font-size:11px; padding:2px 8px; border-radius:4px; font-weight:600; border:1px solid #0284c7;">{safe_publisher}</span>
            <span style="color:#64748b; font-size:11px;">{safe_timestamp}</span>
        </div>
        <div style="color:#f1f5f9; font-size:13px; font-weight:600; line-height:1.4; margin-bottom:4px;">{safe_title}</div>
        {snippet_html}
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px; padding-top:6px; border-top:1px solid #1e293b;">
            <span style="color:#475569; font-size:10px; text-transform:uppercase; letter-spacing:0.5px;">Provider: {safe_provider}</span>
            {url_html}
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def render_news_panel(
    long_news: Optional[List[Dict[str, Any]]] = None,
    short_news: Optional[List[Dict[str, Any]]] = None,
    long_ticker: Optional[str] = None,
    short_ticker: Optional[str] = None,
) -> None:
    """Render a side-by-side institutional news intelligence panel.

    Displays real headlines for both the long leg and short hedge leg.
    Safely handles empty news, missing fields, and partial data with clean fallbacks.
    """
    l_ticker = (long_ticker or "Long Leg").strip()
    s_ticker = (short_ticker or "Short Leg").strip()

    st.subheader("📰 Financial News Intelligence & Catalyst Audit")
    st.caption("Verified cached news intelligence retrieved for catalyst screening.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"#### 📈 {html.escape(l_ticker)} — Long Catalyst Intelligence", unsafe_allow_html=True)
        if not long_news:
            st.info(f"No recent news intelligence cached for {html.escape(l_ticker)}.")
        else:
            for item in long_news:
                _render_single_news_card(item)

    with col2:
        st.markdown(f"#### 📉 {html.escape(s_ticker)} — Short Catalyst Intelligence", unsafe_allow_html=True)
        if not short_news:
            st.info(f"No recent news intelligence cached for {html.escape(s_ticker)}.")
        else:
            for item in short_news:
                _render_single_news_card(item)


# ==============================================================================
# AGENT EXECUTION TRACE
# ==============================================================================

def render_agent_trace(
    view_model_or_rejection_log: Any = None,
    approved: Optional[bool] = None,
    **kwargs: Any,
) -> None:
    """Render the multi-agent execution audit trail.

    Supports both DashboardViewModel input or legacy arguments:
    render_agent_trace(rejection_log, approved=...)
    """
    st.subheader("🤖 Multi-Agent Execution Audit Trail")

    messages: List[Dict[str, Any]] = []
    rej_log: List[Dict[str, Any]] = []
    is_approved: Optional[bool] = approved

    # Check whether the first arg is a DashboardViewModel or a list
    if hasattr(view_model_or_rejection_log, "verification"):
        vm = view_model_or_rejection_log
        rej_log = getattr(vm.verification, "rejection_log", []) or getattr(vm.verification, "rejection_history", []) or []
        messages = getattr(vm.verification, "messages", []) or []
        is_approved = getattr(vm.verification, "approved", None)
        if is_approved is None:
            is_approved = getattr(vm.verification, "is_approved", None)
    elif isinstance(view_model_or_rejection_log, list):
        rej_log = view_model_or_rejection_log
    elif "rejection_log" in kwargs:
        rej_log = kwargs["rejection_log"] or []

    # Verification status banner
    if is_approved is True:
        st.success("✅ **Strategy Approved**: The Adversarial Risk Verifier passed this portfolio.")
    elif is_approved is False:
        st.error("❌ **Strategy Rejected**: The Adversarial Risk Verifier rejected this pair.")
    else:
        st.warning("⚪ **Risk Verification Status**: Not evaluated or pending.")

    # Show agent messages if present
    if messages:
        st.markdown("##### Agent Reasoning & Activity Log")
        for idx, msg in enumerate(messages, 1):
            if isinstance(msg, dict):
                sender = msg.get("sender") or msg.get("role") or msg.get("name") or "Agent"
                content = msg.get("content") or msg.get("message") or ""
            else:
                sender = getattr(msg, "name", None) or getattr(msg, "role", None) or type(msg).__name__
                content = getattr(msg, "content", str(msg))

            safe_sender = html.escape(str(sender))
            safe_content = html.escape(str(content))

            with st.expander(f"Step {idx}: {safe_sender}", expanded=(idx == len(messages))):
                st.markdown(f"**Node:** `{safe_sender}`")
                st.markdown(f"```text\n{safe_content}\n```")
    elif not rej_log:
        st.info("Execution history unavailable. Run the hedge builder pipeline to see agent traces.")

    # Rejection history if any pairs were screened out
    if rej_log:
        st.markdown("##### ⚠️ Rejection & Risk Filter History")
        for i, rej in enumerate(rej_log, 1):
            if not isinstance(rej, dict):
                continue
            pair = rej.get("pair") or rej.get("candidate") or rej.get("agent") or "Unknown Pair"
            reason = rej.get("reason") or rej.get("message") or "Risk criteria not met"
            failed_checks = rej.get("failed_checks") or []
            attempt = rej.get("attempt") or i

            safe_pair = html.escape(str(pair))
            safe_reason = html.escape(str(reason))

            checks_str = ", ".join(str(c) for c in failed_checks) if failed_checks else "None"
            safe_checks = html.escape(checks_str)

            rej_html = f"""
            <div style="background:rgba(239,68,68,0.1); border-left:4px solid #ef4444; padding:8px 12px; margin-bottom:8px; border-radius:0 4px 4px 0;">
                <div style="font-weight:600; color:#f87171; font-size:12px;">Attempt {attempt}: {safe_pair}</div>
                <div style="color:#e2e8f0; font-size:12px; margin-top:2px;">{safe_reason}</div>
                <div style="color:#94a3b8; font-size:11px; margin-top:4px;">Failed Checks: <code>{safe_checks}</code></div>
            </div>
            """
            st.markdown(rej_html, unsafe_allow_html=True)


# ==============================================================================
# PAIR DETAILS & FUNDAMENTALS
# ==============================================================================

def render_pair_details(
    view_model_or_long: Any = None,
    short_stock: Optional[Dict[str, Any]] = None,
) -> None:
    """Render fundamental and catalyst details for selected long & short assets.

    Accepts either a DashboardViewModel or legacy (long_stock, short_stock) dicts.
    Missing metrics display 'N/A', never 0.0 or assumed values.
    """
    long_data: Dict[str, Any] = {}
    short_data: Dict[str, Any] = {}
    long_ticker = "Long Asset"
    short_ticker = "Short Hedge"

    if hasattr(view_model_or_long, "research"):
        vm = view_model_or_long
        long_data = getattr(vm.research, "selected_long_fundamentals", {}) or {}
        short_data = getattr(vm.research, "selected_short_fundamentals", {}) or {}
        run_info = getattr(vm, "run_info", None)
        portfolio = getattr(vm, "portfolio", None)
        long_ticker = (
            getattr(run_info, "selected_long", None)
            or getattr(portfolio, "long_ticker", None)
            or "Long Asset"
        )
        short_ticker = (
            getattr(run_info, "selected_short", None)
            or getattr(portfolio, "short_ticker", None)
            or "Short Hedge"
        )
    elif isinstance(view_model_or_long, dict):
        long_data = view_model_or_long
        long_ticker = str(view_model_or_long.get("symbol") or view_model_or_long.get("ticker", "Long Asset"))
        if isinstance(short_stock, dict):
            short_data = short_stock
            short_ticker = str(short_stock.get("symbol") or short_stock.get("ticker", "Short Hedge"))

    st.subheader("🔍 Selected Pair Fundamental Comparison")

    def _fmt(val: Any, is_pct: bool = False, is_ratio: bool = False) -> str:
        if val is None or val == "":
            return "N/A"
        if isinstance(val, (int, float)):
            if is_pct:
                return f"{val * 100:.2f}%" if abs(val) < 1.0 else f"{val:.2f}%"
            if is_ratio:
                return f"{val:.2f}x"
            return f"{val:.2f}"
        return str(val)

    # Match metric keys across both schema formats
    pe_l = long_data.get("pe_ratio") if "pe_ratio" in long_data else long_data.get("pe")
    pe_s = short_data.get("pe_ratio") if "pe_ratio" in short_data else short_data.get("pe")

    roe_l = long_data.get("roe")
    roe_s = short_data.get("roe")

    de_l = long_data.get("debt_to_equity") if "debt_to_equity" in long_data else long_data.get("de_ratio")
    de_s = short_data.get("debt_to_equity") if "debt_to_equity" in short_data else short_data.get("de_ratio")

    rg_l = long_data.get("revenue_growth") if "revenue_growth" in long_data else long_data.get("rev_growth")
    rg_s = short_data.get("revenue_growth") if "revenue_growth" in short_data else short_data.get("rev_growth")

    mc_l = long_data.get("market_cap")
    mc_s = short_data.get("market_cap")

    sc_l = long_data.get("composite_score")
    sc_s = short_data.get("composite_score")

    metrics = [
        ("P/E Ratio", _fmt(pe_l, is_ratio=True), _fmt(pe_s, is_ratio=True)),
        ("ROE", _fmt(roe_l, is_pct=True), _fmt(roe_s, is_pct=True)),
        ("Debt-to-Equity", _fmt(de_l, is_ratio=True), _fmt(de_s, is_ratio=True)),
        ("Revenue Growth", _fmt(rg_l, is_pct=True), _fmt(rg_s, is_pct=True)),
        ("Market Cap", _fmt(mc_l), _fmt(mc_s)),
        ("Fundamental Score", _fmt(sc_l), _fmt(sc_s)),
    ]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"#### 📈 {html.escape(long_ticker)} (Long)")
        if not long_data:
            st.info(f"Fundamental data unavailable for {html.escape(long_ticker)}.")
        else:
            df_long = pd.DataFrame(
                [{"Metric": m[0], "Value": m[1]} for m in metrics]
            )
            st.table(df_long.set_index("Metric"))

    with col2:
        st.markdown(f"#### 📉 {html.escape(short_ticker)} (Short)")
        if not short_data:
            st.info(f"Fundamental data unavailable for {html.escape(short_ticker)}.")
        else:
            df_short = pd.DataFrame(
                [{"Metric": m[0], "Value": m[2]} for m in metrics]
            )
            st.table(df_short.set_index("Metric"))


# ==============================================================================
# VERIFICATION SUMMARY (PHASE C2 NEW)
# ==============================================================================

def render_verification_summary(view_model: Any) -> None:
    """Render the quantitative gate verification results from the Adversarial Verifier.

    Shows verification status, individual risk gates, diagnostics, and attempt count.
    """
    st.subheader("🛡️ Adversarial Risk Gate Verification")

    if view_model is None or not hasattr(view_model, "verification"):
        st.info("No verification data available.")
        return

    ver = view_model.verification
    is_app = getattr(ver, "approved", None)
    if is_app is None:
        is_app = getattr(ver, "is_approved", None)
    ver_res = getattr(ver, "verifier_result", {}) or {}
    diag = ver_res.get("diagnostic") or getattr(ver, "diagnostic", None)
    failed = ver_res.get("failed_checks") or getattr(ver, "failed_checks", []) or []
    attempt = getattr(ver, "attempt_count", 1) or 1
    run_info = getattr(view_model, "run_info", None)
    max_att = getattr(run_info, "max_attempts", 3) if run_info else 3

    # Status badge
    if is_app is True:
        badge_text = "APPROVED ✅"
        badge_color = "#10b981"
    elif is_app is False:
        badge_text = "REJECTED ❌"
        badge_color = "#ef4444"
    else:
        badge_text = "NOT EVALUATED ⚪"
        badge_color = "#94a3b8"

    header_html = f"""
    <div style="display:flex; justify-content:space-between; align-items:center; background:#1e293b; border:1px solid #334155; padding:12px 16px; border-radius:6px; margin-bottom:12px;">
        <div>
            <span style="font-size:12px; color:#94a3b8; text-transform:uppercase; letter-spacing:0.5px;">Verification Verdict</span>
            <div style="font-size:16px; font-weight:700; color:{badge_color}; margin-top:2px;">{badge_text}</div>
        </div>
        <div style="text-align:right;">
            <span style="font-size:12px; color:#94a3b8;">Screening Loop</span>
            <div style="font-size:13px; font-weight:600; color:#e2e8f0; margin-top:2px;">Attempt {attempt} of {max_att}</div>
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    # Render individual gate results if available
    gate_cols = st.columns(4)
    gates = [
        ("Correlation Gate", "passed" if "correlation" not in failed and is_app is not None else "failed" if "correlation" in failed else "pending"),
        ("Cointegration Gate", "passed" if "cointegration" not in failed and is_app is not None else "failed" if "cointegration" in failed else "pending"),
        ("Drawdown Gate", "passed" if "drawdown" not in failed and is_app is not None else "failed" if "drawdown" in failed else "pending"),
        ("Beta Neutrality", "passed" if "beta" not in failed and is_app is not None else "failed" if "beta" in failed else "pending"),
    ]

    for col, (gate_name, status) in zip(gate_cols, gates):
        with col:
            icon = "✅" if status == "passed" else ("❌" if status == "failed" else "⏳")
            status_text = "PASS" if status == "passed" else ("FAIL" if status == "failed" else "PENDING")
            st.metric(label=gate_name, value=status_text, delta=icon)

    if failed:
        st.markdown(f"**Failed Verification Criteria:** `{', '.join(html.escape(str(c)) for c in failed)}`")

    if diag:
        safe_diag = html.escape(str(diag))
        st.markdown(f"""
        <div style="background:rgba(30,41,59,0.5); border-left:3px solid #38bdf8; padding:8px 12px; margin-top:8px; border-radius:0 4px 4px 0; font-size:12px; color:#cbd5e1;">
            <strong>Verifier Diagnostic:</strong> {safe_diag}
        </div>
        """, unsafe_allow_html=True)


# ==============================================================================
# F&O EXECUTION DETAILS
# ==============================================================================

def render_fno_table(fno_data: Any) -> None:
    """Render the F&O contract specification table."""
    st.subheader("📋 Derivatives (F&O) Execution Specifications")

    if not fno_data:
        st.info("No F&O contract specifications available for this strategy.")
        return

    if isinstance(fno_data, list):
        if not fno_data:
            st.info("No F&O contract specifications available for this strategy.")
            return
        header = "".join(
            f"<th>{col}</th>"
            for col in ["Symbol", "Direction", "Lot Size", "# Lots", "Price (₹)", "Notional (₹)"]
        )
        rows = ""
        for row in fno_data:
            if not isinstance(row, dict):
                continue
            symbol = row.get("symbol", "N/A")
            direction = row.get("direction", "N/A")
            direction_color = _GREEN if direction == "LONG" else _RED
            lot_size = f"{row.get('lot_size'):,}" if row.get("lot_size") is not None else "N/A"
            lots = str(row.get("lots", "N/A"))
            price = f"₹{row['price']:,.2f}" if row.get("price") is not None else "N/A"
            notional = f"₹{row['notional']:,.0f}" if row.get("notional") is not None else "N/A"
            rows += (
                f"<tr>"
                f"<td style='font-weight:600'>{html.escape(str(symbol))}</td>"
                f"<td style='color:{direction_color};font-weight:600'>{html.escape(str(direction))}</td>"
                f"<td>{html.escape(str(lot_size))}</td>"
                f"<td>{html.escape(str(lots))}</td>"
                f"<td>{html.escape(str(price))}</td>"
                f"<td>{html.escape(str(notional))}</td>"
                f"</tr>"
            )
        st.markdown(f"""
        <table class="fno-table">
            <thead><tr>{header}</tr></thead>
            <tbody>{rows}</tbody>
        </table>
        """, unsafe_allow_html=True)
    elif isinstance(fno_data, dict):
        formatted_rows = []
        for k, v in fno_data.items():
            clean_key = str(k).replace("_", " ").title()
            clean_val = "N/A" if v is None else str(v)
            formatted_rows.append({"Parameter": clean_key, "Specification": clean_val})
        df_fno = pd.DataFrame(formatted_rows)
        st.table(df_fno.set_index("Parameter"))
    else:
        st.write(fno_data)
