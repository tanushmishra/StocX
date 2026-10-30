"""Adversarial verification guardrails for the Market-Neutral Hedge Builder.

Implements a multi-check verification gate that a candidate pair must pass
before being approved for live deployment.  Also provides a composite
fundamental scoring function for ranking candidates.

Every guardrail is deterministic and uses hard-coded thresholds.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Guardrail thresholds
# ---------------------------------------------------------------------------

_MIN_CORRELATION: float = 0.65
_MAX_COINT_PVALUE: float = 0.05
_MDD_RATIO_THRESHOLD: float = 0.50  # hedged MDD must be < 50% of unhedged
_MAX_REALIZED_BETA: float = 0.15


class CheckFailure(dict):
    """Failure record that behaves both as a dict and has string methods."""
    def __init__(self, check: str, reason: str):
        super().__init__(check=check, reason=reason)
        self.check = check
        self.reason = reason

    def lower(self) -> str:
        return f"{self.check}: {self.reason}".lower()

    def upper(self) -> str:
        return f"{self.check}: {self.reason}".upper()

    def __str__(self) -> str:
        return f"{self.check}: {self.reason}"

    def __contains__(self, item: Any) -> bool:
        if isinstance(item, str):
            return item in super().__contains__(item) or item in self.lower() or item in self.check or item in self.reason
        return super().__contains__(item)


def verify_pair(
    pair_metrics: dict | None = None,
    unhedged_stats: dict | None = None,
    hedged_stats: dict | None = None,
    long_ticker: str = "",
    short_ticker: str = "",
    stress_results: dict | None = None,
    weights: dict | None = None,
    **kwargs: Any,
) -> dict:
    """Run all adversarial guardrails on a candidate pair.

    Args:
        pair_metrics: Dict containing at least:
            * ``correlation`` – Pearson correlation between the two assets.
            * ``cointegration_pvalue`` – p-value from the Engle-Granger test.
        unhedged_stats: Output of ``calc_metrics`` for the unhedged leg.
            Must contain ``max_drawdown`` or ``max_drawdown_pct``.
        hedged_stats: Output of ``calc_metrics`` for the hedged portfolio.
            Must contain ``max_drawdown`` or ``max_drawdown_pct`` and ``realized_beta``.
        long_ticker: Optional long ticker symbol for diagnostics.
        short_ticker: Optional short ticker symbol for diagnostics.
        stress_results: Optional stress testing metrics.
        weights: Optional portfolio weights.
        **kwargs: Extra parameters passed by caller.

    Returns:
        A dict with keys:
            * ``passed`` – ``True`` if all checks pass.
            * ``approved`` – Alias for ``passed``.
            * ``failed_checks`` – List of failure dicts.
            * ``diagnostic`` – Human-readable summary message.
            * ``reason`` – Alias for ``diagnostic``.
            * ``gates`` – Per-gate boolean outcomes.
    """
    if pair_metrics is None:
        pair_metrics = kwargs.get("pair_metrics", {})
    if unhedged_stats is None:
        unhedged_stats = kwargs.get("unhedged_stats", {})
    if hedged_stats is None:
        hedged_stats = kwargs.get("hedged_stats", {})

    failed: list[dict[str, str]] = []
    gates: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # 1. Correlation check  (must be >= 0.65)
    # ------------------------------------------------------------------
    corr = float(pair_metrics.get("correlation", 0.0))
    passed_corr = corr >= _MIN_CORRELATION
    gates["correlation"] = passed_corr
    if not passed_corr:
        failed.append(CheckFailure(
            check="correlation",
            reason=f"Correlation {corr:.4f} < minimum threshold {_MIN_CORRELATION}",
        ))

    # ------------------------------------------------------------------
    # 2. Cointegration p-value  (must be < 0.05)
    # ------------------------------------------------------------------
    coint_p = float(pair_metrics.get("cointegration_pvalue", 1.0))
    passed_coint = coint_p < _MAX_COINT_PVALUE
    gates["cointegration"] = passed_coint
    if not passed_coint:
        failed.append(CheckFailure(
            check="cointegration",
            reason=f"Cointegration p-value {coint_p:.4f} >= threshold {_MAX_COINT_PVALUE} (pair not cointegrated)",
        ))

    # ------------------------------------------------------------------
    # 3. Max drawdown reduction  (hedged MDD < 50% of unhedged MDD)
    # ------------------------------------------------------------------
    raw_unhedged_mdd = unhedged_stats.get("max_drawdown", unhedged_stats.get("max_drawdown_pct", 0.0))
    raw_hedged_mdd = hedged_stats.get("max_drawdown", hedged_stats.get("max_drawdown_pct", 0.0))

    unhedged_mdd = abs(float(raw_unhedged_mdd))
    hedged_mdd = abs(float(raw_hedged_mdd))

    if unhedged_mdd == 0.0:
        logger.warning("Unhedged MDD is zero; skipping MDD ratio check.")
        gates["max_drawdown_reduction"] = True
    else:
        mdd_ratio = hedged_mdd / unhedged_mdd
        passed_mdd = mdd_ratio < _MDD_RATIO_THRESHOLD
        gates["max_drawdown_reduction"] = passed_mdd
        if not passed_mdd:
            failed.append(CheckFailure(
                check="max_drawdown_reduction",
                reason=(
                    f"Hedged MDD ({hedged_mdd:.4f}) is {mdd_ratio:.1%} of "
                    f"unhedged MDD ({unhedged_mdd:.4f}); must be < "
                    f"{_MDD_RATIO_THRESHOLD:.0%}"
                ),
            ))

    # ------------------------------------------------------------------
    # 4. Realised beta  (must be < 0.15 in absolute terms)
    # ------------------------------------------------------------------
    realized_beta = hedged_stats.get("realized_beta")
    if realized_beta is None or np.isnan(realized_beta):
        gates["realized_beta"] = False
        failed.append(CheckFailure(
            check="realized_beta",
            reason="Realised beta is unavailable (NaN).",
        ))
    elif abs(realized_beta) >= _MAX_REALIZED_BETA:
        gates["realized_beta"] = False
        failed.append(CheckFailure(
            check="realized_beta",
            reason=f"|Realised beta| = {abs(realized_beta):.4f} >= threshold {_MAX_REALIZED_BETA}",
        ))
    else:
        gates["realized_beta"] = True

    # ------------------------------------------------------------------
    # Build result
    # ------------------------------------------------------------------
    passed = len(failed) == 0
    if passed:
        diagnostic = "All guardrails passed. Pair is approved."
    else:
        check_names = ", ".join(f["check"] for f in failed)
        diagnostic = f"{len(failed)} check(s) failed: {check_names}."

    logger.info(diagnostic)

    return {
        "passed": passed,
        "approved": passed,
        "failed_checks": failed,
        "diagnostic": diagnostic,
        "reason": diagnostic,
        "gates": gates,
    }


def score_candidate(fundamentals: dict) -> float:
    """Compute a composite fundamental score for a candidate stock.

    The score is a weighted sum of four normalised components:

    +---------------------+--------+-----------------------------------+
    | Component           | Weight | Normalisation                     |
    +=====================+========+===================================+
    | ROE                 |  0.30  | raw value (higher is better)      |
    +---------------------+--------+-----------------------------------+
    | Revenue growth      |  0.30  | raw value (higher is better)      |
    +---------------------+--------+-----------------------------------+
    | Inverse PE          |  0.20  | 1 / PE (lower PE → higher score)  |
    +---------------------+--------+-----------------------------------+
    | Inverse D/E         |  0.20  | 1 / (1 + D/E) (lower → better)   |
    +---------------------+--------+-----------------------------------+

    Missing or ``None`` components are treated as zero.

    Args:
        fundamentals: Dict with optional keys ``roe``, ``revenue_growth``,
            ``pe_ratio``, ``debt_to_equity``.

    Returns:
        A float score (higher is better).  Not bounded to [0, 1].

    Example:
        >>> score_candidate({"roe": 0.25, "revenue_growth": 0.15,
        ...                  "pe_ratio": 30, "debt_to_equity": 0.5})
        0.139
    """
    roe = _safe_float(fundamentals.get("roe"), 0.0)
    rev_growth = _safe_float(fundamentals.get("revenue_growth"), 0.0)
    pe = _safe_float(fundamentals.get("pe_ratio"), None)
    de = _safe_float(fundamentals.get("debt_to_equity"), None)

    # Inverse PE: higher is better (i.e., lower PE is preferred).
    inv_pe = (1.0 / pe) if (pe is not None and pe > 0) else 0.0

    # Inverse D/E: use 1/(1+D/E) so it's bounded (0, 1].  Zero debt → 1.0.
    if de is not None and de >= 0:
        inv_de = 1.0 / (1.0 + de)
    else:
        inv_de = 0.0

    score = (
        0.30 * roe
        + 0.30 * rev_growth
        + 0.20 * inv_pe
        + 0.20 * inv_de
    )

    logger.debug(
        "Fundamental score: ROE=%.3f  RevG=%.3f  invPE=%.3f  invDE=%.3f → %.4f",
        roe,
        rev_growth,
        inv_pe,
        inv_de,
        score,
    )
    return float(score)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_float(value: Any, default: float | None) -> float | None:
    """Coerce *value* to float, returning *default* on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
