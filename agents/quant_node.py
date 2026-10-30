"""Quant Execution Engine – Deterministic tool node (NO LLM).

This module contains a single **pure-Python** function that orchestrates calls
to the deterministic ``engine`` package.  It is wired into the LangGraph as a
regular node (not an agent) so that:

* Every number is reproducible given the same inputs.
* The LLM nodes can trust these results as ground truth.
* There is zero risk of hallucinated statistics.

Computations performed
----------------------
1. **Beta**: static (OLS), EWMA, and rolling.
2. **Correlation**: Pearson correlation matrix of the pair vs. benchmark.
3. **Cointegration**: Engle-Granger test, spread z-score, OU half-life.
4. **Portfolio construction**: Beta-neutral weights, F&O lot conversion.
5. **Backtest**: Full-period pair backtest with Sharpe, max-drawdown, etc.
6. **Stress test**: Performance under the selected stress regime.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from agents.state import HedgeBuilderState

logger = logging.getLogger(__name__)


def _get(state: Any, key: str, default: Any = None) -> Any:
    """Safely extract an attribute or dict key from state."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def quant_engine_node(state: HedgeBuilderState | dict[str, Any]) -> dict:
    """Run the complete deterministic quant pipeline on the selected pair.

    This function:

    1. Fetches price data for the long, short, and benchmark tickers.
    2. Identifies data provenance (yfinance, cache, or synthetic fallback).
    3. Computes beta (static + EWMA), correlation, and cointegration metrics.
    4. Derives beta-neutral portfolio weights and converts to F&O lots.
    5. Backtests the hedged pair over the lookback window.
    6. Runs a stress test for the chosen regime.
    7. Packs all results into a partial state update.

    **No LLM is invoked.** Every value is computed by the ``engine`` package.

    Args:
        state: Current graph state.  Requires ``selected_long``,
            ``selected_short``, ``benchmark``, ``lookback_days``, and
            ``stress_regime`` to be populated.

    Returns:
        Partial state dict containing ``data_source``, ``pair_metrics``,
        ``weights``, ``unhedged_stats``, ``hedged_stats``, ``stress_results``,
        ``cumulative_returns``, ``fno_execution``, and an informational
        assistant message.

    Raises:
        Does not raise – all exceptions are caught and surfaced as
        degraded results so the pipeline can continue to the verifier.
    """
    long_ticker = _get(state, "selected_long", "")
    short_ticker = _get(state, "selected_short", "")
    benchmark = _get(state, "benchmark", "^NSEI")
    lookback = _get(state, "lookback_days", 252)
    stress_regime = _get(state, "stress_regime", "COVID_2020")

    logger.info(
        "QuantEngine ▸ Running pipeline: LONG=%s SHORT=%s BENCH=%s "
        "LOOKBACK=%d STRESS=%s",
        long_ticker,
        short_ticker,
        benchmark,
        lookback,
        stress_regime,
    )

    # Accumulator for the partial state update
    pair_metrics: dict[str, Any] = {}
    weights: dict[str, Any] = {}
    unhedged_stats: dict[str, Any] = {}
    hedged_stats: dict[str, Any] = {}
    stress_results: dict[str, Any] = {}
    cumulative_returns: dict[str, Any] = {}
    fno_execution: dict[str, Any] = {}
    errors: list[str] = []  # non-fatal error log
    data_source: str = "yfinance"

    # ── 1. Fetch price data ────────────────────────────────────────────
    try:
        from engine.data_fetcher import fetch_prices

        prices = fetch_prices(
            tickers=[long_ticker, short_ticker, benchmark],
            lookback_days=lookback,
        )
        data_source = getattr(prices, "attrs", {}).get("data_source", "yfinance")
        logger.info(
            "QuantEngine ▸ Price data fetched (%d rows, data_source=%s).",
            len(prices),
            data_source,
        )
    except Exception as exc:
        msg = f"Price fetch failed: {exc}"
        logger.error("QuantEngine ▸ %s", msg)
        errors.append(msg)
        prices = None
        data_source = "synthetic_fallback"

    # ── 2. Returns and Beta computation ──────────────────────────────
    if prices is not None:
        try:
            from engine.beta_calculator import (
                compute_ewma_beta,
                compute_rolling_beta,
                compute_static_beta,
            )

            returns = prices.pct_change().dropna()
            long_r = returns[long_ticker]
            short_r = returns[short_ticker]
            mkt_r = returns[benchmark]

            static_beta_long = compute_static_beta(long_r, mkt_r)
            static_beta_short = compute_static_beta(short_r, mkt_r)
            ewma_beta_long = compute_ewma_beta(long_r, mkt_r)
            ewma_beta_short = compute_ewma_beta(short_r, mkt_r)
            rolling_beta_long = compute_rolling_beta(long_r, mkt_r)
            rolling_beta_short = compute_rolling_beta(short_r, mkt_r)

            pair_metrics["static_beta_long"] = static_beta_long
            pair_metrics["static_beta_short"] = static_beta_short
            pair_metrics["ewma_beta_long"] = (
                float(ewma_beta_long.dropna().iloc[-1])
                if not ewma_beta_long.dropna().empty
                else static_beta_long
            )
            pair_metrics["ewma_beta_short"] = (
                float(ewma_beta_short.dropna().iloc[-1])
                if not ewma_beta_short.dropna().empty
                else static_beta_short
            )
            pair_metrics["rolling_beta_long"] = (
                float(rolling_beta_long.dropna().iloc[-1])
                if not rolling_beta_long.dropna().empty
                else static_beta_long
            )
            pair_metrics["rolling_beta_short"] = (
                float(rolling_beta_short.dropna().iloc[-1])
                if not rolling_beta_short.dropna().empty
                else static_beta_short
            )

            logger.info(
                "QuantEngine ▸ Betas: long_static=%.3f short_static=%.3f",
                static_beta_long,
                static_beta_short,
            )
        except Exception as exc:
            msg = f"Beta computation failed: {exc}"
            logger.error("QuantEngine ▸ %s", msg)
            errors.append(msg)

    # ── 3. Correlation matrix ──────────────────────────────────────────
    if prices is not None and "returns" in locals():
        try:
            from engine.portfolio import compute_correlation_matrix

            corr_matrix = compute_correlation_matrix(
                returns[[long_ticker, short_ticker, benchmark]]
            )
            pair_corr = float(returns[[long_ticker, short_ticker]].corr().iloc[0, 1])

            pair_metrics["correlation_matrix"] = corr_matrix
            pair_metrics["pair_correlation"] = pair_corr
            pair_metrics["correlation"] = pair_corr
            logger.info("QuantEngine ▸ Correlation matrix computed: pair_corr=%.4f", pair_corr)
        except Exception as exc:
            msg = f"Correlation computation failed: {exc}"
            logger.error("QuantEngine ▸ %s", msg)
            errors.append(msg)

    # ── 4. Cointegration analysis ──────────────────────────────────────
    if prices is not None:
        try:
            from engine.cointegration import (
                compute_spread_zscore,
                engle_granger_test,
                ou_half_life,
            )

            coint_result = engle_granger_test(prices[long_ticker], prices[short_ticker])
            spread_z = compute_spread_zscore(prices[long_ticker], prices[short_ticker])
            log_spread = np.log(prices[long_ticker]) - np.log(prices[short_ticker])
            half_life = ou_half_life(log_spread)

            pair_metrics["cointegration"] = coint_result
            pair_metrics["cointegration_pvalue"] = coint_result.get("p_value", 1.0)
            pair_metrics["spread_zscore"] = (
                float(spread_z.dropna().iloc[-1]) if not spread_z.dropna().empty else 0.0
            )
            pair_metrics["ou_half_life"] = half_life

            logger.info(
                "QuantEngine ▸ Cointegration p=%.4f, z-score=%.2f, HL=%.1f days",
                coint_result.get("p_value", -1),
                pair_metrics["spread_zscore"],
                half_life if isinstance(half_life, (int, float)) else -999,
            )
        except Exception as exc:
            msg = f"Cointegration analysis failed: {exc}"
            logger.error("QuantEngine ▸ %s", msg)
            errors.append(msg)

    # ── 5. Portfolio weights (beta-neutral) ────────────────────────────
    if prices is not None and pair_metrics:
        try:
            from engine.data_fetcher import get_fno_lot_sizes
            from engine.portfolio import compute_beta_neutral_weights, convert_to_fno_lots

            bl = max(abs(pair_metrics.get("static_beta_long", 1.0)), 0.01)
            bs = max(abs(pair_metrics.get("static_beta_short", 1.0)), 0.01)
            weights = compute_beta_neutral_weights(bl, bs)

            lot_sizes = get_fno_lot_sizes()
            last_prices = {
                t: float(prices[t].iloc[-1])
                for t in [long_ticker, short_ticker, benchmark]
                if t in prices.columns
            }
            fno_weights = {
                long_ticker: weights["w_long"],
                short_ticker: weights["w_short"],
            }
            if long_ticker in lot_sizes and short_ticker in lot_sizes:
                try:
                    fno_execution = convert_to_fno_lots(
                        fno_weights, 100_000, lot_sizes, last_prices
                    )
                except Exception as exc:
                    logger.warning("QuantEngine ▸ FNO conversion skipped: %s", exc)

            logger.info(
                "QuantEngine ▸ Weights: long_wt=%.4f short_wt=%.4f",
                weights.get("long_weight", 0),
                weights.get("short_weight", 0),
            )
        except Exception as exc:
            msg = f"Portfolio weight computation failed: {exc}"
            logger.error("QuantEngine ▸ %s", msg)
            errors.append(msg)

    # ── 6. Backtest ────────────────────────────────────────────────────
    if prices is not None and "returns" in locals() and "weights" in locals() and "w_long" in weights:
        try:
            from engine.backtester import backtest_pair

            bt_result = backtest_pair(
                long_r,
                short_r,
                mkt_r,
                weights["w_long"],
                weights["w_short"],
            )
            hedged_stats = bt_result.get("hedged_metrics", {})
            unhedged_stats = bt_result.get("unhedged_metrics", {})
            cumulative_returns = {
                "hedged": bt_result.get("hedged_returns", pd.Series()),
                "unhedged": bt_result.get("unhedged_returns", pd.Series()),
            }

            logger.info(
                "QuantEngine ▸ Backtest Sharpe: hedged=%.2f unhedged=%.2f",
                hedged_stats.get("sharpe_ratio", 0),
                unhedged_stats.get("sharpe_ratio", 0),
            )
        except Exception as exc:
            msg = f"Backtest failed: {exc}"
            logger.error("QuantEngine ▸ %s", msg)
            errors.append(msg)

    # ── 7. Stress test ─────────────────────────────────────────────────
    if prices is not None:
        try:
            from engine.backtester import stress_test

            stress_results = stress_test(
                long_ticker,
                short_ticker,
                benchmark,
                stress_regime,
            )
            logger.info(
                "QuantEngine ▸ Stress (%s) max-drawdown=%.2f%%",
                stress_regime,
                stress_results.get("hedged_metrics", {}).get("max_drawdown", 0) * 100,
            )
        except Exception as exc:
            msg = f"Stress test failed: {exc}"
            logger.error("QuantEngine ▸ %s", msg)
            errors.append(msg)

    # ── Build informational message ────────────────────────────────────
    source_display = {
        "yfinance": "Live (Yahoo Finance)",
        "cache": "Cached Market Data (Local CSV)",
        "synthetic_fallback": "SYNTHETIC SIMULATION (NOT REAL DATA)",
    }.get(data_source, data_source)

    status = "All computations succeeded." if not errors else (
        "Some computations failed:\n" + "\n".join(f"- {e}" for e in errors)
    )
    summary_msg = (
        f"**Quant Engine – Results**\n\n"
        f"- **Data Source:** {source_display}\n"
        f"- **Pair:** {long_ticker} (long) / {short_ticker} (short)\n"
        f"- **Static β (long):** {pair_metrics.get('static_beta_long', 'N/A')}\n"
        f"- **Static β (short):** {pair_metrics.get('static_beta_short', 'N/A')}\n"
        f"- **Cointegration p-value:** "
        f"{pair_metrics.get('cointegration', {}).get('p_value', 'N/A')}\n"
        f"- **Spread z-score:** {pair_metrics.get('spread_zscore', 'N/A')}\n"
        f"- **OU half-life:** {pair_metrics.get('ou_half_life', 'N/A')} days\n"
        f"- **Hedged Sharpe:** {hedged_stats.get('sharpe', 'N/A')}\n"
        f"- **Stress max-DD:** {stress_results.get('max_drawdown_pct', 'N/A')}%\n\n"
        f"{status}"
    )

    return {
        "data_source": data_source,
        "pair_metrics": pair_metrics,
        "weights": weights,
        "unhedged_stats": unhedged_stats,
        "hedged_stats": hedged_stats,
        "stress_results": stress_results,
        "cumulative_returns": cumulative_returns,
        "fno_execution": fno_execution,
        "messages": [{"role": "assistant", "content": summary_msg}],
    }
