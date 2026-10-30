"""Pydantic state schema for the Market-Neutral Hedge Builder graph.

This module defines :class:`HedgeBuilderState`, the single shared state object
that flows through every node in the LangGraph ``StateGraph``.  It extends
:class:`langgraph.graph.MessagesState` so that the built-in ``messages`` channel
is available for inter-agent chat history while all domain-specific fields are
strongly typed via Pydantic.

Design decisions
----------------
* **Flat namespace** – every node reads / writes the same top-level keys.
  This avoids deeply nested dicts and keeps conditional routing simple.
* **Immutable defaults via ``Field(default_factory=...)``** – prevents the
  classic mutable-default-argument footgun.
* **``rejection_log``** – an append-only audit trail so the CRO Reporter
  can narrate *which* pairs were tried and *why* they were rejected.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from langgraph.graph import MessagesState


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

    # ── Macro intent ─────────────────────────────────────────────────────
    thesis: str = ""
    target_sector: str = ""
    benchmark: str = "^NSEI"
    lookback_days: int = 252
    stress_regime: str = "COVID_2020"

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
