"""Portfolio construction and weight computation module.

Provides utilities for:

* **Beta-neutral weight calculation** — analytically solving for long/short
  weights that zero out the portfolio's net market beta.
* **F&O lot-size conversion** — translating percentage weights into integer
  multiples of NSE futures/options lot sizes, accounting for transaction
  costs.
* **Correlation matrix computation** — full Pearson correlation across a
  return panel.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Default transaction cost assumption: brokerage + STT combined.
_DEFAULT_TXCOST_BPS: float = 10.0  # 0.10 % one-way


def compute_beta_neutral_weights(
    beta_long: float,
    beta_short: float,
) -> dict:
    """Solve for beta-neutral portfolio weights.

    For a long–short pair with betas β_L and β_S the portfolio beta is:

    .. math::

        \\beta_P = w_L \\, \\beta_L - w_S \\, \\beta_S = 0

    subject to  w_L + w_S = 1  (fully invested, dollar-neutral constraint).

    Solving gives:

    .. math::

        w_L &= \\frac{\\beta_S}{\\beta_L + \\beta_S} \\\\
        w_S &= \\frac{\\beta_L}{\\beta_L + \\beta_S}

    The short leg weight is returned as **negative** to flag direction.

    Args:
        beta_long: Beta of the long leg (must be > 0).
        beta_short: Beta of the short leg (must be > 0).

    Returns:
        A dict with keys ``w_long`` (positive) and ``w_short`` (negative).

    Raises:
        ValueError: If either beta is non-positive or their sum is zero.

    Example:
        >>> compute_beta_neutral_weights(1.2, 0.8)
        {'w_long': 0.4, 'w_short': -0.6}
    """
    if beta_long <= 0:
        raise ValueError(f"beta_long must be > 0, got {beta_long}")
    if beta_short <= 0:
        raise ValueError(f"beta_short must be > 0, got {beta_short}")

    denom = beta_long + beta_short
    if denom == 0.0:
        raise ValueError("Sum of betas is zero; cannot solve for weights.")

    w_long = beta_short / denom
    w_short = beta_long / denom

    logger.info(
        "Beta-neutral weights: w_long=%.4f  w_short=%.4f  "
        "(β_L=%.3f, β_S=%.3f)",
        w_long,
        w_short,
        beta_long,
        beta_short,
    )

    return {
        "long": float(w_long),
        "short": float(-w_short),
        "w_long": float(w_long),
        "w_short": float(-w_short),
        "long_weight": float(w_long),
        "short_weight": float(-w_short),
    }


def convert_to_fno_lots(
    weights: dict,
    capital: float,
    lot_sizes: dict[str, int],
    prices: dict[str, float],
    txcost_bps: float = _DEFAULT_TXCOST_BPS,
) -> dict:
    """Convert percentage weights to integer F&O lot positions.

    For each ticker the notional allocation is ``abs(weight) * capital``.
    The maximum number of lots that fit within this notional (after
    deducting one-way transaction costs) is:

    .. math::

        n_{\\text{lots}} = \\left\\lfloor
            \\frac{\\text{notional} \\times (1 - \\text{tc})}{
                \\text{lot\\_size} \\times \\text{price}}
        \\right\\rfloor

    Args:
        weights: Dict mapping ticker → signed weight (negative = short).
            Output of :func:`compute_beta_neutral_weights` can be adapted
            by mapping the generic ``w_long``/``w_short`` keys to actual
            tickers before calling this function.
        capital: Total capital available (INR).
        lot_sizes: Dict mapping ticker → lot size (shares per lot).
        prices: Dict mapping ticker → current price per share.
        txcost_bps: One-way transaction cost in basis points (default 10,
            i.e. 0.10 % covering brokerage + STT).

    Returns:
        A dict per ticker with keys ``lots``, ``direction``,
        ``notional_allocated``, ``txcost_deducted``, and
        ``actual_notional``.

    Raises:
        ValueError: If *capital* ≤ 0, or a ticker is missing from
            *lot_sizes* / *prices*.

    Example:
        >>> result = convert_to_fno_lots(
        ...     {"TCS.NS": 0.4, "INFY.NS": -0.6},
        ...     capital=1_000_000,
        ...     lot_sizes={"TCS.NS": 175, "INFY.NS": 400},
        ...     prices={"TCS.NS": 3500.0, "INFY.NS": 1500.0},
        ... )
        >>> result["TCS.NS"]["lots"]
        0
    """
    if capital <= 0:
        raise ValueError(f"capital must be > 0, got {capital}")

    tc_frac = txcost_bps / 10_000  # convert bps to fraction

    positions: dict = {}
    for ticker, weight in weights.items():
        if ticker not in lot_sizes:
            raise ValueError(f"Lot size missing for {ticker}")
        if ticker not in prices:
            raise ValueError(f"Price missing for {ticker}")

        notional = abs(weight) * capital
        txcost = notional * tc_frac
        net_notional = notional - txcost

        lot_value = lot_sizes[ticker] * prices[ticker]
        if lot_value <= 0:
            lots = 0
        else:
            lots = int(net_notional // lot_value)

        direction = "LONG" if weight > 0 else "SHORT"
        actual_notional = lots * lot_value

        positions[ticker] = {
            "lots": lots,
            "direction": direction,
            "notional_allocated": round(notional, 2),
            "txcost_deducted": round(txcost, 2),
            "actual_notional": round(actual_notional, 2),
        }

        logger.info(
            "%s %s: %d lots × %d shares @ ₹%.2f = ₹%.2f",
            direction,
            ticker,
            lots,
            lot_sizes[ticker],
            prices[ticker],
            actual_notional,
        )

    return positions


def compute_correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """Compute the full Pearson correlation matrix for a return panel.

    Args:
        returns: A ``pd.DataFrame`` where each column is a daily return
            series for a different asset.

    Returns:
        A square ``pd.DataFrame`` containing pairwise Pearson correlations.

    Raises:
        ValueError: If *returns* has fewer than 2 columns or fewer than 2
            rows of data.

    Example:
        >>> corr = compute_correlation_matrix(returns_df)
        >>> corr.loc["TCS.NS", "INFY.NS"]
        0.72
    """
    if returns.shape[1] < 2:
        raise ValueError("Need at least 2 columns to compute correlations.")
    if returns.dropna().shape[0] < 2:
        raise ValueError("Need at least 2 non-NaN rows for correlation.")

    corr = returns.corr(method="pearson")
    logger.debug("Correlation matrix shape: %s", corr.shape)
    return corr
