"""Dashboard State Adapter for the Market-Neutral Hedge Builder.

This module provides a pure, deterministic transformation layer between the
internal LangGraph state (`HedgeBuilderState`) or engine analysis dictionary
and the Streamlit UI presentation layer (`DashboardViewModel`).

Guarantees & Invariants:
------------------------
1. **Purity**: Zero side effects, zero network calls, zero LLM invocations,
   and zero mutations of the input state.
2. **Zero Hallucination / Substitution**: Never replaces uncomputed or missing
   metrics with synthetic values or misleading zeros (`0.00`). If a metric was
   not computed, it remains explicitly `None`.
3. **Type Preservation**: Retains pandas `Series` and `DataFrame` objects
   (including `DatetimeIndex`) without destructive list downcasting so downstream
   charts can render exact temporal series.
4. **Resilient Extraction**: Safely handles dictionary-like objects, Pydantic/TypedDict
   classes, partial runs, missing keys, and explicit `None` values.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd


# ────────────────────────────────────────────────────────────────────────────
# Section ViewModels
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class RunInfo:
    """Run configuration, intent parsing, and candidate selection metadata."""
    thesis: Optional[str] = None
    target_sector: Optional[str] = None
    benchmark: Optional[str] = None
    lookback_days: Optional[int] = None
    stress_regime: Optional[str] = None
    selected_long: Optional[str] = None
    selected_short: Optional[str] = None
    approved: Optional[bool] = None
    attempt_count: Optional[int] = None
    max_attempts: Optional[int] = None
    capital: Optional[float] = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@dataclass
class DashboardMetrics:
    """Quantitative risk and performance metrics before vs after hedging."""
    unhedged_beta: Optional[float] = None
    hedged_beta: Optional[float] = None
    unhedged_max_drawdown: Optional[float] = None
    hedged_max_drawdown: Optional[float] = None
    unhedged_sharpe: Optional[float] = None
    hedged_sharpe: Optional[float] = None
    unhedged_sortino: Optional[float] = None
    hedged_sortino: Optional[float] = None
    unhedged_volatility: Optional[float] = None
    hedged_volatility: Optional[float] = None
    unhedged_var_95: Optional[float] = None
    hedged_var_95: Optional[float] = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@dataclass
class PortfolioData:
    """Portfolio weights, F&O lot sizing, and cumulative returns."""
    weights: Optional[Dict[str, Any]] = None
    fno_execution: Optional[Union[Dict[str, Any], List[Any]]] = None
    cumulative_returns: Optional[Dict[str, Any]] = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@dataclass
class QuantAnalysis:
    """Statistical properties, cointegration tests, and stress testing outputs."""
    pair_metrics: Dict[str, Any] = field(default_factory=dict)
    rolling_beta: Optional[Any] = None  # pd.Series or None
    spread_zscore: Optional[Any] = None  # pd.Series or None
    correlation_matrix: Optional[Any] = None  # pd.DataFrame, dict, or None
    cointegration: Optional[Dict[str, Any]] = None
    half_life: Optional[float] = None
    stress_results: Optional[Dict[str, Any]] = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@dataclass
class VerificationData:
    """Risk verification gate verdicts, rejection logs, and execution trace."""
    verifier_result: Optional[Dict[str, Any]] = None
    rejection_log: List[Dict[str, Any]] = field(default_factory=list)
    attempt_count: Optional[int] = None
    approved: Optional[bool] = None
    messages: List[Any] = field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@dataclass
class ResearchData:
    """Sector candidate universes and candidate fundamental attributes."""
    long_candidates: List[Dict[str, Any]] = field(default_factory=list)
    short_candidates: List[Dict[str, Any]] = field(default_factory=list)
    selected_long_fundamentals: Optional[Dict[str, Any]] = None
    selected_short_fundamentals: Optional[Dict[str, Any]] = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@dataclass
class ReportingData:
    """Institutional executive summaries and memos."""
    cro_report: Optional[str] = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@dataclass
class DashboardViewModel:
    """Master structured viewmodel consumed by Streamlit UI components."""
    run_info: RunInfo
    metrics: DashboardMetrics
    portfolio: PortfolioData
    quant: QuantAnalysis
    verification: VerificationData
    research: ResearchData
    reporting: ReportingData

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"DashboardViewModel has no section '{key}'")

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


# ────────────────────────────────────────────────────────────────────────────
# Safe Value Extraction Utilities
# ────────────────────────────────────────────────────────────────────────────

def _first_not_none(*values: Any) -> Any:
    """Return the first argument that is not None, avoiding truth-value checks on pandas objects."""
    for v in values:
        if v is not None:
            return v
    return None


def _safe_get(source: Any, key: str, default: Any = None) -> Any:
    """Safely extract a key from a dictionary or an object attribute."""
    if source is None:
        return default
    if isinstance(source, dict):
        val = source.get(key, default)
    else:
        val = getattr(source, key, default)
    return default if val is None else val


def _clean_float(val: Any) -> Optional[float]:
    """Sanitize arbitrary numeric values into floats, mapping NaN/inf to None."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _clean_int(val: Any) -> Optional[int]:
    """Sanitize arbitrary values into integers, returning None if invalid."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return int(f)
    except (ValueError, TypeError):
        return None


def _extract_metric(
    sources: Sequence[Any],
    candidate_keys: Sequence[str],
) -> Optional[float]:
    """Search multiple dictionaries for the first valid float metric."""
    for src in sources:
        if not isinstance(src, dict):
            continue
        for k in candidate_keys:
            if k in src:
                val = _clean_float(src[k])
                if val is not None:
                    return val
    return None


def _extract_fundamentals_for_ticker(
    candidates: Sequence[Dict[str, Any]],
    ticker: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Locate candidate dictionary corresponding to ticker without mutating it."""
    if not ticker or not candidates:
        return None
    target_clean = ticker.strip().upper()
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        cand_ticker = cand.get("ticker", "")
        if cand_ticker and cand_ticker.strip().upper() == target_clean:
            # Return copy to prevent downstream mutation
            return copy.deepcopy(cand)
    return None


