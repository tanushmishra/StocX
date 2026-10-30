"""Cointegration and spread analysis module for the Market-Neutral Hedge Builder.

Implements:

* **Engle-Granger two-step cointegration test** (via ``statsmodels``).
* **Rolling Z-score of the log price ratio** for mean-reversion signals.
* **Ornstein-Uhlenbeck half-life estimation** via AR(1) regression, which
  quantifies how quickly a spread reverts to its mean.

All numerical work uses ``numpy``, ``pandas``, ``scipy``, and
``statsmodels``—no LLMs or stochastic sampling.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
try:
    import statsmodels.api as sm
    from statsmodels.tsa.stattools import coint
except ImportError:
    sm = None
    coint = None

from scipy import stats

logger = logging.getLogger(__name__)


def _numpy_ols(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fit OLS y = x @ beta + resid using numpy lstsq."""
    beta, residuals, rank, s = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    return beta, resid


def _approx_coint(series_a: pd.Series, series_b: pd.Series) -> tuple[float, float, list[float]]:
    """Engle-Granger cointegration approximation using OLS + ADF regression."""
    y = series_a.to_numpy(dtype=float)
    x = series_b.to_numpy(dtype=float)
    n = len(y)

    # 1. Regress y on x with constant
    X = np.column_stack([np.ones(n), x])
    beta, resid = _numpy_ols(y, X)

    # 2. ADF regression on residuals: delta_e_t = gamma * e_{t-1} + const
    e_lag = resid[:-1]
    delta_e = np.diff(resid)
    M = np.column_stack([np.ones(len(e_lag)), e_lag])
    params, e_resid = _numpy_ols(delta_e, M)

    gamma = params[1]
    # Standard error of gamma
    s2 = np.sum(e_resid**2) / max(len(delta_e) - 2, 1)
    cov_matrix = np.linalg.inv(M.T @ M) * s2
    se_gamma = np.sqrt(max(cov_matrix[1, 1], 1e-12))
    t_stat = float(gamma / se_gamma)

    # MacKinnon critical values for cointegration with constant (N=2)
    crit_values = [-3.90, -3.34, -3.04]

    # Approximate p-value from t-stat
    if t_stat < -3.90:
        p_val = 0.01
    elif t_stat < -3.34:
        p_val = 0.04
    elif t_stat < -3.04:
        p_val = 0.08
    else:
        # Linear interpolation above -3.04
        p_val = min(1.0, 0.10 + max(0.0, (t_stat - (-3.04)) * 0.15))

    return t_stat, p_val, crit_values


def engle_granger_test(
    series_a: pd.Series | str,
    series_b: pd.Series | str,
    *args: Any,
) -> dict:
    """Run the Engle-Granger two-step cointegration test on two price series.

    Step 1: Regress *series_a* on *series_b* (with constant) to obtain the
    residual spread.  Step 2: Test the residuals for a unit root via the
    ADF test.  A significant (small) *p*-value means the spread is
    stationary, i.e. the pair is cointegrated.

    Supports both (series_a, series_b) and (ticker_a, ticker_b, prices_df).
    """
    if isinstance(series_a, str) and isinstance(series_b, str) and args and isinstance(args[0], pd.DataFrame):
        prices = args[0]
        series_a = np.log(prices[series_a])
        series_b = np.log(prices[series_b])

    _validate_price_series(series_a, series_b)

    if coint is not None:
        try:
            t_stat, p_value, crit_values = coint(series_a, series_b, trend="c")
            crit_dict = {
                "1%": float(crit_values[0]),
                "5%": float(crit_values[1]),
                "10%": float(crit_values[2]),
            }
        except Exception as e:
            logger.warning("statsmodels coint failed (%s), falling back to numpy OLS", e)
            t_stat, p_value, crit_vals = _approx_coint(series_a, series_b)
            crit_dict = {"1%": crit_vals[0], "5%": crit_vals[1], "10%": crit_vals[2]}
    else:
        t_stat, p_value, crit_vals = _approx_coint(series_a, series_b)
        crit_dict = {"1%": crit_vals[0], "5%": crit_vals[1], "10%": crit_vals[2]}

    is_coint = bool(p_value < 0.05)
    result = {
        "t_stat": float(t_stat),
        "p_value": float(p_value),
        "critical_values": crit_dict,
        "cointegrated": is_coint,
        "is_cointegrated": is_coint,
    }

    logger.info(
        "Engle-Granger: t=%.3f  p=%.4f  cointegrated=%s",
        result["t_stat"],
        result["p_value"],
        result["cointegrated"],
    )
    return result


