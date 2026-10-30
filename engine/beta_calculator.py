"""Beta computation module for the Market-Neutral Hedge Builder.

Provides three flavours of market-beta estimation:

* **Static (full-sample) OLS beta** via the covariance / variance formula.
* **EWMA beta** following the RiskMetrics exponentially-weighted approach.
* **Rolling-window beta** using a simple fixed-length sliding window.

All calculations are deterministic and rely exclusively on ``numpy`` and
``pandas``—no LLMs or stochastic sampling.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_static_beta(
    stock_returns: pd.Series,
    market_returns: pd.Series,
) -> float:
    """Compute the full-sample OLS beta of *stock_returns* against *market_returns*.

    Uses the classic covariance / variance formula:

    .. math::

        \\beta = \\frac{\\text{Cov}(R_s, R_m)}{\\text{Var}(R_m)}

    Args:
        stock_returns: Daily log- or simple-return series of the stock.
        market_returns: Daily log- or simple-return series of the market
            benchmark (e.g. NIFTY 50).

    Returns:
        The static beta as a float.

    Raises:
        ValueError: If the series are empty, have different lengths, or the
            market variance is zero (constant market returns).

    Example:
        >>> import pandas as pd, numpy as np
        >>> rng = np.random.default_rng(42)
        >>> mkt = pd.Series(rng.normal(0, 0.01, 252))
        >>> stk = 1.2 * mkt + pd.Series(rng.normal(0, 0.005, 252))
        >>> round(compute_static_beta(stk, mkt), 2)
        1.2
    """
    _validate_return_series(stock_returns, market_returns)

    # Align on shared dates and drop NaNs.
    aligned = pd.concat(
        {"stock": stock_returns, "market": market_returns}, axis=1
    ).dropna()

    cov_matrix = np.cov(aligned["stock"], aligned["market"])
    # cov_matrix shape: [[Var(s), Cov(s,m)], [Cov(s,m), Var(m)]]
    var_m = cov_matrix[1, 1]
    if var_m == 0.0:
        raise ValueError("Market return variance is zero; cannot compute beta.")

    beta = cov_matrix[0, 1] / var_m
    logger.debug("Static beta = %.4f  (n=%d)", beta, len(aligned))
    return float(beta)


def compute_ewma_beta(
    stock_returns: pd.Series,
    market_returns: pd.Series,
    span: int = 60,
    decay: float = 0.94,
) -> pd.Series:
    """Compute the exponentially-weighted moving-average (EWMA) beta series.

    Follows the **RiskMetrics** methodology with a configurable decay factor
    (default λ = 0.94).  At each time-step *t* the covariance and variance
    are updated:

    .. math::

        \\sigma^2_{m,t} &= \\lambda \\, \\sigma^2_{m,t-1}
                          + (1 - \\lambda) \\, r_{m,t}^2 \\\\
        \\sigma_{s,m,t} &= \\lambda \\, \\sigma_{s,m,t-1}
                          + (1 - \\lambda) \\, r_{s,t} \\, r_{m,t} \\\\
        \\beta_t &= \\sigma_{s,m,t} \\;/\\; \\sigma^2_{m,t}

    Args:
        stock_returns: Daily return series of the stock.
        market_returns: Daily return series of the market benchmark.
        span: Minimum number of observations before the first beta is
            emitted (used only for the initial warm-up; default 60).
        decay: The EWMA decay factor λ (must be in (0, 1); default 0.94).

    Returns:
        A ``pd.Series`` of time-varying betas indexed identically to the
        input series.  The first *span − 1* values are ``NaN``.

    Raises:
        ValueError: If inputs are invalid or *decay* is outside (0, 1).

    Example:
        >>> ewma_betas = compute_ewma_beta(stock_rets, market_rets, span=60)
        >>> ewma_betas.dropna().iloc[-1]
        1.15
    """
    _validate_return_series(stock_returns, market_returns)
    if not 0.0 < decay < 1.0:
        raise ValueError(f"decay must be in (0, 1), got {decay}")

    aligned = pd.concat(
        {"stock": stock_returns, "market": market_returns}, axis=1
    ).dropna()

    rs = aligned["stock"].values
    rm = aligned["market"].values
    n = len(rs)

    # Pre-allocate output arrays.
    ewma_cov = np.full(n, np.nan)   # EWMA covariance σ_{s,m}
    ewma_var = np.full(n, np.nan)   # EWMA variance   σ²_m
    betas    = np.full(n, np.nan)

    # Seed with the expanding-window estimates over the warm-up period.
    if n < span:
        logger.warning("Series length (%d) < span (%d); partial results.", n, span)
        seed_end = n
    else:
        seed_end = span

    seed_cov = np.cov(rs[:seed_end], rm[:seed_end])
    ewma_cov[seed_end - 1] = seed_cov[0, 1]
    ewma_var[seed_end - 1] = seed_cov[1, 1]

    if ewma_var[seed_end - 1] != 0.0:
        betas[seed_end - 1] = ewma_cov[seed_end - 1] / ewma_var[seed_end - 1]

    # Recursive EWMA update.
    lam = decay
    for t in range(seed_end, n):
        ewma_var[t] = lam * ewma_var[t - 1] + (1 - lam) * rm[t] ** 2
        ewma_cov[t] = lam * ewma_cov[t - 1] + (1 - lam) * rs[t] * rm[t]
        if ewma_var[t] != 0.0:
            betas[t] = ewma_cov[t] / ewma_var[t]

    return pd.Series(betas, index=aligned.index, name="ewma_beta")


def compute_rolling_beta(
    stock_returns: pd.Series,
    market_returns: pd.Series,
    window: int = 60,
) -> pd.Series:
    """Compute a simple rolling-window beta.

    For each window of *window* trading days the beta is the ordinary
    Cov / Var estimate computed on that sub-sample.

    Args:
        stock_returns: Daily return series of the stock.
        market_returns: Daily return series of the market benchmark.
        window: Rolling window size in trading days (default 60).

    Returns:
        A ``pd.Series`` of rolling betas.  The first *window − 1* values
        are ``NaN``.

    Raises:
        ValueError: If inputs are invalid or *window* < 2.

    Example:
        >>> rolling = compute_rolling_beta(stock_rets, market_rets, window=60)
        >>> rolling.dropna().mean()
        1.1
    """
    _validate_return_series(stock_returns, market_returns)
    if window < 2:
        raise ValueError(f"window must be >= 2, got {window}")

    aligned = pd.concat(
        {"stock": stock_returns, "market": market_returns}, axis=1
    ).dropna()

    # Rolling covariance and variance using pandas built-in rolling.
    rolling_cov = aligned["stock"].rolling(window).cov(aligned["market"])
    rolling_var = aligned["market"].rolling(window).var(ddof=1)

    # Avoid division by zero: replace 0-variance windows with NaN.
    rolling_var = rolling_var.replace(0.0, np.nan)

    beta_series = rolling_cov / rolling_var
    beta_series.name = "rolling_beta"
    return beta_series


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_return_series(
    stock_returns: pd.Series,
    market_returns: pd.Series,
) -> None:
    """Shared validation for return-series inputs.

    Args:
        stock_returns: Stock return series.
        market_returns: Market return series.

    Raises:
        ValueError: On empty series or length mismatch.
    """
    if stock_returns.empty or market_returns.empty:
        raise ValueError("Return series must not be empty.")
    if len(stock_returns) != len(market_returns):
        raise ValueError(
            f"Length mismatch: stock={len(stock_returns)}, "
            f"market={len(market_returns)}.  Align before calling."
        )