# ────────────────────────────────────────────────────────────────────────────
# Master Adapter Function
# ────────────────────────────────────────────────────────────────────────────

def map_state_to_dashboard(
    state: Any,
    capital: Optional[float] = None,
) -> DashboardViewModel:
    """Transform LangGraph state or engine analysis output into DashboardViewModel.

    This is a pure function that never mutates `state` and produces no side effects.

    Args:
        state: State dictionary (e.g. from LangGraph HedgeBuilderState or
            `engine.hedge_pipeline.run_full_hedge_analysis`).
        capital: Optional deployed capital override.

    Returns:
        DashboardViewModel containing strictly verified metrics and data objects.
    """
    if state is None:
        state = {}

    # ── 1. Run Information ──────────────────────────────────────────────
    raw_approved = None
    if isinstance(state, dict):
        if "approved" in state and state["approved"] is not None:
            raw_approved = bool(state["approved"])
    else:
        if hasattr(state, "approved") and getattr(state, "approved") is not None:
            raw_approved = bool(getattr(state, "approved"))

    thesis_val = _safe_get(state, "thesis", None)
    thesis_str = str(thesis_val).strip() if thesis_val is not None else None
    if thesis_str == "":
        thesis_str = None

    target_sector_val = _safe_get(state, "target_sector", None)
    target_sector_str = str(target_sector_val).strip() if target_sector_val is not None else None
    if target_sector_str == "":
        target_sector_str = None

    benchmark_val = _safe_get(state, "benchmark", None)
    benchmark_str = str(benchmark_val).strip() if benchmark_val is not None else None
    if benchmark_str == "":
        benchmark_str = None

    stress_regime_val = _safe_get(state, "stress_regime", None)
    stress_regime_str = str(stress_regime_val).strip() if stress_regime_val is not None else None
    if stress_regime_str == "":
        stress_regime_str = None

    selected_long = _first_not_none(_safe_get(state, "selected_long", None), _safe_get(state, "long_ticker", None))
    if selected_long is not None:
        selected_long = str(selected_long).strip()
        if not selected_long:
            selected_long = None

    selected_short = _first_not_none(_safe_get(state, "selected_short", None), _safe_get(state, "short_ticker", None))
    if selected_short is not None:
        selected_short = str(selected_short).strip()
        if not selected_short:
            selected_short = None

    capital_override = _clean_float(capital)
    capital_state = _clean_float(_safe_get(state, "capital", None))
    capital_val = capital_override if capital_override is not None else capital_state

    run_info = RunInfo(
        thesis=thesis_str,
        target_sector=target_sector_str,
        benchmark=benchmark_str,
        lookback_days=_clean_int(_safe_get(state, "lookback_days", None)),
        stress_regime=stress_regime_str,
        selected_long=selected_long,
        selected_short=selected_short,
        approved=raw_approved,
        attempt_count=_clean_int(_safe_get(state, "attempt_count", None)),
        max_attempts=_clean_int(_safe_get(state, "max_attempts", None)),
        capital=capital_val,
    )

    # ── 2. Risk & Performance Metrics ───────────────────────────────────
    unhedged_stats = _safe_get(state, "unhedged_stats", {})
    hedged_stats = _safe_get(state, "hedged_stats", {})
    pair_metrics_dict = _safe_get(state, "pair_metrics", {})
    weights_dict = _safe_get(state, "weights", {})
    backtest_dict = _safe_get(state, "backtest", {})
    betas_dict = _safe_get(state, "betas", {})

    unhedged_sources = [
        unhedged_stats,
        _safe_get(backtest_dict, "unhedged_metrics", {}),
    ]
    hedged_sources = [
        hedged_stats,
        _safe_get(backtest_dict, "hedged_metrics", {}),
    ]

    # Unhedged beta
    unhedged_beta = _extract_metric(
        [pair_metrics_dict, unhedged_stats, _safe_get(betas_dict, "long", {})],
        ["static_beta_long", "static", "beta", "realized_beta"],
    )

    # Hedged beta
    hedged_beta = _extract_metric(
        [hedged_stats, pair_metrics_dict, weights_dict, _safe_get(backtest_dict, "hedged_metrics", {})],
        ["realized_beta", "portfolio_beta", "hedged_beta", "beta"],
    )

    # Max Drawdowns
    unhedged_mdd = _extract_metric(
        unhedged_sources,
        ["max_drawdown", "max_drawdown_pct", "max_dd"],
    )
    hedged_mdd = _extract_metric(
        hedged_sources,
        ["max_drawdown", "max_drawdown_pct", "max_dd"],
    )

    # Sharpe Ratios
    unhedged_sharpe = _extract_metric(
        unhedged_sources,
        ["sharpe_ratio", "sharpe"],
    )
    hedged_sharpe = _extract_metric(
        hedged_sources,
        ["sharpe_ratio", "sharpe"],
    )

    # Sortino Ratios
    unhedged_sortino = _extract_metric(
        unhedged_sources,
        ["sortino_ratio", "sortino"],
    )
    hedged_sortino = _extract_metric(
        hedged_sources,
        ["sortino_ratio", "sortino"],
    )

    # Annualized Volatility
    unhedged_vol = _extract_metric(
        unhedged_sources,
        ["annual_volatility", "volatility", "vol"],
    )
    hedged_vol = _extract_metric(
        hedged_sources,
        ["annual_volatility", "volatility", "vol"],
    )

    # VaR 95%
    unhedged_var = _extract_metric(
        unhedged_sources,
        ["var_95", "var95", "value_at_risk_95"],
    )
    hedged_var = _extract_metric(
        hedged_sources,
        ["var_95", "var95", "value_at_risk_95"],
    )

    metrics = DashboardMetrics(
        unhedged_beta=unhedged_beta,
        hedged_beta=hedged_beta,
        unhedged_max_drawdown=unhedged_mdd,
        hedged_max_drawdown=hedged_mdd,
        unhedged_sharpe=unhedged_sharpe,
        hedged_sharpe=hedged_sharpe,
        unhedged_sortino=unhedged_sortino,
        hedged_sortino=hedged_sortino,
        unhedged_volatility=unhedged_vol,
        hedged_volatility=hedged_vol,
        unhedged_var_95=unhedged_var,
        hedged_var_95=hedged_var,
    )

    # ── 3. Portfolio Data ───────────────────────────────────────────────
    raw_weights = _safe_get(state, "weights", None)
    weights = copy.deepcopy(raw_weights) if isinstance(raw_weights, dict) and raw_weights else None

    raw_fno = _first_not_none(_safe_get(state, "fno_execution", None), _safe_get(state, "fno_positions", None))
    fno_execution = copy.deepcopy(raw_fno) if raw_fno else None

    raw_cum = _safe_get(state, "cumulative_returns", None)
    cumulative_returns = None
    if isinstance(raw_cum, dict) and raw_cum:
        cumulative_returns = dict(raw_cum)  # preserve pd.Series structures without destructive copy
    elif isinstance(backtest_dict, dict) and backtest_dict:
        # Check alternative producer format in hedge_pipeline
        h_cum = backtest_dict.get("hedged_cumulative")
        u_cum = backtest_dict.get("unhedged_cumulative")
        if h_cum is not None or u_cum is not None:
            cumulative_returns = {"hedged": h_cum, "unhedged": u_cum}

    portfolio = PortfolioData(
        weights=weights,
        fno_execution=fno_execution,
        cumulative_returns=cumulative_returns,
    )

    # ── 4. Quantitative Analysis ────────────────────────────────────────
    pair_metrics = dict(pair_metrics_dict) if isinstance(pair_metrics_dict, dict) else {}

    # Rolling beta: look for verified Series
    rolling_beta = _first_not_none(
        pair_metrics.get("rolling_beta"),
        pair_metrics.get("rolling_beta_long"),
        _safe_get(betas_dict, "rolling_long_series", None),
        _safe_get(state, "rolling_beta", None),
    )

    # Spread Z-score: look for verified Series
    spread_zscore = _first_not_none(
        pair_metrics.get("spread_zscore"),
        _safe_get(state, "spread_zscore", None),
    )

    # Correlation matrix: DataFrame or dict
    corr_matrix = _first_not_none(
        pair_metrics.get("correlation_matrix"),
        _safe_get(state, "correlation_matrix", None),
    )

    # Cointegration result: dict
    raw_coint = _first_not_none(
        pair_metrics.get("cointegration"),
        _safe_get(state, "cointegration", None),
    )
    cointegration = copy.deepcopy(raw_coint) if isinstance(raw_coint, dict) else None

    # OU Half-life: float
    half_life = _clean_float(
        _first_not_none(
            pair_metrics.get("ou_half_life"),
            _safe_get(state, "ou_half_life", None),
        )
    )

    # Stress results: dict
    raw_stress = _first_not_none(
        _safe_get(state, "stress_results", None),
        _safe_get(state, "stress_tests", None),
    )
    stress_results = copy.deepcopy(raw_stress) if isinstance(raw_stress, dict) and raw_stress else None

    quant = QuantAnalysis(
        pair_metrics=pair_metrics,
        rolling_beta=rolling_beta,
        spread_zscore=spread_zscore,
        correlation_matrix=corr_matrix,
        cointegration=cointegration,
        half_life=half_life,
        stress_results=stress_results,
    )

    # ── 5. Verification Data ────────────────────────────────────────────
    verifier_result = _first_not_none(
        _safe_get(state, "verifier_result", None),
        _safe_get(state, "verification", None),
    )
    if isinstance(verifier_result, dict):
        verifier_result = copy.deepcopy(verifier_result)
    else:
        verifier_result = None

    raw_rejections = _safe_get(state, "rejection_log", [])
    rejection_log = copy.deepcopy(raw_rejections) if isinstance(raw_rejections, list) else []

    raw_messages = _safe_get(state, "messages", [])
    messages = list(raw_messages) if isinstance(raw_messages, (list, tuple)) else []

    verification = VerificationData(
        verifier_result=verifier_result,
        rejection_log=rejection_log,
        attempt_count=run_info.attempt_count,
        approved=run_info.approved,
        messages=messages,
    )

    # ── 6. Research Data ────────────────────────────────────────────────
    raw_long_cands = _safe_get(state, "long_candidates", [])
    long_candidates = copy.deepcopy(raw_long_cands) if isinstance(raw_long_cands, list) else []

    raw_short_cands = _safe_get(state, "short_candidates", [])
    short_candidates = copy.deepcopy(raw_short_cands) if isinstance(raw_short_cands, list) else []

    all_cands = long_candidates + short_candidates
    long_fundamentals = _extract_fundamentals_for_ticker(all_cands, run_info.selected_long)
    short_fundamentals = _extract_fundamentals_for_ticker(all_cands, run_info.selected_short)

    research = ResearchData(
        long_candidates=long_candidates,
        short_candidates=short_candidates,
        selected_long_fundamentals=long_fundamentals,
        selected_short_fundamentals=short_fundamentals,
    )

    # ── 7. Reporting Data ───────────────────────────────────────────────
    cro_report_val = _safe_get(state, "cro_report", None)
    cro_report = str(cro_report_val).strip() if cro_report_val is not None else None
    if cro_report == "":
        cro_report = None

    reporting = ReportingData(
        cro_report=cro_report,
    )

    return DashboardViewModel(
        run_info=run_info,
        metrics=metrics,
        portfolio=portfolio,
        quant=quant,
        verification=verification,
        research=research,
        reporting=reporting,
    )
