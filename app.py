"""🛡️ Market-Neutral Hedge Builder — Streamlit Dashboard
======================================================

Main entry point for the interactive dashboard. Executes the autonomous
multi-agent hedge-building pipeline and renders an institutional-grade
tear-sheet driven exclusively by genuine outputs from the quantitative engine.

Run with::

    streamlit run app.py
"""

from __future__ import annotations

import logging
import traceback
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

# ── Page configuration (MUST be the first Streamlit call) ─────────────────
st.set_page_config(
    page_title="Market-Neutral Hedge Builder",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── UI package imports ────────────────────────────────────────────────────
from ui.styles import inject_css
from ui.components import (
    load_cached_news_for_ticker,
    render_agent_trace,
    render_beta_chart,
    render_correlation_heatmap,
    render_cumulative_chart,
    render_drawdown_chart,
    render_fno_table,
    render_metric_card,
    render_news_panel,
    render_pair_details,
    render_verification_summary,
    render_zscore_chart,
)
from ui.adapter import DashboardViewModel, map_state_to_dashboard

# Inject global fintech dark CSS theme
inject_css()

logger = logging.getLogger(__name__)

# ── Import LangGraph pipeline entry point ─────────────────────────────────
_ENGINE_AVAILABLE = False
try:
    from agents.graph import run_hedge_builder
    _ENGINE_AVAILABLE = True
except Exception as _import_exc:
    logger.warning("agents.graph.run_hedge_builder could not be imported: %s", _import_exc)


# ══════════════════════════════════════════════════════════════════════════
# SIDEBAR CONTROLS
# ══════════════════════════════════════════════════════════════════════════

def _render_sidebar() -> Dict[str, Any]:
    """Render the sidebar controls and return the collected parameters."""
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        st.markdown("---")

        capital = st.number_input(
            "💰 Capital (₹)",
            min_value=10_000,
            max_value=100_000_000,
            value=100_000,
            step=10_000,
            format="%d",
            help="Total strategy capital allocation in INR.",
        )

        lookback = st.selectbox(
            "📅 Lookback Period",
            options=["1Y", "2Y", "3Y"],
            index=0,
            help="Historical trailing window for statistical estimation.",
        )
        lookback_days_map = {"1Y": 252, "2Y": 504, "3Y": 756}
        lookback_days = lookback_days_map.get(lookback, 252)

        benchmark = st.text_input(
            "🏛️ Market Benchmark",
            value="^NSEI",
            help="NSE benchmark index ticker (default: ^NSEI for NIFTY 50).",
        )

        st.markdown("---")
        st.markdown("### 🕳️ Black Swan Stress Testing")
        st.caption("Stress-test the statistical hedge against historical crisis regimes:")

        stress_scenario_map = {
            "🦠 COVID 2020": "COVID_2020",
            "💥 2008 GFC": "2008_GFC",
            "📉 Tech Selloff 2022": "TECH_SELLOFF_2022",
            "🗳️ Election Day 2024": "ELECTION_2024",
        }

        stress_regime = st.selectbox(
            "Select Crisis Scenario",
            options=list(stress_scenario_map.keys()),
            index=0,
        )
        selected_regime_key = stress_scenario_map.get(stress_regime, "COVID_2020")

        st.markdown("---")
        st.markdown(
            "<div style='text-align:center; color:#78716c; font-size:0.75rem; line-height:1.5;'>"
            "<strong>Market-Neutral Hedge Builder</strong><br>"
            "Autonomous Multi-Agent System<br>"
            "Zero-Hallucination Quantitative Engine"
            "</div>",
            unsafe_allow_html=True,
        )

    return {
        "capital": float(capital),
        "lookback_days": lookback_days,
        "benchmark": benchmark.strip() or "^NSEI",
        "stress_regime": selected_regime_key,
    }


# ══════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION CONTROLLER
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Application entry point and execution coordinator."""
    params = _render_sidebar()

    # ── Hero Header ──────────────────────────────────────────────────────
    st.markdown("""
    <div class="hero-header">
        <h1>🛡️ Market-Neutral Hedge Builder</h1>
        <p>Autonomous Multi-Agent Quantitative Architecture &nbsp;|&nbsp; Zero-Hallucination Risk Engineering</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Thesis Input Form ────────────────────────────────────────────────
    col_input, col_btn = st.columns([4, 1], gap="medium")
    with col_input:
        thesis_input = st.text_input(
            "Enter your market thesis",
            placeholder="Bullish on Indian IT, terrified of a US recession crash",
            label_visibility="collapsed",
            key="thesis_text_input",
        )
    with col_btn:
        run_clicked = st.button("🚀 Build Hedge", type="primary", use_container_width=True)

    # ── Trigger Pipeline Run On User Submission ──────────────────────────
    if run_clicked:
        thesis_clean = (thesis_input or "").strip()
        if not thesis_clean:
            st.warning("⚠️ Please enter a market thesis before building a hedge.")
        elif not _ENGINE_AVAILABLE:
            st.error("❌ Quantitative pipeline (`agents.graph.run_hedge_builder`) is unavailable in the environment.")
            st.session_state["view_model"] = None
            st.session_state["pipeline_error"] = "Engine module unavailable"
        else:
            # Clear older results and errors
            st.session_state["pipeline_error"] = None
            st.session_state["pipeline_traceback"] = None
            st.session_state["view_model"] = None

            with st.spinner("🤖 Autonomous Multi-Agent Pipeline executing... Math Engine running deterministic models..."):
                try:
                    logger.info("Executing run_hedge_builder for thesis: '%s'", thesis_clean)
                    raw_state = run_hedge_builder(
                        thesis=thesis_clean,
                        benchmark=params["benchmark"],
                        lookback_days=params["lookback_days"],
                        stress_regime=params["stress_regime"],
                    )

                    if not isinstance(raw_state, dict):
                        raise TypeError(f"Expected dict return from run_hedge_builder, got {type(raw_state).__name__}")

                    # Transform pipeline state to structured dashboard ViewModel
                    view_model = map_state_to_dashboard(raw_state, capital=params["capital"])
                    st.session_state["view_model"] = view_model
                    st.session_state["last_thesis"] = thesis_clean
                    logger.info("Pipeline completed successfully and ViewModel mapped.")

                except Exception as exc:
                    logger.exception("Pipeline execution failed: %s", exc)
                    st.session_state["pipeline_error"] = str(exc)
                    st.session_state["pipeline_traceback"] = traceback.format_exc()
                    st.session_state["view_model"] = None

    # ── Display Pipeline Error If Any ────────────────────────────────────
    if st.session_state.get("pipeline_error"):
        st.error(f"❌ **Hedge Builder Pipeline Error**: {st.session_state['pipeline_error']}")
        if st.session_state.get("pipeline_traceback"):
            with st.expander("🔍 Pipeline Error Traceback"):
                st.code(st.session_state["pipeline_traceback"])
        return

    # ── Display Results Or Landing Screen ────────────────────────────────
    current_vm = st.session_state.get("view_model")
    if current_vm is not None:
        _render_dashboard(current_vm)
    else:
        # Clean landing state when no run has executed yet
        st.markdown(
            """
            <div style='text-align:center; padding:4rem 1rem; color:#78716c;'>
                <p style='font-size:3rem; margin-bottom:0.5rem;'>🛡️</p>
                <p style='font-size:1.15rem; font-weight:600; color:#44403c;'>Enter an investment thesis and hit <strong>Build Hedge</strong> to begin.</p>
                <p style='font-size:0.85rem; margin-top:0.5rem; color:#78716c;'>
                    Example: <em>"I am bullish on Indian IT companies but want protection against a broad market crash."</em>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════
# DASHBOARD TEAR-SHEET RENDERER
# ══════════════════════════════════════════════════════════════════════════

def _render_dashboard(vm: DashboardViewModel) -> None:
    """Render the full quantitative hedge tear-sheet from the ViewModel."""

    # ── Section 1: Verification Summary & Verdict ────────────────────────
    render_verification_summary(vm)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 2: Before vs After Hedging Metric Cards ──────────────────
    st.markdown('<div class="section-title">📊 Quantitative Risk & Performance Metrics</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="medium")
    with c1:
        render_metric_card(
            label="Portfolio Beta",
            unhedged_val=vm.metrics.unhedged_beta,
            hedged_val=vm.metrics.hedged_beta,
            format_str="{:.2f}",
            invert=True,
            accent_class="mc-beta",
            help_text="Systematic risk sensitivity relative to the market benchmark.",
        )
    with c2:
        render_metric_card(
            label="Max Drawdown",
            unhedged_val=vm.metrics.unhedged_max_drawdown,
            hedged_val=vm.metrics.hedged_max_drawdown,
            format_str="{:.1f}%",
            format_pct=True,
            invert=True,
            accent_class="mc-dd",
            help_text="Worst peak-to-trough decline over the estimation window.",
        )
    with c3:
        render_metric_card(
            label="Sharpe Ratio",
            unhedged_val=vm.metrics.unhedged_sharpe,
            hedged_val=vm.metrics.hedged_sharpe,
            format_str="{:.2f}",
            invert=False,
            accent_class="mc-sharpe",
            help_text="Excess return per unit of total risk (annualized).",
        )
    with c4:
        render_metric_card(
            label="Sortino Ratio",
            unhedged_val=vm.metrics.unhedged_sortino,
            hedged_val=vm.metrics.hedged_sortino,
            format_str="{:.2f}",
            invert=False,
            accent_class="mc-sortino",
            help_text="Excess return per unit of downside deviation (annualized).",
        )

    # Supplementary metrics row (Volatility & 95% VaR)
    c5, c6 = st.columns(2, gap="medium")
    with c5:
        render_metric_card(
            label="Annualized Volatility",
            unhedged_val=vm.metrics.unhedged_volatility,
            hedged_val=vm.metrics.hedged_volatility,
            format_pct=True,
            invert=True,
            help_text="Standard deviation of daily returns annualized.",
        )
    with c6:
        render_metric_card(
            label="Value at Risk (95% VaR)",
            unhedged_val=vm.metrics.unhedged_var_95,
            hedged_val=vm.metrics.hedged_var_95,
            format_pct=True,
            invert=True,
            help_text="Parametric daily 95% Value at Risk.",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 3: Performance & Risk Analytics Charts ───────────────────
    st.markdown('<div class="section-title">📈 Performance & Risk Analytics</div>', unsafe_allow_html=True)

    row1_left, row1_right = st.columns(2, gap="medium")
    with row1_left:
        # Prepare cumulative returns data dict safely
        cum_data: Optional[Dict[str, Any]] = None
        raw_cum = vm.portfolio.cumulative_returns
        if isinstance(raw_cum, dict):
            if "dates" in raw_cum and ("hedged_cum" in raw_cum or "unhedged_cum" in raw_cum):
                cum_data = raw_cum
            elif "hedged" in raw_cum or "unhedged" in raw_cum:
                h_ser = raw_cum.get("hedged")
                u_ser = raw_cum.get("unhedged")
                dates = getattr(h_ser, "index", getattr(u_ser, "index", None))
                cum_data = {
                    "dates": dates,
                    "hedged_cum": getattr(h_ser, "values", h_ser) if h_ser is not None else None,
                    "unhedged_cum": getattr(u_ser, "values", u_ser) if u_ser is not None else None,
                    "nifty_cum": raw_cum.get("nifty") or raw_cum.get("nifty_cum") or raw_cum.get("benchmark"),
                }
        elif isinstance(raw_cum, pd.DataFrame) and not raw_cum.empty:
            cum_data = {
                "dates": raw_cum.index,
                "hedged_cum": raw_cum.get("Hedged Portfolio", raw_cum.get("hedged", None)),
                "unhedged_cum": raw_cum.get("Unhedged Long", raw_cum.get("unhedged", None)),
                "nifty_cum": raw_cum.get("NIFTY 50", raw_cum.get("benchmark", None)),
            }

        render_cumulative_chart(cum_data)

    with row1_right:
        render_beta_chart(vm.quant.rolling_beta)

    # ── Section 4: Statistical Cointegration & Correlation ───────────────
    st.markdown('<div class="section-title">🔬 Statistical Cointegration & Correlation</div>', unsafe_allow_html=True)
    row2_left, row2_right = st.columns(2, gap="medium")
    with row2_left:
        render_zscore_chart(vm.quant.spread_zscore)
    with row2_right:
        render_correlation_heatmap(vm.quant.correlation_matrix)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 5: Pair Fundamentals Comparison ──────────────────────────
    st.markdown('<div class="section-title">🏢 Pair Fundamental Comparison</div>', unsafe_allow_html=True)
    render_pair_details(vm)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 6: News Intelligence Panel ───────────────────────────────
    st.markdown('<div class="section-title">📰 News Intelligence & Catalyst Audit</div>', unsafe_allow_html=True)
    long_ticker = vm.run_info.selected_long or "Long Leg"
    short_ticker = vm.run_info.selected_short or "Short Hedge"
    long_news = load_cached_news_for_ticker(long_ticker)
    short_news = load_cached_news_for_ticker(short_ticker)
    render_news_panel(
        long_news=long_news,
        short_news=short_news,
        long_ticker=long_ticker,
        short_ticker=short_ticker,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 7: Multi-Agent Execution Trace ───────────────────────────
    st.markdown('<div class="section-title">🤖 Multi-Agent Execution Audit Trail</div>', unsafe_allow_html=True)
    render_agent_trace(vm)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 8: CRO Executive Summary & F&O Execution Table ───────────
    st.markdown('<div class="section-title">📋 Institutional CRO Report & Execution Plan</div>', unsafe_allow_html=True)
    col_cro, col_fno = st.columns([3, 2], gap="medium")
    with col_cro:
        st.markdown("#### 📝 Chief Risk Officer Memo")
        if vm.reporting.cro_report:
            st.markdown(
                f'<div class="cro-report">{vm.reporting.cro_report}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("CRO executive summary memo is unavailable for this run.")

    with col_fno:
        st.markdown("#### 📦 F&O Lot-Size Execution Plan")
        render_fno_table(vm.portfolio.fno_execution)

    st.markdown("<br>", unsafe_allow_html=True)


# ── Direct Entry Execution ────────────────────────────────────────────────
if __name__ == "__main__":
    main()
else:
    main()