def compute_spread_zscore(
    series_a: pd.Series | str,
    series_b: pd.Series | str,
    *args: Any,
    window: int = 60,
) -> pd.Series:
    """Compute the rolling Z-score of the log price ratio (spread)."""
    if isinstance(series_a, str) and isinstance(series_b, str) and args and isinstance(args[0], pd.DataFrame):
        prices = args[0]
        series_a = prices[series_a]
        series_b = prices[series_b]

    _validate_price_series(series_a, series_b)
    if (series_a <= 0).any() or (series_b <= 0).any():
        raise ValueError("Price series must be strictly positive for log transform.")

    # Log price ratio (the spread).
    spread = np.log(series_a) - np.log(series_b)

    rolling_mean = spread.rolling(window).mean()
    rolling_std = spread.rolling(window).std(ddof=1)

    # Guard against zero standard deviation (perfectly flat spread).
    rolling_std = rolling_std.replace(0.0, np.nan)

    zscore = (spread - rolling_mean) / rolling_std
    zscore.name = "spread_zscore"
    return zscore


def ou_half_life(spread: pd.Series | str, *args: Any) -> float:
    """Estimate the Ornstein-Uhlenbeck half-life of mean reversion.

    Fits an AR(1) model on the spread via OLS:
    Delta S_t = theta * S_{t-1} + eps_t.
    If theta >= 0: returns float('inf') indicating no mean reversion.
    """
    if isinstance(spread, str) and len(args) >= 2 and isinstance(args[1], pd.DataFrame):
        long_t = spread
        short_t = args[0]
        prices = args[1]
        spread = np.log(prices[long_t]) - np.log(prices[short_t])

    clean = spread.dropna()
    if len(clean) < 3:
        raise ValueError(
            f"Need at least 3 non-NaN observations, got {len(clean)}."
        )

    # ΔS_t = S_t − S_{t−1}  (dependent variable)
    delta_s = clean.diff().iloc[1:].to_numpy(dtype=float)

    # S_{t−1}  (regressor)
    s_lag = clean.shift(1).iloc[1:].to_numpy(dtype=float)

    if sm is not None:
        try:
            s_lag_const = sm.add_constant(s_lag)
            model = sm.OLS(delta_s, s_lag_const, missing="drop").fit()
            theta: float = float(model.params[1])
        except Exception:
            # Fallback to numpy
            M = np.column_stack([np.ones(len(s_lag)), s_lag])
            params, _ = _numpy_ols(delta_s, M)
            theta = float(params[1])
    else:
        M = np.column_stack([np.ones(len(s_lag)), s_lag])
        params, _ = _numpy_ols(delta_s, M)
        theta = float(params[1])

    if theta >= 0:
        # No mean reversion: spread is a random walk or explosive.
        logger.warning("θ = %.4f ≥ 0 → no mean reversion detected.", theta)
        return float("inf")

    half_life = -np.log(2) / theta
    logger.info("OU half-life = %.2f  (θ = %.4f)", half_life, theta)
    return float(half_life)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_price_series(a: pd.Series, b: pd.Series) -> None:
    """Shared validation for price-level series.

    Args:
        a: First price series.
        b: Second price series.

    Raises:
        ValueError: On empty series or length mismatch.
    """
    if a.empty or b.empty:
        raise ValueError("Price series must not be empty.")
    if len(a) != len(b):
        raise ValueError(
            f"Series length mismatch: A={len(a)}, B={len(b)}.  "
            "Align before calling."
        )
