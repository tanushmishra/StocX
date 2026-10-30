"""Pydantic state schema and StateProxy for the Market-Neutral Hedge Builder graph.

This module defines :class:`HedgeBuilderState`, the single shared state object
that flows through every node in the LangGraph ``StateGraph``. It extends
:class:`langgraph.graph.MessagesState` so that the built-in ``messages`` channel
is available for inter-agent chat history while all domain-specific fields are
strongly typed via Pydantic.

It also defines :class:`StateProxy`, a robust dual dict/attribute wrapper that
prevents state-handling errors (e.g. ``AttributeError`` or ``KeyError``),
guarantees schema default values, protects against unintended mutation of
nested mutable objects, and maintains 100% compatibility with LangGraph.

Design decisions
----------------
* **Flat namespace** – every node reads / writes the same top-level keys.
  This avoids deeply nested dicts and keeps conditional routing simple.
* **Immutable defaults via ``Field(default_factory=...)``** – prevents the
  classic mutable-default-argument footgun.
* **``StateProxy`` wrapper** – provides safe dual dot/dict access across all nodes,
  ensures schema completeness, and prevents state loss or mutation between steps.
* **``rejection_log``** – an append-only audit trail so the CRO Reporter
  can narrate *which* pairs were tried and *why* they were rejected.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Literal

from langgraph.graph import MessagesState
from pydantic import Field

logger = logging.getLogger(__name__)

# Complete schema defaults for all HedgeBuilderState fields
STATE_SCHEMA_DEFAULTS: dict[str, Any] = {
    # Macro intent & provenance
    "thesis": "",
    "target_sector": "",
    "benchmark": "^NSEI",
    "lookback_days": 252,
    "stress_regime": "COVID_2020",
    "data_source": "yfinance",
    # Screening results
    "sector_tickers": [],
    "long_candidates": [],
    "short_candidates": [],
    "selected_long": "",
    "selected_short": "",
    # Quant results
    "pair_metrics": {},
    "weights": {},
    "unhedged_stats": {},
    "hedged_stats": {},
    "stress_results": {},
    "cumulative_returns": {},
    # Verification
    "verifier_result": {},
    "rejection_log": [],
    "attempt_count": 0,
    "max_attempts": 5,
    # Final output
    "approved": False,
    "cro_report": "",
    "fno_execution": {},
    # Chat / message history
    "messages": [],
}


class HedgeBuilderState(MessagesState):
    """Complete state schema carried through the Hedge Builder graph.

    Attributes:
        thesis: Raw natural-language thesis from the portfolio manager.
        target_sector: NSE sector string resolved by the Macro Parser
            (e.g. ``"NIFTY IT"``, ``"NIFTY BANK"``).
        benchmark: Benchmark index ticker used for beta computation.
            Defaults to ``"^NSEI"`` (Nifty 50).
        lookback_days: Number of trailing calendar days for price history.
        stress_regime: Named stress window for scenario analysis
            (e.g. ``"COVID_2020"``, ``"TAPER_TANTRUM_2013"``).
        data_source: Provenance of price data used in analysis
            (``"yfinance"``, ``"cache"``, or ``"synthetic_fallback"``).

        sector_tickers: Universe of tickers returned by
            ``engine.data_fetcher.get_sector_constituents()``.
        long_candidates: Scored candidate dicts for the long leg.
        short_candidates: Scored candidate dicts for the short leg.
        selected_long: Final long ticker chosen by the Screener.
        selected_short: Final short ticker chosen by the Screener.

        pair_metrics: Beta, correlation, cointegration p-value, etc.
        weights: Beta-neutral portfolio weights (``{"long_wt": …, "short_wt": …}``).
        unhedged_stats: Stand-alone backtest stats for the long leg.
        hedged_stats: Backtest stats for the hedged pair.
        stress_results: Drawdown and recovery stats under the stress regime.
        cumulative_returns: Daily cumulative return series for charting.

        verifier_result: Output of ``engine.verifier.verify_pair()``.
        rejection_log: Append-only list of ``{"long", "short", "reason"}`` dicts
            from prior failed verification attempts.
        attempt_count: How many screener→quant→verifier loops have run.
        max_attempts: Hard cap on retry loops to prevent infinite cycling.

        approved: ``True`` iff the current pair passed verification.
        cro_report: Markdown executive memo produced by the CRO Reporter.
        fno_execution: F&O lot sizing and execution plan dict.
    """

    # ── Macro intent & provenance ────────────────────────────────────────
    thesis: str = ""
    target_sector: str = ""
    benchmark: str = "^NSEI"
    lookback_days: int = 252
    stress_regime: str = "COVID_2020"
    data_source: Literal["yfinance", "cache", "synthetic_fallback"] = "yfinance"

    # ── Screening results ────────────────────────────────────────────────
    sector_tickers: list[str] = Field(default_factory=list)
    long_candidates: list[dict] = Field(default_factory=list)
    short_candidates: list[dict] = Field(default_factory=list)
    selected_long: str = ""
    selected_short: str = ""

    # ── Quant results ────────────────────────────────────────────────────
    pair_metrics: dict = Field(default_factory=dict)
    weights: dict = Field(default_factory=dict)
    unhedged_stats: dict = Field(default_factory=dict)
    hedged_stats: dict = Field(default_factory=dict)
    stress_results: dict = Field(default_factory=dict)
    cumulative_returns: dict = Field(default_factory=dict)

    # ── Verification ─────────────────────────────────────────────────────
    verifier_result: dict = Field(default_factory=dict)
    rejection_log: list[dict] = Field(default_factory=list)
    attempt_count: int = 0
    max_attempts: int = 5

    # ── Final output ─────────────────────────────────────────────────────
    approved: bool = False
    cro_report: str = ""
    fno_execution: dict = Field(default_factory=dict)


class StateProxy(dict):
    """Robust dual dict / attribute proxy wrapper for HedgeBuilderState.

    Solves the LangGraph StateProxy and state fragmentation issues:
    1. **Dual Access**: Supports both dot attribute access (``state.thesis``)
       and dict item access (``state["thesis"]`` / ``state.get("thesis")``).
    2. **Field Completeness**: Populates schema default values for missing keys,
       preventing ``KeyError`` or ``AttributeError`` across graph transitions.
    3. **Mutation Isolation**: Deep-copies nested mutable structures (lists, dicts)
       to avoid unintended cross-iteration in-place mutations.
    4. **LangGraph Compatibility**: Inherits from ``dict`` so LangGraph, json
       serialization, and existing node return contracts work seamlessly.
    """

    def __init__(self, data: Any = None, **kwargs: Any) -> None:
        super().__init__()
        # 1. Initialize all schema default fields
        for k, v in STATE_SCHEMA_DEFAULTS.items():
            self[k] = copy.deepcopy(v) if isinstance(v, (list, dict)) else v

        # 2. Ingest input data
        if data is not None:
            if isinstance(data, dict):
                for k, v in data.items():
                    self[k] = copy.deepcopy(v) if isinstance(v, (list, dict)) else v
            else:
                for k in STATE_SCHEMA_DEFAULTS:
                    if hasattr(data, k):
                        val = getattr(data, k)
                        self[k] = copy.deepcopy(val) if isinstance(val, (list, dict)) else val

        # 3. Ingest keyword overrides
        for k, v in kwargs.items():
            self[k] = copy.deepcopy(v) if isinstance(v, (list, dict)) else v

    def __getattr__(self, name: str) -> Any:
        if name in self:
            return self[name]
        if name in STATE_SCHEMA_DEFAULTS:
            return copy.deepcopy(STATE_SCHEMA_DEFAULTS[name])
        raise AttributeError(f"'StateProxy' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def __delattr__(self, name: str) -> None:
        if name in self:
            del self[name]
        else:
            raise AttributeError(f"'StateProxy' object has no attribute '{name}'")

    def get(self, key: str, default: Any = None) -> Any:
        """Safely retrieve key with fallback to schema default or custom default."""
        if key in self:
            return self[key]
        if default is not None:
            return default
        if key in STATE_SCHEMA_DEFAULTS:
            return copy.deepcopy(STATE_SCHEMA_DEFAULTS[key])
        return default

    def to_dict(self) -> dict[str, Any]:
        """Convert proxy back into a plain Python dictionary."""
        return dict(self)

    def to_state(self) -> HedgeBuilderState:
        """Cast proxy into a typed HedgeBuilderState dictionary."""
        return HedgeBuilderState(self)

    def copy(self) -> StateProxy:
        """Create a deep, mutation-isolated copy of this StateProxy."""
        return StateProxy(self)


def wrap_state(state: Any) -> StateProxy:
    """Normalize and wrap any state object into a safe StateProxy instance.

    Guarantees:
    - Never throws an error on None or empty state.
    - Idempotent: returns existing StateProxy without re-wrapping.
    - Transparently accepts dict, MessagesState, or Pydantic instances.

    Args:
        state: State dictionary, MessagesState, or existing StateProxy.

    Returns:
        A fully initialized, schema-complete StateProxy.
    """
    if isinstance(state, StateProxy):
        return state
    return StateProxy(state)
