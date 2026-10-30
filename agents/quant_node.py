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

from agents.state import HedgeBuilderState

logger = logging.getLogger(__name__)


def quant_engine_node(state: HedgeBuilderState) -> dict:
    """Run the complete deterministic quant pipeline on the selected pair.

    This function:

    1. Fetches price data for the long, short, and benchmark tickers.
    2. Computes beta (static + EWMA), correlation, and cointegration metrics.
    3. Derives beta-neutral portfolio weights and converts to F&O lots.
    4. Backtests the hedged pair over the lookback window.
    5. Runs a stress test for the chosen regime.
    6. Packs all results into a partial state update.

    **No LLM is invoked.** Every value is computed by the ``engine`` package.

    Args:
        state: Current graph state.  Requires ``selected_long``,
            ``selected_short``, ``benchmark``, ``lookback_days``, and
            ``stress_regime`` to be populated.

    Returns:
        Partial state dict containing ``pair_metrics``, ``weights``,
        ``unhedged_stats``, ``hedged_stats``, ``stress_results``,
        ``cumulative_returns``, ``fno_execution``, and an informational
        assistant message.

    Raises:
        Does not raise – all exceptions are caught and surfaced as
        degraded results so the pipeline can continue to the verifier.
    """
    long_ticker = state.selected_long
    short_ticker = state.selected_short
    benchmark = state.benchmark
    lookback = state.lookback_days
    stress_regime = state.stress_regime

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

    # ── 1. Fetch price data ────────────────────────────────────────────
    try:
        from engine.data_fetcher import fetch_prices

        prices = fetch_prices(
            tickers=[long_ticker, short_ticker, benchmark],
            lookback_days=lookback,
        )
        logger.info("QuantEngine ▸ Price data fetched (%d rows).", len(prices))
    except Exception as exc:
        msg = f"Price fetch failed: {exc}"
        logger.error("QuantEngine ▸ %s", msg)
        errors.append(msg)
        prices = None

    # ── 2. Beta computation ────────────────────────────────────────────
    if prices is not None:
        try:
            from engine.beta_calculator import (
                compute_ewma_beta,
                compute_rolling_beta,
                compute_static_beta,
            )

            static_beta_long = compute_static_beta(long_ticker, benchmark, prices)
            static_beta_short = compute_static_beta(short_ticker, benchmark, prices)
            ewma_beta_long = compute_ewma_beta(long_ticker, benchmark, prices)
            ewma_beta_short = compute_ewma_beta(short_ticker, benchmark, prices)
            rolling_beta_long = compute_rolling_beta(long_ticker, benchmark, prices)
            rolling_beta_short = compute_rolling_beta(short_ticker, benchmark, prices)

            pair_metrics["static_beta_long"] = static_beta_long
            pair_metrics["static_beta_short"] = static_beta_short
            pair_metrics["ewma_beta_long"] = ewma_beta_long
            pair_metrics["ewma_beta_short"] = ewma_beta_short
            pair_metrics["rolling_beta_long"] = rolling_beta_long
            pair_metrics["rolling_beta_short"] = rolling_beta_short

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
    if prices is not None:
        try:
            from engine.portfolio import compute_correlation_matrix

            corr_matrix = compute_correlation_matrix(
                [long_ticker, short_ticker, benchmark], prices
            )
            pair_metrics["correlation_matrix"] = corr_matrix
            # Extract pairwise correlation for quick reference
            pair_metrics["pair_correlation"] = corr_matrix.get(
                (long_ticker, short_ticker),
                corr_matrix.get(f"{long_ticker}_{short_ticker}", None),
            )
            logger.info("QuantEngine ▸ Correlation matrix computed.")
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

            coint_result = engle_granger_test(long_ticker, short_ticker, prices)
            spread_z = compute_spread_zscore(long_ticker, short_ticker, prices)
            half_life = ou_half_life(long_ticker, short_ticker, prices)

            pair_metrics["cointegration"] = coint_result
            pair_metrics["spread_zscore"] = spread_z
            pair_metrics["ou_half_life"] = half_life

            logger.info(
                "QuantEngine ▸ Cointegration p=%.4f, z-score=%.2f, HL=%.1f days",
                coint_result.get("p_value", -1),
                spread_z if isinstance(spread_z, (int, float)) else -999,
                half_life if isinstance(half_life, (int, float)) else -999,
            )
        except Exception as exc:
            msg = f"Cointegration analysis failed: {exc}"
            logger.error("QuantEngine ▸ %s", msg)
            errors.append(msg)

    # ── 5. Portfolio weights (beta-neutral) ────────────────────────────
    if prices is not None and pair_metrics:
        try:
            from engine.portfolio import compute_beta_neutral_weights, convert_to_fno_lots

            weights = compute_beta_neutral_weights(
                long_ticker=long_ticker,
                short_ticker=short_ticker,
                beta_long=pair_metrics.get("static_beta_long", 1.0),
                beta_short=pair_metrics.get("static_beta_short", 1.0),
            )

            fno_execution = convert_to_fno_lots(
                long_ticker=long_ticker,
                short_ticker=short_ticker,
                weights=weights,
            )

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
    if prices is not None:
        try:
            from engine.backtester import backtest_pair, calc_metrics

            bt_result = backtest_pair(
                long_ticker=long_ticker,
                short_ticker=short_ticker,
                weights=weights,
                prices=prices,
            )
            hedged_stats = calc_metrics(bt_result.get("hedged_returns", []))
            unhedged_stats = calc_metrics(bt_result.get("unhedged_returns", []))
            cumulative_returns = {
                "hedged": bt_result.get("hedged_cumulative", []),
                "unhedged": bt_result.get("unhedged_cumulative", []),
            }

            logger.info(
                "QuantEngine ▸ Backtest Sharpe: hedged=%.2f unhedged=%.2f",
                hedged_stats.get("sharpe", 0),
                unhedged_stats.get("sharpe", 0),
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
                long_ticker=long_ticker,
                short_ticker=short_ticker,
                weights=weights,
                prices=prices,
                regime=stress_regime,
            )
            logger.info(
                "QuantEngine ▸ Stress (%s) max-drawdown=%.2f%%",
                stress_regime,
                stress_results.get("max_drawdown_pct", 0),
            )
        except Exception as exc:
            msg = f"Stress test failed: {exc}"
            logger.error("QuantEngine ▸ %s", msg)
            errors.append(msg)

    # ── Build informational message ────────────────────────────────────
    status = "✅ All computations succeeded." if not errors else (
        "⚠️ Some computations failed:\n" + "\n".join(f"- {e}" for e in errors)
    )
    summary_msg = (
        f"**Quant Engine – Results**\n\n"
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
        "pair_metrics": pair_metrics,
        "weights": weights,
        "unhedged_stats": unhedged_stats,
        "hedged_stats": hedged_stats,
        "stress_results": stress_results,
        "cumulative_returns": cumulative_returns,
        "fno_execution": fno_execution,
        "messages": [{"role": "assistant", "content": summary_msg}],
    }
