"""Comprehensive backtesting engine for the Market-Neutral Hedge Builder.

Provides:

* **Single-pair backtest** — compares hedged (beta-neutral) vs. unhedged
  (long-only) return streams, computing a full suite of risk/return metrics.
* **Risk metrics calculator** — total return, max drawdown, Sharpe, Sortino,
  VaR 95 %, realised beta, and the full cumulative-return curve.
* **Stress-test runner** — re-runs the backtest over predefined crisis
  regimes (GFC 2008, COVID 2020, Tech Sell-off 2022, Election 2024).

All arithmetic uses ``numpy``/``pandas``/``scipy``—no LLMs or stochastic
sampling.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from engine.beta_calculator import compute_static_beta
from engine.data_fetcher import fetch_prices

logger = logging.getLogger(__name__)

# Annualisation constant (trading days per year for Indian markets).
_TRADING_DAYS_PER_YEAR: int = 252

# Predefined stress-test windows.
_STRESS_REGIMES: dict[str, tuple[str, str]] = {
    "2008_GFC": ("2008-01-01", "2009-03-31"),
    "COVID_2020": ("2020-01-01", "2020-06-30"),
    "TECH_SELLOFF_2022": ("2022-01-01", "2022-12-31"),
    "ELECTION_2024": ("2024-05-15", "2024-06-15"),
}


# ---------------------------------------------------------------------------
# Risk / return metrics
# ---------------------------------------------------------------------------


def calc_metrics(
    returns: pd.Series,
    market_returns: pd.Series,
    rf_rate: float = 0.068,
) -> dict:
    """Compute a comprehensive suite of risk and return metrics.

    Args:
        returns: Daily return series of the strategy or asset.
        market_returns: Daily return series of the market benchmark.
        rf_rate: Annual risk-free rate (default 6.8 %, approximate
            Indian T-bill yield).

    Returns:
        A dict with keys:

        * ``total_return`` – cumulative return over the period (fraction).
        * ``max_drawdown`` – worst peak-to-trough decline (negative number).
        * ``annual_volatility`` – annualised standard deviation of daily
          returns.
        * ``sharpe_ratio`` – annualised Sharpe ratio (excess return / vol).
        * ``sortino_ratio`` – annualised Sortino ratio (excess return /
          downside deviation).
        * ``realized_beta`` – full-sample beta vs. *market_returns*.
        * ``var_95`` – daily Value at Risk at the 95 % confidence level
          (left-tail).
        * ``cumulative_returns_series`` – ``pd.Series`` of cumulative
          returns suitable for plotting.

    Raises:
        ValueError: If *returns* is empty.

    Example:
        >>> m = calc_metrics(strategy_rets, nifty_rets, rf_rate=0.068)
        >>> m["sharpe_ratio"]
        1.34
    """
    if returns.empty:
        raise ValueError("returns series must not be empty.")

    clean_returns = returns.dropna()
    clean_market = market_returns.reindex(clean_returns.index).dropna()
    # Re-align after market dropna.
    common_idx = clean_returns.index.intersection(clean_market.index)
    clean_returns = clean_returns.loc[common_idx]
    clean_market = clean_market.loc[common_idx]

    # --- Cumulative returns (growth of ₹1) ---
    cum_returns = (1 + clean_returns).cumprod()

    # --- Total return ---
    total_return = float(cum_returns.iloc[-1] - 1) if len(cum_returns) else 0.0

    # --- Max drawdown ---
    running_max = cum_returns.cummax()
    drawdowns = (cum_returns - running_max) / running_max
    max_drawdown = float(drawdowns.min())

    # --- Annualised volatility ---
    annual_vol = float(clean_returns.std(ddof=1) * np.sqrt(_TRADING_DAYS_PER_YEAR))

    # --- Daily risk-free rate ---
    rf_daily = rf_rate / _TRADING_DAYS_PER_YEAR

    # --- Sharpe ratio ---
    excess = clean_returns - rf_daily
    if annual_vol != 0.0:
        sharpe = float(excess.mean() / clean_returns.std(ddof=1) * np.sqrt(_TRADING_DAYS_PER_YEAR))
    else:
        sharpe = 0.0

    # --- Sortino ratio ---
    downside_diff = np.minimum(0.0, excess)
    downside_dev = float(np.sqrt(np.mean(downside_diff ** 2)))
    if downside_dev != 0.0:
        sortino = float(
            excess.mean()
            / downside_dev
            * np.sqrt(_TRADING_DAYS_PER_YEAR)
        )
    else:
        sortino = 0.0

    # --- Realised beta ---
    try:
        realized_beta = compute_static_beta(clean_returns, clean_market)
    except ValueError:
        realized_beta = np.nan

    # --- VaR 95 % (historical, left tail) ---
    var_95 = float(np.percentile(clean_returns, 5))

    return {
        "total_return": round(total_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "annual_volatility": round(annual_vol, 6),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "realized_beta": round(float(realized_beta), 4) if not np.isnan(realized_beta) else None,
        "var_95": round(var_95, 6),
        "cumulative_returns_series": cum_returns,
    }


# ---------------------------------------------------------------------------
# Pair backtester
# ---------------------------------------------------------------------------


def backtest_pair(
    long_returns: pd.Series,
    short_returns: pd.Series,
    market_returns: pd.Series,
    w_long: float,
    w_short: float,
    rf_rate: float = 0.068,
) -> dict:
    """Backtest a long–short pair and compare hedged vs. unhedged performance.

    The **hedged** (beta-neutral) portfolio return at each time step is:

    .. math::

        R^H_t = w_L \\, R^L_t + w_S \\, R^S_t

    Note *w_short* is expected to be **negative** (short direction).

    The **unhedged** baseline is simply the long-leg returns.

    Args:
        long_returns: Daily return series of the long leg.
        short_returns: Daily return series of the short leg.
        market_returns: Daily return series of the benchmark.
        w_long: Weight of the long leg (positive).
        w_short: Weight of the short leg (negative).
        rf_rate: Annual risk-free rate (default 6.8 %).

    Returns:
        A dict containing:

        * ``hedged_returns`` – daily hedged return series.
        * ``unhedged_returns`` – daily unhedged (long-only) return series.
        * ``hedged_metrics`` – output of :func:`calc_metrics` on the
          hedged stream.
        * ``unhedged_metrics`` – output of :func:`calc_metrics` on the
          unhedged stream.

    Raises:
        ValueError: If input series are empty.

    Example:
        >>> result = backtest_pair(long_r, short_r, mkt_r, 0.4, -0.6)
        >>> result["hedged_metrics"]["sharpe_ratio"]
        1.5
    """
    # Align all series on a common date index.
    aligned = pd.concat(
        {
            "long": long_returns,
            "short": short_returns,
            "market": market_returns,
        },
        axis=1,
    ).dropna()

    if aligned.empty:
        raise ValueError("No overlapping data after alignment.")

    # Hedged portfolio return: w_L * R_L + w_S * R_S  (w_S < 0)
    hedged = w_long * aligned["long"] + w_short * aligned["short"]
    hedged.name = "hedged_return"

    # Unhedged is simply the long leg.
    unhedged = aligned["long"].copy()
    unhedged.name = "unhedged_return"

    hedged_metrics = calc_metrics(hedged, aligned["market"], rf_rate)
    unhedged_metrics = calc_metrics(unhedged, aligned["market"], rf_rate)

    logger.info(
        "Backtest done: hedged Sharpe=%.2f  unhedged Sharpe=%.2f",
        hedged_metrics["sharpe_ratio"],
        unhedged_metrics["sharpe_ratio"],
    )

    return {
        "hedged_returns": hedged,
        "unhedged_returns": unhedged,
        "hedged_metrics": hedged_metrics,
        "unhedged_metrics": unhedged_metrics,
    }


# ---------------------------------------------------------------------------
# Stress tester
# ---------------------------------------------------------------------------


def stress_test(
    long_ticker: str,
    short_ticker: str,
    benchmark: str,
    regime: str,
) -> dict:
    """Run a backtest over a predefined crisis regime.

    This is a convenience wrapper that:

    1. Looks up the date window for *regime*.
    2. Fetches prices for the long/short tickers and benchmark.
    3. Computes simple returns and a quick static beta for weights.
    4. Calls :func:`backtest_pair`.

    Args:
        long_ticker: Yahoo Finance symbol for the long leg.
        short_ticker: Yahoo Finance symbol for the short leg.
        benchmark: Yahoo Finance symbol for the market benchmark
            (e.g. ``"^NSEI"``).
        regime: One of ``"2008_GFC"``, ``"COVID_2020"``,
            ``"TECH_SELLOFF_2022"``, ``"ELECTION_2024"``.

    Returns:
        A dict with keys ``regime``, ``start``, ``end``,
        ``hedged_metrics``, ``unhedged_metrics``, and
        ``hedged_cumulative`` / ``unhedged_cumulative`` return series.

    Raises:
        KeyError: If *regime* is not recognised.
        ValueError: If price data is unavailable for the regime window.

    Example:
        >>> res = stress_test("TCS.NS", "INFY.NS", "^NSEI", "COVID_2020")
        >>> res["hedged_metrics"]["max_drawdown"]
        -0.08
    """
    if regime not in _STRESS_REGIMES:
        available = ", ".join(sorted(_STRESS_REGIMES))
        raise KeyError(f"Unknown regime '{regime}'. Available: {available}")

    start, end = _STRESS_REGIMES[regime]
    logger.info("Stress test [%s]: %s → %s", regime, start, end)

    # Fetch prices for the regime window.
    tickers = [long_ticker, short_ticker, benchmark]
    prices = fetch_prices(tickers, start, end)

    # Simple daily returns.
    returns = prices.pct_change().dropna()

    long_r = returns[long_ticker]
    short_r = returns[short_ticker]
    mkt_r = returns[benchmark]

    # Quick beta-neutral weights using static beta over the regime.
    beta_l = compute_static_beta(long_r, mkt_r)
    beta_s = compute_static_beta(short_r, mkt_r)

    # Handle edge case: negative or zero betas.
    beta_l = max(beta_l, 0.01)
    beta_s = max(beta_s, 0.01)

    w_long = beta_s / (beta_l + beta_s)
    w_short = -(beta_l / (beta_l + beta_s))

    bt = backtest_pair(long_r, short_r, mkt_r, w_long, w_short)

    return {
        "regime": regime,
        "start": start,
        "end": end,
        "hedged_metrics": bt["hedged_metrics"],
        "unhedged_metrics": bt["unhedged_metrics"],
        "hedged_cumulative": bt["hedged_metrics"]["cumulative_returns_series"],
        "unhedged_cumulative": bt["unhedged_metrics"]["cumulative_returns_series"],
    }
