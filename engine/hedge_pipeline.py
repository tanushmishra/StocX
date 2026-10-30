"""End-to-end hedge analysis pipeline for the Market-Neutral Hedge Builder.

Orchestrates every module in the engine to produce a single comprehensive
results dict for a long–short pair.

Pipeline stages:

1. **Data ingestion** – fetch prices via ``data_fetcher``.
2. **Return computation** – simple daily percentage returns.
3. **Beta estimation** – static, EWMA, and rolling betas via
   ``beta_calculator``.
4. **Cointegration analysis** – Engle-Granger test, spread Z-score, and
   O-U half-life via ``cointegration``.
5. **Portfolio construction** – beta-neutral weights and F&O lot sizing
   via ``portfolio``.
6. **Backtesting** – hedged vs. unhedged metrics via ``backtester``.
7. **Stress testing** – crisis-regime backtests via ``backtester``.
8. **Verification** – adversarial guardrails via ``verifier``.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from engine.backtester import backtest_pair, calc_metrics, stress_test, _STRESS_REGIMES
from engine.beta_calculator import (
    compute_ewma_beta,
    compute_rolling_beta,
    compute_static_beta,
)
from engine.cointegration import (
    compute_spread_zscore,
    engle_granger_test,
    ou_half_life,
)
from engine.data_fetcher import fetch_prices, get_fno_lot_sizes
from engine.portfolio import (
    compute_beta_neutral_weights,
    compute_correlation_matrix,
    convert_to_fno_lots,
)
from engine.verifier import verify_pair

logger = logging.getLogger(__name__)


def run_full_hedge_analysis(
    long_ticker: str,
    short_ticker: str,
    benchmark: str,
    start_date: str,
    end_date: str,
    capital: float = 100_000,
) -> dict:
    """Run the complete market-neutral hedge analysis pipeline.

    This function is the single entry-point for the engine.  Given a
    candidate long–short pair and a benchmark, it:

    1. Fetches historical prices and computes returns.
    2. Estimates static, EWMA, and rolling betas.
    3. Tests for cointegration and computes spread metrics.
    4. Solves for beta-neutral portfolio weights.
    5. Converts weights to F&O lot positions (if lot sizes are known).
    6. Back-tests the hedged portfolio against the unhedged baseline.
    7. Runs stress tests over all predefined crisis regimes.
    8. Applies adversarial verification guardrails.

    Args:
        long_ticker: Yahoo Finance symbol for the long leg
            (e.g. ``"TCS.NS"``).
        short_ticker: Yahoo Finance symbol for the short leg
            (e.g. ``"INFY.NS"``).
        benchmark: Yahoo Finance symbol for the market benchmark
            (e.g. ``"^NSEI"``).
        start_date: Analysis start date (``YYYY-MM-DD``).
        end_date: Analysis end date (``YYYY-MM-DD``).
        capital: Total notional capital for lot-size calculation
            (default ₹1,00,000).

    Returns:
        A dict with sections:

        * ``prices`` – aligned price DataFrame.
        * ``returns`` – aligned return DataFrame.
        * ``betas`` – static, EWMA (last value), and rolling (last value)
          for both legs.
        * ``correlation`` – pairwise Pearson correlation.
        * ``cointegration`` – Engle-Granger test result.
        * ``spread_zscore`` – rolling Z-score series.
        * ``ou_half_life`` – Ornstein-Uhlenbeck half-life.
        * ``weights`` – beta-neutral weights dict.
        * ``fno_positions`` – F&O lot breakdown (if lot sizes known).
        * ``backtest`` – hedged vs. unhedged metrics.
        * ``stress_tests`` – per-regime stress-test results.
        * ``verification`` – guardrail pass/fail summary.

    Raises:
        ValueError: If no price data can be fetched or alignment yields
            an empty frame.

    Example:
        >>> results = run_full_hedge_analysis(
        ...     "TCS.NS", "INFY.NS", "^NSEI",
        ...     "2020-01-01", "2024-01-01",
        ...     capital=500_000,
        ... )
        >>> results["verification"]["passed"]
        True
    """
    logger.info(
        "═══ Pipeline START: %s / %s  bench=%s  [%s → %s]  capital=₹%,.0f ═══",
        long_ticker,
        short_ticker,
        benchmark,
        start_date,
        end_date,
        capital,
    )

    # ------------------------------------------------------------------
    # 1. Data ingestion
    # ------------------------------------------------------------------
    logger.info("Stage 1/8 — Fetching prices …")
    tickers = [long_ticker, short_ticker, benchmark]
    prices = fetch_prices(tickers, start_date, end_date)

    # Ensure all three columns exist.
    for t in tickers:
        if t not in prices.columns:
            raise ValueError(f"Missing price data for {t}")

    # ------------------------------------------------------------------
    # 2. Return computation  (simple daily percentage returns)
    # ------------------------------------------------------------------
    logger.info("Stage 2/8 — Computing returns …")
    returns = prices.pct_change().dropna()

    long_r = returns[long_ticker]
    short_r = returns[short_ticker]
    mkt_r = returns[benchmark]

    # ------------------------------------------------------------------
    # 3. Beta estimation
    # ------------------------------------------------------------------
    logger.info("Stage 3/8 — Estimating betas …")
    beta_long_static = compute_static_beta(long_r, mkt_r)
    beta_short_static = compute_static_beta(short_r, mkt_r)

    ewma_long = compute_ewma_beta(long_r, mkt_r)
    ewma_short = compute_ewma_beta(short_r, mkt_r)

    rolling_long = compute_rolling_beta(long_r, mkt_r)
    rolling_short = compute_rolling_beta(short_r, mkt_r)

    betas = {
        "long": {
            "static": beta_long_static,
            "ewma_last": float(ewma_long.dropna().iloc[-1]) if not ewma_long.dropna().empty else None,
            "rolling_last": float(rolling_long.dropna().iloc[-1]) if not rolling_long.dropna().empty else None,
        },
        "short": {
            "static": beta_short_static,
            "ewma_last": float(ewma_short.dropna().iloc[-1]) if not ewma_short.dropna().empty else None,
            "rolling_last": float(rolling_short.dropna().iloc[-1]) if not rolling_short.dropna().empty else None,
        },
        "ewma_long_series": ewma_long,
        "ewma_short_series": ewma_short,
        "rolling_long_series": rolling_long,
        "rolling_short_series": rolling_short,
    }

    # ------------------------------------------------------------------
    # 4. Cointegration & spread analysis
    # ------------------------------------------------------------------
    logger.info("Stage 4/8 — Cointegration analysis …")
    # Cointegration on log prices
    coint_result = engle_granger_test(
        np.log(prices[long_ticker]), np.log(prices[short_ticker])
    )

    spread_zs = compute_spread_zscore(
        prices[long_ticker], prices[short_ticker], window=60
    )

    # OU half-life on the log price ratio (the spread).
    log_spread = np.log(prices[long_ticker]) - np.log(prices[short_ticker])
    half_life = ou_half_life(log_spread)

    # Correlation between the two assets.
    pair_corr = float(returns[[long_ticker, short_ticker]].corr().iloc[0, 1])

    # Full correlation matrix across all tickers.
    corr_matrix = compute_correlation_matrix(returns)

    # ------------------------------------------------------------------
    # 5. Portfolio construction
    # ------------------------------------------------------------------
    logger.info("Stage 5/8 — Constructing portfolio …")
    # Use absolute values for weight computation (betas must be positive).
    bl = max(abs(beta_long_static), 0.01)
    bs = max(abs(beta_short_static), 0.01)
    weights = compute_beta_neutral_weights(bl, bs)

    # F&O lot conversion (best effort; skip if lot sizes unknown).
    lot_sizes = get_fno_lot_sizes()
    last_prices = {t: float(prices[t].iloc[-1]) for t in tickers}

    fno_weights = {
        long_ticker: weights["w_long"],
        short_ticker: weights["w_short"],
    }

    # Only attempt FNO conversion if both tickers have known lot sizes.
    fno_positions: dict | None = None
    if long_ticker in lot_sizes and short_ticker in lot_sizes:
        try:
            fno_positions = convert_to_fno_lots(
                fno_weights, capital, lot_sizes, last_prices
            )
        except ValueError as exc:
            logger.warning("FNO lot conversion skipped: %s", exc)
    else:
        logger.info(
            "F&O lot sizes not available for one or both tickers; "
            "skipping lot conversion."
        )

    # ------------------------------------------------------------------
    # 6. Backtesting
    # ------------------------------------------------------------------
    logger.info("Stage 6/8 — Backtesting …")
    bt = backtest_pair(
        long_r,
        short_r,
        mkt_r,
        weights["w_long"],
        weights["w_short"],
    )

    # ------------------------------------------------------------------
    # 7. Stress testing
    # ------------------------------------------------------------------
    logger.info("Stage 7/8 — Stress testing …")
    stress_results: dict[str, dict] = {}
    for regime in _STRESS_REGIMES:
        try:
            stress_results[regime] = stress_test(
                long_ticker, short_ticker, benchmark, regime
            )
        except (ValueError, KeyError, Exception) as exc:
            logger.warning("Stress test [%s] skipped: %s", regime, exc)
            stress_results[regime] = {"error": str(exc)}

    # ------------------------------------------------------------------
    # 8. Verification
    # ------------------------------------------------------------------
    logger.info("Stage 8/8 — Verification …")
    pair_metrics = {
        "correlation": pair_corr,
        "cointegration_pvalue": coint_result["p_value"],
    }
    verification = verify_pair(
        pair_metrics,
        bt["unhedged_metrics"],
        bt["hedged_metrics"],
    )

    # ------------------------------------------------------------------
    # Assemble final output
    # ------------------------------------------------------------------
    result = {
        "long_ticker": long_ticker,
        "short_ticker": short_ticker,
        "benchmark": benchmark,
        "start_date": start_date,
        "end_date": end_date,
        "capital": capital,
        "prices": prices,
        "returns": returns,
        "betas": betas,
        "correlation": pair_corr,
        "correlation_matrix": corr_matrix,
        "cointegration": coint_result,
        "spread_zscore": spread_zs,
        "ou_half_life": half_life,
        "weights": weights,
        "fno_positions": fno_positions,
        "backtest": {
            "hedged_metrics": bt["hedged_metrics"],
            "unhedged_metrics": bt["unhedged_metrics"],
            "hedged_returns": bt["hedged_returns"],
            "unhedged_returns": bt["unhedged_returns"],
        },
        "stress_tests": stress_results,
        "verification": verification,
    }

    logger.info(
        "═══ Pipeline DONE — Verification: %s ═══",
        "PASSED ✅" if verification["passed"] else "FAILED ❌",
    )
    return result
